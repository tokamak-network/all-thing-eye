"""
Multi-Tenant Management API Endpoints

Provides tenant CRUD operations, user management, and role-based access control.
"""

from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, Field
from bson import ObjectId

from backend.middleware.jwt_auth import (
    get_current_user,
    require_admin,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from backend.middleware.tenant import (
    TenantContext,
    require_tenant_context,
    require_permission,
    create_default_roles,
    DEFAULT_ROLES,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class TenantBrandingRequest(BaseModel):
    """Tenant branding configuration"""
    primary_color: Optional[str] = "#3B82F6"
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    custom_css: Optional[str] = None


class TenantSettingsRequest(BaseModel):
    """Tenant settings configuration"""
    timezone: str = "UTC"
    date_format: str = "YYYY-MM-DD"
    language: str = "en"
    features_enabled: List[str] = Field(default_factory=lambda: [
        "github", "slack", "notion", "google_drive"
    ])


class CreateTenantRequest(BaseModel):
    """Request to create a new tenant"""
    slug: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-z0-9-]+$")
    name: str = Field(..., min_length=1, max_length=100)
    branding: Optional[TenantBrandingRequest] = None
    settings: Optional[TenantSettingsRequest] = None
    github_org: Optional[str] = None
    slack_workspace_id: Optional[str] = None
    notion_workspace_id: Optional[str] = None
    google_drive_folder_id: Optional[str] = None


class UpdateTenantRequest(BaseModel):
    """Request to update a tenant"""
    name: Optional[str] = None
    branding: Optional[TenantBrandingRequest] = None
    settings: Optional[TenantSettingsRequest] = None
    github_org: Optional[str] = None
    slack_workspace_id: Optional[str] = None
    notion_workspace_id: Optional[str] = None
    google_drive_folder_id: Optional[str] = None
    is_active: Optional[bool] = None


class InviteUserRequest(BaseModel):
    """Request to invite a user to a tenant"""
    wallet_address: str
    role: str = "viewer"  # owner, admin, manager, viewer
    email: Optional[str] = None
    display_name: Optional[str] = None


class UpdateUserRoleRequest(BaseModel):
    """Request to update a user's role"""
    role: str


class TenantResponse(BaseModel):
    """Tenant response"""
    id: str
    slug: str
    name: str
    branding: dict
    settings: dict
    plan: str
    max_members: int
    max_projects: int
    github_org: Optional[str]
    slack_workspace_id: Optional[str]
    notion_workspace_id: Optional[str]
    google_drive_folder_id: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TenantUserResponse(BaseModel):
    """Tenant user response"""
    id: str
    tenant_id: str
    wallet_address: str
    email: Optional[str]
    display_name: Optional[str]
    role_id: str
    role_name: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]


class SwitchTenantResponse(BaseModel):
    """Response after switching tenant context"""
    access_token: str
    token_type: str
    expires_in: int
    tenant_id: str
    tenant_slug: str
    tenant_name: str
    role: str
    permissions: List[str]


# =============================================================================
# Tenant CRUD Endpoints
# =============================================================================

