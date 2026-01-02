"""
MCP API Endpoints

HTTP wrapper for MCP server functionality.
Allows web clients to interact with MCP resources, tools, and prompts.
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import get_logger
from backend.middleware.jwt_auth import require_admin

logger = get_logger(__name__)

router = APIRouter()


def get_mongo():
    """Get MongoDB manager from main app"""
    from backend.main import mongo_manager
    return mongo_manager


# ============================================================================
# Request/Response Models
# ============================================================================

class ToolCallRequest(BaseModel):
    """Request to call an MCP tool"""
    name: str
    arguments: Dict[str, Any] = {}


class PromptRequest(BaseModel):
    """Request to get an MCP prompt"""
    name: str
    arguments: Optional[Dict[str, str]] = None


class ChatWithContextRequest(BaseModel):
    """Chat request with automatic context injection"""
    messages: List[Dict[str, str]]
    model: Optional[str] = None
    context_hints: Optional[Dict[str, Any]] = None  # e.g., {"project": "ooo", "member": "Jake"}


# ============================================================================
# Resources Endpoints
# ============================================================================

@router.get("/mcp/resources")
async def list_resources(
    request: Request,
    _admin: str = Depends(require_admin)
):
    """List all available MCP resources"""
    return {
        "resources": [
            {
                "uri": "ate://members",
                "name": "Team Members",
                "description": "List of all team members with their roles and project assignments"
            },
            {
                "uri": "ate://projects",
                "name": "Projects",
                "description": "List of all projects with repositories and team members"
            },
            {
                "uri": "ate://activities/summary",
                "name": "Activity Summary",
                "description": "Summary of recent activities across all sources"
            },
            {
                "uri": "ate://github/stats",
                "name": "GitHub Statistics",
                "description": "GitHub commit and PR statistics"
            },
            {
                "uri": "ate://slack/stats",
                "name": "Slack Statistics",
                "description": "Slack message statistics by channel and member"
            },
        ]
    }


@router.get("/mcp/resources/{resource_path:path}")
async def read_resource(
    resource_path: str,
    request: Request,
    _admin: str = Depends(require_admin)
):
    """Read a specific MCP resource"""
    db = get_mongo().db
    uri = f"ate://{resource_path}"
    
    try:
        if uri == "ate://members":
            members = list(db['members'].find({}, {
                '_id': 0, 'name': 1, 'email': 1, 'role': 1, 
                'projects': 1, 'github_username': 1, 'slack_id': 1
            }))
            return {"uri": uri, "data": members}
        
        elif uri == "ate://projects":
            projects = list(db['projects'].find({}, {
                '_id': 0, 'key': 1, 'name': 1, 'description': 1,
                'lead': 1, 'repositories': 1, 'slack_channel': 1, 'is_active': 1
            }))
            return {"uri": uri, "data": projects}
        
        elif uri == "ate://activities/summary":
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            summary = {
                "period": "last_30_days",
                "github_commits": db['github_commits'].count_documents({
                    'date': {'$gte': thirty_days_ago}
                }),
                "github_prs": db['github_pull_requests'].count_documents({
                    'created_at': {'$gte': thirty_days_ago}
                }),
                "slack_messages": db['slack_messages'].count_documents({
                    'posted_at': {'$gte': thirty_days_ago},
                    'channel_name': {'$ne': 'tokamak-partners'}  # Exclude private channel
                }),
                "notion_pages": db['notion_pages'].count_documents({
                    'last_edited_time': {'$gte': thirty_days_ago}
                }),
            }
            return {"uri": uri, "data": summary}
        
        elif uri == "ate://github/stats":
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            pipeline = [
                {'$match': {'date': {'$gte': thirty_days_ago}}},
                {'$group': {
                    '_id': '$author_name',
                    'commits': {'$sum': 1},
                    'additions': {'$sum': '$stats.additions'},
                    'deletions': {'$sum': '$stats.deletions'}
                }},
                {'$sort': {'commits': -1}},
                {'$limit': 20}
            ]
            raw_stats = list(db['github_commits'].aggregate(pipeline))
            
            # Map GitHub usernames to member names
            stats = []
            for s in raw_stats:
                if s['_id']:
                    member_name = _github_to_member_name(db, s['_id'])
                    stats.append({
                        '_id': member_name,
                        'commits': s['commits'],
                        'additions': s.get('additions', 0),
                        'deletions': s.get('deletions', 0)
                    })
            return {"uri": uri, "data": stats}
        
        elif uri == "ate://slack/stats":
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            pipeline = [
                {'$match': {
                    'posted_at': {'$gte': thirty_days_ago},
                    'channel_name': {'$ne': 'tokamak-partners'}  # Exclude private channel
                }},
                {'$group': {
                    '_id': '$user_name',
                    'messages': {'$sum': 1}
                }},
                {'$sort': {'messages': -1}},
                {'$limit': 20}
            ]
            stats = list(db['slack_messages'].aggregate(pipeline))
            return {"uri": uri, "data": stats}
        
        else:
            raise HTTPException(status_code=404, detail=f"Resource not found: {uri}")
    
    except Exception as e:
        logger.error(f"Error reading resource {uri}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Tools Endpoints
# ============================================================================

@router.get("/mcp/tools")
async def list_tools(
    request: Request,
    _admin: str = Depends(require_admin)
):
    """List all available MCP tools"""
    return {
        "tools": [
            {
                "name": "get_member_activity",
                "description": "Get detailed activity statistics for a specific team member",
                "parameters": {
                    "member_name": {"type": "string", "required": True},
                    "days": {"type": "integer", "default": 30}
                }
            },
            {
                "name": "get_project_activity",
                "description": "Get activity statistics for a specific project",
                "parameters": {
                    "project_key": {"type": "string", "required": True},
                    "days": {"type": "integer", "default": 30}
                }
            },
            {
                "name": "get_top_repositories",
                "description": "Get the most active GitHub repositories by commit count",
                "parameters": {
                    "days": {"type": "integer", "default": 30},
                    "limit": {"type": "integer", "default": 10}
                }
            },
            {
                "name": "compare_contributors",
                "description": "Compare activity between multiple team members",
                "parameters": {
                    "member_names": {"type": "array", "required": True},
                    "metric": {"type": "string", "enum": ["commits", "messages", "prs", "all"], "default": "all"},
                    "days": {"type": "integer", "default": 30}
                }
            },
            {
                "name": "get_top_contributors",
                "description": "Get the most active contributors by a specific metric",
                "parameters": {
                    "metric": {"type": "string", "enum": ["commits", "messages", "prs", "reviews"], "required": True},
                    "project_key": {"type": "string"},
                    "days": {"type": "integer", "default": 30},
                    "limit": {"type": "integer", "default": 10}
                }
            },
            {
                "name": "search_activities",
                "description": "Search for activities matching specific criteria",
                "parameters": {
                    "keyword": {"type": "string", "required": True},
                    "source": {"type": "string", "enum": ["github", "slack", "notion", "all"], "default": "all"},
                    "member_name": {"type": "string"},
                    "days": {"type": "integer", "default": 7},
                    "limit": {"type": "integer", "default": 20}
                }
            },
            {
                "name": "get_weekly_summary",
                "description": "Generate a weekly activity summary",
                "parameters": {
                    "project_key": {"type": "string"},
                    "week_offset": {"type": "integer", "default": 0}
                }
            },
        ]
    }


@router.post("/mcp/tools/call")
async def call_tool(
    request: Request,
    body: ToolCallRequest,
    _admin: str = Depends(require_admin)
):
    """Call an MCP tool"""
    db = get_mongo().db
    name = body.name
    args = body.arguments
    
    try:
        if name == "get_member_activity":
            result = await _get_member_activity(db, args)
        elif name == "get_project_activity":
            result = await _get_project_activity(db, args)
        elif name == "compare_contributors":
            result = await _compare_contributors(db, args)
        elif name == "get_top_contributors":
            result = await _get_top_contributors(db, args)
        elif name == "get_top_repositories":
            result = await _get_top_repositories(db, args)
        elif name == "search_activities":
            result = await _search_activities(db, args)
        elif name == "get_weekly_summary":
            result = await _get_weekly_summary(db, args)
        else:
            raise HTTPException(status_code=404, detail=f"Tool not found: {name}")
        
        return {"tool": name, "result": result}
    
    except Exception as e:
        logger.error(f"Error calling tool {name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Prompts Endpoints
# ============================================================================

@router.get("/mcp/prompts")
async def list_prompts(
    request: Request,
    _admin: str = Depends(require_admin)
):
    """List all available MCP prompts"""
    return {
        "prompts": [
            {
                "name": "analyze_contributor",
                "description": "Analyze a specific contributor's activity and provide insights",
                "arguments": {
                    "member_name": {"required": True, "description": "Name of the team member to analyze"},
                    "period": {"required": False, "description": "Analysis period (e.g., 'last week', 'last month')"}
                }
            },
            {
                "name": "project_health_check",
                "description": "Perform a health check on a project's activity",
                "arguments": {
                    "project_key": {"required": True, "description": "Project key to analyze"}
                }
            },
            {
                "name": "weekly_report",
                "description": "Generate a weekly activity report",
                "arguments": {
                    "project_key": {"required": False, "description": "Optional: Project key to focus on"}
                }
            },
            {
                "name": "compare_team",
                "description": "Compare activity across team members",
                "arguments": {
                    "project_key": {"required": False, "description": "Optional: Filter by project"}
                }
            },
        ]
    }


@router.post("/mcp/prompts/get")
async def get_prompt(
    request: Request,
    body: PromptRequest,
    _admin: str = Depends(require_admin)
):
    """Get an MCP prompt with arguments filled in"""
    name = body.name
    arguments = body.arguments or {}
    
    prompts = {
        "analyze_contributor": {
            "template": f"""Analyze the contributions of team member "{arguments.get('member_name', 'Unknown')}" for {arguments.get('period', 'last 30 days')}.

