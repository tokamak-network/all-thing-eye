"""
Weekly Output Schedules API endpoints

Provides CRUD operations for weekly output bot schedules stored in MongoDB.
Allows creating schedules for any channel with custom member selection and timing.
"""

from fastapi import APIRouter, HTTPException, Request
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from bson import ObjectId

from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ============================================================
# Pydantic models
# ============================================================

class ScheduleTime(BaseModel):
    """Time configuration for a scheduled action"""
    day_of_week: str = Field(..., description="Day of week: mon, tue, wed, thu, fri, sat, sun")
    hour: int = Field(..., ge=0, le=23, description="Hour (0-23)")
    minute: int = Field(0, ge=0, le=59, description="Minute (0-59)")


class ScheduleCreateRequest(BaseModel):
    """Request model for creating a new schedule"""
    name: str = Field(..., description="Schedule display name")
    channel_id: str = Field(..., description="Slack channel ID")
    channel_name: str = Field(..., description="Slack channel name (for display)")
    member_ids: List[str] = Field(default_factory=list, description="List of member ObjectId strings")
    thread_schedule: ScheduleTime = Field(..., description="When to create the weekly thread")
    reminder_schedule: ScheduleTime = Field(..., description="When to send reminder DMs")
    final_schedule: ScheduleTime = Field(..., description="When to send final reminder DMs")
    thread_message: Optional[str] = Field(None, description="Custom thread message (null = default)")
    reminder_message: Optional[str] = Field(None, description="Custom reminder message (null = default)")
    final_message: Optional[str] = Field(None, description="Custom final message (null = default)")
    is_active: bool = True


class ScheduleUpdateRequest(BaseModel):
    """Request model for updating a schedule (all fields optional)"""
    name: Optional[str] = None
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    member_ids: Optional[List[str]] = None
    thread_schedule: Optional[ScheduleTime] = None
    reminder_schedule: Optional[ScheduleTime] = None
    final_schedule: Optional[ScheduleTime] = None
    thread_message: Optional[str] = None
    reminder_message: Optional[str] = None
    final_message: Optional[str] = None
    is_active: Optional[bool] = None


class ScheduleResponse(BaseModel):
    """Response model for schedule data"""
    id: str
    name: str
    channel_id: str
    channel_name: str
    member_ids: List[str] = Field(default_factory=list)
    thread_schedule: ScheduleTime
    reminder_schedule: ScheduleTime
    final_schedule: ScheduleTime
    thread_message: Optional[str] = None
    reminder_message: Optional[str] = None
    final_message: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ScheduleListResponse(BaseModel):
    """Response model for schedule list"""
    total: int
    schedules: List[ScheduleResponse]


class MemberWithSlack(BaseModel):
    """Member info with Slack user ID for member selection"""
    id: str
    name: str
    slack_user_id: Optional[str] = None


# ============================================================
# Helpers
# ============================================================

def get_mongo():
    """Get MongoDB manager from main.py"""
    from backend.main import mongo_manager
    return mongo_manager


def doc_to_schedule_time(doc: dict) -> ScheduleTime:
    """Convert a MongoDB sub-document to ScheduleTime"""
    return ScheduleTime(
        day_of_week=doc.get("day_of_week", "thu"),
        hour=doc.get("hour", 17),
        minute=doc.get("minute", 0),
    )


def schedule_time_to_doc(st: ScheduleTime) -> dict:
    """Convert ScheduleTime to MongoDB sub-document"""
    return {"day_of_week": st.day_of_week, "hour": st.hour, "minute": st.minute}


def doc_to_response(doc: dict) -> ScheduleResponse:
    """Convert a MongoDB document to ScheduleResponse"""
    created_at = doc.get("created_at")
    if not isinstance(created_at, datetime):
        created_at = datetime.utcnow()
    updated_at = doc.get("updated_at")
    if not isinstance(updated_at, datetime):
        updated_at = datetime.utcnow()

    return ScheduleResponse(
        id=str(doc["_id"]),
        name=doc.get("name", ""),
        channel_id=doc.get("channel_id", ""),
        channel_name=doc.get("channel_name", ""),
        member_ids=[str(mid) for mid in doc.get("member_ids", [])],
        thread_schedule=doc_to_schedule_time(doc.get("thread_schedule", {})),
        reminder_schedule=doc_to_schedule_time(doc.get("reminder_schedule", {})),
        final_schedule=doc_to_schedule_time(doc.get("final_schedule", {})),
        thread_message=doc.get("thread_message"),
        reminder_message=doc.get("reminder_message"),
        final_message=doc.get("final_message"),
        is_active=doc.get("is_active", True),
        created_at=created_at,
        updated_at=updated_at,
    )


# ============================================================
# Endpoints
# ============================================================

@router.get("/schedules", response_model=ScheduleListResponse)
async def get_schedules(request: Request, active_only: bool = False):
    """Get list of all weekly output schedules"""
    try:
        mongo = get_mongo()
        db = mongo.db
        col = db["weekly_output_schedules"]

        query = {"is_active": True} if active_only else {}
        cursor = col.find(query).sort("name", 1)

        schedules = [doc_to_response(doc) for doc in cursor]

        return ScheduleListResponse(total=len(schedules), schedules=schedules)

    except Exception as e:
        logger.error(f"Error fetching schedules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch schedules: {str(e)}")


