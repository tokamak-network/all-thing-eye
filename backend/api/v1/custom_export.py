"""
Custom Export API endpoints

Provides filtered raw activity data for custom export builder
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict, Set
from pydantic import BaseModel
from datetime import datetime, timedelta
from bson import ObjectId
import csv
import io
import os
import requests
import yaml
import json
import zipfile
import asyncio
import re

from src.utils.logger import get_logger
from src.utils.toon_encoder import encode_toon

logger = get_logger(__name__)

router = APIRouter()


class CustomExportRequest(BaseModel):
    """Request model for custom export preview"""
    selected_members: List[str] = []
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    project: Optional[str] = None
    selected_fields: List[str] = []
    sources: Optional[List[str]] = None  # Add sources field for activities page
    limit: int = 50
    offset: int = 0


class CollectionExportRequest(BaseModel):
    """Request model for exporting entire collections"""
    collections: List[Dict[str, str]]  # [{"source": "main", "collection": "members"}, ...]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    format: str = "csv"  # csv, json, toon
    limit: Optional[int] = None


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
    elif field.startswith("gemini."):
        return "gemini"
    elif field.startswith("recordings."):
        return "recordings"
    return ""


def get_project_repositories_from_mongodb(project_key: str) -> Set[str]:
    """
    Get repositories for a project from MongoDB projects collection
    
    Repositories are automatically synced from GitHub Teams during daily data collection.
    
    Args:
        project_key: Project key (e.g., "project-ooo", "project-trh")
    
    Returns:
        Set of repository names (without org prefix)
    """
    try:
        mongo = get_mongo()
        if mongo._sync_client is None:
            mongo.connect_sync()
        db = mongo._sync_client[mongo.database_name]
        projects_collection = db["projects"]
        
        # Get project from MongoDB
        project = projects_collection.find_one({"key": project_key, "is_active": True})
        
        if not project:
            logger.warning(f"Project {project_key} not found in MongoDB, falling back to config.yaml")
            return get_project_repositories_from_config(project_key)
        
        repositories = project.get("repositories", [])
        
        if repositories:
            logger.info(f"Found {len(repositories)} repositories for {project_key} from MongoDB")
            return set(repositories)
        else:
            # If repositories list is empty, might not be synced yet, fall back to config
            logger.warning(f"No repositories found for {project_key} in MongoDB, falling back to config.yaml")
            return get_project_repositories_from_config(project_key)
            
    except Exception as e:
        logger.warning(f"Error reading from MongoDB: {e}, falling back to config.yaml")
        return get_project_repositories_from_config(project_key)


def get_project_repositories_from_teams(project_key: str) -> Set[str]:
    """
    Get repositories for a project using GitHub Teams API (legacy, kept for manual sync)
    
    Note: This is now only used for manual repository sync via API endpoint.
    For normal operations, use get_project_repositories_from_mongodb() which reads
    from the automatically synced MongoDB projects collection.
    
    Args:
        project_key: Project key (e.g., "project-ooo", "project-trh")
    
    Returns:
        Set of repository names (without org prefix)
    """
    github_token = os.getenv("GITHUB_TOKEN")
    github_org = os.getenv("GITHUB_ORG", "tokamak-network")
    
    if not github_token:
        logger.warning("GITHUB_TOKEN not set, falling back to config.yaml")
        return get_project_repositories_from_config(project_key)
    
    # Extract team slug from project key (e.g., "project-ooo" -> "project-ooo")
    team_slug = project_key
    
    try:
        # GitHub API: List team repositories
        url = f"https://api.github.com/orgs/{github_org}/teams/{team_slug}/repos"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        repos = set()
        page = 1
        per_page = 100
        
        while True:
            params = {"page": page, "per_page": per_page}
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 404:
                # Team doesn't exist, fall back to config
                logger.warning(f"Team {team_slug} not found, using config.yaml")
                return get_project_repositories_from_config(project_key)
            
            if response.status_code != 200:
                logger.warning(f"GitHub API error {response.status_code}, falling back to config.yaml")
                return get_project_repositories_from_config(project_key)
            
            data = response.json()
            if not data:
                break
            
            # Extract repository names (remove org prefix)
            for repo in data:
                full_name = repo.get("full_name", "")
                if "/" in full_name:
                    repo_name = full_name.split("/", 1)[1]
                    repos.add(repo_name)
            
            # Check if there are more pages
            if len(data) < per_page:
                break
            page += 1
        
        logger.info(f"Found {len(repos)} repositories for {project_key} via GitHub Teams API")
        return repos
        
    except Exception as e:
        logger.warning(f"Error fetching GitHub Teams data: {e}, falling back to config.yaml")
        return get_project_repositories_from_config(project_key)


def get_project_repositories_from_config(project_key: str) -> Set[str]:
    """
    Get repositories for a project from config.yaml (fallback)
    
    Args:
        project_key: Project key (e.g., "project-ooo", "project-trh")
    
    Returns:
        Set of repository names
    """
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "config.yaml")
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        
        project_config = config.get("projects", {}).get(project_key, {})
        repositories = project_config.get("repositories", [])
        
        # Also include DRB repositories if project is TRH
        if project_key == "project-trh":
            drb_config = config.get("projects", {}).get("project-drb", {})
            drb_repos = drb_config.get("repositories", [])
            repositories.extend(drb_repos)
        
        return set(repositories) if repositories else set()
        
    except Exception as e:
        logger.error(f"Error reading config.yaml: {e}")
        return set()


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
            sources_needed = {"github", "slack", "notion", "drive", "gemini", "recordings"}
        
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
                results.extend(await fetch_github_data(db, members_to_filter, date_filter, member_info_map, body.project))
            elif source == "slack":
                results.extend(await fetch_slack_data(db, members_to_filter, date_filter, member_info_map))
            elif source == "notion":
                results.extend(await fetch_notion_data(db, members_to_filter, date_filter, member_info_map))
            elif source == "drive":
                results.extend(await fetch_drive_data(db, members_to_filter, date_filter, member_info_map))
            elif source == "gemini":
                results.extend(await fetch_gemini_data(db, members_to_filter, date_filter, member_info_map))
            elif source == "recordings":
                results.extend(await fetch_recordings_data(db, members_to_filter, date_filter, member_info_map))
        
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


async def fetch_github_data(db, members: List[str], date_filter: dict, member_info_map: dict, project: Optional[str] = None) -> List[dict]:
    """
    Fetch GitHub commits and PRs for selected members
    
    Args:
        db: MongoDB database
        members: List of member names
        date_filter: Date range filter
        member_info_map: Map of member names to info
        project: Optional project key to filter by repositories (e.g., "project-ooo")
    """
    results = []
    
    # Get project repositories if project is specified
    # Read from MongoDB (automatically synced from GitHub Teams during data collection)
    project_repos = None
    if project and project != "all":
        project_repos = get_project_repositories_from_mongodb(project)
        if not project_repos:
            logger.warning(f"No repositories found for project {project}, returning empty results")
            return []
    
    for member_name in members:
        identifiers = get_identifiers_for_member(member_name, db)
        member_info = member_info_map.get(member_name, {})
        
        # Build query for commits (use author_name field like activities_mongo.py)
        commit_query = {}
        or_conditions = []
        if identifiers["github"]:
            or_conditions.append({"author_name": {"$in": identifiers["github"]}})
        # Also add regex match for member name (case-insensitive, partial match)
        or_conditions.append({"author_name": {"$regex": f"{member_name}", "$options": "i"}})
        
        commit_query["$or"] = or_conditions
        
        if date_filter:
            commit_query["date"] = date_filter
        
        # Add repository filter if project is specified
        if project_repos:
            commit_query["repository"] = {"$in": list(project_repos)}
        
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
        or_conditions = []
        if identifiers["github"]:
            or_conditions.append({"author": {"$in": identifiers["github"]}})
        # Also add regex match for member name (case-insensitive, partial match)
        or_conditions.append({"author": {"$regex": f"{member_name}", "$options": "i"}})
        
        pr_query["$or"] = or_conditions
        
        if date_filter:
            pr_query["created_at"] = date_filter
        
        # Add repository filter if project is specified
        if project_repos:
            pr_query["repository"] = {"$in": list(project_repos)}
        
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
            # Use user_email field (not actor_email)
            or_conditions.append({"user_email": {"$in": identifiers["drive"]}})
        # Also add regex match for member name in user field
        or_conditions.append({"user": {"$regex": f"{member_name}", "$options": "i"}})
        
        if or_conditions:
            query["$or"] = or_conditions
        else:
            # If no conditions, skip this member to avoid returning all documents
            continue
        
        if date_filter:
            # Use timestamp field (not activity_time)
            query["timestamp"] = date_filter
        
        # Use timestamp field for sorting (not activity_time)
        activities = list(db["drive_activities"].find(query).sort("timestamp", -1))
        for activity in activities:
            results.append({
                "source": "drive",
                "type": activity.get("action", "activity"),  # Use action field (not activity_type)
                "member_name": member_name,
                "member_email": member_info.get("email"),
                "timestamp": activity.get("timestamp"),  # Use timestamp field (not activity_time)
                "file_name": activity.get("doc_title"),  # Use doc_title field (not file_name)
                "file_type": activity.get("doc_type"),  # Use doc_type field (not mime_type)
                "action": activity.get("action"),
                "event_name": activity.get("event_name"),
                "doc_id": activity.get("doc_id"),
            })
    
    return results


async def fetch_gemini_data(db, members: List[str], date_filter: dict, member_info_map: dict) -> List[dict]:
    """Fetch Gemini AI daily analyses data"""
    results = []
    
    try:
        from backend.api.v1.ai_processed import get_gemini_db
        gemini_db = get_gemini_db()
        recordings_daily_col = gemini_db["recordings_daily"]
        
        # Build query
        query = {}
        if date_filter:
            # target_date is stored as string (YYYY-MM-DD), convert datetime filter to string
            string_date_filter = {}
            for op, value in date_filter.items():
                if isinstance(value, datetime):
                    string_date_filter[op] = value.strftime('%Y-%m-%d')
                else:
                    string_date_filter[op] = value
            query['target_date'] = string_date_filter
        
        # Get documents (sync operation)
        daily_docs = list(recordings_daily_col.find(query).sort("target_date", -1))
        
        for daily in daily_docs:
            # If members are specified, filter by participants
            if members:
                # Check if any selected member is in the participants
                analysis = daily.get("analysis", {})
                participants = analysis.get("participants", []) if analysis else []
                
                # Extract participant names
                participant_names = []
                if isinstance(participants, list):
                    for p in participants:
                        if isinstance(p, dict) and "name" in p:
                            participant_names.append(p["name"])
                        elif isinstance(p, str):
                            participant_names.append(p)
                
                # Check if any selected member is in participants
                has_match = False
                for member in members:
                    for participant_name in participant_names:
                        if member.lower() in participant_name.lower() or participant_name.lower() in member.lower():
                            has_match = True
                            break
                    if has_match:
                        break
                
                # Skip this document if no match found
                if not has_match:
                    continue
            
            # Continue processing matched document
            try:
                timestamp = daily.get("timestamp")
                if isinstance(timestamp, datetime):
                    timestamp_str = timestamp.isoformat() + 'Z' if timestamp.tzinfo is None else timestamp.isoformat()
                else:
                    timestamp_str = str(timestamp) if timestamp else daily.get("target_date", "")
                
                # Get analysis data, handle _raw field if present
                analysis = daily.get("analysis", {})
                
                # If _raw exists and summary doesn't, try to parse it
                if analysis and "_raw" in analysis and not analysis.get("summary"):
                    try:
                        import json
                        import re
                        
                        raw_content = analysis.get("_raw", "")
                        # Try to extract JSON from markdown code blocks
                        json_match = re.search(r'```json\s*(\{.*?\})\s*```', raw_content, re.DOTALL)
                        if json_match:
                            raw_content = json_match.group(1)
                        else:
                            # Try to find JSON object directly
                            json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
                            if json_match:
                                raw_content = json_match.group(0)
                        
                        # Parse JSON
                        parsed_analysis = json.loads(raw_content)
                        if isinstance(parsed_analysis, dict):
                            # Merge parsed data into analysis
                            for key, value in parsed_analysis.items():
                                if key != "_raw":
                                    analysis[key] = value
                    except (json.JSONDecodeError, Exception) as e:
                        logger.warning(f"Failed to parse _raw field for recordings_daily: {e}")
                
                # Safely get nested values with defaults
                summary = analysis.get("summary", {}) if analysis else {}
                topics = summary.get("topics", []) if summary else []
                key_decisions = summary.get("key_decisions", []) if summary else []
                participants = analysis.get("participants", []) if analysis else []
                
                results.append({
                    "source": "gemini",
                    "type": "daily_analysis",
                    "member_name": "System",
                    "member_email": None,
                    "timestamp": timestamp_str,
                    "target_date": daily.get("target_date"),
                    "meeting_count": daily.get("meeting_count", 0),
                    "total_meeting_time": daily.get("total_meeting_time"),
                    "total_meeting_time_seconds": daily.get("total_meeting_time_seconds", 0),
                    "meeting_titles": daily.get("meeting_titles", []),
                    "topics_count": len(topics) if isinstance(topics, list) else 0,
                    "decisions_count": len(key_decisions) if isinstance(key_decisions, list) else 0,
                    "participants_count": len(participants) if isinstance(participants, list) else 0,
                    "status": daily.get("status"),
                    "model_used": daily.get("model_used"),
                })
            except Exception as e:
                logger.warning(f"Error processing recordings_daily document: {e}")
                import traceback
                logger.warning(traceback.format_exc())
                continue
    except Exception as e:
        logger.error(f"Error fetching gemini data: {e}")
    
    return results


async def fetch_recordings_data(db, members: List[str], date_filter: dict, member_info_map: dict) -> List[dict]:
    """Fetch recordings data from gemini database"""
    results = []
    
    try:
        from backend.api.v1.ai_processed import get_gemini_db
        gemini_db = get_gemini_db()
        recordings_col = gemini_db["recordings"]
        
        # Build query
        query = {}
        
        if members:
            # participants is a list of strings like ['YEONGJU BAK', 'Eugenie Nguyen']
            # Create $or conditions for each member name with case-insensitive regex
            or_conditions = []
            for name in members:
                or_conditions.append({"participants": {"$regex": name, "$options": "i"}})
            query["$or"] = or_conditions
        
        if date_filter:
            # meeting_date is a datetime field
            query["meeting_date"] = date_filter
        
        logger.info(f"[RECORDINGS] Query: {query}")
        logger.info(f"[RECORDINGS] Members filter: {members}")
        logger.info(f"[RECORDINGS] Date filter: {date_filter}")
        
        # Get recordings (sync operation for gemini)
        recordings = list(recordings_col.find(query).sort("meeting_date", -1).limit(10000))
        
        logger.info(f"[RECORDINGS] Found {len(recordings)} documents")
        
        for recording in recordings:
            try:
                meeting_date = recording.get("meeting_date")
                if isinstance(meeting_date, datetime):
                    timestamp_str = meeting_date.isoformat() + 'Z' if meeting_date.tzinfo is None else meeting_date.isoformat()
                else:
                    timestamp_str = str(meeting_date) if meeting_date else ""
                
                participants = recording.get("participants", [])
                
                # Find which selected member(s) participated
                participating_members = []
                if members:
                    for member in members:
                        for participant in participants:
                            if member.lower() in participant.lower() or participant.lower() in member.lower():
                                participating_members.append(participant)
                                break
                
                # Use first participating member as primary
                primary_member = participating_members[0] if participating_members else (participants[0] if participants else "Unknown")
                member_info = member_info_map.get(primary_member, {})
                
                results.append({
                    "source": "recordings",
                    "type": "meeting_recording",
                    "member_name": primary_member,
                    "member_email": member_info.get("email"),
                    "timestamp": timestamp_str,
                    "meeting_title": recording.get("meeting_title"),
                    "meeting_id": recording.get("meeting_id"),
                    "meeting_date": timestamp_str,
                    "participants": ", ".join(participants),
                    "participant_count": len(participants),
                })
            except Exception as e:
                logger.warning(f"Error processing recording document: {e}")
                continue
    except Exception as e:
        logger.error(f"Error fetching recordings data: {e}")
    
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


@router.post("/custom-export/export")
async def export_custom_data(
    request: Request, 
    body: CustomExportRequest,
    format: str = Query("csv", regex="^(csv|json|toon)$")
):
    """
    Export filtered raw data in CSV, JSON, or TOON format
    
    Args:
        body: Custom export request with filters and field selections
        format: Export format (csv, json, or toon)
    
    Returns:
        File download response
    """
    try:
        logger.info(f"[EXPORT] Request body: members={body.selected_members}, fields={body.selected_fields}, sources={body.sources}")
        
        # Get preview data (full, not limited)
        mongo = get_mongo()
        db = mongo.db
        
        # Determine which sources to query
        sources_needed = set()
        
        # First check if body.sources is provided (from activities page)
        if hasattr(body, 'sources') and body.sources:
            sources_needed = set(body.sources)
            logger.info(f"[EXPORT] Using sources from body.sources: {sources_needed}")
        else:
            # Fall back to determining from selected_fields
        for field in body.selected_fields:
            source = get_source_from_field(field)
            if source and source != "member":
                sources_needed.add(source)
            logger.info(f"[EXPORT] Determined sources from fields: {sources_needed}")
        
        if not sources_needed:
            sources_needed = {"github", "slack", "notion", "drive", "gemini", "recordings"}
            logger.info(f"[EXPORT] No sources specified, using all: {sources_needed}")
        
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
        source_results_count = {}
        
        for source in sources_needed:
            source_data = []
            if source == "github":
                source_data = await fetch_github_data(db, members_to_filter, date_filter, member_info_map, body.project)
            elif source == "slack":
                source_data = await fetch_slack_data(db, members_to_filter, date_filter, member_info_map)
            elif source == "notion":
                source_data = await fetch_notion_data(db, members_to_filter, date_filter, member_info_map)
            elif source == "drive":
                source_data = await fetch_drive_data(db, members_to_filter, date_filter, member_info_map)
            elif source == "gemini":
                source_data = await fetch_gemini_data(db, members_to_filter, date_filter, member_info_map)
            elif source == "recordings":
                source_data = await fetch_recordings_data(db, members_to_filter, date_filter, member_info_map)
            
            source_results_count[source] = len(source_data)
            results.extend(source_data)
            logger.info(f"Fetched {len(source_data)} records from {source}")
        
        # Sort by timestamp
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        if not results:
            logger.warning(f"No data found with filters - Members: {members_to_filter}, Sources: {sources_needed}, Results by source: {source_results_count}")
            raise HTTPException(
                status_code=404, 
                detail=f"No data found with the given filters. Members: {', '.join(members_to_filter) if members_to_filter else 'All'}, Sources queried: {', '.join(sources_needed)}, Results: {source_results_count}"
            )
        
        # Generate filename
        date_suffix = f"{body.start_date or 'all'}_{body.end_date or 'all'}"
        
        if format == "json":
            # JSON export
            output = json.dumps(results, indent=2, ensure_ascii=False, default=str)
            filename = f"custom_export_{date_suffix}.json"
            media_type = "application/json"
            
        elif format == "toon":
            # TOON export
            toon_data = {"custom_export": results}
            output = encode_toon(toon_data, indent=2, delimiter=',')
            filename = f"custom_export_{date_suffix}.toon"
            media_type = "text/plain"
            
        else:
            # CSV export (default)
            output_stream = io.StringIO()
            
            # Get all possible field names from results
            all_fields = set()
            for row in results:
                all_fields.update(row.keys())
            
            # Order fields logically
            ordered_fields = ["source", "type", "member_name", "member_email", "timestamp"]
            for field in sorted(all_fields):
                if field not in ordered_fields:
                    ordered_fields.append(field)
            
            writer = csv.DictWriter(output_stream, fieldnames=ordered_fields, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(results)
            
            output = output_stream.getvalue()
            filename = f"custom_export_{date_suffix}.csv"
            media_type = "text/csv"
        
        return StreamingResponse(
            iter([output]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/custom-export/csv")
async def export_custom_csv(request: Request, body: CustomExportRequest):
    """
    Export filtered raw data as CSV (backward compatibility)
    """
    return await export_custom_data(request, body, format="csv")


@router.get("/custom-export/collections")
async def get_custom_export_collections(request: Request):
    """
    Get list of all available collections dynamically from database
    
    Returns collections organized by database (main, shared, gemini)
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        shared_db = mongo.shared_async_db
        
        # Get gemini database
        from backend.api.v1.ai_processed import get_gemini_db
        gemini_db_sync = get_gemini_db()
        
        collections_by_source = {
            "main": [],
            "shared": [],
            "gemini": []
        }
        
        # Get main database collections
        main_collections = await db.list_collection_names()
        for name in main_collections:
            try:
                count = await db[name].count_documents({})
                collections_by_source["main"].append({
                    "name": name,
                    "count": count,
                    "source": "main"
                })
            except Exception as e:
                logger.warning(f"Failed to get count for {name}: {e}")
        
        # Get shared database collections
        try:
            shared_collections = await shared_db.list_collection_names()
            for name in shared_collections:
                try:
                    count = await shared_db[name].count_documents({})
                    collections_by_source["shared"].append({
                        "name": f"shared.{name}",
                        "count": count,
                        "source": "shared"
                    })
                except Exception as e:
                    logger.warning(f"Failed to get count for shared.{name}: {e}")
        except Exception as e:
            logger.warning(f"Failed to access shared database: {e}")
        
        # Get gemini database collections
        try:
            gemini_collections = gemini_db_sync.list_collection_names()
            for name in gemini_collections:
                try:
                    count = gemini_db_sync[name].count_documents({})
                    collections_by_source["gemini"].append({
                        "name": f"gemini.{name}",
                        "count": count,
                        "source": "gemini"
                    })
                except Exception as e:
                    logger.warning(f"Failed to get count for gemini.{name}: {e}")
        except Exception as e:
            logger.warning(f"Failed to access gemini database: {e}")
        
        return {
            "sources": collections_by_source,
            "total_collections": sum(len(cols) for cols in collections_by_source.values())
        }
        
    except Exception as e:
        logger.error(f"Error getting collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/custom-export/collection")
