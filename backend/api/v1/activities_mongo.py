"""
Activities API endpoints (MongoDB Version)

Provides activity data across all sources from MongoDB
"""

from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from src.utils.logger import get_logger
from src.core.mongo_manager import mongo_manager

logger = get_logger(__name__)

router = APIRouter()


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
        db = mongo_manager.get_database_sync()
        activities = []
        
        # Determine which sources to query
        sources_to_query = [source_type] if source_type else ['github', 'slack', 'notion', 'drive']
        
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
                    commits = db[mongo_manager._collections_config.get("github_commits", "github_commits")]
                    query = {}
                    if member_name:
                        query['author_login'] = member_name
                    if date_filter:
                        query['committed_at'] = date_filter
                    
                    for commit in commits.find(query).sort("committed_at", -1).limit(limit):
                        activities.append(ActivityResponse(
                            id=str(commit['_id']),
                            member_name=commit.get('author_login', ''),
                            source_type='github',
                            activity_type='commit',
                            timestamp=commit['committed_at'].isoformat() if isinstance(commit['committed_at'], datetime) else commit['committed_at'],
                            metadata={
                                'sha': commit.get('sha'),
                                'message': commit.get('message'),
                                'repository': commit.get('repository_name'),
                                'additions': commit.get('additions', 0),
                                'deletions': commit.get('deletions', 0)
                            }
                        ))
                
                # GitHub PRs
                if not activity_type or activity_type == 'pull_request':
                    prs = db[mongo_manager._collections_config.get("github_pull_requests", "github_pull_requests")]
                    query = {}
                    if member_name:
                        query['author'] = member_name
                    if date_filter:
                        query['created_at'] = date_filter
                    
                    for pr in prs.find(query).sort("created_at", -1).limit(limit):
                        activities.append(ActivityResponse(
                            id=str(pr['_id']),
                            member_name=pr.get('author', ''),
                            source_type='github',
                            activity_type='pull_request',
                            timestamp=pr['created_at'].isoformat() if isinstance(pr['created_at'], datetime) else pr['created_at'],
                            metadata={
                                'number': pr.get('number'),
                                'title': pr.get('title'),
                                'repository': pr.get('repository'),
                                'state': pr.get('state')
                            }
                        ))
            
            elif source == 'slack':
                messages = db[mongo_manager._collections_config.get("slack_messages", "slack_messages")]
                query = {}
                if member_name:
                    query['user_name'] = member_name
                if date_filter:
                    query['posted_at'] = date_filter
                
                for msg in messages.find(query).sort("posted_at", -1).limit(limit):
                    activities.append(ActivityResponse(
                        id=str(msg['_id']),
                        member_name=msg.get('user_name', ''),
                        source_type='slack',
                        activity_type='message',
                        timestamp=msg['posted_at'].isoformat() if isinstance(msg['posted_at'], datetime) else msg['posted_at'],
                        metadata={
                            'channel': msg.get('channel_name'),
                            'text': msg.get('text', '')[:200],
                            'reactions': len(msg.get('reactions', [])),
                            'links': len(msg.get('links', []))
                        }
                    ))
            
            elif source == 'notion':
                pages = db[mongo_manager._collections_config.get("notion_pages", "notion_pages")]
                query = {}
                if member_name:
                    query['created_by.name'] = member_name
                if date_filter:
                    query['created_time'] = date_filter
                
                for page in pages.find(query).sort("created_time", -1).limit(limit):
                    activities.append(ActivityResponse(
                        id=str(page['_id']),
                        member_name=page.get('created_by', {}).get('name', ''),
                        source_type='notion',
                        activity_type='page_created',
                        timestamp=page['created_time'].isoformat() if isinstance(page['created_time'], datetime) else page['created_time'],
                        metadata={
                            'title': page.get('title'),
                            'comments': page.get('comments_count', 0)
                        }
                    ))
            
            elif source == 'drive':
                drive_activities = db[mongo_manager._collections_config.get("drive_activities", "drive_activities")]
                query = {}
                if member_name:
                    query['user_email'] = {"$regex": member_name, "$options": "i"}
                if date_filter:
                    query['timestamp'] = date_filter
                
                for activity in drive_activities.find(query).sort("timestamp", -1).limit(limit):
                    activities.append(ActivityResponse(
                        id=str(activity['_id']),
                        member_name=activity.get('user_email', '').split('@')[0],
                        source_type='google_drive',
                        activity_type=activity.get('event_name', 'activity'),
                        timestamp=activity['timestamp'].isoformat() if isinstance(activity['timestamp'], datetime) else activity['timestamp'],
                        metadata={
                            'action': activity.get('action'),
                            'doc_title': activity.get('doc_title'),
                            'doc_type': activity.get('doc_type')
                        }
                    ))
        
        # Sort all activities by timestamp descending
        activities.sort(key=lambda x: x.timestamp, reverse=True)
        
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
        db = mongo_manager.get_database_sync()
        summary = {}
        
        # Build date filter
        date_filter = {}
        if start_date:
            date_filter['$gte'] = datetime.fromisoformat(start_date)
        if end_date:
            date_filter['$lte'] = datetime.fromisoformat(end_date)
        
        sources_to_query = [source_type] if source_type else ['github', 'slack', 'notion', 'drive']
        
        for source in sources_to_query:
            source_summary = {
                'total_activities': 0,
                'activity_types': {}
            }
            
            if source == 'github':
                # Commits
                commits = db[mongo_manager._collections_config.get("github_commits", "github_commits")]
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
                prs = db[mongo_manager._collections_config.get("github_pull_requests", "github_pull_requests")]
                pr_count = prs.count_documents(query if date_filter else {})
                if pr_count > 0:
                    source_summary['total_activities'] += pr_count
                    source_summary['activity_types']['pull_request'] = {
                        'count': pr_count
                    }
            
            elif source == 'slack':
                messages = db[mongo_manager._collections_config.get("slack_messages", "slack_messages")]
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
                pages = db[mongo_manager._collections_config.get("notion_pages", "notion_pages")]
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
                drive_activities = db[mongo_manager._collections_config.get("drive_activities", "drive_activities")]
                query = {}
                if date_filter:
                    query['timestamp'] = date_filter
                
                drive_count = drive_activities.count_documents(query)
                if drive_count > 0:
                    source_summary['total_activities'] = drive_count
            
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
            'google_drive': ['create', 'edit', 'upload', 'download', 'share']
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

