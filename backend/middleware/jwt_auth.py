"""
JWT Authentication Middleware for All-Thing-Eye

Provides JWT token generation, verification, and Ethereum signature validation.
Supports multi-tenant authentication with tenant context.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import Depends, HTTPException, status, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from eth_account.messages import encode_defunct
from eth_account import Account
import os

from src.utils.logger import get_logger

logger = get_logger(__name__)

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour

# Security scheme
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


def get_admin_addresses() -> List[str]:
    """
    Get list of admin wallet addresses from environment variable
    
    Returns:
        List of admin addresses (lowercase)
    """
    admin_env = os.getenv("ADMIN_ADDRESSES", "")
    if not admin_env:
        logger.warning("⚠️ No ADMIN_ADDRESSES found in environment")
        return []
    
    # Split by comma and normalize to lowercase
    addresses = [addr.strip().lower() for addr in admin_env.split(",") if addr.strip()]
    return addresses


def verify_ethereum_signature(message: str, signature: str, address: str) -> bool:
    """
    Verify Ethereum signature
    
    Args:
        message: Original message that was signed
        signature: Signature hex string
        address: Expected signer address
        
    Returns:
        True if signature is valid, False otherwise
    """
    try:
        # Encode message
        encoded_message = encode_defunct(text=message)
        
        # Recover address from signature
        recovered_address = Account.recover_message(encoded_message, signature=signature)
        
        # Compare addresses (case-insensitive)
        is_valid = recovered_address.lower() == address.lower()
        
        if is_valid:
            logger.info(f"✅ Valid signature from {address}")
        else:
            logger.warning(f"❌ Invalid signature for {address} (recovered: {recovered_address})")
        
        return is_valid
        
    except Exception as e:
        logger.error(f"❌ Signature verification failed: {e}")
        return False


def is_admin(address: str) -> bool:
    """
    Check if address is in admin list
    
    Args:
        address: Wallet address to check
        
    Returns:
        True if address is admin, False otherwise
    """
    admin_addresses = get_admin_addresses()
    is_admin_user = address.lower() in admin_addresses
    
    if is_admin_user:
        logger.info(f"✅ Admin access granted for {address}")
    else:
        logger.warning(f"❌ Admin access denied for {address}")
    
    return is_admin_user


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    tenant_id: Optional[str] = None,
    tenant_slug: Optional[str] = None,
    role: Optional[str] = None,
    permissions: Optional[List[str]] = None
) -> str:
    """
    Create JWT access token with optional tenant context

    Args:
        data: Data to encode in token
        expires_delta: Token expiration time (default: 1 hour)
        tenant_id: Tenant ID for multi-tenant support
        tenant_slug: Tenant slug for multi-tenant support
        role: User role within the tenant
        permissions: List of permissions for the user

    Returns:
        JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})

    # Add tenant context if provided
    if tenant_id:
        to_encode["tenant_id"] = tenant_id
    if tenant_slug:
        to_encode["tenant_slug"] = tenant_slug
    if role:
        to_encode["role"] = role
    if permissions:
        to_encode["permissions"] = permissions

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    logger.info(f"🔑 JWT token created for {data.get('sub')} (expires: {expire})")

    return encoded_jwt


def verify_token(token: str) -> dict:
    """
    Verify and decode JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        address: str = payload.get("sub")
        
        if address is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return payload
        
    except JWTError as e:
        logger.error(f"❌ JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    Dependency to get current authenticated user from JWT token
    
    Args:
        credentials: HTTP Authorization credentials
        
    Returns:
        User's wallet address
        
    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials
    payload = verify_token(token)
    address = payload.get("sub")
    
    if not address:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    
    return address


async def require_admin(
    address: str = Depends(get_current_user)
) -> str:
    """
    Dependency to require admin privileges
    
    Args:
        address: User's wallet address from JWT token
        
    Returns:
        User's wallet address
        
    Raises:
        HTTPException: If user is not admin
    """
    if not is_admin(address):
        logger.warning(f"⛔ Unauthorized admin access attempt from {address}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    
    return address


# Optional: API Key fallback for backwards compatibility
async def verify_api_key_or_jwt(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
) -> str:
    """
    Verify either JWT token or API key (for backwards compatibility)

    Args:
        authorization: Bearer token from Authorization header
        x_api_key: API key from X-API-Key header

    Returns:
        User identifier

    Raises:
        HTTPException: If authentication fails
    """
    # Try JWT first
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        try:
            payload = verify_token(token)
            return payload.get("sub")
        except HTTPException:
            pass

    # Fall back to API key
    if x_api_key:
        api_key = os.getenv("API_SECRET_KEY")
        if api_key and x_api_key == api_key:
            return "api_key_user"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


# =============================================================================
# Multi-Tenant Authentication
# =============================================================================

async def get_current_user_with_tenant(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(optional_security)
) -> Optional[dict]:
    """
    Get current user with tenant context from JWT token.

    Returns None if no valid token (allows optional auth).
    For required auth, use require_tenant_auth dependency.

    Returns:
        Dict with user info and tenant context, or None
    """
    if credentials is None:
        return None

    token = credentials.credentials
    try:
        payload = verify_token(token)
        return {
            "address": payload.get("sub"),
            "tenant_id": payload.get("tenant_id"),
            "tenant_slug": payload.get("tenant_slug"),
            "role": payload.get("role"),
            "permissions": payload.get("permissions", []),
        }
    except HTTPException:
        return None


async def require_tenant_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Require authentication with tenant context.

    Raises HTTPException if:
    - No valid JWT token
    - Token has no tenant context

    Returns:
        Dict with user info and tenant context
    """
    token = credentials.credentials
    payload = verify_token(token)

    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant context required. Please select a tenant.",
        )

    return {
        "address": payload.get("sub"),
        "tenant_id": tenant_id,
        "tenant_slug": payload.get("tenant_slug"),
        "role": payload.get("role"),
        "permissions": payload.get("permissions", []),
    }


async def inject_tenant_context(request: Request, db):
    """
    Middleware helper to inject tenant context into request state.

    Call this in endpoint handlers or middleware to set up tenant context.
    """
    from backend.middleware.tenant import TenantContext

    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return

    token = auth_header.replace("Bearer ", "")
    try:
        payload = verify_token(token)
        tenant_id = payload.get("tenant_id")

        if tenant_id:
            # Fetch tenant details from database
            tenant = await db["tenants"].find_one({"_id": ObjectId(tenant_id)})
            if tenant:
                request.state.tenant_context = TenantContext(
                    tenant_id=str(tenant["_id"]),
                    tenant_slug=tenant["slug"],
                    tenant_name=tenant["name"],
                    user_wallet=payload.get("sub"),
                    user_role=payload.get("role", "viewer"),
                    permissions=payload.get("permissions", []),
                )
    except (HTTPException, Exception) as e:
        logger.debug(f"Failed to inject tenant context: {e}")


# Import ObjectId for inject_tenant_context
from bson import ObjectId

