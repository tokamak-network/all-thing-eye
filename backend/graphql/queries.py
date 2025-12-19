"""
GraphQL Query Resolvers

Implements query resolvers for fetching data from MongoDB.
"""

import strawberry
from typing import List, Optional, Any, Dict
from datetime import datetime
from bson import ObjectId

from .types import (
    Member, Activity, Project, SourceType, ActivitySummary,
    Collaboration, CollaborationDetail, CollaborationNetwork
)


def ensure_datetime(value: Any) -> Optional[datetime]:
    """
    Ensure a value is converted to timezone-aware datetime object in UTC.
    
    Args:
        value: Timestamp value (datetime, string, or None)
        
    Returns:
        Timezone-aware datetime object in UTC or None if conversion fails
    """
    from datetime import timezone
    
    if value is None:
        return None
    
    if isinstance(value, datetime):
        # If already timezone-aware, convert to UTC
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc)
        # If naive, assume UTC
        else:
            return value.replace(tzinfo=timezone.utc)
    
    if isinstance(value, str):
        try:
            # Try ISO format
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            # Ensure timezone-aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except:
            try:
                # Try other common formats (assume UTC)
                dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                return dt.replace(tzinfo=timezone.utc)
            except:
                return None
    
    return None


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize metadata for JSON serialization.
    
    Converts datetime objects and ObjectIds to strings.
    
    Args:
        metadata: Raw metadata dictionary from MongoDB
        
    Returns:
        Sanitized metadata dictionary safe for JSON serialization
    """
    sanitized = {}
    for key, value in metadata.items():
        if isinstance(value, datetime):
            sanitized[key] = value.isoformat()
        elif isinstance(value, ObjectId):
            sanitized[key] = str(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_metadata(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_metadata(item) if isinstance(item, dict) else
                item.isoformat() if isinstance(item, datetime) else
                str(item) if isinstance(item, ObjectId) else
                item
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


async def get_activities_for_member(
    db,
    member_name: str,
    limit: int = 10,
    source: Optional[SourceType] = None
) -> List[Activity]:
    """
    Helper function to get activities for a specific member.
    
    Args:
        db: MongoDB async database instance
        member_name: Name of the member
        limit: Maximum number of activities to return
        source: Optional filter by data source
        
    Returns:
        List of Activity objects
    """
    activities = []
    
    # GitHub commits
    if not source or source == SourceType.GITHUB:
        async for doc in db['github_commits'].find({'author_name': member_name}).sort('date', -1).limit(limit):
            author_name = doc.get('author_name', member_name)
            timestamp = doc.get('date') or doc.get('committed_date')
            if not timestamp:
                continue
            
            activities.append(Activity(
                id=str(doc['_id']),
                member_name=author_name,
                source_type='github',
                activity_type='commit',
                timestamp=timestamp,
                metadata=sanitize_metadata({
                    'sha': doc.get('sha'),
                    'message': doc.get('message'),
                    'repository': doc.get('repository'),
                    'additions': doc.get('additions', 0),
                    'deletions': doc.get('deletions', 0),
                    'url': doc.get('url')
                })
            ))
    
    # GitHub PRs
    if not source or source == SourceType.GITHUB:
        async for doc in db['github_pull_requests'].find({'author': member_name}).sort('created_at', -1).limit(limit):
            author = doc.get('author', member_name)
            timestamp = doc.get('created_at')
            if not timestamp:
                continue
            
            activities.append(Activity(
                id=str(doc['_id']),
                member_name=author,
                source_type='github',
                activity_type='pull_request',
                timestamp=timestamp,
                metadata=sanitize_metadata({
                    'number': doc.get('number'),
                    'title': doc.get('title'),
                    'state': doc.get('state'),
                    'repository': doc.get('repository'),
                    'url': doc.get('url')
                })
            ))
    
    # Slack messages
    if not source or source == SourceType.SLACK:
        async for doc in db['slack_messages'].find({'user_name': member_name}).sort('posted_at', -1).limit(limit):
            user_name = doc.get('user_name', member_name)
            timestamp = doc.get('posted_at')
            if not timestamp:
                continue
            
            activities.append(Activity(
                id=str(doc['_id']),
                member_name=user_name,
                source_type='slack',
                activity_type='message',
                timestamp=timestamp,
                metadata={
                    'text': doc.get('text'),
                    'channel_name': doc.get('channel_name'),
                    'thread_ts': doc.get('thread_ts')
                }
            ))
    
    # Sort by timestamp and return limited results
    activities.sort(key=lambda a: a.timestamp, reverse=True)
    return activities[:limit]


async def get_top_collaborators(
    db,
    member_name: str,
    limit: int = 10
) -> List:
    """
    Get top collaborators for a member using MongoDB aggregation.
    
    Analyzes GitHub PR reviews, co-authored commits, and Slack interactions.
    """
    from .types import Collaborator
    from datetime import timezone as tz
    
    collaborators = {}
    
    # 1. GitHub PR Reviews (members who reviewed this member's PRs)
    pipeline_pr_reviews = [
        {'$match': {'author': member_name}},
        {'$unwind': '$reviewers'},
        {'$group': {
            '_id': '$reviewers',
            'count': {'$sum': 1},
            'last_date': {'$max': '$created_at'}
        }},
        {'$match': {'_id': {'$ne': member_name}}},  # Exclude self
        {'$sort': {'count': -1}},
        {'$limit': limit * 2}
    ]
    
    try:
        async for doc in db['github_pull_requests'].aggregate(pipeline_pr_reviews):
            reviewer = doc['_id']
            if reviewer and reviewer != member_name:
                if reviewer not in collaborators:
                    collaborators[reviewer] = {
                        'github': doc['count'],
                        'slack': 0,
                        'last_date': ensure_datetime(doc.get('last_date'))
                    }
                else:
                    collaborators[reviewer]['github'] += doc['count']
                    last_date = ensure_datetime(doc.get('last_date'))
                    if last_date and (not collaborators[reviewer]['last_date'] or last_date > collaborators[reviewer]['last_date']):
                        collaborators[reviewer]['last_date'] = last_date
    except Exception as e:
        print(f"Error fetching PR reviews: {e}")
    
    # 2. Slack Interactions (threads, mentions)
    pipeline_slack = [
        {'$match': {'user_name': member_name}},
        {'$group': {
            '_id': '$channel_id',
            'messages': {'$push': {'ts': '$ts', 'thread_ts': '$thread_ts'}}
        }}
    ]
    
    try:
        # Find who replied to this member's messages
        async for doc in db['slack_messages'].aggregate([
            {'$match': {'user_name': {'$ne': member_name}}},
            {'$group': {
                '_id': '$user_name',
                'count': {'$sum': 1},
                'last_date': {'$max': '$posted_at'}
            }},
            {'$sort': {'count': -1}},
            {'$limit': limit * 2}
        ]):
            user = doc['_id']
            if user and user != member_name:
                if user not in collaborators:
                    collaborators[user] = {
                        'github': 0,
                        'slack': doc['count'],
                        'last_date': ensure_datetime(doc.get('last_date'))
                    }
                else:
                    collaborators[user]['slack'] += doc['count']
                    last_date = ensure_datetime(doc.get('last_date'))
                    if last_date and (not collaborators[user]['last_date'] or last_date > collaborators[user]['last_date']):
                        collaborators[user]['last_date'] = last_date
    except Exception as e:
        print(f"Error fetching Slack interactions: {e}")
    
    # Build result list
    result = []
    for name, data in collaborators.items():
        github_count = data['github']
        slack_count = data['slack']
        total = github_count + slack_count
        
        if total > 0:
            collab_type = 'both' if github_count > 0 and slack_count > 0 else ('github' if github_count > 0 else 'slack')
            result.append(Collaborator(
                member_name=name,
                collaboration_count=total,
                collaboration_type=collab_type,
                last_collaboration=data['last_date']
            ))
    
    # Sort by collaboration count and return top N
    result.sort(key=lambda x: x.collaboration_count, reverse=True)
    return result[:limit]


async def get_active_repositories(
    db,
    member_name: str,
    limit: int = 10
) -> List:
    """
    Get repositories where member is active using MongoDB aggregation.
    """
    from .types import RepositoryActivity
    
    repos = {}
    
    # 1. Commits
    pipeline_commits = [
        {'$match': {'author_name': member_name}},
        {'$group': {
            '_id': '$repository',
            'commit_count': {'$sum': 1},
            'additions': {'$sum': '$additions'},
            'deletions': {'$sum': '$deletions'},
            'last_date': {'$max': '$date'}
        }},
        {'$sort': {'commit_count': -1}},
        {'$limit': limit * 2}
    ]
    
    try:
        async for doc in db['github_commits'].aggregate(pipeline_commits):
            repo = doc['_id']
            if repo:
                repos[repo] = {
                    'commit_count': doc['commit_count'],
                    'pr_count': 0,
                    'issue_count': 0,
                    'additions': doc.get('additions', 0),
                    'deletions': doc.get('deletions', 0),
                    'last_date': ensure_datetime(doc.get('last_date'))
                }
    except Exception as e:
        print(f"Error fetching commit stats: {e}")
    
    # 2. Pull Requests
    pipeline_prs = [
        {'$match': {'author': member_name}},
        {'$group': {
            '_id': '$repository',
            'pr_count': {'$sum': 1},
            'last_date': {'$max': '$created_at'}
        }},
        {'$sort': {'pr_count': -1}},
        {'$limit': limit * 2}
    ]
    
    try:
        async for doc in db['github_pull_requests'].aggregate(pipeline_prs):
            repo = doc['_id']
            if repo:
                if repo not in repos:
                    repos[repo] = {
                        'commit_count': 0,
                        'pr_count': doc['pr_count'],
                        'issue_count': 0,
                        'additions': 0,
                        'deletions': 0,
                        'last_date': ensure_datetime(doc.get('last_date'))
                    }
                else:
                    repos[repo]['pr_count'] = doc['pr_count']
                    last_date = ensure_datetime(doc.get('last_date'))
                    if last_date and (not repos[repo]['last_date'] or last_date > repos[repo]['last_date']):
                        repos[repo]['last_date'] = last_date
    except Exception as e:
        print(f"Error fetching PR stats: {e}")
    
    # Build result list
    result = []
    for repo, data in repos.items():
        result.append(RepositoryActivity(
            repository=repo,
            commit_count=data['commit_count'],
            pr_count=data['pr_count'],
            issue_count=data['issue_count'],
            additions=data['additions'],
            deletions=data['deletions'],
            last_activity=data['last_date']
        ))
    
    # Sort by total activity (commits + PRs)
    result.sort(key=lambda x: x.commit_count + x.pr_count, reverse=True)
    return result[:limit]


async def get_activity_stats(
    db,
    member_name: str
) -> 'ActivityStats':
    """
    Get comprehensive activity statistics for a member.
    """
    from .types import ActivityStats, SourceStats, WeeklyStats
    from datetime import datetime, timedelta, timezone as tz
    
    # Calculate date ranges
    now = datetime.now(tz.utc)
    thirty_days_ago = now - timedelta(days=30)
    four_weeks_ago = now - timedelta(weeks=4)
    
    # Count by source
    source_counts = {}
    
    # GitHub
    github_commits = await db['github_commits'].count_documents({'author_name': member_name})
    github_prs = await db['github_pull_requests'].count_documents({'author': member_name})
    source_counts['github'] = github_commits + github_prs
    
    # Slack
    source_counts['slack'] = await db['slack_messages'].count_documents({'user_name': member_name})
    
    # Notion
    source_counts['notion'] = await db['notion_pages'].count_documents({
        '$or': [
            {'created_by.name': member_name},
            {'last_edited_by.name': member_name}
        ]
    })
    
    # Drive
    source_counts['drive'] = await db['drive_activities'].count_documents({'actor_name': member_name})
    
    total = sum(source_counts.values())
    
    # Build source stats with percentages
    by_source = []
    for source, count in source_counts.items():
        percentage = (count / total * 100) if total > 0 else 0
        by_source.append(SourceStats(
            source=source,
            count=count,
            percentage=round(percentage, 2)
        ))
    
    # Sort by count descending
    by_source.sort(key=lambda x: x.count, reverse=True)
    
    # Weekly trend (last 4 weeks)
    weekly_trend = []
    for i in range(4):
        week_start = four_weeks_ago + timedelta(weeks=i)
        week_end = week_start + timedelta(weeks=1)
        
        # Count activities in this week
        week_count = 0
        week_count += await db['github_commits'].count_documents({
            'author_name': member_name,
            'date': {'$gte': week_start, '$lt': week_end}
        })
        week_count += await db['github_pull_requests'].count_documents({
            'author': member_name,
            'created_at': {'$gte': week_start, '$lt': week_end}
        })
        week_count += await db['slack_messages'].count_documents({
            'user_name': member_name,
            'posted_at': {'$gte': week_start, '$lt': week_end}
        })
        
        weekly_trend.append(WeeklyStats(
            week_start=week_start,
            count=week_count
        ))
    
    # Last 30 days count
    last_30_days = 0
    last_30_days += await db['github_commits'].count_documents({
        'author_name': member_name,
        'date': {'$gte': thirty_days_ago}
    })
    last_30_days += await db['github_pull_requests'].count_documents({
        'author': member_name,
        'created_at': {'$gte': thirty_days_ago}
    })
    last_30_days += await db['slack_messages'].count_documents({
        'user_name': member_name,
        'posted_at': {'$gte': thirty_days_ago}
    })
    
    return ActivityStats(
        total_activities=total,
        by_source=by_source,
        weekly_trend=weekly_trend,
        last_30_days=last_30_days
    )


@strawberry.type
class Query:
    """Root Query type for GraphQL API"""
    
    @strawberry.field
    async def members(
        self,
        info,
        limit: int = 100,
        offset: int = 0
    ) -> List[Member]:
        """
        Get all members with pagination.
        
        Args:
            limit: Maximum number of members to return (default: 100)
            offset: Number of members to skip (default: 0)
            
        Returns:
            List of Member objects
        """
        db = info.context['db']
        
        members = []
        # Sort by name alphabetically (case-insensitive)
        async for doc in db['members'].find().sort('name', 1).skip(offset).limit(limit):
            members.append(Member(
                id=str(doc['_id']),
                name=doc['name'],
                email=doc['email'],
                role=doc.get('role'),
                team=doc.get('team'),
                github_username=doc.get('github_username'),
                slack_id=doc.get('slack_id'),
                notion_id=doc.get('notion_id'),
                eoa_address=doc.get('eoa_address'),
                recording_name=doc.get('recording_name')
            ))
        
        return members
    
    @strawberry.field
    async def member(
        self,
        info,
        name: Optional[str] = None,
        id: Optional[str] = None
    ) -> Optional[Member]:
        """
        Get a specific member by name or ID.
        
        Args:
            name: Member name (case-sensitive)
            id: Member ID (MongoDB ObjectId as string)
            
        Returns:
            Member object or None if not found
        """
        db = info.context['db']
        
        query = {}
        if id:
            query['_id'] = ObjectId(id)
        elif name:
            query['name'] = name
        else:
            return None
        
        doc = await db['members'].find_one(query)
        if not doc:
            return None
        
        return Member(
            id=str(doc['_id']),
            name=doc['name'],
            email=doc['email'],
            role=doc.get('role'),
            team=doc.get('team'),
            github_username=doc.get('github_username'),
            slack_id=doc.get('slack_id'),
            notion_id=doc.get('notion_id'),
            eoa_address=doc.get('eoa_address'),
            recording_name=doc.get('recording_name')
        )
    
    @strawberry.field
    async def activities(
        self,
        info,
        source: Optional[SourceType] = None,
        member_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        keyword: Optional[str] = None,
        project_key: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Activity]:
        """
        Query activities with flexible filtering.
        
        This is the main query for fetching team activities across all sources.
        Supports filtering by source, member, date range, keyword search, and project.
        
        Args:
            source: Filter by data source (github, slack, notion, drive)
            member_name: Filter by member name
            start_date: Filter activities after this date
            end_date: Filter activities before this date
            keyword: Search in messages/titles
            project_key: Filter by project key (filters GitHub by repositories)
            limit: Maximum number of activities to return (default: 100)
            offset: Number of activities to skip (default: 0)
            
        Returns:
            List of Activity objects sorted by timestamp (newest first)
        """
        db = info.context['db']
        
        # Debug: Log actual variables received by Strawberry
        import time
        request_id = int(time.time() * 1000) % 100000
        print(f"🔍 [{request_id}] ===== GraphQL Activities Query Start =====")
        print(f"🔍 [{request_id}] Strawberry variable_values: {info.variable_values}")
        print(f"🔍 [{request_id}] Python parameters:")
        print(f"🔍 [{request_id}]   - source: {source} (type: {type(source).__name__})")
        print(f"🔍 [{request_id}]   - member_name: {member_name}")
        print(f"🔍 [{request_id}]   - project_key: {project_key}")
        print(f"🔍 [{request_id}]   - keyword: {keyword}")
        print(f"🔍 [{request_id}]   - start_date: {start_date}")
        print(f"🔍 [{request_id}]   - end_date: {end_date}")
        print(f"🔍 [{request_id}]   - limit: {limit}")
        print(f"🔍 [{request_id}]   - offset: {offset}")
        
        # Get project repositories if project_key is specified
        project_repositories = []
        if project_key:
            project_doc = await db['projects'].find_one({'key': project_key})
            if project_doc:
                project_repositories = project_doc.get('repositories', [])
        
        # Build mapping: identifier -> display name for ALL members (to resolve "Unknown")
        # Uses the same structure as REST API's load_member_mappings
        identifier_to_member = {}
        member_to_identifiers = {}  # For filtering: member_name -> {source: [identifiers]}
        
        print(f"🔍 [{request_id}] 📍 BEFORE member_identifiers loop: source={source}, type={type(source).__name__}")
        
        async for id_doc in db['member_identifiers'].find():
            id_source = id_doc.get('source')  # Renamed to avoid conflict with function parameter
            identifier_value = id_doc.get('identifier_value')
            display_name = id_doc.get('member_name')  # Direct member_name field!
            
            if id_source and identifier_value and display_name:
                # Case-insensitive key for GitHub and email (like REST API)
                if id_source in ['github', 'drive', 'email']:
                    key = (id_source, identifier_value.lower())
                else:
                    key = (id_source, identifier_value)
                
                # Store mapping for display conversion
                identifier_to_member[key] = display_name
                
                # Build reverse mapping for filtering
                if display_name not in member_to_identifiers:
                    member_to_identifiers[display_name] = {}
                if id_source not in member_to_identifiers[display_name]:
                    member_to_identifiers[display_name][id_source] = []
                member_to_identifiers[display_name][id_source].append(identifier_value)
        
        # Get identifiers for the specified member (for filtering)
        member_identifiers = {}
        if member_name and member_name in member_to_identifiers:
            member_identifiers = member_to_identifiers[member_name]
            print(f"🔍 [{request_id}] 👤 Member '{member_name}' identifiers: {member_identifiers}")
        elif member_name:
            print(f"🔍 [{request_id}] ⚠️  Member '{member_name}' NOT FOUND in member_to_identifiers!")
            print(f"🔍 [{request_id}] Available members: {list(member_to_identifiers.keys())[:10]}")
        
        # Checkpoint: Verify source variable hasn't been corrupted
        print(f"🔍 [{request_id}] 📍 CHECKPOINT before sources logic: source={source}, type={type(source).__name__}")
        
        # Determine which sources to query
        # Handle both SourceType enum and string values
        if source:
            source_value = source.value if hasattr(source, 'value') else source
            sources = [source_value]  # No .lower() - keep original case
        else:
            sources = ['github', 'slack', 'notion', 'drive', 'recordings', 'recordings_daily']
        
        print(f"🔍 [{request_id}] ⚡ sources = {sources} (from source={source}, type={type(source).__name__})")
        
        activities = []
        
        # GitHub commits
        if 'github' in sources:
            query = {}
            if member_name:
                # Use GitHub usernames from identifiers if available (REST API pattern)
                github_usernames = member_identifiers.get('github', [])
                if github_usernames:
                    query['author_name'] = {'$in': github_usernames}
                else:
                    # Fallback to display name
                    query['author_name'] = member_name
            if start_date:
                query['date'] = {'$gte': start_date}
            if end_date:
                query['date'] = query.get('date', {})
                query['date']['$lte'] = end_date
            if keyword:
                query['message'] = {'$regex': keyword, '$options': 'i'}
            if project_repositories:
                query['repository'] = {'$in': project_repositories}
            
            async for doc in db['github_commits'].find(query).sort('date', -1).limit(limit * 2):
                # Safely get required fields
                author_name = doc.get('author_name') or doc.get('author', 'Unknown')
                timestamp = ensure_datetime(doc.get('date') or doc.get('committed_date'))
                if not timestamp:
                    continue
                
                # Convert GitHub username to display name (case-insensitive like REST API)
                display_name = identifier_to_member.get(('github', author_name.lower()), author_name)
                # Capitalize first letter (REST API pattern)
                if display_name and isinstance(display_name, str) and len(display_name) > 0:
                    display_name = display_name[0].upper() + display_name[1:]
                
                activities.append(Activity(
                    id=str(doc['_id']),
                    member_name=display_name,
                    source_type='github',
                    activity_type='commit',
                    timestamp=timestamp,
                    metadata=sanitize_metadata({
                        'sha': doc.get('sha'),
                        'message': doc.get('message'),
                        'repository': doc.get('repository'),
                        'additions': doc.get('additions', 0),
                        'deletions': doc.get('deletions', 0),
                        'url': doc.get('url'),
                        'author': doc.get('author'),
                        'date': doc.get('date'),
                        'committed_date': doc.get('committed_date')
                    })
                ))
        
        # GitHub PRs
        if 'github' in sources:
            query = {}
            if member_name:
                # Use GitHub usernames from identifiers if available
                github_usernames = member_identifiers.get('github', [])
                if github_usernames:
                    query['author'] = {'$in': github_usernames}
                else:
                    # Fallback to display name
                    query['author'] = member_name
            if start_date:
                query['created_at'] = {'$gte': start_date}
            if end_date:
                query['created_at'] = query.get('created_at', {})
                query['created_at']['$lte'] = end_date
            if keyword:
                query['title'] = {'$regex': keyword, '$options': 'i'}
            if project_repositories:
                query['repository'] = {'$in': project_repositories}
            
            async for doc in db['github_pull_requests'].find(query).sort('created_at', -1).limit(limit * 2):
                # Safely get required fields
                author = doc.get('author', 'Unknown')
                timestamp = ensure_datetime(doc.get('created_at'))
                if not timestamp:
                    continue
                
                # Convert GitHub username to display name (case-insensitive)
                display_name = identifier_to_member.get(('github', author.lower()), author)
                # Capitalize first letter
                if display_name and isinstance(display_name, str) and len(display_name) > 0:
                    display_name = display_name[0].upper() + display_name[1:]
                
                activities.append(Activity(
                    id=str(doc['_id']),
                    member_name=display_name,
                    source_type='github',
                    activity_type='pull_request',
                    timestamp=timestamp,
                    metadata=sanitize_metadata({
                        'number': doc.get('number'),
                        'title': doc.get('title'),
                        'state': doc.get('state'),
                        'repository': doc.get('repository'),
                        'additions': doc.get('additions', 0),
                        'deletions': doc.get('deletions', 0),
                        'url': doc.get('url'),
                        'created_at': doc.get('created_at'),
                        'updated_at': doc.get('updated_at'),
                        'merged_at': doc.get('merged_at'),
                        'closed_at': doc.get('closed_at')
                    })
                ))
        
        # Slack messages
        if 'slack' in sources:
            query = {}
            
            # Exclude tokamak-partners channel (private channel data)
            query['channel_name'] = {'$ne': 'tokamak-partners'}
            
            if member_name:
                # Use Slack identifiers (REST API pattern: user_id, user_email, user_name)
                slack_identifiers = member_identifiers.get('slack', [])
                print(f"🔍 [{request_id}] 💬 Slack identifiers for '{member_name}': {slack_identifiers}")
                
                if slack_identifiers:
                    # Build $or conditions for multiple search fields (like REST API)
                    or_conditions = []
                    or_conditions.append({'user_id': {'$in': slack_identifiers}})
                    or_conditions.append({'user_email': {'$in': slack_identifiers}})
                    or_conditions.append({'user_name': {'$in': slack_identifiers}})
                    query['$or'] = or_conditions
                else:
                    # Fallback to display name (case-insensitive)
                    query['user_name'] = {'$regex': f'^{member_name}$', '$options': 'i'}
            if start_date:
                query['posted_at'] = {'$gte': start_date}
            if end_date:
                query['posted_at'] = query.get('posted_at', {})
                query['posted_at']['$lte'] = end_date
            if keyword:
                query['text'] = {'$regex': keyword, '$options': 'i'}
            
            print(f"🔍 [{request_id}] 💬 Slack query: {query}")
            
            # Debug: Check actual user_name values in DB
            if member_name:
                sample_users = []
                async for sample_doc in db['slack_messages'].find().limit(10):
                    if 'user_name' in sample_doc:
                        sample_users.append(sample_doc['user_name'])
                print(f"🔍 [{request_id}] 💬 Sample user_name values in DB: {list(set(sample_users))[:5]}")
                
                # Check if query matches any documents
                count = await db['slack_messages'].count_documents(query)
                print(f"🔍 [{request_id}] 💬 Slack messages found for query: {count}")
            
            slack_before = len(activities)
            async for doc in db['slack_messages'].find(query).sort('posted_at', -1).limit(limit * 2):
                # Safely get required fields
                user_name = doc.get('user_name', 'Unknown')
                timestamp = ensure_datetime(doc.get('posted_at'))
                if not timestamp:
                    continue
                
                # Convert Slack username to display name
                display_name = identifier_to_member.get(('slack', user_name), user_name)
                # Capitalize first letter
                if display_name and isinstance(display_name, str) and len(display_name) > 0:
                    display_name = display_name[0].upper() + display_name[1:]
                
                # Build Slack message URL (same logic as REST API)
                channel_id = doc.get('channel_id', '')
                ts = doc.get('ts', '')
                slack_url = None
                if channel_id and ts:
                    # Convert ts (1763525860.094349) to Slack URL format (p1763525860094349)
                    ts_formatted = ts.replace('.', '')
                    slack_url = f"https://tokamak-network.slack.com/archives/{channel_id}/p{ts_formatted}"
                
                activities.append(Activity(
                    id=str(doc['_id']),
                    member_name=display_name,
                    source_type='slack',
                    activity_type='message',
                    timestamp=timestamp,
                    metadata=sanitize_metadata({
                        'text': doc.get('text'),
                        'channel_name': doc.get('channel_name'),
                        'channel_id': doc.get('channel_id'),
                        'thread_ts': doc.get('thread_ts'),
                        'posted_at': doc.get('posted_at'),
                        'reactions': doc.get('reactions', []),
                        'url': slack_url
                    })
                ))
            
            slack_after = len(activities)
            print(f"🔍 [{request_id}] 💬 Slack activities added: {slack_after - slack_before}")
        
        # Notion pages
        if 'notion' in sources:
            query = {}
            if member_name:
                # REST API pattern: only created_by (not last_edited_by)
                notion_ids = member_identifiers.get('notion', [])
                or_conditions = []
                if notion_ids:
                    or_conditions.append({'created_by.id': {'$in': notion_ids}})
                    or_conditions.append({'created_by.email': {'$in': notion_ids}})
                # Always add name search as fallback (case-insensitive)
                or_conditions.append({'created_by.name': {'$regex': f'^{member_name}', '$options': 'i'}})
                query['$or'] = or_conditions
                print(f"🔍 [{request_id}] 📝 Notion identifiers for '{member_name}': {notion_ids}")
            
            if start_date:
                # Notion stores last_edited_time as timezone-naive datetime
                # Convert timezone-aware datetime to timezone-naive UTC for comparison
                from datetime import timezone as tz
                start_date_naive = start_date.astimezone(tz.utc).replace(tzinfo=None)
                query['last_edited_time'] = {'$gte': start_date_naive}
            if end_date:
                # Notion stores last_edited_time as timezone-naive datetime
                # Convert timezone-aware datetime to timezone-naive UTC for comparison
                from datetime import timezone as tz
                end_date_naive = end_date.astimezone(tz.utc).replace(tzinfo=None)
                query['last_edited_time'] = query.get('last_edited_time', {})
                query['last_edited_time']['$lte'] = end_date_naive
            if keyword:
                query['title'] = {'$regex': keyword, '$options': 'i'}
            
            print(f"🔍 [{request_id}] 📝 Notion query: {query}")
            
            async for doc in db['notion_pages'].find(query).sort('last_edited_time', -1).limit(limit * 2):
                # Get the person who actually made the action (last_edited_by preferred)
                last_edited_by = doc.get('last_edited_by', {})
                created_by = doc.get('created_by', {})
                
                # Priority: last_edited_by (the person who actually made the action)
                notion_id = last_edited_by.get('id') or created_by.get('id')
                fallback_name = last_edited_by.get('name') or created_by.get('name', 'Unknown')
                
                # Convert Notion ID to display name
                if notion_id:
                    doc_member_name = identifier_to_member.get(('notion', notion_id), fallback_name)
                else:
                    doc_member_name = fallback_name
                
                # Capitalize first letter
                if doc_member_name and isinstance(doc_member_name, str) and len(doc_member_name) > 0:
                    doc_member_name = doc_member_name[0].upper() + doc_member_name[1:]
                
                # Safely get timestamp
                timestamp = ensure_datetime(doc.get('last_edited_time') or doc.get('created_time'))
                if not timestamp:
                    continue  # Skip documents without timestamp
                
                activities.append(Activity(
                    id=str(doc['_id']),
                    member_name=doc_member_name,
                    source_type='notion',
                    activity_type='page_edit',
                    timestamp=timestamp,
                    metadata=sanitize_metadata({
                        'title': doc.get('title'),
                        'url': doc.get('url'),
                        'created_time': doc.get('created_time'),
                        'last_edited_time': doc.get('last_edited_time'),
                        'created_by': doc.get('created_by'),
                        'last_edited_by': doc.get('last_edited_by'),
                        'parent': doc.get('parent'),
                        'properties': doc.get('properties')
                    })
                ))
        
        # Drive activities
        if 'drive' in sources:
            query = {}
            if member_name:
                # Try to use emails from identifiers (REST API pattern: user_email field)
                emails = member_identifiers.get('email', []) or member_identifiers.get('drive', [])
                print(f"🔍 [{request_id}] 📁 Drive emails for '{member_name}': {emails}")
                if emails:
                    # Use user_email field (like REST API)
                    query['user_email'] = {'$in': emails}
                else:
                    # Fallback to regex search (case-insensitive)
                    query['user_email'] = {'$regex': member_name, '$options': 'i'}
            if start_date:
                # Drive uses 'timestamp' field (not 'time'), and it's timezone-naive
                # Convert timezone-aware datetime to timezone-naive UTC for comparison
                from datetime import timezone as tz
                start_date_naive = start_date.astimezone(tz.utc).replace(tzinfo=None)
                query['timestamp'] = {'$gte': start_date_naive}
            if end_date:
                # Drive uses 'timestamp' field (not 'time'), and it's timezone-naive
                # Convert timezone-aware datetime to timezone-naive UTC for comparison
                from datetime import timezone as tz
                end_date_naive = end_date.astimezone(tz.utc).replace(tzinfo=None)
                query['timestamp'] = query.get('timestamp', {})
                query['timestamp']['$lte'] = end_date_naive
            if keyword:
                query['title'] = {'$regex': keyword, '$options': 'i'}
            
            print(f"🔍 [{request_id}] 📁 Drive query: {query}")
            
            async for doc in db['drive_activities'].find(query).sort('timestamp', -1).limit(limit * 2):
                # Get user email (Drive stores as 'user_email' field, following REST API pattern)
                user_email = doc.get('user_email') or doc.get('actor_email')
                actor_name = doc.get('actor_name')
                
                # Try to get display name from identifier mapping
                display_name = None
                if user_email:
                    # First try email mapping
                    display_name = identifier_to_member.get(('email', user_email.lower()))
                    # Then try drive mapping
                    if not display_name:
                        display_name = identifier_to_member.get(('drive', user_email.lower()))
                    # If still not found, extract name from email (like REST API)
                    if not display_name or '@' in display_name:
                        # Extract username from email and capitalize
                        username = user_email.split('@')[0] if user_email else 'Unknown'
                        display_name = username.capitalize() if username else 'Unknown'
                else:
                    # No email, use actor_name or fallback to Unknown
                    display_name = actor_name or 'Unknown'
                
                # Capitalize first letter
                if display_name and isinstance(display_name, str) and len(display_name) > 0 and display_name != display_name.capitalize():
                    display_name = display_name[0].upper() + display_name[1:]
                
                # Safely get timestamp (time field might not exist)
                timestamp = ensure_datetime(doc.get('time') or doc.get('timestamp') or doc.get('created_at'))
                if not timestamp:
                    continue  # Skip documents without timestamp
                
                # Get target object (if exists)
                target = doc.get('target', {})
                
                activities.append(Activity(
                    id=str(doc['_id']),
                    member_name=display_name,
                    source_type='drive',
                    activity_type=doc.get('event_name', 'activity'),
                    timestamp=timestamp,
                    metadata=sanitize_metadata({
                        # REST API style fields (primary)
                        'action': doc.get('action'),
                        'doc_title': doc.get('doc_title'),
                        'doc_type': doc.get('doc_type'),
                        'url': doc.get('link'),
                        'file_id': doc.get('doc_id'),
                        # Also include target object fields (for fallback)
                        'target': target,
                        'target_name': target.get('name') if target else doc.get('doc_title'),
                        'target_type': target.get('type') if target else doc.get('doc_type'),
                        'target_url': target.get('url') if target else doc.get('link'),
                        # Additional metadata
                        'type': doc.get('type'),
                        'event_name': doc.get('event_name'),
                        'user_email': user_email,
                        'time': doc.get('time')
                    })
                ))
        
        # Recordings (Google Drive recordings via shared_async_db)
        if 'recordings' in sources:
            try:
                from backend.main import mongo_manager
                shared_db = mongo_manager.shared_async_db
                recordings_col = shared_db["recordings"]
                
                query = {}
                
                # Debug: Sample one recording to see actual field structure
                sample_doc = await recordings_col.find_one()
                if sample_doc:
                    print(f"🔍 [{request_id}] 🎥 Sample recording doc fields: {list(sample_doc.keys())}")
                    print(f"🔍 [{request_id}] 🎥 Sample recording creator fields:")
                    print(f"🔍 [{request_id}] 🎥   - createdBy (camelCase): {sample_doc.get('createdBy')}")
                    print(f"🔍 [{request_id}] 🎥   - created_by (snake_case): {sample_doc.get('created_by')}")
                    print(f"🔍 [{request_id}] 🎥   - owner: {sample_doc.get('owner')}")
                    print(f"🔍 [{request_id}] 🎥   - lastModifyingUser: {sample_doc.get('lastModifyingUser')}")
                
                if member_name:
                    print(f"🔍 [{request_id}] 🎥 Filtering by member name: {member_name}")
                    
                    # Get recording_name for this member (if exists)
                    recording_names = member_identifiers.get('recordings', [])
                    print(f"🔍 [{request_id}] 🎥 Recording names for '{member_name}': {recording_names}")
                    
                    # NEW APPROACH: Get meeting_ids from gemini.recordings where member is a participant
                    try:
                        from backend.api.v1.ai_processed import get_gemini_db
                        gemini_db = get_gemini_db()
                        gemini_recordings_col = gemini_db["recordings"]
                        
                        # Build participant query (participants is a string array)
                        participant_query = {
                            'participants': {'$regex': f'\\b{member_name}\\b', '$options': 'i'}
                        }
                        
                        # Add recording_name patterns
                        if recording_names:
                            or_conditions = [
                                {'participants': {'$regex': f'\\b{member_name}\\b', '$options': 'i'}}
                            ]
                            for rec_name in recording_names:
                                if rec_name:
                                    or_conditions.append(
                                        {'participants': {'$regex': f'\\b{rec_name}\\b', '$options': 'i'}}
                                    )
                            participant_query = {'$or': or_conditions}
                        
                        # Get meeting_ids where member is a participant
                        gemini_docs = list(gemini_recordings_col.find(
                            participant_query,
                            {'meeting_id': 1}
                        ))
                        
                        meeting_ids = [doc.get('meeting_id') for doc in gemini_docs if doc.get('meeting_id')]
                        print(f"🔍 [{request_id}] 🎥 Found {len(meeting_ids)} meetings where '{member_name}' is a participant")
                        
                        if meeting_ids:
                            # Filter shared.recordings by _id matching meeting_ids
                            from bson import ObjectId
                            # Convert meeting_id strings to ObjectId
                            object_ids = []
                            for mid in meeting_ids:
                                try:
                                    if isinstance(mid, str):
                                        object_ids.append(ObjectId(mid))
                                    elif isinstance(mid, ObjectId):
                                        object_ids.append(mid)
                                except:
                                    pass
                            
                            if object_ids:
                                query['_id'] = {'$in': object_ids}
                            else:
                                # No valid ObjectIds, return empty results
                                query['_id'] = {'$in': []}
                        else:
                            # No meetings found for this member, return empty results
                            query['_id'] = {'$in': []}
                    
                    except Exception as e:
                        print(f"🔍 [{request_id}] ⚠️  Error querying gemini.recordings: {e}")
                        # Fallback to old method (created_by and name)
                    or_conditions = [
                        {'created_by': {'$regex': f'^{member_name}$', '$options': 'i'}},
                            {'created_by': {'$regex': f'\\b{member_name}\\b', '$options': 'i'}},
                            {'name': {'$regex': f'\\b{member_name}\\b', '$options': 'i'}}
                    ]
                    
                    for rec_name in recording_names:
                        if rec_name:
                                or_conditions.extend([
                                    {'created_by': {'$regex': f'^{rec_name}$', '$options': 'i'}},
                                    {'created_by': {'$regex': f'\\b{rec_name}\\b', '$options': 'i'}},
                                    {'name': {'$regex': f'\\b{rec_name}\\b', '$options': 'i'}}
                                ])
                    
                    query['$or'] = or_conditions
                if start_date:
                    # modifiedTime is stored as ISO string, convert datetime to ISO string for comparison
                    query['modifiedTime'] = {'$gte': start_date.isoformat()}
                if end_date:
                    # modifiedTime is stored as ISO string, convert datetime to ISO string for comparison
                    query['modifiedTime'] = query.get('modifiedTime', {})
                    query['modifiedTime']['$lte'] = end_date.isoformat()
                if keyword:
                    query['name'] = {'$regex': keyword, '$options': 'i'}
                
                print(f"🔍 [{request_id}] 🎥 Recordings query: {query}")
                
                # Debug: Check if query matches any documents
                if member_name:
                    count = await recordings_col.count_documents(query)
                    print(f"🔍 [{request_id}] 🎥 Documents matching query: {count}")
                
                # Async MongoDB query
                recordings_before = len(activities)
                async for doc in recordings_col.find(query).sort('modifiedTime', -1).limit(limit * 2):
                    timestamp = ensure_datetime(doc.get('modifiedTime'))
                    if not timestamp:
                        continue
                    
                    # Get creator (created_by field is email)
                    created_by = doc.get('created_by', 'Unknown')
                    
                    # Convert email to display name
                    if created_by and '@' in str(created_by):
                        display_name = identifier_to_member.get(('email', created_by.lower()), 
                                                               identifier_to_member.get(('drive', created_by.lower()), created_by))
                    else:
                        display_name = created_by
                    
                    # Capitalize first letter
                    if display_name and isinstance(display_name, str) and len(display_name) > 0:
                        display_name = display_name[0].upper() + display_name[1:]
                    
                    activities.append(Activity(
                        id=str(doc['_id']),
                        member_name=display_name,
                        source_type='recordings',
                        activity_type='meeting_recording',
                        timestamp=timestamp,
                        metadata=sanitize_metadata({
                            'name': doc.get('name'),
                            'size': doc.get('size', 0),
                            'recording_id': doc.get('id'),
                            'created_by': doc.get('created_by'),  # Use snake_case from DB
                            'modified_time': doc.get('modifiedTime'),
                            'mime_type': doc.get('mimeType')
                        })
                    ))
                
                recordings_after = len(activities)
                print(f"🔍 [{request_id}] 🎥 Recordings activities added: {recordings_after - recordings_before}")
            except Exception as e:
                print(f"Error fetching recordings: {e}")
                import traceback
                print(traceback.format_exc())
        
        # Recordings Daily (Daily analysis)
        if 'recordings_daily' in sources:
            try:
                from backend.api.v1.ai_processed import get_gemini_db
                gemini_db = get_gemini_db()
                recordings_daily_col = gemini_db["recordings_daily"]
                
                # Debug: Sample one daily doc to see structure
                sample_daily = recordings_daily_col.find_one()
                if sample_daily:
                    print(f"🔍 [{request_id}] 📅 Sample recordings_daily fields: {list(sample_daily.keys())}")
                    
                    # Check analysis.participants structure
                    analysis = sample_daily.get('analysis', {})
                    if analysis and 'participants' in analysis:
                        participants = analysis['participants']
                        print(f"🔍 [{request_id}] 📅 analysis.participants type: {type(participants)}")
                        if isinstance(participants, list) and len(participants) > 0:
                            sample_participant = participants[0]
                            print(f"🔍 [{request_id}] 📅 Sample participant: {sample_participant}")
                        elif isinstance(participants, dict):
                            print(f"🔍 [{request_id}] 📅 Participants dict keys: {list(participants.keys())[:5]}")
                        else:
                            print(f"🔍 [{request_id}] 📅 Participants value: {str(participants)[:200]}")
                
                query = {}
                # recordings_daily uses target_date (date string) instead of timestamp
                if start_date:
                    query['target_date'] = {'$gte': start_date.strftime('%Y-%m-%d')}
                if end_date:
                    query['target_date'] = query.get('target_date', {})
                    query['target_date']['$lte'] = end_date.strftime('%Y-%m-%d')
                if keyword:
                    # Search in analysis.summary.overview field
                    query['analysis.summary.overview'] = {'$regex': keyword, '$options': 'i'}
                
                # If member filter is specified, filter by analysis.participants
                # participants is array of dicts: [{'name': 'Ale Son', ...}, {'name': 'Jake Jang', ...}]
                if member_name:
                    print(f"🔍 [{request_id}] 📅 Filtering recordings_daily by analysis.participants.name containing: {member_name}")
                    
                    # Get recording_name for this member (if exists)
                    recording_names = member_identifiers.get('recordings', [])
                    print(f"🔍 [{request_id}] 📅 Recording names for '{member_name}': {recording_names}")
                    
                    # Build search patterns: search for both member_name and recording_name
                    name_patterns = [
                        {'name': {'$regex': f'\\b{member_name}\\b', '$options': 'i'}}
                    ]
                    
                    # Add recording_name patterns
                    for rec_name in recording_names:
                        if rec_name:
                            # Exact match for recording name (e.g., "YEONGJU BAK")
                            name_patterns.append({'name': {'$regex': f'^{rec_name}$', '$options': 'i'}})
                            # Also try word boundary match
                            name_patterns.append({'name': {'$regex': f'\\b{rec_name}\\b', '$options': 'i'}})
                    
                    # Search for member name OR recording name in participants
                    query['analysis.participants'] = {
                        '$elemMatch': {
                            '$or': name_patterns
                        }
                    }
                
                print(f"🔍 [{request_id}] 📅 recordings_daily query: {query}")
                
                # Debug: Check if query matches any documents
                if member_name:
                    count = recordings_daily_col.count_documents(query)
                    print(f"🔍 [{request_id}] 📅 Documents matching query: {count}")
                    
                    # Check total documents without filter
                    total_count = recordings_daily_col.count_documents({})
                    print(f"🔍 [{request_id}] 📅 Total documents (no filter): {total_count}")
                    
                    # Check recent documents (last 10) to see if member is in participants
                    recent_docs = list(recordings_daily_col.find({}).sort('target_date', -1).limit(10))
                    print(f"🔍 [{request_id}] 📅 Recent 10 documents analysis:")
                    for doc in recent_docs:
                        target_date = doc.get('target_date')
                        analysis = doc.get('analysis', {})
                        participants = analysis.get('participants', []) if analysis else []
                        
                        # Check if member is in participants
                        member_found = False
                        participant_names = []
                        if isinstance(participants, list):
                            for p in participants:
                                if isinstance(p, dict) and 'name' in p:
                                    name = p['name']
                                    participant_names.append(name)
                                    # Check if member_name matches (word boundary)
                                    import re
                                    if re.search(rf'\b{member_name}\b', name, re.IGNORECASE):
                                        member_found = True
                        
                        status = "✅ MATCH" if member_found else "❌ NO MATCH"
                        print(f"🔍 [{request_id}] 📅   {target_date}: {status} | Names: {participant_names[:3]}")
                
                # Sync MongoDB query (recordings_daily uses sync client)
                daily_docs = list(recordings_daily_col.find(query).sort('target_date', -1).limit(limit * 2))
                
                # Debug: Show matched dates
                if member_name and daily_docs:
                    matched_dates = [doc.get('target_date') for doc in daily_docs[:15]]
                    print(f"🔍 [{request_id}] 📅 Matched dates (first 15): {matched_dates}")
                    if len(daily_docs) > 15:
                        print(f"🔍 [{request_id}] 📅 ... and {len(daily_docs) - 15} more documents")
                    
                    # Show date range
                    if daily_docs:
                        oldest = daily_docs[-1].get('target_date')
                        newest = daily_docs[0].get('target_date')
                        print(f"🔍 [{request_id}] 📅 Date range: {newest} to {oldest}")
                
                daily_before = len(activities)
                for doc in daily_docs:
                    target_date = doc.get('target_date')
                    if not target_date:
                        continue
                    
                    # Parse target_date to datetime
                    try:
                        from datetime import datetime as dt
                        timestamp = ensure_datetime(dt.strptime(target_date, '%Y-%m-%d'))
                    except:
                        continue
                    
                    if not timestamp:
                        continue
                    
                    analysis = doc.get('analysis', {})
                    summary = analysis.get('summary', {}) if analysis else {}
                    
                    # Helper function to convert recording name to display name
                    def recording_name_to_display(recording_name: str) -> str:
                        """
                        Convert recording participant name to system display name.
                        Examples: "Ale Son" -> "Ale", "YEONGJU BAK" -> "Zena"
                        """
                        if not recording_name:
                            return recording_name
                        
                        # 1. Try exact match in recordings source (from member_identifiers)
                        display = identifier_to_member.get(('recordings', recording_name))
                        if display:
                            return display[0].upper() + display[1:] if display else display
                        
                        # 2. Try case-insensitive match across all sources
                        for (source, identifier), display in identifier_to_member.items():
                            if identifier.lower() == recording_name.lower():
                                return display[0].upper() + display[1:] if display else display
                        
                        # 3. Try first word match (e.g., "Ale Son" -> "Ale", "Jason Hwang" -> "Jason")
                        first_word = recording_name.split()[0] if recording_name else ""
                        if first_word:
                            # Check if any member's display name starts with or matches first word
                            for display in set(identifier_to_member.values()):
                                if display and display.lower() == first_word.lower():
                                    return display[0].upper() + display[1:] if display else display
                        
                        # Fallback: capitalize first letter of original name
                        return recording_name[0].upper() + recording_name[1:] if recording_name else recording_name
                    
                    # Extract participant names
                    display_name = 'System'
                    participants = analysis.get('participants', []) if analysis else []
                    if isinstance(participants, list) and participants:
                        # If member filter is active, show only the filtered member
                        if member_name:
                            for p in participants:
                                if isinstance(p, dict) and 'name' in p:
                                    name = p['name']
                                    import re
                                    if re.search(rf'\b{member_name}\b', name, re.IGNORECASE):
                                        # Convert to display name
                                        display_name = recording_name_to_display(name)
                                        break
                        else:
                            # No filter: show all participants (up to 3), convert each to display name
                            recording_names = [p.get('name') for p in participants if isinstance(p, dict) and 'name' in p]
                            if recording_names:
                                display_names = [recording_name_to_display(rn) for rn in recording_names[:3]]
                                display_name = ', '.join(display_names)
                                if len(participants) > 3:
                                    display_name += f' +{len(participants) - 3} more'
                    
                    activities.append(Activity(
                        id=str(doc['_id']),
                        member_name=display_name,
                        source_type='recordings_daily',
                        activity_type='daily_analysis',
                        timestamp=timestamp,
                        metadata=sanitize_metadata({
                            'target_date': target_date,
                            'meeting_count': doc.get('meeting_count', 0),
                            'total_duration': doc.get('total_duration', 0),
                            'total_participants': doc.get('total_participants', 0),
                            'summary': summary.get('overview', ''),
                            'key_topics': summary.get('key_topics', []),
                            'decisions': summary.get('decisions', [])
                        })
                    ))
                
                daily_after = len(activities)
                print(f"🔍 [{request_id}] 📅 recordings_daily activities added: {daily_after - daily_before}")
            except Exception as e:
                if "Skip recordings_daily" in str(e):
                    print(f"🔍 [{request_id}] 📅 {str(e)}")
                else:
                    print(f"Error fetching recordings_daily: {e}")
        
        # Sort by timestamp (newest first) and apply pagination
        # Handle mixed datetime/string timestamps
        from datetime import timezone as tz
        
        def get_sort_key(activity):
            ts = activity.timestamp
            if isinstance(ts, datetime):
                # Ensure timezone-aware
                if ts.tzinfo is None:
                    return ts.replace(tzinfo=tz.utc)
                return ts.astimezone(tz.utc)
            elif isinstance(ts, str):
                try:
                    # Try parsing ISO format
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=tz.utc)
                    return dt.astimezone(tz.utc)
                except:
                    # If parsing fails, return a very old date (timezone-aware)
                    return datetime.min.replace(tzinfo=tz.utc)
            else:
                return datetime.min.replace(tzinfo=tz.utc)
        
        activities.sort(key=get_sort_key, reverse=True)
        
        print(f"🔍 [{request_id}] 📊 Total activities before pagination: {len(activities)}")
        print(f"🔍 [{request_id}] 📊 Returning activities[{offset}:{offset + limit}] = {len(activities[offset:offset + limit])} items")
        
        return activities[offset:offset + limit]
    
    @strawberry.field
    async def projects(
        self,
        info,
        is_active: Optional[bool] = None,
        limit: int = 100
    ) -> List[Project]:
        """
        Get all projects.
        
        Args:
            is_active: Filter by active status (None = all projects)
            limit: Maximum number of projects to return
            
        Returns:
            List of Project objects
        """
        db = info.context['db']
        
        query = {}
        if is_active is not None:
            query['is_active'] = is_active
        
        projects = []
        async for doc in db['projects'].find(query).limit(limit):
            projects.append(Project(
                id=str(doc['_id']),
                key=doc['key'],
                name=doc['name'],
                description=doc.get('description'),
                slack_channel=doc.get('slack_channel'),
                lead=doc.get('lead'),
                repositories=doc.get('repositories', []),
                is_active=doc.get('is_active', True),
                member_ids=doc.get('member_ids', [])
            ))
        
        return projects
    
    @strawberry.field
    async def project(
        self,
        info,
        key: Optional[str] = None,
        id: Optional[str] = None
    ) -> Optional[Project]:
        """
        Get a specific project by key or ID.
        
        Args:
            key: Project key (e.g., "project-ooo")
            id: Project ID (MongoDB ObjectId as string)
            
        Returns:
            Project object or None if not found
        """
        db = info.context['db']
        
        query = {}
        if id:
            query['_id'] = ObjectId(id)
        elif key:
            query['key'] = key
        else:
            return None
        
        doc = await db['projects'].find_one(query)
        if not doc:
            return None
        
        return Project(
            id=str(doc['_id']),
            key=doc['key'],
            name=doc['name'],
            description=doc.get('description'),
            slack_channel=doc.get('slack_channel'),
            lead=doc.get('lead'),
            repositories=doc.get('repositories', []),
            is_active=doc.get('is_active', True),
            member_ids=doc.get('member_ids', [])
        )
    
    @strawberry.field
    async def activity_summary(
        self,
        info,
        source: Optional[SourceType] = None,
        member_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> ActivitySummary:
        """
        Get summary statistics for activities.
        
        Args:
            source: Filter by data source
            member_name: Filter by member name
            start_date: Filter activities after this date
            end_date: Filter activities before this date
            
        Returns:
            ActivitySummary with counts and breakdowns
        """
        db = info.context['db']
        
        # Handle both SourceType enum and string values
        if source:
            source_value = source.value if hasattr(source, 'value') else source
            sources = [source_value]
        else:
            sources = ['github', 'slack', 'notion', 'drive']
        
        by_source = {}
        by_type = {}
        total = 0
        
        # Get member mapping if member_name is provided
        member_github_id = None
        member_email = None
        if member_name:
            member_doc = await db['members'].find_one({'name': member_name})
            if member_doc:
                member_github_id = member_doc.get('github_id') or member_doc.get('github_username')
                member_email = member_doc.get('email')
        
        # GitHub
        if 'github' in sources:
            github_query = {}
            if member_github_id:
                github_query['author_name'] = member_github_id
            if start_date:
                github_query['date'] = {'$gte': start_date}
            if end_date:
                github_query['date'] = github_query.get('date', {})
                github_query['date']['$lte'] = end_date
            
            commits_count = await db['github_commits'].count_documents(github_query)
            
            pr_query = {}
            if member_github_id:
                pr_query['author'] = member_github_id
            if start_date:
                pr_query['created_at'] = {'$gte': start_date}
            if end_date:
                pr_query['created_at'] = pr_query.get('created_at', {})
                pr_query['created_at']['$lte'] = end_date
            
            prs_count = await db['github_pull_requests'].count_documents(pr_query)
            
            by_source['github'] = commits_count + prs_count
            by_type['commit'] = commits_count
            by_type['pull_request'] = prs_count
            total += commits_count + prs_count
        
        # Slack
        if 'slack' in sources:
            slack_query = {}
            if member_name:
                slack_query['user_name'] = member_name.lower()
            if start_date:
                slack_query['posted_at'] = {'$gte': start_date}
            if end_date:
                slack_query['posted_at'] = slack_query.get('posted_at', {})
                slack_query['posted_at']['$lte'] = end_date
            
            slack_count = await db['slack_messages'].count_documents(slack_query)
            by_source['slack'] = slack_count
            by_type['message'] = slack_count
            total += slack_count
        
        # Notion
        if 'notion' in sources:
            notion_query = {}
            if member_name:
                notion_query = {
                    '$or': [
                        {'created_by.name': member_name},
                        {'last_edited_by.name': member_name}
                    ]
                }
            if start_date:
                notion_query['last_edited_time'] = {'$gte': start_date}
            if end_date:
                notion_query['last_edited_time'] = notion_query.get('last_edited_time', {})
                notion_query['last_edited_time']['$lte'] = end_date
            
            notion_count = await db['notion_pages'].count_documents(notion_query)
            by_source['notion'] = notion_count
            by_type['page_edit'] = notion_count
            total += notion_count
        
        # Drive
        if 'drive' in sources:
            drive_query = {}
            if member_name or member_email:
                # Try both member name and email
                identifiers = []
                if member_name:
                    identifiers.append(member_name)
                if member_email:
                    identifiers.append(member_email)
                drive_query['actor_name'] = {'$in': identifiers}
            if start_date:
                drive_query['time'] = {'$gte': start_date}
            if end_date:
                drive_query['time'] = drive_query.get('time', {})
                drive_query['time']['$lte'] = end_date
            
            drive_count = await db['drive_activities'].count_documents(drive_query)
            by_source['drive'] = drive_count
            total += drive_count
        
        return ActivitySummary(
            total=total,
            by_source=by_source,
            by_type=by_type,
            date_range_start=start_date,
            date_range_end=end_date
        )
    
    @strawberry.field
    async def member_collaborations(
        self,
        info,
        name: str,
        days: int = 90,
        limit: int = 10,
        min_score: float = 5.0
    ) -> CollaborationNetwork:
        """
        Get collaboration network for a member.
        
        Calculates collaboration scores based on:
        - GitHub PR reviews (3.0x weight)
        - Slack thread participation (2.0x weight)
        - Meeting attendance (2.2x weight)
        - GitHub issue discussions (1.5x weight)
        
        Args:
            name: Member name
            days: Time range in days (default: 90)
            limit: Max number of top collaborators to return
            min_score: Minimum collaboration score threshold
            
        Returns:
            CollaborationNetwork with top collaborators
        """
        db = info.context['db']
        
        from datetime import timedelta
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        collaborations = await calculate_member_collaborations(
            db, name, start_date, end_date, min_score
        )
        
        # Sort by total score descending
        sorted_collaborations = sorted(
            collaborations.values(),
            key=lambda x: x['total_score'],
            reverse=True
        )[:limit]
        
        # Convert to Collaboration objects
        collab_objects = []
        for collab in sorted_collaborations:
            details = [
                CollaborationDetail(
                    source=d['source'],
                    activity_count=d['count'],
                    score=d['score'],
                    recent_activity=d.get('recent_activity')
                )
                for d in collab['details']
            ]
            
            collab_objects.append(
                Collaboration(
                    collaborator_name=collab['name'],
                    collaborator_id=collab.get('id'),
                    total_score=collab['total_score'],
                    collaboration_details=details,
                    common_projects=collab.get('common_projects', []),
                    interaction_count=collab['interaction_count'],
                    first_interaction=collab.get('first_interaction'),
                    last_interaction=collab.get('last_interaction')
                )
            )
        
        total_score = sum(c['total_score'] for c in collaborations.values())
        
        return CollaborationNetwork(
            member_name=name,
            member_id=None,
            top_collaborators=collab_objects,
            total_collaborators=len(collaborations),
            time_range_days=days,
            total_score=total_score,
            generated_at=datetime.utcnow()
        )


async def calculate_member_collaborations(
    db,
    member_name: str,
    start_date: datetime,
    end_date: datetime,
    min_score: float = 5.0
) -> Dict[str, Dict]:
    """
    Calculate collaboration scores for a member with all other members.
    
    Returns:
        Dict mapping collaborator names to their collaboration data
    """
    from collections import defaultdict
    
    collaborations = defaultdict(lambda: {
        'name': '',
        'total_score': 0.0,
        'interaction_count': 0,
        'details': [],
        'common_projects': set(),
        'first_interaction': None,
        'last_interaction': None
    })
    
    # 1. GitHub PR Reviews (weight: 3.0)
    await calculate_github_pr_collaborations(
        db, member_name, start_date, end_date, collaborations
    )
    
    # 2. Slack Thread Participation (weight: 2.0)
    await calculate_slack_thread_collaborations(
        db, member_name, start_date, end_date, collaborations
    )
    
    # 3. Meeting Attendance (weight: 2.2) - DISABLED: No recordings_daily collection
    # await calculate_meeting_collaborations(
    #     db, member_name, start_date, end_date, collaborations
    # )
    
    # 4. GitHub Issue Discussions (weight: 1.5)
    await calculate_github_issue_collaborations(
        db, member_name, start_date, end_date, collaborations
    )
    
    # Filter by minimum score and convert sets to lists
    filtered = {}
    for collab_name, data in collaborations.items():
        if data['total_score'] >= min_score:
            data['common_projects'] = list(data['common_projects'])
            filtered[collab_name] = data
    
    return filtered


async def calculate_github_pr_collaborations(
    db, member_name: str, start_date: datetime, end_date: datetime, collaborations: Dict
):
    """Calculate collaborations from GitHub PR reviews."""
    # Get member's GitHub username
    member_id_doc = await db['member_identifiers'].find_one({
        'member_name': member_name,
        'source': 'github',
        'identifier_type': 'username'
    })
    
    if not member_id_doc:
        return
    
    github_username = member_id_doc.get('identifier_value')
    if not github_username:
        return
    
    # Find PRs where member is author or reviewer
    prs = db['github_pull_requests'].find({
        'created_at': {'$gte': start_date, '$lte': end_date},
        '$or': [
            {'author': github_username},
            {'reviews.reviewer': github_username}
        ]
    })
    
    async for pr in prs:
        author = pr.get('author', '')
        reviewers = set()
        
        for review in pr.get('reviews', []):
            reviewer = review.get('reviewer')
            if reviewer:
                reviewers.add(reviewer)
        
        # Get project from repository
        repo = pr.get('repository', '')
        project_key = await get_project_from_repo(db, repo)
        
        # If member is author, collaborators are reviewers
        if author == github_username:
            for reviewer in reviewers:
                if reviewer != github_username:
                    await add_collaboration(
                        db, collaborations, reviewer, 'github_pr_review',
                        3.0, pr.get('created_at'), project_key
                    )
        
        # If member is reviewer, collaborator is author
        if github_username in reviewers and author != github_username:
            await add_collaboration(
                db, collaborations, author, 'github_pr_review',
                3.0, pr.get('created_at'), project_key
            )


async def calculate_slack_thread_collaborations(
    db, member_name: str, start_date: datetime, end_date: datetime, collaborations: Dict
):
    """Calculate collaborations from Slack thread participation."""
    # Find threads where member participated
    member_threads = set()
    async for msg in db['slack_messages'].find({
        'user_name': member_name.lower(),
        'posted_at': {'$gte': start_date, '$lte': end_date},
        'thread_ts': {'$exists': True, '$ne': None}
    }):
        member_threads.add(msg['thread_ts'])
    
    # For each thread, find co-participants
    for thread_ts in member_threads:
        messages = db['slack_messages'].find({
            'thread_ts': thread_ts,
            'posted_at': {'$gte': start_date, '$lte': end_date}
        })
        
        co_participants = set()
        latest_time = None
        channel_id = None
        
        async for msg in messages:
            user = msg.get('user_name', '')
            if user and user != member_name.lower():
                co_participants.add(user)
            
            msg_time = msg.get('posted_at')
            if msg_time and (not latest_time or msg_time > latest_time):
                latest_time = msg_time
            
            if not channel_id:
                channel_id = msg.get('channel_id')
        
        # Get project from channel
        project_key = await get_project_from_channel(db, channel_id)
        
        # Add collaboration for each co-participant
        for co_participant in co_participants:
            await add_collaboration(
                db, collaborations, co_participant, 'slack_thread',
                2.0, latest_time, project_key
            )


async def calculate_meeting_collaborations(
    db, member_name: str, start_date: datetime, end_date: datetime, collaborations: Dict
):
    """Calculate collaborations from meeting attendance."""
    # Find recordings where member participated
    recordings = db['recordings_daily'].find({
        'target_date': {
            '$gte': start_date.strftime('%Y-%m-%d'),
            '$lte': end_date.strftime('%Y-%m-%d')
        },
        'analysis.participants.name': member_name
    })
    
    async for recording in recordings:
        participants = recording.get('analysis', {}).get('participants', [])
        meeting_date_str = recording.get('target_date')
        meeting_date = datetime.fromisoformat(meeting_date_str) if meeting_date_str else None
        
        # Extract project from title or metadata
        title = recording.get('title', '')
        project_key = extract_project_from_title(title)
        
        # Add collaboration with each co-participant
        for participant in participants:
            participant_name = participant.get('name', '')
            if participant_name and participant_name != member_name:
                await add_collaboration(
                    db, collaborations, participant_name, 'meeting',
                    2.2, meeting_date, project_key
                )


async def calculate_github_issue_collaborations(
    db, member_name: str, start_date: datetime, end_date: datetime, collaborations: Dict
):
    """Calculate collaborations from GitHub issue discussions."""
    # Get member's GitHub username
    member_id_doc = await db['member_identifiers'].find_one({
        'member_name': member_name,
        'source': 'github',
        'identifier_type': 'username'
    })
    
    if not member_id_doc:
        return
    
    github_username = member_id_doc.get('identifier_value')
    if not github_username:
        return
    
    # Find issues where member commented
    issues = db['github_issues'].find({
        'created_at': {'$gte': start_date, '$lte': end_date},
        '$or': [
            {'user.login': github_username},
            {'assignees.login': github_username}
        ]
    })
    
    async for issue in issues:
        author = issue.get('user', {}).get('login', '')
        assignees = {a.get('login') for a in issue.get('assignees', [])}
        
        repo = issue.get('repository_name', '')
        project_key = await get_project_from_repo(db, repo)
        
        # Collaborators are author + assignees (excluding self)
        collaborators = {author} | assignees
        collaborators.discard(github_username)
        collaborators.discard('')
        
        for collaborator in collaborators:
            await add_collaboration(
                db, collaborations, collaborator, 'github_issue',
                1.5, issue.get('created_at'), project_key
            )


async def add_collaboration(
    db, collaborations: Dict, identifier: str, source: str,
    weight: float, timestamp: Optional[datetime], project_key: Optional[str]
):
    """Add a collaboration interaction to the collaborations dict."""
    # Convert GitHub username to member name if needed
    if source.startswith('github'):
        member_name = await get_member_name_from_github(db, identifier)
    elif source.startswith('slack'):
        member_name = await get_member_name_from_slack_username(db, identifier)
    else:
        member_name = identifier.title()
    
    if not member_name or member_name == identifier:
        # Try to capitalize properly
        member_name = identifier.title()
    
    # Calculate recency multiplier (recent = higher score)
    recency_multiplier = 1.0
    if timestamp:
        days_ago = (datetime.utcnow() - timestamp).days
        recency_multiplier = max(0.3, 1.0 - (days_ago / 90))
    
    score = weight * recency_multiplier
    
    # Update collaboration data
    collab = collaborations[member_name]
    if not collab['name']:
        collab['name'] = member_name
    
    collab['total_score'] += score
    collab['interaction_count'] += 1
    
    # Update timestamps
    if timestamp:
        if not collab['first_interaction'] or timestamp < collab['first_interaction']:
            collab['first_interaction'] = timestamp
        if not collab['last_interaction'] or timestamp > collab['last_interaction']:
            collab['last_interaction'] = timestamp
    
    # Add project
    if project_key:
        collab['common_projects'].add(project_key)
    
    # Add to details
    existing_detail = next((d for d in collab['details'] if d['source'] == source), None)
    if existing_detail:
        existing_detail['count'] += 1
        existing_detail['score'] += score
        if timestamp and (not existing_detail.get('recent_activity') or timestamp > existing_detail['recent_activity']):
            existing_detail['recent_activity'] = timestamp
    else:
        collab['details'].append({
            'source': source,
            'count': 1,
            'score': score,
            'recent_activity': timestamp
        })


async def get_member_name_from_github(db, github_username: str) -> Optional[str]:
    """Get member name from GitHub username."""
    doc = await db['member_identifiers'].find_one({
        'source': 'github',
        'identifier_type': 'username',
        'identifier_value': github_username
    })
    return doc.get('member_name') if doc else None


async def get_member_name_from_slack_username(db, slack_username: str) -> Optional[str]:
    """Get member name from Slack username."""
    # Slack stores lowercase usernames
    doc = await db['member_identifiers'].find_one({
        'source': 'slack',
        'identifier_value': {'$regex': f'^{slack_username}$', '$options': 'i'}
    })
    return doc.get('member_name') if doc else None


async def get_project_from_repo(db, repo_name: str) -> Optional[str]:
    """Get project key from repository name."""
    if not repo_name:
        return None
    
    # Projects collection is empty, so infer from repo name
    repo_lower = repo_name.lower()
    
    if 'zk' in repo_lower or 'ooo' in repo_lower or 'zkp' in repo_lower:
        return 'ooo'
    elif 'rollup' in repo_lower or 'trh' in repo_lower:
        return 'trh'
    elif 'drb' in repo_lower:
        return 'drb'
    elif 'eco' in repo_lower or 'grants' in repo_lower:
        return 'eco'
    elif 'syb' in repo_lower or 'sybil' in repo_lower:
        return 'syb'
    
    return None


async def get_project_from_channel(db, channel_id: str) -> Optional[str]:
    """Get project key from Slack channel ID."""
    if not channel_id:
        return None
    
    # Get channel name from channels collection
    channel = await db['slack_channels'].find_one({'channel_id': channel_id})
    if not channel:
        return None
    
    channel_name = channel.get('name', '').lower()
    
    if 'ooo' in channel_name or 'zkp' in channel_name:
        return 'ooo'
    elif 'trh' in channel_name or 'rollup' in channel_name:
        return 'trh'
    elif 'drb' in channel_name:
        return 'drb'
    elif 'eco' in channel_name:
        return 'eco'
    elif 'syb' in channel_name or 'sybil' in channel_name:
        return 'syb'
    
    return None


def extract_project_from_title(title: str) -> Optional[str]:
    """Extract project key from meeting title."""
    title_lower = title.lower()
    
    if 'ooo' in title_lower or 'zk' in title_lower:
        return 'ooo'
    elif 'trh' in title_lower or 'rollup' in title_lower:
        return 'trh'
    elif 'drb' in title_lower:
        return 'drb'
    elif 'eco' in title_lower or 'ecosystem' in title_lower:
        return 'eco'
    elif 'syb' in title_lower or 'sybil' in title_lower:
        return 'syb'
    
    return None
