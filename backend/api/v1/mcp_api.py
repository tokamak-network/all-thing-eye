"""
MCP API - 2-Phase Analysis Implementation
Optimized for custom export analysis and template-based queries.
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import json
import httpx
from datetime import datetime, timedelta
from pathlib import Path

from src.utils.logger import get_logger
from backend.middleware.jwt_auth import require_admin
from backend.api.v1.mcp_utils import (
    get_mongo, 
    fetch_github_activities, 
    fetch_slack_messages,
    github_to_member_name,
    slack_to_member_name
)

logger = get_logger(__name__)
router = APIRouter()

class ChatWithContextRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: Optional[str] = "gpt-oss:120b"
    context_hints: Optional[Dict[str, Any]] = None

@router.post("/mcp/chat")
async def chat_with_context(
    body: ChatWithContextRequest,
    _admin: str = Depends(require_admin)
):
    """
    Chat with AI using MCP context injection.
    """
    return await run_mcp_chat_logic(body)

@router.post("/mcp/chat/test")
async def chat_with_context_test(
    body: ChatWithContextRequest
):
    """Test endpoint for MCP Chat - NO AUTH REQUIRED (Development only)."""
    is_dev = os.getenv("ENVIRONMENT", "development") != "production"
    if not is_dev:
        raise HTTPException(status_code=403, detail="Test endpoint disabled in production")
    return await run_mcp_chat_logic(body)

async def run_mcp_chat_logic(body: ChatWithContextRequest):
    """Internal logic for MCP chat analysis."""
    db = get_mongo().db
    user_message = body.messages[-1].get("content", "") if body.messages else ""
    context_hints = body.context_hints or {}
    
    api_key = os.getenv("AI_API_KEY", "")
    api_url = os.getenv("AI_API_URL", "https://api.toka.ngrok.app")
    
    if not api_key:
        raise HTTPException(status_code=500, detail="AI API key not configured")

    # PHASE 1: Data Gathering
    data_for_ai = {}
    data_source_info = ""
    
    raw_data = context_hints.get("raw_data")
    if raw_data:
        # Custom export path: data is already provided
        data_for_ai = raw_data
        data_source_info = "Data source: Custom Export UI Selection"
        logger.info("Using raw data from context hints")
    else:
        # Auto-fetch path: identify what's needed
        analysis = analyze_question(user_message)
        logger.info(f"Auto-analysis for query: {analysis}")
        
        start_dt = datetime.utcnow() - timedelta(days=analysis.get("days", 30))
        
        results = {}
        if analysis.get("needs_github"):
            results["github"] = await fetch_github_activities(db, start_date=start_dt)
        if analysis.get("needs_slack"):
            results["slack"] = await fetch_slack_messages(db, start_date=start_dt)
            
        data_for_ai = results
        data_source_info = f"Data source: Auto-fetched for last {analysis.get('days', 30)} days"

    # PHASE 2: AI Analysis
    system_prompt = f"""You are a data analyst for All-Thing-Eye. 
Analyze the provided data and answer the user's question accurately.

## RULES
1. **Be Exact**: Use the numbers provided in the data.
2. **Markdown Tables**: Always use tables for comparison or rankings.
3. **Combined View**: Sum activities from all sources (GitHub + Slack) when calculating "total activity".
4. **Member List**: Only mention members found in the data.

## DATA CONTEXT
{data_source_info}
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Question: {user_message}\n\nData for Analysis:\n{json.dumps(data_for_ai, ensure_ascii=False)[:15000]}"}
    ]

    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        resp = await client.post(
            f"{api_url}/api/chat",
            json={"messages": messages, "model": body.model},
            headers=headers
        )
        
        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"AI API Error: {resp.text}")
            
        return resp.json()

def analyze_question(question: str) -> Dict[str, Any]:
    """Simple heuristic to determine data needs."""
    q = question.lower()
    needs_github = any(w in q for w in ["commit", "github", "pr", "코드", "커밋"])
    needs_slack = any(w in q for w in ["slack", "message", "메시지", "채팅"])
    
    # If generic activity question, get both
    if not needs_github and not needs_slack:
        needs_github = needs_slack = True
        
    days = 30
    if "지난 주" in q or "last week" in q: days = 7
    elif "오늘" in q or "today" in q: days = 1
    
    return {"needs_github": needs_github, "needs_slack": needs_slack, "days": days}
