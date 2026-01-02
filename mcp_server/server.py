"""
All-Thing-Eye MCP Server

Main MCP server implementation that exposes resources, tools, and prompts
for AI assistants to interact with the All-Thing-Eye platform data.
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    Prompt,
    PromptMessage,
    PromptArgument,
    GetPromptResult,
    INTERNAL_ERROR,
    INVALID_PARAMS,
)

from dotenv import load_dotenv

# Load environment variables
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# Import MongoDB manager
from src.core.config import Config
from src.core.mongo_manager import get_mongo_manager

# Initialize config and MongoDB
config = Config()
mongo_config = {
    'uri': config.get('mongodb.uri', os.getenv('MONGODB_URI', 'mongodb://localhost:27017')),
    'database': config.get('mongodb.database', os.getenv('MONGODB_DATABASE', 'all_thing_eye'))
}
mongo_manager = get_mongo_manager(mongo_config)

# Create the MCP server
server = Server("all-thing-eye")


# ============================================================================
# RESOURCES - Read-only data access
# ============================================================================

@server.list_resources()
async def list_resources() -> List[Resource]:
    """List all available resources"""
    return [
        Resource(
            uri="ate://members",
            name="Team Members",
            description="List of all team members with their roles and project assignments",
            mimeType="application/json"
        ),
        Resource(
            uri="ate://projects",
            name="Projects",
            description="List of all projects with repositories and team members",
            mimeType="application/json"
        ),
        Resource(
            uri="ate://activities/summary",
            name="Activity Summary",
            description="Summary of recent activities across all sources (GitHub, Slack, etc.)",
            mimeType="application/json"
        ),
        Resource(
            uri="ate://github/stats",
            name="GitHub Statistics",
            description="GitHub commit and PR statistics for all repositories",
            mimeType="application/json"
        ),
        Resource(
            uri="ate://slack/stats",
            name="Slack Statistics",
            description="Slack message statistics by channel and member",
            mimeType="application/json"
        ),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    """Read a specific resource"""
    db = mongo_manager.db
    
    if uri == "ate://members":
        members = list(db['members'].find({}, {
            '_id': 0, 'name': 1, 'email': 1, 'role': 1, 
            'projects': 1, 'github_username': 1, 'slack_id': 1
        }))
        return json.dumps(members, indent=2, default=str)
    
    elif uri == "ate://projects":
        projects = list(db['projects'].find({}, {
            '_id': 0, 'key': 1, 'name': 1, 'description': 1,
            'lead': 1, 'repositories': 1, 'slack_channel': 1, 'is_active': 1
        }))
        return json.dumps(projects, indent=2, default=str)
    
    elif uri == "ate://activities/summary":
        # Get last 30 days summary
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        summary = {
            "period": "last_30_days",
            "github_commits": db['github_commits'].count_documents({
                'committed_at': {'$gte': thirty_days_ago}
            }),
            "github_prs": db['github_pull_requests'].count_documents({
                'created_at': {'$gte': thirty_days_ago}
            }),
            "slack_messages": db['slack_messages'].count_documents({
                'timestamp': {'$gte': thirty_days_ago}
            }),
            "notion_pages": db['notion_pages'].count_documents({
                'last_edited_time': {'$gte': thirty_days_ago}
            }),
        }
        return json.dumps(summary, indent=2, default=str)
    
    elif uri == "ate://github/stats":
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        # Aggregate commits by author
        pipeline = [
            {'$match': {'committed_at': {'$gte': thirty_days_ago}}},
            {'$group': {
                '_id': '$author_login',
                'commits': {'$sum': 1},
                'additions': {'$sum': '$stats.additions'},
                'deletions': {'$sum': '$stats.deletions'}
            }},
            {'$sort': {'commits': -1}},
            {'$limit': 20}
        ]
        stats = list(db['github_commits'].aggregate(pipeline))
        return json.dumps(stats, indent=2, default=str)
    
    elif uri == "ate://slack/stats":
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        # Aggregate messages by user
        pipeline = [
            {'$match': {'timestamp': {'$gte': thirty_days_ago}}},
            {'$group': {
                '_id': '$user_name',
                'messages': {'$sum': 1}
            }},
            {'$sort': {'messages': -1}},
            {'$limit': 20}
        ]
        stats = list(db['slack_messages'].aggregate(pipeline))
        return json.dumps(stats, indent=2, default=str)
    
    else:
        raise ValueError(f"Unknown resource: {uri}")


# ============================================================================
# TOOLS - Functions that AI can call
# ============================================================================

@server.list_tools()
async def list_tools() -> List[Tool]:
    """List all available tools"""
    return [
        Tool(
            name="get_member_activity",
            description="Get detailed activity statistics for a specific team member",
            inputSchema={
                "type": "object",
                "properties": {
                    "member_name": {
                        "type": "string",
                        "description": "Name of the team member"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back (default: 30)",
                        "default": 30
                    }
                },
                "required": ["member_name"]
            }
        ),
        Tool(
            name="get_project_activity",
            description="Get activity statistics for a specific project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_key": {
                        "type": "string",
                        "description": "Project key (e.g., 'project-ooo', 'project-eco')"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back (default: 30)",
                        "default": 30
                    }
                },
                "required": ["project_key"]
            }
        ),
        Tool(
            name="compare_contributors",
            description="Compare activity between multiple team members",
            inputSchema={
                "type": "object",
                "properties": {
                    "member_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of member names to compare"
                    },
                    "metric": {
                        "type": "string",
                        "enum": ["commits", "messages", "prs", "all"],
                        "description": "Metric to compare (default: all)",
                        "default": "all"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back (default: 30)",
                        "default": 30
                    }
                },
                "required": ["member_names"]
            }
        ),
        Tool(
            name="get_top_contributors",
            description="Get the most active contributors by a specific metric",
            inputSchema={
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "enum": ["commits", "messages", "prs", "reviews"],
                        "description": "Metric to rank by"
                    },
                    "project_key": {
                        "type": "string",
                        "description": "Optional: Filter by project key"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back (default: 30)",
                        "default": 30
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of top contributors to return (default: 10)",
                        "default": 10
                    }
                },
                "required": ["metric"]
            }
        ),
        Tool(
            name="search_activities",
            description="Search for activities matching specific criteria",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Keyword to search for"
                    },
                    "source": {
                        "type": "string",
                        "enum": ["github", "slack", "notion", "all"],
                        "description": "Source to search in (default: all)",
                        "default": "all"
                    },
                    "member_name": {
                        "type": "string",
                        "description": "Optional: Filter by member name"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back (default: 7)",
                        "default": 7
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default: 20)",
                        "default": 20
                    }
                },
                "required": ["keyword"]
            }
        ),
        Tool(
            name="get_weekly_summary",
            description="Generate a weekly activity summary for a project or the entire team",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_key": {
                        "type": "string",
                        "description": "Optional: Project key to summarize"
                    },
                    "week_offset": {
                        "type": "integer",
                        "description": "Week offset from current week (0 = this week, -1 = last week)",
                        "default": 0
                    }
                },
                "required": []
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute a tool and return results"""
    db = mongo_manager.db
    
    try:
        if name == "get_member_activity":
            result = await _get_member_activity(db, arguments)
        elif name == "get_project_activity":
            result = await _get_project_activity(db, arguments)
        elif name == "compare_contributors":
            result = await _compare_contributors(db, arguments)
        elif name == "get_top_contributors":
            result = await _get_top_contributors(db, arguments)
        elif name == "search_activities":
            result = await _search_activities(db, arguments)
        elif name == "get_weekly_summary":
            result = await _get_weekly_summary(db, arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]


