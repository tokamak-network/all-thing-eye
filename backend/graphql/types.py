"""
GraphQL Types

Defines Strawberry GraphQL types for the All-Thing-Eye platform.
These types map to MongoDB collections and provide field resolvers.
"""

import strawberry
from typing import List, Optional
from datetime import datetime
from enum import Enum


@strawberry.enum
class SourceType(Enum):
    """Data source types"""
    GITHUB = "github"
    SLACK = "slack"
    NOTION = "notion"
    DRIVE = "drive"
    RECORDINGS = "recordings"


@strawberry.type
class Member:
    """
    Member type representing a team member.
    
    Corresponds to 'members' collection in MongoDB.
    """
    id: str
    name: str
    email: str
    role: Optional[str] = None
    team: Optional[str] = None
    github_username: Optional[str] = None
    slack_id: Optional[str] = None
    notion_id: Optional[str] = None
    eoa_address: Optional[str] = None
    
    @strawberry.field
    async def activity_count(
        self,
        info,
        source: Optional[SourceType] = None
    ) -> int:
        """
        Get total activity count for this member.
        
        Uses DataLoader for batch loading when no source filter is specified.
        
        Args:
            source: Optional filter by data source
            
        Returns:
            Total number of activities
        """
        # Use DataLoader for batch loading (all sources)
        if not source:
            dataloaders = info.context.get('dataloaders')
            if dataloaders:
                return await dataloaders['activity_counts'].load(self.name)
        
        # Fallback to direct query if source filter is specified
        db = info.context['db']
        count = 0
        
        # GitHub activities
        if not source or source == SourceType.GITHUB:
            count += await db['github_commits'].count_documents({'author_name': self.name})
            count += await db['github_pull_requests'].count_documents({'author': self.name})
        
        # Slack activities
        if not source or source == SourceType.SLACK:
            count += await db['slack_messages'].count_documents({'user_name': self.name})
        
        # Notion activities
        if not source or source == SourceType.NOTION:
            notion_count = await db['notion_pages'].count_documents({
                '$or': [
                    {'created_by.name': self.name},
                    {'last_edited_by.name': self.name}
                ]
            })
            count += notion_count
        
        # Drive activities
        if not source or source == SourceType.DRIVE:
            count += await db['drive_activities'].count_documents({'actor_name': self.name})
        
        return count
    
    @strawberry.field
    async def recent_activities(
        self,
        info,
        limit: int = 10,
        source: Optional[SourceType] = None
    ) -> List['Activity']:
        """
        Get recent activities for this member.
        
        Uses DataLoader for batch loading to prevent N+1 queries.
        
        Args:
            limit: Maximum number of activities to return
            source: Optional filter by data source
            
        Returns:
            List of recent activities
        """
        # Use DataLoader for batch loading
        dataloaders = info.context.get('dataloaders')
        
        if dataloaders:
            # DataLoader key: (member_name, limit, source)
            return await dataloaders['recent_activities'].load(
                (self.name, limit, source)
            )
        
        # Fallback to direct query if DataLoader not available
        from .queries import get_activities_for_member
        return await get_activities_for_member(
            db=info.context['db'],
            member_name=self.name,
            limit=limit,
            source=source
        )


@strawberry.type
class Activity:
    """
    Unified activity type representing any team activity.
    
    Aggregates data from multiple sources (GitHub, Slack, Notion, Drive).
    """
    id: str
    member_name: str
    source_type: str
    activity_type: str
    timestamp: datetime
    metadata: strawberry.scalars.JSON
    
    @strawberry.field
    def repository(self) -> Optional[str]:
        """Get repository name for GitHub activities"""
        if self.source_type == 'github':
            return self.metadata.get('repository')
        return None
    
    @strawberry.field
    def message(self) -> Optional[str]:
        """Get message content (commit message, Slack message, etc.)"""
        if self.source_type == 'github':
            return self.metadata.get('message') or self.metadata.get('title')
        elif self.source_type == 'slack':
            return self.metadata.get('text')
        elif self.source_type == 'notion':
            return self.metadata.get('title')
        return None
    
    @strawberry.field
    def url(self) -> Optional[str]:
        """Get URL to the original activity"""
        return self.metadata.get('url')


@strawberry.type
class ActivitySummary:
    """
    Summary statistics for activities.
    """
    total: int
    by_source: strawberry.scalars.JSON
    by_type: strawberry.scalars.JSON
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None


@strawberry.type
class Project:
    """
    Project type representing a project/team.
    
    Corresponds to 'projects' collection in MongoDB.
    """
    id: str
    key: str
    name: str
    description: Optional[str] = None
    slack_channel: Optional[str] = None
    repositories: List[str]
    is_active: bool = True
    member_ids: List[str] = strawberry.field(default_factory=list)  # Internal field
    
    @strawberry.field
    async def member_count(self, info) -> int:
        """
        Get number of members in this project.
        
        Uses DataLoader for batch loading when querying multiple projects.
        """
        # Use DataLoader for batch loading
        dataloaders = info.context.get('dataloaders')
        if dataloaders and self.member_ids:
            return await dataloaders['project_member_counts'].load(self.member_ids)
        
        # Fallback: just return length of member_ids
        if self.member_ids:
            return len(self.member_ids)
        
        # If member_ids not loaded, query database
        db = info.context['db']
        from bson import ObjectId
        
        project_doc = await db['projects'].find_one({'_id': ObjectId(self.id)})
        if not project_doc:
            return 0
        
        member_ids = project_doc.get('member_ids', [])
        return len(member_ids)
    
    @strawberry.field
    async def activity_summary(
        self,
        info,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> ActivitySummary:
        """Get activity statistics for this project"""
        db = info.context['db']
        
        # Count GitHub activities for project repositories
        github_query = {'repository': {'$in': self.repositories}}
        if start_date:
            github_query['date'] = {'$gte': start_date}
        if end_date:
            github_query['date'] = github_query.get('date', {})
            github_query['date']['$lte'] = end_date
        
        github_commits = await db['github_commits'].count_documents(github_query)
        github_prs = await db['github_pull_requests'].count_documents(github_query)
        
        # Count Slack activities (if slack_channel exists)
        slack_count = 0
        if self.slack_channel:
            slack_query = {'channel_name': self.slack_channel}
            if start_date:
                slack_query['posted_at'] = {'$gte': start_date}
            if end_date:
                slack_query['posted_at'] = slack_query.get('posted_at', {})
                slack_query['posted_at']['$lte'] = end_date
            
            slack_count = await db['slack_messages'].count_documents(slack_query)
        
        total = github_commits + github_prs + slack_count
        
        return ActivitySummary(
            total=total,
            by_source={
                'github': github_commits + github_prs,
                'slack': slack_count
            },
            by_type={
                'commit': github_commits,
                'pull_request': github_prs,
                'message': slack_count
            },
            date_range_start=start_date,
            date_range_end=end_date
        )
