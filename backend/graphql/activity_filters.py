"""
Activity Filtering Logic - Common Module

This module provides reusable query builders and filters for fetching activities
across different data sources (GitHub, Slack, Notion, Drive, Recordings).

Used by:
- /activities page
- /members/[id] page (individual activities)
- /projects/[key] page (project activities)
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import strawberry


# ============================================================================
# Helper Functions
# ============================================================================

def get_member_identifiers(db, member_name: str) -> Dict[str, List[str]]:
    """
    Get all identifiers for a member across different sources.
    
    Args:
        db: MongoDB database instance
        member_name: Name of the member
        
    Returns:
        Dict mapping source type to list of identifier values
        Example: {
            'github': ['SonYoungsung'],
            'slack': ['U04DNT2QS31'],
            'email': ['ale@tokamak.network'],
            'recordings': ['Kevin Jeong']
        }
    """
    identifiers = {}
    
    # Synchronous query for member identifiers
    identifier_docs = list(db['member_identifiers'].find({
        'member_name': member_name
    }))
    
    for doc in identifier_docs:
        source = doc.get('source')
        value = doc.get('identifier_value')
        if source and value:
            if source not in identifiers:
                identifiers[source] = []
            identifiers[source].append(value)
    
    return identifiers


def build_identifier_mapping(db) -> Dict[Tuple[str, str], str]:
    """
    Build a mapping of (source, identifier) -> member_name for display purposes.
    
    Returns:
        Dict mapping (source_type, identifier_value) to member display name
        Example: {('email', 'ale@tokamak.network'): 'Ale'}
    """
    mapping = {}
    
    identifier_docs = list(db['member_identifiers'].find())
    
    for doc in identifier_docs:
        source = doc.get('source')
        value = doc.get('identifier_value')
        member_name = doc.get('member_name')
        
        if source and value and member_name:
            mapping[(source, value.lower())] = member_name
    
    return mapping


def should_skip_source_for_project(
    source: str,
    project_config: Optional[Dict[str, Any]]
) -> bool:
    """
    Determine if a data source should be skipped when filtering by project.
    
    Args:
        source: Source type ('github', 'slack', 'notion', 'drive', 'recordings', 'recordings_daily')
        project_config: Project configuration from database (repositories, slack_channel_id, etc.)
        
    Returns:
        True if source should be skipped (no project configuration for this source)
    """
    if not project_config:
        return False
    
    # Check if project has configuration for this source
    if source == 'github':
        return not project_config.get('repositories')
    elif source == 'slack':
        return not project_config.get('slack_channel_id')
    elif source == 'notion':
        return not project_config.get('notion_parent_page_id')
    elif source == 'drive':
        return not project_config.get('drive_folders')
    elif source == 'recordings':
        # Recordings can be filtered by project name in title
        return False
    elif source == 'recordings_daily':
        # Recordings daily don't have project-level filtering
        return True
    
    return False


# ============================================================================
# Query Builders for Each Source
# ============================================================================

def build_github_commits_query(
    member_name: Optional[str] = None,
    member_identifiers: Optional[Dict[str, List[str]]] = None,
    project_repositories: Optional[List[str]] = None,
    keyword: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """Build MongoDB query for GitHub commits"""
    query = {}
    
    # Filter by member (author)
    if member_name and member_identifiers:
        github_usernames = member_identifiers.get('github', [])
        if github_usernames:
            query['author'] = {'$in': github_usernames}
    
    # Filter by project repositories
    if project_repositories:
        query['repository'] = {'$in': project_repositories}
    
    # Filter by keyword (message)
    if keyword:
        query['message'] = {'$regex': keyword, '$options': 'i'}
    
    # Date range
    if start_date:
        query['committed_date'] = {'$gte': start_date}
    if end_date:
        query.setdefault('committed_date', {})['$lte'] = end_date
    
    return query


def build_github_prs_query(
    member_name: Optional[str] = None,
    member_identifiers: Optional[Dict[str, List[str]]] = None,
    project_repositories: Optional[List[str]] = None,
    keyword: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """Build MongoDB query for GitHub pull requests"""
    query = {}
    
    # Filter by member (author)
    if member_name and member_identifiers:
        github_usernames = member_identifiers.get('github', [])
        if github_usernames:
            query['author'] = {'$in': github_usernames}
    
    # Filter by project repositories
    if project_repositories:
        query['repository'] = {'$in': project_repositories}
    
    # Filter by keyword (title or body)
    if keyword:
        query['$or'] = [
            {'title': {'$regex': keyword, '$options': 'i'}},
            {'body': {'$regex': keyword, '$options': 'i'}}
        ]
    
    # Date range
    if start_date:
        query['created_at'] = {'$gte': start_date}
    if end_date:
        query.setdefault('created_at', {})['$lte'] = end_date
    
    return query


def build_github_issues_query(
    member_name: Optional[str] = None,
    member_identifiers: Optional[Dict[str, List[str]]] = None,
    project_repositories: Optional[List[str]] = None,
    keyword: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """Build MongoDB query for GitHub issues"""
    query = {}
    
    # Filter by member (author)
    if member_name and member_identifiers:
        github_usernames = member_identifiers.get('github', [])
        if github_usernames:
            query['user_login'] = {'$in': github_usernames}
    
    # Filter by project repositories
    if project_repositories:
        query['repository'] = {'$in': project_repositories}
    
    # Filter by keyword (title or body)
    if keyword:
        query['$or'] = [
            {'title': {'$regex': keyword, '$options': 'i'}},
            {'body': {'$regex': keyword, '$options': 'i'}}
        ]
    
    # Date range
    if start_date:
        query['created_at'] = {'$gte': start_date}
    if end_date:
        query.setdefault('created_at', {})['$lte'] = end_date
    
    return query


def build_slack_query(
    member_name: Optional[str] = None,
    member_identifiers: Optional[Dict[str, List[str]]] = None,
    project_slack_channel_id: Optional[str] = None,
    keyword: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """Build MongoDB query for Slack messages"""
    query = {}
    
    # Exclude private channel (tokamak-partners)
    query['channel_name'] = {'$ne': 'tokamak-partners'}
    
    # Filter by project slack channel
    if project_slack_channel_id:
        query['channel_id'] = project_slack_channel_id
    
    # Filter by member (user_id or user_name)
    if member_name and member_identifiers:
        slack_ids = member_identifiers.get('slack', [])
        if slack_ids:
            query['$or'] = [
                {'user_id': {'$in': slack_ids}},
                {'user_name': {'$regex': f'^{member_name}$', '$options': 'i'}}
            ]
    
    # Filter by keyword (text content)
    if keyword:
        if '$or' in query:
            # Combine with member filter using $and
            existing_or = query.pop('$or')
            query['$and'] = [
                {'$or': existing_or},
                {'text': {'$regex': keyword, '$options': 'i'}}
            ]
        else:
            query['text'] = {'$regex': keyword, '$options': 'i'}
    
    # Date range
    if start_date:
        query['posted_at'] = {'$gte': start_date}
    if end_date:
        query.setdefault('posted_at', {})['$lte'] = end_date
    
    return query


def build_notion_query(
    member_name: Optional[str] = None,
    member_identifiers: Optional[Dict[str, List[str]]] = None,
    project_notion_page_id: Optional[str] = None,
    keyword: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """Build MongoDB query for Notion pages"""
    query = {}
    and_conditions = []
    
    # Filter by project notion parent page
    if project_notion_page_id:
        and_conditions.append({
            '$or': [
                {'parent.page_id': project_notion_page_id},
                {'parent.database_id': project_notion_page_id}
            ]
        })
    
    # Filter by member (created_by or last_edited_by)
    if member_name and member_identifiers:
        notion_ids = member_identifiers.get('notion', [])
        if notion_ids:
            and_conditions.append({
                '$or': [
                    {'created_by.id': {'$in': notion_ids}},
                    {'last_edited_by.id': {'$in': notion_ids}}
                ]
            })
    
    # Filter by keyword (title)
    if keyword:
        and_conditions.append({
            'title': {'$regex': keyword, '$options': 'i'}
        })
    
    # Combine all AND conditions
    if and_conditions:
        query['$and'] = and_conditions
    
    # Date range
    if start_date:
        query['created_time'] = {'$gte': start_date}
    if end_date:
        query.setdefault('created_time', {})['$lte'] = end_date
    
    return query


def build_drive_query(
    member_name: Optional[str] = None,
    member_identifiers: Optional[Dict[str, List[str]]] = None,
    project_drive_folders: Optional[List[str]] = None,
    keyword: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """Build MongoDB query for Google Drive activities"""
    query = {}
    
    # Filter by project drive folders
    if project_drive_folders:
        query['parent_folders'] = {'$in': project_drive_folders}
    
    # Filter by member (actor email)
    if member_name and member_identifiers:
        drive_emails = member_identifiers.get('drive', []) + member_identifiers.get('email', [])
        if drive_emails:
            query['actor_email'] = {'$in': drive_emails}
    
    # Filter by keyword (title)
    if keyword:
        query['title'] = {'$regex': keyword, '$options': 'i'}
    
    # Date range
    if start_date:
        query['time'] = {'$gte': start_date}
    if end_date:
        query.setdefault('time', {})['$lte'] = end_date
    
    return query


def build_recordings_query(
    member_name: Optional[str] = None,
    member_identifiers: Optional[Dict[str, List[str]]] = None,
    project_key: Optional[str] = None,
    keyword: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """Build MongoDB query for Google Drive recordings"""
    query = {}
    
    # Filter by project key in recording name (title)
    if project_key:
        project_name_pattern = {'$regex': project_key, '$options': 'i'}
        if keyword:
            query['$and'] = [
                {'name': project_name_pattern},
                {'name': {'$regex': keyword, '$options': 'i'}}
            ]
        else:
            query['name'] = project_name_pattern
    elif keyword:
        query['name'] = {'$regex': keyword, '$options': 'i'}
    
    # Filter by member (created_by, name, or participants)
    if member_name:
        recording_names = member_identifiers.get('recordings', []) if member_identifiers else []
        
        or_conditions = [
            {'created_by': {'$regex': f'^{member_name}$', '$options': 'i'}},
            {'created_by': {'$regex': f'\\b{member_name}\\b', '$options': 'i'}},
            {'name': {'$regex': f'\\b{member_name}\\b', '$options': 'i'}},
            {'participants': {'$regex': f'\\b{member_name}\\b', '$options': 'i'}}
        ]
        
        for rec_name in recording_names:
            if rec_name:
                or_conditions.extend([
                    {'created_by': {'$regex': f'^{rec_name}$', '$options': 'i'}},
                    {'created_by': {'$regex': f'\\b{rec_name}\\b', '$options': 'i'}},
                    {'name': {'$regex': f'\\b{rec_name}\\b', '$options': 'i'}},
                    {'participants': {'$regex': f'\\b{rec_name}\\b', '$options': 'i'}}
                ])
        
        # Combine with keyword filter if exists
        if '$and' in query:
            query['$and'].append({'$or': or_conditions})
        else:
            query['$or'] = or_conditions
    
    # Date range
    if start_date:
        query['modifiedTime'] = {'$gte': start_date}
    if end_date:
        query.setdefault('modifiedTime', {})['$lte'] = end_date
    
    return query


def build_recordings_daily_query(
    member_name: Optional[str] = None,
    member_identifiers: Optional[Dict[str, List[str]]] = None,
    keyword: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """Build MongoDB query for recordings daily analysis"""
    query = {}
    
    # Filter by member (participants)
    if member_name:
        recording_names = member_identifiers.get('recordings', []) if member_identifiers else []
        
        or_conditions = [
            {'analysis.participants.name': {'$regex': f'^{member_name}$', '$options': 'i'}},
            {'analysis.participants.name': {'$regex': f'\\b{member_name}\\b', '$options': 'i'}}
        ]
        
        for rec_name in recording_names:
            if rec_name:
                or_conditions.extend([
                    {'analysis.participants.name': {'$regex': f'^{rec_name}$', '$options': 'i'}},
                    {'analysis.participants.name': {'$regex': f'\\b{rec_name}\\b', '$options': 'i'}}
                ])
        
        query['$or'] = or_conditions
    
    # Filter by keyword (summary.overview)
    if keyword:
        if '$or' in query:
            existing_or = query.pop('$or')
            query['$and'] = [
                {'$or': existing_or},
                {'analysis.summary.overview': {'$regex': keyword, '$options': 'i'}}
            ]
        else:
            query['analysis.summary.overview'] = {'$regex': keyword, '$options': 'i'}
    
    # Date range (target_date field)
    if start_date:
        query['target_date'] = {'$gte': start_date.strftime('%Y-%m-%d')}
    if end_date:
        query.setdefault('target_date', {})['$lte'] = end_date.strftime('%Y-%m-%d')
    
    return query

