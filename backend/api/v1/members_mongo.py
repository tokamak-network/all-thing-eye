"""
Members Management API
Handles CRUD operations for team members
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime
from src.utils.logger import get_logger
from backend.middleware.jwt_auth import require_admin

logger = get_logger(__name__)
router = APIRouter()


# Get MongoDB manager instance
def get_mongo():
    from backend.main import mongo_manager
    return mongo_manager


class MemberIdentifier(BaseModel):
    """Member identifier model"""
    identifier_type: str
    identifier_value: str


class MemberCreate(BaseModel):
    """Member creation model"""
    name: str
    email: EmailStr
    github_id: Optional[str] = None
    slack_id: Optional[str] = None
    notion_id: Optional[str] = None
    role: Optional[str] = None
    project: Optional[str] = None


class MemberUpdate(BaseModel):
    """Member update model"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    github_id: Optional[str] = None
    slack_id: Optional[str] = None
    notion_id: Optional[str] = None
    role: Optional[str] = None
    project: Optional[str] = None


@router.get("/members")
async def get_members(
    request: Request,
    _admin: str = Depends(require_admin)
) -> List[Dict[str, Any]]:
    """
    Get all team members with their identifiers
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        # Get all members
        members_cursor = db["members"].find({})
        members = []
        
        async for member in members_cursor:
            member_id = str(member["_id"])
            
            # Get member identifiers
            identifiers_cursor = db["member_identifiers"].find({"member_id": member_id})
            identifiers = {}
            
            async for identifier in identifiers_cursor:
                identifiers[identifier["identifier_type"]] = identifier["identifier_value"]
            
            members.append({
                "id": member_id,
                "name": member.get("name"),
                "email": member.get("email"),
                "role": member.get("role"),
                "project": member.get("project"),
                "identifiers": identifiers,
                "created_at": member.get("created_at"),
                "updated_at": member.get("updated_at")
            })
        
        # Sort by name
        members.sort(key=lambda x: x.get("name", "").lower())
        
        return members
        
    except Exception as e:
        logger.error(f"Error fetching members: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch members: {str(e)}")


@router.post("/members")
async def create_member(
    member_data: MemberCreate,
    request: Request,
    _admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    """
    Create a new team member
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        # Check if member with same email already exists
        existing_member = await db["members"].find_one({"email": member_data.email})
        if existing_member:
            raise HTTPException(status_code=400, detail=f"Member with email {member_data.email} already exists")
        
        # Create member document
        now = datetime.utcnow().isoformat() + 'Z'
        member_doc = {
            "name": member_data.name,
            "email": member_data.email,
            "role": member_data.role,
            "project": member_data.project,
            "created_at": now,
            "updated_at": now
        }
        
        # Insert member
        result = await db["members"].insert_one(member_doc)
        member_id = str(result.inserted_id)
        
        # Create member identifiers
        identifiers = []
        
        # Email identifier (for Drive/general use)
        await db["member_identifiers"].insert_one({
            "member_id": member_id,
            "member_name": member_data.name,
            "source": "drive",
            "identifier_type": "email",
            "identifier_value": member_data.email,
            "created_at": now
        })
        identifiers.append({"type": "email", "value": member_data.email})
        
        # GitHub identifier
        if member_data.github_id:
            await db["member_identifiers"].insert_one({
                "member_id": member_id,
                "member_name": member_data.name,
                "source": "github",
                "identifier_type": "username",
                "identifier_value": member_data.github_id,
                "created_at": now
            })
            identifiers.append({"type": "github_id", "value": member_data.github_id})
        
        # Slack identifier
        if member_data.slack_id:
            # Determine if it's email or user_id
            id_type = "email" if '@' in member_data.slack_id else "user_id"
            await db["member_identifiers"].insert_one({
                "member_id": member_id,
                "member_name": member_data.name,
                "source": "slack",
                "identifier_type": id_type,
                "identifier_value": member_data.slack_id,
                "created_at": now
            })
            identifiers.append({"type": "slack_id", "value": member_data.slack_id})
        
        # Notion identifier
        if member_data.notion_id:
            await db["member_identifiers"].insert_one({
                "member_id": member_id,
                "member_name": member_data.name,
                "source": "notion",
                "identifier_type": "email",
                "identifier_value": member_data.notion_id,
                "created_at": now
            })
            identifiers.append({"type": "notion_id", "value": member_data.notion_id})
        
        logger.info(f"Created new member: {member_data.name} ({member_id})")
        
        return {
            "id": member_id,
            "name": member_data.name,
            "email": member_data.email,
            "role": member_data.role,
            "project": member_data.project,
            "identifiers": identifiers,
            "created_at": now,
            "updated_at": now
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating member: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create member: {str(e)}")


@router.patch("/members/{member_id}")
async def update_member(
    member_id: str,
    member_data: MemberUpdate,
    request: Request,
    _admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    """
    Update an existing team member
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        # Check if member exists
        from bson import ObjectId
        try:
            member_obj_id = ObjectId(member_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid member ID format")
        
        existing_member = await db["members"].find_one({"_id": member_obj_id})
        if not existing_member:
            raise HTTPException(status_code=404, detail=f"Member with ID {member_id} not found")
        
        # Prepare update data
        update_data = {}
        if member_data.name is not None:
            update_data["name"] = member_data.name
        if member_data.email is not None:
            update_data["email"] = member_data.email
        if member_data.role is not None:
            update_data["role"] = member_data.role
        if member_data.project is not None:
            update_data["project"] = member_data.project
        
        if update_data:
            update_data["updated_at"] = datetime.utcnow().isoformat() + 'Z'
            await db["members"].update_one(
                {"_id": member_obj_id},
                {"$set": update_data}
            )
        
        # Update identifiers
        now = datetime.utcnow().isoformat() + 'Z'
        
        async def update_identifier(source: str, sub_type: str, identifier_value: Optional[str]):
            if identifier_value is not None:
                # Check if identifier exists
                existing_identifier = await db["member_identifiers"].find_one({
                    "member_id": member_id,
                    "source": source
                })
                
                member_name = update_data.get("name", existing_member.get("name"))
                
                if existing_identifier:
                    # Update existing
                    await db["member_identifiers"].update_one(
                        {"_id": existing_identifier["_id"]},
                        {"$set": {
                            "member_name": member_name,
                            "identifier_type": sub_type,
                            "identifier_value": identifier_value,
                            "updated_at": now
                        }}
                    )
                else:
                    # Create new
                    await db["member_identifiers"].insert_one({
                        "member_id": member_id,
                        "member_name": member_name,
                        "source": source,
                        "identifier_type": sub_type,
                        "identifier_value": identifier_value,
                        "created_at": now
                    })
        
        # Update GitHub identifier
        if member_data.github_id is not None:
            await update_identifier("github", "username", member_data.github_id)
        
        # Update Slack identifier
        if member_data.slack_id is not None:
            slack_type = "email" if '@' in member_data.slack_id else "user_id"
            await update_identifier("slack", slack_type, member_data.slack_id)
        
        # Update Notion identifier
        if member_data.notion_id is not None:
            await update_identifier("notion", "email", member_data.notion_id)
        
        # Update email identifier (for Drive)
        if member_data.email is not None:
            await update_identifier("drive", "email", member_data.email)
        
        # Get updated member
        updated_member = await db["members"].find_one({"_id": member_obj_id})
        
        # Get identifiers
        identifiers_cursor = db["member_identifiers"].find({"member_id": member_id})
        identifiers = {}
        async for identifier in identifiers_cursor:
            # Use source as key for consistency
            source = identifier.get("source", identifier.get("identifier_type"))
            identifiers[source] = identifier["identifier_value"]
        
        logger.info(f"Updated member: {member_id}")
        
        return {
            "id": member_id,
            "name": updated_member.get("name"),
            "email": updated_member.get("email"),
            "role": updated_member.get("role"),
            "project": updated_member.get("project"),
            "identifiers": identifiers,
            "created_at": updated_member.get("created_at"),
            "updated_at": updated_member.get("updated_at")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating member: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update member: {str(e)}")


@router.get("/members/{member_id}")
async def get_member_detail(
    member_id: str,
    request: Request,
    _admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    """
    Get detailed information for a specific member including activity statistics
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        # Check if member exists
        from bson import ObjectId
        try:
            member_obj_id = ObjectId(member_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid member ID format")
        
        member = await db["members"].find_one({"_id": member_obj_id})
        if not member:
            raise HTTPException(status_code=404, detail=f"Member with ID {member_id} not found")
        
        member_name = member.get("name")
        
        # Get identifiers - try both string and ObjectId
        identifiers_cursor = db["member_identifiers"].find({
            "$or": [
                {"member_id": member_id},
                {"member_id": member_obj_id}
            ]
        })
        identifiers = {}
        async for identifier in identifiers_cursor:
            # Use source as key for consistency
            source = identifier.get("source", identifier.get("identifier_type"))
            identifiers[source] = identifier["identifier_value"]
        
        # Get activity statistics
        activity_stats = {
            "total_activities": 0,
            "by_source": {},
            "by_type": {},
            "recent_activities": []
        }
        
        # GitHub statistics
        github_commits = await db["github_commits"].count_documents({"author_name": member_name})
        github_prs = await db["github_pull_requests"].count_documents({"user_login": member_name})
        github_issues = await db["github_issues"].count_documents({"user_login": member_name})
        
        if github_commits + github_prs + github_issues > 0:
            activity_stats["by_source"]["github"] = {
                "total": github_commits + github_prs + github_issues,
                "commits": github_commits,
                "pull_requests": github_prs,
                "issues": github_issues
            }
            activity_stats["total_activities"] += github_commits + github_prs + github_issues
        
        # Slack statistics
        slack_email = identifiers.get("slack") or identifiers.get("email")
        if slack_email:
            slack_messages = await db["slack_messages"].count_documents({"user_email": slack_email})
            if slack_messages > 0:
                activity_stats["by_source"]["slack"] = {
                    "total": slack_messages,
                    "messages": slack_messages
                }
                activity_stats["total_activities"] += slack_messages
        
        # Notion statistics
        notion_pages = await db["notion_pages"].count_documents({"created_by": member_name})
        if notion_pages > 0:
            activity_stats["by_source"]["notion"] = {
                "total": notion_pages,
                "pages": notion_pages
            }
            activity_stats["total_activities"] += notion_pages
        
        # Drive statistics
        drive_activities = await db["drive_activities"].count_documents({"actor_email": identifiers.get("email")})
        if drive_activities > 0:
            activity_stats["by_source"]["drive"] = {
                "total": drive_activities,
                "activities": drive_activities
            }
            activity_stats["total_activities"] += drive_activities
        
        # Get recent activities (last 20)
        recent = []
        
        # Recent GitHub commits
        github_commits_cursor = db["github_commits"].find(
            {"author_name": member_name}
        ).sort("date", -1).limit(5)
        async for commit in github_commits_cursor:
            recent.append({
                "source": "github",
                "type": "commit",
                "timestamp": commit.get("date"),
                "description": commit.get("message", "")[:100],
                "repository": commit.get("repository")
            })
        
        # Recent Slack messages
        if slack_email:
            slack_cursor = db["slack_messages"].find(
                {"user_email": slack_email}
            ).sort("timestamp", -1).limit(5)
            async for msg in slack_cursor:
                recent.append({
                    "source": "slack",
                    "type": "message",
                    "timestamp": msg.get("timestamp"),
                    "description": msg.get("text", "")[:100]
                })
        
        # Sort recent activities by timestamp
        recent.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
        activity_stats["recent_activities"] = recent[:20]
        
        logger.info(f"Retrieved member detail: {member_name} ({member_id})")
        
        return {
            "id": member_id,
            "name": member.get("name"),
            "email": member.get("email"),
            "role": member.get("role"),
            "project": member.get("project"),
            "identifiers": identifiers,
            "activity_stats": activity_stats,
            "created_at": member.get("created_at"),
            "updated_at": member.get("updated_at")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching member detail: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch member detail: {str(e)}")


@router.get("/members/{member_id}/activities")
async def get_member_activities(
    member_id: str,
    request: Request,
    source_type: Optional[str] = None,
    activity_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    _admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    """
    Get activities for a specific member with detailed information
    
    Args:
        member_id: Member ID
        source_type: Filter by source (github, slack, notion, google_drive)
        activity_type: Filter by activity type
        start_date: Filter by start date (ISO format)
        end_date: Filter by end date (ISO format)
        limit: Maximum number of activities to return
        offset: Number of activities to skip
    
    Returns:
        List of member activities with detailed information
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        # Check if member exists
        from bson import ObjectId
        try:
            member_obj_id = ObjectId(member_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid member ID format")
        
        member = await db["members"].find_one({"_id": member_obj_id})
        if not member:
            raise HTTPException(status_code=404, detail=f"Member with ID {member_id} not found")
        
        member_name = member.get("name")
        
        # Build query for member_activities collection - try both string and ObjectId
        base_query = {
            "$or": [
                {"member_id": member_id},
                {"member_id": member_obj_id}
            ]
        }
        
        query = base_query.copy()
        
        if source_type:
            query["source_type"] = source_type
        
        if activity_type:
            query["activity_type"] = activity_type
        
        if start_date:
            query["timestamp"] = {"$gte": start_date}
        
        if end_date:
            if "timestamp" not in query:
                query["timestamp"] = {}
            elif isinstance(query["timestamp"], dict):
                query["timestamp"]["$lte"] = end_date
            else:
                # If timestamp was already a single value, convert to range
                query["timestamp"] = {
                    "$gte": query["timestamp"],
                    "$lte": end_date
                }
        
        # Get total count
        total = await db["member_activities"].count_documents(query)
        
        # Get activities from member_activities collection
        activities_cursor = (
            db["member_activities"]
            .find(query)
            .sort("timestamp", -1)
            .skip(offset)
            .limit(limit)
        )
        
        activities = []
        async for activity in activities_cursor:
            # Parse metadata if it's a string
            metadata = activity.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    import json
                    metadata = json.loads(metadata)
                except:
                    metadata = {}
            
            activities.append({
                "id": str(activity.get("_id")),
                "source_type": activity.get("source_type", "unknown"),
                "activity_type": activity.get("activity_type", "unknown"),
                "timestamp": activity.get("timestamp"),
                "metadata": metadata
            })
        
        return {
            "member_id": member_id,
            "member_name": member_name,
            "total": total,
            "activities": activities
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching member activities: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch member activities: {str(e)}")


class SummaryRequest(BaseModel):
    """Request model for member summary generation"""
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@router.post("/members/{member_id}/summary")
async def generate_member_summary(
    member_id: str,
    request: Request,
    summary_request: Optional[SummaryRequest] = None,
    _admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    """
    Generate AI-powered summary of member activities using Gemini
    
    Args:
        member_id: Member ID
        summary_request: Optional request body with start_date and end_date
    
    Returns:
        AI-generated summary of member activities
    """
    try:
        import os
        import google.generativeai as genai
        
        # Extract dates from request
        start_date = summary_request.start_date if summary_request else None
        end_date = summary_request.end_date if summary_request else None
        
        # Get Gemini API key
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
        
        # Configure Gemini
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        # Get member activities
        mongo = get_mongo()
        db = mongo.async_db
        
        from bson import ObjectId
        try:
            member_obj_id = ObjectId(member_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid member ID format")
        
        member = await db["members"].find_one({"_id": member_obj_id})
        if not member:
            raise HTTPException(status_code=404, detail=f"Member with ID {member_id} not found")
        
        member_name = member.get("name")
        
        # Build query for member_activities collection - try both string and ObjectId
        base_query = {
            "$or": [
                {"member_id": member_id},
                {"member_id": member_obj_id}
            ]
        }
        
        query = base_query.copy()
        
        if start_date:
            query["timestamp"] = {"$gte": start_date}
        
        if end_date:
            if "timestamp" not in query:
                query["timestamp"] = {}
            elif isinstance(query["timestamp"], dict):
                query["timestamp"]["$lte"] = end_date
            else:
                query["timestamp"] = {
                    "$gte": query["timestamp"],
                    "$lte": end_date
                }
        
        # Get activities from member_activities collection (limit to 100 for summary)
        activities_cursor = (
            db["member_activities"]
            .find(query)
            .sort("timestamp", -1)
            .limit(100)
        )
        
        activities = []
        async for activity in activities_cursor:
            # Parse metadata if it's a string
            metadata = activity.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    import json
                    metadata = json.loads(metadata)
                except:
                    metadata = {}
            
            activities.append({
                "id": str(activity.get("_id")),
                "source_type": activity.get("source_type", "unknown"),
                "activity_type": activity.get("activity_type", "unknown"),
                "timestamp": activity.get("timestamp"),
                "metadata": metadata
            })
        
        if not activities:
            return {
                "member_id": member_id,
                "member_name": member_name,
                "summary": f"{member_name} has no activities in the specified period.",
                "period": {
                    "start": start_date,
                    "end": end_date
                }
            }
        
        # Format activities for AI prompt
        activities_text = []
        by_source = {}
        
        for activity in activities:
            source = activity.get("source_type", "unknown")
            activity_type = activity.get("activity_type", "unknown")
            timestamp = activity.get("timestamp", "")
            metadata = activity.get("metadata", {})
            
            if source not in by_source:
                by_source[source] = []
            
            activity_desc = f"- {activity_type} at {timestamp}"
            if source == "github":
                if activity_type == "commit":
                    activity_desc += f": {metadata.get('message', '')[:100]} in {metadata.get('repository', '')} (+{metadata.get('additions', 0)}/-{metadata.get('deletions', 0)} lines)"
                elif activity_type == "pull_request":
                    activity_desc += f": PR #{metadata.get('number', '')} - {metadata.get('title', '')[:100]} in {metadata.get('repository', '')} ({metadata.get('state', '')})"
                elif activity_type == "issue":
                    activity_desc += f": Issue #{metadata.get('number', '')} - {metadata.get('title', '')[:100]} in {metadata.get('repository', '')} ({metadata.get('state', '')})"
            elif source == "slack":
                activity_desc += f": {metadata.get('text', '')[:100]} in {metadata.get('channel_name', '')}"
            elif source == "notion":
                activity_desc += f": {metadata.get('title', '')[:100]}"
            elif source == "google_drive":
                activity_desc += f": {metadata.get('primary_action', '')} on {metadata.get('target_name', '')}"
            
            by_source[source].append(activity_desc)
        
        # Build prompt
        prompt = f"""Analyze the following activities for team member {member_name} and provide a comprehensive summary.

## Activities by Source

"""
        for source, source_activities in by_source.items():
            prompt += f"### {source.upper()}\n"
            prompt += "\n".join(source_activities[:20])  # Limit to 20 per source
            prompt += "\n\n"
        
        prompt += f"""
## Analysis Request

Please provide:
1. **Overall Activity Assessment**: Evaluate the member's overall activity level and engagement
2. **Work Patterns**: Identify patterns in their work (e.g., focus areas, collaboration style)
3. **Key Contributions**: Highlight significant contributions or achievements
4. **Activity Distribution**: Analyze how activities are distributed across different sources
5. **Trends and Insights**: Identify any trends or notable patterns in their work

Provide a clear, concise summary in English that would be useful for performance review or team insights.
"""
        
        # Generate summary using Gemini
        try:
            response = model.generate_content(prompt)
            summary = response.text
        except Exception as e:
            logger.error(f"Error generating Gemini summary: {e}")
            summary = f"Error generating summary: {str(e)}"
        
        return {
            "member_id": member_id,
            "member_name": member_name,
            "summary": summary,
            "period": {
                "start": start_date,
                "end": end_date
            },
            "activity_count": len(activities),
            "sources": list(by_source.keys())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating member summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")


@router.delete("/members/{member_id}")
async def delete_member(
    member_id: str,
    request: Request,
    _admin: str = Depends(require_admin)
) -> Dict[str, str]:
    """
    Delete a team member and their identifiers
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        # Check if member exists
        from bson import ObjectId
        try:
            member_obj_id = ObjectId(member_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid member ID format")
        
        existing_member = await db["members"].find_one({"_id": member_obj_id})
        if not existing_member:
            raise HTTPException(status_code=404, detail=f"Member with ID {member_id} not found")
        
        member_name = existing_member.get("name", "Unknown")
        
        # Delete member identifiers
        await db["member_identifiers"].delete_many({"member_id": member_id})
        
        # Delete member
        await db["members"].delete_one({"_id": member_obj_id})
        
        logger.info(f"Deleted member: {member_name} ({member_id})")
        
        return {
            "message": f"Member {member_name} deleted successfully",
            "deleted_member_id": member_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting member: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete member: {str(e)}")
