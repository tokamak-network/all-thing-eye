"""
Activities API endpoints (MongoDB Version)

Provides activity data across all sources from MongoDB
"""

from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from src.utils.logger import get_logger
from src.core.mongo_manager import get_mongo_manager

# Get MongoDB manager instance
def get_mongo():
    from backend.main import mongo_manager
    return mongo_manager

logger = get_logger(__name__)

router = APIRouter()


# Cache for member mappings to avoid repeated DB queries
_member_mapping_cache = {}

async def load_member_mappings(db) -> dict:
    """
    Load all member mappings into memory for fast lookup
    
    Returns:
        Dict with structure: {
            'github': {'username': 'MemberName', ...},
            'slack': {'U12345': 'MemberName', ...},
            'notion': {'notion-id': 'MemberName', ...},
            'drive': {'email@domain.com': 'MemberName', ...}
        }
    """
    global _member_mapping_cache
    
    # Return cached if available
    if _member_mapping_cache:
        return _member_mapping_cache
    
    try:
        mappings = {
            'github': {},
            'slack': {},
            'notion': {},
            'drive': {}
        }
        
        # Load all member_identifiers
        async for identifier in db["member_identifiers"].find({}):
            source = identifier.get("source")
            identifier_value = identifier.get("identifier_value")
            member_name = identifier.get("member_name")
            
            if source and identifier_value and member_name:
                # Case-insensitive key for GitHub and email
                if source in ['github', 'drive']:
                    key = identifier_value.lower()
                else:
                    key = identifier_value
                
                mappings[source][key] = member_name
        
        _member_mapping_cache = mappings
        logger.info(f"Loaded member mappings: GitHub={len(mappings['github'])}, Slack={len(mappings['slack'])}, Notion={len(mappings['notion'])}, Drive={len(mappings['drive'])}")
        return mappings
        
    except Exception as e:
        logger.error(f"Failed to load member mappings: {e}")
        return {'github': {}, 'slack': {}, 'notion': {}, 'drive': {}}


def get_mapped_member_name(mappings: dict, source: str, identifier: str) -> str:
    """
    Get member name from pre-loaded mappings (fast, no DB query)
    
    Args:
        mappings: Pre-loaded member mappings dict
        source: Source name (github, slack, notion, drive)
        identifier: Identifier value to look up
    
    Returns:
        Member display name with capitalized first letter
    """
    if not identifier or source not in mappings:
        return identifier
    
    # Case-insensitive lookup for GitHub and Drive
    if source in ['github', 'drive']:
        key = identifier.lower()
    else:
        key = identifier
    
    name = mappings[source].get(key, identifier)
    
    # Ensure first letter is capitalized for consistency
    if name and isinstance(name, str):
        return name[0].upper() + name[1:] if len(name) > 0 else name
    
    return name


def get_identifiers_for_member(mappings: dict, source: str, member_name: str) -> list:
    """
    Reverse lookup: Get all identifiers for a member name (for filtering)
    
    Args:
        mappings: Pre-loaded member mappings dict
        source: Source name (github, slack, notion, drive)
        member_name: Member display name (e.g., "Ale")
    
    Returns:
        List of identifiers for this member in the source
    """
    if not member_name or source not in mappings:
        return []
    
    identifiers = []
    for identifier, name in mappings[source].items():
        # Case-insensitive comparison
        if name.lower() == member_name.lower():
            identifiers.append(identifier)
    
    return identifiers


# Response models
class ActivityResponse(BaseModel):
    id: str
    member_name: str
    source_type: str
    activity_type: str
    timestamp: str
    metadata: dict = {}


class ActivityListResponse(BaseModel):
    total: int
    activities: List[ActivityResponse]
    filters: dict


