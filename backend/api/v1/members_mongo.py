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
    eoa_address: Optional[str] = None  # Ethereum address for All-Thing-Eye beta access


class MemberUpdate(BaseModel):
    """Member update model"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    github_id: Optional[str] = None
    slack_id: Optional[str] = None
    notion_id: Optional[str] = None
    role: Optional[str] = None
    project: Optional[str] = None
    eoa_address: Optional[str] = None  # Ethereum address for All-Thing-Eye beta access


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
        
        # Check if collections exist
        collection_names = await db.list_collection_names()
        if "members" not in collection_names:
            logger.warning("Members collection does not exist")
            return []
        
        # Get all members
        members_cursor = db["members"].find({})
        members = []
        
        async for member in members_cursor:
            try:
                member_id = str(member["_id"])
                
                # Get member identifiers (if collection exists)
                # Group by source (github, slack, notion, drive) and get the primary identifier
                # Prefer username/user_id over email for display
                identifiers = {}
                if "member_identifiers" in collection_names:
                    from bson import ObjectId
                    # Try both string and ObjectId format for member_id
                    try:
                        member_obj_id = ObjectId(member_id)
                    except:
                        member_obj_id = None
                    
                    # Query with both formats
                    query = {"$or": [{"member_id": member_id}]}
                    if member_obj_id:
                        query["$or"].append({"member_id": member_obj_id})
                    
                    identifiers_cursor = db["member_identifiers"].find(query)
                    identifier_list = []
                    async for identifier in identifiers_cursor:
                        identifier_list.append(identifier)
                        source = identifier.get("source")
                        identifier_type = identifier.get("identifier_type")
                        identifier_value = identifier.get("identifier_value")
                        
                        logger.debug(f"Member {member_id} identifier: source={source}, type={identifier_type}, value={identifier_value}")
                        
                        if source and identifier_value:
                            # For each source, prefer username/user_id over email
                            if source not in identifiers:
                                identifiers[source] = identifier_value
                            elif identifier_type in ["username", "user_id"]:
                                # Prefer username/user_id over email
                                identifiers[source] = identifier_value
                    
                    # Log only if identifiers found (to reduce log noise)
                    if identifier_list:
                        logger.debug(f"Member {member_id} ({member.get('name')}) has {len(identifier_list)} identifiers: {identifiers}")
                
                members.append({
                    "id": member_id,
                    "name": member.get("name"),
                    "email": member.get("email"),
                    "role": member.get("role"),
                    "project": member.get("project"),
                    "eoa_address": member.get("eoa_address"),
                    "identifiers": identifiers,
                    "created_at": member.get("created_at"),
                    "updated_at": member.get("updated_at")
                })
            except Exception as e:
                logger.warning(f"Error processing member {member.get('_id')}: {e}")
                continue
        
        # Sort by name
        members.sort(key=lambda x: x.get("name", "").lower())
        
        return members
        
    except Exception as e:
        logger.error(f"Error fetching members: {e}")
        import traceback
        logger.error(traceback.format_exc())
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
            "eoa_address": member_data.eoa_address,
            "created_at": now,
            "updated_at": now
        }
        
        # Insert member
        result = await db["members"].insert_one(member_doc)
        member_id = str(result.inserted_id)
        
        # Create member identifiers
        identifiers = []
        
        # Email identifier (for Drive/general use)
        await db["member_identifiers"].insert_one({
            "member_id": member_id,
            "member_name": member_data.name,
            "source": "drive",
            "identifier_type": "email",
            "identifier_value": member_data.email,
            "created_at": now
        })
        identifiers.append({"type": "email", "value": member_data.email})
        
        # GitHub identifier
        if member_data.github_id:
            await db["member_identifiers"].insert_one({
                "member_id": member_id,
                "member_name": member_data.name,
                "source": "github",
                "identifier_type": "username",
                "identifier_value": member_data.github_id,
                "created_at": now
            })
            identifiers.append({"type": "github_id", "value": member_data.github_id})
        
        # Slack identifier
        if member_data.slack_id:
            # Determine if it's email or user_id
            id_type = "email" if '@' in member_data.slack_id else "user_id"
            await db["member_identifiers"].insert_one({
                "member_id": member_id,
                "member_name": member_data.name,
                "source": "slack",
                "identifier_type": id_type,
                "identifier_value": member_data.slack_id,
                "created_at": now
            })
            identifiers.append({"type": "slack_id", "value": member_data.slack_id})
            
            # If slack_id is an email, try to find actual Slack user_id from existing messages
            if '@' in member_data.slack_id:
                slack_email = member_data.slack_id
                try:
                    # Try to find actual user_id from slack_messages collection
                    slack_msg = await db["slack_messages"].find_one({
                        "$or": [
                            {"user_email": slack_email},
                            {"user_email": slack_email.lower()}
                        ]
                    })
                    if slack_msg and slack_msg.get("user_id"):
                        actual_user_id = slack_msg["user_id"]
                        # Add user_id identifier as well
                        await db["member_identifiers"].insert_one({
                            "member_id": member_id,
                            "member_name": member_data.name,
                            "source": "slack",
                            "identifier_type": "user_id",
                            "identifier_value": actual_user_id,
                            "created_at": now
                        })
                        identifiers.append({"type": "slack_user_id", "value": actual_user_id})
                        logger.info(f"Found Slack user_id {actual_user_id} for email {slack_email}")
                except Exception as e:
                    # If collection doesn't exist or query fails, just log and continue
                    logger.warning(f"Could not find Slack user_id for {slack_email}: {e}")
        
        # Notion identifier
        if member_data.notion_id:
            # Notion ID is typically an email
            notion_email = member_data.notion_id
            await db["member_identifiers"].insert_one({
                "member_id": member_id,
                "member_name": member_data.name,
                "source": "notion",
                "identifier_type": "email",
                "identifier_value": notion_email,
                "created_at": now
            })
            identifiers.append({"type": "notion_id", "value": notion_email})
            
            # Try to find actual Notion user ID from existing pages
            if '@' in notion_email:
                try:
                    notion_page = await db["notion_pages"].find_one({
                        "$or": [
                            {"created_by.email": notion_email},
                            {"created_by.email": notion_email.lower()},
                            {"last_edited_by.email": notion_email},
                            {"last_edited_by.email": notion_email.lower()}
                        ]
                    })
                    if notion_page:
                        # Try to get user ID from created_by or last_edited_by
                        created_by = notion_page.get("created_by", {})
                        last_edited_by = notion_page.get("last_edited_by", {})
                        
                        notion_user_id = None
                        if created_by.get("id"):
                            notion_user_id = created_by["id"]
                        elif last_edited_by.get("id"):
                            notion_user_id = last_edited_by["id"]
                        
                        if notion_user_id:
                            # Add user_id identifier as well
                            await db["member_identifiers"].insert_one({
                                "member_id": member_id,
                                "member_name": member_data.name,
                                "source": "notion",
                                "identifier_type": "user_id",
                                "identifier_value": notion_user_id,
                                "created_at": now
                            })
                            identifiers.append({"type": "notion_user_id", "value": notion_user_id})
                            logger.info(f"Found Notion user_id {notion_user_id} for email {notion_email}")
                except Exception as e:
                    # If collection doesn't exist or query fails, just log and continue
                    logger.warning(f"Could not find Notion user_id for {notion_email}: {e}")
        
        # Clear member mapping cache to ensure fresh data after creation
        from backend.api.v1.activities_mongo import clear_member_mapping_cache
        clear_member_mapping_cache()
        
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
        if member_data.eoa_address is not None:
            update_data["eoa_address"] = member_data.eoa_address
        
        if update_data:
            update_data["updated_at"] = datetime.utcnow().isoformat() + 'Z'
            await db["members"].update_one(
                {"_id": member_obj_id},
                {"$set": update_data}
            )
        
        # Update identifiers
        now = datetime.utcnow().isoformat() + 'Z'
        
        # If name was updated, update all existing identifiers' member_name field
        if member_data.name is not None:
            new_name = member_data.name
            await db["member_identifiers"].update_many(
                {"member_id": member_id},
                {"$set": {"member_name": new_name, "updated_at": now}}
            )
        
        async def update_identifier(source: str, sub_type: str, identifier_value: Optional[str]):
            if identifier_value is not None:
                # Check if identifier exists for this member
                existing_identifier = await db["member_identifiers"].find_one({
                    "member_id": member_id,
                    "source": source,
                    "identifier_type": sub_type
                })
                
                # Check if this identifier value already exists for another member
                duplicate_identifier = await db["member_identifiers"].find_one({
                    "source": source,
                    "identifier_type": sub_type,
                    "identifier_value": identifier_value,
                    "member_id": {"$ne": member_id}
                })
                
                if duplicate_identifier:
                    # Identifier already exists for another member - skip to avoid duplicate key error
                    logger.warning(
                        f"Identifier {source}:{sub_type}:{identifier_value} already exists for member {duplicate_identifier.get('member_id')}. "
                        f"Skipping update for member {member_id}."
                    )
                    return
                
                member_name = update_data.get("name", existing_member.get("name"))
                
                if existing_identifier:
                    # Update existing
                    await db["member_identifiers"].update_one(
                        {"_id": existing_identifier["_id"]},
                        {"$set": {
                            "member_name": member_name,
                            "identifier_type": sub_type,
                            "identifier_value": identifier_value,
                            "updated_at": now
                        }}
                    )
                else:
                    # Create new - check again to avoid race condition
                    try:
                        await db["member_identifiers"].insert_one({
                            "member_id": member_id,
                            "member_name": member_name,
                            "source": source,
                            "identifier_type": sub_type,
                            "identifier_value": identifier_value,
                            "created_at": now
                        })
                    except Exception as e:
                        # If duplicate key error, it means another process created it
                        if "duplicate key" in str(e).lower() or "E11000" in str(e):
                            logger.warning(
                                f"Duplicate key error when inserting identifier {source}:{sub_type}:{identifier_value} "
                                f"for member {member_id}. It may have been created by another process."
                            )
                        else:
                            raise
        
        # Update GitHub identifier
        if member_data.github_id is not None:
            await update_identifier("github", "username", member_data.github_id)
        
        # Update Slack identifier
        if member_data.slack_id is not None:
            slack_type = "email" if '@' in member_data.slack_id else "user_id"
            await update_identifier("slack", slack_type, member_data.slack_id)
            
            # If slack_id is an email, try to find actual Slack user_id from existing messages
            if '@' in member_data.slack_id:
                slack_email = member_data.slack_id
                try:
                    # Try to find actual user_id from slack_messages collection
                    slack_msg = await db["slack_messages"].find_one({
                        "$or": [
                            {"user_email": slack_email},
                            {"user_email": slack_email.lower()}
                        ]
                    })
                    if slack_msg and slack_msg.get("user_id"):
                        actual_user_id = slack_msg["user_id"]
                        # Add user_id identifier as well (don't overwrite email)
                        existing_user_id = await db["member_identifiers"].find_one({
                            "member_id": member_id,
                            "source": "slack",
                            "identifier_type": "user_id"
                        })
                        if not existing_user_id:
                            # Check if this user_id already exists for another member
                            duplicate_user_id = await db["member_identifiers"].find_one({
                                "source": "slack",
                                "identifier_type": "user_id",
                                "identifier_value": actual_user_id,
                                "member_id": {"$ne": member_id}
                            })
                            if not duplicate_user_id:
                                member_name = update_data.get("name", existing_member.get("name"))
                                try:
                                    await db["member_identifiers"].insert_one({
                                        "member_id": member_id,
                                        "member_name": member_name,
                                        "source": "slack",
                                        "identifier_type": "user_id",
                                        "identifier_value": actual_user_id,
                                        "created_at": now
                                    })
                                    logger.info(f"Found Slack user_id {actual_user_id} for email {slack_email}")
                                except Exception as e:
                                    if "duplicate key" in str(e).lower() or "E11000" in str(e):
                                        logger.warning(f"Duplicate key error when inserting Slack user_id {actual_user_id}: {e}")
                                    else:
                                        raise
                            else:
                                logger.warning(f"Slack user_id {actual_user_id} already exists for another member")
                except Exception as e:
                    logger.warning(f"Could not find Slack user_id for {slack_email}: {e}")
        
        # Update Notion identifier
        if member_data.notion_id is not None:
            await update_identifier("notion", "email", member_data.notion_id)
            
            # Try to find actual Notion user ID from existing pages
            if '@' in member_data.notion_id:
                notion_email = member_data.notion_id
                try:
                    notion_page = await db["notion_pages"].find_one({
                        "$or": [
                            {"created_by.email": notion_email},
                            {"created_by.email": notion_email.lower()},
                            {"last_edited_by.email": notion_email},
                            {"last_edited_by.email": notion_email.lower()}
                        ]
                    })
                    if notion_page:
                        # Try to get user ID from created_by or last_edited_by
                        created_by = notion_page.get("created_by", {})
                        last_edited_by = notion_page.get("last_edited_by", {})
                        
                        notion_user_id = None
                        if created_by.get("id"):
                            notion_user_id = created_by["id"]
                        elif last_edited_by.get("id"):
                            notion_user_id = last_edited_by["id"]
                        
                        if notion_user_id:
                            # Add user_id identifier as well (don't overwrite email)
                            existing_user_id = await db["member_identifiers"].find_one({
                                "member_id": member_id,
                                "source": "notion",
                                "identifier_type": "user_id"
                            })
                            if not existing_user_id:
                                # Check if this user_id already exists for another member
                                duplicate_user_id = await db["member_identifiers"].find_one({
                                    "source": "notion",
                                    "identifier_type": "user_id",
                                    "identifier_value": notion_user_id,
                                    "member_id": {"$ne": member_id}
                                })
                                if not duplicate_user_id:
                                    member_name = update_data.get("name", existing_member.get("name"))
                                    try:
                                        await db["member_identifiers"].insert_one({
                                            "member_id": member_id,
                                            "member_name": member_name,
                                            "source": "notion",
                                            "identifier_type": "user_id",
                                            "identifier_value": notion_user_id,
                                            "created_at": now
                                        })
                                        logger.info(f"Found Notion user_id {notion_user_id} for email {notion_email}")
                                    except Exception as e:
                                        if "duplicate key" in str(e).lower() or "E11000" in str(e):
                                            logger.warning(f"Duplicate key error when inserting Notion user_id {notion_user_id}: {e}")
                                        else:
                                            raise
                                else:
                                    logger.warning(f"Notion user_id {notion_user_id} already exists for another member")
                except Exception as e:
                    logger.warning(f"Could not find Notion user_id for {notion_email}: {e}")
        
        # Update email identifier (for Drive)
        if member_data.email is not None:
            await update_identifier("drive", "email", member_data.email)
        
        # Clear member mapping cache to ensure fresh data after update
        from backend.api.v1.activities_mongo import clear_member_mapping_cache
        clear_member_mapping_cache()
        
        # Get updated member
        updated_member = await db["members"].find_one({"_id": member_obj_id})
        
        # Get identifiers
        identifiers_cursor = db["member_identifiers"].find({"member_id": member_id})
        identifiers = {}
        async for identifier in identifiers_cursor:
            # Use source as key for consistency
            source = identifier.get("source", identifier.get("identifier_type"))
            identifiers[source] = identifier["identifier_value"]
        
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


@router.get("/members/{member_id}")
async def get_member_detail(
    member_id: str,
    request: Request,
    _admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    """
    Get detailed information for a specific member including activity statistics
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        # Check if member exists
        from bson import ObjectId
        try:
            member_obj_id = ObjectId(member_id)
        except Exception as e:
            logger.error(f"Invalid member ID format: {member_id}, error: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid member ID format: {member_id}")
        
        # Try to find member by ObjectId first
        member = await db["members"].find_one({"_id": member_obj_id})
        
        # If not found, try to find by string ID (in case _id is stored as string)
        if not member:
            member = await db["members"].find_one({"_id": member_id})
        
        # If still not found, log available members for debugging
        if not member:
            # Get first few members for debugging
            sample_members = await db["members"].find({}).limit(5).to_list(length=5)
            sample_ids = [str(m.get("_id")) for m in sample_members]
            logger.warning(f"Member with ID {member_id} not found. Sample member IDs: {sample_ids}")
            raise HTTPException(
                status_code=404, 
                detail=f"Member with ID {member_id} not found. Please check if the member exists in the database."
            )
        
        member_name = member.get("name")
        
        # Get identifiers - try both string and ObjectId
        identifiers_cursor = db["member_identifiers"].find({
            "$or": [
                {"member_id": member_id},
                {"member_id": member_obj_id}
            ]
        })
        identifiers = {}
        async for identifier in identifiers_cursor:
            # Use source as key for consistency
            source = identifier.get("source", identifier.get("identifier_type"))
            identifiers[source] = identifier["identifier_value"]
        
        # Import helper functions from activities_mongo for accurate member filtering
        from backend.api.v1.activities_mongo import (
            load_member_mappings,
            get_identifiers_for_member
        )
        
        # Load member mappings for accurate filtering
        member_mappings = await load_member_mappings(db)
        
        # Get activity statistics
        activity_stats = {
            "total_activities": 0,
            "by_source": {},
            "by_type": {},
            "recent_activities": []
        }
        
        # GitHub statistics - use both member_mappings and direct identifiers
        github_identifiers = get_identifiers_for_member(member_mappings, 'github', member_name)
        
        # Also get identifiers directly from member_identifiers collection
        github_identifier_docs = await db["member_identifiers"].find({
            "$or": [
                {"member_id": member_id},
                {"member_id": member_obj_id}
            ],
            "source": "github"
        }).to_list(None)
        
        # Collect all GitHub identifiers
        all_github_identifiers = set(github_identifiers) if github_identifiers else set()
        for doc in github_identifier_docs:
            identifier_value = doc.get("identifier_value")
            if identifier_value:
                all_github_identifiers.add(identifier_value)
                # Also add lowercase version for case-insensitive matching
                all_github_identifiers.add(identifier_value.lower())
        
        github_query = {}
        
        # Build query with identifiers and fallback to member_name
        or_conditions = []
        if all_github_identifiers:
            or_conditions.append({'author_name': {'$in': list(all_github_identifiers)}})
        or_conditions.append({'author_name': member_name})
        # Case-insensitive fallback
        or_conditions.append({'author_name': {'$regex': f'^{member_name}$', '$options': 'i'}})
        
        if len(or_conditions) > 1:
            github_query['$or'] = or_conditions
        else:
            github_query.update(or_conditions[0])
        
        logger.debug(f"GitHub commits query for {member_name}: {github_query}, all_identifiers: {all_github_identifiers}")
        github_commits = await db["github_commits"].count_documents(github_query)
        
        # PRs - use author field with all identifiers
        pr_query = {}
        pr_or_conditions = []
        if all_github_identifiers:
            pr_or_conditions.append({'author': {'$in': list(all_github_identifiers)}})
        pr_or_conditions.append({'author': member_name})
        pr_or_conditions.append({'author': {'$regex': f'^{member_name}$', '$options': 'i'}})
        
        if len(pr_or_conditions) > 1:
            pr_query['$or'] = pr_or_conditions
        else:
            pr_query.update(pr_or_conditions[0])
        
        github_prs = await db["github_pull_requests"].count_documents(pr_query)
        
        # Issues - use author field with all identifiers
        issue_query = {}
        issue_or_conditions = []
        if all_github_identifiers:
            issue_or_conditions.append({'author': {'$in': list(all_github_identifiers)}})
        issue_or_conditions.append({'author': member_name})
        issue_or_conditions.append({'author': {'$regex': f'^{member_name}$', '$options': 'i'}})
        
        if len(issue_or_conditions) > 1:
            issue_query['$or'] = issue_or_conditions
        else:
            issue_query.update(issue_or_conditions[0])
        
        github_issues = await db["github_issues"].count_documents(issue_query)
        
        if github_commits + github_prs + github_issues > 0:
            activity_stats["by_source"]["github"] = {
                "total": github_commits + github_prs + github_issues,
                "commits": github_commits,
                "pull_requests": github_prs,
                "issues": github_issues
            }
            activity_stats["total_activities"] += github_commits + github_prs + github_issues
        
        # Slack statistics - use both member_mappings and direct identifiers
        slack_identifiers = get_identifiers_for_member(member_mappings, 'slack', member_name)
        slack_email = identifiers.get("slack") or identifiers.get("email")
        
        # Also get identifiers directly from member_identifiers collection
        slack_identifier_docs = await db["member_identifiers"].find({
            "$or": [
                {"member_id": member_id},
                {"member_id": member_obj_id}
            ],
            "source": "slack"
        }).to_list(None)
        
        # Collect all Slack identifiers
        all_slack_identifiers = set(slack_identifiers) if slack_identifiers else set()
        for doc in slack_identifier_docs:
            identifier_value = doc.get("identifier_value")
            if identifier_value:
                all_slack_identifiers.add(identifier_value)
        
        slack_query = {}
        or_conditions = []
        
        # Always include user_name as fallback (case-insensitive)
        or_conditions.append({'user_name': {'$regex': f'^{member_name}$', '$options': 'i'}})
        # Also try without case sensitivity for common name variations
        if member_name:
            or_conditions.append({'user_name': {'$regex': member_name, '$options': 'i'}})
        
        # Add identifier-based conditions
        if all_slack_identifiers:
            or_conditions.append({'user_id': {'$in': list(all_slack_identifiers)}})
            or_conditions.append({'user_email': {'$in': list(all_slack_identifiers)}})
        
        # Add email-based condition if available
        if slack_email:
            or_conditions.append({'user_email': slack_email})
            or_conditions.append({'user_email': slack_email.lower()})
        
        # Use $or if we have multiple conditions, otherwise use single condition
        if len(or_conditions) > 1:
            slack_query['$or'] = or_conditions
        elif len(or_conditions) == 1:
            slack_query.update(or_conditions[0])
        
        logger.debug(f"Slack query for {member_name}: {slack_query}, all_identifiers: {all_slack_identifiers}, email: {slack_email}")
        slack_messages = await db["slack_messages"].count_documents(slack_query)
        if slack_messages > 0:
            activity_stats["by_source"]["slack"] = {
                "total": slack_messages,
                "messages": slack_messages
            }
            activity_stats["total_activities"] += slack_messages
        
        # Notion statistics - use member_mappings for accurate filtering
        notion_identifiers = get_identifiers_for_member(member_mappings, 'notion', member_name)
        notion_query = {}
        if notion_identifiers:
            or_conditions = []
            or_conditions.append({'created_by.id': {'$in': notion_identifiers}})
            or_conditions.append({'created_by.email': {'$in': notion_identifiers}})
            or_conditions.append({'created_by.name': {"$regex": f"^{member_name}", "$options": "i"}})
            notion_query['$or'] = or_conditions
        else:
            notion_query['created_by.name'] = {"$regex": f"^{member_name}", "$options": "i"}
        
        notion_pages = await db["notion_pages"].count_documents(notion_query)
        if notion_pages > 0:
            activity_stats["by_source"]["notion"] = {
                "total": notion_pages,
                "pages": notion_pages
            }
            activity_stats["total_activities"] += notion_pages
        
        # Drive statistics - use member_mappings for accurate filtering
        drive_identifiers = get_identifiers_for_member(member_mappings, 'drive', member_name)
        drive_email = identifiers.get("email")
        
        drive_query = {}
        if drive_identifiers:
            drive_query['user_email'] = {'$in': drive_identifiers}
        elif drive_email:
            drive_query['user_email'] = drive_email
        else:
            drive_query['user_email'] = {"$regex": member_name, "$options": "i"}
        
        drive_activities = await db["drive_activities"].count_documents(drive_query)
        if drive_activities > 0:
            activity_stats["by_source"]["drive"] = {
                "total": drive_activities,
                "activities": drive_activities
            }
            activity_stats["total_activities"] += drive_activities
        
        # Get recent activities (last 20)
        recent = []
        
        # Recent GitHub commits
        github_commits_cursor = db["github_commits"].find(
            {"author_name": member_name}
        ).sort("date", -1).limit(5)
        async for commit in github_commits_cursor:
            recent.append({
                "source": "github",
                "type": "commit",
                "timestamp": commit.get("date"),
                "description": commit.get("message", "")[:100],
                "repository": commit.get("repository")
            })
        
        # Recent Slack messages
        if slack_email:
            slack_cursor = db["slack_messages"].find(
                {"user_email": slack_email}
            ).sort("timestamp", -1).limit(5)
            async for msg in slack_cursor:
                recent.append({
                    "source": "slack",
                    "type": "message",
                    "timestamp": msg.get("timestamp"),
                    "description": msg.get("text", "")[:100]
                })
        
        # Sort recent activities by timestamp
        recent.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
        activity_stats["recent_activities"] = recent[:20]

        # Calculate daily trends (last 90 days)
        from datetime import timedelta
        daily_trends = []
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=90)
            
            # Helper for aggregation with existing query
            async def get_daily_counts_with_query(collection_name, query, date_field):
                try:
                    coll = db[collection_name]
                    # Clone query and add date filter
                    trend_query = query.copy()
                    trend_query[date_field] = {"$gte": start_date, "$lte": end_date}
                    
                    # Build dateToString expression properly for MongoDB
                    # Use dictionary construction to properly reference the field
                    date_expr = {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": f"${date_field}"  # This will be evaluated as "$date", "$posted_at", etc.
                        }
                    }
                    
                    pipeline = [
                        {"$match": trend_query},
                        {
                            "$group": {
                                "_id": date_expr,
                                "count": {"$sum": 1}
                            }
                        },
                        {"$sort": {"_id": 1}}
                    ]
                    result = await coll.aggregate(pipeline).to_list(None)
                    return {doc["_id"]: doc["count"] for doc in result if doc["_id"] is not None}
                except Exception as e:
                    logger.warning(f"Trend aggregation failed for {collection_name} with query {query} and date_field {date_field}: {e}")
                    import traceback
                    logger.warning(traceback.format_exc())
                    return {}

            # Execute aggregations
            github_trend = await get_daily_counts_with_query("github_commits", github_query, "date")
            slack_trend = await get_daily_counts_with_query("slack_messages", slack_query, "posted_at")
            notion_trend = await get_daily_counts_with_query("notion_pages", notion_query, "created_time")
            drive_trend = await get_daily_counts_with_query("drive_activities", drive_query, "timestamp")
            
            # Initialize map with 0s for all dates in range
            trend_map = {}
            current = start_date
            while current <= end_date:
                d = current.strftime("%Y-%m-%d")
                trend_map[d] = {
                    "date": d, 
                    "github": 0, 
                    "slack": 0, 
                    "notion": 0, 
                    "drive": 0
                }
                current += timedelta(days=1)
                
            # Fill data
            for date_str, count in github_trend.items():
                if date_str in trend_map: trend_map[date_str]["github"] = count
            for date_str, count in slack_trend.items():
                if date_str in trend_map: trend_map[date_str]["slack"] = count
            for date_str, count in notion_trend.items():
                if date_str in trend_map: trend_map[date_str]["notion"] = count
            for date_str, count in drive_trend.items():
                # Force drive count to 0 for charts due to noise
                if date_str in trend_map: trend_map[date_str]["drive"] = 0 
                
            daily_trends = sorted(trend_map.values(), key=lambda x: x["date"])
            activity_stats["daily_trends"] = daily_trends
            
        except Exception as e:
            logger.error(f"Failed to generate member daily trends: {e}")

        logger.info(f"Retrieved member detail: {member_name} ({member_id})")
        
        return {
            "id": member_id,
            "name": member.get("name"),
            "email": member.get("email"),
            "role": member.get("role"),
            "project": member.get("project"),
            "eoa_address": member.get("eoa_address"),
            "identifiers": identifiers,
            "activity_stats": activity_stats,
            "created_at": member.get("created_at"),
            "updated_at": member.get("updated_at")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching member detail: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch member detail: {str(e)}")


@router.get("/members/{member_id}/activities")
async def get_member_activities(
    member_id: str,
    request: Request,
    source_type: Optional[str] = None,
    activity_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    _admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    """
    Get activities for a specific member with detailed information
    
    Args:
        member_id: Member ID
        source_type: Filter by source (github, slack, notion, google_drive)
        activity_type: Filter by activity type
        start_date: Filter by start date (ISO format)
        end_date: Filter by end date (ISO format)
        limit: Maximum number of activities to return
        offset: Number of activities to skip
    
    Returns:
        List of member activities with detailed information
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
        
        member = await db["members"].find_one({"_id": member_obj_id})
        if not member:
            raise HTTPException(status_code=404, detail=f"Member with ID {member_id} not found")
        
        member_name = member.get("name")
        
        # Import helper functions from activities_mongo
        from backend.api.v1.activities_mongo import (
            load_member_mappings,
            get_identifiers_for_member,
            get_mapped_member_name
        )
        
        # Load member mappings for filtering
        member_mappings = await load_member_mappings(db)
        
        activities = []
        
        # Build date filter
        date_filter = {}
        if start_date:
            # Parse date string (format: yyyy-MM-dd) and set to start of day
            try:
                if 'T' in start_date or ' ' in start_date:
                    # Already has time component
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                else:
                    # Date only, set to start of day (00:00:00)
                    start_dt = datetime.fromisoformat(f"{start_date}T00:00:00")
                date_filter['$gte'] = start_dt
            except Exception as e:
                logger.warning(f"Failed to parse start_date {start_date}: {e}")
        
        if end_date:
            # Parse date string (format: yyyy-MM-dd) and set to end of day (23:59:59)
            try:
                if 'T' in end_date or ' ' in end_date:
                    # Already has time component
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                else:
                    # Date only, set to end of day (23:59:59.999999)
                    end_dt = datetime.fromisoformat(f"{end_date}T23:59:59.999999")
                date_filter['$lte'] = end_dt
            except Exception as e:
                logger.warning(f"Failed to parse end_date {end_date}: {e}")
        
        # Determine which sources to query (same logic as activities API)
        sources_to_query = [source_type] if source_type else ['github', 'slack', 'notion', 'drive']
        
        # When date filter is applied, fetch more data from each source to ensure we get all relevant activities
        # Then we'll sort and limit after combining all sources
        source_limit = limit * 10 if date_filter else limit
        
        for source in sources_to_query:
            if source == 'github':
                # GitHub commits
                if not activity_type or activity_type == 'commit':
                    commits = db["github_commits"]
                    query = {}
                    # Find identifiers for this member name
                    identifiers = get_identifiers_for_member(member_mappings, 'github', member_name)
                    if identifiers:
                        query['author_name'] = {'$in': identifiers}
                    else:
                        query['author_name'] = member_name
                    if date_filter:
                        query['date'] = date_filter
                    
                    async for commit in commits.find(query).sort("date", -1).limit(source_limit):
                        commit_date = commit.get('date')
                        if isinstance(commit_date, datetime):
                            timestamp_str = commit_date.isoformat() + 'Z' if commit_date.tzinfo is None else commit_date.isoformat()
                        else:
                            timestamp_str = str(commit_date) if commit_date else ''
                        
                        repo_name = commit.get('repository', '')
                        sha = commit.get('sha', '')
                        commit_url = commit.get('url') or (f"https://github.com/tokamak-network/{repo_name}/commit/{sha}" if repo_name and sha else None)
                        
                        activities.append({
                            "id": str(commit['_id']),
                            "source_type": "github",
                            "activity_type": "commit",
                            "timestamp": timestamp_str,
                            "metadata": {
                                "sha": sha,
                                "message": commit.get('message'),
                                "repository": repo_name,
                                "additions": commit.get('additions', 0),
                                "deletions": commit.get('deletions', 0),
                                "url": commit_url
                            }
                        })
                
                # GitHub PRs
                if not activity_type or activity_type == 'pull_request':
                    prs = db["github_pull_requests"]
                    query = {}
                    identifiers = get_identifiers_for_member(member_mappings, 'github', member_name)
                    if identifiers:
                        query['author'] = {'$in': identifiers}
                    else:
                        query['author'] = member_name
                    if date_filter:
                        query['created_at'] = date_filter
                    
                    async for pr in prs.find(query).sort("created_at", -1).limit(source_limit):
                        created_at = pr.get('created_at')
                        if isinstance(created_at, datetime):
                            timestamp_str = created_at.isoformat() + 'Z' if created_at.tzinfo is None else created_at.isoformat()
                        else:
                            timestamp_str = str(created_at) if created_at else ''
                        
                        activities.append({
                            "id": str(pr['_id']),
                            "source_type": "github",
                            "activity_type": "pull_request",
                            "timestamp": timestamp_str,
                            "metadata": {
                                "number": pr.get('number'),
                                "title": pr.get('title'),
                                "repository": pr.get('repository'),
                                "state": pr.get('state'),
                                "url": pr.get('url')
                            }
                        })
            
            elif source == 'slack':
                messages = db["slack_messages"]
                query = {}
                identifiers = get_identifiers_for_member(member_mappings, 'slack', member_name)
                or_conditions = []
                if identifiers:
                    or_conditions.append({'user_id': {'$in': identifiers}})
                    or_conditions.append({'user_email': {'$in': identifiers}})
                or_conditions.append({'user_name': {'$regex': f'^{member_name}$', '$options': 'i'}})
                query['$or'] = or_conditions
                if date_filter:
                    query['posted_at'] = date_filter
                
                async for msg in messages.find(query).sort("posted_at", -1).limit(source_limit):
                    posted_at = msg.get('posted_at')
                    if isinstance(posted_at, datetime):
                        timestamp_str = posted_at.isoformat() + 'Z' if posted_at.tzinfo is None else posted_at.isoformat()
                    else:
                        timestamp_str = str(posted_at) if posted_at else ''
                    
                    channel_id = msg.get('channel_id', '')
                    ts = msg.get('ts', '')
                    if channel_id and ts:
                        ts_formatted = ts.replace('.', '')
                        slack_url = f"https://tokamak-network.slack.com/archives/{channel_id}/p{ts_formatted}"
                    else:
                        slack_url = None
                    
                    activities.append({
                        "id": str(msg['_id']),
                        "source_type": "slack",
                        "activity_type": "message",
                        "timestamp": timestamp_str,
                        "metadata": {
                            "channel": msg.get('channel_name'),
                            "channel_id": channel_id,
                            "text": msg.get('text', '')[:500],
                            "url": slack_url
                        }
                    })
            
            elif source == 'notion':
                pages = db["notion_pages"]
                query = {}
                identifiers = get_identifiers_for_member(member_mappings, 'notion', member_name)
                or_conditions = []
                if identifiers:
                    or_conditions.append({'created_by.id': {'$in': identifiers}})
                    or_conditions.append({'created_by.email': {'$in': identifiers}})
                or_conditions.append({'created_by.name': {"$regex": f"^{member_name}", "$options": "i"}})
                query['$or'] = or_conditions
                if date_filter:
                    query['created_time'] = date_filter
                
                async for page in pages.find(query).sort("created_time", -1).limit(source_limit):
                    created_time = page.get('created_time')
                    if isinstance(created_time, datetime):
                        timestamp_str = created_time.isoformat() + 'Z' if created_time.tzinfo is None else created_time.isoformat()
                    else:
                        timestamp_str = str(created_time) if created_time else ''
                    
                    activities.append({
                        "id": str(page['_id']),
                        "source_type": "notion",
                        "activity_type": "page",
                        "timestamp": timestamp_str,
                        "metadata": {
                            "title": page.get('title'),
                            "url": page.get('url')
                        }
                    })
            
            elif source == 'drive' or source == 'google_drive':
                drive_activities = db["drive_activities"]
                query = {}
                identifiers = get_identifiers_for_member(member_mappings, 'drive', member_name)
                if identifiers:
                    query['user_email'] = {'$in': identifiers}
                else:
                    query['user_email'] = {"$regex": member_name, "$options": "i"}
                if date_filter:
                    query['timestamp'] = date_filter
                
                async for activity in drive_activities.find(query).sort("timestamp", -1).limit(source_limit):
                    timestamp_val = activity.get('timestamp')
                    if isinstance(timestamp_val, datetime):
                        timestamp_str = timestamp_val.isoformat() + 'Z' if timestamp_val.tzinfo is None else timestamp_val.isoformat()
                    else:
                        timestamp_str = str(timestamp_val) if timestamp_val else ''
                    
                    activities.append({
                        "id": str(activity['_id']),
                        "source_type": "google_drive",
                        "activity_type": "activity",
                        "timestamp": timestamp_str,
                        "metadata": {
                            "primary_action": activity.get('action'),
                            "target_name": activity.get('doc_title'),
                            "doc_type": activity.get('doc_type')
                        }
                    })
        
        # Sort all activities by timestamp descending
        def sort_key(activity):
            if not activity.get("timestamp"):
                return datetime.min
            try:
                ts = activity["timestamp"].replace('Z', '+00:00')
                return datetime.fromisoformat(ts)
            except:
                return datetime.min
        
        activities.sort(key=sort_key, reverse=True)
        
        # Apply offset and limit
        total = len(activities)
        activities = activities[offset:offset+limit]
        
        return {
            "member_id": member_id,
            "member_name": member_name,
            "total": total,
            "activities": activities
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching member activities: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch member activities: {str(e)}")


class SummaryRequest(BaseModel):
    """Request model for member summary generation"""
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@router.post("/members/{member_id}/summary")
async def generate_member_summary(
    member_id: str,
    request: Request,
    summary_request: Optional[SummaryRequest] = None,
    _admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    """
    Generate AI-powered summary of member activities using Gemini
    
    Args:
        member_id: Member ID
        summary_request: Optional request body with start_date and end_date
    
    Returns:
        AI-generated summary of member activities
    """
    try:
        import os
        import google.generativeai as genai
        
        # Extract dates from request
        start_date = summary_request.start_date if summary_request else None
        end_date = summary_request.end_date if summary_request else None
        
        # Get Gemini API key
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
        
        # Configure Gemini
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Get member activities
        mongo = get_mongo()
        db = mongo.async_db
        
        from bson import ObjectId
        try:
            member_obj_id = ObjectId(member_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid member ID format")
        
        member = await db["members"].find_one({"_id": member_obj_id})
        if not member:
            raise HTTPException(status_code=404, detail=f"Member with ID {member_id} not found")
        
        member_name = member.get("name")
        
        # Import helper functions from activities_mongo
        from backend.api.v1.activities_mongo import (
            load_member_mappings,
            get_identifiers_for_member
        )
        
        # Load member mappings for filtering
        member_mappings = await load_member_mappings(db)
        
        activities = []
        
        # Build date filter
        date_filter = {}
        if start_date:
            # Parse date string (format: yyyy-MM-dd) and set to start of day
            try:
                if 'T' in start_date or ' ' in start_date:
                    # Already has time component
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                else:
                    # Date only, set to start of day (00:00:00)
                    start_dt = datetime.fromisoformat(f"{start_date}T00:00:00")
                date_filter['$gte'] = start_dt
            except Exception as e:
                logger.warning(f"Failed to parse start_date {start_date}: {e}")
        
        if end_date:
            # Parse date string (format: yyyy-MM-dd) and set to end of day (23:59:59)
            try:
                if 'T' in end_date or ' ' in end_date:
                    # Already has time component
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                else:
                    # Date only, set to end of day (23:59:59.999999)
                    end_dt = datetime.fromisoformat(f"{end_date}T23:59:59.999999")
                date_filter['$lte'] = end_dt
            except Exception as e:
                logger.warning(f"Failed to parse end_date {end_date}: {e}")
        
        # Query all sources (limit to 100 total for summary)
        sources_to_query = ['github', 'slack', 'notion', 'drive']
        
        for source in sources_to_query:
            if source == 'github':
                # Commits
                commits = db["github_commits"]
                query = {}
                identifiers = get_identifiers_for_member(member_mappings, 'github', member_name)
                if identifiers:
                    query['author_name'] = {'$in': identifiers}
                else:
                    query['author_name'] = member_name
                if date_filter:
                    query['date'] = date_filter
                
                async for commit in commits.find(query).sort("date", -1).limit(30):
                    commit_date = commit.get('date')
                    if isinstance(commit_date, datetime):
                        timestamp_str = commit_date.isoformat() + 'Z' if commit_date.tzinfo is None else commit_date.isoformat()
                    else:
                        timestamp_str = str(commit_date) if commit_date else ''
                    
                    activities.append({
                        "id": str(commit['_id']),
                        "source_type": "github",
                        "activity_type": "commit",
                        "timestamp": timestamp_str,
                        "metadata": {
                            "message": commit.get('message'),
                            "repository": commit.get('repository'),
                            "additions": commit.get('additions', 0),
                            "deletions": commit.get('deletions', 0)
                        }
                    })
                
                # PRs
                prs = db["github_pull_requests"]
                query = {}
                identifiers = get_identifiers_for_member(member_mappings, 'github', member_name)
                if identifiers:
                    query['author'] = {'$in': identifiers}
                else:
                    query['author'] = member_name
                if date_filter:
                    query['created_at'] = date_filter
                
                async for pr in prs.find(query).sort("created_at", -1).limit(20):
                    created_at = pr.get('created_at')
                    if isinstance(created_at, datetime):
                        timestamp_str = created_at.isoformat() + 'Z' if created_at.tzinfo is None else created_at.isoformat()
                    else:
                        timestamp_str = str(created_at) if created_at else ''
                    
                    activities.append({
                        "id": str(pr['_id']),
                        "source_type": "github",
                        "activity_type": "pull_request",
                        "timestamp": timestamp_str,
                        "metadata": {
                            "number": pr.get('number'),
                            "title": pr.get('title'),
                            "repository": pr.get('repository'),
                            "state": pr.get('state')
                        }
                    })
            
            elif source == 'slack':
                messages = db["slack_messages"]
                query = {}
                identifiers = get_identifiers_for_member(member_mappings, 'slack', member_name)
                or_conditions = []
                if identifiers:
                    or_conditions.append({'user_id': {'$in': identifiers}})
                    or_conditions.append({'user_email': {'$in': identifiers}})
                or_conditions.append({'user_name': {'$regex': f'^{member_name}$', '$options': 'i'}})
                query['$or'] = or_conditions
                if date_filter:
                    query['posted_at'] = date_filter
                
                async for msg in messages.find(query).sort("posted_at", -1).limit(30):
                    posted_at = msg.get('posted_at')
                    if isinstance(posted_at, datetime):
                        timestamp_str = posted_at.isoformat() + 'Z' if posted_at.tzinfo is None else posted_at.isoformat()
                    else:
                        timestamp_str = str(posted_at) if posted_at else ''
                    
                    activities.append({
                        "id": str(msg['_id']),
                        "source_type": "slack",
                        "activity_type": "message",
                        "timestamp": timestamp_str,
                        "metadata": {
                            "text": msg.get('text', '')[:500],
                            "channel_name": msg.get('channel_name')
                        }
                    })
            
            elif source == 'notion':
                pages = db["notion_pages"]
                query = {}
                identifiers = get_identifiers_for_member(member_mappings, 'notion', member_name)
                or_conditions = []
                if identifiers:
                    or_conditions.append({'created_by.id': {'$in': identifiers}})
                    or_conditions.append({'created_by.email': {'$in': identifiers}})
                or_conditions.append({'created_by.name': {"$regex": f"^{member_name}", "$options": "i"}})
                query['$or'] = or_conditions
                if date_filter:
                    query['created_time'] = date_filter
                
                async for page in pages.find(query).sort("created_time", -1).limit(20):
                    created_time = page.get('created_time')
                    if isinstance(created_time, datetime):
                        timestamp_str = created_time.isoformat() + 'Z' if created_time.tzinfo is None else created_time.isoformat()
                    else:
                        timestamp_str = str(created_time) if created_time else ''
                    
                    activities.append({
                        "id": str(page['_id']),
                        "source_type": "notion",
                        "activity_type": "page",
                        "timestamp": timestamp_str,
                        "metadata": {
                            "title": page.get('title')
                        }
                    })
            
            elif source == 'drive':
                drive_activities = db["drive_activities"]
                query = {}
                identifiers = get_identifiers_for_member(member_mappings, 'drive', member_name)
                if identifiers:
                    query['user_email'] = {'$in': identifiers}
                else:
                    query['user_email'] = {"$regex": member_name, "$options": "i"}
                if date_filter:
                    query['timestamp'] = date_filter
                
                async for activity in drive_activities.find(query).sort("timestamp", -1).limit(20):
                    timestamp_val = activity.get('timestamp')
                    if isinstance(timestamp_val, datetime):
                        timestamp_str = timestamp_val.isoformat() + 'Z' if timestamp_val.tzinfo is None else timestamp_val.isoformat()
                    else:
                        timestamp_str = str(timestamp_val) if timestamp_val else ''
                    
                    activities.append({
                        "id": str(activity['_id']),
                        "source_type": "google_drive",
                        "activity_type": "activity",
                        "timestamp": timestamp_str,
                        "metadata": {
                            "primary_action": activity.get('action'),
                            "target_name": activity.get('doc_title')
                        }
                    })
        
        # Sort all activities by timestamp descending
        def sort_key(activity):
            if not activity.get("timestamp"):
                return datetime.min
            try:
                ts = activity["timestamp"].replace('Z', '+00:00')
                return datetime.fromisoformat(ts)
            except:
                return datetime.min
        
        activities.sort(key=sort_key, reverse=True)
        activities = activities[:100]  # Limit to 100 for summary
        
        if not activities:
            return {
                "member_id": member_id,
                "member_name": member_name,
                "summary": f"{member_name} has no activities in the specified period.",
                "period": {
                    "start": start_date,
                    "end": end_date
                }
            }
        
        # Format activities for AI prompt
        activities_text = []
        by_source = {}
        
        for activity in activities:
            source = activity.get("source_type", "unknown")
            activity_type = activity.get("activity_type", "unknown")
            timestamp = activity.get("timestamp", "")
            metadata = activity.get("metadata", {})
            
            if source not in by_source:
                by_source[source] = []
            
            activity_desc = f"- {activity_type} at {timestamp}"
            if source == "github":
                if activity_type == "commit":
                    activity_desc += f": {metadata.get('message', '')[:100]} in {metadata.get('repository', '')} (+{metadata.get('additions', 0)}/-{metadata.get('deletions', 0)} lines)"
                elif activity_type == "pull_request":
                    activity_desc += f": PR #{metadata.get('number', '')} - {metadata.get('title', '')[:100]} in {metadata.get('repository', '')} ({metadata.get('state', '')})"
                elif activity_type == "issue":
                    activity_desc += f": Issue #{metadata.get('number', '')} - {metadata.get('title', '')[:100]} in {metadata.get('repository', '')} ({metadata.get('state', '')})"
            elif source == "slack":
                activity_desc += f": {metadata.get('text', '')[:100]} in {metadata.get('channel_name', '')}"
            elif source == "notion":
                activity_desc += f": {metadata.get('title', '')[:100]}"
            elif source == "google_drive":
                activity_desc += f": {metadata.get('primary_action', '')} on {metadata.get('target_name', '')}"
            
            by_source[source].append(activity_desc)
        
        # Build prompt
        prompt = f"""Analyze the following activities for team member {member_name} and provide a comprehensive summary.

## Activities by Source

"""
        for source, source_activities in by_source.items():
            prompt += f"### {source.upper()}\n"
            prompt += "\n".join(source_activities[:20])  # Limit to 20 per source
            prompt += "\n\n"
        
        prompt += f"""
## Analysis Request

Please provide:
1. **Overall Activity Assessment**: Evaluate the member's overall activity level and engagement
2. **Work Patterns**: Identify patterns in their work (e.g., focus areas, collaboration style)
3. **Key Contributions**: Highlight significant contributions or achievements
4. **Activity Distribution**: Analyze how activities are distributed across different sources
5. **Trends and Insights**: Identify any trends or notable patterns in their work

Provide a clear, concise summary in English that would be useful for performance review or team insights.
"""
        
        # Generate summary using Gemini
        try:
            response = model.generate_content(prompt)
            summary = response.text
        except Exception as e:
            logger.error(f"Error generating Gemini summary: {e}")
            summary = f"Error generating summary: {str(e)}"
        
        return {
            "member_id": member_id,
            "member_name": member_name,
            "summary": summary,
            "period": {
                "start": start_date,
                "end": end_date
            },
            "activity_count": len(activities),
            "sources": list(by_source.keys())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating member summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")


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
        
        # Clear member mapping cache to ensure fresh data after deletion
        from backend.api.v1.activities_mongo import clear_member_mapping_cache
        clear_member_mapping_cache()
        
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
