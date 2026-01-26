"""
Projects Management API endpoints

Provides CRUD operations for project configurations stored in MongoDB.
This replaces the static config.yaml approach with dynamic project management.
"""

from fastapi import APIRouter, HTTPException, Request
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from bson import ObjectId
import re
import pickle
from pathlib import Path

from src.utils.logger import get_logger
from src.core.mongo_manager import get_mongo_manager

logger = get_logger(__name__)

router = APIRouter()


# Request/Response models
class ProjectCreateRequest(BaseModel):
    """Request model for creating a new project"""
    key: str = Field(..., description="Project key (e.g., 'project-ooo')")
    name: str = Field(..., description="Project display name")
    description: Optional[str] = None
    slack_channel: Optional[str] = None
    slack_channel_id: Optional[str] = None
    lead: Optional[str] = None
    github_team_slug: Optional[str] = None
    drive_folders: List[str] = Field(default_factory=list)
    notion_page_ids: List[str] = Field(default_factory=list)
    notion_parent_page_id: Optional[str] = None
    sub_projects: List[str] = Field(default_factory=list)
    member_ids: List[str] = Field(default_factory=list, description="List of member IDs")
    is_active: bool = True


class ProjectUpdateRequest(BaseModel):
    """Request model for updating a project"""
    name: Optional[str] = None
    description: Optional[str] = None
    slack_channel: Optional[str] = None
    slack_channel_id: Optional[str] = None
    lead: Optional[str] = None
    github_team_slug: Optional[str] = None
    repositories: Optional[List[str]] = None
    drive_folders: Optional[List[str]] = None
    notion_page_ids: Optional[List[str]] = None
    notion_parent_page_id: Optional[str] = None
    sub_projects: Optional[List[str]] = None
    member_ids: Optional[List[str]] = None
    is_active: Optional[bool] = None
    grant_reports_folder_id: Optional[str] = None  # Google Drive folder ID for auto-sync grant reports


class ProjectResponse(BaseModel):
    """Response model for project data"""
    id: str
    key: str
    name: str
    description: Optional[str] = None
    slack_channel: Optional[str] = None
    slack_channel_id: Optional[str] = None
    lead: Optional[str] = None
    repositories: List[str] = Field(default_factory=list)
    repositories_synced_at: Optional[datetime] = None
    github_team_slug: Optional[str] = None
    drive_folders: List[str] = Field(default_factory=list)
    notion_page_ids: List[str] = Field(default_factory=list)
    notion_parent_page_id: Optional[str] = None
    sub_projects: List[str] = Field(default_factory=list)
    member_ids: List[str] = Field(default_factory=list)
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    """Response model for project list"""
    total: int
    projects: List[ProjectResponse]


class GrantReportRequest(BaseModel):
    """Request model for adding/updating a grant report"""
    title: str = Field(..., description="Report title (e.g., 'TRH 2024 Q4 Report')")
    year: int = Field(..., description="Report year (e.g., 2024)")
    quarter: int = Field(..., ge=1, le=4, description="Report quarter (1-4)")
    drive_url: str = Field(..., description="Google Drive URL to the report file")
    file_name: Optional[str] = None


class GrantReportResponse(BaseModel):
    """Response model for grant report"""
    id: str
    title: str
    year: int
    quarter: int
    drive_url: str
    file_name: Optional[str] = None
    created_at: Optional[datetime] = None


class GrantReportsResponse(BaseModel):
    """Response model for list of grant reports"""
    project_key: str
    reports: List[GrantReportResponse]


class DriveFileResponse(BaseModel):
    """Response model for a Drive file"""
    id: str
    name: str
    link: str
    mimeType: Optional[str] = None
    modifiedTime: Optional[str] = None
    year: Optional[int] = None
    quarter: Optional[int] = None


class DriveFolderFilesResponse(BaseModel):
    """Response model for Drive folder files"""
    folder_id: str
    files: List[DriveFileResponse]


def get_mongo():
    """Get MongoDB manager from main.py"""
    from backend.main import mongo_manager
    return mongo_manager


def convert_member_ids_to_strings(member_ids: list) -> List[str]:
    """Convert ObjectIds in member_ids to strings"""
    if not member_ids:
        return []
    return [str(mid) if isinstance(mid, ObjectId) else str(mid) for mid in member_ids]


