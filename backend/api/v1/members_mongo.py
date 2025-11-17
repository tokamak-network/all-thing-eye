"""
Members API endpoints (MongoDB Version)

Provides member information and statistics from MongoDB
"""

from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from src.utils.logger import get_logger
from src.core.mongo_manager import get_mongo_manager

logger = get_logger(__name__)

router = APIRouter()

# Get MongoDB manager instance
def get_mongo():
    from backend.main_mongo import mongo_manager
    return mongo_manager


# Response models
class MemberResponse(BaseModel):
    id: str  # ObjectId as string
    name: str
    email: Optional[str] = None
    created_at: str
    
    class Config:
        from_attributes = True


class MemberDetailResponse(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    identifiers: List[dict] = []
    activity_summary: dict = {}
    created_at: str


class MemberListResponse(BaseModel):
    total: int
    members: List[MemberResponse]


@router.get("/members", response_model=MemberListResponse)
async def get_members(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Get list of all members from MongoDB
    
    Args:
        limit: Maximum number of members to return
        offset: Number of members to skip
    
    Returns:
        List of members with pagination
    """
    try:
        db = get_mongo().db
        members_collection = db["members"]
        
        # Get total count
        total = members_collection.count_documents({})
        
        # Get members with pagination
        cursor = members_collection.find({}).sort("name", 1).skip(offset).limit(limit)
        
        members = []
        for doc in cursor:
            members.append(MemberResponse(
                id=str(doc['_id']),
                name=doc.get('name', ''),
                email=doc.get('email'),
                created_at=doc.get('created_at', '').isoformat() if isinstance(doc.get('created_at'), datetime) else doc.get('created_at', '')
            ))
        
        return MemberListResponse(
            total=total,
            members=members
        )
        
    except Exception as e:
        logger.error(f"Error fetching members: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch members")


@router.get("/members/{member_name}", response_model=MemberDetailResponse)
async def get_member_detail(
    request: Request,
    member_name: str
):
    """
    Get detailed information for a specific member
    
    Args:
        member_name: Member name
    
    Returns:
        Detailed member information including identifiers and activity summary
    """
    try:
        db = get_mongo().db
        members_collection = db["members"]
        
        # Find member by name
        member_doc = members_collection.find_one({"name": member_name})
        
        if not member_doc:
            raise HTTPException(status_code=404, detail="Member not found")
        
        member_data = {
            'id': str(member_doc['_id']),
            'name': member_doc.get('name', ''),
            'email': member_doc.get('email'),
            'created_at': member_doc.get('created_at', '').isoformat() if isinstance(member_doc.get('created_at'), datetime) else member_doc.get('created_at', '')
        }
        
        # Get member identifiers (embedded in member document)
        identifiers = member_doc.get('identifiers', [])
        
        # Get activity summary from various collections
        activity_summary = {}
        
        # GitHub activities
        github_commits = db["github_commits"]
        github_prs = db["github_pull_requests"]
        
        github_commit_count = github_commits.count_documents({"author_login": member_name})
        github_pr_count = github_prs.count_documents({"author": member_name})
        
        if github_commit_count > 0 or github_pr_count > 0:
            activity_summary['github'] = {
                'commits': github_commit_count,
                'pull_requests': github_pr_count
            }
        
        # Slack activities
        slack_messages = db["slack_messages"]
        slack_message_count = slack_messages.count_documents({"user_name": member_name})
        
        if slack_message_count > 0:
            activity_summary['slack'] = {
                'messages': slack_message_count
            }
        
        # Notion activities
        notion_pages = db["notion_pages"]
        notion_page_count = notion_pages.count_documents({"created_by.name": member_name})
        
        if notion_page_count > 0:
            activity_summary['notion'] = {
                'pages_created': notion_page_count
            }
        
        return MemberDetailResponse(
            **member_data,
            identifiers=identifiers,
            activity_summary=activity_summary
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching member detail: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch member detail")


@router.get("/members/{member_name}/activities")
async def get_member_activities(
    request: Request,
    member_name: str,
    source_type: Optional[str] = Query(None, description="Filter by source (github, slack, notion, google_drive)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Get activities for a specific member across all sources
    
    Args:
        member_name: Member name
        source_type: Filter by source
        limit: Maximum number of activities to return
        offset: Number of activities to skip
    
    Returns:
        List of member activities from various collections
    """
    try:
        db = get_mongo().db
        activities = []
        
        # Collect from different sources based on filter
        sources_to_query = [source_type] if source_type else ['github', 'slack', 'notion', 'drive']
        
        for source in sources_to_query:
            if source == 'github':
                # GitHub commits
                commits = db["github_commits"]
                for commit in commits.find({"author_login": member_name}).sort("committed_at", -1).limit(limit):
                    activities.append({
                        'source_type': 'github',
                        'activity_type': 'commit',
                        'timestamp': commit['committed_at'].isoformat() if isinstance(commit['committed_at'], datetime) else commit['committed_at'],
                        'metadata': {
                            'sha': commit.get('sha'),
                            'message': commit.get('message'),
                            'repository': commit.get('repository_name')
                        }
                    })
                
                # GitHub PRs
                prs = db["github_pull_requests"]
                for pr in prs.find({"author": member_name}).sort("created_at", -1).limit(limit):
                    activities.append({
                        'source_type': 'github',
                        'activity_type': 'pull_request',
                        'timestamp': pr['created_at'].isoformat() if isinstance(pr['created_at'], datetime) else pr['created_at'],
                        'metadata': {
                            'number': pr.get('number'),
                            'title': pr.get('title'),
                            'repository': pr.get('repository')
                        }
                    })
            
            elif source == 'slack':
                messages = db["slack_messages"]
                for msg in messages.find({"user_name": member_name}).sort("posted_at", -1).limit(limit):
                    activities.append({
                        'source_type': 'slack',
                        'activity_type': 'message',
                        'timestamp': msg['posted_at'].isoformat() if isinstance(msg['posted_at'], datetime) else msg['posted_at'],
                        'metadata': {
                            'channel': msg.get('channel_name'),
                            'text': msg.get('text', '')[:100]
                        }
                    })
            
            elif source == 'notion':
                pages = db["notion_pages"]
                for page in pages.find({"created_by.name": member_name}).sort("created_time", -1).limit(limit):
                    activities.append({
                        'source_type': 'notion',
                        'activity_type': 'page_created',
                        'timestamp': page['created_time'].isoformat() if isinstance(page['created_time'], datetime) else page['created_time'],
                        'metadata': {
                            'title': page.get('title')
                        }
                    })
        
        # Sort by timestamp descending
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Apply offset and limit
        activities = activities[offset:offset+limit]
        
        return {
            'member_name': member_name,
            'total': len(activities),
            'activities': activities
        }
        
    except Exception as e:
        logger.error(f"Error fetching member activities: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch member activities")