@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: Request,
    body: CreateTenantRequest,
    current_user: str = Depends(get_current_user),
):
    """
    Create a new tenant.

    The creating user becomes the tenant owner automatically.
    """
    db = request.app.state.mongo_manager.async_db

    # Check if slug is already taken
    existing = await db["tenants"].find_one({"slug": body.slug})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenant slug '{body.slug}' is already taken"
        )

    # Create tenant document
    tenant_doc = {
        "slug": body.slug,
        "name": body.name,
        "branding": (body.branding.model_dump() if body.branding
                     else {"primary_color": "#3B82F6"}),
        "settings": (body.settings.model_dump() if body.settings
                     else {"timezone": "UTC", "date_format": "YYYY-MM-DD",
                           "language": "en",
                           "features_enabled": ["github", "slack", "notion", "google_drive"]}),
        "plan": "free",
        "max_members": 10,
        "max_projects": 5,
        "github_org": body.github_org,
        "slack_workspace_id": body.slack_workspace_id,
        "notion_workspace_id": body.notion_workspace_id,
        "google_drive_folder_id": body.google_drive_folder_id,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    result = await db["tenants"].insert_one(tenant_doc)
    tenant_id = str(result.inserted_id)

    logger.info(f"Created tenant '{body.slug}' (ID: {tenant_id})")

    # Create default roles for the tenant
    role_ids = await create_default_roles(db, tenant_id)

    # Add creating user as owner
    owner_user_doc = {
        "tenant_id": ObjectId(tenant_id),
        "wallet_address": current_user.lower(),
        "email": None,
        "display_name": None,
        "role_id": ObjectId(role_ids["owner"]),
        "role_name": "Owner",
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "last_login_at": None,
    }
    await db["tenant_users"].insert_one(owner_user_doc)

    logger.info(f"Added {current_user} as owner of tenant '{body.slug}'")

    # Return created tenant
    tenant_doc["id"] = tenant_id
    return TenantResponse(**tenant_doc)


@router.get("/", response_model=List[TenantResponse])
async def list_my_tenants(
    request: Request,
    current_user: str = Depends(get_current_user),
):
    """
    List all tenants the current user belongs to.
    """
    db = request.app.state.mongo_manager.async_db

    # Find all tenant memberships for this user
    memberships = await db["tenant_users"].find({
        "wallet_address": current_user.lower(),
        "is_active": True,
    }).to_list(100)

    tenant_ids = [m["tenant_id"] for m in memberships]

    # Fetch tenant details
    tenants = await db["tenants"].find({
        "_id": {"$in": tenant_ids},
        "is_active": True,
    }).to_list(100)

    return [
        TenantResponse(
            id=str(t["_id"]),
            slug=t["slug"],
            name=t["name"],
            branding=t.get("branding", {}),
            settings=t.get("settings", {}),
            plan=t.get("plan", "free"),
            max_members=t.get("max_members", 10),
            max_projects=t.get("max_projects", 5),
            github_org=t.get("github_org"),
            slack_workspace_id=t.get("slack_workspace_id"),
            notion_workspace_id=t.get("notion_workspace_id"),
            google_drive_folder_id=t.get("google_drive_folder_id"),
            is_active=t.get("is_active", True),
            created_at=t.get("created_at", datetime.utcnow()),
            updated_at=t.get("updated_at", datetime.utcnow()),
        )
        for t in tenants
    ]


@router.get("/{tenant_slug}", response_model=TenantResponse)
async def get_tenant(
    request: Request,
    tenant_slug: str,
    current_user: str = Depends(get_current_user),
):
    """
    Get tenant details by slug.

    User must be a member of the tenant.
    """
    db = request.app.state.mongo_manager.async_db

    # Find tenant
    tenant = await db["tenants"].find_one({"slug": tenant_slug})
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_slug}' not found"
        )

    # Check membership
    membership = await db["tenant_users"].find_one({
        "tenant_id": tenant["_id"],
        "wallet_address": current_user.lower(),
        "is_active": True,
    })
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this tenant"
        )

    return TenantResponse(
        id=str(tenant["_id"]),
        slug=tenant["slug"],
        name=tenant["name"],
        branding=tenant.get("branding", {}),
        settings=tenant.get("settings", {}),
        plan=tenant.get("plan", "free"),
        max_members=tenant.get("max_members", 10),
        max_projects=tenant.get("max_projects", 5),
        github_org=tenant.get("github_org"),
        slack_workspace_id=tenant.get("slack_workspace_id"),
        notion_workspace_id=tenant.get("notion_workspace_id"),
        google_drive_folder_id=tenant.get("google_drive_folder_id"),
        is_active=tenant.get("is_active", True),
        created_at=tenant.get("created_at", datetime.utcnow()),
        updated_at=tenant.get("updated_at", datetime.utcnow()),
    )


@router.patch("/{tenant_slug}", response_model=TenantResponse)
async def update_tenant(
    request: Request,
    tenant_slug: str,
    body: UpdateTenantRequest,
    tenant: TenantContext = Depends(require_permission("settings:write")),
):
    """
    Update tenant settings.

    Requires 'settings:write' permission.
    """
    db = request.app.state.mongo_manager.async_db

    # Build update document
    update_doc = {"updated_at": datetime.utcnow()}
    if body.name is not None:
        update_doc["name"] = body.name
    if body.branding is not None:
        update_doc["branding"] = body.branding.model_dump()
    if body.settings is not None:
        update_doc["settings"] = body.settings.model_dump()
    if body.github_org is not None:
        update_doc["github_org"] = body.github_org
    if body.slack_workspace_id is not None:
        update_doc["slack_workspace_id"] = body.slack_workspace_id
    if body.notion_workspace_id is not None:
        update_doc["notion_workspace_id"] = body.notion_workspace_id
    if body.google_drive_folder_id is not None:
        update_doc["google_drive_folder_id"] = body.google_drive_folder_id
    if body.is_active is not None:
        update_doc["is_active"] = body.is_active

    result = await db["tenants"].find_one_and_update(
        {"slug": tenant_slug},
        {"$set": update_doc},
        return_document=True,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_slug}' not found"
        )

    logger.info(f"Updated tenant '{tenant_slug}'")

    return TenantResponse(
        id=str(result["_id"]),
        slug=result["slug"],
        name=result["name"],
        branding=result.get("branding", {}),
        settings=result.get("settings", {}),
        plan=result.get("plan", "free"),
        max_members=result.get("max_members", 10),
        max_projects=result.get("max_projects", 5),
        github_org=result.get("github_org"),
        slack_workspace_id=result.get("slack_workspace_id"),
        notion_workspace_id=result.get("notion_workspace_id"),
        google_drive_folder_id=result.get("google_drive_folder_id"),
        is_active=result.get("is_active", True),
        created_at=result.get("created_at", datetime.utcnow()),
        updated_at=result.get("updated_at", datetime.utcnow()),
    )


