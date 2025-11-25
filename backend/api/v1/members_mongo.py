"""
Members Management API
Handles CRUD operations for team members
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime
from src.utils.logger import get_logger
from backend.middleware.jwt_auth import require_admin

logger = get_logger(__name__)
router = APIRouter()


# Get MongoDB manager instance
def get_mongo():
    from backend.main import mongo_manager
    return mongo_manager


class MemberIdentifier(BaseModel):
    """Member identifier model"""
    identifier_type: str
    identifier_value: str


class MemberCreate(BaseModel):
    """Member creation model"""
    name: str
    email: EmailStr
    github_id: Optional[str] = None
    slack_id: Optional[str] = None
    notion_id: Optional[str] = None
    role: Optional[str] = None
    project: Optional[str] = None


class MemberUpdate(BaseModel):
    """Member update model"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    github_id: Optional[str] = None
    slack_id: Optional[str] = None
    notion_id: Optional[str] = None
    role: Optional[str] = None
    project: Optional[str] = None


@router.get("/members")
async def get_members(
    request: Request,
    _admin: str = Depends(require_admin)
) -> List[Dict[str, Any]]:
    """
    Get all team members with their identifiers
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        # Get all members
        members_cursor = db["members"].find({})
        members = []
        
        async for member in members_cursor:
            member_id = str(member["_id"])
            
            # Get member identifiers
            identifiers_cursor = db["member_identifiers"].find({"member_id": member_id})
            identifiers = {}
            
            async for identifier in identifiers_cursor:
                identifiers[identifier["identifier_type"]] = identifier["identifier_value"]
            
            members.append({
                "id": member_id,
                "name": member.get("name"),
                "email": member.get("email"),
                "role": member.get("role"),
                "project": member.get("project"),
                "identifiers": identifiers,
                "created_at": member.get("created_at"),
                "updated_at": member.get("updated_at")
            })
        
        # Sort by name
        members.sort(key=lambda x: x.get("name", "").lower())
        
        return members
        
    except Exception as e:
        logger.error(f"Error fetching members: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch members: {str(e)}")


@router.post("/members")
async def create_member(
    member_data: MemberCreate,
    request: Request,
    _admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    """
    Create a new team member
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        # Check if member with same email already exists
        existing_member = await db["members"].find_one({"email": member_data.email})
        if existing_member:
            raise HTTPException(status_code=400, detail=f"Member with email {member_data.email} already exists")
        
        # Create member document
        now = datetime.utcnow().isoformat() + 'Z'
        member_doc = {
            "name": member_data.name,
            "email": member_data.email,
            "role": member_data.role,
            "project": member_data.project,
            "created_at": now,
            "updated_at": now
        }
        
        # Insert member
        result = await db["members"].insert_one(member_doc)
        member_id = str(result.inserted_id)
        
        # Create member identifiers
        identifiers = []
        
        # Email identifier
        await db["member_identifiers"].insert_one({
            "member_id": member_id,
            "identifier_type": "email",
            "identifier_value": member_data.email,
            "created_at": now
        })
        identifiers.append({"type": "email", "value": member_data.email})
        
        # GitHub identifier
        if member_data.github_id:
            await db["member_identifiers"].insert_one({
                "member_id": member_id,
                "identifier_type": "github",
                "identifier_value": member_data.github_id,
                "created_at": now
            })
            identifiers.append({"type": "github", "value": member_data.github_id})
        
        # Slack identifier
        if member_data.slack_id:
            await db["member_identifiers"].insert_one({
                "member_id": member_id,
                "identifier_type": "slack",
                "identifier_value": member_data.slack_id,
                "created_at": now
            })
            identifiers.append({"type": "slack", "value": member_data.slack_id})
        
        # Notion identifier
        if member_data.notion_id:
            await db["member_identifiers"].insert_one({
                "member_id": member_id,
                "identifier_type": "notion",
                "identifier_value": member_data.notion_id,
                "created_at": now
            })
            identifiers.append({"type": "notion", "value": member_data.notion_id})
        
        logger.info(f"Created new member: {member_data.name} ({member_id})")
        
        return {
            "id": member_id,
            "name": member_data.name,
            "email": member_data.email,
            "role": member_data.role,
            "project": member_data.project,
            "identifiers": identifiers,
            "created_at": now,
            "updated_at": now
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating member: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create member: {str(e)}")


@router.patch("/members/{member_id}")
async def update_member(
    member_id: str,
    member_data: MemberUpdate,
    request: Request,
    _admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    """
    Update an existing team member
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        # Check if member exists
        from bson import ObjectId
        try:
            member_obj_id = ObjectId(member_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid member ID format")
        
        existing_member = await db["members"].find_one({"_id": member_obj_id})
        if not existing_member:
            raise HTTPException(status_code=404, detail=f"Member with ID {member_id} not found")
        
        # Prepare update data
        update_data = {}
        if member_data.name is not None:
            update_data["name"] = member_data.name
        if member_data.email is not None:
            update_data["email"] = member_data.email
        if member_data.role is not None:
            update_data["role"] = member_data.role
        if member_data.project is not None:
            update_data["project"] = member_data.project
        
        if update_data:
            update_data["updated_at"] = datetime.utcnow().isoformat() + 'Z'
            await db["members"].update_one(
                {"_id": member_obj_id},
                {"$set": update_data}
            )
        
        # Update identifiers
        now = datetime.utcnow().isoformat() + 'Z'
        
        async def update_identifier(identifier_type: str, identifier_value: Optional[str]):
            if identifier_value is not None:
                # Check if identifier exists
                existing_identifier = await db["member_identifiers"].find_one({
                    "member_id": member_id,
                    "identifier_type": identifier_type
                })
                
                if existing_identifier:
                    # Update existing
                    await db["member_identifiers"].update_one(
                        {"_id": existing_identifier["_id"]},
                        {"$set": {"identifier_value": identifier_value, "updated_at": now}}
                    )
                else:
                    # Create new
                    await db["member_identifiers"].insert_one({
                        "member_id": member_id,
                        "identifier_type": identifier_type,
                        "identifier_value": identifier_value,
                        "created_at": now
                    })
        
        await update_identifier("github", member_data.github_id)
        await update_identifier("slack", member_data.slack_id)
        await update_identifier("notion", member_data.notion_id)
        
        # Get updated member
        updated_member = await db["members"].find_one({"_id": member_obj_id})
        
        # Get identifiers
        identifiers_cursor = db["member_identifiers"].find({"member_id": member_id})
        identifiers = {}
        async for identifier in identifiers_cursor:
            identifiers[identifier["identifier_type"]] = identifier["identifier_value"]
        
        logger.info(f"Updated member: {member_id}")
        
        return {
            "id": member_id,
            "name": updated_member.get("name"),
            "email": updated_member.get("email"),
            "role": updated_member.get("role"),
            "project": updated_member.get("project"),
            "identifiers": identifiers,
            "created_at": updated_member.get("created_at"),
            "updated_at": updated_member.get("updated_at")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating member: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update member: {str(e)}")


@router.delete("/members/{member_id}")
async def delete_member(
    member_id: str,
    request: Request,
    _admin: str = Depends(require_admin)
) -> Dict[str, str]:
    """
    Delete a team member and their identifiers
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        # Check if member exists
        from bson import ObjectId
        try:
            member_obj_id = ObjectId(member_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid member ID format")
        
        existing_member = await db["members"].find_one({"_id": member_obj_id})
        if not existing_member:
            raise HTTPException(status_code=404, detail=f"Member with ID {member_id} not found")
        
        member_name = existing_member.get("name", "Unknown")
        
        # Delete member identifiers
        await db["member_identifiers"].delete_many({"member_id": member_id})
        
        # Delete member
        await db["members"].delete_one({"_id": member_obj_id})
        
        logger.info(f"Deleted member: {member_name} ({member_id})")
        
        return {
            "message": f"Member {member_name} deleted successfully",
            "deleted_member_id": member_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting member: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete member: {str(e)}")
