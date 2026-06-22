"""
Report Distribution API

Distributes biweekly report HTML: upload to S3, generate a summary email, and
send via AWS SES (test sends + batched broadcast to subscribers). Subscribers
are stored in the `email_subscribers` MongoDB collection.

Ported from the standalone biweekly-reporter project (Express/TS) into FastAPI,
reusing All-Thing-Eye's admin auth (`require_admin`) and MongoDB.
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, EmailStr

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.integrations.aws_email import BATCH_DELAY_SECONDS, BATCH_SIZE, send_batch, send_email
from src.integrations.aws_s3 import upload_report_html
from src.report.summary_email import build_summary_email_html, parse_report_metadata
from src.utils.logger import get_logger
from backend.middleware.jwt_auth import require_admin

logger = get_logger(__name__)

router = APIRouter()

COLLECTION = "email_subscribers"
JOBS_COLLECTION = "report_distributions"  # broadcast job/progress + send history


def get_mongo():
    """Get MongoDB manager from main.py"""
    from backend.main import mongo_manager

    return mongo_manager


async def _subscribers_collection():
    db = get_mongo().async_db
    col = db[COLLECTION]
    # Idempotent; ensures uniqueness on email
    await col.create_index("email", unique=True)
    return col


def _jobs_collection():
    return get_mongo().async_db[JOBS_COLLECTION]


# ---------- Models ----------


class ReportStat(BaseModel):
    value: str
    label: str


class UploadRequest(BaseModel):
    html: str
    report_number: Optional[str] = None
    report_title: Optional[str] = None


class PreviewEmailRequest(BaseModel):
    report_url: str
    stats: List[ReportStat] = []
    summary: str = ""
    report_number: str = ""
    date_range: str = ""


class SendTestRequest(BaseModel):
    to: List[EmailStr]
    subject: str
    html: str


class SendAllRequest(BaseModel):
    subject: str
    html: str


class SubscriberCreate(BaseModel):
    email: EmailStr
    name: Optional[str] = None


# ---------- Report upload + email preview ----------


@router.post("/upload")
async def upload_report(
    body: UploadRequest, _admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    """
    Upload report HTML to S3 and return its public URL plus parsed KPI
    stats and metadata (title, report number, date range, executive summary).
    """
    if not body.html or not body.html.strip():
        raise HTTPException(status_code=400, detail="HTML content is required.")

    metadata = parse_report_metadata(body.html)
    report_number = body.report_number or metadata.get("report_number") or "0"

    try:
        report_url = await run_in_threadpool(
            upload_report_html, body.html, report_number
        )
    except RuntimeError as e:
        # Missing AWS config
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.error(f"S3 upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    return {
        "success": True,
        "report_url": report_url,
        "stats": metadata["stats"],
        "executive_summary": metadata["executive_summary"],
        "metadata": metadata,
        "html_size": len(body.html),
    }


@router.post("/preview-email")
async def preview_email(
    body: PreviewEmailRequest, _admin: str = Depends(require_admin)
) -> Dict[str, str]:
    """Render the summary/notification email HTML (no sending)."""
    html = build_summary_email_html(
        report_url=body.report_url,
        stats=[s.model_dump() for s in body.stats],
        summary=body.summary,
        report_number=body.report_number,
        date_range=body.date_range,
    )
    return {"html": html}


# ---------- Sending ----------


@router.post("/send-test")
async def send_test(
    body: SendTestRequest, _admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    """Send the email to one or more test recipients (synchronous)."""
    if not body.to:
        raise HTTPException(status_code=400, detail="At least one recipient is required.")
    if not body.subject:
        raise HTTPException(status_code=400, detail="Subject is required.")

    recipients = [str(e) for e in body.to]
    try:
        await run_in_threadpool(send_email, recipients, body.subject, body.html)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.error(f"Test email failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send test email: {e}")

    return {"success": True, "message": f"Test email sent to {len(recipients)} recipient(s)."}


async def _run_broadcast(job_id: ObjectId, recipients: List[str], subject: str, html: str) -> None:
    """
    Background broadcast with live progress persisted to MongoDB.

    Sends in BCC batches; after each batch increments the job doc's sent/failed
    counters so the frontend can poll `/send-all/status/{job_id}` for real-time
    n/total progress. Runs in the event loop (SES calls offloaded to a thread).
    """
    jobs = _jobs_collection()
    for i in range(0, len(recipients), BATCH_SIZE):
        batch = recipients[i : i + BATCH_SIZE]
        try:
            await run_in_threadpool(send_batch, batch, subject, html)
            await jobs.update_one({"_id": job_id}, {"$inc": {"sent": len(batch)}})
        except Exception as e:  # noqa: BLE001 - record and continue to next batch
            await jobs.update_one(
                {"_id": job_id},
                {"$inc": {"failed": len(batch)}, "$push": {"errors": f"batch@{i}: {e}"}},
            )
            logger.error(f"❌ Broadcast batch@{i} failed (job {job_id}): {e}")
        # Delay between batches (skip after the last one) to respect SES rate limit
        if i + BATCH_SIZE < len(recipients):
            await asyncio.sleep(BATCH_DELAY_SECONDS)

    await jobs.update_one(
        {"_id": job_id},
        {"$set": {"status": "done", "finished_at": datetime.now(timezone.utc)}},
    )
    logger.info(f"📨 Broadcast job {job_id} complete.")


@router.post("/send-all")
async def send_all(
    body: SendAllRequest,
    background_tasks: BackgroundTasks,
    _admin: str = Depends(require_admin),
) -> Dict[str, Any]:
    """
    Broadcast to all active subscribers in the background. Creates a job doc
    for progress tracking and returns its job_id + total immediately; poll
    `/send-all/status/{job_id}` for live n/total progress.
    """
    if not body.subject:
        raise HTTPException(status_code=400, detail="Subject is required.")
    if not body.html:
        raise HTTPException(status_code=400, detail="Email HTML is required.")

    col = await _subscribers_collection()
    cursor = col.find({"status": "active"}, {"email": 1})
    recipients = [doc["email"] async for doc in cursor]

    if not recipients:
        raise HTTPException(status_code=400, detail="No active subscribers.")

    job = {
        "subject": body.subject,
        "total": len(recipients),
        "sent": 0,
        "failed": 0,
        "status": "running",
        "admin": _admin,
        "errors": [],
        "started_at": datetime.now(timezone.utc),
    }
    result = await _jobs_collection().insert_one(job)
    job_id = result.inserted_id

    background_tasks.add_task(_run_broadcast, job_id, recipients, body.subject, body.html)
    logger.info(f"📨 Queued broadcast job {job_id} to {len(recipients)} subscribers by {_admin}")

    return {
        "success": True,
        "job_id": str(job_id),
        "total": len(recipients),
        "message": f"Broadcasting to {len(recipients)} subscribers.",
    }


@router.get("/send-all/status/{job_id}")
async def send_all_status(
    job_id: str, _admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    """Return live progress for a broadcast job (sent/total + percent)."""
    try:
        oid = ObjectId(job_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid job id.")

    job = await _jobs_collection().find_one({"_id": oid})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    total = job.get("total", 0)
    sent = job.get("sent", 0)
    failed = job.get("failed", 0)
    processed = sent + failed
    percent = round(100 * processed / total) if total else 0

    return {
        "job_id": job_id,
        "status": job.get("status", "running"),
        "total": total,
        "sent": sent,
        "failed": failed,
        "percent": percent,
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
    }


# ---------- Subscriber management ----------


@router.get("/subscribers")
async def list_subscribers(
    _admin: str = Depends(require_admin),
) -> Dict[str, Any]:
    """List subscribers with active/total counts."""
    col = await _subscribers_collection()
    subscribers: List[Dict[str, Any]] = []
    async for doc in col.find({}).sort("created_at", -1):
        subscribers.append(
            {
                "id": str(doc["_id"]),
                "email": doc.get("email"),
                "name": doc.get("name"),
                "source": doc.get("source"),
                "status": doc.get("status", "active"),
                "created_at": doc.get("created_at"),
            }
        )
    active = sum(1 for s in subscribers if s["status"] == "active")
    return {"total": len(subscribers), "active": active, "subscribers": subscribers}


@router.post("/subscribers")
async def add_subscriber(
    body: SubscriberCreate, _admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    """Add (or re-activate) a single subscriber."""
    col = await _subscribers_collection()
    email = str(body.email).strip().lower()

    existing = await col.find_one({"email": email})
    if existing:
        # Re-activate if previously unsubscribed
        await col.update_one(
            {"_id": existing["_id"]},
            {"$set": {"status": "active", "name": body.name or existing.get("name")}},
        )
        return {"success": True, "id": str(existing["_id"]), "reactivated": True}

    doc = {
        "email": email,
        "name": body.name,
        "source": "manual",
        "status": "active",
        "created_at": datetime.now(timezone.utc),
    }
    result = await col.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id), "reactivated": False}


@router.delete("/subscribers/{subscriber_id}")
async def remove_subscriber(
    subscriber_id: str, _admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    """Soft-unsubscribe a subscriber (status -> unsubscribed)."""
    col = await _subscribers_collection()
    try:
        oid = ObjectId(subscriber_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid subscriber id.")

    result = await col.update_one(
        {"_id": oid},
        {"$set": {"status": "unsubscribed", "unsubscribed_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Subscriber not found.")
    return {"success": True}
