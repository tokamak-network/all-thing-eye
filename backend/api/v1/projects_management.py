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