async def _get_member_activity(db, args: Dict[str, Any]) -> Dict:
    """Get activity for a specific member"""
    member_name = args["member_name"]
    days = args.get("days", 30)
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Find member
    member = db['members'].find_one({'name': {'$regex': member_name, '$options': 'i'}})
    if not member:
        return {"error": f"Member '{member_name}' not found"}
    
    member_name_exact = member['name']
    github_username = member.get('github_username')
    
    # Get GitHub commits
    commit_query = {'committed_at': {'$gte': start_date}}
    if github_username:
        commit_query['author_login'] = github_username
    else:
        commit_query['author_login'] = {'$regex': member_name_exact, '$options': 'i'}
    
    commits = list(db['github_commits'].find(commit_query, {'_id': 0, 'sha': 1, 'message': 1, 'repository': 1, 'committed_at': 1}).limit(50))
    
    # Get Slack messages
    message_query = {
        'timestamp': {'$gte': start_date},
        'user_name': {'$regex': member_name_exact, '$options': 'i'}
    }
    messages = db['slack_messages'].count_documents(message_query)
    
    # Get PRs
    pr_query = {'created_at': {'$gte': start_date}}
    if github_username:
        pr_query['author'] = github_username
    prs = list(db['github_pull_requests'].find(pr_query, {'_id': 0, 'title': 1, 'repository': 1, 'state': 1, 'created_at': 1}).limit(20))
    
    return {
        "member": member_name_exact,
        "period": f"last_{days}_days",
        "github": {
            "commits": len(commits),
            "recent_commits": commits[:10],
            "pull_requests": len(prs),
            "recent_prs": prs[:5]
        },
        "slack": {
            "messages": messages
        },
        "projects": member.get('projects', [])
    }