@router.get("/projects", response_model=ProjectListResponse)
async def get_projects(request: Request, active_only: bool = False):
    """
    Get list of all projects from MongoDB
    
    Args:
        active_only: If True, only return active projects
    
    Returns:
        List of projects with configuration
    """
    try:
        mongo = get_mongo()
        db = mongo.db
        projects_collection = db["projects"]
        
        query = {"is_active": True} if active_only else {}
        cursor = projects_collection.find(query).sort("name", 1)
        
        projects = []
        for doc in cursor:
            # Safely handle datetime fields - MongoDB returns datetime objects or None
            created_at = doc.get("created_at")
            if not isinstance(created_at, datetime):
                created_at = datetime.utcnow()
            
            updated_at = doc.get("updated_at")
            if not isinstance(updated_at, datetime):
                updated_at = datetime.utcnow()
            
            repositories_synced_at = doc.get("repositories_synced_at")
            if repositories_synced_at is not None and not isinstance(repositories_synced_at, datetime):
                repositories_synced_at = None
            
            projects.append(ProjectResponse(
                id=str(doc["_id"]),
                key=doc["key"],
                name=doc["name"],
                description=doc.get("description"),
                slack_channel=doc.get("slack_channel"),
                slack_channel_id=doc.get("slack_channel_id"),
                lead=doc.get("lead"),
                repositories=doc.get("repositories", []),
                repositories_synced_at=repositories_synced_at,
                github_team_slug=doc.get("github_team_slug"),
                drive_folders=doc.get("drive_folders", []),
                notion_page_ids=doc.get("notion_page_ids", []),
                notion_parent_page_id=doc.get("notion_parent_page_id"),
                sub_projects=doc.get("sub_projects", []),
                member_ids=convert_member_ids_to_strings(doc.get("member_ids", [])),
                is_active=doc.get("is_active", True),
                created_at=created_at,
                updated_at=updated_at
            ))
        
        return ProjectListResponse(
            total=len(projects),
            projects=projects
        )
        
    except Exception as e:
        logger.error(f"Error fetching projects: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch projects: {str(e)}")


