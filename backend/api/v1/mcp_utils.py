"""
Shared utilities for MCP API and Agent.
Centralized data fetching, member mapping, and data summarization logic.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import os
import json
import re
from collections import Counter
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Cache for member name mapping to reduce DB calls during heavy processing
_MEMBER_CACHE = {}

def get_mongo():
    """Get MongoDB manager from main app."""
    from backend.main import mongo_manager
    return mongo_manager

def github_to_member_name(db, github_username: str) -> str:
    """Convert GitHub username to member display name."""
    if not github_username:
        return "Unknown"
    
    cache_key = f"gh:{github_username.lower()}"
    if cache_key in _MEMBER_CACHE:
        return _MEMBER_CACHE[cache_key]

    # Check member_identifiers collection
    identifier = db['member_identifiers'].find_one({
        'source': 'github',
        'identifier_value': {'$regex': f'^{github_username}$', '$options': 'i'}
    })
    if identifier:
        res = identifier.get('member_name', github_username)
        _MEMBER_CACHE[cache_key] = res
        return res
    
    # Check members collection for github_username field
    member = db['members'].find_one({
        'github_username': {'$regex': f'^{github_username}$', '$options': 'i'}
    })
    if member:
        res = member.get('name', github_username)
        _MEMBER_CACHE[cache_key] = res
        return res
    
    return github_username.capitalize()

def slack_to_member_name(db, slack_username: str) -> str:
    """Convert Slack username or ID to member display name."""
    if not slack_username:
        return "Unknown"
    
    cache_key = f"sl:{slack_username.lower()}"
    if cache_key in _MEMBER_CACHE:
        return _MEMBER_CACHE[cache_key]

    # 1. Try direct member name match (if it's a username)
    member = db['members'].find_one({
        'name': {'$regex': f'^{slack_username}$', '$options': 'i'}
    })
    if member:
        _MEMBER_CACHE[cache_key] = member['name']
        return member['name']
    
    # 2. Check member_identifiers (handles both IDs like U123 and usernames)
    identifier = db['member_identifiers'].find_one({
        'source': 'slack',
        'identifier_value': {'$regex': f'^{slack_username}$', '$options': 'i'}
    })
    if identifier:
        res = identifier.get('member_name', slack_username)
        _MEMBER_CACHE[cache_key] = res
        return res
    
    return slack_username.capitalize()

def replace_slack_mentions(db, text: str) -> str:
    """Replace Slack user IDs (<@U12345>) with real names in text."""
    if not text or '@' not in text:
        return text
    
    # Find all patterns like <@U075F3T4MRB> or @U075F3T4MRB
    mention_pattern = re.compile(r'<@([A-Z0-9]+)>|@([A-Z0-9]{9,})')
    
    def replace_match(match):
        user_id = match.group(1) or match.group(2)
        return f"@{slack_to_member_name(db, user_id)}"
    
    return mention_pattern.sub(replace_match, text)

async def fetch_github_activities(
    db, 
    start_date: Optional[datetime] = None, 
    end_date: Optional[datetime] = None,
    member_name: Optional[str] = None,
    project_key: Optional[str] = None,
    limit: int = 500
) -> Dict[str, Any]:
    """Unified logic to fetch and summarize GitHub activities."""
    query = {}
    if start_date:
        query["date"] = {"$gte": start_date}
    if end_date:
        if "date" in query:
            query["date"]["$lte"] = end_date
        else:
            query["date"] = {"$lte": end_date}
            
    if project_key:
        project = db["projects"].find_one({"key": project_key})
        if project and project.get("repositories"):
            query["repository"] = {"$in": project["repositories"]}

    commits = list(db["github_commits"].find(query).sort("date", -1).limit(limit))
    
    activities = []
    member_counts = Counter()
    repo_counts = Counter()
    
    for commit in commits:
        author = commit.get("author_name") or commit.get("author_login") or "Unknown"
        m_name = github_to_member_name(db, author)
        
        if member_name and m_name.lower() != member_name.lower():
            continue
            
        m_name = m_name or author
        member_counts[m_name] += 1
        repo_counts[commit.get("repository", "unknown")] += 1
        
        activities.append({
            "member": m_name,
            "repository": commit.get("repository"),
            "message": commit.get("message", "")[:100],
            "date": str(commit.get("date", ""))[:16],
            "impact": f"+{commit.get('additions', 0)}/-{commit.get('deletions', 0)}",
        })
        
    return {
        "success": True,
        "total_count": len(activities),
        "summary": {
            "top_contributors": dict(member_counts.most_common(10)),
            "top_repositories": dict(repo_counts.most_common(5)),
        },
        "sample_data": activities[:30]
    }

async def fetch_slack_messages(
    db,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    member_name: Optional[str] = None,
    project_key: Optional[str] = None,
    limit: int = 500
) -> Dict[str, Any]:
    """Unified logic to fetch and summarize Slack messages with ID mapping."""
    query = {"channel_name": {"$ne": "tokamak-partners"}}
    if start_date:
        query["posted_at"] = {"$gte": start_date}
    if end_date:
        if "posted_at" in query:
            query["posted_at"]["$lte"] = end_date
        else:
            query["posted_at"] = {"$lte": end_date}
            
    if project_key:
        project = db["projects"].find_one({"key": project_key})
        if project and project.get("slack_channel_id"):
            query["channel_id"] = project["slack_channel_id"]

    messages = list(db["slack_messages"].find(query).sort("posted_at", -1).limit(limit))
    
    activities = []
    member_counts = Counter()
    channel_counts = Counter()
    
    for msg in messages:
        user = msg.get("user_name") or "Unknown"
        m_name = slack_to_member_name(db, user)
        
        if member_name and m_name.lower() != member_name.lower():
            continue
            
        m_name = m_name or user
        member_counts[m_name] += 1
        channel_counts[msg.get("channel_name", "unknown")] += 1
        
        # Replace IDs in text before sending to AI
        clean_text = replace_slack_mentions(db, msg.get("text", "") or "")
        
        activities.append({
            "member": m_name,
            "channel": msg.get("channel_name", "Unknown"),
            "text": clean_text[:100],
            "date": str(msg.get("posted_at", ""))[:16],
        })
        
    return {
        "success": True,
        "total_count": len(activities),
        "summary": {
            "top_messengers": dict(member_counts.most_common(10)),
            "top_channels": dict(channel_counts.most_common(5)),
        },
        "sample_data": activities[:30]
    }
