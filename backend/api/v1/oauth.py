"""
OAuth Authentication API Endpoints

Handles Google and GitHub OAuth login with proper security measures.
"""

import os
import secrets
from datetime import timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from backend.middleware.jwt_auth import (
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

# =============================================================================
# OAuth Configuration
# =============================================================================

# Google OAuth Config
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/api/v1/oauth/google/callback")

# GitHub OAuth Config
GITHUB_CLIENT_ID = os.getenv("GITHUB_OAUTH_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_OAUTH_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_OAUTH_REDIRECT_URI", "http://localhost:8000/api/v1/oauth/github/callback")

# Frontend redirect URL after successful OAuth
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# State storage (in production, use Redis or database)
# Simple in-memory storage with TTL for CSRF protection
_oauth_states: dict[str, dict] = {}


# =============================================================================
# Pydantic Models
# =============================================================================

class OAuthLoginResponse(BaseModel):
    """OAuth login redirect response"""
    auth_url: str
    state: str


class OAuthTokenResponse(BaseModel):
    """OAuth callback response with JWT token"""
    access_token: str
    token_type: str
    expires_in: int
    user: dict


class OAuthProviderInfo(BaseModel):
    """OAuth provider availability info"""
    google: bool
    github: bool


# =============================================================================
# Helper Functions
# =============================================================================

def generate_state() -> str:
    """Generate a secure random state for CSRF protection"""
    return secrets.token_urlsafe(32)


def store_oauth_state(state: str, provider: str, redirect_uri: Optional[str] = None) -> None:
    """Store OAuth state for validation"""
    _oauth_states[state] = {
        "provider": provider,
        "redirect_uri": redirect_uri,
    }


def validate_and_consume_state(state: str, provider: str) -> Optional[dict]:
    """Validate OAuth state and remove it (single use)"""
    stored = _oauth_states.pop(state, None)
    if stored and stored.get("provider") == provider:
        return stored
    return None


# =============================================================================
# Common Endpoints
# =============================================================================

@router.get("/providers", response_model=OAuthProviderInfo)
async def get_available_providers():
    """
    Get available OAuth providers

    Returns:
        Available OAuth providers based on configuration
    """
    return OAuthProviderInfo(
        google=bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        github=bool(GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET),
    )


# =============================================================================
# Google OAuth Endpoints
# =============================================================================

@router.get("/google/login")
async def google_login(redirect_uri: Optional[str] = None):
    """
    Initiate Google OAuth login flow

    Args:
        redirect_uri: Optional frontend redirect URI after login

    Returns:
        Redirect to Google OAuth consent screen
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured"
        )

    state = generate_state()
    store_oauth_state(state, "google", redirect_uri)

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }

    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    logger.info(f"🔐 Google OAuth login initiated (state: {state[:8]}...)")

    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
async def google_callback(code: str, state: str, error: Optional[str] = None):
    """
    Handle Google OAuth callback

    Args:
        code: Authorization code from Google
        state: State parameter for CSRF validation
        error: Error message if authentication failed

    Returns:
        Redirect to frontend with JWT token
    """
    if error:
        logger.warning(f"❌ Google OAuth error: {error}")
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?error={error}"
        )

    # Validate state
    state_data = validate_and_consume_state(state, "google")
    if not state_data:
        logger.warning(f"❌ Invalid OAuth state: {state[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state"
        )

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": GOOGLE_REDIRECT_URI,
            },
        )

        if token_response.status_code != 200:
            logger.error(f"❌ Google token exchange failed: {token_response.text}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to exchange authorization code"
            )

        tokens = token_response.json()

        # Get user info
        userinfo_response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )

        if userinfo_response.status_code != 200:
            logger.error(f"❌ Failed to get Google user info: {userinfo_response.text}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to get user information"
            )

        user_info = userinfo_response.json()

    # Create JWT token
    access_token = create_access_token(
        data={
            "sub": user_info["email"],
            "provider": "google",
            "name": user_info.get("name"),
            "picture": user_info.get("picture"),
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    logger.info(f"✅ Google OAuth login successful for {user_info['email']}")

    # Redirect to frontend with token
    frontend_redirect = state_data.get("redirect_uri") or FRONTEND_URL
    return RedirectResponse(
        url=f"{frontend_redirect}?token={access_token}&provider=google"
    )


# =============================================================================
# GitHub OAuth Endpoints
# =============================================================================

@router.get("/github/login")
async def github_login(redirect_uri: Optional[str] = None):
    """
    Initiate GitHub OAuth login flow

    Args:
        redirect_uri: Optional frontend redirect URI after login

    Returns:
        Redirect to GitHub OAuth consent screen
    """
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="GitHub OAuth is not configured"
        )

    state = generate_state()
    store_oauth_state(state, "github", redirect_uri)

    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": "read:user user:email",
        "state": state,
    }

    auth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"

    logger.info(f"🔐 GitHub OAuth login initiated (state: {state[:8]}...)")

    return RedirectResponse(url=auth_url)


@router.get("/github/callback")
async def github_callback(code: str, state: str, error: Optional[str] = None):
    """
    Handle GitHub OAuth callback

    Args:
        code: Authorization code from GitHub
        state: State parameter for CSRF validation
        error: Error message if authentication failed

    Returns:
        Redirect to frontend with JWT token
    """
    if error:
        logger.warning(f"❌ GitHub OAuth error: {error}")
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?error={error}"
        )

    # Validate state
    state_data = validate_and_consume_state(state, "github")
    if not state_data:
        logger.warning(f"❌ Invalid OAuth state: {state[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state"
        )

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )

        if token_response.status_code != 200:
            logger.error(f"❌ GitHub token exchange failed: {token_response.text}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to exchange authorization code"
            )

        tokens = token_response.json()

        if "error" in tokens:
            logger.error(f"❌ GitHub OAuth error: {tokens['error_description']}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=tokens.get("error_description", "Authentication failed")
            )

        access_token = tokens["access_token"]

        # Get user info
        userinfo_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )

        if userinfo_response.status_code != 200:
            logger.error(f"❌ Failed to get GitHub user info: {userinfo_response.text}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to get user information"
            )

        user_info = userinfo_response.json()

        # Get primary email if not public
        email = user_info.get("email")
        if not email:
            emails_response = await client.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            if emails_response.status_code == 200:
                emails = emails_response.json()
                primary_email = next(
                    (e["email"] for e in emails if e.get("primary")),
                    emails[0]["email"] if emails else None
                )
                email = primary_email

    # Create JWT token
    jwt_token = create_access_token(
        data={
            "sub": email or user_info["login"],
            "provider": "github",
            "github_username": user_info["login"],
            "name": user_info.get("name") or user_info["login"],
            "picture": user_info.get("avatar_url"),
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    logger.info(f"✅ GitHub OAuth login successful for {user_info['login']}")

    # Redirect to frontend with token
    frontend_redirect = state_data.get("redirect_uri") or FRONTEND_URL
    return RedirectResponse(
        url=f"{frontend_redirect}?token={jwt_token}&provider=github"
    )


# =============================================================================
# Token Exchange Endpoint (for SPA)
# =============================================================================

class TokenExchangeRequest(BaseModel):
    """Request to exchange OAuth code for JWT token"""
    provider: str
    code: str
    redirect_uri: str


@router.post("/token", response_model=OAuthTokenResponse)
async def exchange_token(request: TokenExchangeRequest):
    """
    Exchange OAuth authorization code for JWT token (for SPA flows)

    This endpoint is for Single Page Applications that handle the OAuth
    callback in the frontend and need to exchange the code server-side.

    Args:
        request: Token exchange request with provider, code, and redirect_uri

    Returns:
        JWT token and user information
    """
    if request.provider == "google":
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Google OAuth is not configured"
            )

        async with httpx.AsyncClient() as client:
            # Exchange code for tokens
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "code": request.code,
                    "grant_type": "authorization_code",
                    "redirect_uri": request.redirect_uri,
                },
            )

            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Failed to exchange authorization code"
                )

            tokens = token_response.json()

            # Get user info
            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )

            if userinfo_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Failed to get user information"
                )

            user_info = userinfo_response.json()

        jwt_token = create_access_token(
            data={
                "sub": user_info["email"],
                "provider": "google",
                "name": user_info.get("name"),
                "picture": user_info.get("picture"),
            },
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        return OAuthTokenResponse(
            access_token=jwt_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user={
                "email": user_info["email"],
                "name": user_info.get("name"),
                "picture": user_info.get("picture"),
                "provider": "google",
            },
        )

    elif request.provider == "github":
        if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="GitHub OAuth is not configured"
            )

        async with httpx.AsyncClient() as client:
            # Exchange code for tokens
            token_response = await client.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": GITHUB_CLIENT_ID,
                    "client_secret": GITHUB_CLIENT_SECRET,
                    "code": request.code,
                },
                headers={"Accept": "application/json"},
            )

            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Failed to exchange authorization code"
                )

            tokens = token_response.json()

            if "error" in tokens:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=tokens.get("error_description", "Authentication failed")
                )

            access_token = tokens["access_token"]

            # Get user info
            userinfo_response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )

            if userinfo_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Failed to get user information"
                )

            user_info = userinfo_response.json()

            # Get primary email if not public
            email = user_info.get("email")
            if not email:
                emails_response = await client.get(
                    "https://api.github.com/user/emails",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                )
                if emails_response.status_code == 200:
                    emails = emails_response.json()
                    primary_email = next(
                        (e["email"] for e in emails if e.get("primary")),
                        emails[0]["email"] if emails else None
                    )
                    email = primary_email

        jwt_token = create_access_token(
            data={
                "sub": email or user_info["login"],
                "provider": "github",
                "github_username": user_info["login"],
                "name": user_info.get("name") or user_info["login"],
                "picture": user_info.get("avatar_url"),
            },
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        return OAuthTokenResponse(
            access_token=jwt_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user={
                "email": email,
                "username": user_info["login"],
                "name": user_info.get("name") or user_info["login"],
                "picture": user_info.get("avatar_url"),
                "provider": "github",
            },
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OAuth provider: {request.provider}"
        )