Please provide:
1. **Activity Summary**: Overview of commits, PRs, and Slack messages
2. **Key Contributions**: Notable commits or PRs
3. **Collaboration**: Interaction with other team members
4. **Trends**: Any notable patterns in activity
5. **Recommendations**: Suggestions for the team member""",
            "suggested_tools": ["get_member_activity", "search_activities", "compare_contributors"]
        },
        "project_health_check": {
            "template": f"""Perform a health check on project "{arguments.get('project_key', 'Unknown')}".

Please analyze:
1. **Activity Level**: Is the project active? How many commits/messages?
2. **Team Engagement**: Are all team members contributing?
3. **Code Quality Indicators**: PR review rates, merge times
4. **Communication**: Slack activity, response times
5. **Risks**: Any concerning patterns?
6. **Recommendations**: Actionable suggestions""",
            "suggested_tools": ["get_project_activity", "get_top_contributors", "get_weekly_summary"]
        },
        "weekly_report": {
            "template": f"""Generate a weekly activity report for {f"project {arguments.get('project_key')}" if arguments.get('project_key') else "the entire team"}.

Include:
1. **Executive Summary**: Key highlights in 2-3 sentences
2. **GitHub Activity**: Commits, PRs, notable changes
3. **Slack Activity**: Communication patterns
4. **Top Contributors**: Most active team members
5. **Notable Achievements**: Merged PRs, completed features
6. **Areas of Concern**: Low activity, pending reviews
7. **Next Week Focus**: Recommendations""",
            "suggested_tools": ["get_weekly_summary", "get_top_contributors", "search_activities"]
        },
        "compare_team": {
            "template": f"""Compare team member activity {f"in project {arguments.get('project_key')}" if arguments.get('project_key') else ""}.

Provide:
1. **Activity Rankings**: Who's most active by different metrics
2. **Comparison Chart**: Visual representation of contributions
3. **Collaboration Patterns**: Who works together
4. **Balance Assessment**: Is workload evenly distributed?
5. **Recommendations**: Team optimization suggestions""",
            "suggested_tools": ["get_top_contributors", "compare_contributors", "get_project_activity"]
        }
    }
    
    if name not in prompts:
        raise HTTPException(status_code=404, detail=f"Prompt not found: {name}")
    
    return {
        "name": name,
        "prompt": prompts[name]["template"],
        "suggested_tools": prompts[name]["suggested_tools"]
    }


# ============================================================================
# Question Analysis & Template-Based Data Fetching
# ============================================================================

def _analyze_question(user_message: str) -> dict:
    """Analyze user question to extract parameters for data fetching."""
    from datetime import datetime, timedelta
    
    message_lower = user_message.lower()
    now = datetime.utcnow()
    
    result = {
        "date_range": None,
        "start_date": None,
        "end_date": None,
        "project_key": None,
        "member_name": None,
        "query_type": "activity",  # activity, project, member
    }
    
    # Detect date range
    if "지난 달" in message_lower or "last month" in message_lower:
        last_month_end = now.replace(day=1) - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        result["start_date"] = last_month_start.strftime("%Y-%m-%dT00:00:00Z")
        result["end_date"] = last_month_end.strftime("%Y-%m-%dT23:59:59Z")
        result["date_range"] = f"{last_month_start.strftime('%Y-%m')} (last month)"
    elif "이번 주" in message_lower or "this week" in message_lower:
        week_ago = now - timedelta(days=7)
        result["start_date"] = week_ago.strftime("%Y-%m-%dT00:00:00Z")
        result["date_range"] = "this week (last 7 days)"
    elif "이번 달" in message_lower or "this month" in message_lower:
        month_start = now.replace(day=1)
        result["start_date"] = month_start.strftime("%Y-%m-%dT00:00:00Z")
        result["date_range"] = f"{now.strftime('%Y-%m')} (this month)"
    elif "오늘" in message_lower or "today" in message_lower:
        result["start_date"] = now.strftime("%Y-%m-%dT00:00:00Z")
        result["date_range"] = "today"
    else:
        # Default to last 30 days
        month_ago = now - timedelta(days=30)
        result["start_date"] = month_ago.strftime("%Y-%m-%dT00:00:00Z")
        result["date_range"] = "last 30 days"
    
    # Detect project
    project_keywords = {
        "ooo": "project-ooo",
        "eco": "project-eco",
        "syb": "project-syb",
        "trh": "project-trh",
    }
    for keyword, project_key in project_keywords.items():
        if keyword in message_lower:
            result["project_key"] = project_key
            break
    
    # Detect member names (common names)
    member_names = ["jake", "ale", "zena", "mehdi", "luca", "aamir", "harvey", "jason", "kevin", "thomas"]
    for name in member_names:
        if name in message_lower:
            result["member_name"] = name.capitalize()
            break
    
    # Detect query type
    if "프로젝트" in message_lower or "project" in message_lower:
        if "비교" in message_lower or "compare" in message_lower:
            result["query_type"] = "project_compare"
        else:
            result["query_type"] = "project"
    elif result["member_name"]:
        result["query_type"] = "member"
    
    return result


async def _fetch_activity_data(start_date: str, end_date: str = None, project_key: str = None, member_name: str = None) -> dict:
    """Fetch activity data using hardcoded template query."""
    
    # Build query parts
    github_filters = f'source: GITHUB, startDate: "{start_date}"'
    slack_filters = f'source: SLACK, startDate: "{start_date}"'
    
    if end_date:
        github_filters += f', endDate: "{end_date}"'
        slack_filters += f', endDate: "{end_date}"'
    
    if project_key:
        github_filters += f', projectKey: "{project_key}"'
        slack_filters += f', projectKey: "{project_key}"'
    
    if member_name:
        github_filters += f', memberName: "{member_name}"'
        slack_filters += f', memberName: "{member_name}"'
    
    query = f"""
    query CombinedActivity {{
      github: activities({github_filters}, limit: 500) {{
        memberName
        sourceType
        timestamp
        metadata
      }}
      slack: activities({slack_filters}, limit: 500) {{
        memberName
        sourceType
        timestamp
        metadata
      }}
    }}
    """
    
    return await _execute_graphql_query(query)


async def _fetch_project_data() -> dict:
    """Fetch all projects data."""
    query = """
    query AllProjects {
      projects {
        key
        name
        lead
        repositories
        slackChannel
        isActive
        members {
          name
        }
      }
    }
    """
    return await _execute_graphql_query(query)


# ============================================================================
# Context-Aware Chat Endpoint
# ============================================================================

@router.post("/mcp/chat")
async def chat_with_context(
    request: Request,
    body: ChatWithContextRequest,
    _admin: str = Depends(require_admin)
):
    """
    Chat with AI using template-based data fetching.
    
    This endpoint uses a 2-phase approach:
    1. Analyze question and fetch data using template queries
    2. AI generates final answer with the fetched data
    """
    import httpx
    import os
    from dotenv import load_dotenv
    
    # Load env
    env_path = Path(__file__).parent.parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
    
    db = get_mongo().db
    messages = body.messages
    context_hints = body.context_hints or {}
    
    # Extract user message
    user_message = messages[-1].get("content", "") if messages else ""
    
    api_key = os.getenv("AI_API_KEY", "")
    api_url = os.getenv("AI_API_URL", "https://api.toka.ngrok.app")
    
    if not api_key:
        return {"error": "AI API key not configured"}
    
    try:
        # ========================================
        # PHASE 1: Get data from context or fetch
        # ========================================
        graphql_result = {}
        query_info = ""
        
        # Check if frontend provided raw data directly (from custom export)
        raw_data = context_hints.get("raw_data")
        data_stats = context_hints.get("data_stats")
        selected_fields = context_hints.get("selected_fields", [])
        provided_filters = context_hints.get("filters", {})
        
        if raw_data:
            # Use data provided directly from custom export
            logger.info(f"=== Using Raw Data from Custom Export ===")
            logger.info(f"Data stats: {data_stats}")
            
            # Format data for AI
            graphql_result = {"data": raw_data}
            query_info = f"""# Data from Custom Export UI
