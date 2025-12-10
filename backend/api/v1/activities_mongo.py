"""
Activities API endpoints (MongoDB Version)

Provides activity data across all sources from MongoDB
"""

from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone

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
            'github': {'username_lower': {'original': 'Username', 'member': 'MemberName'}, ...},
            'slack': {'U12345': {'original': 'U12345', 'member': 'MemberName'}, ...},
            'notion': {'notion-id': {'original': 'notion-id', 'member': 'MemberName'}, ...},
            'drive': {'email_lower': {'original': 'email@domain.com', 'member': 'MemberName'}, ...}
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
                # Case-insensitive key for GitHub and email, but keep original value
                if source in ['github', 'drive']:
                    key = identifier_value.lower()
                else:
                    key = identifier_value
                
                # Store both original identifier and member name
                mappings[source][key] = {
                    'original': identifier_value,
                    'member': member_name
                }
        
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
    
    mapping_entry = mappings[source].get(key)
    if mapping_entry and isinstance(mapping_entry, dict):
        name = mapping_entry.get('member', identifier)
    else:
        name = identifier
    
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
        List of original identifiers for this member in the source
    """
    if not member_name or source not in mappings:
        return []
    
    identifiers = []
    for key, mapping_entry in mappings[source].items():
        if isinstance(mapping_entry, dict):
            stored_member = mapping_entry.get('member', '')
            original_identifier = mapping_entry.get('original', key)
        else:
            # Backward compatibility if entry is just a string
            stored_member = mapping_entry
            original_identifier = key
        
        # Case-insensitive comparison
        if stored_member.lower() == member_name.lower():
            identifiers.append(original_identifier)
    
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
    member_name: Optional[str] = Query(None, description="Filter by member name (for recordings and daily analysis, filters by participant)"),
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
        
        # IMPORTANT: Store filter member_name separately to avoid overwriting in loops
        filter_member_name = member_name
        
        # Load member mappings once for all activities (performance optimization)
        member_mappings = await load_member_mappings(db)
        
        # Determine which sources to query
        sources_to_query = [source_type] if source_type else ['github', 'slack', 'notion', 'drive', 'recordings', 'recordings_daily']
        
        # Build date filter
        # MongoDB stores datetimes as timezone-naive (assumed UTC)
        # Convert to timezone-naive UTC for MongoDB query compatibility
        date_filter = {}
        if start_date:
            # Parse datetime and convert to UTC timezone-naive for MongoDB
            start_str = start_date.replace('Z', '+00:00') if start_date.endswith('Z') else start_date
            start_dt = datetime.fromisoformat(start_str)
            # Convert to UTC if timezone-aware, then remove timezone info for MongoDB
            if start_dt.tzinfo is not None:
                start_dt = start_dt.astimezone(timezone.utc).replace(tzinfo=None)
            date_filter['$gte'] = start_dt
        if end_date:
            # Parse datetime and convert to UTC timezone-naive for MongoDB
            end_str = end_date.replace('Z', '+00:00') if end_date.endswith('Z') else end_date
            end_dt = datetime.fromisoformat(end_str)
            # Convert to UTC if timezone-aware, then remove timezone info for MongoDB
            if end_dt.tzinfo is not None:
                end_dt = end_dt.astimezone(timezone.utc).replace(tzinfo=None)
            date_filter['$lte'] = end_dt
        
        for source in sources_to_query:
            if source == 'github':
                # GitHub commits
                if not activity_type or activity_type == 'commit':
                    commits = db["github_commits"]
                    query = {}
                    if filter_member_name:
                        # Reverse lookup: Find identifiers for this member name
                        identifiers = get_identifiers_for_member(member_mappings, 'github', filter_member_name)
                        if identifiers:
                            query['author_name'] = {'$in': identifiers}
                        else:
                            # No identifiers found, query won't match anything
                            query['author_name'] = filter_member_name
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
                        display_member_name = get_mapped_member_name(member_mappings, 'github', github_username)
                        
                        activities.append(ActivityResponse(
                            id=str(commit['_id']),
                            member_name=display_member_name,
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
                    if filter_member_name:
                        # Reverse lookup: Find identifiers for this member name
                        identifiers = get_identifiers_for_member(member_mappings, 'github', filter_member_name)
                        if identifiers:
                            query['author'] = {'$in': identifiers}
                        else:
                            query['author'] = filter_member_name
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
                        display_member_name = get_mapped_member_name(member_mappings, 'github', github_username)
                        
                        # PR URL
                        pr_url = pr.get('url')
                        
                        activities.append(ActivityResponse(
                            id=str(pr['_id']),
                            member_name=display_member_name,
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
                if filter_member_name:
                    # Reverse lookup: Find user_ids and emails for this member name
                    identifiers = get_identifiers_for_member(member_mappings, 'slack', filter_member_name)
                    # Build $or conditions for multiple search fields
                    or_conditions = []
                    if identifiers:
                        or_conditions.append({'user_id': {'$in': identifiers}})
                        or_conditions.append({'user_email': {'$in': identifiers}})
                    # Always add user_name search as fallback (case-insensitive)
                    or_conditions.append({'user_name': {'$regex': f'^{filter_member_name}$', '$options': 'i'}})
                    query['$or'] = or_conditions
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
                        slack_activity_type = 'thread_reply'
                    elif has_files:
                        slack_activity_type = 'file_share'
                    else:
                        slack_activity_type = 'message'
                    
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
                    display_member_name = slack_user_name.capitalize() if slack_user_name else slack_user_id
                    
                    # Try to find better mapping
                    if slack_user_id:
                        mapped = get_mapped_member_name(member_mappings, 'slack', slack_user_id)
                        if mapped and mapped != slack_user_id:
                            display_member_name = mapped
                    
                    if display_member_name == slack_user_id or not display_member_name:  # Still using ID, try email
                        if slack_user_email:
                            mapped = get_mapped_member_name(member_mappings, 'slack', slack_user_email)
                            if mapped and '@' not in mapped:
                                display_member_name = mapped
                    
                    activities.append(ActivityResponse(
                        id=str(msg['_id']),
                        member_name=display_member_name,
                        source_type='slack',
                        activity_type=slack_activity_type,
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
                if filter_member_name:
                    # Reverse lookup: Find UUIDs for this member name
                    identifiers = get_identifiers_for_member(member_mappings, 'notion', filter_member_name)
                    # Build $or conditions for multiple search fields
                    or_conditions = []
                    if identifiers:
                        or_conditions.append({'created_by.id': {'$in': identifiers}})
                        or_conditions.append({'created_by.email': {'$in': identifiers}})
                    # Always add name search as fallback (case-insensitive)
                    or_conditions.append({'created_by.name': {"$regex": f"^{filter_member_name}", "$options": "i"}})
                    query['$or'] = or_conditions
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
                    display_member_name = None
                    if notion_user_email:
                        display_member_name = get_mapped_member_name(member_mappings, 'notion', notion_user_email)
                        if display_member_name and '@' not in display_member_name:
                            # Successfully mapped to members.yaml name
                            pass
                        else:
                            display_member_name = None
                    
                    # Priority 2: Map by UUID
                    if not display_member_name and notion_user_id:
                        display_member_name = get_mapped_member_name(member_mappings, 'notion', notion_user_id)
                        if display_member_name and display_member_name != notion_user_id and 'Notion-' not in display_member_name:
                            # Successfully mapped
                            pass
                        else:
                            display_member_name = None
                    
                    # Priority 3: Extract first name from full name (fallback)
                    if not display_member_name and notion_user_name:
                        # "Manish Kumar" → "Manish", "Jaden Kong" → "Jaden"
                        first_name = notion_user_name.split()[0] if ' ' in notion_user_name else notion_user_name
                        display_member_name = first_name.capitalize() if first_name else None
                    
                    # Priority 4: Use short UUID if nothing else works
                    if not display_member_name:
                        display_member_name = f"Notion-{notion_user_id[:8]}" if notion_user_id else "Unknown"
                    
                    activities.append(ActivityResponse(
                        id=str(page['_id']),
                        member_name=display_member_name,
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
                if filter_member_name:
                    # Reverse lookup: Find emails for this member name
                    identifiers = get_identifiers_for_member(member_mappings, 'drive', filter_member_name)
                    if identifiers:
                        query['user_email'] = {'$in': identifiers}
                    else:
                        # Fallback to regex search
                        query['user_email'] = {"$regex": filter_member_name, "$options": "i"}
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
                    display_member_name = get_mapped_member_name(member_mappings, 'drive', user_email) if user_email else ''
                    
                    # If mapping returns the email itself (not mapped), extract username and capitalize
                    if not display_member_name or '@' in display_member_name:
                        username = user_email.split('@')[0] if user_email else 'Unknown'
                        display_member_name = username.capitalize() if username else 'Unknown'
                    
                    activities.append(ActivityResponse(
                        id=str(activity['_id']),
                        member_name=display_member_name,
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
                if date_filter:
                    query['modifiedTime'] = date_filter
                
                # For recordings, filter by participant (not createdBy)
                if filter_member_name:
                    from backend.api.v1.ai_processed import get_gemini_db
                    from bson import ObjectId
                    gemini_db = get_gemini_db()
                    gemini_recordings_col = gemini_db["recordings"]
                    
                    # Find meeting_ids where participant matches
                    # MongoDB array field search: use $expr with $regexMatch for array elements
                    # This works for MongoDB 4.2+
                    try:
                        # Try using $expr with $regexMatch for array field search
                        participant_query = {
                            "$expr": {
                                "$anyElementTrue": {
                                    "$map": {
                                        "input": "$participants",
                                        "as": "participant",
                                        "in": {
                                            "$regexMatch": {
                                                "input": "$$participant",
                                                "regex": filter_member_name,
                                                "options": "i"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        matching_meetings = list(gemini_recordings_col.find(
                            participant_query,
                            {"meeting_id": 1}
                        ))
                    except Exception:
                        # Fallback: filter in Python if MongoDB query fails
                        # Get all documents and filter in Python for case-insensitive partial match
                        all_meetings = list(gemini_recordings_col.find(
                            {},
                            {"meeting_id": 1, "participants": 1}
                        ))
                        matching_meetings = [
                            m for m in all_meetings
                            if m.get("participants") and any(
                                filter_member_name.lower() in p.lower() 
                                for p in m.get("participants", [])
                            )
                        ]
                    
                    # Extract meeting_ids (could be ObjectId or string)
                    matching_meeting_ids = []
                    for m in matching_meetings:
                        meeting_id = m.get('meeting_id')
                        if meeting_id:
                            # If it's already an ObjectId, use it directly
                            if isinstance(meeting_id, ObjectId):
                                matching_meeting_ids.append(meeting_id)
                            # If it's a string, try to convert to ObjectId
                            elif isinstance(meeting_id, str) and ObjectId.is_valid(meeting_id):
                                matching_meeting_ids.append(ObjectId(meeting_id))
                    
                    if matching_meeting_ids:
                        # Filter recordings by matching meeting_ids (using _id)
                        query['_id'] = {'$in': matching_meeting_ids}
                    else:
                        # No matching participants, return empty
                        query['_id'] = {'$in': []}
                
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
            
            elif source == 'recordings_daily':
                try:
                    # Get recordings_daily from gemini database
                    from backend.api.v1.ai_processed import get_gemini_db
                    gemini_db = get_gemini_db()
                    recordings_daily_col = gemini_db["recordings_daily"]
                    
                    query = {}
                    if date_filter:
                        # Use target_date for filtering
                        query['target_date'] = date_filter
                    
                    # Get documents (sync operation)
                    # Sort by timestamp if available, otherwise by target_date (as date, not string)
                    # We'll sort in Python after fetching to ensure proper date sorting
                    daily_docs = list(recordings_daily_col.find(query).limit(limit * 2))  # Fetch more to sort properly
                    
                    # Sort by target_date as date (not string) - newest first
                    def sort_daily_doc(doc):
                        target_date = doc.get('target_date')
                        if target_date:
                            try:
                                if isinstance(target_date, str):
                                    date_parts = target_date.split('-')
                                    if len(date_parts) == 3:
                                        year, month, day = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
                                        return datetime(year, month, day)
                            except (ValueError, TypeError):
                                pass
                        # Fallback to timestamp if available
                        timestamp = doc.get('timestamp')
                        if isinstance(timestamp, datetime):
                            return timestamp
                        return datetime.min
                    
                    daily_docs.sort(key=sort_daily_doc, reverse=True)
                    daily_docs = daily_docs[:limit]  # Limit after sorting
                    
                    for daily in daily_docs:
                        try:
                            # Filter by participant if member_name is specified
                            if filter_member_name:
                                analysis = daily.get('analysis', {})
                                participants = analysis.get('participants', [])
                                # Check if any participant name matches (case-insensitive)
                                participant_names = [p.get('name', '') for p in participants if isinstance(p, dict)]
                                if not any(filter_member_name.lower() in name.lower() for name in participant_names):
                                    continue  # Skip this daily analysis if participant doesn't match
                            
                            # Convert timestamp
                            timestamp = daily.get("timestamp")
                            if isinstance(timestamp, datetime):
                                timestamp_str = timestamp.isoformat() + 'Z' if timestamp.tzinfo is None else timestamp.isoformat()
                            else:
                                timestamp_str = str(timestamp) if timestamp else daily.get("target_date", "")
                            
                            activities.append(ActivityResponse(
                                id=str(daily.get('_id', '')),
                                member_name="System",  # Daily analysis is system-generated
                                source_type='recordings_daily',
                                activity_type='daily_analysis',
                                timestamp=timestamp_str,
                                metadata={
                                    'target_date': daily.get('target_date'),
                                    'meeting_count': daily.get('meeting_count', 0),
                                    'total_meeting_time': daily.get('total_meeting_time'),
                                    'status': daily.get('status'),
                                    'model_used': daily.get('model_used'),
                                    'meeting_titles': daily.get('meeting_titles', [])
                                }
                            ))
                        except Exception as e:
                            logger.warning(f"Error processing recordings_daily document {daily.get('_id')}: {e}")
                            continue
                except Exception as e:
                    logger.error(f"Error fetching recordings_daily: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    # Continue with other sources even if recordings_daily fails
        
        # Sort all activities by timestamp descending (newest first)
        # Empty timestamps are treated as oldest
        def sort_key(activity):
            # For recordings_daily, use target_date from metadata if timestamp is not available or is a date string
            if activity.source_type == 'recordings_daily':
                target_date = activity.metadata.get('target_date') if activity.metadata else None
                if target_date:
                    try:
                        # Parse target_date as YYYY-MM-DD format
                        if isinstance(target_date, str):
                            # Parse date string (YYYY-MM-DD)
                            date_parts = target_date.split('-')
                            if len(date_parts) == 3:
                                year, month, day = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
                                parsed_dt = datetime(year, month, day, tzinfo=timezone.utc)
                                return parsed_dt
                    except (ValueError, TypeError):
                        pass
            
            # For other activities or if target_date parsing fails, use timestamp
            if not activity.timestamp:
                # Use timezone-aware datetime.min for comparison
                return datetime.min.replace(tzinfo=timezone.utc)
            try:
                # Parse ISO timestamp (with or without Z)
                ts = activity.timestamp.replace('Z', '+00:00')
                parsed_dt = datetime.fromisoformat(ts)
                # Ensure timezone-aware
                if parsed_dt.tzinfo is None:
                    parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
                return parsed_dt
            except:
                # Use timezone-aware datetime.min for comparison
                return datetime.min.replace(tzinfo=timezone.utc)
        
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
                'member_name': filter_member_name,
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
        # Build date filter
        # MongoDB stores datetimes as timezone-naive (assumed UTC)
        # So we need to convert to timezone-naive for query compatibility
        date_filter = {}
        if start_date:
            # Parse datetime and convert to UTC timezone-naive for MongoDB
            start_str = start_date.replace('Z', '+00:00') if start_date.endswith('Z') else start_date
            start_dt = datetime.fromisoformat(start_str)
            # Convert to UTC if timezone-aware, then remove timezone info for MongoDB
            if start_dt.tzinfo is not None:
                start_dt = start_dt.astimezone(timezone.utc).replace(tzinfo=None)
            date_filter['$gte'] = start_dt
        if end_date:
            # Parse datetime and convert to UTC timezone-naive for MongoDB
            end_str = end_date.replace('Z', '+00:00') if end_date.endswith('Z') else end_date
            end_dt = datetime.fromisoformat(end_str)
            # Convert to UTC if timezone-aware, then remove timezone info for MongoDB
            if end_dt.tzinfo is not None:
                end_dt = end_dt.astimezone(timezone.utc).replace(tzinfo=None)
            date_filter['$lte'] = end_dt
        
        sources_to_query = [source_type] if source_type else ['github', 'slack', 'notion', 'drive', 'recordings', 'recordings_daily']
        
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