@router.get("/projects/{project_key}", response_model=ProjectResponse)
async def get_project(request: Request, project_key: str):
    """
    Get a specific project by key
    
    Args:
        project_key: Project identifier (e.g., 'project-ooo')
    
    Returns:
        Project configuration
    """
    try:
        mongo = get_mongo()
        db = mongo.db
        projects_collection = db["projects"]
        
        doc = projects_collection.find_one({"key": project_key})
        
        if not doc:
            raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")
        
        # Safely handle datetime fields
        created_at = doc.get("created_at")
        if not isinstance(created_at, datetime):
            created_at = datetime.utcnow()
        
        updated_at = doc.get("updated_at")
        if not isinstance(updated_at, datetime):
            updated_at = datetime.utcnow()
        
        repositories_synced_at = doc.get("repositories_synced_at")
        if repositories_synced_at is not None and not isinstance(repositories_synced_at, datetime):
            repositories_synced_at = None
        
        return ProjectResponse(
            id=str(doc["_id"]),
            key=doc["key"],
            name=doc["name"],
            description=doc.get("description"),
            slack_channel=doc.get("slack_channel"),
            slack_channel_id=doc.get("slack_channel_id"),
            lead=doc.get("lead"),
            repositories=doc.get("repositories", []),
            repositories_synced_at=repositories_synced_at,
            github_team_slug=doc.get("github_team_slug"),
            drive_folders=doc.get("drive_folders", []),
            notion_page_ids=doc.get("notion_page_ids", []),
            notion_parent_page_id=doc.get("notion_parent_page_id"),
            sub_projects=doc.get("sub_projects", []),
                member_ids=convert_member_ids_to_strings(doc.get("member_ids", [])),
                is_active=doc.get("is_active", True),
                created_at=created_at,
                updated_at=updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching project: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch project: {str(e)}")


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(request: Request, body: ProjectCreateRequest):
    """
    Create a new project
    
    Args:
        body: Project creation data
    
    Returns:
        Created project configuration
    """
    try:
        mongo = get_mongo()
        db = mongo.db
        projects_collection = db["projects"]
        
        # Check if project key already exists
        existing = projects_collection.find_one({"key": body.key})
        if existing:
            raise HTTPException(status_code=409, detail=f"Project with key '{body.key}' already exists")
        
        # Prepare document
        now = datetime.utcnow()
        project_doc = {
            "key": body.key,
            "name": body.name,
            "description": body.description,
            "slack_channel": body.slack_channel,
            "slack_channel_id": body.slack_channel_id,
            "lead": body.lead,
            "repositories": [],  # Will be synced from GitHub Teams
            "repositories_synced_at": None,
            "github_team_slug": body.github_team_slug or body.key,
            "drive_folders": body.drive_folders,
            "notion_page_ids": body.notion_page_ids,
            "notion_parent_page_id": body.notion_parent_page_id,
            "sub_projects": body.sub_projects,
            "member_ids": body.member_ids,
            "is_active": body.is_active,
            "created_at": now,
            "updated_at": now
        }
        
        # Insert document
        result = projects_collection.insert_one(project_doc)
        project_doc["_id"] = result.inserted_id
        
        logger.info(f"Created project: {body.key}")
        
        return ProjectResponse(
            id=str(project_doc["_id"]),
            key=project_doc["key"],
            name=project_doc["name"],
            description=project_doc.get("description"),
            slack_channel=project_doc.get("slack_channel"),
            slack_channel_id=project_doc.get("slack_channel_id"),
            lead=project_doc.get("lead"),
            repositories=project_doc.get("repositories", []),
            repositories_synced_at=project_doc.get("repositories_synced_at"),
            github_team_slug=project_doc.get("github_team_slug"),
            drive_folders=project_doc.get("drive_folders", []),
            notion_page_ids=project_doc.get("notion_page_ids", []),
            notion_parent_page_id=project_doc.get("notion_parent_page_id"),
            sub_projects=project_doc.get("sub_projects", []),
                member_ids=convert_member_ids_to_strings(project_doc.get("member_ids", [])),
                is_active=project_doc.get("is_active", True),
                created_at=project_doc.get("created_at"),
                updated_at=project_doc.get("updated_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating project: {e}")
        raise HTTPException(status_code=500, detail="Failed to create project")


@router.put("/projects/{project_key}", response_model=ProjectResponse)
async def update_project(request: Request, project_key: str, body: ProjectUpdateRequest):
    """
    Update an existing project
    
    Args:
        project_key: Project identifier
        body: Project update data (only provided fields will be updated)
    
    Returns:
        Updated project configuration
    """
    try:
        mongo = get_mongo()
        db = mongo.db
        projects_collection = db["projects"]
        members_collection = db["members"]
        
        # Check if project exists
        existing = projects_collection.find_one({"key": project_key})
        if not existing:
            raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")
        
        # Prepare update document (only include provided fields)
        update_doc = {"updated_at": datetime.utcnow()}
        
        if body.name is not None:
            update_doc["name"] = body.name
        if body.description is not None:
            update_doc["description"] = body.description
        if body.slack_channel is not None:
            update_doc["slack_channel"] = body.slack_channel
        if body.slack_channel_id is not None:
            update_doc["slack_channel_id"] = body.slack_channel_id
        if body.lead is not None:
            update_doc["lead"] = body.lead
        if body.github_team_slug is not None:
            update_doc["github_team_slug"] = body.github_team_slug
        # repositories are automatically synced from GitHub Teams by data collector
        # Do not allow manual updates via API
        # if body.repositories is not None:
        #     update_doc["repositories"] = body.repositories
        if body.drive_folders is not None:
            update_doc["drive_folders"] = body.drive_folders
        if body.notion_page_ids is not None:
            update_doc["notion_page_ids"] = body.notion_page_ids
        if body.notion_parent_page_id is not None:
            update_doc["notion_parent_page_id"] = body.notion_parent_page_id
        if body.sub_projects is not None:
            update_doc["sub_projects"] = body.sub_projects
        if body.member_ids is not None:
            update_doc["member_ids"] = [ObjectId(mid) if not isinstance(mid, ObjectId) else mid for mid in body.member_ids]
        if body.is_active is not None:
            update_doc["is_active"] = body.is_active
        if body.grant_reports_folder_id is not None:
            # Extract folder ID from URL if needed
            folder_id = body.grant_reports_folder_id.strip()
            if '/' in folder_id:
                match = re.search(r'/folders/([a-zA-Z0-9_-]+)', folder_id)
                if match:
                    folder_id = match.group(1)
            update_doc["grant_reports_folder_id"] = folder_id if folder_id else None
        
        # Sync member's projects field when member_ids changes
        if body.member_ids is not None:
            old_member_ids = set(str(mid) for mid in existing.get("member_ids", []))
            new_member_ids = set(body.member_ids)
            
            logger.info(f"[Project-Member Sync] Project: {project_key}")
            logger.info(f"[Project-Member Sync] Old member_ids: {old_member_ids}")
            logger.info(f"[Project-Member Sync] New member_ids: {new_member_ids}")
            
            # Members removed from project - remove project key from their projects array
            removed_members = old_member_ids - new_member_ids
            logger.info(f"[Project-Member Sync] Members to remove: {removed_members}")
            
            for member_id in removed_members:
                try:
                    member_obj_id = ObjectId(member_id)
                    
                    # Get member before update to see current projects
                    member = members_collection.find_one({"_id": member_obj_id})
                    if not member:
                        logger.warning(f"[Project-Member Sync] Member {member_id} not found in database")
                        continue
                    
                    member_name = member.get('name', 'Unknown')
                    current_projects = member.get('projects', [])
                    logger.info(f"[Project-Member Sync] Member {member_id} ({member_name}) current projects: {current_projects}")
                    
                    # Normalize function to handle both "ooo" and "project-ooo" formats
                    def normalize_key(key: str) -> str:
                        key_lower = key.lower()
                        if key_lower.startswith("project-"):
                            return key_lower[8:]  # Remove "project-" prefix
                        return key_lower
                    
                    # Remove project_key from member's projects array
                    # Filter out any project keys that match (normalized comparison)
                    project_key_normalized = normalize_key(project_key)
                    updated_projects = [
                        p for p in current_projects 
                        if normalize_key(p) != project_key_normalized
                    ]
                    
                    if len(updated_projects) != len(current_projects):
                        # Projects were actually removed
                        result = members_collection.update_one(
                            {"_id": member_obj_id},
                            {
                                "$set": {
                                    "projects": updated_projects,
                                    "updated_at": datetime.utcnow()
                                }
                            }
                        )
                        logger.info(f"[Project-Member Sync] Removed {project_key} from member {member_id} ({member_name}): {current_projects} -> {updated_projects}, modified={result.modified_count}")
                    else:
                        logger.info(f"[Project-Member Sync] Project {project_key} not found in member {member_id} ({member_name}) projects: {current_projects}")
                    
                    # Also update team field if it matches this project
                    # Handle both formats: "ooo" and "project-ooo"
                    current_team = member.get("team", "")
                    if current_team:
                        # Normalize both for comparison (strip "project-" prefix)
                        def normalize_key(key: str) -> str:
                            key_lower = key.lower()
                            if key_lower.startswith("project-"):
                                return key_lower[8:]  # Remove "project-" prefix
                            return key_lower
                        
                        current_team_normalized = normalize_key(current_team)
                        project_key_normalized = normalize_key(project_key)
                        
                        if current_team_normalized == project_key_normalized:
                            # Set team to first remaining project or None
                            new_team = updated_projects[0] if updated_projects else None
                            members_collection.update_one(
                                {"_id": member_obj_id},
                                {"$set": {"team": new_team}}
                            )
                            logger.info(f"[Project-Member Sync] Updated team for member {member_id} ({member_name}): {current_team} -> {new_team}")
                    
                except Exception as e:
                    logger.error(f"[Project-Member Sync] Failed to remove {project_key} from member {member_id}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            # Members added to project - add project key to their projects array
            added_members = new_member_ids - old_member_ids
            logger.info(f"[Project-Member Sync] Members to add: {added_members}")
            
            for member_id in added_members:
                try:
                    member_obj_id = ObjectId(member_id)
                    
                    # Get member first to check if project is already in list
                    member = members_collection.find_one({"_id": member_obj_id})
                    if not member:
                        logger.warning(f"[Project-Member Sync] Member {member_id} not found in database")
                        continue
                    
                    member_name = member.get('name', 'Unknown')
                    current_projects = member.get('projects', [])
                    
                    # Normalize function to handle both "ooo" and "project-ooo" formats
                    def normalize_key(key: str) -> str:
                        key_lower = key.lower()
                        if key_lower.startswith("project-"):
                            return key_lower[8:]  # Remove "project-" prefix
                        return key_lower
                    
                    # Check if project is already in list (normalized comparison)
                    project_key_normalized = normalize_key(project_key)
                    if any(normalize_key(p) == project_key_normalized for p in current_projects):
                        logger.info(f"[Project-Member Sync] Project {project_key} already in member {member_id} ({member_name}) projects: {current_projects}")
                    else:
                        result = members_collection.update_one(
                            {"_id": member_obj_id},
                            {
                                "$addToSet": {"projects": project_key},
                                "$set": {"updated_at": datetime.utcnow()}
                            }
                        )
                        logger.info(f"[Project-Member Sync] Added {project_key} to member {member_id} ({member_name}): matched={result.matched_count}, modified={result.modified_count}")
                    
                    # Also update team field if not set
                    if not member.get("team"):
                        members_collection.update_one(
                            {"_id": member_obj_id},
                            {"$set": {"team": project_key}}
                        )
                        logger.info(f"[Project-Member Sync] Set team for member {member_id} ({member_name}): {project_key}")
                        
                except Exception as e:
                    logger.error(f"[Project-Member Sync] Failed to add {project_key} to member {member_id}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
        
        # Update document
        projects_collection.update_one(
            {"key": project_key},
            {"$set": update_doc}
        )
        
        # Fetch updated document
        updated = projects_collection.find_one({"key": project_key})
        
        logger.info(f"Updated project: {project_key}")
        
        return ProjectResponse(
            id=str(updated["_id"]),
            key=updated["key"],
            name=updated["name"],
            description=updated.get("description"),
            slack_channel=updated.get("slack_channel"),
            slack_channel_id=updated.get("slack_channel_id"),
            lead=updated.get("lead"),
            repositories=updated.get("repositories", []),
            repositories_synced_at=updated.get("repositories_synced_at"),
            github_team_slug=updated.get("github_team_slug"),
            drive_folders=updated.get("drive_folders", []),
            notion_page_ids=updated.get("notion_page_ids", []),
            notion_parent_page_id=updated.get("notion_parent_page_id"),
            sub_projects=updated.get("sub_projects", []),
                member_ids=convert_member_ids_to_strings(updated.get("member_ids", [])),
                is_active=updated.get("is_active", True),
                created_at=updated.get("created_at", datetime.utcnow()),
                updated_at=updated.get("updated_at", datetime.utcnow())
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating project: {e}")
        raise HTTPException(status_code=500, detail="Failed to update project")


@router.delete("/projects/{project_key}", status_code=204)
async def delete_project(request: Request, project_key: str):
    """
    Delete a project (soft delete by setting is_active=False)
    
    Args:
        project_key: Project identifier
    """
    try:
        mongo = get_mongo()
        db = mongo.db
        projects_collection = db["projects"]
        
        # Check if project exists
        existing = projects_collection.find_one({"key": project_key})
        if not existing:
            raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")
        
        # Soft delete (set is_active=False)
        projects_collection.update_one(
            {"key": project_key},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )
        
        logger.info(f"Deleted (deactivated) project: {project_key}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete project")


@router.post("/projects/{project_key}/sync-repositories", response_model=ProjectResponse)
async def sync_repositories(request: Request, project_key: str):
    """
    Manually trigger GitHub Teams API sync for project repositories
    
    Args:
        project_key: Project identifier
    
    Returns:
        Updated project with synced repositories
    """
    try:
        from backend.api.v1.custom_export import get_project_repositories_from_teams
        
        mongo = get_mongo()
        db = mongo.get_database_sync()
        projects_collection = db["projects"]
        
        # Get project
        project = projects_collection.find_one({"key": project_key})
        if not project:
            raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")
        
        # Get GitHub team slug
        team_slug = project.get("github_team_slug") or project_key
        
        # Fetch repositories from GitHub Teams API
        repositories = list(get_project_repositories_from_teams(project_key))
        
        # Update project
        now = datetime.utcnow()
        projects_collection.update_one(
            {"key": project_key},
            {"$set": {
                "repositories": repositories,
                "repositories_synced_at": now,
                "updated_at": now
            }}
        )
        
        # Fetch updated document
        updated = projects_collection.find_one({"key": project_key})
        
        logger.info(f"Synced {len(repositories)} repositories for project: {project_key}")
        
        return ProjectResponse(
            id=str(updated["_id"]),
            key=updated["key"],
            name=updated["name"],
            description=updated.get("description"),
            slack_channel=updated.get("slack_channel"),
            slack_channel_id=updated.get("slack_channel_id"),
            lead=updated.get("lead"),
            repositories=updated.get("repositories", []),
            repositories_synced_at=updated.get("repositories_synced_at"),
            github_team_slug=updated.get("github_team_slug"),
            drive_folders=updated.get("drive_folders", []),
            notion_page_ids=updated.get("notion_page_ids", []),
            notion_parent_page_id=updated.get("notion_parent_page_id"),
            sub_projects=updated.get("sub_projects", []),
            member_ids=convert_member_ids_to_strings(updated.get("member_ids", [])),
            is_active=updated.get("is_active", True),
            created_at=updated.get("created_at", datetime.utcnow()),
            updated_at=updated.get("updated_at", datetime.utcnow())
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing repositories: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync repositories")


# ============================================
# Grant Reports Management
# ============================================

@router.get("/projects/{project_key}/grant-reports", response_model=GrantReportsResponse)
async def get_grant_reports(request: Request, project_key: str):
    """
    Get all grant reports for a project
    
    Args:
        project_key: Project identifier (e.g., 'project-trh')
    
    Returns:
        List of grant reports sorted by year and quarter (most recent first)
    """
    try:
        mongo = get_mongo()
        db = mongo.db
        projects_collection = db["projects"]
        
        # Check if project exists
        project = projects_collection.find_one({"key": project_key})
        if not project:
            raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")
        
        # Get grant reports
        grant_reports = project.get("grant_reports", [])
        
        # Sort by year (desc) and quarter (desc)
        sorted_reports = sorted(
            grant_reports,
            key=lambda r: (r.get("year", 0), r.get("quarter", 0)),
            reverse=True
        )
        
        reports = [
            GrantReportResponse(
                id=report.get("id", ""),
                title=report.get("title", ""),
                year=report.get("year", 0),
                quarter=report.get("quarter", 0),
                drive_url=report.get("drive_url", ""),
                file_name=report.get("file_name"),
                created_at=report.get("created_at")
            )
            for report in sorted_reports
        ]
        
        return GrantReportsResponse(project_key=project_key, reports=reports)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching grant reports: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch grant reports: {str(e)}")


@router.post("/projects/{project_key}/grant-reports", response_model=GrantReportResponse, status_code=201)
async def add_grant_report(request: Request, project_key: str, body: GrantReportRequest):
    """
    Add a grant report to a project
    
    Args:
        project_key: Project identifier
        body: Grant report data
    
    Returns:
        Created grant report
    """
    try:
        import uuid
        
        mongo = get_mongo()
        db = mongo.db
        projects_collection = db["projects"]
        
        # Check if project exists
        project = projects_collection.find_one({"key": project_key})
        if not project:
            raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")
        
        # Check if report for this year/quarter already exists
        existing_reports = project.get("grant_reports", [])
        for report in existing_reports:
            if report.get("year") == body.year and report.get("quarter") == body.quarter:
                raise HTTPException(
                    status_code=409,
                    detail=f"Grant report for {body.year} Q{body.quarter} already exists"
                )
        
        # Create new report
        now = datetime.utcnow()
        new_report = {
            "id": str(uuid.uuid4()),
            "title": body.title,
            "year": body.year,
            "quarter": body.quarter,
            "drive_url": body.drive_url,
            "file_name": body.file_name,
            "created_at": now
        }
        
        # Add to project's grant_reports array
        projects_collection.update_one(
            {"key": project_key},
            {
                "$push": {"grant_reports": new_report},
                "$set": {"updated_at": now}
            }
        )
        
        logger.info(f"Added grant report for {project_key}: {body.year} Q{body.quarter}")
        
        return GrantReportResponse(
            id=new_report["id"],
            title=new_report["title"],
            year=new_report["year"],
            quarter=new_report["quarter"],
            drive_url=new_report["drive_url"],
            file_name=new_report.get("file_name"),
            created_at=new_report.get("created_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding grant report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add grant report: {str(e)}")


@router.put("/projects/{project_key}/grant-reports/{report_id}", response_model=GrantReportResponse)
async def update_grant_report(request: Request, project_key: str, report_id: str, body: GrantReportRequest):
    """
    Update an existing grant report
    
    Args:
        project_key: Project identifier
        report_id: Grant report ID
        body: Updated grant report data
    
    Returns:
        Updated grant report
    """
    try:
        mongo = get_mongo()
        db = mongo.db
        projects_collection = db["projects"]
        
        # Check if project exists
        project = projects_collection.find_one({"key": project_key})
        if not project:
            raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")
        
        # Find the report
        grant_reports = project.get("grant_reports", [])
        report_index = None
        for i, report in enumerate(grant_reports):
            if report.get("id") == report_id:
                report_index = i
                break
        
        if report_index is None:
            raise HTTPException(status_code=404, detail=f"Grant report '{report_id}' not found")
        
        # Check if new year/quarter conflicts with existing report
        for i, report in enumerate(grant_reports):
            if i != report_index and report.get("year") == body.year and report.get("quarter") == body.quarter:
                raise HTTPException(
                    status_code=409,
                    detail=f"Grant report for {body.year} Q{body.quarter} already exists"
                )
        
        # Update report
        grant_reports[report_index].update({
            "title": body.title,
            "year": body.year,
            "quarter": body.quarter,
            "drive_url": body.drive_url,
            "file_name": body.file_name
        })
        
        # Save to database
        now = datetime.utcnow()
        projects_collection.update_one(
            {"key": project_key},
            {
                "$set": {
                    "grant_reports": grant_reports,
                    "updated_at": now
                }
            }
        )
        
        updated_report = grant_reports[report_index]
        logger.info(f"Updated grant report for {project_key}: {report_id}")
        
        return GrantReportResponse(
            id=updated_report["id"],
            title=updated_report["title"],
            year=updated_report["year"],
            quarter=updated_report["quarter"],
            drive_url=updated_report["drive_url"],
            file_name=updated_report.get("file_name"),
            created_at=updated_report.get("created_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating grant report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update grant report: {str(e)}")


@router.delete("/projects/{project_key}/grant-reports/{report_id}", status_code=204)
async def delete_grant_report(request: Request, project_key: str, report_id: str):
    """
    Delete a grant report
    
    Args:
        project_key: Project identifier
        report_id: Grant report ID
    """
    try:
        mongo = get_mongo()
        db = mongo.db
        projects_collection = db["projects"]
        
        # Check if project exists
        project = projects_collection.find_one({"key": project_key})
        if not project:
            raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")
        
        # Find and remove the report
        grant_reports = project.get("grant_reports", [])
        report_found = False
        updated_reports = []
        
        for report in grant_reports:
            if report.get("id") == report_id:
                report_found = True
            else:
                updated_reports.append(report)
        
        if not report_found:
            raise HTTPException(status_code=404, detail=f"Grant report '{report_id}' not found")
        
        # Save to database
        now = datetime.utcnow()
        projects_collection.update_one(
            {"key": project_key},
            {
                "$set": {
                    "grant_reports": updated_reports,
                    "updated_at": now
                }
            }
        )
        
        logger.info(f"Deleted grant report for {project_key}: {report_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting grant report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete grant report: {str(e)}")


# ============================================
# Drive Folder Files API
# ============================================

def get_drive_service():
    """Get authenticated Google Drive service."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        raise HTTPException(
            status_code=500, 
            detail="Google API libraries not installed"
        )
    
    creds = None
    
    # Check for existing token (prefer token_diff.pickle which has drive.readonly scope)
    token_paths = [
        Path("config/google_drive/token_diff.pickle"),
        Path("config/google_drive/token_admin.pickle"),
        Path("config/google_drive/token.pickle"),
        Path("logs/token_admin.pickle"),
        Path("/app/logs/token_admin.pickle"),
    ]
    
    for token_path in token_paths:
        if token_path.exists():
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
            logger.info(f"Loaded Drive credentials from {token_path}")
            break
    
    if not creds:
        raise HTTPException(
            status_code=500,
            detail="No Google Drive credentials found. Please authenticate first."
        )
    
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    return build('drive', 'v3', credentials=creds)


def extract_year_quarter(filename: str) -> tuple:
    """Extract year and quarter from filename like TRH_2024_Q4.pdf"""
    year = None
    quarter = None
    
    # Pattern: XXX_2024_Q4.pdf or 2024_Q4 or Q4_2024
    match = re.search(r'(\d{4}).*[Qq](\d)', filename)
    if match:
        year = int(match.group(1))
        quarter = int(match.group(2))
    else:
        # Try reverse pattern: Q4_2024
        match = re.search(r'[Qq](\d).*(\d{4})', filename)
        if match:
            quarter = int(match.group(1))
            year = int(match.group(2))
    
    return year, quarter


@router.get("/drive/folders")
async def list_drive_folders(request: Request):
    """
    List all folders accessible by the Drive API.
    """
    try:
        service = get_drive_service()
        
        folders = []
        query = "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        page_token = None
        
        while True:
            response = service.files().list(
                q=query,
                spaces='drive',
                fields='nextPageToken, files(id, name, parents)',
                orderBy='name',
                pageSize=100,
                pageToken=page_token
            ).execute()
            
            for file in response.get('files', []):
                folders.append({
                    'id': file['id'],
                    'name': file['name'],
                    'url': f"https://drive.google.com/drive/folders/{file['id']}",
                    'parents': file.get('parents', [])
                })
            
            page_token = response.get('nextPageToken')
            if not page_token:
                break
        
        return {"folders": folders}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing Drive folders: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list Drive folders: {str(e)}")


@router.get("/drive/folder/{folder_id}/files", response_model=DriveFolderFilesResponse)
async def list_drive_folder_files(request: Request, folder_id: str, include_subfolders: bool = True):
    """
    List files in a Google Drive folder.
    
    Args:
        folder_id: Google Drive folder ID
        include_subfolders: Whether to include files from subfolders
    
    Returns:
        List of files with their direct links
    """
    try:
        service = get_drive_service()
        
        all_files = []
        folders_to_process = [(folder_id, "")]
        
        while folders_to_process:
            current_folder_id, path_prefix = folders_to_process.pop(0)
            
            query = f"'{current_folder_id}' in parents and trashed = false"
            page_token = None
            
            while True:
                response = service.files().list(
                    q=query,
                    spaces='drive',
                    fields='nextPageToken, files(id, name, mimeType, modifiedTime)',
                    orderBy='name',
                    pageSize=100,
                    pageToken=page_token
                ).execute()
                
                for file in response.get('files', []):
                    file_path = f"{path_prefix}/{file['name']}" if path_prefix else file['name']
                    
                    if file['mimeType'] == 'application/vnd.google-apps.folder':
                        if include_subfolders:
                            folders_to_process.append((file['id'], file_path))
                    else:
                        # Construct direct file link
                        file_id = file['id']
                        direct_link = f"https://drive.google.com/file/d/{file_id}/view"
                        
                        year, quarter = extract_year_quarter(file['name'])
                        
                        all_files.append(DriveFileResponse(
                            id=file_id,
                            name=file['name'],
                            link=direct_link,
                            mimeType=file.get('mimeType'),
                            modifiedTime=file.get('modifiedTime'),
                            year=year,
                            quarter=quarter
                        ))
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
        
        # Sort by year (desc) and quarter (desc)
        all_files.sort(key=lambda x: (x.year or 0, x.quarter or 0), reverse=True)
        
        return DriveFolderFilesResponse(
            folder_id=folder_id,
            files=all_files
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing Drive folder: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list Drive folder: {str(e)}")


@router.get("/drive/file/{file_id}/download")
async def download_drive_file(request: Request, file_id: str):
    """
    Download a file from Google Drive.
    
    Args:
        file_id: Google Drive file ID
    
    Returns:
        The file content as a streaming response
    """
    from fastapi.responses import StreamingResponse
    import io
    
    try:
        service = get_drive_service()
        
        # Get file metadata first
        file_metadata = service.files().get(
            fileId=file_id, 
            fields='name, mimeType'
        ).execute()
        
        file_name = file_metadata.get('name', 'download')
        mime_type = file_metadata.get('mimeType', 'application/octet-stream')
        
        # Download file content
        from googleapiclient.http import MediaIoBaseDownload
        
        request_download = service.files().get_media(fileId=file_id)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request_download)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        file_content.seek(0)
        
        # Return as streaming response
        headers = {
            'Content-Disposition': f'attachment; filename="{file_name}"'
        }
        
        return StreamingResponse(
            file_content,
            media_type=mime_type,
            headers=headers
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading Drive file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")