# Selected Fields: {', '.join(selected_fields) if selected_fields else 'All'}
# Date Range: {provided_filters.get('startDate', 'N/A')} ~ {provided_filters.get('endDate', 'N/A')}
# Project: {provided_filters.get('project', 'all')}
# Members: {', '.join(provided_filters.get('selectedMembers', [])) or 'All'}
# Total Records: {data_stats.get('total', 0) if data_stats else 'Unknown'}"""
            
            # Skip to AI analysis phase
            data = raw_data
            github_count = len(data.get("activities", [])) if isinstance(data.get("activities"), list) else 0
            slack_count = 0  # Activities are mixed
            logger.info(f"✅ Raw data received: {github_count} activities")
        
        elif context_hints.get("graphql_query"):
            # Check if frontend provided a GraphQL query
            provided_query = context_hints.get("graphql_query")
            # Use the query provided by frontend
            logger.info(f"=== Using Provided Query ===")
            logger.info(f"Query:\n{provided_query}")
            logger.info(f"Selected fields: {selected_fields}")
            
            graphql_result = await _execute_graphql_query(provided_query)
            query_info = f"""# Query from Custom Export UI
# Selected Fields: {', '.join(selected_fields)}
# Date Range: {provided_filters.get('startDate', 'N/A')} ~ {provided_filters.get('endDate', 'N/A')}
# Project: {provided_filters.get('project', 'all')}
# Members: {', '.join(provided_filters.get('selectedMembers', [])) or 'All'}"""
        else:
            # Analyze question and build query automatically
            analysis = _analyze_question(user_message)
            
            logger.info(f"=== Question Analysis ===")
            logger.info(f"Question: {user_message}")
            logger.info(f"Analysis: {analysis}")
            
            # Fetch data based on analysis
            if analysis["query_type"] == "project_compare":
                # Fetch all projects for comparison
                graphql_result = await _fetch_project_data()
                # Also fetch activity for each project
                for project_key in ["project-ooo", "project-eco", "project-syb", "project-trh"]:
                    project_data = await _fetch_activity_data(
                        start_date=analysis["start_date"],
                        end_date=analysis.get("end_date"),
                        project_key=project_key
                    )
                    graphql_result[project_key] = project_data.get("data", {})
            elif analysis["query_type"] == "project" and analysis["project_key"]:
                # Fetch specific project activities
                graphql_result = await _fetch_activity_data(
                    start_date=analysis["start_date"],
                    end_date=analysis.get("end_date"),
                    project_key=analysis["project_key"]
                )
            elif analysis["query_type"] == "member" and analysis["member_name"]:
                # Fetch specific member activities
                graphql_result = await _fetch_activity_data(
                    start_date=analysis["start_date"],
                    end_date=analysis.get("end_date"),
                    member_name=analysis["member_name"]
                )
            else:
                # Default: fetch all activity
                graphql_result = await _fetch_activity_data(
                    start_date=analysis["start_date"],
                    end_date=analysis.get("end_date")
                )
            
            query_info = f"""# Auto-generated Query
# Date Range: {analysis['date_range']}
# Project: {analysis.get('project_key', 'All')}
# Member: {analysis.get('member_name', 'All')}"""
        
        # Log the results
        data = graphql_result.get("data", {})
        github_count = len(data.get("github", [])) if isinstance(data.get("github"), list) else 0
        slack_count = len(data.get("slack", [])) if isinstance(data.get("slack"), list) else 0
        logger.info(f"✅ Data fetched: GitHub={github_count}, Slack={slack_count}")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            
            # ========================================
            # PHASE 2: AI analyzes the fetched data
            # ========================================
            
            # Get context info from query_info (already set in phase 1)
            # Extract from provided_filters if raw_data, otherwise use defaults
            date_range_info = f"{provided_filters.get('startDate', 'N/A')} ~ {provided_filters.get('endDate', 'N/A')}" if provided_filters else "N/A"
            project_info = provided_filters.get('project', 'All') if provided_filters else 'All'
            member_info = ', '.join(provided_filters.get('selectedMembers', [])) if provided_filters and provided_filters.get('selectedMembers') else 'All'
            
            phase2_messages = [
                {"role": "system", "content": f"""You are an AI assistant for All-Thing-Eye, a team activity analytics platform.

You have been provided with REAL data from the team's database. Answer the question based ONLY on this data.
Be specific with names and numbers. If the data doesn't contain enough information, say so clearly.

## Data Context:
- Date Range: {date_range_info}
- Project Filter: {project_info}
- Member Filter: {member_info}

## CRITICAL: Analyze ALL data sources!
The data contains two arrays:
- "github": GitHub activities (commits, PRs, etc.)
- "slack": Slack messages

You MUST:
1. Count activities from BOTH arrays for each member
2. **ADD them together** to get TOTAL activity per member
3. Rank by TOTAL (GitHub + Slack combined), NOT just GitHub alone
4. Show breakdown: "Member X: 50 total (30 GitHub + 20 Slack)"

Example calculation:
- Jake: 100 GitHub + 150 Slack = 250 TOTAL
- Zena: 17 GitHub + 5 Slack = 22 TOTAL
→ Jake is more active (250 > 22)

Format your response clearly with:
- Use markdown tables for comparisons
- Use bullet points for lists
- Highlight key numbers and names
- Keep responses concise but informative"""},
                {"role": "user", "content": f"""Question: {user_message}

{query_info}

Data Retrieved:
```json
{json.dumps(graphql_result, indent=2, default=str)[:12000]}
```

Please analyze this data and answer the question. Remember to count BOTH github AND slack activities!"""}
            ]
            
            # Add conversation history (excluding the last user message which we already included)
            for m in messages[:-1]:
                phase2_messages.insert(1, {"role": m.get("role", "user"), "content": m.get("content", "")})
            
            phase2_payload = {
                "messages": phase2_messages,
                "model": body.model or "gpt-oss:120b"
            }
            
            phase2_response = await client.post(
                f"{api_url}/api/chat",
                json=phase2_payload,
                headers=headers
            )
            
            if phase2_response.status_code != 200:
                return {
                    "error": f"AI API error: {phase2_response.text}",
                    "query_info": query_info,
                    "data": graphql_result
                }
            
            final_response = phase2_response.json()
            
            return {
                "response": final_response,
                "debug": {
                    "analysis": analysis,
                    "github_count": github_count,
                    "slack_count": slack_count,
                    "data_preview": str(graphql_result)[:500]
                }
            }
    
    except Exception as e:
        logger.error(f"MCP chat error: {e}")
        return {
            "error": str(e)
        }


