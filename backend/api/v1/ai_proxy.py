"""
AI API Proxy Endpoints

Proxies requests to Tokamak AI API server with proper authentication.
This keeps API keys secure on the backend.
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import httpx
import os
from pathlib import Path
from dotenv import load_dotenv

from src.utils.logger import get_logger
from backend.middleware.jwt_auth import require_admin

logger = get_logger(__name__)

router = APIRouter()

# Load .env file if it exists
# ai_proxy.py is at: backend/api/v1/ai_proxy.py
# Project root is: backend/api/v1/../../../
project_root = Path(__file__).parent.parent.parent.parent
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=False)
    logger.info(f"✅ Loaded .env from: {env_path}")
else:
    logger.warning(f"⚠️  .env file not found at: {env_path}")

def get_ai_api_key() -> str:
    """Get AI API key from environment variable"""
    api_key = os.getenv("AI_API_KEY", "").strip()
    if not api_key:
        logger.warning("AI_API_KEY not found in environment variables")
    else:
        logger.debug(f"AI_API_KEY loaded: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '***'} (length: {len(api_key)})")
    return api_key

def get_ai_api_url() -> str:
    """Get AI API base URL from environment variable"""
    return os.getenv("AI_API_URL", "https://api.ai.tokamak.network").strip()


class ChatMessage(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class GenerateRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


@router.post("/ai/chat")
async def proxy_chat(
    request: Request,
    chat_request: ChatRequest,
    _admin: str = Depends(require_admin)
):
    """
    Proxy chat request to Tokamak AI API
    
    Args:
        chat_request: Chat request with messages and optional model/context
        
    Returns:
        AI response from Tokamak AI API
    """
    # Get API key from environment (loads .env if needed)
    api_key = get_ai_api_key()
    api_url = get_ai_api_url()
    
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="AI API key not configured. Please set AI_API_KEY environment variable."
        )
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            
            payload = {
                "messages": [
                    {"role": msg.role, "content": msg.content}
                    for msg in chat_request.messages
                ]
            }
            
            if chat_request.model:
                payload["model"] = chat_request.model
            
            # Note: context is not part of OpenAI standard, but we'll keep it for compatibility
            if chat_request.context:
                payload["context"] = chat_request.context
            
            request_url = f"{api_url}/v1/chat/completions"
            logger.info(f"📤 AI Proxy Chat - Request URL: {request_url}")
            logger.info(f"📤 AI Proxy Chat - Model: {payload.get('model', 'default')}, Messages: {len(payload.get('messages', []))}")
            
            response = await client.post(
                request_url,
                json=payload,
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"❌ AI Proxy Chat - Error: Status {response.status_code}, Response: {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"AI API error: {response.text}"
                )
            
            # Convert OpenAI format to expected format for frontend compatibility
            ai_data = response.json()
            if "choices" in ai_data and len(ai_data["choices"]) > 0:
                content = ai_data["choices"][0]["message"]["content"]
                return {"message": {"content": content}}
            else:
                return ai_data
            
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="AI API request timeout"
        )
    except httpx.RequestError as e:
        logger.error(f"AI API request error: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to AI API: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in AI proxy: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/ai/generate")
async def proxy_generate(
    request: Request,
    generate_request: GenerateRequest,
    _admin: str = Depends(require_admin)
):
    """
    Proxy generate request to Tokamak AI API
    
    Args:
        generate_request: Generate request with prompt and optional model/context
        
    Returns:
        AI generated text from Tokamak AI API
    """
    # Get API key from environment (loads .env if needed)
    api_key = get_ai_api_key()
    api_url = get_ai_api_url()
    
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="AI API key not configured. Please set AI_API_KEY environment variable."
        )
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            
            payload = {
                "prompt": generate_request.prompt
            }
            
            if generate_request.model:
                payload["model"] = generate_request.model
            
            if generate_request.context:
                payload["context"] = generate_request.context
            
            response = await client.post(
                f"{api_url}/api/generate",
                json=payload,
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"AI API error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"AI API error: {response.text}"
                )
            
            return response.json()
            
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="AI API request timeout"
        )
    except httpx.RequestError as e:
        logger.error(f"AI API request error: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to AI API: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in AI proxy: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/ai/models")
async def proxy_list_models(
    request: Request,
    _admin: str = Depends(require_admin)
):
    """
    Proxy request to list available AI models
    
    Returns:
        List of available models from Tokamak AI API
    """
    # Get API key from environment (loads .env if needed)
    api_key = get_ai_api_key()
    api_url = get_ai_api_url()
    
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="AI API key not configured. Please set AI_API_KEY environment variable."
        )
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {api_key}",
            }
            
            # Try /v1/models first (OpenAI standard), fallback to /api/tags
            try:
                response = await client.get(
                    f"{api_url}/v1/models",
                    headers=headers
                )
                if response.status_code == 200:
                    # Convert OpenAI models format to expected format
                    models_data = response.json()
                    if "data" in models_data:
                        # OpenAI format: { "data": [{"id": "...", ...}] }
                        tags = [{"name": model.get("id", ""), "size": ""} for model in models_data["data"]]
                        return {"tags": tags}
                    return models_data
            except Exception as e:
                logger.warning(f"Failed to get models from /v1/models: {e}, trying /api/tags")
            
            # Fallback to /api/tags
            response = await client.get(
                f"{api_url}/api/tags",
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"AI API error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"AI API error: {response.text}"
                )
            
            return response.json()
            
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="AI API request timeout"
        )
    except httpx.RequestError as e:
        logger.error(f"AI API request error: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to AI API: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in AI proxy: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

