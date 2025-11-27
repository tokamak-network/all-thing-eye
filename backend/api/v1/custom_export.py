"""
Custom Export API endpoints

Provides filtered raw activity data for custom export builder
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, timedelta
from bson import ObjectId
import csv
import io

from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


class CustomExportRequest(BaseModel):
    """Request model for custom export preview"""
    selected_members: List[str] = []
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    project: Optional[str] = None
    selected_fields: List[str] = []
    limit: int = 50
    offset: int = 0


def get_mongo():
    """Get MongoDB manager from main.py"""
    from backend.main import mongo_manager
    return mongo_manager


def get_identifiers_for_member(member_name: str, db) -> dict:
    """Get all identifiers for a member across different sources"""
    identifiers = {"github": [], "slack": [], "notion": [], "drive": []}
    
    # Use same field names as activities_mongo.py: source, identifier_value, member_name
    member_identifiers = db["member_identifiers"].find({"member_name": member_name})
    for identifier in member_identifiers:
        source = identifier.get("source", "").lower()
        identifier_value = identifier.get("identifier_value")
        if source in identifiers and identifier_value:
            identifiers[source].append(identifier_value)
    
    return identifiers


def get_source_from_field(field: str) -> str:
    """Extract source type from field name"""
    if field.startswith("github."):
        return "github"
    elif field.startswith("slack."):
        return "slack"
    elif field.startswith("notion."):
        return "notion"
    elif field.startswith("drive."):
        return "drive"
    elif field.startswith("member."):
        return "member"
    return ""


@router.post("/custom-export/preview")
async def get_custom_export_preview(request: Request, body: CustomExportRequest):
    """
    Get filtered raw activity data based on selected members and fields
    
    Returns actual activity records, not aggregated statistics
    """
    try:
        mongo = get_mongo()
        db = mongo.db
        
        # Determine which sources to query based on selected fields
        sources_needed = set()
        for field in body.selected_fields:
            source = get_source_from_field(field)
            if source and source != "member":
                sources_needed.add(source)
        
        # If no specific source fields selected, default to showing member info
        if not sources_needed:
            sources_needed = {"github", "slack", "notion", "drive"}
        
        # Build date filter - convert string to datetime for MongoDB comparison
        date_filter = {}
        if body.start_date:
            try:
                date_filter["$gte"] = datetime.fromisoformat(body.start_date)
            except ValueError:
                date_filter["$gte"] = body.start_date
        if body.end_date:
            try:
                # Add 1 day to include the entire end date
                end_dt = datetime.fromisoformat(body.end_date) + timedelta(days=1)
                date_filter["$lt"] = end_dt
            except ValueError:
                date_filter["$lte"] = body.end_date + "T23:59:59"
        
        # Get members to filter
        members_to_filter = body.selected_members if body.selected_members else []
        
        results = []
        
        # Get member info map
        member_info_map = {}
        if members_to_filter:
            for name in members_to_filter:
                member = db["members"].find_one({"name": name})
                if member:
                    member_info_map[name] = {
                        "email": member.get("email"),
                        "role": member.get("role"),
                        "team": member.get("team")
                    }
        
        # Query each source
        for source in sources_needed:
            if source == "github":
                results.extend(await fetch_github_data(db, members_to_filter, date_filter, member_info_map))
            elif source == "slack":
                results.extend(await fetch_slack_data(db, members_to_filter, date_filter, member_info_map))
            elif source == "notion":
                results.extend(await fetch_notion_data(db, members_to_filter, date_filter, member_info_map))
            elif source == "drive":
                results.extend(await fetch_drive_data(db, members_to_filter, date_filter, member_info_map))
        
        # Sort by timestamp descending
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Apply pagination
        total_count = len(results)
        paginated_results = results[body.offset:body.offset + body.limit]
        has_more = (body.offset + body.limit) < total_count
        
        return {
            "success": True,
            "data": paginated_results,
            "total": total_count,
            "offset": body.offset,
            "limit": body.limit,
            "has_more": has_more,
            "filters": {
                "start_date": body.start_date,
                "end_date": body.end_date,
                "project": body.project,
                "selected_members": body.selected_members,
                "selected_fields": body.selected_fields,
                "sources_queried": list(sources_needed)
            }
        }
        
    except Exception as e:
        logger.error(f"Error in custom export preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def fetch_github_data(db, members: List[str], date_filter: dict, member_info_map: dict) -> List[dict]:
    """Fetch GitHub commits and PRs for selected members"""
    results = []
    
    for member_name in members:
        identifiers = get_identifiers_for_member(member_name, db)
        member_info = member_info_map.get(member_name, {})
        
        # Build query for commits (use author_name field like activities_mongo.py)
        commit_query = {}
        if identifiers["github"]:
            commit_query["author_name"] = {"$in": identifiers["github"]}
        else:
            # Fallback: exact match on member name
            commit_query["author_name"] = member_name
        
        if date_filter:
            commit_query["date"] = date_filter
        
        # Fetch commits (no limit for full export)
        commits = list(db["github_commits"].find(commit_query).sort("date", -1))
        for commit in commits:
            results.append({
                "source": "github",
                "type": "commit",
                "member_name": member_name,
                "member_email": member_info.get("email"),
                "timestamp": commit.get("date"),
                "repository": commit.get("repository"),
                "message": commit.get("message", "")[:200],
                "additions": commit.get("additions", 0),
                "deletions": commit.get("deletions", 0),
                "sha": commit.get("sha", "")[:8],
            })
        
        # Fetch PRs (use author field like activities_mongo.py)
        pr_query = {}
        if identifiers["github"]:
            pr_query["author"] = {"$in": identifiers["github"]}
        else:
            # Fallback: exact match on member name
            pr_query["author"] = member_name
        
        if date_filter:
            pr_query["created_at"] = date_filter
        
        prs = list(db["github_pull_requests"].find(pr_query).sort("created_at", -1))
        for pr in prs:
            results.append({
                "source": "github",
                "type": "pull_request",
                "member_name": member_name,
                "member_email": member_info.get("email"),
                "timestamp": pr.get("created_at"),
                "repository": pr.get("repository"),
                "title": pr.get("title"),
                "state": pr.get("state"),
                "pr_number": pr.get("number"),
            })
    
    return results


async def fetch_slack_data(db, members: List[str], date_filter: dict, member_info_map: dict) -> List[dict]:
    """Fetch Slack messages for selected members"""
    results = []
    
    for member_name in members:
        identifiers = get_identifiers_for_member(member_name, db)
        member_info = member_info_map.get(member_name, {})
        
        # Build query
        query = {}
        or_conditions = []
        if identifiers["slack"]:
            or_conditions.append({"user_id": {"$in": identifiers["slack"]}})
            or_conditions.append({"user_email": {"$in": identifiers["slack"]}})
        or_conditions.append({"user_name": {"$regex": f"^{member_name}", "$options": "i"}})
        
        query["$or"] = or_conditions
        
        if date_filter:
            query["posted_at"] = date_filter
        
        messages = list(db["slack_messages"].find(query).sort("posted_at", -1))
        for msg in messages:
            results.append({
                "source": "slack",
                "type": "message",
                "member_name": member_name,
                "member_email": member_info.get("email"),
                "timestamp": msg.get("posted_at"),
                "channel": msg.get("channel_name"),
                "text": (msg.get("text") or "")[:300],
                "has_thread": bool(msg.get("thread_ts")),
                "reactions_count": len(msg.get("reactions", [])),
            })
    
    return results


async def fetch_notion_data(db, members: List[str], date_filter: dict, member_info_map: dict) -> List[dict]:
    """Fetch Notion pages for selected members"""
    results = []
    
    for member_name in members:
        identifiers = get_identifiers_for_member(member_name, db)
        member_info = member_info_map.get(member_name, {})
        
        # Build query
        query = {}
        or_conditions = []
        if identifiers["notion"]:
            or_conditions.append({"created_by.id": {"$in": identifiers["notion"]}})
            or_conditions.append({"created_by.email": {"$in": identifiers["notion"]}})
        or_conditions.append({"created_by.name": {"$regex": f"^{member_name}", "$options": "i"}})
        
        query["$or"] = or_conditions
        
        if date_filter:
            query["created_time"] = date_filter
        
        pages = list(db["notion_pages"].find(query).sort("created_time", -1))
        for page in pages:
            # Get title from properties
            title = ""
            props = page.get("properties", {})
            for prop_name, prop_value in props.items():
                if prop_value.get("type") == "title":
                    title_arr = prop_value.get("title", [])
                    if title_arr:
                        title = title_arr[0].get("plain_text", "")
                    break
            
            results.append({
                "source": "notion",
                "type": "page",
                "member_name": member_name,
                "member_email": member_info.get("email"),
                "timestamp": page.get("created_time"),
                "title": title or page.get("id", "Untitled"),
                "last_edited": page.get("last_edited_time"),
                "parent_type": page.get("parent", {}).get("type"),
            })
    
    return results


async def fetch_drive_data(db, members: List[str], date_filter: dict, member_info_map: dict) -> List[dict]:
    """Fetch Google Drive activities for selected members"""
    results = []
    
    for member_name in members:
        identifiers = get_identifiers_for_member(member_name, db)
        member_info = member_info_map.get(member_name, {})
        
        # Build query for drive activities
        query = {}
        or_conditions = []
        if identifiers["drive"]:
            or_conditions.append({"actor_email": {"$in": identifiers["drive"]}})
        or_conditions.append({"actor_name": {"$regex": f"^{member_name}", "$options": "i"}})
        
        query["$or"] = or_conditions
        
        if date_filter:
            query["activity_time"] = date_filter
        
        activities = list(db["drive_activities"].find(query).sort("activity_time", -1))
        for activity in activities:
            results.append({
                "source": "drive",
                "type": activity.get("activity_type", "activity"),
                "member_name": member_name,
                "member_email": member_info.get("email"),
                "timestamp": activity.get("activity_time"),
                "file_name": activity.get("file_name"),
                "file_type": activity.get("mime_type"),
                "action": activity.get("action"),
            })
    
    return results


@router.get("/custom-export/members")
async def get_export_members(request: Request):
    """
    Get list of all members with their emails for custom export selection
    """
    try:
        mongo = get_mongo()
        db = mongo.db
        
        members = list(db["members"].find({}, {"name": 1, "email": 1, "role": 1, "team": 1}))
        
        return {
            "success": True,
            "members": [
                {
                    "name": m.get("name"),
                    "email": m.get("email"),
                    "role": m.get("role"),
                    "team": m.get("team")
                }
                for m in members
            ],
            "total": len(members)
        }
        
    except Exception as e:
        logger.error(f"Error getting members for export: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/custom-export/csv")
async def export_custom_csv(request: Request, body: CustomExportRequest):
    """
    Export filtered raw data as CSV
    """
    try:
        # Get preview data (full, not limited)
        mongo = get_mongo()
        db = mongo.db
        
        # Determine which sources to query
        sources_needed = set()
        for field in body.selected_fields:
            source = get_source_from_field(field)
            if source and source != "member":
                sources_needed.add(source)
        
        if not sources_needed:
            sources_needed = {"github", "slack", "notion", "drive"}
        
        # Build date filter - convert string to datetime for MongoDB comparison
        date_filter = {}
        if body.start_date:
            try:
                date_filter["$gte"] = datetime.fromisoformat(body.start_date)
            except ValueError:
                date_filter["$gte"] = body.start_date
        if body.end_date:
            try:
                end_dt = datetime.fromisoformat(body.end_date) + timedelta(days=1)
                date_filter["$lt"] = end_dt
            except ValueError:
                date_filter["$lte"] = body.end_date + "T23:59:59"
        
        members_to_filter = body.selected_members if body.selected_members else []
        
        # Get member info
        member_info_map = {}
        if members_to_filter:
            for name in members_to_filter:
                member = db["members"].find_one({"name": name})
                if member:
                    member_info_map[name] = {
                        "email": member.get("email"),
                        "role": member.get("role"),
                        "team": member.get("team")
                    }
        
        results = []
        for source in sources_needed:
            if source == "github":
                results.extend(await fetch_github_data(db, members_to_filter, date_filter, member_info_map))
            elif source == "slack":
                results.extend(await fetch_slack_data(db, members_to_filter, date_filter, member_info_map))
            elif source == "notion":
                results.extend(await fetch_notion_data(db, members_to_filter, date_filter, member_info_map))
            elif source == "drive":
                results.extend(await fetch_drive_data(db, members_to_filter, date_filter, member_info_map))
        
        # Sort by timestamp
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        if not results:
            raise HTTPException(status_code=404, detail="No data found with the given filters")
        
        # Create CSV
        output = io.StringIO()
        
        # Get all possible field names from results
        all_fields = set()
        for row in results:
            all_fields.update(row.keys())
        
        # Order fields logically
        ordered_fields = ["source", "type", "member_name", "member_email", "timestamp"]
        for field in sorted(all_fields):
            if field not in ordered_fields:
                ordered_fields.append(field)
        
        writer = csv.DictWriter(output, fieldnames=ordered_fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(results)
        
        output.seek(0)
        
        # Generate filename
        filename = f"custom_export_{body.start_date or 'all'}_{body.end_date or 'all'}.csv"
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))