def _get_graphql_schema_prompt() -> str:
    """Return GraphQL schema documentation for AI to generate queries."""
    from datetime import datetime, timedelta
    
    # Calculate dynamic dates
    now = datetime.utcnow()
    today = now.strftime("%Y-%m-%d")
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    month_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    last_month_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1).strftime("%Y-%m-%d")
    last_month_end = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")
    
    return f"""You are a GraphQL query generator for All-Thing-Eye platform.

## CURRENT DATE: {today}
Use this to calculate correct date ranges. Today is {now.strftime("%B %d, %Y")}.

## Available GraphQL Schema:

### Query: activities
Fetches activity records with filtering options.

```graphql
activities(
  source: SourceType          # ⚠️ REQUIRED! Use: GITHUB, SLACK, NOTION, or RECORDINGS
  memberName: String          # Filter by member name (optional)
  keyword: String             # Search keyword (optional)
  projectKey: String          # Filter by project: project-ooo, project-eco, project-syb, project-trh
  startDate: DateTime         # ISO format: "2024-01-01T00:00:00Z"
  endDate: DateTime           # ISO format: "2024-12-31T23:59:59Z"  
  limit: Int                  # Default: 50, Max: 500
  offset: Int                 # For pagination
): [Activity!]!
```

Activity type fields (ONLY these fields exist):
- id: ID!
- memberName: String
- sourceType: String (github_commit, github_pull_request, slack_message, notion_page, recordings)
- timestamp: DateTime
- metadata: JSON (contains source-specific data)

⚠️ NOTE: Activity does NOT have a `projectKey` field! Use the `projectKey` parameter in the query to filter by project.

## ⚠️ CRITICAL RULES (MUST FOLLOW):

### RULE #1: ALWAYS QUERY BOTH GITHUB AND SLACK FOR ACTIVITY QUESTIONS
For ANY question about:
- "most active", "가장 활발한", "활동량"
- "contributor", "기여자"  
- "activity", "활동"
- "busy", "productive"
- General member/project status

You MUST generate a query with TWO aliases:
```graphql
query CombinedActivity {{
  github: activities(source: GITHUB, ...) {{ ... }}
  slack: activities(source: SLACK, ...) {{ ... }}
}}
```

**IF YOU ONLY QUERY GITHUB, YOUR ANSWER IS INCOMPLETE AND WRONG!**

### RULE #2: ALWAYS specify `source` parameter
Never query activities without source filter - it will include broken DRIVE data.

### RULE #3: NEVER use DRIVE
Google Drive data is broken/noisy. Only use: GITHUB, SLACK, NOTION, RECORDINGS

### RULE #4: When to query single source
- ONLY GitHub: Questions specifically about "commits", "code", "PR", "repository"
- ONLY Slack: Questions specifically about "messages", "Slack", "채팅"

### Query: members
```graphql
members(limit: Int, offset: Int): [Member!]!
member(id: ID!): Member
```

Member fields: id, name, email, role, githubUsername, slackId, projectKeys

### Query: projects
```graphql
projects: [Project!]!
project(key: String!): Project
```

Project fields (ONLY these exist - NO `status` field!):
- id: ID!
- key: String! (e.g., "project-ooo")
- name: String! (e.g., "Ooo")
- lead: String (project lead name)
- repositories: [String!] (list of repo names)
- slackChannel: String
- slackChannelId: String
- memberIds: [String!]
- members: [Member!]
- isActive: Boolean

⚠️ NOTE: Project does NOT have a `status` field! Use `isActive` boolean instead.

## Date Calculation Guide:
- **Today**: {today}
- **This week** (last 7 days): startDate = "{week_ago}T00:00:00Z"
- **This month** (last 30 days): startDate = "{month_ago}T00:00:00Z"
- **Last month**: startDate = "{last_month_start}T00:00:00Z", endDate = "{last_month_end}T23:59:59Z"

## Important Notes:
1. **ALWAYS calculate dates relative to today ({today})**
2. Project keys: project-ooo, project-eco, project-syb, project-trh
3. **ALWAYS specify source**: GITHUB, SLACK, NOTION, or RECORDINGS
4. **NEVER omit source parameter** - this will include broken DRIVE data!
5. **NEVER use DRIVE** - Google Drive data is noisy and unreliable

## Example Queries:

### ✅ "Most active contributor this week" (MUST query BOTH):
```graphql
query MostActiveContributor {{
  github: activities(source: GITHUB, startDate: "{week_ago}T00:00:00Z", limit: 200) {{
    memberName
    sourceType
    timestamp
  }}
  slack: activities(source: SLACK, startDate: "{week_ago}T00:00:00Z", limit: 200) {{
    memberName
    sourceType
    timestamp
  }}
}}
```

### ✅ "Last month activity":
```graphql
query LastMonthActivity {{
  github: activities(source: GITHUB, startDate: "{last_month_start}T00:00:00Z", endDate: "{last_month_end}T23:59:59Z", limit: 300) {{
    memberName
    sourceType
    timestamp
  }}
  slack: activities(source: SLACK, startDate: "{last_month_start}T00:00:00Z", endDate: "{last_month_end}T23:59:59Z", limit: 300) {{
    memberName
    sourceType
    timestamp
  }}
}}
```

### ✅ Project activity:
```graphql
query ProjectActivity {{
  github: activities(source: GITHUB, projectKey: "project-ooo", startDate: "{month_ago}T00:00:00Z", limit: 100) {{
    memberName
    sourceType
    timestamp
  }}
  slack: activities(source: SLACK, projectKey: "project-ooo", startDate: "{month_ago}T00:00:00Z", limit: 100) {{
    memberName
    sourceType
    timestamp
  }}
}}
```

### ✅ "Which project is most active?" - Query each project separately:
```graphql
query CompareProjectActivity {{
  ooo_github: activities(source: GITHUB, projectKey: "project-ooo", startDate: "{month_ago}T00:00:00Z", limit: 200) {{
    memberName
    timestamp
  }}
  ooo_slack: activities(source: SLACK, projectKey: "project-ooo", startDate: "{month_ago}T00:00:00Z", limit: 200) {{
    memberName
    timestamp
  }}
  eco_github: activities(source: GITHUB, projectKey: "project-eco", startDate: "{month_ago}T00:00:00Z", limit: 200) {{
    memberName
    timestamp
  }}
  eco_slack: activities(source: SLACK, projectKey: "project-eco", startDate: "{month_ago}T00:00:00Z", limit: 200) {{
    memberName
    timestamp
  }}
  syb_github: activities(source: GITHUB, projectKey: "project-syb", startDate: "{month_ago}T00:00:00Z", limit: 200) {{
    memberName
    timestamp
  }}
  syb_slack: activities(source: SLACK, projectKey: "project-syb", startDate: "{month_ago}T00:00:00Z", limit: 200) {{
    memberName
    timestamp
  }}
  trh_github: activities(source: GITHUB, projectKey: "project-trh", startDate: "{month_ago}T00:00:00Z", limit: 200) {{
    memberName
    timestamp
  }}
  trh_slack: activities(source: SLACK, projectKey: "project-trh", startDate: "{month_ago}T00:00:00Z", limit: 200) {{
    memberName
    timestamp
  }}
}}
```

### ✅ Project details (status):
```graphql
query ProjectStatus {{
  project(key: "project-ooo") {{
    key
    name
    lead
    isActive
    repositories
    members {{
      name
    }}
  }}
}}
```

### ❌ WRONG - Using old dates (NEVER use 2024 dates!):
```graphql
# DON'T DO THIS! Always use current dates!
query WrongQuery {{
  activities(startDate: "2024-01-01T00:00:00Z") {{
    memberName
  }}
}}
```

### ❌ WRONG - Querying non-existent fields:
```graphql
# DON'T DO THIS! Activity doesn't have projectKey field
query WrongQuery {{
  activities(source: GITHUB) {{
    projectKey  # ❌ This field doesn't exist!
  }}
}}
```

```graphql
# DON'T DO THIS! Project doesn't have status field
query WrongQuery {{
  project(key: "project-ooo") {{
    status  # ❌ This field doesn't exist! Use isActive instead
  }}
}}
```
"""


def _extract_graphql_query(ai_response: str) -> Optional[str]:
    """Extract GraphQL query from AI response."""
    import re
    
    # Try to find graphql code block
    pattern = r'```graphql\s*([\s\S]*?)\s*```'
    match = re.search(pattern, ai_response)
    
    if match:
        return match.group(1).strip()
    
    # Try generic code block
    pattern = r'```\s*(query[\s\S]*?)\s*```'
    match = re.search(pattern, ai_response)
    
    if match:
        return match.group(1).strip()
    
    # Try to find query without code block
    pattern = r'(query\s+\w+\s*\{[\s\S]*?\})'
    match = re.search(pattern, ai_response)
    
    if match:
        return match.group(1).strip()
    
    return None


async def _execute_graphql_query(query: str) -> Dict[str, Any]:
    """Execute a GraphQL query against our schema."""
    import httpx
    
    try:
        # Get the GraphQL endpoint URL (same server)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://localhost:8000/graphql",
                json={"query": query},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"GraphQL error: {response.text}"}
    except Exception as e:
        logger.error(f"GraphQL execution error: {e}")
        return {"error": str(e)}


async def _fallback_keyword_approach(db, user_message: str, context_hints: dict, model: str, client, headers: dict, api_url: str) -> Dict[str, Any]:
    """Fallback to keyword-based data fetching when AI query generation fails."""
    logger.info("Using fallback keyword-based approach")
    
    # Use existing keyword-based analysis
    required_data = await _analyze_question_and_fetch_data(db, user_message, context_hints)
    system_prompt = _build_dynamic_system_prompt(required_data)
    
    ai_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    payload = {
        "messages": ai_messages,
        "model": model or "gpt-oss:120b"
    }
    
    try:
        response = await client.post(
            f"{api_url}/api/chat",
            json=payload,
            headers=headers
        )
        
        if response.status_code == 200:
            return {
                "response": response.json(),
                "method": "fallback_keyword"
            }
        else:
            return {
                "error": f"Fallback AI error: {response.text}",
                "context_data": required_data
            }
    except Exception as e:
        return {
            "error": str(e),
            "context_data": required_data
        }


async def _detect_context(message: str, db) -> Dict[str, Any]:
    """Detect context from user message"""
    context = {}
    message_lower = message.lower()
    
    # Detect project mentions
    projects = list(db['projects'].find({}, {'key': 1, 'name': 1}))
    for proj in projects:
        if proj['key'].lower() in message_lower or proj.get('name', '').lower() in message_lower:
            context['project_key'] = proj['key']
            break
    
    # Detect member mentions
    members = list(db['members'].find({}, {'name': 1}))
    for member in members:
        if member['name'].lower() in message_lower:
            context['member_name'] = member['name']
            break
    
    # Detect time period
    if "last week" in message_lower or "지난 주" in message_lower:
        context['period'] = 'last_week'
        context['days'] = 7
    elif "last month" in message_lower or "지난 달" in message_lower:
        context['period'] = 'last_month'
        context['days'] = 30
    elif "today" in message_lower or "오늘" in message_lower:
        context['period'] = 'today'
        context['days'] = 1
    else:
        context['days'] = 30  # Default
    
    return context


