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
    from backend.main_mongo import mongo_manager
    return mongo_manager

logger = get_logger(__name__)

router = APIRouter()


# Helper function to map GitHub username to member name
async def get_member_display_name(github_username: str, db) -> str:
    """Map GitHub username to member's display name from members collection"""
    if not github_username:
        return github_username
    
    try:
        # Look up member by GitHub username (case-insensitive)
        member_identifier = await db["member_identifiers"].find_one({
            "source": "github",
            "identifier_value": {"$regex": f"^{github_username}$", "$options": "i"}
        })
        
        if member_identifier:
            member = await db["members"].find_one({"_id": member_identifier["member_id"]})
            if member:
                logger.info(f"Mapped GitHub user '{github_username}' to '{member.get('name')}'")
                return member.get("name", github_username)
        
        logger.warning(f"No mapping found for GitHub user '{github_username}'")
        return github_username
    except Exception as e:
        logger.warning(f"Failed to map GitHub username {github_username}: {e}")
        return github_username


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
                        query['author_name'] = member_name
                    if date_filter:
                        query['date'] = date_filter
                    
                    async for commit in commits.find(query).sort("date", -1).limit(limit):
                        commit_date = commit.get('date')
                        timestamp_str = commit_date.isoformat() if isinstance(commit_date, datetime) else str(commit_date) if commit_date else ''
                        
                        # Get member display name
                        github_username = commit.get('author_name', '')
                        display_name = await get_member_display_name(github_username, db)
                        
                        # Build commit URL (use existing URL or construct it)
                        repo_name = commit.get('repository', '')
                        sha = commit.get('sha', '')
                        commit_url = commit.get('url') or (f"https://github.com/tokamak-network/{repo_name}/commit/{sha}" if repo_name and sha else None)
                        
                        activities.append(ActivityResponse(
                            id=str(commit['_id']),
                            member_name=display_name,
                            source_type='github',
                            activity_type='commit',
                            timestamp=timestamp_str,
                            metadata={
                                'sha': sha,
                                'message': commit.get('message'),
                                'repository': repo_name,
                                'additions': commit.get('additions', 0),
                                'deletions': commit.get('deletions', 0),
                                'url': commit_url,
                                'github_username': github_username
                            }
                        ))
                
                # GitHub PRs
                if not activity_type or activity_type == 'pull_request':
                    prs = db["github_pull_requests"]
                    query = {}
                    if member_name:
                        query['author'] = member_name
                    if date_filter:
                        query['created_at'] = date_filter
                    
                    async for pr in prs.find(query).sort("created_at", -1).limit(limit):
                        created_at = pr.get('created_at')
                        timestamp_str = created_at.isoformat() if isinstance(created_at, datetime) else str(created_at) if created_at else ''
                        
                        # Get member display name
                        github_username = pr.get('author', '')
                        display_name = await get_member_display_name(github_username, db)
                        
                        # PR URL
                        pr_url = pr.get('url')
                        
                        activities.append(ActivityResponse(
                            id=str(pr['_id']),
                            member_name=display_name,
                            source_type='github',
                            activity_type='pull_request',
                            timestamp=timestamp_str,
                            metadata={
                                'number': pr.get('number'),
                                'title': pr.get('title'),
                                'repository': pr.get('repository'),
                                'state': pr.get('state'),
                                'url': pr_url,
                                'github_username': github_username
                            }
                        ))
            
            elif source == 'slack':
                messages = db["slack_messages"]
                query = {}
                if member_name:
                    query['user_name'] = member_name
                if date_filter:
                    query['posted_at'] = date_filter
                
                async for msg in messages.find(query).sort("posted_at", -1).limit(limit):
                    posted_at = msg.get('posted_at')
                    timestamp_str = posted_at.isoformat() if isinstance(posted_at, datetime) else str(posted_at) if posted_at else ''
                    
                    activities.append(ActivityResponse(
                        id=str(msg['_id']),
                        member_name=msg.get('user_name', ''),
                        source_type='slack',
                        activity_type='message',
                        timestamp=timestamp_str,
                        metadata={
                            'channel': msg.get('channel_name'),
                            'text': msg.get('text', '')[:200],
                            'reactions': len(msg.get('reactions', [])),
                            'links': len(msg.get('links', []))
                        }
                    ))
            
            elif source == 'notion':
                pages = db["notion_pages"]
                query = {}
                if member_name:
                    query['created_by.name'] = member_name
                if date_filter:
                    query['created_time'] = date_filter
                
                async for page in pages.find(query).sort("created_time", -1).limit(limit):
                    created_time = page.get('created_time')
                    timestamp_str = created_time.isoformat() if isinstance(created_time, datetime) else str(created_time) if created_time else ''
                    
                    activities.append(ActivityResponse(
                        id=str(page['_id']),
                        member_name=page.get('created_by', {}).get('name', ''),
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
                    query['user_email'] = {"$regex": member_name, "$options": "i"}
                if date_filter:
                    query['timestamp'] = date_filter
                
                async for activity in drive_activities.find(query).sort("timestamp", -1).limit(limit):
                    timestamp_val = activity.get('timestamp')
                    timestamp_str = timestamp_val.isoformat() if isinstance(timestamp_val, datetime) else str(timestamp_val) if timestamp_val else ''
                    
                    activities.append(ActivityResponse(
                        id=str(activity['_id']),
                        member_name=activity.get('user_email', '').split('@')[0],
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
                    timestamp_str = modified_time.isoformat() if isinstance(modified_time, datetime) else str(modified_time) if modified_time else ''
                    
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
                return ''  # Empty strings sort first (oldest)
            return activity.timestamp
        
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

