"""
Projects API endpoints

Provides project-specific activity data and reports
"""

from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import text
import json

from src.utils.logger import get_logger

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
    Get list of all projects
    
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
    Get detailed information for a specific project
    
    Args:
        project_key: Project identifier (e.g., project-ooo)
    
    Returns:
        Project details with activity statistics
    """
    try:
        config = request.app.state.config
        projects_config = config.get('projects', {})
        
        if project_key not in projects_config:
            raise HTTPException(status_code=404, detail="Project not found")
        
        project_data = projects_config[project_key]
        
        # Get project activity statistics
        db_manager = request.app.state.db_manager
        slack_channel_id = project_data.get('slack_channel_id')
        repositories = project_data.get('repositories', [])
        
        stats = {
            'slack_activities': 0,
            'github_activities': 0,
            'google_drive_activities': 0,
            'active_members': []
        }
        
        if slack_channel_id:
            # Get Slack activities count
            with db_manager.get_connection('slack') as conn:
                try:
                    result = conn.execute(
                        text("""
                            SELECT COUNT(*) as count
                            FROM slack_messages
                            WHERE channel_id = :channel_id
                        """),
                        {'channel_id': slack_channel_id}
                    )
                    stats['slack_activities'] = result.fetchone()[0]
                except Exception as e:
                    logger.warning(f"Could not fetch Slack stats: {e}")
        
        if repositories:
            # Get GitHub activities count
            with db_manager.get_connection('github') as conn:
                try:
                    placeholders = ','.join([f':repo{i}' for i in range(len(repositories))])
                    params = {f'repo{i}': repo for i, repo in enumerate(repositories)}
                    
                    result = conn.execute(
                        text(f"""
                            SELECT COUNT(*) as count
                            FROM github_commits
                            WHERE repository_name IN ({placeholders})
                        """),
                        params
                    )
                    stats['github_activities'] = result.fetchone()[0]
                except Exception as e:
                    logger.warning(f"Could not fetch GitHub stats: {e}")
        
        # Get active members from member_activities
        with db_manager.get_connection() as conn:
            try:
                result = conn.execute(
                    text("""
                        SELECT DISTINCT m.name, m.email
                        FROM members m
                        JOIN member_activities ma ON m.id = ma.member_id
                        WHERE ma.source_type = 'slack'
                        LIMIT 100
                    """)
                )
                
                stats['active_members'] = [
                    {'name': row[0], 'email': row[1]}
                    for row in result
                ]
            except Exception as e:
                logger.warning(f"Could not fetch active members: {e}")
        
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
    Get active members for a specific project
    
    Args:
        project_key: Project identifier
    
    Returns:
        List of active members in the project
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
        db_manager = request.app.state.db_manager
        
        with db_manager.get_connection('slack') as slack_conn:
            result = slack_conn.execute(
                text("""
                    SELECT DISTINCT user_id
                    FROM slack_messages
                    WHERE channel_id = :channel_id
                """),
                {'channel_id': slack_channel_id}
            )
            
            slack_user_ids = [row[0] for row in result]
        
        # Map Slack user IDs to members
        members = []
        
        with db_manager.get_connection() as conn:
            for user_id in slack_user_ids:
                result = conn.execute(
                    text("""
                        SELECT m.id, m.name, m.email
                        FROM members m
                        JOIN member_identifiers mi ON m.id = mi.member_id
                        WHERE mi.source_type = 'slack'
                        AND mi.source_user_id = :user_id
                    """),
                    {'user_id': user_id}
                )
                
                row = result.fetchone()
                if row:
                    members.append({
                        'id': row[0],
                        'name': row[1],
                        'email': row[2]
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