async def _analyze_question_and_fetch_data(db, question: str, context_hints: Dict) -> Dict[str, Any]:
    """
    Analyze the question and dynamically fetch relevant data.
    
    This is the core of the dynamic query system - it understands what
    the user is asking for and fetches ONLY the necessary data.
    """
    result = {"detected_context": {}, "data": {}}
    question_lower = question.lower()
    
    # Detect time period - more comprehensive detection
    days = 30  # Default
    period_label = "last 30 days"
    
    # Week detection
    if any(kw in question_lower for kw in ["this week", "이번 주", "금주", "이번주"]):
        days = 7
        period_label = "this week (last 7 days)"
    elif any(kw in question_lower for kw in ["last week", "지난 주", "저번 주", "지난주", "저번주"]):
        days = 7
        period_label = "last week (7 days)"
    elif any(kw in question_lower for kw in ["weekly", "주간", "week"]):
        days = 7
        period_label = "last 7 days"
    # Day detection
    elif any(kw in question_lower for kw in ["today", "오늘", "today's"]):
        days = 1
        period_label = "today (last 24 hours)"
    elif any(kw in question_lower for kw in ["yesterday", "어제"]):
        days = 2
        period_label = "last 2 days"
    # Month detection
    elif any(kw in question_lower for kw in ["this month", "이번 달", "이번달", "금월"]):
        days = 30
        period_label = "this month (last 30 days)"
    elif any(kw in question_lower for kw in ["last month", "지난 달", "지난달", "저번 달"]):
        days = 30
        period_label = "last month (30 days)"
    # Quarter/Year detection
    elif any(kw in question_lower for kw in ["quarter", "분기"]):
        days = 90
        period_label = "last quarter (90 days)"
    elif any(kw in question_lower for kw in ["this year", "올해", "year"]):
        days = 365
        period_label = "this year (365 days)"
    # Specific day patterns
    elif "3 days" in question_lower or "3일" in question_lower:
        days = 3
        period_label = "last 3 days"
    elif "7 days" in question_lower or "7일" in question_lower:
        days = 7
        period_label = "last 7 days"
    elif "14 days" in question_lower or "2 weeks" in question_lower or "2주" in question_lower:
        days = 14
        period_label = "last 14 days"
    
    result["detected_context"]["days"] = days
    result["detected_context"]["period_label"] = period_label
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Detect data sources mentioned
    needs_github = any(kw in question_lower for kw in [
        "github", "commit", "pr", "pull request", "repository", "repo", "코드", "커밋"
    ])
    needs_slack = any(kw in question_lower for kw in [
        "slack", "message", "메시지", "채팅", "communication", "chat"
    ])
    needs_comparison = any(kw in question_lower for kw in [
        "compare", "comparison", "vs", "versus", "비교"
    ])
    needs_top = any(kw in question_lower for kw in [
        "top", "most", "best", "active", "highest", "가장", "활발", "최고"
    ])
    needs_project_comparison = any(kw in question_lower for kw in [
        "which project", "most active project", "프로젝트별", "project activity",
        "project comparison", "프로젝트 비교", "어떤 프로젝트"
    ])
    
    # Detect specific member
    member_name = None
    members = list(db['members'].find({}, {'_id': 1, 'name': 1}))
    member_names = {m['name'].lower(): m['name'] for m in members}
    
    # Check for "my" (user's own activity - would need user identification)
    if "my " in question_lower or "내 " in question_lower:
        # For now, we can't identify the current user, so we'll note this
        result["detected_context"]["self_query"] = True
    
    for name_lower, name in member_names.items():
        if name_lower in question_lower:
            member_name = name
            result["detected_context"]["member_name"] = member_name
            break
    
    # Detect specific project
    project_key = context_hints.get('project_key')
    if not project_key:
        projects = list(db['projects'].find({}, {'key': 1, 'name': 1}))
        for proj in projects:
            proj_name = proj.get('name', '').lower()
            proj_key = proj['key'].lower()
            if proj_name in question_lower or proj_key in question_lower:
                project_key = proj['key']
                result["detected_context"]["project_key"] = project_key
                break
    
    # ========================================
    # DYNAMIC DATA FETCHING BASED ON ANALYSIS
    # ========================================
    
    # 1. If specific member is mentioned, get their detailed activity
    if member_name:
        result["data"]["member_activity"] = await _get_member_activity(db, {
            'member_name': member_name,
            'days': days
        })
    
    # 2. If specific project is mentioned, get project activity
    if project_key:
        result["data"]["project_activity"] = await _get_project_activity(db, {
            'project_key': project_key,
            'days': days
        })
    
    # 3. If asking about top/most active (and no specific member)
    # Always fetch ALL data sources for comprehensive analysis
    if needs_top and not member_name:
        # Always get GitHub data
        result["data"]["top_github_contributors"] = await _get_top_contributors(db, {
            'metric': 'commits',
            'days': days,
            'limit': 10,
            'project_key': project_key
        })
        result["data"]["top_repositories"] = await _get_top_repositories(db, {
            'days': days,
            'limit': 10
        })
        # Always get Slack data
        result["data"]["top_slack_users"] = await _get_top_slack_users(db, {
            'days': days,
            'limit': 10
        })
        # Add combined activity ranking
        result["data"]["combined_activity"] = await _get_combined_activity_ranking(db, days, 10)
        # Add project comparison if asking about projects
        if needs_project_comparison or not project_key:
            result["data"]["all_projects_activity"] = await _get_all_projects_activity(db, days)
    
    # 4. If asking for comparison
    if needs_comparison:
        result["data"]["comparison"] = {
            "github_total": db['github_commits'].count_documents({'date': {'$gte': start_date}}),
            "slack_total": db['slack_messages'].count_documents({
                'posted_at': {'$gte': start_date},
                'channel_name': {'$ne': 'tokamak-partners'}  # Exclude private channel
            }),
            "avg_commits_per_day": db['github_commits'].count_documents({'date': {'$gte': start_date}}) / max(days, 1),
            "avg_messages_per_day": db['slack_messages'].count_documents({
                'posted_at': {'$gte': start_date},
                'channel_name': {'$ne': 'tokamak-partners'}  # Exclude private channel
            }) / max(days, 1),
        }
    
    # 5. If no specific context detected, provide general summary
    if not result["data"]:
        result["data"]["summary"] = {
            "period": f"last_{days}_days",
            "total_commits": db['github_commits'].count_documents({'date': {'$gte': start_date}}),
            "total_messages": db['slack_messages'].count_documents({
                'posted_at': {'$gte': start_date},
                'channel_name': {'$ne': 'tokamak-partners'}  # Exclude private channel
            }),
            "total_prs": db['github_pull_requests'].count_documents({'created_at': {'$gte': start_date}}),
            "total_members": db['members'].count_documents({}),
            "total_projects": db['projects'].count_documents({}),
        }
        # Also provide some top lists for general queries
        result["data"]["top_github_contributors"] = await _get_top_contributors(db, {
            'metric': 'commits', 'days': days, 'limit': 5
        })
        result["data"]["top_slack_users"] = await _get_top_slack_users(db, {
            'days': days, 'limit': 5
        })
    
    return result


def _load_reference_docs() -> str:
    """Load AI reference documentation for better query understanding."""
    docs_dir = Path(__file__).parent.parent.parent.parent / "docs" / "ai-reference"
    reference_content = ""
    
    try:
        # Load database schema (condensed version)
        schema_file = docs_dir / "database-schema.md"
        if schema_file.exists():
            content = schema_file.read_text()
            # Extract just the key information sections
            reference_content += "\n## Database Schema Summary:\n"
            reference_content += "- members: name, email, role, projects\n"
            reference_content += "- github_commits: author_name (GitHub username), repository, date, message\n"
            reference_content += "- slack_messages: user_name (lowercase), channel_id, text, posted_at\n"
            reference_content += "- projects: key, name, lead, repositories, slack_channel_id\n"
            reference_content += "\nNote: author_name in commits is GitHub username, not display name.\n"
            reference_content += "Note: user_name in Slack is lowercase (e.g., 'ale' for member 'Ale').\n"
        
        # Load available queries info
        queries_file = docs_dir / "available-queries.md"
        if queries_file.exists():
            content = queries_file.read_text()
            # Extract project and member lists
            if "project-ooo" in content:
                reference_content += "\n## Available Projects:\n"
                reference_content += "- project-ooo (Ooo) - Lead: Jake\n"
                reference_content += "- project-eco (ECO) - Lead: Jason\n"
                reference_content += "- project-syb (SYB) - Lead: Jamie\n"
                reference_content += "- project-trh (TRH) - Lead: Praveen\n"
        
        # Load GraphQL examples - CRITICAL for proper query generation
        examples_file = docs_dir / "graphql-examples.md"
        if examples_file.exists():
            reference_content += "\n## IMPORTANT: GraphQL Query Pattern\n"
            reference_content += "For 'most active' or 'activity' questions, ALWAYS use this pattern:\n"
            reference_content += "```graphql\n"
            reference_content += "query CombinedActivity {\n"
            reference_content += "  github: activities(source: GITHUB, startDate: \"...\", limit: 300) { memberName }\n"
            reference_content += "  slack: activities(source: SLACK, startDate: \"...\", limit: 300) { memberName }\n"
            reference_content += "}\n"
            reference_content += "```\n"
            reference_content += "NEVER query only GitHub for activity questions!\n"
    except Exception as e:
        logger.warning(f"Failed to load reference docs: {e}")
    
    return reference_content


