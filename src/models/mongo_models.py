"""
MongoDB Models

Pydantic models for MongoDB documents in the All-Thing-Eye project.
These replace the SQLAlchemy models used in the relational database.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from bson import ObjectId


# Custom type for MongoDB ObjectId (Pydantic v2 compatible)
class PyObjectId(str):
    """Custom ObjectId type for Pydantic v2"""
    
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        from pydantic_core import core_schema
        
        def validate(value):
            if isinstance(value, ObjectId):
                return str(value)
            if isinstance(value, str):
                if not ObjectId.is_valid(value):
                    raise ValueError(f"Invalid ObjectId: {value}")
                return value
            raise ValueError(f"Expected ObjectId or str, got {type(value)}")
        
        return core_schema.no_info_after_validator_function(
            validate,
            core_schema.str_schema(),
        )


# =============================================================================
# Main Collections
# =============================================================================

class MemberIdentifier(BaseModel):
    """
    Embedded document for member identifiers
    (was separate table in SQL database)
    """
    source_type: str  # github, slack, notion, google_drive
    source_user_id: str
    source_user_name: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Member(BaseModel):
    """
    Member document
    
    Embeds identifiers that were in a separate table in SQL.
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    name: str
    email: str  # Changed from EmailStr for prototype simplicity
    role: Optional[str] = None
    team: Optional[str] = None
    
    # Denormalized fields for quick access
    github_username: Optional[str] = None
    slack_id: Optional[str] = None
    notion_id: Optional[str] = None
    
    # Embedded identifiers (was separate member_identifiers table)
    identifiers: List[MemberIdentifier] = Field(default_factory=list)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class MemberActivity(BaseModel):
    """
    Member activity document
    
    Unified activity log from all data sources.
    References members collection but denormalizes member_name for display.
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    activity_id: str  # Unique hash for deduplication
    
    # Member reference
    member_id: PyObjectId
    member_name: str  # Denormalized for quick display
    
    # Activity details
    source_type: str  # github, slack, notion, google_drive
    activity_type: str  # commit, pull_request, message, reaction, etc.
    timestamp: datetime
    
    # Flexible metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class DataCollection(BaseModel):
    """
    Data collection run tracking document
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    source_type: str  # github, slack, notion, google_drive
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str  # pending, running, completed, failed
    records_collected: int = 0
    errors: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# =============================================================================
# GitHub Collections
# =============================================================================

class GitHubFileChange(BaseModel):
    """Embedded document for file changes in commits"""
    filename: str
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    status: str  # added, modified, removed


class GitHubCommit(BaseModel):
    """GitHub commit document"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    sha: str
    repository: str
    author_name: str
    author_email: str
    message: str
    date: datetime
    
    # Code changes
    additions: int = 0
    deletions: int = 0
    total_changes: int = 0
    
    # File changes (embedded)
    files: List[GitHubFileChange] = Field(default_factory=list)
    
    # Metadata
    url: str
    verified: bool = False
    
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class GitHubReview(BaseModel):
    """Embedded document for PR reviews"""
    reviewer: str
    state: str  # APPROVED, CHANGES_REQUESTED, COMMENTED
    submitted_at: datetime
    body: Optional[str] = None


class GitHubPullRequest(BaseModel):
    """GitHub pull request document"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    repository: str
    number: int
    title: str
    state: str  # open, closed, merged
    author: str
    
    # PR details
    created_at: datetime
    updated_at: datetime
    merged_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # Code changes
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    commits: int = 0
    
    # Reviews (embedded)
    reviews: List[GitHubReview] = Field(default_factory=list)
    
    # Labels
    labels: List[str] = Field(default_factory=list)
    
    # Assignees
    assignees: List[str] = Field(default_factory=list)
    
    # URLs
    url: str
    
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class GitHubIssue(BaseModel):
    """GitHub issue document"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    repository: str
    number: int
    title: str
    state: str  # open, closed
    author: str
    
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    
    labels: List[str] = Field(default_factory=list)
    assignees: List[str] = Field(default_factory=list)
    
    url: str
    
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# =============================================================================
# Slack Collections
# =============================================================================

class SlackReaction(BaseModel):
    """Embedded document for message reactions"""
    reaction: str
    count: int
    users: List[str] = Field(default_factory=list)


class SlackLink(BaseModel):
    """Embedded document for links in messages"""
    url: str
    type: str  # github_repo, github_pr, external, etc.


class SlackFile(BaseModel):
    """Embedded document for file attachments"""
    id: str
    name: str
    url_private: str
    size: int


class SlackMessage(BaseModel):
    """Slack message document"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    channel_id: str
    channel_name: str  # Denormalized
    ts: str  # Slack timestamp
    
    # User information
    user_id: str
    user_name: str  # Denormalized
    
    # Message content
    text: str
    type: str = "message"
    
    # Thread information
    thread_ts: Optional[str] = None
    reply_count: int = 0
    
    # Reactions (embedded)
    reactions: List[SlackReaction] = Field(default_factory=list)
    
    # Links (embedded)
    links: List[SlackLink] = Field(default_factory=list)
    
    # Files (embedded)
    files: List[SlackFile] = Field(default_factory=list)
    
    posted_at: datetime
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class SlackChannel(BaseModel):
    """Slack channel document"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    channel_id: str
    name: str
    is_private: bool = False
    created: datetime
    num_members: int = 0
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# =============================================================================
# Notion Collections
# =============================================================================

class NotionUser(BaseModel):
    """Embedded document for Notion users"""
    id: str
    name: str
    email: Optional[str] = None


class NotionBlock(BaseModel):
    """Embedded document for Notion page blocks"""
    type: str
    content: str


class NotionPage(BaseModel):
    """Notion page document"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    notion_id: str  # Notion's page ID
    title: str
    
    # Page metadata
    created_time: datetime
    last_edited_time: datetime
    
    # Created/edited by (embedded)
    created_by: NotionUser
    last_edited_by: NotionUser
    
    # Parent information
    parent: Dict[str, Any] = Field(default_factory=dict)
    
    # Properties (flexible schema)
    properties: Dict[str, Any] = Field(default_factory=dict)
    
    # Content (embedded blocks)
    blocks: List[NotionBlock] = Field(default_factory=list)
    
    # Comments count
    comments_count: int = 0
    
    # URL
    url: str
    
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# =============================================================================
# Google Drive Collections
# =============================================================================

class DriveTarget(BaseModel):
    """Embedded document for Drive activity targets"""
    type: str  # document, spreadsheet, presentation, folder
    id: str
    name: str
    url: str


class DriveDetails(BaseModel):
    """Embedded document for Drive activity details"""
    action: str
    description: str
    changed_fields: List[str] = Field(default_factory=list)
    moved_from: Optional[str] = None
    moved_to: Optional[str] = None


class DriveActivity(BaseModel):
    """Google Drive activity document"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    activity_id: str
    type: str  # create, edit, move, delete, share
    
    # Actor information
    actor_email: str
    actor_name: str  # Denormalized
    
    # Target information (embedded)
    target: DriveTarget
    
    # Activity details (embedded)
    details: DriveDetails
    
    time: datetime
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class DriveFolder(BaseModel):
    """Google Drive folder document"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    drive_id: str
    name: str
    owner: str
    created_time: datetime
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

