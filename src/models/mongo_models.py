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
    
    # Ethereum address for All-Thing-Eye beta access
    eoa_address: Optional[str] = None  # Ethereum address (EOA)
    
    # Embedded identifiers (was separate member_identifiers table)
    identifiers: List[MemberIdentifier] = Field(default_factory=list)
    
    # Employment status fields
    is_active: bool = True  # False if member has resigned
    resigned_at: Optional[datetime] = None  # Resignation date
    resignation_reason: Optional[str] = None  # Optional reason for resignation
    
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


class GitHubReviewDocument(BaseModel):
    """GitHub review document for separate collection"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")

    # PR reference
    repository: str
    pr_number: int
    pr_title: str
    pr_url: str
    pr_author: str

    # Review details
    reviewer: str  # GitHub username (will be mapped to member name)
    state: str  # APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED
    submitted_at: datetime
    body: Optional[str] = None

    # Code comment specifics (optional)
    comment_path: Optional[str] = None  # File path
    comment_line: Optional[int] = None  # Line number

    # Metadata
    collected_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


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


class DriveFile(BaseModel):
    """Google Drive file document"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    file_id: str = Field(..., unique=True)
    name: str
    owner: str
    mime_type: str
    created_time: datetime
    modified_time: datetime
    size: Optional[int] = None
    parents: List[str] = Field(default_factory=list)
    permissions: List[Dict[str, Any]] = Field(default_factory=list)
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class DriveFolder(BaseModel):
    """Google Drive folder document (alias for DriveFile)"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    drive_id: str
    name: str
    owner: str
    created_time: datetime
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# Alias for backward compatibility
DriveDocument = DriveFile


# =============================================================================
# Notion Models
# =============================================================================

class NotionUser(BaseModel):
    """Notion user information (embedded)"""
    id: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    type: Optional[str] = None  # person, bot
    email: Optional[str] = None


class NotionBlock(BaseModel):
    """Notion block information (embedded)"""
    id: str
    type: str
    has_children: bool = False
    created_time: Optional[datetime] = None
    last_edited_time: Optional[datetime] = None


class NotionPage(BaseModel):
    """Notion page document"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    page_id: str = Field(..., unique=True)
    title: Optional[str] = None
    url: str
    
    # Parent information
    parent_type: Optional[str] = None  # database_id, page_id, workspace
    parent_id: Optional[str] = None
    
    # User information (denormalized)
    created_by: Optional[NotionUser] = None
    last_edited_by: Optional[NotionUser] = None
    
    # Timestamps
    created_time: datetime
    last_edited_time: datetime
    
    # Properties (raw JSON from Notion API)
    properties: Dict[str, Any] = Field(default_factory=dict)
    
    # Comments
    comments: List[Dict[str, Any]] = Field(default_factory=list)
    comments_count: int = 0
    
    # Metadata
    is_archived: bool = False
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class NotionDatabase(BaseModel):
    """Notion database document"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    database_id: str = Field(..., unique=True)
    title: Optional[str] = None
    description: Optional[str] = None
    url: str
    
    # Parent information
    parent_type: Optional[str] = None
    parent_id: Optional[str] = None
    
    # User information (denormalized)
    created_by: Optional[NotionUser] = None
    last_edited_by: Optional[NotionUser] = None
    
    # Timestamps
    created_time: datetime
    last_edited_time: datetime
    
    # Properties schema
    properties: Dict[str, Any] = Field(default_factory=dict)
    
    # Metadata
    is_archived: bool = False
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class Translation(BaseModel):
    """
    Translation cache document
    
    Stores translated text to avoid redundant API calls
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    
    # Unique key: hash of original_text + source_lang + target_lang
    cache_key: str = Field(..., unique=True)
    
    # Original content
    original_text: str
    source_language: str  # e.g., "ko", "en"
    
    # Translated content
    translated_text: str
    target_language: str  # e.g., "ko", "en"
    
    # Translation metadata
    translation_provider: str = "deepl"  # "deepl", "gemini", etc.
    detected_source_language: Optional[str] = None  # Auto-detected if not provided
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class NotionComment(BaseModel):
    """Notion comment document"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    comment_id: str = Field(..., unique=True)
    
    # Parent page
    page_id: str
    discussion_id: Optional[str] = None
    
    # Comment content
    rich_text: List[Dict[str, Any]] = Field(default_factory=list)
    plain_text: Optional[str] = None
    
    # User information (denormalized)
    created_by: Optional[NotionUser] = None
    
    # Timestamp
    created_time: datetime
    last_edited_time: Optional[datetime] = None
    
    # Metadata
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# =============================================================================
# Multi-Tenant Support Collections
# =============================================================================

class TenantBranding(BaseModel):
    """Embedded document for tenant custom branding"""
    primary_color: Optional[str] = "#3B82F6"  # Default blue
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    custom_css: Optional[str] = None


class TenantSettings(BaseModel):
    """Embedded document for tenant configuration settings"""
    timezone: str = "UTC"
    date_format: str = "YYYY-MM-DD"
    language: str = "en"
    features_enabled: List[str] = Field(default_factory=lambda: [
        "github", "slack", "notion", "google_drive"
    ])


class Tenant(BaseModel):
    """
    Tenant document for multi-tenant support.

    Each tenant represents an organization with isolated data.
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    slug: str  # Unique identifier, e.g., "acme-corp"
    name: str  # Display name, e.g., "Acme Corporation"

    # Branding (embedded)
    branding: TenantBranding = Field(default_factory=TenantBranding)

    # Settings (embedded)
    settings: TenantSettings = Field(default_factory=TenantSettings)

    # Plan/subscription info
    plan: str = "free"  # free, starter, professional, enterprise
    max_members: int = 10
    max_projects: int = 5

    # Data source configuration
    github_org: Optional[str] = None
    slack_workspace_id: Optional[str] = None
    notion_workspace_id: Optional[str] = None
    google_drive_folder_id: Optional[str] = None

    # Status
    is_active: bool = True

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class UserRole(BaseModel):
    """
    User role document for role-based access control (RBAC).

    Defines permissions for users within a tenant.
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    tenant_id: PyObjectId  # Reference to tenant
    name: str  # e.g., "admin", "manager", "viewer"

    # Permissions
    permissions: List[str] = Field(default_factory=list)
    # Example permissions:
    # - "members:read", "members:write", "members:delete"
    # - "projects:read", "projects:write", "projects:delete"
    # - "activities:read", "activities:export"
    # - "settings:read", "settings:write"
    # - "tenant:manage"

    # Is this a system role (cannot be deleted)
    is_system_role: bool = False

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class TenantUser(BaseModel):
    """
    Tenant user document linking users to tenants with roles.

    A user can belong to multiple tenants with different roles.
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    tenant_id: PyObjectId  # Reference to tenant

    # User identification
    wallet_address: str  # Ethereum wallet address (primary identifier)
    email: Optional[str] = None
    display_name: Optional[str] = None

    # Role reference
    role_id: PyObjectId  # Reference to UserRole
    role_name: str  # Denormalized for quick access

    # Member link (if this user is also a tracked team member)
    member_id: Optional[PyObjectId] = None

    # Status
    is_active: bool = True

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# =============================================================================
# Projects Collection
# =============================================================================