def _build_dynamic_system_prompt(data: Dict[str, Any]) -> str:
    """Build a concise system prompt with only the relevant fetched data."""
    
    # Load reference documentation
    reference_docs = _load_reference_docs()
    
    prompt = """You are an AI assistant for All-Thing-Eye, a team activity analytics platform.

You have access to REAL data from this team's GitHub commits, Slack messages, and project information.
Answer questions based ONLY on the data provided below. Be specific with names and numbers.
"""
    
    # Add reference documentation
    if reference_docs:
        prompt += reference_docs
    
    prompt += "\n## Fetched Data:\n\n"
    
    # Add detected context
    ctx = data.get("detected_context", {})
    if ctx:
        prompt += f"### Query Context:\n"
        days = ctx.get("days", 30)
        period_label = ctx.get("period_label", f"last {days} days")
        prompt += f"- **Time period: {period_label}** (data is dynamically fetched for this period)\n"
        if ctx.get("member_name"):
            prompt += f"- Specific member: {ctx['member_name']}\n"
        if ctx.get("project_key"):
            prompt += f"- Specific project: {ctx['project_key']}\n"
        prompt += "\n"
        prompt += "**IMPORTANT**: All data below is for the specified time period. You CAN answer questions about any time period.\n\n"
    
    fetched = data.get("data", {})
    
    # Summary
    if "summary" in fetched:
        s = fetched["summary"]
        prompt += f"""### Overall Summary ({s.get('period', 'recent')}):
- Total GitHub commits: {s.get('total_commits', 0)}
- Total Slack messages: {s.get('total_messages', 0)}
- Total PRs: {s.get('total_prs', 0)}
- Total members: {s.get('total_members', 0)}
- Total projects: {s.get('total_projects', 0)}

"""
    
    # Member activity
    if "member_activity" in fetched:
        ma = fetched["member_activity"]
        if "error" not in ma:
            prompt += f"""### {ma.get('member', 'Unknown')}'s Activity ({ma.get('period', 'recent')}):
- GitHub commits: {ma.get('github', {}).get('commits', 0)}
- Pull requests: {ma.get('github', {}).get('pull_requests', 0)}
- Slack messages: {ma.get('slack', {}).get('messages', 0)}
- Projects: {', '.join(ma.get('projects', [])) or 'None'}
"""
            # Add recent Slack messages if available
            recent_msgs = ma.get('slack', {}).get('recent_messages', [])
            if recent_msgs:
                prompt += f"- Recent Slack messages:\n"
                for msg in recent_msgs[:3]:
                    text = msg.get('text', '')[:100]
                    prompt += f"  • [{msg.get('channel', 'unknown')}] {text}...\n"
            prompt += "\n"
    
    # Project activity
    if "project_activity" in fetched:
        pa = fetched["project_activity"]
        if "error" not in pa:
            prompt += f"""### Project {pa.get('project', 'Unknown')} Activity ({pa.get('period', 'recent')}):
- Lead: {pa.get('lead', 'Unknown')}
- Total commits: {pa.get('github', {}).get('total_commits', 0)}
- Total Slack messages: {pa.get('slack', {}).get('total_messages', 0)}
- Repositories: {len(pa.get('repositories', []))} repos

"""
    
    # Top GitHub contributors
    if "top_github_contributors" in fetched:
        tc = fetched["top_github_contributors"]
        if tc.get("top_contributors"):
            prompt += f"### Top GitHub Contributors ({tc.get('period', 'recent')}):\n"
            for i, c in enumerate(tc["top_contributors"], 1):
                prompt += f"{i}. {c['name']}: {c['count']} commits\n"
            prompt += "\n"
    
    # Top Slack users
    if "top_slack_users" in fetched:
        ts = fetched["top_slack_users"]
        if ts.get("top_slack_users"):
            prompt += f"### Top Slack Users ({ts.get('period', 'recent')}):\n"
            for i, u in enumerate(ts["top_slack_users"], 1):
                channels = ", ".join(u.get('active_channels', [])[:2]) or "various"
                prompt += f"{i}. {u['name']}: {u['message_count']} messages (channels: {channels})\n"
            prompt += "\n"
    
    # Combined activity ranking (most important for "most active" questions)
    if "combined_activity" in fetched:
        ca = fetched["combined_activity"]
        if ca.get("rankings"):
            prompt += f"### Combined Activity Ranking ({ca.get('period', 'recent')}):\n"
            prompt += f"Scoring: {ca.get('scoring', 'commits + PRs + messages')}\n\n"
            prompt += "| Rank | Member | Commits | PRs | Messages | Total Score |\n"
            prompt += "|------|--------|---------|-----|----------|-------------|\n"
            for r in ca["rankings"][:10]:
                prompt += f"| {r['rank']} | {r['name']} | {r['commits']} | {r['prs']} | {r['messages']} | {r['total_score']} |\n"
            prompt += "\n"
    
    # Top repositories
    if "top_repositories" in fetched:
        tr = fetched["top_repositories"]
        if tr.get("top_repositories"):
            prompt += f"### Top Active Repositories ({tr.get('period', 'recent')}):\n"
            for i, r in enumerate(tr["top_repositories"][:5], 1):
                prompt += f"{i}. {r['repository']}: {r['commit_count']} commits\n"
            prompt += "\n"
    
    # Comparison data
    if "comparison" in fetched:
        c = fetched["comparison"]
        prompt += f"""### GitHub vs Slack Comparison:
- GitHub commits: {c.get('github_total', 0)} ({c.get('avg_commits_per_day', 0):.1f}/day)
- Slack messages: {c.get('slack_total', 0)} ({c.get('avg_messages_per_day', 0):.1f}/day)
- Ratio: 1 commit ≈ {c.get('slack_total', 1) / max(c.get('github_total', 1), 1):.1f} Slack messages

"""
    
    prompt += """## Instructions:
- Answer based ONLY on the data above
- Use specific numbers and names from the data
- If asked about something not in the data, say the data is not available
- Keep responses clear and concise
- Use markdown formatting for tables and lists when helpful
"""
    
    return prompt