# =============================================================================
# Tenant User Management
# =============================================================================

@router.get("/{tenant_slug}/users", response_model=List[TenantUserResponse])
async def list_tenant_users(
    request: Request,
    tenant_slug: str,
    tenant: TenantContext = Depends(require_permission("users:read")),
):
    """
    List all users in a tenant.

    Requires 'users:read' permission.
    """
    db = request.app.state.mongo_manager.async_db

    # Get tenant ID
    tenant_doc = await db["tenants"].find_one({"slug": tenant_slug})
    if not tenant_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_slug}' not found"
        )

    # Get all users
    users = await db["tenant_users"].find({
        "tenant_id": tenant_doc["_id"],
    }).to_list(1000)

    return [
        TenantUserResponse(
            id=str(u["_id"]),
            tenant_id=str(u["tenant_id"]),
            wallet_address=u["wallet_address"],
            email=u.get("email"),
            display_name=u.get("display_name"),
            role_id=str(u["role_id"]),
            role_name=u["role_name"],
            is_active=u.get("is_active", True),
            created_at=u.get("created_at", datetime.utcnow()),
            last_login_at=u.get("last_login_at"),
        )
        for u in users
    ]


@router.post("/{tenant_slug}/users", response_model=TenantUserResponse,
             status_code=status.HTTP_201_CREATED)
async def invite_user(
    request: Request,
    tenant_slug: str,
    body: InviteUserRequest,
    tenant: TenantContext = Depends(require_permission("users:write")),
):
    """
    Invite a user to a tenant.

    Requires 'users:write' permission.
    """
    db = request.app.state.mongo_manager.async_db

    # Get tenant
    tenant_doc = await db["tenants"].find_one({"slug": tenant_slug})
    if not tenant_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_slug}' not found"
        )

    # Check if user already exists
    existing = await db["tenant_users"].find_one({
        "tenant_id": tenant_doc["_id"],
        "wallet_address": body.wallet_address.lower(),
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this tenant"
        )

    # Check member limit
    user_count = await db["tenant_users"].count_documents({
        "tenant_id": tenant_doc["_id"],
        "is_active": True,
    })
    if user_count >= tenant_doc.get("max_members", 10):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenant has reached maximum member limit ({tenant_doc.get('max_members', 10)})"
        )

    # Get role
    if body.role not in DEFAULT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {body.role}. Valid roles: {list(DEFAULT_ROLES.keys())}"
        )

    role_doc = await db["user_roles"].find_one({
        "tenant_id": tenant_doc["_id"],
        "name": DEFAULT_ROLES[body.role]["name"],
    })

    if not role_doc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Role not found. Please contact support."
        )

    # Create user
    user_doc = {
        "tenant_id": tenant_doc["_id"],
        "wallet_address": body.wallet_address.lower(),
        "email": body.email,
        "display_name": body.display_name,
        "role_id": role_doc["_id"],
        "role_name": role_doc["name"],
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "last_login_at": None,
    }

    result = await db["tenant_users"].insert_one(user_doc)

    logger.info(f"Invited {body.wallet_address} to tenant '{tenant_slug}' as {body.role}")

    return TenantUserResponse(
        id=str(result.inserted_id),
        tenant_id=str(tenant_doc["_id"]),
        wallet_address=body.wallet_address.lower(),
        email=body.email,
        display_name=body.display_name,
        role_id=str(role_doc["_id"]),
        role_name=role_doc["name"],
        is_active=True,
        created_at=datetime.utcnow(),
        last_login_at=None,
    )


