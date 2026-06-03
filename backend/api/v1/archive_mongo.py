"""
Archive API — retired members data (profiles, artifacts, recordings).

Reads from the separate `ati_archive` MongoDB database (mongo.archive_async_db).
Read-only. All endpoints require admin (Depends(require_admin)).
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
import re

from src.utils.logger import get_logger
from backend.middleware.jwt_auth import require_admin

logger = get_logger(__name__)
router = APIRouter()


def get_mongo():
    from backend.main import mongo_manager

    return mongo_manager


def _archive_db():
    return get_mongo().archive_async_db


def _rx(value: str) -> Dict[str, Any]:
    """Case-insensitive 'contains' regex filter."""
    return {"$regex": re.escape(value), "$options": "i"}


@router.get("/archive/stats")
async def archive_stats(_admin: str = Depends(require_admin)) -> Dict[str, Any]:
    """Summary counts for the archive database."""
    db = _archive_db()
    members = await db["archive_members"].count_documents({})
    artifacts = await db["archive_artifacts"].count_documents({})
    recordings = await db["archive_recordings"].count_documents({})

    # recording date range
    first = await db["archive_recordings"].find_one({"date": {"$ne": ""}}, sort=[("date", 1)])
    last = await db["archive_recordings"].find_one({"date": {"$ne": ""}}, sort=[("date", -1)])
    return {
        "members": members,
        "artifacts": artifacts,
        "recordings": recordings,
        "recordings_date_range": {
            "first": (first or {}).get("date"),
            "last": (last or {}).get("date"),
        },
    }


@router.get("/archive/members")
async def list_archive_members(
    q: Optional[str] = None,
    era: Optional[str] = None,
    team: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    _admin: str = Depends(require_admin),
) -> Dict[str, Any]:
    """List retired members with optional filters."""
    db = _archive_db()
    flt: Dict[str, Any] = {}
    if q:
        flt["$or"] = [
            {"member_name": _rx(q)},
            {"real_name_en": _rx(q)},
            {"real_name_kr": _rx(q)},
            {"github_username": _rx(q)},
        ]
    if era:
        flt["active_era"] = era
    if team:
        flt["vault_teams"] = _rx(team)
    if status:
        flt["status"] = status

    total = await db["archive_members"].count_documents(flt)
    cursor = (
        db["archive_members"]
        .find(flt, {"_id": 0})
        .sort("artifact_count", -1)
        .skip(offset)
        .limit(limit)
    )
    items = [m async for m in cursor]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/archive/members/{member_key}")
async def get_archive_member(
    member_key: str, _admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    """Member profile + their artifacts grouped by source + meeting links."""
    db = _archive_db()
    member = await db["archive_members"].find_one({"member_key": member_key}, {"_id": 0})
    if not member:
        raise HTTPException(status_code=404, detail=f"Archive member not found: {member_key}")

    # artifacts for this member (cap to a reasonable number, newest first)
    cursor = (
        db["archive_artifacts"]
        .find({"member_key": member_key}, {"_id": 0})
        .sort("date", -1)
        .limit(2000)
    )
    artifacts = [a async for a in cursor]

    by_source: Dict[str, int] = {}
    meetings: List[Dict[str, Any]] = []
    for a in artifacts:
        by_source[a.get("source", "?")] = by_source.get(a.get("source", "?"), 0) + 1
        if a.get("source") == "google_meet":
            meetings.append(a)

    return {
        "member": member,
        "artifact_count": len(artifacts),
        "by_source": by_source,
        "artifacts": artifacts,
        "meetings": meetings[:200],
    }


@router.get("/archive/artifacts")
async def list_archive_artifacts(
    member: Optional[str] = None,
    source: Optional[str] = None,
    project: Optional[str] = None,
    type: Optional[str] = None,
    q: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    _admin: str = Depends(require_admin),
) -> Dict[str, Any]:
    """Search artifacts across retired members."""
    db = _archive_db()
    flt: Dict[str, Any] = {}
    if member:
        flt["member_key"] = member
    if source:
        flt["source"] = source
    if project:
        flt["project"] = _rx(project)
    if type:
        flt["type"] = type
    if q:
        flt["title"] = _rx(q)
    if date_from or date_to:
        rng: Dict[str, Any] = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to
        flt["date"] = rng

    total = await db["archive_artifacts"].count_documents(flt)
    cursor = (
        db["archive_artifacts"].find(flt, {"_id": 0}).sort("date", -1).skip(offset).limit(limit)
    )
    items = [a async for a in cursor]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/archive/recordings")
async def list_archive_recordings(
    category: Optional[str] = None,
    q: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    _admin: str = Depends(require_admin),
) -> Dict[str, Any]:
    """Recording/transcript file catalog."""
    db = _archive_db()
    flt: Dict[str, Any] = {}
    if category:
        flt["category"] = category
    if q:
        flt["title"] = _rx(q)
    if date_from or date_to:
        rng: Dict[str, Any] = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to
        flt["date"] = rng

    total = await db["archive_recordings"].count_documents(flt)
    cursor = (
        db["archive_recordings"].find(flt, {"_id": 0}).sort("date", -1).skip(offset).limit(limit)
    )
    items = [r async for r in cursor]
    return {"total": total, "limit": limit, "offset": offset, "items": items}