async def _get_project_activity(db, args: Dict[str, Any]) -> Dict:
    """Get activity for a specific project"""
    project_key = args["project_key"]
    days = args.get("days", 30)
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Find project
    project = db['projects'].find_one({'key': project_key})
    if not project:
        return {"error": f"Project '{project_key}' not found"}
    
    repositories = project.get('repositories', [])
    slack_channel_id = project.get('slack_channel_id')
    
    # Get GitHub commits for project repositories
    commits_by_author = {}
    if repositories:
        pipeline = [
            {'$match': {
                'committed_at': {'$gte': start_date},
                'repository': {'$in': repositories}
            }},
            {'$group': {
                '_id': '$author_login',
                'commits': {'$sum': 1}
            }},
            {'$sort': {'commits': -1}}
        ]
        for doc in db['github_commits'].aggregate(pipeline):
            commits_by_author[doc['_id']] = doc['commits']
    
    # Get Slack messages for project channel
    messages_by_user = {}
    if slack_channel_id:
        pipeline = [
            {'$match': {
                'timestamp': {'$gte': start_date},
                'channel_id': slack_channel_id
            }},
            {'$group': {
                '_id': '$user_name',
                'messages': {'$sum': 1}
            }},
            {'$sort': {'messages': -1}}
        ]
        for doc in db['slack_messages'].aggregate(pipeline):
            messages_by_user[doc['_id']] = doc['messages']
    
    return {
        "project": project.get('name', project_key),
        "key": project_key,
        "period": f"last_{days}_days",
        "lead": project.get('lead'),
        "repositories": repositories,
        "github": {
            "total_commits": sum(commits_by_author.values()),
            "by_contributor": commits_by_author
        },
        "slack": {
            "total_messages": sum(messages_by_user.values()),
            "by_user": messages_by_user
        }
    }


async def _compare_contributors(db, args: Dict[str, Any]) -> Dict:
    """Compare multiple contributors"""
    member_names = args["member_names"]
    metric = args.get("metric", "all")
    days = args.get("days", 30)
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    results = {}
    for name in member_names:
        member = db['members'].find_one({'name': {'$regex': name, '$options': 'i'}})
        if not member:
            results[name] = {"error": "Member not found"}
            continue
        
        member_name = member['name']
        github_username = member.get('github_username')
        
        stats = {}
        
        if metric in ["commits", "all"]:
            commit_query = {'committed_at': {'$gte': start_date}}
            if github_username:
                commit_query['author_login'] = github_username
            stats['commits'] = db['github_commits'].count_documents(commit_query)
        
        if metric in ["messages", "all"]:
            stats['messages'] = db['slack_messages'].count_documents({
                'timestamp': {'$gte': start_date},
                'user_name': member_name
            })
        
        if metric in ["prs", "all"]:
            pr_query = {'created_at': {'$gte': start_date}}
            if github_username:
                pr_query['author'] = github_username
            stats['prs'] = db['github_pull_requests'].count_documents(pr_query)
        
        results[member_name] = stats
    
    return {
        "period": f"last_{days}_days",
        "metric": metric,
        "comparison": results
    }