@router.get("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(request: Request, schedule_id: str):
    """Get a specific schedule by ID"""
    try:
        mongo = get_mongo()
        db = mongo.db
        col = db["weekly_output_schedules"]

        doc = col.find_one({"_id": ObjectId(schedule_id)})
        if not doc:
            raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found")

        return doc_to_response(doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching schedule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch schedule: {str(e)}")


@router.post("/schedules", response_model=ScheduleResponse, status_code=201)
async def create_schedule(request: Request, body: ScheduleCreateRequest):
    """Create a new weekly output schedule"""
    try:
        mongo = get_mongo()
        db = mongo.db
        col = db["weekly_output_schedules"]

        now = datetime.utcnow()
        schedule_doc = {
            "name": body.name,
            "channel_id": body.channel_id,
            "channel_name": body.channel_name,
            "member_ids": body.member_ids,
            "thread_schedule": schedule_time_to_doc(body.thread_schedule),
            "reminder_schedule": schedule_time_to_doc(body.reminder_schedule),
            "final_schedule": schedule_time_to_doc(body.final_schedule),
            "thread_message": body.thread_message,
            "reminder_message": body.reminder_message,
            "final_message": body.final_message,
            "is_active": body.is_active,
            "created_at": now,
            "updated_at": now,
        }

        result = col.insert_one(schedule_doc)
        schedule_doc["_id"] = result.inserted_id

        logger.info(f"Created schedule: {body.name} (channel: {body.channel_name})")
        return doc_to_response(schedule_doc)

    except Exception as e:
        logger.error(f"Error creating schedule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create schedule: {str(e)}")


@router.put("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(request: Request, schedule_id: str, body: ScheduleUpdateRequest):
    """Update an existing schedule (only provided fields)"""
    try:
        mongo = get_mongo()
        db = mongo.db
        col = db["weekly_output_schedules"]

        existing = col.find_one({"_id": ObjectId(schedule_id)})
        if not existing:
            raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found")

        update_doc = {"updated_at": datetime.utcnow()}

        if body.name is not None:
            update_doc["name"] = body.name
        if body.channel_id is not None:
            update_doc["channel_id"] = body.channel_id
        if body.channel_name is not None:
            update_doc["channel_name"] = body.channel_name
        if body.member_ids is not None:
            update_doc["member_ids"] = body.member_ids
        if body.thread_schedule is not None:
            update_doc["thread_schedule"] = schedule_time_to_doc(body.thread_schedule)
        if body.reminder_schedule is not None:
            update_doc["reminder_schedule"] = schedule_time_to_doc(body.reminder_schedule)
        if body.final_schedule is not None:
            update_doc["final_schedule"] = schedule_time_to_doc(body.final_schedule)
        if body.thread_message is not None:
            update_doc["thread_message"] = body.thread_message
        if body.reminder_message is not None:
            update_doc["reminder_message"] = body.reminder_message
        if body.final_message is not None:
            update_doc["final_message"] = body.final_message
        if body.is_active is not None:
            update_doc["is_active"] = body.is_active

        col.update_one({"_id": ObjectId(schedule_id)}, {"$set": update_doc})
        updated = col.find_one({"_id": ObjectId(schedule_id)})

        logger.info(f"Updated schedule: {schedule_id}")
        return doc_to_response(updated)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating schedule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update schedule: {str(e)}")


@router.delete("/schedules/{schedule_id}", status_code=204)
async def delete_schedule(request: Request, schedule_id: str):
    """Delete a schedule"""
    try:
        mongo = get_mongo()
        db = mongo.db
        col = db["weekly_output_schedules"]

        existing = col.find_one({"_id": ObjectId(schedule_id)})
        if not existing:
            raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found")

        col.delete_one({"_id": ObjectId(schedule_id)})
        logger.info(f"Deleted schedule: {schedule_id} ({existing.get('name', '')})")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting schedule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete schedule: {str(e)}")


@router.get("/members-with-slack", response_model=List[MemberWithSlack])
async def get_members_with_slack(request: Request):
    """Get all active members with their Slack user IDs (for member selection dropdown)"""
    try:
        mongo = get_mongo()
        db = mongo.db

        members_cursor = db["members"].find({"is_active": {"$ne": False}}).sort("name", 1)

        result = []
        for m in members_cursor:
            member_id = str(m["_id"])
            name = m.get("name", "Unknown")

            # Resolve Slack user ID (3-step fallback)
            slack_user_id = m.get("slack_id")

            if not slack_user_id:
                ident = db["member_identifiers"].find_one({
                    "member_name": name,
                    "source": "slack",
                })
                if ident:
                    slack_user_id = ident.get("identifier_value")

            if not slack_user_id:
                for ident in m.get("identifiers", []):
                    if ident.get("source_type") == "slack":
                        slack_user_id = ident.get("source_user_id")
                        break

            result.append(MemberWithSlack(
                id=member_id,
                name=name,
                slack_user_id=slack_user_id,
            ))

        return result

    except Exception as e:
        logger.error(f"Error fetching members with Slack IDs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch members: {str(e)}")
