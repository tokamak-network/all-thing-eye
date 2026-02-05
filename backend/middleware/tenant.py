"""
Multi-Tenant Middleware for All-Thing-Eye

Provides tenant context injection and data isolation for multi-tenant support.
"""

from typing import Optional
from fastapi import Request, HTTPException, status, Depends
from bson import ObjectId

from src.utils.logger import get_logger

logger = get_logger(__name__)


class TenantContext:
    """
    Tenant context object containing current tenant information.

    This is injected into requests for tenant-aware data access.
    """

    def __init__(
        self,
        tenant_id: str,
        tenant_slug: str,
        tenant_name: str,
        user_wallet: str,
        user_role: str,
        permissions: list[str]
    ):
        self.tenant_id = tenant_id
        self.tenant_slug = tenant_slug
        self.tenant_name = tenant_name
        self.user_wallet = user_wallet
        self.user_role = user_role
        self.permissions = permissions

    def has_permission(self, permission: str) -> bool:
        """Check if the current user has a specific permission."""
        # Admin has all permissions
        if "tenant:manage" in self.permissions:
            return True
        return permission in self.permissions

    def require_permission(self, permission: str) -> None:
        """Raise HTTPException if user lacks permission."""
        if not self.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission} required"
            )

    def get_tenant_filter(self) -> dict:
        """Get MongoDB filter for tenant isolation."""
        return {"tenant_id": ObjectId(self.tenant_id)}


async def get_tenant_context(request: Request) -> Optional[TenantContext]:
    """
    Dependency to get current tenant context from request.

    The tenant context is set by the tenant middleware based on:
    1. JWT token containing tenant_id
    2. X-Tenant-ID header (for API key auth)
    3. Subdomain (e.g., acme.allthings.eye)

    Returns:
        TenantContext if authenticated with tenant, None otherwise
    """
    return getattr(request.state, "tenant_context", None)


async def require_tenant_context(
    tenant_context: Optional[TenantContext] = Depends(get_tenant_context)
) -> TenantContext:
    """
    Dependency to require tenant context.

    Raises HTTPException if no tenant context is available.
    """
    if tenant_context is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant context required"
        )
    return tenant_context


def require_permission(permission: str):
    """
    Dependency factory to require a specific permission.

    Usage:
        @router.get("/members")
        async def list_members(
            tenant: TenantContext = Depends(require_permission("members:read"))
        ):
            ...
    """
    async def permission_checker(
        tenant_context: TenantContext = Depends(require_tenant_context)
    ) -> TenantContext:
        tenant_context.require_permission(permission)
        return tenant_context

    return permission_checker


# Default roles with their permissions
DEFAULT_ROLES = {
    "owner": {
        "name": "Owner",
        "permissions": [
            "tenant:manage",
            "members:read", "members:write", "members:delete",
            "projects:read", "projects:write", "projects:delete",
            "activities:read", "activities:export",
            "settings:read", "settings:write",
            "roles:read", "roles:write", "roles:delete",
            "users:read", "users:write", "users:delete",
        ],
        "is_system_role": True,
    },
    "admin": {
        "name": "Admin",
        "permissions": [
            "members:read", "members:write", "members:delete",
            "projects:read", "projects:write", "projects:delete",
            "activities:read", "activities:export",
            "settings:read", "settings:write",
            "users:read", "users:write",
        ],
        "is_system_role": True,
    },
    "manager": {
        "name": "Manager",
        "permissions": [
            "members:read", "members:write",
            "projects:read", "projects:write",
            "activities:read", "activities:export",
        ],
        "is_system_role": True,
    },
    "viewer": {
        "name": "Viewer",
        "permissions": [
            "members:read",
            "projects:read",
            "activities:read",
        ],
        "is_system_role": True,
    },
}


async def create_default_roles(db, tenant_id: str) -> dict:
    """
    Create default roles for a new tenant.

    Returns:
        Dict mapping role names to their IDs
    """
    roles_collection = db["user_roles"]
    role_ids = {}

    for role_key, role_data in DEFAULT_ROLES.items():
        role_doc = {
            "tenant_id": ObjectId(tenant_id),
            "name": role_data["name"],
            "permissions": role_data["permissions"],
            "is_system_role": role_data["is_system_role"],
        }

        result = await roles_collection.insert_one(role_doc)
        role_ids[role_key] = str(result.inserted_id)
        logger.info(f"Created default role '{role_key}' for tenant {tenant_id}")

    return role_ids
