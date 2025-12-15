"""
GraphQL Query Resolvers

Implements query resolvers for fetching data from MongoDB.
"""

import strawberry
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

from .types import Member, Activity, Project, SourceType, ActivitySummary


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
                metadata={
                    'sha': doc.get('sha'),
                    'message': doc.get('message'),
                    'repository': doc.get('repository'),
                    'additions': doc.get('additions', 0),
                    'deletions': doc.get('deletions', 0),
                    'url': doc.get('url')
                }
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
                metadata={
                    'number': doc.get('number'),
                    'title': doc.get('title'),
                    'state': doc.get('state'),
                    'repository': doc.get('repository'),
                    'url': doc.get('url')
                }
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
        async for doc in db['members'].find().skip(offset).limit(limit):
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
        limit: int = 100,
        offset: int = 0
    ) -> List[Activity]:
        """
        Query activities with flexible filtering.
        
        This is the main query for fetching team activities across all sources.
        Supports filtering by source, member, date range, and keyword search.
        
        Args:
            source: Filter by data source (github, slack, notion, drive)
            member_name: Filter by member name
            start_date: Filter activities after this date
            end_date: Filter activities before this date
            keyword: Search in messages/titles
            limit: Maximum number of activities to return (default: 100)
            offset: Number of activities to skip (default: 0)
            
        Returns:
            List of Activity objects sorted by timestamp (newest first)
        """
        db = info.context['db']
        
        # Determine which sources to query
        sources = [source.value] if source else ['github', 'slack', 'notion', 'drive']
        
        activities = []
        
        # GitHub commits
        if 'github' in sources:
            query = {}
            if member_name:
                query['author_name'] = member_name
            if start_date:
                query['date'] = {'$gte': start_date}
            if end_date:
                query['date'] = query.get('date', {})
                query['date']['$lte'] = end_date
            if keyword:
                query['message'] = {'$regex': keyword, '$options': 'i'}
            
            async for doc in db['github_commits'].find(query).sort('date', -1).limit(limit * 2):
                # Safely get required fields
                author_name = doc.get('author_name') or doc.get('author', 'Unknown')
                timestamp = doc.get('date') or doc.get('committed_date')
                if not timestamp:
                    continue
                
                activities.append(Activity(
                    id=str(doc['_id']),
                    member_name=author_name,
                    source_type='github',
                    activity_type='commit',
                    timestamp=timestamp,
                    metadata={
                        'sha': doc.get('sha'),
                        'message': doc.get('message'),
                        'repository': doc.get('repository'),
                        'additions': doc.get('additions', 0),
                        'deletions': doc.get('deletions', 0),
                        'url': doc.get('url')
                    }
                ))
        
        # GitHub PRs
        if 'github' in sources:
            query = {}
            if member_name:
                query['author'] = member_name
            if start_date:
                query['created_at'] = {'$gte': start_date}
            if end_date:
                query['created_at'] = query.get('created_at', {})
                query['created_at']['$lte'] = end_date
            if keyword:
                query['title'] = {'$regex': keyword, '$options': 'i'}
            
            async for doc in db['github_pull_requests'].find(query).sort('created_at', -1).limit(limit * 2):
                # Safely get required fields
                author = doc.get('author', 'Unknown')
                timestamp = doc.get('created_at')
                if not timestamp:
                    continue
                
                activities.append(Activity(
                    id=str(doc['_id']),
                    member_name=author,
                    source_type='github',
                    activity_type='pull_request',
                    timestamp=timestamp,
                    metadata={
                        'number': doc.get('number'),
                        'title': doc.get('title'),
                        'state': doc.get('state'),
                        'repository': doc.get('repository'),
                        'additions': doc.get('additions', 0),
                        'deletions': doc.get('deletions', 0),
                        'url': doc.get('url')
                    }
                ))
        
        # Slack messages
        if 'slack' in sources:
            query = {}
            if member_name:
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
                        'channel_id': doc.get('channel_id'),
                        'thread_ts': doc.get('thread_ts')
                    }
                ))
        
        # Notion pages
        if 'notion' in sources:
            query = {}
            if member_name:
                query['$or'] = [
                    {'created_by.name': member_name},
                    {'last_edited_by.name': member_name}
                ]
            if start_date:
                query['last_edited_time'] = {'$gte': start_date}
            if end_date:
                query['last_edited_time'] = query.get('last_edited_time', {})
                query['last_edited_time']['$lte'] = end_date
            if keyword:
                query['title'] = {'$regex': keyword, '$options': 'i'}
            
            async for doc in db['notion_pages'].find(query).sort('last_edited_time', -1).limit(limit * 2):
                # Determine member name from created_by or last_edited_by
                doc_member_name = member_name
                if not doc_member_name:
                    created_by = doc.get('created_by', {})
                    doc_member_name = created_by.get('name', 'Unknown')
                
                # Safely get timestamp
                timestamp = doc.get('last_edited_time') or doc.get('created_time')
                if not timestamp:
                    continue  # Skip documents without timestamp
                
                activities.append(Activity(
                    id=str(doc['_id']),
                    member_name=doc_member_name,
                    source_type='notion',
                    activity_type='page_edit',
                    timestamp=timestamp,
                    metadata={
                        'title': doc.get('title'),
                        'url': doc.get('url'),
                        'created_time': doc.get('created_time'),
                        'last_edited_time': doc.get('last_edited_time')
                    }
                ))
        
        # Drive activities
        if 'drive' in sources:
            query = {}
            if member_name:
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
                
                # Safely get timestamp (time field might not exist)
                timestamp = doc.get('time') or doc.get('timestamp') or doc.get('created_at')
                if not timestamp:
                    continue  # Skip documents without timestamp
                
                activities.append(Activity(
                    id=str(doc['_id']),
                    member_name=actor_name,
                    source_type='drive',
                    activity_type=doc.get('type', 'unknown'),
                    timestamp=timestamp,
                    metadata={
                        'type': doc.get('type'),
                        'target_name': target.get('name'),
                        'target_type': target.get('type'),
                        'target_url': target.get('url'),
                        'actor_email': doc.get('actor_email')
                    }
                ))
        
        # Sort by timestamp (newest first) and apply pagination
        activities.sort(key=lambda a: a.timestamp, reverse=True)
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
                is_active=doc.get('is_active', True)
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
            is_active=doc.get('is_active', True)
        )
    
    @strawberry.field
    async def activity_summary(
        self,
        info,
        source: Optional[SourceType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> ActivitySummary:
        """
        Get summary statistics for activities.
        
        Args:
            source: Filter by data source
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
        
        # GitHub
        if 'github' in sources:
            github_query = {}
            if start_date:
                github_query['date'] = {'$gte': start_date}
            if end_date:
                github_query['date'] = github_query.get('date', {})
                github_query['date']['$lte'] = end_date
            
            commits_count = await db['github_commits'].count_documents(github_query)
            
            pr_query = {}
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
