"""
Projects API endpoints (MongoDB Version)

Provides project-specific activity data and reports from MongoDB
"""

from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Optional
from pydantic import BaseModel

from src.utils.logger import get_logger
from src.core.mongo_manager import get_mongo_manager

# Get MongoDB manager instance
def get_mongo():
    from backend.main import mongo_manager
    return mongo_manager

logger = get_logger(__name__)

router = APIRouter()


# Response models
class ProjectResponse(BaseModel):
    key: str
    name: str
    slack_channel: str
    slack_channel_id: str
    lead: str
    repositories: List[str]
    drive_folders: Optional[List[str]] = []
    description: str


class ProjectListResponse(BaseModel):
    total: int
    projects: List[ProjectResponse]


@router.get("/projects", response_model=ProjectListResponse)
async def get_projects(request: Request):
    """
    Get list of all projects from configuration
    
    Returns:
        List of projects with configuration
    """
    try:
        config = request.app.state.config
        projects_config = config.get('projects', {})
        
        projects = []
        for key, project_data in projects_config.items():
            projects.append(ProjectResponse(
                key=key,
                name=project_data.get('name', key),
                slack_channel=project_data.get('slack_channel', ''),
                slack_channel_id=project_data.get('slack_channel_id', ''),
                lead=project_data.get('lead', ''),
                repositories=project_data.get('repositories', []),
                drive_folders=project_data.get('drive_folders', []),
                description=project_data.get('description', '')
            ))
        
        return ProjectListResponse(
            total=len(projects),
            projects=projects
        )
        
    except Exception as e:
        logger.error(f"Error fetching projects: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch projects")


