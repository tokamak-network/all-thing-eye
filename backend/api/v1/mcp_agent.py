"""
MCP Agent - Refactored for gpt-oss:120b
Enhanced with strict Thought/Action parsing and data summarization handling.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
import json
import re
import httpx
import os
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

from src.utils.logger import get_logger
from backend.api.v1.auth import require_admin
from backend.api.v1.mcp_utils import (
    get_mongo,
    fetch_github_activities,
    fetch_slack_messages,
    github_to_member_name,
    slack_to_member_name,
)
from bson import ObjectId


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, ObjectId):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


logger = get_logger(__name__)
router = APIRouter()

# Load environment
env_path = Path(__file__).parent.parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=False)

# ============================================================================
# Tool Definitions
# ============================================================================

TOOLS = [
    {
        "name": "get_team_members",
        "description": "Get a list of all team members and their roles. Use this first to identify real people.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_projects",
        "description": "Get a list of all projects and their leads.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_project_details",
        "description": "Get detailed information about a specific project including grant reports, milestones, and progress summary. Use this when asked about project progress, grant reports, or milestones.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_key": {
                    "type": "string",
                    "description": "Project key (e.g., 'eco', 'price-api')",
                },
                "include_reports": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include grant reports",
                },
                "include_milestones": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include milestones",
                },
            },
            "required": ["project_key"],
        },
    },
    {
        "name": "get_activities",
        "description": "Fetch summarized activities from GitHub and Slack. Recommended for general activity questions.",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": ["github", "slack", "all"],
                    "description": "Data source",
                },
                "member_name": {
                    "type": "string",
                    "description": "Filter by member name (optional)",
                },
                "project_key": {
                    "type": "string",
                    "description": "Filter by project key (optional)",
                },
                "start_date": {
                    "type": "string",
                    "description": "ISO format date, e.g., '2025-12-01' (optional)",
                },
                "end_date": {
                    "type": "string",
                    "description": "ISO format date (optional)",
                },
                "limit": {"type": "integer", "default": 500},
            },
            "required": ["source"],
        },
    },
    {
        "name": "get_code_stats",
        "description": "Get code change statistics (lines added/deleted) from GitHub commits. Use this for questions about code contributions, lines of code, additions, deletions, or code volume. Returns total additions/deletions, daily breakdown, top contributors by code volume, and top repositories.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format (optional, defaults to last 30 days)",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format (optional)",
                },
            },
        },
    },
    {
        "name": "final_answer",
        "description": "Provide the final answer to the user. Use this ONLY after you have gathered all data.",
        "parameters": {
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": "The final user-facing answer in Markdown.",
                }
            },
            "required": ["answer"],
        },
    },
]

# ============================================================================
# Tool Executors
# ============================================================================


class MCPToolManager:
    @staticmethod
    async def get_team_members(args: Dict[str, Any]) -> Dict[str, Any]:
        db = get_mongo().db
        members = list(
            db["members"].find({}, {"_id": 0, "name": 1, "role": 1, "projects": 1})
        )
        return {"success": True, "data": {"members": members}}

    @staticmethod
    async def get_projects(args: Dict[str, Any]) -> Dict[str, Any]:
        db = get_mongo().db
        projects = list(
            db["projects"].find({}, {"_id": 0, "key": 1, "name": 1, "lead": 1})
        )
        return {"success": True, "data": {"projects": projects}}

    @staticmethod
    async def get_project_details(args: Dict[str, Any]) -> Dict[str, Any]:
        db = get_mongo().db
        project_key = args.get("project_key", "").lower()
        include_reports = args.get("include_reports", True)
        include_milestones = args.get("include_milestones", True)

        # Build projection
        projection = {
            "_id": 0,
            "key": 1,
            "name": 1,
            "lead": 1,
            "overall_summary": 1,
            "progress_trend": 1,
        }
        if include_reports:
            projection["grant_reports"] = 1
        if include_milestones:
            projection["milestones_data"] = 1

        project = db["projects"].find_one({"key": project_key}, projection)

        if not project:
            return {"success": False, "error": f"Project '{project_key}' not found"}

        return {"success": True, "data": project}

    @staticmethod
    async def get_activities(args: Dict[str, Any]) -> Dict[str, Any]:
        db = get_mongo().db
        source = args.get("source", "all").lower()
        member_name = args.get("member_name")
        project_key = args.get("project_key")
        limit = args.get("limit", 500)

        start_dt = None
        if args.get("start_date"):
            try:
                start_dt = datetime.fromisoformat(
                    args["start_date"].replace("Z", "+00:00")
                )
            except:
                start_dt = datetime.strptime(args["start_date"], "%Y-%m-%d")

        end_dt = None
        if args.get("end_date"):
            try:
                end_dt = datetime.fromisoformat(args["end_date"].replace("Z", "+00:00"))
            except:
                end_dt = datetime.strptime(args["end_date"], "%Y-%m-%d")

        results = {}
        if source in ["github", "all"]:
            results["github"] = await fetch_github_activities(
                db, start_dt, end_dt, member_name, project_key, limit
            )
        if source in ["slack", "all"]:
            results["slack"] = await fetch_slack_messages(
                db, start_dt, end_dt, member_name, project_key, limit
            )

        return {"success": True, "data": results}

    @staticmethod
    async def get_code_stats(args: Dict[str, Any]) -> Dict[str, Any]:
        """Get code change statistics from GitHub commits."""
        db = get_mongo().db

        # Parse date range
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=30)  # Default: last 30 days

        if args.get("start_date"):
            try:
                start_dt = datetime.strptime(args["start_date"], "%Y-%m-%d")
            except:
                pass

        if args.get("end_date"):
            try:
                end_dt = datetime.strptime(args["end_date"], "%Y-%m-%d")
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
            except:
                pass

        # Build date filter
        date_filter = {"date": {"$gte": start_dt, "$lte": end_dt}}

        # GitHub username to member name mapping
        github_to_member = {}
        github_identifiers = list(db["member_identifiers"].find({"source": "github"}))
        for ident in github_identifiers:
            member_id = ident.get("member_id")
            github_username = ident.get("identifier_value", "").lower()
            if member_id and github_username:
                member = db["members"].find_one({"_id": ObjectId(member_id)})
                if member:
                    github_to_member[github_username] = member.get("name", github_username)

        # Aggregate total stats
        total_pipeline = [
            {"$match": date_filter},
            {"$group": {
                "_id": None,
                "additions": {"$sum": "$additions"},
                "deletions": {"$sum": "$deletions"},
                "commits": {"$sum": 1}
            }}
        ]
        total_result = list(db["github_commits"].aggregate(total_pipeline))
        total = total_result[0] if total_result else {"additions": 0, "deletions": 0, "commits": 0}

        # Aggregate by member
        member_pipeline = [
            {"$match": date_filter},
            {"$group": {
                "_id": "$author_name",
                "additions": {"$sum": "$additions"},
                "deletions": {"$sum": "$deletions"},
                "commits": {"$sum": 1}
            }},
            {"$sort": {"additions": -1}},
            {"$limit": 10}
        ]
        member_results = list(db["github_commits"].aggregate(member_pipeline))
        by_member = []
        for m in member_results:
            github_username = (m["_id"] or "").lower()
            member_name = github_to_member.get(github_username, m["_id"])
            by_member.append({
                "name": member_name,
                "additions": m["additions"],
                "deletions": m["deletions"],
                "commits": m["commits"]
            })

        # Aggregate by repository
        repo_pipeline = [
            {"$match": date_filter},
            {"$group": {
                "_id": "$repository",
                "additions": {"$sum": "$additions"},
                "deletions": {"$sum": "$deletions"},
                "commits": {"$sum": 1}
            }},
            {"$sort": {"additions": -1}},
            {"$limit": 10}
        ]
        repo_results = list(db["github_commits"].aggregate(repo_pipeline))
        by_repository = [
            {
                "name": r["_id"],
                "additions": r["additions"],
                "deletions": r["deletions"],
                "commits": r["commits"]
            }
            for r in repo_results
        ]

        return {
            "success": True,
            "data": {
                "period": {
                    "start": start_dt.strftime("%Y-%m-%d"),
                    "end": end_dt.strftime("%Y-%m-%d")
                },
                "total": {
                    "additions": total.get("additions", 0),
                    "deletions": total.get("deletions", 0),
                    "commits": total.get("commits", 0),
                    "net_change": total.get("additions", 0) - total.get("deletions", 0)
                },
                "top_contributors": by_member,
                "top_repositories": by_repository
            }
        }


TOOL_EXECUTOR_MAP = {
    "get_team_members": MCPToolManager.get_team_members,
    "get_projects": MCPToolManager.get_projects,
    "get_project_details": MCPToolManager.get_project_details,
    "get_activities": MCPToolManager.get_activities,
    "get_code_stats": MCPToolManager.get_code_stats,
}

# ============================================================================
# Core Agent Logic
# ============================================================================


def build_system_prompt() -> str:
    # Use KST (Korea Standard Time, UTC+9) as the reference timezone
    from datetime import timezone

    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    today = now.strftime("%Y-%m-%d")

    # Calculate explicit date ranges for common relative terms
    # "Today"
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)

    # "Yesterday"
    yesterday = now - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    # "This week" (Monday to Sunday)
    days_since_monday = now.weekday()  # Monday = 0
    this_week_start = (now - timedelta(days=days_since_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    this_week_end = (this_week_start + timedelta(days=6)).replace(
        hour=23, minute=59, second=59, microsecond=0
    )

    # "Last week" (Previous Monday to Sunday)
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start - timedelta(seconds=1)  # Sunday 23:59:59

    # "This month"
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # "Last month"
    last_month_end = this_month_start - timedelta(seconds=1)
    last_month_start = last_month_end.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    # Pre-fetch actual members for grounding
    db = get_mongo().db
    members = [m["name"] for m in db["members"].find({}, {"name": 1})]
    member_list = ", ".join(members)

    return f"""You are the All-Thing-Eye Analytics Specialist.