# =============================================================================
# Support Ticket Collection
# =============================================================================

class SupportTicketMessage(BaseModel):
    """Embedded document for ticket conversation messages"""
    from_type: str  # "reporter" or "admin"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SupportTicket(BaseModel):
    """
    Support ticket document for bug reports, feature requests, and questions.
    Used by the ATI Support Slack bot.
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    ticket_id: str  # Human-readable ID like "TKT-001"

    # Reporter information
    reporter_id: str  # Slack User ID
    reporter_name: str  # Slack display name

    # Ticket details
    category: str  # "bug", "feature", "question"
    title: str
    description: str

    # Status tracking
    status: str = "open"  # "open", "in_progress", "resolved", "closed"

    # Admin handling
    admin_notes: Optional[str] = None

    # Conversation history (embedded)
    messages: List[SupportTicketMessage] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# =============================================================================
# Projects Collection
# =============================================================================

class Project(BaseModel):
    """Project configuration document"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    key: str = Field(..., unique=True)  # e.g., "project-ooo", "project-trh"
    name: str  # Display name
    description: Optional[str] = None
    
    # Slack configuration
    slack_channel: Optional[str] = None  # Channel name
    slack_channel_id: Optional[str] = None  # Channel ID
    
    # Project lead
    lead: Optional[str] = None
    
    # GitHub repositories (auto-synced from Teams API)
    repositories: List[str] = Field(default_factory=list)
    repositories_synced_at: Optional[datetime] = None
    github_team_slug: Optional[str] = None  # GitHub team slug for auto-sync
    
    # Google Drive folders
    drive_folders: List[str] = Field(default_factory=list)
    
    # Notion pages (under dev Internal)
    notion_page_ids: List[str] = Field(default_factory=list)  # Notion page IDs
    notion_parent_page_id: Optional[str] = None  # Parent page ID (dev Internal)
    
    # Sub-projects
    sub_projects: List[str] = Field(default_factory=list)  # e.g., ["drb"] for TRH
    
    # Project members (member IDs from members collection)
    member_ids: List[str] = Field(default_factory=list)  # List of member IDs
    
    # Metadata
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

