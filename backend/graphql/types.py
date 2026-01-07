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
    RECORDINGS_DAILY = "recordings_daily"


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
    recording_name: Optional[str] = None
    projects: List[str] = strawberry.field(default_factory=list)  # Internal field
    
    # Employment status fields
    is_active: bool = True  # False if member has resigned
    resigned_at: Optional[datetime] = None  # Resignation date (ISO format)
    resignation_reason: Optional[str] = None  # Optional reason for resignation
    
    @strawberry.field
    def projectKeys(self) -> List[str]:
        """Get list of project keys this member belongs to."""
        return self.projects
    
    @strawberry.field
    async def projectDetails(self, info) -> List['Project']:
        """Get detailed project information for projects this member belongs to."""
        if not self.projects:
            return []
        
        db = info.context['db']
        projects = []
        
        # Find projects by keys
        async for doc in db['projects'].find({'key': {'$in': self.projects}}):
            projects.append(Project(
                id=str(doc['_id']),
                key=doc['key'],
                name=doc.get('name', doc['key']),
                description=doc.get('description'),
                slack_channel=doc.get('slack_channel'),
                lead=doc.get('lead'),
                repositories=doc.get('repositories', []),
                is_active=doc.get('is_active', True),
                member_ids=doc.get('member_ids', [])
            ))
        
        return projects
    
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
            count += await db['slack_messages'].count_documents({
                'user_name': self.name,
                'channel_name': {'$ne': 'tokamak-partners'}  # Exclude private channel
            })
        
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
    
    @strawberry.field
    async def top_collaborators(
        self,
        info,
        limit: int = 10
    ) -> List['Collaborator']:
        """
        Get top collaborators for this member.
        
        Analyzes GitHub and Slack data to find frequent collaborators.
        
        Args:
            limit: Maximum number of collaborators to return
            
        Returns:
            List of Collaborator objects
        """
        from .queries import get_top_collaborators
        return await get_top_collaborators(
            db=info.context['db'],
            member_name=self.name,
            limit=limit
        )
    
    @strawberry.field
    async def active_repositories(
        self,
        info,
        limit: int = 10
    ) -> List['RepositoryActivity']:
        """
        Get repositories where this member is active.
        
        Args:
            limit: Maximum number of repositories to return
            
        Returns:
            List of RepositoryActivity objects
        """
        from .queries import get_active_repositories
        return await get_active_repositories(
            db=info.context['db'],
            member_name=self.name,
            limit=limit
        )
    
    @strawberry.field
    async def activity_stats(
        self,
        info
    ) -> 'ActivityStats':
        """
        Get comprehensive activity statistics for this member.
        
        Returns:
            ActivityStats object with detailed metrics
        """
        from .queries import get_activity_stats
        return await get_activity_stats(
            db=info.context['db'],
            member_name=self.name
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
    slack_channel_id: Optional[str] = None  # Internal field
    lead: Optional[str] = None
    repositories: List[str]
    is_active: bool = True
    member_ids: List[str] = strawberry.field(default_factory=list)  # Internal field
    
    @strawberry.field
    def slackChannelId(self) -> Optional[str]:
        """Get Slack channel ID for this project."""
        return self.slack_channel_id
    
    @strawberry.field
    def memberIds(self) -> List[str]:
        """Get list of member IDs for this project."""
        return self.member_ids
    
    @strawberry.field
    async def members(self, info) -> List['Member']:
        """Get list of members in this project."""
        if not self.member_ids:
            return []
        
        db = info.context['db']
        from bson import ObjectId
        
        print(f"🔍 [Project.members] Project {self.key}: Looking for {len(self.member_ids)} members")
        print(f"🔍 [Project.members] member_ids: {self.member_ids[:3]}...")
        
        # Convert string IDs to ObjectIds for MongoDB query
        object_ids = []
        invalid_ids = []
        for member_id in self.member_ids:
            try:
                # Handle both string and ObjectId formats
                if isinstance(member_id, ObjectId):
                    object_ids.append(member_id)
                else:
                    object_ids.append(ObjectId(str(member_id)))
            except Exception as e:
                invalid_ids.append(str(member_id))
                print(f"⚠️ [Project.members] Invalid member_id: {member_id}, error: {e}")
                continue
        
        if not object_ids:
            if invalid_ids:
                print(f"⚠️ [Project.members] Project {self.key}: All member_ids are invalid: {invalid_ids}")
            return []
        
        if invalid_ids:
            print(f"⚠️ [Project.members] Project {self.key}: {len(invalid_ids)} invalid member_ids: {invalid_ids}")
        
        print(f"🔍 [Project.members] Querying with {len(object_ids)} ObjectIds: {[str(oid) for oid in object_ids[:3]]}...")
        
        # Fetch members from database
        members = []
        found_ids = set()
        async for doc in db['members'].find({'_id': {'$in': object_ids}}):
            found_ids.add(str(doc['_id']))
            members.append(Member(
                id=str(doc['_id']),
                name=doc.get('name', 'Unknown'),
                email=doc.get('email', ''),
                role=doc.get('role'),
                team=doc.get('team'),
                github_username=doc.get('github_username'),
                slack_id=doc.get('slack_id'),
                notion_id=doc.get('notion_id'),
                eoa_address=doc.get('eoa_address'),
                recording_name=doc.get('recording_name'),
                is_active=doc.get('is_active', True),
                resigned_at=doc.get('resigned_at'),
                resignation_reason=doc.get('resignation_reason')
            ))
        
        print(f"✅ [Project.members] Project {self.key}: Found {len(members)}/{len(object_ids)} members")
        
        if len(members) < len(object_ids):
            missing_ids = [str(oid) for oid in object_ids if str(oid) not in found_ids]
            print(f"⚠️ [Project.members] Project {self.key}: Missing {len(missing_ids)} members. IDs: {missing_ids[:3]}...")
            
            # Check if members exist with different ID format
            print(f"🔍 [Project.members] Checking sample members in database...")
            sample_members = []
            async for doc in db['members'].find().limit(5):
                sample_members.append({
                    'id': str(doc['_id']),
                    'name': doc.get('name', 'Unknown')
                })
            print(f"📋 [Project.members] Sample member IDs in DB: {sample_members}")
        
        return members
    
    @strawberry.field
    async def member_count(self, info) -> int:
        """
        Get number of members in this project.
        """
        # Simply return length of member_ids if available
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
        if self.slack_channel and self.slack_channel != 'tokamak-partners':
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


@strawberry.type
class Collaborator:
    """
    Represents a member's collaborator with activity metrics.
    """
    member_name: str
    collaboration_count: int
    collaboration_type: str  # "github", "slack", "both"
    last_collaboration: Optional[datetime] = None


@strawberry.type
class RepositoryActivity:
    """
    Represents activity in a specific repository.
    """
    repository: str
    commit_count: int
    pr_count: int
    issue_count: int
    last_activity: Optional[datetime] = None
    additions: int
    deletions: int


@strawberry.type
class SourceStats:
    """
    Activity statistics by source.
    """
    source: str
    count: int
    percentage: float


@strawberry.type
class WeeklyStats:
    """
    Weekly activity statistics.
    """
    week_start: datetime
    count: int


@strawberry.type
class ActivityStats:
    """
    Comprehensive activity statistics for a member.
    """
    total_activities: int
    by_source: List[SourceStats]
    weekly_trend: List[WeeklyStats]
    last_30_days: int


@strawberry.type
class CollaborationDetail:
    """
    Detailed breakdown of collaboration by source/type.
    """
    source: str  # "github_pr_review", "slack_thread", "meeting", etc.
    activity_count: int
    score: float
    recent_activity: Optional[datetime] = None


@strawberry.type
class Collaboration:
    """
    Represents collaboration relationship between two members.
    """
    collaborator_name: str
    collaborator_id: Optional[str] = None
    total_score: float
    collaboration_details: List[CollaborationDetail]
    common_projects: List[str]  # Projects they worked together on
    interaction_count: int  # Total number of interactions
    first_interaction: Optional[datetime] = None
    last_interaction: Optional[datetime] = None


@strawberry.type
class CollaborationNetwork:
    """
    Complete collaboration network for a member.
    """
    member_name: str
    member_id: Optional[str] = None
    top_collaborators: List[Collaboration]
    total_collaborators: int
    time_range_days: int
    total_score: float  # Sum of all collaboration scores
    generated_at: datetime