@router.get("/projects/{project_key}")
async def get_project_detail(
    request: Request,
    project_key: str
):
    """
    Get detailed information for a specific project from MongoDB
    
    Args:
        project_key: Project identifier (e.g., project-ooo)
    
    Returns:
        Project details with activity statistics from MongoDB
    """
    try:
        config = request.app.state.config
        projects_config = config.get('projects', {})
        
        if project_key not in projects_config:
            raise HTTPException(status_code=404, detail="Project not found")
        
        project_data = projects_config[project_key]
        
        # Get MongoDB connection
        db = mongo_manager.get_database_sync()
        
        slack_channel_id = project_data.get('slack_channel_id')
        repositories = project_data.get('repositories', [])
        
        stats = {
            'slack_activities': 0,
            'github_activities': 0,
            'google_drive_activities': 0,
            'active_members': []
        }
        
        # Get Slack activities
        if slack_channel_id:
            try:
                slack_messages = db[mongo_manager._collections_config.get("slack_messages", "slack_messages")]
                stats['slack_activities'] = slack_messages.count_documents({
                    "channel_id": slack_channel_id
                })
                
                # Get active members from Slack messages
                pipeline = [
                    {"$match": {"channel_id": slack_channel_id}},
                    {"$group": {"_id": "$user_name"}},
                    {"$limit": 100}
                ]
                active_users = list(slack_messages.aggregate(pipeline))
                stats['active_members'] = [{"name": user['_id']} for user in active_users if user['_id']]
                
            except Exception as e:
                logger.warning(f"Could not fetch Slack stats: {e}")
        
        # Get GitHub activities
        if repositories:
            try:
                github_commits = db[mongo_manager._collections_config.get("github_commits", "github_commits")]
                
                # Count commits from project repositories
                stats['github_activities'] = github_commits.count_documents({
                    "repository_name": {"$in": repositories}
                })
                
            except Exception as e:
                logger.warning(f"Could not fetch GitHub stats: {e}")
        
        # Get Google Drive activities
        try:
            drive_activities = db[mongo_manager._collections_config.get("drive_activities", "drive_activities")]
            stats['google_drive_activities'] = drive_activities.count_documents({})
        except Exception as e:
            logger.warning(f"Could not fetch Drive stats: {e}")
        
        return {
            'project': ProjectResponse(
                key=project_key,
                name=project_data.get('name', project_key),
                slack_channel=project_data.get('slack_channel', ''),
                slack_channel_id=project_data.get('slack_channel_id', ''),
                lead=project_data.get('lead', ''),
                repositories=repositories,
                drive_folders=project_data.get('drive_folders', []),
                description=project_data.get('description', '')
            ),
            'statistics': stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching project detail: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch project detail")


@router.get("/projects/{project_key}/members")
async def get_project_members(
    request: Request,
    project_key: str
):
    """
    Get active members for a specific project from MongoDB
    
    Args:
        project_key: Project identifier
    
    Returns:
        List of active members in the project based on Slack channel activity
    """
    try:
        config = request.app.state.config
        projects_config = config.get('projects', {})
        
        if project_key not in projects_config:
            raise HTTPException(status_code=404, detail="Project not found")
        
        project_data = projects_config[project_key]
        slack_channel_id = project_data.get('slack_channel_id')
        
        if not slack_channel_id:
            return {
                'project_key': project_key,
                'members': []
            }
        
        # Get active members from Slack channel
        db = mongo_manager.get_database_sync()
        slack_messages = db[mongo_manager._collections_config.get("slack_messages", "slack_messages")]
        
        # Use aggregation to get unique users
        pipeline = [
            {"$match": {"channel_id": slack_channel_id}},
            {"$group": {
                "_id": "$user_name",
                "message_count": {"$sum": 1}
            }},
            {"$sort": {"message_count": -1}}
        ]
        
        results = list(slack_messages.aggregate(pipeline))
        
        members = []
        for result in results:
            if result['_id']:  # Skip empty usernames
                members.append({
                    'name': result['_id'],
                    'message_count': result['message_count']
                })
        
        return {
            'project_key': project_key,
            'total': len(members),
            'members': members
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching project members: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch project members")


@router.get("/projects/{project_key}/activity")
async def get_project_activity(
    request: Request,
    project_key: str,
    source_type: Optional[str] = Query(None, description="Filter by source (github, slack)"),
    limit: int = Query(100, ge=1, le=1000)
):
    """
    Get recent activity for a specific project
    
    Args:
        project_key: Project identifier
        source_type: Filter by source
        limit: Maximum number of activities
    
    Returns:
        Recent project activities from MongoDB
    """
    try:
        config = request.app.state.config
        projects_config = config.get('projects', {})
        
        if project_key not in projects_config:
            raise HTTPException(status_code=404, detail="Project not found")
        
        project_data = projects_config[project_key]
        slack_channel_id = project_data.get('slack_channel_id')
        repositories = project_data.get('repositories', [])
        
        db = mongo_manager.get_database_sync()
        activities = []
        
        sources_to_query = [source_type] if source_type else ['github', 'slack']
        
        if 'github' in sources_to_query and repositories:
            # Get GitHub commits
            github_commits = db[mongo_manager._collections_config.get("github_commits", "github_commits")]
            
            for commit in github_commits.find({
                "repository_name": {"$in": repositories}
            }).sort("committed_at", -1).limit(limit):
                from datetime import datetime
                activities.append({
                    'source': 'github',
                    'type': 'commit',
                    'timestamp': commit['committed_at'].isoformat() if isinstance(commit['committed_at'], datetime) else commit['committed_at'],
                    'author': commit.get('author_login'),
                    'details': {
                        'message': commit.get('message'),
                        'repository': commit.get('repository_name')
                    }
                })
        
        if 'slack' in sources_to_query and slack_channel_id:
            # Get Slack messages
            slack_messages = db[mongo_manager._collections_config.get("slack_messages", "slack_messages")]
            
            for msg in slack_messages.find({
                "channel_id": slack_channel_id,
                "channel_name": {"$ne": "tokamak-partners"}  # Exclude private channel
            }).sort("posted_at", -1).limit(limit):
                from datetime import datetime
                activities.append({
                    'source': 'slack',
                    'type': 'message',
                    'timestamp': msg['posted_at'].isoformat() if isinstance(msg['posted_at'], datetime) else msg['posted_at'],
                    'author': msg.get('user_name'),
                    'details': {
                        'text': msg.get('text', '')[:100],
                        'channel': msg.get('channel_name')
                    }
                })
        
        # Sort by timestamp descending
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        activities = activities[:limit]
        
        return {
            'project_key': project_key,
            'total': len(activities),
            'activities': activities
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching project activity: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch project activity")

