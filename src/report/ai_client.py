"""
AI Client for Report Generation

Uses Tokamak AI API (OpenAI-compatible) for generating reports.
"""

import os
import asyncio
from typing import Optional, List, Dict, Any
import httpx
from dotenv import load_dotenv

load_dotenv()


def get_ai_api_key() -> str:
    """Get AI API key from environment."""
    return os.getenv("AI_API_KEY", "")


def get_ai_api_url() -> str:
    """Get AI API URL from environment."""
    return os.getenv("AI_API_URL", "https://api.ai.tokamak.network")


def get_default_model() -> str:
    """Get default AI model from environment."""
    return os.getenv("AI_MODEL", "qwen3-235b")


async def generate_completion(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 4000,
    temperature: float = 0.2,
    max_retries: int = 3
) -> str:
    """
    Generate completion using Tokamak AI API.
    
    Args:
        prompt: User prompt/message
        system_prompt: System message for context
        model: Model to use (optional, uses API default)
        max_tokens: Maximum tokens in response
        temperature: Temperature for generation
        max_retries: Number of retries on failure
        
    Returns:
        Generated text response
    """
    api_key = get_ai_api_key()
    api_url = get_ai_api_url()
    
    if not api_key:
        raise ValueError("AI_API_KEY environment variable is required")
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    # Model is required for Tokamak AI API
    actual_model = model or get_default_model()
    
    payload = {
        "messages": messages,
        "model": actual_model,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    
    request_url = f"{api_url}/v1/chat/completions"
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    request_url,
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 429:
                    # Rate limit - wait and retry
                    wait_time = 30 * (attempt + 1)
                    print(f"Rate limited, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                data = response.json()
                
                # Extract content from OpenAI-compatible response
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
                else:
                    raise ValueError(f"Unexpected response format: {data}")
                    
        except httpx.HTTPStatusError as e:
            if attempt < max_retries - 1:
                wait_time = 5 * (attempt + 1)
                print(f"API error: {e}, retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
            raise RuntimeError(f"AI API error after {max_retries} attempts: {e}")
        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                print(f"Timeout, retrying...")
                continue
            raise RuntimeError("AI API timeout after multiple attempts")
    
    raise RuntimeError("Failed to generate completion")


def generate_completion_sync(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 4000,
    temperature: float = 0.2
) -> str:
    """Synchronous wrapper for generate_completion."""
    return asyncio.run(generate_completion(
        prompt, system_prompt, model, max_tokens, temperature
    ))