async def export_collection(
    request: Request,
    body: CollectionExportRequest
):
    """
    Export a single collection in CSV, JSON, or TOON format
    
    Args:
        body: Collection export request with source, collection name, format, and filters
    
    Returns:
        File download response
    """
    if not body.collections or len(body.collections) != 1:
        raise HTTPException(status_code=400, detail="Must specify exactly one collection")
    
    collection_info = body.collections[0]
    source = collection_info.get("source")
    collection_name = collection_info.get("collection")
    
    if not source or not collection_name:
        raise HTTPException(status_code=400, detail="Must specify source and collection")
    
    try:
        mongo = get_mongo()
        
        # Select database based on source
        # Handle collection_name that might already have prefix (e.g., "shared.recordings")
        if collection_name.startswith("shared."):
            db = mongo.shared_async_db
            actual_collection = collection_name.replace("shared.", "")
            source = "shared"  # Override source if collection name has prefix
        elif collection_name.startswith("gemini."):
            from backend.api.v1.ai_processed import get_gemini_db
            gemini_db_sync = get_gemini_db()
            actual_collection = collection_name.replace("gemini.", "")
            source = "gemini"  # Override source if collection name has prefix
            db = None  # Will handle separately
        elif source == 'shared' or source == 'other':
            db = mongo.shared_async_db
            actual_collection = collection_name
        elif source == 'gemini':
            from backend.api.v1.ai_processed import get_gemini_db
            gemini_db_sync = get_gemini_db()
            actual_collection = collection_name
            db = None  # Will handle separately
        else:
            db = mongo.async_db
            actual_collection = collection_name
        
        # Build query filter
        query_filter = {}
        
        # Date filtering
        if body.start_date or body.end_date:
            if source == 'gemini' and actual_collection == 'recordings_daily':
                date_filter = {}
                if body.start_date:
                    date_filter['$gte'] = body.start_date
                if body.end_date:
                    date_filter['$lte'] = body.end_date
                if date_filter:
                    query_filter['target_date'] = date_filter
            else:
                timestamp_fields = ['timestamp', 'posted_at', 'created_at', 'updated_at', 'committed_at', 'target_date']
                timestamp_field = None
                
                if source == 'gemini':
                    sample_doc = gemini_db_sync[actual_collection].find_one({})
                else:
                    sample_doc = await db[actual_collection].find_one({})
                
                if sample_doc:
                    for field in timestamp_fields:
                        if field in sample_doc:
                            timestamp_field = field
                            break
                
                if timestamp_field:
                    date_filter = {}
                    if body.start_date:
                        try:
                            date_filter['$gte'] = datetime.fromisoformat(body.start_date)
                        except ValueError:
                            date_filter['$gte'] = body.start_date
                    if body.end_date:
                        try:
                            end_dt = datetime.fromisoformat(body.end_date) + timedelta(days=1)
                            date_filter['$lt'] = end_dt
                        except ValueError:
                            date_filter['$lte'] = body.end_date + "T23:59:59"
                    
                    if date_filter:
                        query_filter[timestamp_field] = date_filter
        
        # Query MongoDB with batching for large collections
        if source == 'gemini':
            cursor = gemini_db_sync[actual_collection].find(query_filter)
            if body.limit:
                cursor = cursor.limit(body.limit)
            documents = list(cursor)
        else:
            cursor = db[actual_collection].find(query_filter)
            if body.limit:
                cursor = cursor.limit(body.limit)
            # Use batch processing for large collections to avoid memory issues
            max_docs = body.limit or 100000
            documents = []
            count = 0
            async for doc in cursor:
                documents.append(doc)
                count += 1
                if count >= max_docs:
                    break
                # Yield control periodically for large collections (every 10000 docs)
                if count % 10000 == 0:
                    await asyncio.sleep(0)  # Yield to event loop
        
        if not documents:
            raise HTTPException(status_code=404, detail="No documents found")
        
        # Convert documents
        rows = []
        for doc in documents:
            clean_doc = {}
            for key, value in doc.items():
                if isinstance(value, ObjectId):
                    clean_doc[key] = str(value)
                elif isinstance(value, datetime):
                    clean_doc[key] = value.isoformat()
                elif isinstance(value, (dict, list)):
                    clean_doc[key] = json.dumps(value, default=str, ensure_ascii=False)
                else:
                    clean_doc[key] = value
            rows.append(clean_doc)
        
        # Generate filename
        date_suffix = f"{body.start_date or 'all'}_{body.end_date or 'all'}" if (body.start_date or body.end_date) else "all"
        filename_base = f"{collection_name}_{date_suffix}"
        
        if body.format == "json":
            output = json.dumps(rows, indent=2, ensure_ascii=False, default=str)
            filename = f"{filename_base}.json"
            media_type = "application/json"
            
        elif body.format == "toon":
            toon_data = {actual_collection: rows}
            output = encode_toon(toon_data, indent=2, delimiter=',')
            filename = f"{filename_base}.toon"
            media_type = "text/plain"
            
        else:  # CSV
            output_stream = io.StringIO()
            if rows:
                # Collect all possible fieldnames from all rows
                all_fieldnames = set()
                for row in rows:
                    all_fieldnames.update(row.keys())
                fieldnames = sorted(list(all_fieldnames))
                
                writer = csv.DictWriter(output_stream, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(rows)
            output = output_stream.getvalue()
            filename = f"{filename_base}.csv"
            media_type = "text/csv"
        
        return StreamingResponse(
            iter([output]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/custom-export/collections/bulk")
async def export_collections_bulk(
    request: Request,
    body: CollectionExportRequest
):
    """
    Export multiple collections as a ZIP file
    
    Supports CSV, JSON, and TOON formats
    """
    if not body.collections:
        raise HTTPException(status_code=400, detail="No collections selected")
    
    try:
        mongo = get_mongo()
        
        # Create in-memory ZIP file
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            total_collections = len(body.collections)
            logger.info(f"Starting bulk export of {total_collections} collections")
            
            for idx, collection_info in enumerate(body.collections, 1):
                logger.info(f"Processing collection {idx}/{total_collections}: {collection_info.get('collection')}")
                source = collection_info.get("source")
                collection_name = collection_info.get("collection")
                
                if not source or not collection_name:
                    continue
                
                try:
                    # Select database
                    # Handle collection_name that might already have prefix (e.g., "shared.recordings")
                    if collection_name.startswith("shared."):
                        db = mongo.shared_async_db
                        actual_collection = collection_name.replace("shared.", "")
                        source = "shared"  # Override source if collection name has prefix
                    elif collection_name.startswith("gemini."):
                        from backend.api.v1.ai_processed import get_gemini_db
                        gemini_db_sync = get_gemini_db()
                        actual_collection = collection_name.replace("gemini.", "")
                        source = "gemini"  # Override source if collection name has prefix
                        db = None
                    elif source == 'shared' or source == 'other':
                        db = mongo.shared_async_db
                        actual_collection = collection_name
                    elif source == 'gemini':
                        from backend.api.v1.ai_processed import get_gemini_db
                        gemini_db_sync = get_gemini_db()
                        actual_collection = collection_name
                        db = None
                    else:
                        db = mongo.async_db
                        actual_collection = collection_name
                    
                    # Build query filter
                    query_filter = {}
                    if body.start_date or body.end_date:
                        if source == 'gemini' and actual_collection == 'recordings_daily':
                            date_filter = {}
                            if body.start_date:
                                date_filter['$gte'] = body.start_date
                            if body.end_date:
                                date_filter['$lte'] = body.end_date
                            if date_filter:
                                query_filter['target_date'] = date_filter
                        else:
                            timestamp_fields = ['timestamp', 'posted_at', 'created_at', 'updated_at', 'committed_at']
                            timestamp_field = None
                            
                            if source == 'gemini':
                                sample_doc = gemini_db_sync[actual_collection].find_one({})
                            else:
                                sample_doc = await db[actual_collection].find_one({})
                            
                            if sample_doc:
                                for field in timestamp_fields:
                                    if field in sample_doc:
                                        timestamp_field = field
                                        break
                            
                            if timestamp_field:
                                date_filter = {}
                                if body.start_date:
                                    try:
                                        date_filter['$gte'] = datetime.fromisoformat(body.start_date)
                                    except ValueError:
                                        date_filter['$gte'] = body.start_date
                                if body.end_date:
                                    try:
                                        end_dt = datetime.fromisoformat(body.end_date) + timedelta(days=1)
                                        date_filter['$lt'] = end_dt
                                    except ValueError:
                                        date_filter['$lte'] = body.end_date + "T23:59:59"
                                
                                if date_filter:
                                    query_filter[timestamp_field] = date_filter
                    
                    # Query documents with batching for large collections
                    if source == 'gemini':
                        cursor = gemini_db_sync[actual_collection].find(query_filter)
                        if body.limit:
                            cursor = cursor.limit(body.limit)
                        documents = list(cursor)
                    else:
                        cursor = db[actual_collection].find(query_filter)
                        if body.limit:
                            cursor = cursor.limit(body.limit)
                        # Use batch processing for large collections to avoid memory issues
                        # Process in chunks to yield control periodically
                        max_docs = body.limit or 100000
                        documents = []
                        count = 0
                        async for doc in cursor:
                            documents.append(doc)
                            count += 1
                            if count >= max_docs:
                                break
                            # Yield control periodically for large collections (every 10000 docs)
                            if count % 10000 == 0:
                                await asyncio.sleep(0)  # Yield to event loop
                    
                    if not documents:
                        continue
                    
                    # Convert documents
                    rows = []
                    for doc in documents:
                        clean_doc = {}
                        for key, value in doc.items():
                            if isinstance(value, ObjectId):
                                clean_doc[key] = str(value)
                            elif isinstance(value, datetime):
                                clean_doc[key] = value.isoformat()
                            elif isinstance(value, (dict, list)):
                                clean_doc[key] = json.dumps(value, default=str, ensure_ascii=False)
                            else:
                                clean_doc[key] = value
                        rows.append(clean_doc)
                    
                    # Generate file content based on format
                    if body.format == "json":
                        file_content = json.dumps(rows, indent=2, ensure_ascii=False, default=str)
                        file_ext = "json"
                    elif body.format == "toon":
                        toon_data = {actual_collection: rows}
                        file_content = encode_toon(toon_data, indent=2, delimiter=',')
                        file_ext = "toon"
                    else:  # CSV
                        output_stream = io.StringIO()
                        if rows:
                            # Collect all possible fieldnames from all rows
                            all_fieldnames = set()
                            for row in rows:
                                all_fieldnames.update(row.keys())
                            fieldnames = sorted(list(all_fieldnames))
                            
                            writer = csv.DictWriter(output_stream, fieldnames=fieldnames, extrasaction='ignore')
                            writer.writeheader()
                            writer.writerows(rows)
                        file_content = output_stream.getvalue()
                        file_ext = "csv"
                    
                    # Add to ZIP
                    # Remove database prefix from collection name for filename
                    clean_collection_name = re.sub(r'^(main|shared|gemini)\.', '', actual_collection) if isinstance(actual_collection, str) else actual_collection
                    date_suffix = f"_{body.start_date or 'all'}_{body.end_date or 'all'}" if (body.start_date or body.end_date) else ""
                    zip_filename = f"{source}_{clean_collection_name}{date_suffix}.{file_ext}"
                    
                    # Ensure file_content is bytes for ZIP
                    if isinstance(file_content, str):
                        file_content_bytes = file_content.encode('utf-8')
                    else:
                        file_content_bytes = file_content
                    
                    zip_file.writestr(zip_filename, file_content_bytes)
                    logger.info(f"Added {zip_filename} to ZIP ({len(rows)} documents, {body.format.upper()} format)")
                    
                except Exception as e:
                    logger.error(f"Failed to export {collection_name}: {e}", exc_info=True)
                    continue
        
        zip_buffer.seek(0)
        zip_data = zip_buffer.getvalue()
        
        # Check if ZIP is empty or corrupted
        if len(zip_data) < 22:  # Minimum ZIP file size (empty ZIP is ~22 bytes)
            logger.warning("Generated ZIP file is empty or too small")
            raise HTTPException(
                status_code=400, 
                detail="No data was exported. All collections may be empty or failed to export."
            )
        
        # Verify ZIP file integrity
        try:
            test_zip = zipfile.ZipFile(io.BytesIO(zip_data), 'r')
            file_list = test_zip.namelist()
            test_zip.close()
            
            if not file_list:
                logger.warning("ZIP file contains no files")
                raise HTTPException(
                    status_code=400,
                    detail="No files were added to the ZIP. All collections may be empty or failed to export."
                )
            
            logger.info(f"ZIP file created successfully with {len(file_list)} files: {', '.join(file_list[:5])}{'...' if len(file_list) > 5 else ''}")
        except zipfile.BadZipFile as e:
            logger.error(f"Generated ZIP file is corrupted: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to create ZIP file. The file may be corrupted."
            )
        
        # Generate ZIP filename
        date_suffix = f"_{body.start_date or 'all'}_{body.end_date or 'all'}" if (body.start_date or body.end_date) else ""
        zip_filename = f"collections_export{date_suffix}.zip"
        
        return StreamingResponse(
            iter([zip_data]),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
        )
        
    except Exception as e:
        logger.error(f"Error exporting collections bulk: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/custom-export/members")
async def export_members(
    request: Request,
    format: str = Query("csv", regex="^(csv|json|toon)$")
):
    """
    Export members list in CSV, JSON, or TOON format
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        # Query members collection
        cursor = db['members'].find({}).sort('name', 1)
        members_docs = await cursor.to_list(length=10000)
        
        members = []
        for doc in members_docs:
            members.append({
                'id': str(doc['_id']),
                'name': doc.get('name'),
                'email': doc.get('email'),
                'role': doc.get('role'),
                'team': doc.get('team'),
                'created_at': doc.get('created_at').isoformat() if doc.get('created_at') else None
            })
        
        if format == 'json':
            output = json.dumps(members, indent=2, ensure_ascii=False)
            filename = f"members_{datetime.now().strftime('%Y%m%d')}.json"
            media_type = "application/json"
            
        elif format == 'toon':
            toon_data = {"members": members}
            output = encode_toon(toon_data, indent=2, delimiter=',')
            filename = f"members_{datetime.now().strftime('%Y%m%d')}.toon"
            media_type = "text/plain"
            
        else:  # CSV
            output_stream = io.StringIO()
            fieldnames = ['id', 'name', 'email', 'role', 'team', 'created_at']
            writer = csv.DictWriter(output_stream, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(members)
            output = output_stream.getvalue()
            filename = f"members_{datetime.now().strftime('%Y%m%d')}.csv"
            media_type = "text/csv"
        
        return StreamingResponse(
            iter([output]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Error exporting members: {e}")
        raise HTTPException(status_code=500, detail=str(e))
