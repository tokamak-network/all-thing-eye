"""
Report Distribution API

Distributes biweekly report HTML: upload to S3, generate a summary email, and
send via AWS SES (test sends + batched broadcast to subscribers). Subscribers
are stored in the `email_subscribers` MongoDB collection.

Ported from the standalone biweekly-reporter project (Express/TS) into FastAPI,
reusing All-Thing-Eye's admin auth (`require_admin`) and MongoDB.
"""

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

from src.integrations.aws_email import send_bulk, send_email
from src.integrations.aws_s3 import upload_report_html
from src.report.summary_email import build_summary_email_html, parse_report_metadata
from src.utils.logger import get_logger
from backend.middleware.jwt_auth import require_admin

logger = get_logger(__name__)

router = APIRouter()

COLLECTION = "email_subscribers"


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


@router.post("/send-all")
async def send_all(
    body: SendAllRequest,
    background_tasks: BackgroundTasks,
    _admin: str = Depends(require_admin),
) -> Dict[str, Any]:
    """
    Broadcast the email to all active subscribers. Runs in the background
    (batched) and returns immediately with the queued recipient count.
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

    background_tasks.add_task(send_bulk, recipients, body.subject, body.html)
    logger.info(f"📨 Queued broadcast to {len(recipients)} subscribers by {_admin}")

    return {
        "success": True,
        "queued_count": len(recipients),
        "message": f"Queued broadcast to {len(recipients)} subscribers.",
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