@router.get("/activities", response_model=ActivityListResponse)
async def get_activities(
    request: Request,
    source_type: Optional[str] = Query(None, description="Filter by source (github, slack, notion, google_drive)"),
    activity_type: Optional[str] = Query(None, description="Filter by activity type"),
    member_name: Optional[str] = Query(None, description="Filter by member name"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Get list of activities with filters from MongoDB
    
    Returns:
        Paginated list of activities from various collections
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        activities = []
        
        # Load member mappings once for all activities (performance optimization)
        member_mappings = await load_member_mappings(db)
        
        # Determine which sources to query
        sources_to_query = [source_type] if source_type else ['github', 'slack', 'notion', 'drive', 'recordings']
        
        # Build date filter
        date_filter = {}
        if start_date:
            date_filter['$gte'] = datetime.fromisoformat(start_date)
        if end_date:
            date_filter['$lte'] = datetime.fromisoformat(end_date)
        
        for source in sources_to_query:
            if source == 'github':
                # GitHub commits
                if not activity_type or activity_type == 'commit':
                    commits = db["github_commits"]
                    query = {}
                    if member_name:
                        # Reverse lookup: Find identifiers for this member name
                        identifiers = get_identifiers_for_member(member_mappings, 'github', member_name)
                        if identifiers:
                            query['author_name'] = {'$in': identifiers}
                        else:
                            # No identifiers found, query won't match anything
                            query['author_name'] = member_name
                    if date_filter:
                        query['date'] = date_filter
                    
                    async for commit in commits.find(query).sort("date", -1).limit(limit):
                        commit_date = commit.get('date')
                        # Add 'Z' to indicate UTC timezone for proper frontend conversion
                        if isinstance(commit_date, datetime):
                            timestamp_str = commit_date.isoformat() + 'Z' if commit_date.tzinfo is None else commit_date.isoformat()
                        else:
                            timestamp_str = str(commit_date) if commit_date else ''
                        
                        # Build commit URL (use existing URL or construct it)
                        repo_name = commit.get('repository', '')
                        sha = commit.get('sha', '')
                        commit_url = commit.get('url') or (f"https://github.com/tokamak-network/{repo_name}/commit/{sha}" if repo_name and sha else None)
                        
                        # Map GitHub username to member name
                        github_username = commit.get('author_name', '')
                        member_name = get_mapped_member_name(member_mappings, 'github', github_username)
                        
                        activities.append(ActivityResponse(
                            id=str(commit['_id']),
                            member_name=member_name,
                            source_type='github',
                            activity_type='commit',
                            timestamp=timestamp_str,
                            metadata={
                                'sha': sha,
                                'message': commit.get('message'),
                                'repository': repo_name,
                                'additions': commit.get('additions', 0),
                                'deletions': commit.get('deletions', 0),
                                'url': commit_url
                            }
                        ))
                
                # GitHub PRs
                if not activity_type or activity_type == 'pull_request':
                    prs = db["github_pull_requests"]
                    query = {}
                    if member_name:
                        # Reverse lookup: Find identifiers for this member name
                        identifiers = get_identifiers_for_member(member_mappings, 'github', member_name)
                        if identifiers:
                            query['author'] = {'$in': identifiers}
                        else:
                            query['author'] = member_name
                    if date_filter:
                        query['created_at'] = date_filter
                    
                    async for pr in prs.find(query).sort("created_at", -1).limit(limit):
                        created_at = pr.get('created_at')
                        # Add 'Z' to indicate UTC timezone for proper frontend conversion
                        if isinstance(created_at, datetime):
                            timestamp_str = created_at.isoformat() + 'Z' if created_at.tzinfo is None else created_at.isoformat()
                        else:
                            timestamp_str = str(created_at) if created_at else ''
                        
                        # Map GitHub username to member name
                        github_username = pr.get('author', '')
                        member_name = get_mapped_member_name(member_mappings, 'github', github_username)
                        
                        # PR URL
                        pr_url = pr.get('url')
                        
                        activities.append(ActivityResponse(
                            id=str(pr['_id']),
                            member_name=member_name,
                            source_type='github',
                            activity_type='pull_request',
                            timestamp=timestamp_str,
                            metadata={
                                'number': pr.get('number'),
                                'title': pr.get('title'),
                                'repository': pr.get('repository'),
                                'state': pr.get('state'),
                                'url': pr_url
                            }
                        ))
            
            elif source == 'slack':
                messages = db["slack_messages"]
                query = {}
                if member_name:
                    # Reverse lookup: Find user_ids and emails for this member name
                    identifiers = get_identifiers_for_member(member_mappings, 'slack', member_name)
                    if identifiers:
                        # Search by user_id or user_email
                        query['$or'] = [
                            {'user_id': {'$in': identifiers}},
                            {'user_email': {'$in': identifiers}}
                        ]
                    else:
                        # Fallback to name search
                        query['user_name'] = member_name
                if date_filter:
                    query['posted_at'] = date_filter
                
                async for msg in messages.find(query).sort("posted_at", -1).limit(limit):
                    posted_at = msg.get('posted_at')
                    # Add 'Z' to indicate UTC timezone for proper frontend conversion
                    if isinstance(posted_at, datetime):
                        timestamp_str = posted_at.isoformat() + 'Z' if posted_at.tzinfo is None else posted_at.isoformat()
                    else:
                        timestamp_str = str(posted_at) if posted_at else ''
                    
                    # Determine activity type
                    ts = msg.get('ts', '')
                    thread_ts = msg.get('thread_ts', '')
                    has_files = len(msg.get('files', [])) > 0
                    is_thread_reply = thread_ts and str(thread_ts) != str(ts)
                    
                    if is_thread_reply:
                        activity_type = 'thread_reply'
                    elif has_files:
                        activity_type = 'file_share'
                    else:
                        activity_type = 'message'
                    
                    # Build Slack message URL
                    channel_id = msg.get('channel_id', '')
                    if channel_id and ts:
                        # Convert ts (1763525860.094349) to Slack URL format (p1763525860094349)
                        ts_formatted = ts.replace('.', '')
                        slack_url = f"https://tokamak-network.slack.com/archives/{channel_id}/p{ts_formatted}"
                    else:
                        slack_url = None
                    
                    # Map Slack user to member name
                    # Try: user_id → user_email → user_name (capitalized)
                    slack_user_id = msg.get('user_id') or msg.get('user', '')
                    slack_user_email = msg.get('user_email', '').lower() if msg.get('user_email') else None
                    slack_user_name = msg.get('user_name', '')
                    
                    # Try mapping in order: user_id, user_email, then fall back to user_name
                    member_name = slack_user_name.capitalize() if slack_user_name else slack_user_id
                    
                    # Try to find better mapping
                    if slack_user_id:
                        mapped = get_mapped_member_name(member_mappings, 'slack', slack_user_id)
                        if mapped and mapped != slack_user_id:
                            member_name = mapped
                    
                    if member_name == slack_user_id or not member_name:  # Still using ID, try email
                        if slack_user_email:
                            mapped = get_mapped_member_name(member_mappings, 'slack', slack_user_email)
                            if mapped and '@' not in mapped:
                                member_name = mapped
                    
                    activities.append(ActivityResponse(
                        id=str(msg['_id']),
                        member_name=member_name,
                        source_type='slack',
                        activity_type=activity_type,
                        timestamp=timestamp_str,
                        metadata={
                            'channel': msg.get('channel_name'),
                            'channel_id': channel_id,
                            'text': msg.get('text', '')[:200],
                            'reactions': len(msg.get('reactions', [])),
                            'links': len(msg.get('links', [])),
                            'files': len(msg.get('files', [])),
                            'reply_count': msg.get('reply_count', 0),
                            'url': slack_url,
                            'is_thread': is_thread_reply
                        }
                    ))
            
            elif source == 'notion':
                pages = db["notion_pages"]
                query = {}
                if member_name:
                    # Reverse lookup: Find UUIDs for this member name
                    identifiers = get_identifiers_for_member(member_mappings, 'notion', member_name)
                    if identifiers:
                        query['created_by.id'] = {'$in': identifiers}
                    else:
                        # Fallback to name search (less reliable)
                        query['created_by.name'] = {"$regex": f"^{member_name}", "$options": "i"}
                if date_filter:
                    query['created_time'] = date_filter
                
                async for page in pages.find(query).sort("created_time", -1).limit(limit):
                    created_time = page.get('created_time')
                    # Add 'Z' to indicate UTC timezone for proper frontend conversion
                    if isinstance(created_time, datetime):
                        timestamp_str = created_time.isoformat() + 'Z' if created_time.tzinfo is None else created_time.isoformat()
                    else:
                        timestamp_str = str(created_time) if created_time else ''
                    
                    # Map Notion user to member name (MUST use members.yaml standard name)
                    notion_user = page.get('created_by', {})
                    notion_user_name = notion_user.get('name', '')
                    notion_user_email = notion_user.get('email', '')
                    notion_user_id = notion_user.get('id', '')
                    
                    # Priority 1: Map by email (most reliable)
                    member_name = None
                    if notion_user_email:
                        member_name = get_mapped_member_name(member_mappings, 'notion', notion_user_email)
                        if member_name and '@' not in member_name:
                            # Successfully mapped to members.yaml name
                            pass
                        else:
                            member_name = None
                    
                    # Priority 2: Map by UUID
                    if not member_name and notion_user_id:
                        member_name = get_mapped_member_name(member_mappings, 'notion', notion_user_id)
                        if member_name and member_name != notion_user_id and 'Notion-' not in member_name:
                            # Successfully mapped
                            pass
                        else:
                            member_name = None
                    
                    # Priority 3: Extract first name from full name (fallback)
                    if not member_name and notion_user_name:
                        # "Manish Kumar" → "Manish", "Jaden Kong" → "Jaden"
                        first_name = notion_user_name.split()[0] if ' ' in notion_user_name else notion_user_name
                        member_name = first_name.capitalize() if first_name else None
                    
                    # Priority 4: Use short UUID if nothing else works
                    if not member_name:
                        member_name = f"Notion-{notion_user_id[:8]}" if notion_user_id else "Unknown"
                    
                    activities.append(ActivityResponse(
                        id=str(page['_id']),
                        member_name=member_name,
                        source_type='notion',
                        activity_type='page_created',
                        timestamp=timestamp_str,
                        metadata={
                            'title': page.get('title'),
                            'comments': page.get('comments_count', 0)
                        }
                    ))
            
            elif source == 'drive':
                drive_activities = db["drive_activities"]
                query = {}
                if member_name:
                    # Reverse lookup: Find emails for this member name
                    identifiers = get_identifiers_for_member(member_mappings, 'drive', member_name)
                    if identifiers:
                        query['user_email'] = {'$in': identifiers}
                    else:
                        # Fallback to regex search
                        query['user_email'] = {"$regex": member_name, "$options": "i"}
                if date_filter:
                    query['timestamp'] = date_filter
                
                async for activity in drive_activities.find(query).sort("timestamp", -1).limit(limit):
                    timestamp_val = activity.get('timestamp')
                    # Add 'Z' to indicate UTC timezone for proper frontend conversion
                    if isinstance(timestamp_val, datetime):
                        timestamp_str = timestamp_val.isoformat() + 'Z' if timestamp_val.tzinfo is None else timestamp_val.isoformat()
                    else:
                        timestamp_str = str(timestamp_val) if timestamp_val else ''
                    
                    # Map Drive email to member name (MUST use members.yaml standard name)
                    user_email = activity.get('user_email', '')
                    
                    # Try mapping first
                    member_name = get_mapped_member_name(member_mappings, 'drive', user_email) if user_email else ''
                    
                    # If mapping returns the email itself (not mapped), extract username and capitalize
                    if not member_name or '@' in member_name:
                        username = user_email.split('@')[0] if user_email else 'Unknown'
                        member_name = username.capitalize() if username else 'Unknown'
                    
                    activities.append(ActivityResponse(
                        id=str(activity['_id']),
                        member_name=member_name,
                        source_type='drive',
                        activity_type=activity.get('event_name', 'activity'),
                        timestamp=timestamp_str,
                        metadata={
                            'action': activity.get('action'),
                            'doc_title': activity.get('doc_title'),
                            'doc_type': activity.get('doc_type')
                        }
                    ))
            
            elif source == 'recordings':
                shared_db = mongo.shared_async_db
                recordings = shared_db["recordings"]
                query = {}
                if member_name:
                    query['createdBy'] = {"$regex": member_name, "$options": "i"}
                if date_filter:
                    query['modifiedTime'] = date_filter
                
                async for recording in recordings.find(query).sort("modifiedTime", -1).limit(limit):
                    modified_time = recording.get('modifiedTime')
                    # Add 'Z' to indicate UTC timezone for proper frontend conversion
                    if isinstance(modified_time, datetime):
                        timestamp_str = modified_time.isoformat() + 'Z' if modified_time.tzinfo is None else modified_time.isoformat()
                    else:
                        timestamp_str = str(modified_time) if modified_time else ''
                    
                    activities.append(ActivityResponse(
                        id=str(recording['_id']),
                        member_name=recording.get('createdBy', ''),
                        source_type='recordings',
                        activity_type='meeting_recording',
                        timestamp=timestamp_str,
                        metadata={
                            'name': recording.get('name'),
                            'size': recording.get('size', 0),
                            'recording_id': recording.get('id'),  # Google Drive file ID
                            'webViewLink': recording.get('webViewLink')  # Google Docs link
                        }
                    ))
        
        # Sort all activities by timestamp descending (newest first)
        # Empty timestamps are treated as oldest
        def sort_key(activity):
            if not activity.timestamp:
                return datetime.min  # Oldest possible datetime
            try:
                # Parse ISO timestamp (with or without Z)
                ts = activity.timestamp.replace('Z', '+00:00')
                return datetime.fromisoformat(ts)
            except:
                return datetime.min
        
        activities.sort(key=sort_key, reverse=True)
        
        # Apply offset and limit
        total = len(activities)
        activities = activities[offset:offset+limit]
        
        return ActivityListResponse(
            total=total,
            activities=activities,
            filters={
                'source_type': source_type,
                'activity_type': activity_type,
                'member_name': member_name,
                'start_date': start_date,
                'end_date': end_date,
                'limit': limit,
                'offset': offset
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching activities: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch activities")


@router.get("/activities/summary")
async def get_activities_summary(
    request: Request,
    source_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """
    Get activity summary statistics using MongoDB aggregation
    
    Returns:
        Summary statistics grouped by source and activity type
    """
    try:
        db = get_mongo().db
        summary = {}
        
        # Build date filter
        date_filter = {}
        if start_date:
            date_filter['$gte'] = datetime.fromisoformat(start_date)
        if end_date:
            date_filter['$lte'] = datetime.fromisoformat(end_date)
        
        sources_to_query = [source_type] if source_type else ['github', 'slack', 'notion', 'drive', 'recordings']
        
        for source in sources_to_query:
            source_summary = {
                'total_activities': 0,
                'activity_types': {}
            }
            
            if source == 'github':
                # Commits
                commits = db["github_commits"]
                query = {}
                if date_filter:
                    query['committed_at'] = date_filter
                
                pipeline = [
                    {"$match": query},
                    {"$group": {
                        "_id": None,
                        "count": {"$sum": 1},
                        "unique_authors": {"$addToSet": "$author_login"}
                    }}
                ]
                result = list(commits.aggregate(pipeline))
                if result:
                    commit_count = result[0]['count']
                    source_summary['total_activities'] += commit_count
                    source_summary['activity_types']['commit'] = {
                        'count': commit_count,
                        'unique_members': len(result[0]['unique_authors'])
                    }
                
                # PRs
                prs = db["github_pull_requests"]
                pr_count = prs.count_documents(query if date_filter else {})
                if pr_count > 0:
                    source_summary['total_activities'] += pr_count
                    source_summary['activity_types']['pull_request'] = {
                        'count': pr_count
                    }
            
            elif source == 'slack':
                messages = db["slack_messages"]
                query = {}
                if date_filter:
                    query['posted_at'] = date_filter
                
                pipeline = [
                    {"$match": query},
                    {"$group": {
                        "_id": None,
                        "count": {"$sum": 1},
                        "unique_users": {"$addToSet": "$user_name"}
                    }}
                ]
                result = list(messages.aggregate(pipeline))
                if result:
                    msg_count = result[0]['count']
                    source_summary['total_activities'] = msg_count
                    source_summary['activity_types']['message'] = {
                        'count': msg_count,
                        'unique_members': len(result[0]['unique_users'])
                    }
            
            elif source == 'notion':
                pages = db["notion_pages"]
                query = {}
                if date_filter:
                    query['created_time'] = date_filter
                
                page_count = pages.count_documents(query)
                if page_count > 0:
                    source_summary['total_activities'] = page_count
                    source_summary['activity_types']['page_created'] = {
                        'count': page_count
                    }
            
            elif source == 'drive':
                drive_activities = db["drive_activities"]
                query = {}
                if date_filter:
                    query['timestamp'] = date_filter
                
                drive_count = drive_activities.count_documents(query)
                if drive_count > 0:
                    source_summary['total_activities'] = drive_count
            
            elif source == 'recordings':
                shared_db = get_mongo().shared_db
                recordings = shared_db["recordings"]
                query = {}
                if date_filter:
                    query['modifiedTime'] = date_filter
                
                pipeline = [
                    {"$match": query},
                    {"$group": {
                        "_id": None,
                        "count": {"$sum": 1},
                        "unique_creators": {"$addToSet": "$createdBy"}
                    }}
                ]
                result = list(recordings.aggregate(pipeline))
                if result:
                    recording_count = result[0]['count']
                    source_summary['total_activities'] = recording_count
                    source_summary['activity_types']['meeting_recording'] = {
                        'count': recording_count,
                        'unique_members': len(result[0]['unique_creators'])
                    }
            
            if source_summary['total_activities'] > 0:
                summary[source] = source_summary
        
        return {
            'summary': summary,
            'filters': {
                'source_type': source_type,
                'start_date': start_date,
                'end_date': end_date
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching activity summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch activity summary")


@router.get("/activities/types")
async def get_activity_types(
    request: Request,
    source_type: Optional[str] = Query(None)
):
    """
    Get list of available activity types from MongoDB
    
    Returns:
        List of activity types grouped by source
    """
    try:
        types = {
            'github': ['commit', 'pull_request', 'issue'],
            'slack': ['message', 'reaction'],
            'notion': ['page_created', 'page_edited', 'comment_added'],
            'drive': ['create', 'edit', 'upload', 'download', 'share'],
            'recordings': ['meeting_recording']
        }
        
        if source_type:
            if source_type in types:
                return {
                    'activity_types': {source_type: types[source_type]}
                }
            else:
                return {'activity_types': {}}
        
        return {
            'activity_types': types
        }
        
    except Exception as e:
        logger.error(f"Error fetching activity types: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch activity types")

