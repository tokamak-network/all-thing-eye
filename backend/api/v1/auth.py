"""
Authentication API Endpoints

Handles wallet signature verification and JWT token issuance.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from datetime import timedelta

from backend.middleware.jwt_auth import (
    verify_ethereum_signature,
    is_admin,
    create_access_token,
    get_admin_addresses,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    require_admin
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request with wallet signature"""
    address: str
    message: str
    signature: str


class LoginResponse(BaseModel):
    """Login response with JWT token"""
    access_token: str
    token_type: str
    expires_in: int
    address: str
    is_admin: bool


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Authenticate user with Ethereum wallet signature and issue JWT token
    
    Process:
    1. Verify Ethereum signature
    2. Check if user is admin
    3. Generate JWT token
    
    Args:
        request: Login request containing address, message, and signature
        
    Returns:
        JWT access token and user info
        
    Raises:
        HTTPException: If signature is invalid or user is not admin
    """
    logger.info(f"🔐 Login attempt from {request.address}")
    
    # Verify signature
    if not verify_ethereum_signature(request.message, request.signature, request.address):
        logger.warning(f"❌ Invalid signature for {request.address}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )
    
    # Check admin status
    if not is_admin(request.address):
        logger.warning(f"⛔ Non-admin login attempt from {request.address}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    # Create JWT token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": request.address.lower()},
        expires_delta=access_token_expires
    )
    
    logger.info(f"✅ Login successful for admin {request.address}")
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # seconds
        address=request.address.lower(),
        is_admin=True
    )


@router.post("/verify")
async def verify_token(token: str):
    """
    Verify JWT token validity
    
    Args:
        token: JWT token to verify
        
    Returns:
        Token validity status and payload
    """
    from backend.middleware.jwt_auth import verify_token as verify_jwt
    
    try:
        payload = verify_jwt(token)
        return {
            "valid": True,
            "address": payload.get("sub"),
            "exp": payload.get("exp")
        }
    except HTTPException:
        return {"valid": False}


@router.get("/admins")
async def list_admins(current_user: dict = Depends(require_admin)):
    """
    Get list of admin addresses (protected endpoint - requires admin authentication)
    
    Returns:
        List of admin wallet addresses
    """
    admin_addresses = get_admin_addresses()
    
    return {
        "admins": admin_addresses,
        "count": len(admin_addresses)
    }


@router.get("/check-admin/{address}")
async def check_admin(address: str, current_user: dict = Depends(require_admin)):
    """
    Check if an address has admin privileges (protected endpoint - requires admin authentication)
    
    Args:
        address: Wallet address to check
        
    Returns:
        Admin status
    """
    is_admin_user = is_admin(address)
    
    return {
        "address": address.lower(),
        "is_admin": is_admin_user
    }

