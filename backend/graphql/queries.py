"""
GraphQL Query Resolvers

Implements query resolvers for fetching data from MongoDB.
"""

import strawberry
from typing import List, Optional, Any, Dict
from datetime import datetime
from bson import ObjectId

from .types import Member, Activity, Project, SourceType, ActivitySummary


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
                eoa_address=doc.get('eoa_address')
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
            eoa_address=doc.get('eoa_address')
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
        
        async for id_doc in db['member_identifiers'].find():
            source = id_doc.get('source')
            identifier_value = id_doc.get('identifier_value')
            display_name = id_doc.get('member_name')  # Direct member_name field!
            
            if source and identifier_value and display_name:
                # Case-insensitive key for GitHub and email (like REST API)
                if source in ['github', 'drive', 'email']:
                    key = (source, identifier_value.lower())
                else:
                    key = (source, identifier_value)
                
                # Store mapping for display conversion
                identifier_to_member[key] = display_name
                
                # Build reverse mapping for filtering
                if display_name not in member_to_identifiers:
                    member_to_identifiers[display_name] = {}
                if source not in member_to_identifiers[display_name]:
                    member_to_identifiers[display_name][source] = []
                member_to_identifiers[display_name][source].append(identifier_value)
        
        # Get identifiers for the specified member (for filtering)
        member_identifiers = {}
        if member_name and member_name in member_to_identifiers:
            member_identifiers = member_to_identifiers[member_name]
        
        # Determine which sources to query
        # Handle both enum and string values
        if source:
            source_value = source.value if hasattr(source, 'value') else source
            # Convert to lowercase for consistent comparison
            sources = [source_value.lower()]
        else:
            sources = ['github', 'slack', 'notion', 'drive', 'recordings', 'recordings_daily']
        
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
            if member_name:
                # Use Slack usernames from identifiers if available
                slack_usernames = member_identifiers.get('slack', [])
                if slack_usernames:
                    query['user_name'] = {'$in': slack_usernames}
                else:
                    # Fallback to display name
                    query['user_name'] = member_name
            if start_date:
                query['posted_at'] = {'$gte': start_date}
            if end_date:
                query['posted_at'] = query.get('posted_at', {})
                query['posted_at']['$lte'] = end_date
            if keyword:
                query['text'] = {'$regex': keyword, '$options': 'i'}
            
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
                        'reactions': doc.get('reactions', [])
                    })
                ))
        
        # Notion pages
        if 'notion' in sources:
            query = {}
            if member_name:
                # Try to use Notion IDs from identifiers
                notion_ids = member_identifiers.get('notion', [])
                if notion_ids:
                    query['$or'] = [
                        {'last_edited_by.id': {'$in': notion_ids}},
                        {'created_by.id': {'$in': notion_ids}}
                    ]
                else:
                    # Fallback to display name
                    query['$or'] = [
                        {'last_edited_by.name': member_name},
                        {'created_by.name': member_name}
                    ]
            if start_date:
                query['last_edited_time'] = {'$gte': start_date}
            if end_date:
                query['last_edited_time'] = query.get('last_edited_time', {})
                query['last_edited_time']['$lte'] = end_date
            if keyword:
                query['title'] = {'$regex': keyword, '$options': 'i'}
            
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
                # Try to use emails from identifiers (Drive uses email)
                emails = member_identifiers.get('email', []) or member_identifiers.get('drive', [])
                if emails:
                    query['$or'] = [
                        {'actor_email': {'$in': emails}},
                        {'actor_name': member_name}
                    ]
                else:
                    # Fallback to display name
                    query['actor_name'] = member_name
            if start_date:
                query['time'] = {'$gte': start_date}
            if end_date:
                query['time'] = query.get('time', {})
                query['time']['$lte'] = end_date
            
            async for doc in db['drive_activities'].find(query).sort('time', -1).limit(limit * 2):
                target = doc.get('target', {})
                # Safely get actor_name with fallback
                actor_name = doc.get('actor_name') or doc.get('actor_email', 'Unknown')
                
                # Convert email to display name (Drive uses email, case-insensitive)
                actor_email = doc.get('actor_email')
                if actor_email:
                    display_name = identifier_to_member.get(('email', actor_email.lower()), 
                                                           identifier_to_member.get(('drive', actor_email.lower()), actor_name))
                else:
                    display_name = actor_name
                
                # Capitalize first letter
                if display_name and isinstance(display_name, str) and len(display_name) > 0:
                    display_name = display_name[0].upper() + display_name[1:]
                
                # Safely get timestamp (time field might not exist)
                timestamp = ensure_datetime(doc.get('time') or doc.get('timestamp') or doc.get('created_at'))
                if not timestamp:
                    continue  # Skip documents without timestamp
                
                activities.append(Activity(
                    id=str(doc['_id']),
                    member_name=display_name,
                    source_type='drive',
                    activity_type=doc.get('type', 'unknown'),
                    timestamp=timestamp,
                    metadata=sanitize_metadata({
                        'type': doc.get('type'),
                        'target_name': target.get('name') if target else None,
                        'target_type': target.get('type') if target else None,
                        'target_url': target.get('url') if target else None,
                        'actor_email': doc.get('actor_email'),
                        'time': doc.get('time'),
                        'target': doc.get('target')
                    })
                ))
        
        # Recordings (Google Drive recordings via shared_async_db)
        if 'recordings' in sources:
            try:
                from backend.main import mongo_manager
                shared_db = mongo_manager.shared_async_db
                recordings_col = shared_db["recordings"]
                
                query = {}
                if start_date:
                    query['modifiedTime'] = {'$gte': start_date}
                if end_date:
                    query['modifiedTime'] = query.get('modifiedTime', {})
                    query['modifiedTime']['$lte'] = end_date
                if keyword:
                    query['name'] = {'$regex': keyword, '$options': 'i'}
                
                # Async MongoDB query
                async for doc in recordings_col.find(query).sort('modifiedTime', -1).limit(limit * 2):
                    timestamp = ensure_datetime(doc.get('modifiedTime'))
                    if not timestamp:
                        continue
                    
                    activities.append(Activity(
                        id=str(doc['_id']),
                        member_name=doc.get('createdBy', 'Unknown'),
                        source_type='recordings',
                        activity_type='meeting_recording',
                        timestamp=timestamp,
                        metadata=sanitize_metadata({
                            'name': doc.get('name'),
                            'size': doc.get('size', 0),
                            'recording_id': doc.get('id'),
                            'created_by': doc.get('createdBy'),
                            'modified_time': doc.get('modifiedTime'),
                            'mime_type': doc.get('mimeType')
                        })
                    ))
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
                
                query = {}
                # recordings_daily uses target_date (date string) instead of timestamp
                if start_date:
                    query['target_date'] = {'$gte': start_date.strftime('%Y-%m-%d')}
                if end_date:
                    query['target_date'] = query.get('target_date', {})
                    query['target_date']['$lte'] = end_date.strftime('%Y-%m-%d')
                
                # Sync MongoDB query
                daily_docs = list(recordings_daily_col.find(query).limit(limit * 2))
                
                # Sort by target_date (newest first)
                daily_docs.sort(key=lambda d: d.get('target_date', ''), reverse=True)
                
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
                    
                    activities.append(Activity(
                        id=str(doc['_id']),
                        member_name='System',  # Daily analysis is system-generated
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
            except Exception as e:
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
        
        sources = [source.value] if source else ['github', 'slack', 'notion', 'drive']
        
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