Your mission is to provide deep, accurate insights into team productivity, project progress, grant reports, and milestones.

## CORE PRINCIPLES
1. **NO HALLUCINATION**: If tool data is missing or empty, state "No data available". Never invent facts.
2. **STRICT FORMATTING**: You MUST use the Thought/Action pattern for every turn.
3. **REAL MEMBERS ONLY**: Use ONLY these names: {member_list}.
4. **INTEGRATED ANALYSIS**: When asked for "activity", always combine GitHub commits and Slack messages.
5. **ENGLISH OUTPUT**: Always respond to the user in English. Keep internal Thoughts in English as well.

## RESPONSE PROTOCOL
Thought: <Detailed plan or data analysis>
Action: ```json
{{
  "tool": "tool_name",
  "args": {{"param": "value"}}
}}
```

Wait for the "Observation" before continuing.
When the analysis is complete, use the "final_answer" tool.

## AVAILABLE TOOLS
{json.dumps(TOOLS, indent=2)}

## CURRENT DATE AND TIME REFERENCE (KST - Korea Standard Time)
**Today**: {today} (KST)
**Current Time**: {now.strftime("%Y-%m-%d %H:%M:%S")} KST

## DATE RANGES FOR RELATIVE TERMS (USE THESE EXACT DATES)
When the user mentions relative time expressions, use these exact date ranges:

| Term | Start Date | End Date |
|------|------------|----------|
| "today", "오늘" | {today} | {today} |
| "yesterday", "어제" | {yesterday_str} | {yesterday_str} |
| "this week", "이번 주", "이번주" | {this_week_start.strftime("%Y-%m-%d")} | {this_week_end.strftime("%Y-%m-%d")} |
| "last week", "지난 주", "지난주", "저번 주", "저번주" | {last_week_start.strftime("%Y-%m-%d")} | {last_week_end.strftime("%Y-%m-%d")} |
| "this month", "이번 달", "이번달" | {this_month_start.strftime("%Y-%m-%d")} | {today} |
| "last month", "지난 달", "지난달", "저번 달", "저번달" | {last_month_start.strftime("%Y-%m-%d")} | {last_month_end.strftime("%Y-%m-%d")} |

**IMPORTANT**: Always use the dates from the table above. Do NOT calculate dates yourself.
"""


def parse_agent_response(text: str) -> Dict[str, Any]:
    """Extremely robust extraction of Thought and Action."""
    result = {"thought": "", "action": None}

    # 1. Try to find Thought
    thought_match = re.search(
        r"Thought:\s*(.*?)(?=Action:|$)", text, re.DOTALL | re.IGNORECASE
    )
    if thought_match:
        result["thought"] = thought_match.group(1).strip()

    # 2. Try to find Action (JSON)
    # Search for any JSON block first
    json_blocks = re.findall(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if json_blocks:
        try:
            result["action"] = json.loads(json_blocks[-1])  # Use the last JSON block
        except:
            pass

    # If no code block, try searching for raw JSON structure
    if not result["action"]:
        raw_json_match = re.search(r'\{\s*"tool"\s*:.*\}', text, re.DOTALL)
        if raw_json_match:
            try:
                result["action"] = json.loads(raw_json_match.group(0))
            except:
                pass

    return result


class AgentRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: Optional[str] = (
        "qwen3-235b"  # Model: qwen3-235b, Context Window: 131072 tokens
    )
    max_iterations: int = 10


@router.post("/mcp/agent")
@router.post("/mcp/agent/test")
async def run_mcp_agent(body: AgentRequest, _admin: Any = None):
    # Check environment for test endpoint
    is_test = "/test" in str(Request.url) if hasattr(Request, "url") else False
    if is_test and os.getenv("ENVIRONMENT") == "production":
        raise HTTPException(
            status_code=403, detail="Test endpoint disabled in production"
        )

    api_key = os.getenv("AI_API_KEY", "").strip()
    api_url = os.getenv("AI_API_URL", "https://api.ai.tokamak.network").strip()

    if not api_key:
        raise HTTPException(status_code=500, detail="AI API key not configured")

    # Debug logging (mask API key for security)
    logger.info(f"🔑 Using AI API URL: {api_url}")
    logger.info(
        f"🔑 API Key loaded: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '***'} (length: {len(api_key)})"
    )

    conversation = [{"role": "system", "content": build_system_prompt()}]
    for m in body.messages:
        conversation.append({"role": m["role"], "content": m["content"]})

    iterations = 0
    tool_history = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        logger.info(f"📤 Request URL: {api_url}/v1/chat/completions")
        logger.info(f"📤 Request headers: Authorization: Bearer {api_key[:10]}...")

        while iterations < body.max_iterations:
            iterations += 1
            logger.info(f"Iteration {iterations} for model {body.model}")

            # Step 1: AI Reason & Act
            try:
                resp = await client.post(
                    f"{api_url}/v1/chat/completions",
                    json={
                        "model": body.model,
                        "messages": conversation,
                        "temperature": 0.1,
                    },
                    headers=headers,
                )
                if resp.status_code != 200:
                    logger.error(
                        f"❌ AI API Error: Status {resp.status_code}, Response: {resp.text}"
                    )
                    raise Exception(f"AI API Error: {resp.text}")

                ai_data = resp.json()
                # OpenAI format: choices[0].message.content
                ai_text = (
                    ai_data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )

                # Step 2: Parse
                parsed = parse_agent_response(ai_text)
                conversation.append({"role": "assistant", "content": ai_text})

                if not parsed["action"]:
                    # Fallback if AI forgets format but provides answer
                    if iterations > 1:  # Only fallback if it's not the first turn
                        return {
                            "answer": ai_text,
                            "iterations": iterations,
                            "history": tool_history,
                        }
                    # If first turn and no action, prompt it again
                    conversation.append(
                        {
                            "role": "user",
                            "content": "Please follow the protocol: Thought then Action (JSON).",
                        }
                    )
                    continue

                tool_name = parsed["action"].get("tool")
                tool_args = parsed["action"].get("args", {})

                # Step 3: Handle Final Answer
                if tool_name == "final_answer":
                    final_text = tool_args.get("answer", ai_text)
                    return {
                        "answer": final_text,
                        "iterations": iterations,
                        "history": tool_history,
                    }

                # Step 4: Execute Tool
                if tool_name not in TOOL_EXECUTOR_MAP:
                    observation = {"error": f"Tool '{tool_name}' not found."}
                else:
                    obs_data = await TOOL_EXECUTOR_MAP[tool_name](tool_args)
                    observation = obs_data.get("data", obs_data)

                tool_history.append(
                    {
                        "tool": tool_name,
                        "args": tool_args,
                        "success": "error" not in observation,
                    }
                )

                # Step 5: Feed back to AI
                conversation.append(
                    {
                        "role": "user",
                        "content": f"Observation: {json.dumps(observation, ensure_ascii=False, default=json_serial)}",
                    }
                )

            except Exception as e:
                logger.error(f"Agent error at iteration {iterations}: {e}")
                return {
                    "error": str(e),
                    "iterations": iterations,
                    "history": tool_history,
                }

    return {
        "answer": "죄송합니다. 최대 시도 횟수에 도달하여 답변을 드릴 수 없습니다.",
        "iterations": iterations,
        "history": tool_history,
    }