async def _get_top_contributors(db, args: Dict[str, Any]) -> Dict:
    """Get top contributors by metric"""
    metric = args["metric"]
    project_key = args.get("project_key")
    days = args.get("days", 30)
    limit = args.get("limit", 10)
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get project repositories if project specified
    repositories = None
    if project_key:
        project = db['projects'].find_one({'key': project_key})
        if project:
            repositories = project.get('repositories', [])
    
    if metric == "commits":
        match_query = {'committed_at': {'$gte': start_date}}
        if repositories:
            match_query['repository'] = {'$in': repositories}
        
        pipeline = [
            {'$match': match_query},
            {'$group': {'_id': '$author_login', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
            {'$limit': limit}
        ]
        results = list(db['github_commits'].aggregate(pipeline))
    
    elif metric == "messages":
        match_query = {'timestamp': {'$gte': start_date}}
        
        pipeline = [
            {'$match': match_query},
            {'$group': {'_id': '$user_name', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
            {'$limit': limit}
        ]
        results = list(db['slack_messages'].aggregate(pipeline))
    
    elif metric == "prs":
        match_query = {'created_at': {'$gte': start_date}}
        if repositories:
            match_query['repository'] = {'$in': repositories}
        
        pipeline = [
            {'$match': match_query},
            {'$group': {'_id': '$author', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
            {'$limit': limit}
        ]
        results = list(db['github_pull_requests'].aggregate(pipeline))
    
    elif metric == "reviews":
        match_query = {'submitted_at': {'$gte': start_date}}
        
        pipeline = [
            {'$match': match_query},
            {'$group': {'_id': '$user', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
            {'$limit': limit}
        ]
        results = list(db.get('github_reviews', db['github_pull_requests']).aggregate(pipeline))
    
    else:
        return {"error": f"Unknown metric: {metric}"}
    
    return {
        "metric": metric,
        "period": f"last_{days}_days",
        "project": project_key,
        "top_contributors": [
            {"name": r['_id'], "count": r['count']} 
            for r in results if r['_id']
        ]
    }


async def _search_activities(db, args: Dict[str, Any]) -> Dict:
    """Search activities by keyword"""
    keyword = args["keyword"]
    source = args.get("source", "all")
    member_name = args.get("member_name")
    days = args.get("days", 7)
    limit = args.get("limit", 20)
    
    start_date = datetime.utcnow() - timedelta(days=days)
    results = []
    
    if source in ["github", "all"]:
        query = {
            'committed_at': {'$gte': start_date},
            'message': {'$regex': keyword, '$options': 'i'}
        }
        if member_name:
            query['author_login'] = {'$regex': member_name, '$options': 'i'}
        
        for commit in db['github_commits'].find(query).limit(limit // 2 if source == "all" else limit):
            results.append({
                "source": "github",
                "type": "commit",
                "author": commit.get('author_login'),
                "message": commit.get('message', '')[:200],
                "repository": commit.get('repository'),
                "timestamp": commit.get('committed_at')
            })
    
    if source in ["slack", "all"]:
        query = {
            'timestamp': {'$gte': start_date},
            'text': {'$regex': keyword, '$options': 'i'}
        }
        if member_name:
            query['user_name'] = {'$regex': member_name, '$options': 'i'}
        
        for msg in db['slack_messages'].find(query).limit(limit // 2 if source == "all" else limit):
            results.append({
                "source": "slack",
                "type": "message",
                "author": msg.get('user_name'),
                "message": msg.get('text', '')[:200],
                "channel": msg.get('channel_name'),
                "timestamp": msg.get('timestamp')
            })
    
    return {
        "keyword": keyword,
        "source": source,
        "period": f"last_{days}_days",
        "count": len(results),
        "results": results
    }


async def _get_weekly_summary(db, args: Dict[str, Any]) -> Dict:
    """Generate weekly summary"""
    project_key = args.get("project_key")
    week_offset = args.get("week_offset", 0)
    
    # Calculate week boundaries (Friday to Thursday)
    now = datetime.utcnow()
    days_since_friday = (now.weekday() - 4) % 7
    this_friday = now - timedelta(days=days_since_friday)
    this_friday = this_friday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    start_date = this_friday + timedelta(weeks=week_offset)
    end_date = start_date + timedelta(days=7)
    
    # Get project info if specified
    repositories = None
    slack_channel_id = None
    project_name = None
    if project_key:
        project = db['projects'].find_one({'key': project_key})
        if project:
            repositories = project.get('repositories', [])
            slack_channel_id = project.get('slack_channel_id')
            project_name = project.get('name')
    
    # GitHub stats
    commit_query = {
        'committed_at': {'$gte': start_date, '$lt': end_date}
    }
    if repositories:
        commit_query['repository'] = {'$in': repositories}
    
    total_commits = db['github_commits'].count_documents(commit_query)
    
    # Top committers
    pipeline = [
        {'$match': commit_query},
        {'$group': {'_id': '$author_login', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}},
        {'$limit': 5}
    ]
    top_committers = list(db['github_commits'].aggregate(pipeline))
    
    # Slack stats
    message_query = {
        'timestamp': {'$gte': start_date, '$lt': end_date}
    }
    if slack_channel_id:
        message_query['channel_id'] = slack_channel_id
    
    total_messages = db['slack_messages'].count_documents(message_query)
    
    return {
        "project": project_name or "All Projects",
        "week": start_date.strftime("%Y-W%W"),
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        },
        "github": {
            "total_commits": total_commits,
            "top_contributors": [
                {"name": c['_id'], "commits": c['count']} 
                for c in top_committers if c['_id']
            ]
        },
        "slack": {
            "total_messages": total_messages
        }
    }


# ============================================================================
# PROMPTS - Pre-defined prompt templates
# ============================================================================

@server.list_prompts()
async def list_prompts() -> List[Prompt]:
    """List available prompts"""
    return [
        Prompt(
            name="analyze_contributor",
            description="Analyze a specific contributor's activity and provide insights",
            arguments=[
                PromptArgument(
                    name="member_name",
                    description="Name of the team member to analyze",
                    required=True
                ),
                PromptArgument(
                    name="period",
                    description="Analysis period (e.g., 'last week', 'last month')",
                    required=False
                )
            ]
        ),
        Prompt(
            name="project_health_check",
            description="Perform a health check on a project's activity",
            arguments=[
                PromptArgument(
                    name="project_key",
                    description="Project key to analyze",
                    required=True
                )
            ]
        ),
        Prompt(
            name="weekly_report",
            description="Generate a weekly activity report",
            arguments=[
                PromptArgument(
                    name="project_key",
                    description="Optional: Project key to focus on",
                    required=False
                )
            ]
        ),
        Prompt(
            name="compare_team",
            description="Compare activity across team members",
            arguments=[
                PromptArgument(
                    name="project_key",
                    description="Optional: Filter by project",
                    required=False
                )
            ]
        ),
    ]


@server.get_prompt()
async def get_prompt(name: str, arguments: Optional[Dict[str, str]] = None) -> GetPromptResult:
    """Get a specific prompt with arguments filled in"""
    
    if name == "analyze_contributor":
        member_name = arguments.get("member_name", "Unknown") if arguments else "Unknown"
        period = arguments.get("period", "last 30 days") if arguments else "last 30 days"
        
        return GetPromptResult(
            description=f"Analyze {member_name}'s contributions",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"""Analyze the contributions of team member "{member_name}" for {period}.

Please provide:
1. **Activity Summary**: Overview of commits, PRs, and Slack messages
2. **Key Contributions**: Notable commits or PRs
3. **Collaboration**: Interaction with other team members
4. **Trends**: Any notable patterns in activity
5. **Recommendations**: Suggestions for the team member

Use the available tools to gather data:
- get_member_activity: Get detailed stats
- search_activities: Find specific contributions
- compare_contributors: Compare with peers"""
                    )
                )
            ]
        )
    
    elif name == "project_health_check":
        project_key = arguments.get("project_key", "Unknown") if arguments else "Unknown"
        
        return GetPromptResult(
            description=f"Health check for {project_key}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"""Perform a health check on project "{project_key}".

Please analyze:
1. **Activity Level**: Is the project active? How many commits/messages?
2. **Team Engagement**: Are all team members contributing?
3. **Code Quality Indicators**: PR review rates, merge times
4. **Communication**: Slack activity, response times
5. **Risks**: Any concerning patterns?
6. **Recommendations**: Actionable suggestions

Use the available tools:
- get_project_activity: Get project-specific stats
- get_top_contributors: See who's most active
- get_weekly_summary: Compare recent weeks"""
                    )
                )
            ]
        )
    
    elif name == "weekly_report":
        project_key = arguments.get("project_key") if arguments else None
        scope = f"project {project_key}" if project_key else "the entire team"
        
        return GetPromptResult(
            description="Generate weekly report",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"""Generate a weekly activity report for {scope}.

Include:
1. **Executive Summary**: Key highlights in 2-3 sentences
2. **GitHub Activity**: Commits, PRs, notable changes
3. **Slack Activity**: Communication patterns
4. **Top Contributors**: Most active team members
5. **Notable Achievements**: Merged PRs, completed features
6. **Areas of Concern**: Low activity, pending reviews
7. **Next Week Focus**: Recommendations

Use the available tools:
- get_weekly_summary: Get structured weekly data
- get_top_contributors: Identify key contributors
- search_activities: Find notable items"""
                    )
                )
            ]
        )
    
    elif name == "compare_team":
        project_key = arguments.get("project_key") if arguments else None
        scope = f"in project {project_key}" if project_key else ""
        
        return GetPromptResult(
            description="Compare team activity",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"""Compare team member activity {scope}.

Provide:
1. **Activity Rankings**: Who's most active by different metrics
2. **Comparison Chart**: Visual representation of contributions
3. **Collaboration Patterns**: Who works together
4. **Balance Assessment**: Is workload evenly distributed?
5. **Recommendations**: Team optimization suggestions

Use the available tools:
- get_top_contributors: Get rankings
- compare_contributors: Direct comparisons
- get_project_activity: Project-level view"""
                    )
                )
            ]
        )
    
    else:
        raise ValueError(f"Unknown prompt: {name}")


# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Run the MCP server"""
    print("🚀 Starting All-Thing-Eye MCP Server...")
    print(f"📊 Connected to MongoDB: {mongo_config['database']}")
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

