"""
MCP Agent - True Function Calling Agent Implementation

This module implements a real MCP-style agent that can:
1. Understand user questions
2. Decide which tools to call
3. Execute tools and get results
4. Iterate until it has enough information
5. Generate final answer
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import re
import httpx
import os
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

from src.utils.logger import get_logger
from backend.api.v1.auth import require_admin

logger = get_logger(__name__)
router = APIRouter()

# Load environment
env_path = Path(__file__).parent.parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=False)


# ============================================================================
# Tool Definitions
# ============================================================================

TOOLS = [
    {
        "name": "query_database",
        "description": "Execute a query to fetch data from the database. Use this to get ANY data: GitHub commits, Slack messages, Notion pages, Google Drive activities, members, projects, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "data_type": {
                    "type": "string",
                    "description": "Type of data to fetch: 'github', 'slack', 'notion', 'drive', 'recordings', 'members', 'projects'"
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date in ISO format (e.g., '2025-12-01'). Optional."
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in ISO format (e.g., '2025-12-31'). Optional."
                },
                "member_name": {
                    "type": "string",
                    "description": "Filter by member name. Optional."
                },
                "project_key": {
                    "type": "string",
                    "description": "Filter by project key. Optional."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results. Default: 200"
                }
            },
            "required": ["data_type"]
        }
    },
    {
        "name": "get_github_activities",
        "description": "Get GitHub activities (commits, pull requests, issues) for a specific time period. Use this when user asks about code contributions, commits, PRs, or GitHub activity.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start date in ISO format (e.g., '2025-12-01'). Required."
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in ISO format (e.g., '2025-12-31'). Optional."
                },
                "member_name": {
                    "type": "string",
                    "description": "Filter by member name (e.g., 'Jake', 'Ale'). Optional."
                },
                "project_key": {
                    "type": "string",
                    "description": "Filter by project key: 'project-ooo', 'project-eco', 'project-syb', 'project-trh'. Optional."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results. Default: 200"
                }
            },
            "required": ["start_date"]
        }
    },
    {
        "name": "get_slack_messages",
        "description": "Get Slack messages for a specific time period. Use this when user asks about communication, messages, or Slack activity.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start date in ISO format. Required."
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in ISO format. Optional."
                },
                "member_name": {
                    "type": "string",
                    "description": "Filter by member name. Optional."
                },
                "project_key": {
                    "type": "string",
                    "description": "Filter by project key. Optional."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results. Default: 200"
                }
            },
            "required": ["start_date"]
        }
    },
    {
        "name": "get_member_list",
        "description": "Get list of all team members with their basic info. Use this to know who is on the team.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_project_info",
        "description": "Get project details including repositories, lead, and team members. Use this for project-specific questions.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_key": {
                    "type": "string",
                    "description": "Project key: 'project-ooo', 'project-eco', 'project-syb', 'project-trh'. If not specified, returns all projects."
                }
            },
            "required": []
        }
    },
    {
        "name": "final_answer",
        "description": "Use this when you have gathered enough information and are ready to provide the final answer to the user. ALWAYS use this to end the conversation.",
        "parameters": {
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": "The final answer to present to the user. Use markdown formatting."
                }
            },
            "required": ["answer"]
        }
    }
]


def get_mongo():
    """Get MongoDB manager."""
    from backend.main import mongo_manager
    return mongo_manager


# ============================================================================
# Tool Execution Functions
# ============================================================================

async def execute_get_github_activities(args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute get_github_activities tool."""
    try:
        mongo = get_mongo()
        db = mongo.db
        
        # Build query
        query = {}
        
        # Date filter
        start_date = args.get("start_date")
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query["date"] = {"$gte": start_dt}
        
        end_date = args.get("end_date")
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            if "date" in query:
                query["date"]["$lte"] = end_dt
            else:
                query["date"] = {"$lte": end_dt}
        
        # Project filter
        project_key = args.get("project_key")
        if project_key:
            project = db["projects"].find_one({"key": project_key})
            if project and project.get("repositories"):
                query["repository"] = {"$in": project["repositories"]}
        
        limit = args.get("limit", 200)
        
        # Fetch commits
        commits = list(db["github_commits"].find(query).sort("date", -1).limit(limit))
        
        # Map GitHub usernames to member names
        member_map = {}
        for identifier in db["member_identifiers"].find({"source": "github"}):
            member_map[identifier.get("identifier_value", "").lower()] = identifier.get("member_name")
        
        # Process results
        activities = []
        member_counts = {}
        
        for commit in commits:
            author = commit.get("author_name", "Unknown")
            member_name = member_map.get(author.lower(), author)
            
            # Filter by member if specified
            if args.get("member_name"):
                if member_name.lower() != args["member_name"].lower():
                    continue
            
            member_counts[member_name] = member_counts.get(member_name, 0) + 1
            
            activities.append({
                "type": "commit",
                "member": member_name,
                "repository": commit.get("repository"),
                "message": commit.get("message", "")[:100],
                "date": str(commit.get("date", ""))[:10],
                "additions": commit.get("additions", 0),
                "deletions": commit.get("deletions", 0),
            })
        
        return {
            "success": True,
            "total_count": len(activities),
            "member_summary": dict(sorted(member_counts.items(), key=lambda x: -x[1])),
            "sample_activities": activities[:20],  # Only return sample for context size
        }
        
    except Exception as e:
        logger.error(f"Error executing get_github_activities: {e}")
        return {"success": False, "error": str(e)}