async def _fetch_context_data(db, context: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch relevant data based on context"""
    data = {}
    days = context.get('days', 30)
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # If specific member mentioned
    if 'member_name' in context:
        args = {'member_name': context['member_name'], 'days': days}
        data['member_activity'] = await _get_member_activity(db, args)
    
    # If specific project mentioned
    if 'project_key' in context:
        args = {'project_key': context['project_key'], 'days': days}
        data['project_activity'] = await _get_project_activity(db, args)
    
    # Always include top contributors
    data['top_committers'] = await _get_top_contributors(db, {
        'metric': 'commits',
        'days': days,
        'limit': 5,
        'project_key': context.get('project_key')
    })
    
    # Always include top repositories
    data['top_repositories'] = await _get_top_repositories(db, {
        'days': days,
        'limit': 5
    })
    
    # Always include top Slack users
    data['top_slack_users'] = await _get_top_slack_users(db, {
        'days': days,
        'limit': 10
    })
    
    # Include summary - uses 'date' for github_commits and 'posted_at' for slack_messages
    data['summary'] = {
        "period": f"last_{days}_days",
        "total_commits": db['github_commits'].count_documents({
            'date': {'$gte': start_date}
        }),
        "total_messages": db['slack_messages'].count_documents({
            'posted_at': {'$gte': start_date},
            'channel_name': {'$ne': 'tokamak-partners'}  # Exclude private channel
        }),
    }
    
    return data


def _build_system_prompt(context_data: Dict[str, Any]) -> str:
    """Build system prompt with context data"""
    # Get period info
    period_label = context_data.get('period_label', 'last 30 days')
    days = context_data.get('days', 30)
    
    prompt = f"""You are an AI assistant for the All-Thing-Eye platform, a team activity analytics system.

You have access to real-time data from:
- GitHub: commits, pull requests, issues
- Slack: messages, reactions
- Notion: pages, updates
- Google Drive: file activities

## IMPORTANT: Data Time Period
**All data below is for: {period_label} ({days} days)**
You CAN answer questions about any time period - the data has been dynamically fetched based on the user's question.

## Current Data Context:

"""
    
    if 'summary' in context_data:
        s = context_data['summary']
        prompt += f"""### Summary ({s.get('period', 'last 30 days')}):
- Total GitHub commits: {s.get('total_commits', 'N/A')}
- Total Slack messages: {s.get('total_messages', 'N/A')}

"""
    
    if 'top_committers' in context_data:
        tc = context_data['top_committers']
        if tc.get('top_contributors'):
            prompt += "### Top Contributors by Commits:\n"
            for i, c in enumerate(tc['top_contributors'][:5], 1):
                prompt += f"{i}. {c['name']}: {c['count']} commits\n"
            prompt += "\n"
    
    if 'top_repositories' in context_data:
        tr = context_data['top_repositories']
        if tr.get('top_repositories'):
            prompt += "### Top Active Repositories:\n"
            for i, r in enumerate(tr['top_repositories'][:5], 1):
                prompt += f"{i}. {r['repository']}: {r['commit_count']} commits (+{r.get('additions', 0)}/-{r.get('deletions', 0)})\n"
            prompt += "\n"
    
    if 'top_slack_users' in context_data:
        ts = context_data['top_slack_users']
        if ts.get('top_slack_users'):
            prompt += "### Top Slack Users by Messages:\n"
            for i, u in enumerate(ts['top_slack_users'][:10], 1):
                channels_str = ", ".join(u.get('active_channels', [])[:2]) if u.get('active_channels') else "various"
                prompt += f"{i}. {u['name']}: {u['message_count']} messages (channels: {channels_str})\n"
            prompt += "\n"
    
    if 'member_activity' in context_data:
        ma = context_data['member_activity']
        if 'error' not in ma:
            prompt += f"""### Member Activity - {ma.get('member', 'Unknown')}:
- GitHub commits: {ma.get('github', {}).get('commits', 0)}
- Pull requests: {ma.get('github', {}).get('pull_requests', 0)}
- Slack messages: {ma.get('slack', {}).get('messages', 0)}
- Projects: {', '.join(ma.get('projects', []))}

"""
    
    if 'project_activity' in context_data:
        pa = context_data['project_activity']
        if 'error' not in pa:
            prompt += f"""### Project Activity - {pa.get('project', 'Unknown')}:
- Lead: {pa.get('lead', 'Unknown')}
- Repositories: {len(pa.get('repositories', []))} repos
- Total commits: {pa.get('github', {}).get('total_commits', 0)}
- Total Slack messages: {pa.get('slack', {}).get('total_messages', 0)}

"""
    
    if 'all_projects_activity' in context_data:
        apa = context_data['all_projects_activity']
        if apa.get('projects'):
            prompt += f"### All Projects Activity Ranking ({apa.get('period', 'last 30 days')}):\n"
            prompt += f"Scoring: {apa.get('scoring', 'commits + messages × 0.3')}\n\n"
            prompt += "| Rank | Project | Lead | Repos | Commits | Messages | Score |\n"
            prompt += "|------|---------|------|-------|---------|----------|-------|\n"
            for i, p in enumerate(apa['projects'], 1):
                prompt += f"| {i} | {p['project']} | {p.get('lead', 'N/A')} | {len(p.get('repositories', []))} | {p['commits']} | {p['messages']} | {p['combined_score']} |\n"
            prompt += "\n"
    
    prompt += """## Instructions:
- Answer questions based on the data provided above
- Be specific with numbers and names
- If asked about trends, analyze the data patterns
- If data is not available, say so clearly
- Keep responses concise but informative
"""
    
    return prompt


# ============================================================================
# Tool Implementation Functions (shared with MCP server)
# ============================================================================

async def _get_member_activity(db, args: Dict[str, Any]) -> Dict:
    """Get activity for a specific member"""
    member_name = args.get("member_name", "")
    days = args.get("days", 30)
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    member = db['members'].find_one({'name': {'$regex': member_name, '$options': 'i'}})
    if not member:
        return {"error": f"Member '{member_name}' not found"}
    
    member_name_exact = member['name']
    member_id = str(member['_id'])
    
    # Get identifiers for this member (GitHub username, Slack ID, etc.)
    github_usernames = []
    slack_user_ids = []
    slack_user_names = []
    
    identifiers = list(db['member_identifiers'].find({'member_id': member_id}))
    for ident in identifiers:
        if ident.get('identifier_type') == 'github':
            github_usernames.append(ident.get('identifier_value'))
        elif ident.get('identifier_type') == 'slack_id':
            slack_user_ids.append(ident.get('identifier_value'))
        elif ident.get('identifier_type') == 'slack_name':
            slack_user_names.append(ident.get('identifier_value'))
    
    # Also try lowercase member name for Slack (common pattern)
    slack_user_names.append(member_name_exact.lower())
    
    # GitHub commits - uses 'author_name' field which contains GitHub username
    commits_count = 0
    if github_usernames:
        commits_count = db['github_commits'].count_documents({
            'date': {'$gte': start_date},
            'author_name': {'$in': github_usernames}
        })
    
    # Slack messages - uses 'user_name' (lowercase name) or 'user_id' fields
    messages_query = {
        'posted_at': {'$gte': start_date},
        'channel_name': {'$ne': 'tokamak-partners'}  # Exclude private channel
    }
    slack_conditions = []
    if slack_user_ids:
        slack_conditions.append({'user_id': {'$in': slack_user_ids}})
    if slack_user_names:
        slack_conditions.append({'user_name': {'$in': slack_user_names}})
    
    messages_count = 0
    if slack_conditions:
        messages_query['$or'] = slack_conditions
        messages_count = db['slack_messages'].count_documents(messages_query)
    
    # PRs - uses 'author' field (GitHub username)
    prs_count = 0
    if github_usernames:
        prs_count = db['github_pull_requests'].count_documents({
            'created_at': {'$gte': start_date},
            'author': {'$in': github_usernames}
        })
    
    # Get recent Slack messages for context
    recent_messages = []
    if slack_conditions:
        recent_msgs = list(db['slack_messages'].find(
            {
                'posted_at': {'$gte': start_date}, 
                '$or': slack_conditions,
                'channel_name': {'$ne': 'tokamak-partners'}  # Exclude private channel
            },
            {'text': 1, 'channel_name': 1, 'posted_at': 1}
        ).sort('posted_at', -1).limit(5))
        for msg in recent_msgs:
            recent_messages.append({
                'text': msg.get('text', '')[:200],  # Truncate long messages
                'channel': msg.get('channel_name', 'Unknown'),
                'time': msg.get('posted_at').isoformat() if msg.get('posted_at') else None
            })
    
    return {
        "member": member_name_exact,
        "period": f"last_{days}_days",
        "github": {
            "commits": commits_count,
            "pull_requests": prs_count,
            "usernames": github_usernames
        },
        "slack": {
            "messages": messages_count,
            "recent_messages": recent_messages
        },
        "projects": member.get('projects', [])
    }


async def _get_project_activity(db, args: Dict[str, Any]) -> Dict:
    """Get activity for a specific project"""
    project_key = args.get("project_key", "")
    days = args.get("days", 30)
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    project = db['projects'].find_one({'key': project_key})
    if not project:
        return {"error": f"Project '{project_key}' not found"}
    
    repositories = project.get('repositories', [])
    slack_channel_id = project.get('slack_channel_id')
    
    # GitHub commits - uses 'date' and 'repository' fields
    commit_query = {'date': {'$gte': start_date}}
    if repositories:
        commit_query['repository'] = {'$in': repositories}
    total_commits = db['github_commits'].count_documents(commit_query)
    
    # Slack messages - uses 'posted_at' and 'channel_id' fields
    message_query = {
        'posted_at': {'$gte': start_date},
        'channel_name': {'$ne': 'tokamak-partners'}  # Exclude private channel
    }
    if slack_channel_id:
        message_query['channel_id'] = slack_channel_id
    total_messages = db['slack_messages'].count_documents(message_query)
    
    return {
        "project": project.get('name', project_key),
        "key": project_key,
        "period": f"last_{days}_days",
        "lead": project.get('lead'),
        "repositories": repositories,
        "github": {"total_commits": total_commits},
        "slack": {"total_messages": total_messages}
    }


async def _get_all_projects_activity(db, days: int = 30) -> Dict:
    """Get activity for all projects and rank them"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    projects = list(db['projects'].find({'is_active': True}))
    
    project_activities = []
    for project in projects:
        project_key = project['key']
        project_name = project.get('name', project_key)
        repositories = project.get('repositories', [])
        slack_channel_id = project.get('slack_channel_id')
        
        # GitHub commits for this project's repositories
        commit_count = 0
        if repositories:
            commit_count = db['github_commits'].count_documents({
                'date': {'$gte': start_date},
                'repository': {'$in': repositories}
            })
        
        # Slack messages for this project's channel
        message_count = 0
        if slack_channel_id:
            message_count = db['slack_messages'].count_documents({
                'posted_at': {'$gte': start_date},
                'channel_id': slack_channel_id,
                'channel_name': {'$ne': 'tokamak-partners'}  # Exclude private channel
            })
        
        # Calculate combined score (commits + messages * 0.3)
        combined_score = commit_count + (message_count * 0.3)
        
        project_activities.append({
            "project": project_name,
            "key": project_key,
            "lead": project.get('lead'),
            "repositories": repositories,
            "commits": commit_count,
            "messages": message_count,
            "combined_score": round(combined_score, 1)
        })
    
    # Sort by combined score
    project_activities.sort(key=lambda x: x['combined_score'], reverse=True)
    
    return {
        "period": f"last_{days}_days",
        "scoring": "commits + messages × 0.3",
        "projects": project_activities
    }


async def _compare_contributors(db, args: Dict[str, Any]) -> Dict:
    """Compare multiple contributors"""
    member_names = args.get("member_names", [])
    days = args.get("days", 30)
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    results = {}
    for name in member_names:
        member = db['members'].find_one({'name': {'$regex': name, '$options': 'i'}})
        if not member:
            results[name] = {"error": "Member not found"}
            continue
        
        member_name_exact = member['name']
        
        results[member_name_exact] = {
            'commits': db['github_commits'].count_documents({
                'date': {'$gte': start_date},
                'author_name': member_name_exact
            }),
            'messages': db['slack_messages'].count_documents({
                'posted_at': {'$gte': start_date},
                'user_name': member_name_exact,
                'channel_name': {'$ne': 'tokamak-partners'}  # Exclude private channel
            })
        }
    
    return {"period": f"last_{days}_days", "comparison": results}


async def _get_top_contributors(db, args: Dict[str, Any]) -> Dict:
    """Get top contributors by metric"""
    metric = args.get("metric", "commits")
    project_key = args.get("project_key")
    days = args.get("days", 30)
    limit = args.get("limit", 10)
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    repositories = None
    if project_key:
        project = db['projects'].find_one({'key': project_key})
        if project:
            repositories = project.get('repositories', [])
    
    if metric == "commits":
        match_query = {'date': {'$gte': start_date}}
        if repositories:
            match_query['repository'] = {'$in': repositories}
        
        pipeline = [
            {'$match': match_query},
            {'$group': {'_id': '$author_name', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
            {'$limit': limit}
        ]
        results = list(db['github_commits'].aggregate(pipeline))
        
        # Map GitHub usernames to member names
        contributors = []
        for r in results:
            if r['_id']:
                member_name = _github_to_member_name(db, r['_id'])
                contributors.append({"name": member_name, "count": r['count']})
    
    elif metric == "messages":
        pipeline = [
            {'$match': {'posted_at': {'$gte': start_date}}},
            {'$group': {'_id': '$user_name', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
            {'$limit': limit}
        ]
        results = list(db['slack_messages'].aggregate(pipeline))
        contributors = [
            {"name": r['_id'], "count": r['count']} 
            for r in results if r['_id']
        ]
    
    else:
        return {"error": f"Unknown metric: {metric}"}
    
    return {
        "metric": metric,
        "period": f"last_{days}_days",
        "top_contributors": contributors
    }


async def _get_combined_activity_ranking(db, days: int, limit: int = 10) -> Dict:
    """
    Calculate combined activity score across all platforms.
    
    Scoring weights:
    - GitHub commit: 1.0 points
    - GitHub PR: 2.0 points
    - Slack message: 0.3 points
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get all members
    members = list(db['members'].find({}, {'_id': 1, 'name': 1}))
    member_scores = {}
    
    for member in members:
        member_name = member['name']
        member_id = str(member['_id'])
        
        # Get identifiers
        github_usernames = []
        slack_names = [member_name.lower()]  # Default: lowercase name
        
        identifiers = list(db['member_identifiers'].find({'member_id': member_id}))
        for ident in identifiers:
            if ident.get('identifier_type') == 'github':
                github_usernames.append(ident.get('identifier_value'))
            elif ident.get('identifier_type') == 'slack_name':
                slack_names.append(ident.get('identifier_value'))
        
        # Count GitHub commits
        commits = 0
        if github_usernames:
            commits = db['github_commits'].count_documents({
                'date': {'$gte': start_date},
                'author_name': {'$in': github_usernames}
            })
        
        # Count GitHub PRs
        prs = 0
        if github_usernames:
            prs = db['github_pull_requests'].count_documents({
                'created_at': {'$gte': start_date},
                'author': {'$in': github_usernames}
            })
        
        # Count Slack messages
        messages = db['slack_messages'].count_documents({
            'posted_at': {'$gte': start_date},
            'user_name': {'$in': slack_names},
            'channel_name': {'$ne': 'tokamak-partners'}  # Exclude private channel
        })
        
        # Calculate weighted score
        score = (commits * 1.0) + (prs * 2.0) + (messages * 0.3)
        
        if score > 0:
            member_scores[member_name] = {
                'commits': commits,
                'prs': prs,
                'messages': messages,
                'score': round(score, 1)
            }
    
    # Sort by score
    sorted_members = sorted(member_scores.items(), key=lambda x: x[1]['score'], reverse=True)[:limit]
    
    return {
        "period": f"last_{days}_days",
        "scoring": "commits×1.0 + PRs×2.0 + messages×0.3",
        "rankings": [
            {
                "rank": i + 1,
                "name": name,
                "commits": data['commits'],
                "prs": data['prs'],
                "messages": data['messages'],
                "total_score": data['score']
            }
            for i, (name, data) in enumerate(sorted_members)
        ]
    }


async def _get_top_slack_users(db, args: Dict[str, Any]) -> Dict:
    """Get top Slack users by message count"""
    days = args.get("days", 30)
    limit = args.get("limit", 10)
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    pipeline = [
        {'$match': {
            'posted_at': {'$gte': start_date},
            'channel_name': {'$ne': 'tokamak-partners'}  # Exclude private channel
        }},
        {'$group': {
            '_id': '$user_name',
            'message_count': {'$sum': 1},
            'channels': {'$addToSet': '$channel_name'}
        }},
        {'$sort': {'message_count': -1}},
        {'$limit': limit}
    ]
    
    results = list(db['slack_messages'].aggregate(pipeline))
    
    users = []
    for r in results:
        if r['_id']:
            # Map Slack user_name to member display name
            member_name = _slack_to_member_name(db, r['_id'])
            users.append({
                "name": member_name,
                "slack_name": r['_id'],
                "message_count": r['message_count'],
                "active_channels": r.get('channels', [])[:3]  # Top 3 channels
            })
    
    return {
        "period": f"last_{days}_days",
        "top_slack_users": users
    }


def _slack_to_member_name(db, slack_username: str) -> str:
    """Convert Slack username to member display name"""
    if not slack_username:
        return slack_username
    
    # Try to find member by lowercase name match
    member = db['members'].find_one({
        'name': {'$regex': f'^{slack_username}$', '$options': 'i'}
    })
    if member:
        return member['name']
    
    # Try member_identifiers
    identifier = db['member_identifiers'].find_one({
        'identifier_type': 'slack_name',
        'identifier_value': slack_username
    })
    if identifier:
        member = db['members'].find_one({'_id': identifier['member_id']})
        if member:
            return member['name']
    
    # Return capitalized version as fallback
    return slack_username.capitalize()


async def _get_top_repositories(db, args: Dict[str, Any]) -> Dict:
    """Get top GitHub repositories by commit count"""
    days = args.get("days", 30)
    limit = args.get("limit", 10)
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    pipeline = [
        {'$match': {'date': {'$gte': start_date}}},
        {'$group': {
            '_id': '$repository',
            'commit_count': {'$sum': 1},
            'additions': {'$sum': '$additions'},
            'deletions': {'$sum': '$deletions'},
            'contributors': {'$addToSet': '$author_name'}
        }},
        {'$sort': {'commit_count': -1}},
        {'$limit': limit}
    ]
    
    results = list(db['github_commits'].aggregate(pipeline))
    
    repositories = []
    for r in results:
        if r['_id']:
            # Map contributors to member names
            contributor_names = [
                _github_to_member_name(db, gh_name) 
                for gh_name in r.get('contributors', [])
            ]
            repositories.append({
                "repository": r['_id'],
                "commit_count": r['commit_count'],
                "additions": r.get('additions', 0),
                "deletions": r.get('deletions', 0),
                "contributor_count": len(contributor_names),
                "contributors": contributor_names[:5]  # Top 5 contributors
            })
    
    return {
        "period": f"last_{days}_days",
        "top_repositories": repositories
    }


def _github_to_member_name(db, github_username: str) -> str:
    """Convert GitHub username to member display name"""
    if not github_username:
        return github_username
    
    # First check member_identifiers collection (uses identifier_value field)
    identifier = db['member_identifiers'].find_one({
        'source': 'github',
        'identifier_value': {'$regex': f'^{github_username}$', '$options': 'i'}
    })
    if identifier:
        return identifier.get('member_name', github_username)
    
    # Check members collection for github_username field
    member = db['members'].find_one({
        'github_username': {'$regex': f'^{github_username}$', '$options': 'i'}
    })
    if member:
        return member.get('name', github_username)
    
    # Return original if not found
    return github_username


async def _search_activities(db, args: Dict[str, Any]) -> Dict:
    """Search activities by keyword"""
    keyword = args.get("keyword", "")
    source = args.get("source", "all")
    days = args.get("days", 7)
    limit = args.get("limit", 20)
    
    start_date = datetime.utcnow() - timedelta(days=days)
    results = []
    
    if source in ["github", "all"]:
        for commit in db['github_commits'].find({
            'date': {'$gte': start_date},
            'message': {'$regex': keyword, '$options': 'i'}
        }).limit(limit // 2 if source == "all" else limit):
            github_username = commit.get('author_name', '')
            member_name = _github_to_member_name(db, github_username)
            results.append({
                "source": "github",
                "author": member_name,
                "message": commit.get('message', '')[:200],
                "timestamp": commit.get('date')
            })
    
    if source in ["slack", "all"]:
        for msg in db['slack_messages'].find({
            'posted_at': {'$gte': start_date},
            'text': {'$regex': keyword, '$options': 'i'},
            'channel_name': {'$ne': 'tokamak-partners'}  # Exclude private channel
        }).limit(limit // 2 if source == "all" else limit):
            results.append({
                "source": "slack",
                "author": msg.get('user_name'),
                "message": msg.get('text', '')[:200],
                "timestamp": msg.get('posted_at')
            })
    
    return {"keyword": keyword, "count": len(results), "results": results}


async def _get_weekly_summary(db, args: Dict[str, Any]) -> Dict:
    """Generate weekly summary"""
    project_key = args.get("project_key")
    week_offset = args.get("week_offset", 0)
    
    now = datetime.utcnow()
    days_since_friday = (now.weekday() - 4) % 7
    this_friday = now - timedelta(days=days_since_friday)
    this_friday = this_friday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    start_date = this_friday + timedelta(weeks=week_offset)
    end_date = start_date + timedelta(days=7)
    
    repositories = None
    if project_key:
        project = db['projects'].find_one({'key': project_key})
        if project:
            repositories = project.get('repositories', [])
    
    commit_query = {'date': {'$gte': start_date, '$lt': end_date}}
    if repositories:
        commit_query['repository'] = {'$in': repositories}
    
    total_commits = db['github_commits'].count_documents(commit_query)
    total_messages = db['slack_messages'].count_documents({
        'posted_at': {'$gte': start_date, '$lt': end_date},
        'channel_name': {'$ne': 'tokamak-partners'}  # Exclude private channel
    })
    
    return {
        "project": project_key or "All Projects",
        "week": start_date.strftime("%Y-W%W"),
        "github": {"total_commits": total_commits},
        "slack": {"total_messages": total_messages}
    }