@router.patch("/{tenant_slug}/users/{wallet_address}", response_model=TenantUserResponse)
async def update_user_role(
    request: Request,
    tenant_slug: str,
    wallet_address: str,
    body: UpdateUserRoleRequest,
    tenant: TenantContext = Depends(require_permission("users:write")),
):
    """
    Update a user's role in a tenant.

    Requires 'users:write' permission.
    """
    db = request.app.state.mongo_manager.async_db

    # Get tenant
    tenant_doc = await db["tenants"].find_one({"slug": tenant_slug})
    if not tenant_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_slug}' not found"
        )

    # Get role
    if body.role not in DEFAULT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {body.role}. Valid roles: {list(DEFAULT_ROLES.keys())}"
        )

    role_doc = await db["user_roles"].find_one({
        "tenant_id": tenant_doc["_id"],
        "name": DEFAULT_ROLES[body.role]["name"],
    })

    if not role_doc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Role not found"
        )

    # Update user
    result = await db["tenant_users"].find_one_and_update(
        {
            "tenant_id": tenant_doc["_id"],
            "wallet_address": wallet_address.lower(),
        },
        {
            "$set": {
                "role_id": role_doc["_id"],
                "role_name": role_doc["name"],
                "updated_at": datetime.utcnow(),
            }
        },
        return_document=True,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in this tenant"
        )

    logger.info(f"Updated role of {wallet_address} in '{tenant_slug}' to {body.role}")

    return TenantUserResponse(
        id=str(result["_id"]),
        tenant_id=str(result["tenant_id"]),
        wallet_address=result["wallet_address"],
        email=result.get("email"),
        display_name=result.get("display_name"),
        role_id=str(result["role_id"]),
        role_name=result["role_name"],
        is_active=result.get("is_active", True),
        created_at=result.get("created_at", datetime.utcnow()),
        last_login_at=result.get("last_login_at"),
    )


@router.delete("/{tenant_slug}/users/{wallet_address}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(
    request: Request,
    tenant_slug: str,
    wallet_address: str,
    tenant: TenantContext = Depends(require_permission("users:delete")),
):
    """
    Remove a user from a tenant.

    Requires 'users:delete' permission.
    """
    db = request.app.state.mongo_manager.async_db

    # Get tenant
    tenant_doc = await db["tenants"].find_one({"slug": tenant_slug})
    if not tenant_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_slug}' not found"
        )

    # Cannot remove yourself
    if wallet_address.lower() == tenant.user_wallet.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove yourself from the tenant"
        )

    # Soft delete (deactivate)
    result = await db["tenant_users"].update_one(
        {
            "tenant_id": tenant_doc["_id"],
            "wallet_address": wallet_address.lower(),
        },
        {
            "$set": {
                "is_active": False,
                "updated_at": datetime.utcnow(),
            }
        },
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in this tenant"
        )

    logger.info(f"Removed {wallet_address} from tenant '{tenant_slug}'")


# =============================================================================
# Tenant Context Switching
# =============================================================================

@router.post("/{tenant_slug}/switch", response_model=SwitchTenantResponse)
async def switch_tenant(
    request: Request,
    tenant_slug: str,
    current_user: str = Depends(get_current_user),
):
    """
    Switch to a different tenant context.

    Returns a new JWT token with the tenant context.
    """
    db = request.app.state.mongo_manager.async_db

    # Find tenant
    tenant = await db["tenants"].find_one({"slug": tenant_slug, "is_active": True})
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_slug}' not found or inactive"
        )

    # Check membership
    membership = await db["tenant_users"].find_one({
        "tenant_id": tenant["_id"],
        "wallet_address": current_user.lower(),
        "is_active": True,
    })
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this tenant"
        )

    # Get role permissions
    role = await db["user_roles"].find_one({"_id": membership["role_id"]})
    permissions = role.get("permissions", []) if role else []

    # Update last login
    await db["tenant_users"].update_one(
        {"_id": membership["_id"]},
        {"$set": {"last_login_at": datetime.utcnow()}}
    )

    # Create new token with tenant context
    access_token = create_access_token(
        data={"sub": current_user.lower()},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        tenant_id=str(tenant["_id"]),
        tenant_slug=tenant["slug"],
        role=membership["role_name"],
        permissions=permissions,
    )

    logger.info(f"User {current_user} switched to tenant '{tenant_slug}'")

    return SwitchTenantResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        tenant_id=str(tenant["_id"]),
        tenant_slug=tenant["slug"],
        tenant_name=tenant["name"],
        role=membership["role_name"],
        permissions=permissions,
    )