async def execute_get_slack_messages(args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute get_slack_messages tool."""
    try:
        mongo = get_mongo()
        db = mongo.db
        
        # Build query - exclude tokamak-partners
        query = {"channel_name": {"$ne": "tokamak-partners"}}
        
        # Date filter
        start_date = args.get("start_date")
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query["posted_at"] = {"$gte": start_dt}
        
        end_date = args.get("end_date")
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            if "posted_at" in query:
                query["posted_at"]["$lte"] = end_dt
            else:
                query["posted_at"] = {"$lte": end_dt}
        
        # Project filter (by channel)
        project_key = args.get("project_key")
        if project_key:
            project = db["projects"].find_one({"key": project_key})
            if project and project.get("slack_channel_id"):
                query["channel_id"] = project["slack_channel_id"]
        
        limit = args.get("limit", 200)
        
        # Fetch messages
        messages = list(db["slack_messages"].find(query).sort("posted_at", -1).limit(limit))
        
        # Map Slack user names to member names
        member_map = {}
        for identifier in db["member_identifiers"].find({"source": "slack"}):
            # Use user_id or lowercase name matching
            member_map[identifier.get("identifier_value", "").lower()] = identifier.get("member_name")
        
        # Also map by lowercase member names
        for member in db["members"].find():
            name = member.get("name", "")
            member_map[name.lower()] = name
        
        # Process results
        activities = []
        member_counts = {}
        
        for msg in messages:
            user_name = msg.get("user_name", "Unknown")
            member_name = member_map.get(user_name.lower(), user_name.capitalize())
            
            # Filter by member if specified
            if args.get("member_name"):
                if member_name.lower() != args["member_name"].lower():
                    continue
            
            member_counts[member_name] = member_counts.get(member_name, 0) + 1
            
            activities.append({
                "type": "slack_message",
                "member": member_name,
                "channel": msg.get("channel_name", "Unknown"),
                "text": (msg.get("text", "") or "")[:100],
                "date": str(msg.get("posted_at", ""))[:10],
            })
        
        return {
            "success": True,
            "total_count": len(activities),
            "member_summary": dict(sorted(member_counts.items(), key=lambda x: -x[1])),
            "sample_messages": activities[:20],
        }
        
    except Exception as e:
        logger.error(f"Error executing get_slack_messages: {e}")
        return {"success": False, "error": str(e)}


async def execute_get_member_list(args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute get_member_list tool."""
    try:
        mongo = get_mongo()
        db = mongo.db
        
        members = list(db["members"].find())
        
        member_list = []
        for m in members:
            member_list.append({
                "name": m.get("name"),
                "email": m.get("email"),
                "role": m.get("role"),
                "projects": m.get("projects", []),
            })
        
        return {
            "success": True,
            "total_members": len(member_list),
            "members": member_list,
        }
        
    except Exception as e:
        logger.error(f"Error executing get_member_list: {e}")
        return {"success": False, "error": str(e)}


async def execute_get_project_info(args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute get_project_info tool."""
    try:
        mongo = get_mongo()
        db = mongo.db
        
        project_key = args.get("project_key")
        
        if project_key:
            projects = [db["projects"].find_one({"key": project_key})]
        else:
            projects = list(db["projects"].find())
        
        result = []
        for p in projects:
            if not p:
                continue
            result.append({
                "key": p.get("key"),
                "name": p.get("name"),
                "lead": p.get("lead"),
                "repositories": p.get("repositories", [])[:10],  # Limit for context
                "repository_count": len(p.get("repositories", [])),
                "slack_channel": p.get("slack_channel"),
                "member_count": len(p.get("member_ids", [])),
                "is_active": p.get("is_active", True),
            })
        
        return {
            "success": True,
            "projects": result,
        }
        
    except Exception as e:
        logger.error(f"Error executing get_project_info: {e}")
        return {"success": False, "error": str(e)}


async def execute_query_database(args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute query_database tool - unified database access."""
    try:
        mongo = get_mongo()
        db = mongo.db
        
        data_type = args.get("data_type", "").lower()
        start_date = args.get("start_date")
        end_date = args.get("end_date")
        member_name = args.get("member_name")
        project_key = args.get("project_key")
        limit = args.get("limit", 200)
        
        # Build date filter
        date_filter = {}
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            date_filter["$gte"] = start_dt
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            date_filter["$lte"] = end_dt
        
        if data_type == "members":
            members = list(db["members"].find().limit(limit))
            return {
                "success": True,
                "data_type": "members",
                "total_count": len(members),
                "data": [{"name": m.get("name"), "email": m.get("email"), "role": m.get("role")} for m in members]
            }
        
        if data_type == "projects":
            projects = list(db["projects"].find().limit(limit))
            return {
                "success": True,
                "data_type": "projects",
                "total_count": len(projects),
                "data": [{"key": p.get("key"), "name": p.get("name"), "lead": p.get("lead")} for p in projects]
            }
        
        # Handle each data type specifically
        if data_type == "github":
            query = {}
            if date_filter:
                query["date"] = date_filter
            if project_key:
                project = db["projects"].find_one({"key": project_key})
                if project and project.get("repositories"):
                    query["repository"] = {"$in": project["repositories"]}
            
            items = list(db["github_commits"].find(query).sort("date", -1).limit(limit))
            member_counts = {}
            for item in items:
                user = item.get("author_name", "Unknown")
                member_counts[user] = member_counts.get(user, 0) + 1
            
            return {
                "success": True,
                "data_type": "github",
                "total_count": len(items),
                "date_range": f"{start_date or 'N/A'} ~ {end_date or 'N/A'}",
                "by_member": dict(sorted(member_counts.items(), key=lambda x: -x[1])),
            }
        
        elif data_type == "slack":
            query = {"channel_name": {"$ne": "tokamak-partners"}}
            if date_filter:
                query["posted_at"] = date_filter
            if project_key:
                project = db["projects"].find_one({"key": project_key})
                if project and project.get("slack_channel_id"):
                    query["channel_id"] = project["slack_channel_id"]
            
            items = list(db["slack_messages"].find(query).sort("posted_at", -1).limit(limit))
            member_counts = {}
            for item in items:
                user = item.get("user_name", "Unknown")
                member_counts[user] = member_counts.get(user, 0) + 1
            
            return {
                "success": True,
                "data_type": "slack",
                "total_count": len(items),
                "date_range": f"{start_date or 'N/A'} ~ {end_date or 'N/A'}",
                "by_member": dict(sorted(member_counts.items(), key=lambda x: -x[1])),
            }
        
        elif data_type == "notion":
            query = {}
            if date_filter:
                query["last_edited_time"] = date_filter
            
            items = list(db["notion_pages"].find(query).sort("last_edited_time", -1).limit(limit))
            member_counts = {}
            for item in items:
                # created_by is an object with {name, email, id}
                created_by = item.get("created_by", {})
                if isinstance(created_by, dict):
                    user = created_by.get("name") or created_by.get("email") or "Unknown"
                else:
                    user = str(created_by) if created_by else "Unknown"
                member_counts[user] = member_counts.get(user, 0) + 1
            
            return {
                "success": True,
                "data_type": "notion",
                "total_count": len(items),
                "date_range": f"{start_date or 'N/A'} ~ {end_date or 'N/A'}",
                "by_member": dict(sorted(member_counts.items(), key=lambda x: -x[1])),
                "sample_titles": [item.get("title", "")[:50] for item in items[:5]],
            }
        
        elif data_type == "drive":
            query = {}
            if date_filter:
                query["timestamp"] = date_filter
            
            items = list(db["drive_activities"].find(query).sort("timestamp", -1).limit(limit))
            member_counts = {}
            for item in items:
                user = item.get("user_email", "Unknown")
                # Extract username from email
                if "@" in user:
                    user = user.split("@")[0].capitalize()
                member_counts[user] = member_counts.get(user, 0) + 1
            
            return {
                "success": True,
                "data_type": "drive",
                "total_count": len(items),
                "date_range": f"{start_date or 'N/A'} ~ {end_date or 'N/A'}",
                "by_member": dict(sorted(member_counts.items(), key=lambda x: -x[1])),
            }
        
        elif data_type == "recordings":
            query = {}
            if date_filter:
                query["modified_time"] = date_filter
            
            items = list(db["recordings"].find(query).sort("modified_time", -1).limit(limit))
            member_counts = {}
            for item in items:
                user = item.get("created_by", "Unknown")
                member_counts[user] = member_counts.get(user, 0) + 1
            
            return {
                "success": True,
                "data_type": "recordings",
                "total_count": len(items),
                "date_range": f"{start_date or 'N/A'} ~ {end_date or 'N/A'}",
                "by_member": dict(sorted(member_counts.items(), key=lambda x: -x[1])),
                "sample_titles": [item.get("name", "")[:50] for item in items[:5]],
            }
        
        else:
            return {"success": False, "error": f"Unknown data_type: {data_type}. Use: github, slack, notion, drive, recordings, members, projects"}
        
    except Exception as e:
        logger.error(f"Error in query_database: {e}")
        import traceback
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


# Tool executor mapping
TOOL_EXECUTORS = {
    "query_database": execute_query_database,
    "get_github_activities": execute_get_github_activities,
    "get_slack_messages": execute_get_slack_messages,
    "get_member_list": execute_get_member_list,
    "get_project_info": execute_get_project_info,
}


# ============================================================================
# Agent Loop
# ============================================================================

def get_all_member_names() -> list:
    """Get all member names from database."""
    try:
        mongo = get_mongo()
        db = mongo.db
        members = list(db["members"].find({}, {"name": 1}))
        return [m.get("name") for m in members if m.get("name")]
    except Exception as e:
        logger.error(f"Error fetching member names: {e}")
        return []


def load_reference_docs() -> str:
    """Load AI reference documentation."""
    docs_path = Path(__file__).parent.parent.parent.parent / 'docs' / 'ai-reference'
    content = []
    
    if docs_path.exists():
        for md_file in docs_path.glob('*.md'):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content.append(f"## {md_file.stem}\n\n{f.read()}")
            except Exception as e:
                logger.warning(f"Could not read {md_file}: {e}")
    
    return "\n\n---\n\n".join(content) if content else ""


def build_system_prompt() -> str:
    """Build the system prompt for the agent."""
    now = datetime.utcnow()
    today = now.strftime("%Y-%m-%d")
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    month_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    last_month_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1).strftime("%Y-%m-%d")
    last_month_end = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Get actual member names from database
    member_names = get_all_member_names()
    member_list_str = ", ".join(member_names) if member_names else "Unable to fetch members"
    
    tools_desc = "\n".join([
        f"- **{t['name']}**: {t['description']}"
        for t in TOOLS
    ])
    
    # Load reference documentation
    reference_docs = load_reference_docs()
    
    return f"""You are an AI assistant for All-Thing-Eye team analytics platform.

## YOUR CAPABILITIES:
✅ You CAN access the database through tools provided
✅ You CAN fetch: GitHub commits, Slack messages, Notion pages, Drive activities, Recordings
✅ You CAN query http://localhost:8000/graphql

## Current Date: {today}
## Date References:
- This week: {week_ago} to {today}
- This month: {month_ago} to {today}
- Last month: {last_month_start} to {last_month_end}
- Last quarter (Q4 2025): 2025-10-01 to 2025-12-31

## Team Members ({len(member_names)} people):
{member_list_str}

## Available Tools:
{tools_desc}

## Tool Call Format:
```json
{{"tool": "tool_name", "args": {{"param1": "value1"}}}}
```

## WORKFLOW:
1. Call query_database or other tools to fetch data
2. Analyze the returned data
3. Use final_answer to respond with markdown-formatted summary

## IMPORTANT RULES:
- You HAVE database access - USE THE TOOLS!
- ONLY use member names from the list above
- Use Korean when user asks in Korean
- Create markdown tables for summaries
- NEVER say "I cannot access the database" - you CAN!

---

## DATABASE SCHEMA REFERENCE:

{reference_docs}
"""


def extract_tool_call(response_text: str) -> Optional[Dict[str, Any]]:
    """Extract tool call from AI response."""
    # Try to find JSON in the response
    # Pattern 1: ```json ... ```
    json_match = re.search(r'```json\s*\n?(.*?)\n?```', response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except:
            pass
    
    # Pattern 2: Direct JSON object
    json_match = re.search(r'\{[^{}]*"tool"[^{}]*\}', response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except:
            pass
    
    # Pattern 3: Look for tool name pattern
    tool_match = re.search(r'"tool"\s*:\s*"(\w+)"', response_text)
    if tool_match:
        tool_name = tool_match.group(1)
        args_match = re.search(r'"args"\s*:\s*(\{[^}]*\})', response_text)
        args = {}
        if args_match:
            try:
                args = json.loads(args_match.group(1))
            except:
                pass
        return {"tool": tool_name, "args": args}
    
    return None


class AgentChatRequest(BaseModel):
    """Request model for agent chat."""
    messages: List[Dict[str, str]]
    model: Optional[str] = "gpt-oss:120b"
    max_iterations: Optional[int] = 10


@router.post("/mcp/agent")
async def agent_chat(
    request: Request,
    body: AgentChatRequest,
    _admin: str = Depends(require_admin)
):
    """
    MCP Agent endpoint - AI decides which tools to call.
    
    This implements a true agent loop:
    1. AI analyzes question
    2. AI decides to call a tool
    3. Tool is executed, result returned to AI
    4. Repeat until AI calls final_answer
    """
    api_key = os.getenv("AI_API_KEY", "")
    api_url = os.getenv("AI_API_URL", "https://api.toka.ngrok.app")
    
    if not api_key:
        return {"error": "AI API key not configured"}
    
    messages = body.messages
    user_message = messages[-1].get("content", "") if messages else ""
    
    # Build conversation with system prompt
    system_prompt = build_system_prompt()
    conversation = [
        {"role": "system", "content": system_prompt},
    ]
    
    # Add previous messages
    for m in messages:
        conversation.append({
            "role": m.get("role", "user"),
            "content": m.get("content", "")
        })
    
    # Agent loop
    iterations = 0
    max_iterations = body.max_iterations or 10
    tool_results = []
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            
            while iterations < max_iterations:
                iterations += 1
                logger.info(f"=== Agent Iteration {iterations} ===")
                
                # Call AI
                payload = {
                    "messages": conversation,
                    "model": body.model or "gpt-oss:120b"
                }
                
                response = await client.post(
                    f"{api_url}/api/chat",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code != 200:
                    return {"error": f"AI API error: {response.text}"}
                
                ai_response = response.json()
                ai_content = ai_response.get("message", {}).get("content", "")
                
                logger.info(f"AI Response: {ai_content[:500]}...")
                
                # Extract tool call
                tool_call = extract_tool_call(ai_content)
                
                if not tool_call:
                    # No tool call found - might be final answer without proper format
                    logger.warning("No tool call found in response")
                    return {
                        "response": {"message": {"content": ai_content}},
                        "iterations": iterations,
                        "tool_calls": tool_results,
                    }
                
                tool_name = tool_call.get("tool")
                tool_args = tool_call.get("args", {})
                
                logger.info(f"Tool Call: {tool_name} with args: {tool_args}")
                
                # Check if it's final answer
                if tool_name == "final_answer":
                    final_answer = tool_args.get("answer", ai_content)
                    return {
                        "response": {"message": {"content": final_answer}},
                        "iterations": iterations,
                        "tool_calls": tool_results,
                    }
                
                # Execute tool
                if tool_name not in TOOL_EXECUTORS:
                    tool_result = {"error": f"Unknown tool: {tool_name}"}
                else:
                    executor = TOOL_EXECUTORS[tool_name]
                    tool_result = await executor(tool_args)
                
                tool_results.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result_summary": {
                        "success": tool_result.get("success"),
                        "count": tool_result.get("total_count") or tool_result.get("total_members") or len(tool_result.get("projects", [])),
                    }
                })
                
                # Add AI response and tool result to conversation
                conversation.append({
                    "role": "assistant",
                    "content": ai_content
                })
                conversation.append({
                    "role": "user",
                    "content": f"Tool result for {tool_name}:\n```json\n{json.dumps(tool_result, indent=2, default=str, ensure_ascii=False)[:4000]}\n```\n\nAnalyze this data and either call another tool if needed or use final_answer to respond."
                })
            
            # Max iterations reached
            return {
                "response": {"message": {"content": "Maximum iterations reached. Please try a simpler question."}},
                "iterations": iterations,
                "tool_calls": tool_results,
            }
    
    except Exception as e:
        logger.error(f"Agent error: {e}")
        return {"error": str(e)}


# ============================================================================
# Simple test endpoint
# ============================================================================

@router.get("/mcp/agent/tools")
async def list_agent_tools():
    """List available agent tools."""
    return {
        "tools": [
            {
                "name": t["name"],
                "description": t["description"],
                "parameters": list(t["parameters"].get("properties", {}).keys())
            }
            for t in TOOLS
        ]
    }


# ============================================================================
# Test endpoint (no auth required) - FOR DEVELOPMENT ONLY
# ============================================================================

def analyze_question(question: str) -> Dict[str, Any]:
    """Analyze user question to determine what data to fetch."""
    q_lower = question.lower()
    
    result = {
        "needs_github": False,
        "needs_slack": False,
        "needs_notion": False,
        "needs_drive": False,
        "needs_recordings": False,
        "needs_members": False,
        "needs_projects": False,
        "start_date": None,
        "end_date": None,
        "project_key": None,
        "member_name": None,
    }
    
    # Determine what data is needed
    if any(word in q_lower for word in ["github", "commit", "pr", "pull request", "코드", "커밋", "개발", "contribution"]):
        result["needs_github"] = True
    
    if any(word in q_lower for word in ["slack", "message", "메시지", "communication", "소통", "채팅"]):
        result["needs_slack"] = True
    
    if any(word in q_lower for word in ["notion", "노션", "document", "문서", "page", "페이지"]):
        result["needs_notion"] = True
    
    if any(word in q_lower for word in ["drive", "드라이브", "google", "구글", "file", "파일"]):
        result["needs_drive"] = True
    
    if any(word in q_lower for word in ["recording", "녹음", "녹화", "회의", "meeting", "zoom", "transcript"]):
        result["needs_recordings"] = True
    
    if any(word in q_lower for word in ["member", "team", "멤버", "팀", "contributor", "활동", "activity", "요약", "summary", "전체", "all"]):
        result["needs_github"] = True
        result["needs_slack"] = True
        result["needs_members"] = True
    
    if any(word in q_lower for word in ["project", "프로젝트", "ooo", "eco", "syb", "trh"]):
        result["needs_projects"] = True
    
    # Determine date range
    now = datetime.utcnow()
    
    if "지난 달" in q_lower or "last month" in q_lower or "저번 달" in q_lower:
        last_month_end = now.replace(day=1) - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        result["start_date"] = last_month_start.strftime("%Y-%m-%d")
        result["end_date"] = last_month_end.strftime("%Y-%m-%d")
    elif "이번 달" in q_lower or "this month" in q_lower:
        result["start_date"] = now.replace(day=1).strftime("%Y-%m-%d")
        result["end_date"] = now.strftime("%Y-%m-%d")
    elif "지난 주" in q_lower or "last week" in q_lower:
        result["start_date"] = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        result["end_date"] = now.strftime("%Y-%m-%d")
    elif "이번 주" in q_lower or "this week" in q_lower:
        result["start_date"] = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        result["end_date"] = now.strftime("%Y-%m-%d")
    elif "지난 분기" in q_lower or "last quarter" in q_lower or "q4" in q_lower:
        result["start_date"] = "2025-10-01"
        result["end_date"] = "2025-12-31"
    elif any(word in q_lower for word in ["2025-12", "12월", "december"]):
        result["start_date"] = "2025-12-01"
        result["end_date"] = "2025-12-31"
    else:
        # Default: last 30 days
        result["start_date"] = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        result["end_date"] = now.strftime("%Y-%m-%d")
    
    return result


@router.post("/mcp/agent/test")
async def agent_chat_test(
    request: Request,
    body: AgentChatRequest,
):
    """
    Test endpoint for MCP Agent - NO AUTH REQUIRED.
    WARNING: This should be disabled in production!
    
    This version pre-fetches data based on question analysis,
    since the AI model doesn't reliably call tools.
    """
    # Check if we're in development mode
    is_dev = os.getenv("ENVIRONMENT", "development") != "production"
    if not is_dev:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Test endpoint disabled in production")
    
    api_key = os.getenv("AI_API_KEY", "")
    api_url = os.getenv("AI_API_URL", "https://api.toka.ngrok.app")
    
    if not api_key:
        return {"error": "AI API key not configured"}
    
    messages = body.messages
    user_message = messages[-1].get("content", "") if messages else ""
    
    logger.info(f"=== Test Agent Request ===")
    logger.info(f"Question: {user_message}")
    
    # PRE-FETCH DATA based on question analysis
    analysis = analyze_question(user_message)
    logger.info(f"Question Analysis: {analysis}")
    
    pre_fetched_data = {}
    
    # Fetch GitHub data if needed
    if analysis["needs_github"]:
        github_result = await execute_get_github_activities({
            "start_date": analysis["start_date"],
            "end_date": analysis["end_date"],
            "project_key": analysis.get("project_key"),
            "limit": 500,
        })
        pre_fetched_data["github"] = github_result
        logger.info(f"Pre-fetched GitHub: {github_result.get('total_count', 0)} activities")
    
    # Fetch Slack data if needed
    if analysis["needs_slack"]:
        slack_result = await execute_get_slack_messages({
            "start_date": analysis["start_date"],
            "end_date": analysis["end_date"],
            "project_key": analysis.get("project_key"),
            "limit": 500,
        })
        pre_fetched_data["slack"] = slack_result
        logger.info(f"Pre-fetched Slack: {slack_result.get('total_count', 0)} messages")
    
    # Fetch Notion data if needed
    if analysis["needs_notion"]:
        notion_result = await execute_query_database({
            "data_type": "notion",
            "start_date": analysis["start_date"],
            "end_date": analysis["end_date"],
            "limit": 200,
        })
        pre_fetched_data["notion"] = notion_result
        logger.info(f"Pre-fetched Notion: {notion_result.get('total_count', 0)} pages")
    
    # Fetch Drive data if needed
    if analysis["needs_drive"]:
        drive_result = await execute_query_database({
            "data_type": "drive",
            "start_date": analysis["start_date"],
            "end_date": analysis["end_date"],
            "limit": 200,
        })
        pre_fetched_data["drive"] = drive_result
        logger.info(f"Pre-fetched Drive: {drive_result.get('total_count', 0)} activities")
    
    # Fetch Recordings data if needed
    if analysis["needs_recordings"]:
        recordings_result = await execute_query_database({
            "data_type": "recordings",
            "start_date": analysis["start_date"],
            "end_date": analysis["end_date"],
            "limit": 200,
        })
        pre_fetched_data["recordings"] = recordings_result
        logger.info(f"Pre-fetched Recordings: {recordings_result.get('total_count', 0)}")
    
    # Fetch member list if needed
    if analysis["needs_members"]:
        member_result = await execute_get_member_list({})
        pre_fetched_data["members"] = member_result
        logger.info(f"Pre-fetched Members: {member_result.get('total_members', 0)}")
    
    # Fetch project info if needed
    if analysis["needs_projects"]:
        project_result = await execute_get_project_info({"project_key": analysis.get("project_key")})
        pre_fetched_data["projects"] = project_result
        logger.info(f"Pre-fetched Projects: {len(project_result.get('projects', []))}")
    
    # Build analysis-focused prompt with pre-fetched data
    now = datetime.utcnow()
    member_names = get_all_member_names()
    
    data_summary = f"""## Pre-fetched Data for Analysis

### Date Range: {analysis["start_date"]} ~ {analysis["end_date"]}
"""
    
    if "github" in pre_fetched_data:
        gh = pre_fetched_data["github"]
        data_summary += f"""
### GitHub Activity ({gh.get('total_count', 0)} commits found):
**By Member:**
{json.dumps(gh.get('member_summary', {}), indent=2, ensure_ascii=False)}
"""
    
    if "slack" in pre_fetched_data:
        sl = pre_fetched_data["slack"]
        data_summary += f"""
### Slack Messages ({sl.get('total_count', 0)} messages found):
**By Member:**
{json.dumps(sl.get('member_summary', {}), indent=2, ensure_ascii=False)}
"""
    
    if "notion" in pre_fetched_data:
        notion = pre_fetched_data["notion"]
        data_summary += f"""
### Notion Pages ({notion.get('total_count', 0)} pages found):
**By Member:**
{json.dumps(notion.get('by_member', {}), indent=2, ensure_ascii=False)}
"""
    
    if "drive" in pre_fetched_data:
        drive = pre_fetched_data["drive"]
        data_summary += f"""
### Google Drive Activity ({drive.get('total_count', 0)} activities found):
**By Member:**
{json.dumps(drive.get('by_member', {}), indent=2, ensure_ascii=False)}
"""
    
    if "recordings" in pre_fetched_data:
        rec = pre_fetched_data["recordings"]
        data_summary += f"""
### Meeting Recordings ({rec.get('total_count', 0)} recordings found):
**By Member:**
{json.dumps(rec.get('by_member', {}), indent=2, ensure_ascii=False)}
"""
    
    if "members" in pre_fetched_data:
        mem = pre_fetched_data["members"]
        data_summary += f"""
### Team Members ({mem.get('total_members', 0)} total):
{', '.join([m.get('name', '') for m in mem.get('members', [])])}
"""
    
    system_prompt = f"""You are a data analyst for All-Thing-Eye team analytics platform.

## Current Date: {now.strftime("%Y-%m-%d")}

## Team Members (ONLY use these names):
{', '.join(member_names)}

{data_summary}

## Your Task:
Analyze the data above and answer the user's question.

## Rules:
1. ONLY use the member names listed above
2. ONLY use the numbers from the data provided
3. Create a nice markdown table for summaries
4. Use Korean if user asks in Korean
5. For members not in the data, show 0 activity
6. Rank by total activity (GitHub + Slack)

## Example Output Format:
| # | 멤버 | GitHub 커밋 | Slack 메시지 | 총 활동 |
|---|-----|-----------|-------------|---------|
| 1 | Jake | 32 | 41 | 73 |
| 2 | Ale | 27 | 35 | 62 |
...
"""

    conversation = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            
            payload = {
                "messages": conversation,
                "model": body.model or "gpt-oss:120b"
            }
            
            logger.info(f"📤 Calling AI for analysis...")
            
            response = await client.post(
                f"{api_url}/api/chat",
                json=payload,
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"AI API error: {response.text[:500]}")
                return {"error": f"AI API error: {response.text[:500]}"}
            
            ai_response = response.json()
            
            # Extract content
            ai_content = ""
            if "message" in ai_response:
                msg = ai_response["message"]
                if isinstance(msg, dict):
                    ai_content = msg.get("content", "")
                elif isinstance(msg, str):
                    ai_content = msg
            elif "response" in ai_response:
                ai_content = ai_response.get("response", "")
            elif "content" in ai_response:
                ai_content = ai_response.get("content", "")
            
            logger.info(f"✅ AI Response: {len(ai_content)} chars")
            
            return {
                "response": {"message": {"content": ai_content}},
                "iterations": 1,
                "data_fetched": {
                    "github_count": pre_fetched_data.get("github", {}).get("total_count", 0),
                    "slack_count": pre_fetched_data.get("slack", {}).get("total_count", 0),
                    "date_range": f"{analysis['start_date']} ~ {analysis['end_date']}",
                },
                "analysis": analysis,
            }
    
    except Exception as e:
        logger.error(f"Agent error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "traceback": traceback.format_exc()}

