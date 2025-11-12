# Database Schema Reference

**Last Updated**: November 10, 2025

This document defines all database schemas used in the All-Thing-Eye project. Always refer to this document when writing queries or modifying database structures.

---

## Overview

The system uses multiple databases:

- **Main Database** (`main.db`): Member index and cross-source activity tracking
- **Source Databases**: One per data source (e.g., `github.db`, `slack.db`)

---

## Main Database (`main.db`)

### Table: `members`

Stores team member information.

```sql
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Columns:**

- `id` (INTEGER): Primary key, auto-increment
- `name` (TEXT): Member's name, **UNIQUE**, **NOT NULL**
- `email` (TEXT): Member's email address
- `created_at` (TIMESTAMP): Registration timestamp

**Important Notes:**

- **`name` is the PRIMARY IDENTIFIER** for all member queries
- `name` should match the 'name' column from `members.csv` (e.g., 'Ale', 'Kevin', 'Jason')
- **ALL QUERIES use `name` as the key**, not email or other identifiers
- Email is stored for reference but is NOT used for member lookups
- Example: Query for 'Ale', not 'ale@tokamak.network'

---

### Table: `member_identifiers`

Maps members to their source-specific IDs (GitHub login, Slack ID, etc.).

```sql
CREATE TABLE IF NOT EXISTS member_identifiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    source_user_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_id) REFERENCES members(id),
    UNIQUE(source_type, source_user_id)
)
```

**Columns:**

- `id` (INTEGER): Primary key, auto-increment
- `member_id` (INTEGER): Foreign key to `members.id`
- `source_type` (TEXT): Data source type (`'github'`, `'slack'`, `'notion'`, etc.)
- `source_user_id` (TEXT): User ID in the external source
- `created_at` (TIMESTAMP): Registration timestamp

**Important Notes:**

- **CRITICAL**: `source_user_id` must match the **EXACT CASE** used in source databases
- Example: GitHub stores `SonYoungsung` (camelCase), so member_identifiers must also store `SonYoungsung`
- ❌ **WRONG**: Storing `sonyoungsung` (lowercase) will cause query failures
- ✅ **CORRECT**: Store the exact username from the source system
- Composite unique constraint on (`source_type`, `source_user_id`)

---

### Table: `member_activities`

Unified activity log across all sources. **Duplicate prevention via unique `activity_id`.**

```sql
CREATE TABLE IF NOT EXISTS member_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    metadata TEXT,
    activity_id TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_id) REFERENCES members(id)
)
```

**Columns:**

- `id` (INTEGER): Primary key, auto-increment
- `member_id` (INTEGER): Foreign key to `members.id`
- `source_type` (TEXT): Data source (`'github'`, `'slack'`, etc.)
- `activity_type` (TEXT): Type of activity (`'github_commit'`, `'github_pull_request'`, `'message'`, `'reaction'`, etc.)
- `timestamp` (TIMESTAMP): When the activity occurred
- `metadata` (TEXT): JSON-serialized activity details
- `activity_id` (TEXT): **UNIQUE** identifier for deduplication
  - GitHub commit: `github:commit:{sha}`
  - GitHub PR: `github:pr:{repo}:{number}`
  - GitHub issue: `github:issue:{repo}:{number}`
  - Slack message: `slack:message:{channel_id}:{ts}`
  - Slack reaction: `slack:reaction:{message_ts}:{emoji}:{user_id}`
- `created_at` (TIMESTAMP): When it was recorded

**Important Notes:**

- Use ISO 8601 format for timestamps: `YYYY-MM-DDTHH:MM:SSZ`
- **UNIQUE constraint on `activity_id` prevents duplicate activities**
- Uses `INSERT OR IGNORE` to silently skip duplicates

---

### Table: `data_collections`

Tracks data collection jobs.

```sql
CREATE TABLE IF NOT EXISTS data_collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    status TEXT DEFAULT 'pending',
    records_collected INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
)
```

**Columns:**

- `id` (INTEGER): Primary key, auto-increment
- `source_type` (TEXT): Data source type
- `start_date` (TIMESTAMP): Collection period start
- `end_date` (TIMESTAMP): Collection period end
- `status` (TEXT): `'pending'`, `'running'`, `'completed'`, `'failed'`
- `records_collected` (INTEGER): Number of records collected
- `error_message` (TEXT): Error details if failed
- `created_at` (TIMESTAMP): Job creation time
- `completed_at` (TIMESTAMP): Job completion time

---

## GitHub Database (`github.db`)

### Table: `github_members`

GitHub users (members and collaborators).

```sql
CREATE TABLE IF NOT EXISTS github_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT NOT NULL UNIQUE,
    name TEXT,
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Columns:**

- `id` (INTEGER): Primary key, auto-increment
- `login` (TEXT): GitHub username, **UNIQUE**, **NOT NULL**
- `name` (TEXT): Display name
- `email` (TEXT): Email address
- `created_at` (TIMESTAMP): Registration timestamp

**Important Notes:**

- `login` is the GitHub username (case-sensitive!)
- Must match the exact case used in GitHub API responses

---

### Table: `github_commits`

GitHub commit data.

```sql
CREATE TABLE IF NOT EXISTS github_commits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sha TEXT NOT NULL UNIQUE,
    message TEXT,
    url TEXT,
    committed_at TIMESTAMP,
    author_login TEXT,
    repository_name TEXT,
    additions INTEGER DEFAULT 0,
    deletions INTEGER DEFAULT 0,
    changed_files INTEGER DEFAULT 0,
    branch TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (author_login) REFERENCES github_members(login)
)
```

**Columns:**

- `id` (INTEGER): Primary key, auto-increment
- `sha` (TEXT): Commit SHA hash, **UNIQUE**, **NOT NULL**
- `message` (TEXT): Commit message
- `url` (TEXT): GitHub commit URL
- `committed_at` (TIMESTAMP): When the commit was made (ISO 8601 with 'Z')
- `author_login` (TEXT): GitHub username of committer
- `repository_name` (TEXT): Repository name (e.g., `tokamak-network/repo-name`)
- `additions` (INTEGER): Lines added
- `deletions` (INTEGER): Lines deleted
- `changed_files` (INTEGER): Number of files changed
- `branch` (TEXT): Branch name
- `created_at` (TIMESTAMP): When record was created

**Important Notes:**

- `committed_at` format: `YYYY-MM-DDTHH:MM:SSZ` (e.g., `2025-11-04T12:44:04Z`)
- `author_login` is **case-sensitive** - must match GitHub API response exactly
- Foreign key references `github_members(login)`

**Query Examples:**

```sql
-- Get commits by author (case-sensitive!)
SELECT * FROM github_commits WHERE author_login = 'SonYoungsung';

-- Get commits in date range (ISO 8601 comparison)
SELECT * FROM github_commits
WHERE author_login = 'SonYoungsung'
AND committed_at >= '2025-10-30T15:00:00'
AND committed_at <= '2025-11-06T14:59:59';
```

---

### Table: `github_commit_files`

File changes within commits.

```sql
CREATE TABLE IF NOT EXISTS github_commit_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    commit_sha TEXT NOT NULL,
    filename TEXT,
    additions INTEGER DEFAULT 0,
    deletions INTEGER DEFAULT 0,
    changes INTEGER DEFAULT 0,
    status TEXT,
    patch TEXT,
    added_lines TEXT,
    deleted_lines TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (commit_sha) REFERENCES github_commits(sha),
    UNIQUE(commit_sha, filename)
)
```

**Columns:**

- `id` (INTEGER): Primary key, auto-increment
- `commit_sha` (TEXT): Foreign key to `github_commits.sha`
- `filename` (TEXT): File path
- `additions` (INTEGER): Lines added in this file
- `deletions` (INTEGER): Lines deleted in this file
- `changes` (INTEGER): Total changes (additions + deletions)
- `status` (TEXT): File status (`'added'`, `'modified'`, `'deleted'`, `'renamed'`)
- `patch` (TEXT): Git diff patch string
- `added_lines` (TEXT): JSON array of added line strings
- `deleted_lines` (TEXT): JSON array of deleted line strings
- `created_at` (TIMESTAMP): Record creation timestamp

**Important Notes:**

- Composite unique constraint on (`commit_sha`, `filename`)
- Use `INSERT OR IGNORE` to prevent duplicates
- `added_lines` and `deleted_lines` store JSON arrays

---

### Table: `github_pull_requests`

GitHub pull request data.

```sql
CREATE TABLE IF NOT EXISTS github_pull_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number INTEGER NOT NULL,
    title TEXT,
    url TEXT,
    state TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    merged_at TIMESTAMP,
    closed_at TIMESTAMP,
    author_login TEXT,
    repository_name TEXT,
    additions INTEGER DEFAULT 0,
    deletions INTEGER DEFAULT 0,
    changed_files INTEGER DEFAULT 0,
    UNIQUE(repository_name, number),
    FOREIGN KEY (author_login) REFERENCES github_members(login)
)
```

**Columns:**

- `id` (INTEGER): Primary key, auto-increment
- `number` (INTEGER): PR number (unique per repository)
- `title` (TEXT): PR title
- `url` (TEXT): GitHub PR URL
- `state` (TEXT): PR state (`'open'`, `'closed'`)
- `created_at` (TIMESTAMP): PR creation time
- `updated_at` (TIMESTAMP): Last update time
- `merged_at` (TIMESTAMP): Merge time (NULL if not merged)
- `closed_at` (TIMESTAMP): Close time (NULL if still open)
- `author_login` (TEXT): GitHub username of PR author
- `repository_name` (TEXT): Repository name
- `additions` (INTEGER): Lines added
- `deletions` (INTEGER): Lines deleted
- `changed_files` (INTEGER): Files changed

**Important Notes:**

- Composite unique constraint on (`repository_name`, `number`)
- `author_login` is case-sensitive
- All timestamps in ISO 8601 format

---

### Table: `github_issues`

GitHub issue data.

```sql
CREATE TABLE IF NOT EXISTS github_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number INTEGER NOT NULL,
    title TEXT,
    url TEXT,
    state TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    closed_at TIMESTAMP,
    author_login TEXT,
    repository_name TEXT,
    UNIQUE(repository_name, number),
    FOREIGN KEY (author_login) REFERENCES github_members(login)
)
```

**Columns:**

- `id` (INTEGER): Primary key, auto-increment
- `number` (INTEGER): Issue number (unique per repository)
- `title` (TEXT): Issue title
- `url` (TEXT): GitHub issue URL
- `state` (TEXT): Issue state (`'open'`, `'closed'`)
- `created_at` (TIMESTAMP): Issue creation time
- `updated_at` (TIMESTAMP): Last update time
- `closed_at` (TIMESTAMP): Close time (NULL if still open)
- `author_login` (TEXT): GitHub username of issue author
- `repository_name` (TEXT): Repository name

**Important Notes:**

- Composite unique constraint on (`repository_name`, `number`)
- `author_login` is case-sensitive
- All timestamps in ISO 8601 format

---

## Common Patterns & Best Practices

### Timestamp Format

**Always use ISO 8601 format:**

- Format: `YYYY-MM-DDTHH:MM:SSZ`
- Example: `2025-11-04T12:44:04Z`
- Python: `datetime.isoformat()` or `strftime('%Y-%m-%dT%H:%M:%SZ')`

### Case Sensitivity

**CRITICAL**: SQLite is case-sensitive by default for text comparisons.

- GitHub usernames: Use exact case from GitHub API (e.g., `SonYoungsung` not `sonyoungsung`)
- When comparing strings in WHERE clauses, ensure case matches
- For case-insensitive search, use: `WHERE LOWER(column) = LOWER(:value)`

### Preventing Duplicates

Use `INSERT OR IGNORE` with unique constraints:

```sql
INSERT OR IGNORE INTO github_commits (sha, message, ...)
VALUES (:sha, :message, ...);
```

### Foreign Key Integrity

- Enable foreign keys: `PRAGMA foreign_keys = ON;`
- Ensure referenced records exist before inserting
- Use transactions for multi-table inserts

### Query Performance

- Index frequently queried columns:

  ```sql
  CREATE INDEX IF NOT EXISTS idx_commits_author
  ON github_commits(author_login);

  CREATE INDEX IF NOT EXISTS idx_commits_date
  ON github_commits(committed_at);
  ```

---

## Schema Version History

### Version 1.1 (2025-11-10)

- Added Slack database schema
- Tables: slack_channels, slack_messages, slack_reactions, slack_links, slack_files, slack_users
- Link extraction and classification system
- Cross-reference support for GitHub, Notion, Google Drive

### Version 1.0 (2025-11-10)

- Initial schema definition
- Main database: members, member_identifiers, member_activities, data_collections
- GitHub database: github_members, github_commits, github_commit_files, github_pull_requests, github_issues
- Added `added_lines` and `deleted_lines` to `github_commit_files`
- Added unique constraints for duplicate prevention

---

## Slack Database (`slack.db`)

### Table: `slack_channels`

Stores Slack channel information.

```sql
CREATE TABLE IF NOT EXISTS slack_channels (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    is_private BOOLEAN DEFAULT 0,
    is_archived BOOLEAN DEFAULT 0,
    member_count INTEGER DEFAULT 0,
    topic TEXT,
    purpose TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Columns:**

- `id` (TEXT): Slack channel ID (e.g., `C01ABC123`), **PRIMARY KEY**
- `name` (TEXT): Channel name without # (e.g., `dev`, `general`)
- `is_private` (BOOLEAN): `1` if private channel, `0` if public
- `is_archived` (BOOLEAN): `1` if archived
- `member_count` (INTEGER): Number of members
- `topic` (TEXT): Channel topic
- `purpose` (TEXT): Channel purpose
- `created_at` (TIMESTAMP): Channel creation time
- `updated_at` (TIMESTAMP): Last update time

---

### Table: `slack_messages`

Stores Slack messages.

```sql
CREATE TABLE IF NOT EXISTS slack_messages (
    ts TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    user_id TEXT,
    text TEXT,
    thread_ts TEXT,
    reply_count INTEGER DEFAULT 0,
    reply_users_count INTEGER DEFAULT 0,
    is_thread_parent BOOLEAN DEFAULT 0,
    has_links BOOLEAN DEFAULT 0,
    has_files BOOLEAN DEFAULT 0,
    posted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (channel_id) REFERENCES slack_channels(id),
    FOREIGN KEY (thread_ts) REFERENCES slack_messages(ts)
)
```

**Columns:**

- `ts` (TEXT): Message timestamp (Slack's unique ID), **PRIMARY KEY**
- `channel_id` (TEXT): Foreign key to `slack_channels.id`
- `user_id` (TEXT): Slack user ID (e.g., `U01ABC123`)
- `text` (TEXT): Message content
- `thread_ts` (TEXT): Parent message ts if this is a reply
- `reply_count` (INTEGER): Number of replies (if thread parent)
- `reply_users_count` (INTEGER): Number of unique repliers
- `is_thread_parent` (BOOLEAN): `1` if this message has replies
- `has_links` (BOOLEAN): `1` if message contains URLs
- `has_files` (BOOLEAN): `1` if message has file attachments
- `posted_at` (TIMESTAMP): When message was posted (converted from ts)
- `created_at` (TIMESTAMP): When record was created

**Important Notes:**

- `ts` is Slack's unique message identifier (format: `1234567890.123456`)
- `thread_ts` references the parent message for threaded replies
- Use `posted_at` for date range queries (indexed)

---

### Table: `slack_reactions`

Stores emoji reactions to messages.

```sql
CREATE TABLE IF NOT EXISTS slack_reactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_ts TEXT NOT NULL,
    emoji TEXT NOT NULL,
    user_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_ts) REFERENCES slack_messages(ts),
    UNIQUE(message_ts, emoji, user_id)
)
```

**Columns:**

- `id` (INTEGER): Primary key, auto-increment
- `message_ts` (TEXT): Foreign key to `slack_messages.ts`
- `emoji` (TEXT): Emoji name (e.g., `thumbsup`, `rocket`)
- `user_id` (TEXT): User who added the reaction
- `created_at` (TIMESTAMP): When reaction was added

**Important Notes:**

- Composite unique constraint prevents duplicate reactions
- Each user can only add one of each emoji per message

---

### Table: `slack_links`

Stores extracted links from messages with classification.

```sql
CREATE TABLE IF NOT EXISTS slack_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_ts TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    url TEXT NOT NULL,
    link_type TEXT,
    resource_id TEXT,
    repository_name TEXT,
    shared_by_user_id TEXT,
    shared_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_ts) REFERENCES slack_messages(ts),
    FOREIGN KEY (channel_id) REFERENCES slack_channels(id)
)
```

**Columns:**

- `id` (INTEGER): Primary key, auto-increment
- `message_ts` (TEXT): Foreign key to `slack_messages.ts`
- `channel_id` (TEXT): Foreign key to `slack_channels.id`
- `url` (TEXT): Full URL
- `link_type` (TEXT): Classified link type
- `resource_id` (TEXT): Extracted resource identifier
- `repository_name` (TEXT): For GitHub links (e.g., `tokamak-network/repo`)
- `shared_by_user_id` (TEXT): User who shared the link
- `shared_at` (TIMESTAMP): When link was shared
- `created_at` (TIMESTAMP): Record creation time

**Link Types:**

```
GitHub:
- github_pr: Pull request
- github_issue: Issue
- github_commit: Commit
- github_repo: Repository
- github_discussion: Discussion

Google Drive:
- gdrive_doc: Google Docs
- gdrive_sheet: Google Sheets
- gdrive_slide: Google Slides
- gdrive_folder: Folder

Notion:
- notion_page: Notion page
- notion_database: Notion database

Other:
- external: Other external links
```

**Resource ID Examples:**

```sql
-- GitHub PR
url: https://github.com/org/repo/pull/123
link_type: github_pr
resource_id: 123
repository_name: org/repo

-- Google Docs
url: https://docs.google.com/document/d/abc123/edit
link_type: gdrive_doc
resource_id: abc123

-- Notion
url: https://www.notion.so/page-title-abc123
link_type: notion_page
resource_id: abc123
```

---

### Table: `slack_files`

Stores file metadata shared in Slack.

```sql
CREATE TABLE IF NOT EXISTS slack_files (
    id TEXT PRIMARY KEY,
    message_ts TEXT,
    channel_id TEXT NOT NULL,
    name TEXT,
    title TEXT,
    filetype TEXT,
    size INTEGER,
    url_private TEXT,
    uploaded_by_user_id TEXT,
    uploaded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_ts) REFERENCES slack_messages(ts),
    FOREIGN KEY (channel_id) REFERENCES slack_channels(id)
)
```

**Columns:**

- `id` (TEXT): Slack file ID, **PRIMARY KEY**
- `message_ts` (TEXT): Foreign key to message (if attached)
- `channel_id` (TEXT): Channel where file was shared
- `name` (TEXT): File name
- `title` (TEXT): File title/description
- `filetype` (TEXT): File extension (e.g., `pdf`, `png`)
- `size` (INTEGER): File size in bytes
- `url_private` (TEXT): Private download URL
- `uploaded_by_user_id` (TEXT): User who uploaded
- `uploaded_at` (TIMESTAMP): Upload timestamp
- `created_at` (TIMESTAMP): Record creation time

---

### Table: `slack_users`

Stores Slack user information for reference.

```sql
CREATE TABLE IF NOT EXISTS slack_users (
    id TEXT PRIMARY KEY,
    name TEXT,
    real_name TEXT,
    email TEXT,
    is_bot BOOLEAN DEFAULT 0,
    is_deleted BOOLEAN DEFAULT 0,
    timezone TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Columns:**

- `id` (TEXT): Slack user ID (e.g., `U01ABC123`), **PRIMARY KEY**
- `name` (TEXT): Username/display name
- `real_name` (TEXT): Full name
- `email` (TEXT): Email address (for member matching)
- `is_bot` (BOOLEAN): `1` if bot account
- `is_deleted` (BOOLEAN): `1` if deactivated
- `timezone` (TEXT): User timezone
- `created_at` (TIMESTAMP): Record creation
- `updated_at` (TIMESTAMP): Last update

**Important Notes:**

- Use `email` to match with `members.csv`
- Filter out bots (`is_bot = 0`) for member analysis
- `is_deleted = 1` for deactivated accounts

---

## Common Patterns & Best Practices (Slack)

### Timestamp Handling

Slack uses unique timestamp format:

```python
# Slack ts format: "1234567890.123456"
# Convert to datetime:
from datetime import datetime

ts = "1234567890.123456"
dt = datetime.fromtimestamp(float(ts))
```

### Link Extraction

Use regex patterns to extract and classify links:

```python
import re

LINK_PATTERNS = {
    'github_pr': r'https://github\.com/([^/]+/[^/]+)/pull/(\d+)',
    'github_issue': r'https://github\.com/([^/]+/[^/]+)/issues/(\d+)',
    'github_commit': r'https://github\.com/([^/]+/[^/]+)/commit/([a-f0-9]{7,40})',
    'gdrive_doc': r'https://docs\.google\.com/document/d/([^/]+)',
    'notion_page': r'https://(?:www\.)?notion\.so/(?:[^/]+/)?([a-f0-9]{32})',
}
```

### Cross-Reference Queries

**Find GitHub PRs discussed in Slack:**

```sql
SELECT
    s.text as slack_message,
    s.posted_at,
    sl.url,
    g.title as pr_title,
    g.state as pr_state,
    g.merged_at
FROM slack_links sl
JOIN slack_messages s ON sl.message_ts = s.ts
JOIN github_pull_requests g
    ON sl.resource_id = g.number
    AND sl.repository_name = g.repository_name
WHERE sl.link_type = 'github_pr'
ORDER BY s.posted_at DESC;
```

**Member activity across Slack and GitHub:**

```sql
SELECT
    m.name,
    COUNT(DISTINCT sm.ts) as slack_messages,
    COUNT(DISTINCT gc.sha) as github_commits
FROM members m
JOIN member_identifiers mi ON m.id = mi.member_id
LEFT JOIN slack_messages sm
    ON mi.source_user_id = sm.user_id
    AND mi.source_type = 'slack'
LEFT JOIN github_commits gc
    ON mi.source_user_id = gc.author_login
    AND mi.source_type = 'github'
WHERE sm.posted_at >= '2025-10-30'
GROUP BY m.name;
```

---

## Future Schema Changes

When modifying schemas:

1. **Update this document first**
2. Create migration scripts in `migrations/` directory
3. Update affected query code
4. Test with existing data
5. Update version history

---

## Quick Reference

### Main DB Queries

```sql
-- Find member by name or email
SELECT * FROM members WHERE name = :name OR email = :name;

-- Get member's GitHub ID
SELECT source_user_id FROM member_identifiers
WHERE member_id = :member_id AND source_type = 'github';

-- Get member's activities
SELECT * FROM member_activities
WHERE member_id = :member_id
AND occurred_at >= :start_date
AND occurred_at <= :end_date;
```

### GitHub DB Queries

```sql
-- Get commits by author in date range
SELECT * FROM github_commits
WHERE author_login = :github_login
AND committed_at >= :start_date
AND committed_at <= :end_date
ORDER BY committed_at DESC;

-- Get PR statistics
SELECT
    COUNT(*) as total_prs,
    SUM(CASE WHEN merged_at IS NOT NULL THEN 1 ELSE 0 END) as merged_prs,
    SUM(additions) as total_additions,
    SUM(deletions) as total_deletions
FROM github_pull_requests
WHERE author_login = :github_login
AND created_at >= :start_date;

-- Get file changes for commits
SELECT cf.* FROM github_commit_files cf
JOIN github_commits c ON cf.commit_sha = c.sha
WHERE c.author_login = :github_login
AND c.committed_at >= :start_date;
```

---

## Google Drive Database (`google_drive.db`)

Stores Google Drive activity data collected via Admin SDK Reports API.

### Table: `drive_activities`

Stores all Drive activity events.

```sql
CREATE TABLE IF NOT EXISTS drive_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL,
    user_email TEXT NOT NULL,
    action TEXT NOT NULL,
    event_name TEXT NOT NULL,
    doc_title TEXT,
    doc_type TEXT,
    doc_id TEXT,
    raw_event TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Columns:**

- `id` (INTEGER): Primary key, auto-increment
- `timestamp` (TIMESTAMP): Activity timestamp (UTC)
- `user_email` (TEXT): User's Google Workspace email address
- `action` (TEXT): Activity type in Korean (e.g., '생성', '편집', '공유')
- `event_name` (TEXT): Raw event name from Google API (e.g., 'create', 'edit', 'share')
- `doc_title` (TEXT): Document title
- `doc_type` (TEXT): Document type in Korean (e.g., '문서', '스프레드시트', '폴더')
- `doc_id` (TEXT): Google Drive file/folder ID
- `raw_event` (TEXT): Full event JSON for debugging
- `created_at` (TIMESTAMP): Record creation timestamp

**Important Notes:**

- **`user_email` is lowercase** for consistency
- Map `user_email` to member names via `member_identifiers` table
- `timestamp` is in UTC; convert to KST for reports
- `doc_id` can be used to construct Drive URLs: `https://drive.google.com/file/d/{doc_id}`

### Table: `drive_documents`

Tracks unique documents and their metadata.

```sql
CREATE TABLE IF NOT EXISTS drive_documents (
    doc_id TEXT PRIMARY KEY,
    title TEXT,
    doc_type TEXT,
    first_seen TIMESTAMP,
    last_activity TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Columns:**

- `doc_id` (TEXT): Google Drive file/folder ID (primary key)
- `title` (TEXT): Document title
- `doc_type` (TEXT): Document type in Korean
- `first_seen` (TIMESTAMP): When this document was first observed
- `last_activity` (TIMESTAMP): Most recent activity timestamp
- `created_at` (TIMESTAMP): Record creation timestamp

---

### Table: `drive_folders`

Tracks folder structure and project associations.

```sql
CREATE TABLE IF NOT EXISTS drive_folders (
    folder_id TEXT PRIMARY KEY,
    folder_name TEXT NOT NULL,
    parent_folder_id TEXT,
    project_key TEXT,
    is_project_root BOOLEAN DEFAULT 0,
    created_by TEXT,
    first_seen TIMESTAMP,
    last_activity TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_folder_id) REFERENCES drive_folders(folder_id)
)
```

**Columns:**

- `folder_id` (TEXT): Google Drive folder ID (primary key)
- `folder_name` (TEXT): Folder name
- `parent_folder_id` (TEXT): Parent folder ID for hierarchical structure
- `project_key` (TEXT): Associated project key (e.g., 'project-ooo', 'project-eco')
- `is_project_root` (BOOLEAN): `1` if this is a project's root folder
- `created_by` (TEXT): User email who created the folder
- `first_seen` (TIMESTAMP): When folder was first observed
- `last_activity` (TIMESTAMP): Most recent activity in this folder
- `created_at` (TIMESTAMP): Record creation timestamp

**Important Notes:**

- `project_key` links to `config.yaml` projects section
- `parent_folder_id` creates folder hierarchy (self-referencing foreign key)
- Use for filtering activities by project

---

### Table: `drive_folder_members`

Tracks folder access permissions and members.

```sql
CREATE TABLE IF NOT EXISTS drive_folder_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id TEXT NOT NULL,
    user_email TEXT NOT NULL,
    access_level TEXT,
    added_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (folder_id) REFERENCES drive_folders(folder_id),
    UNIQUE(folder_id, user_email)
)
```

**Columns:**

- `id` (INTEGER): Primary key, auto-increment
- `folder_id` (TEXT): Foreign key to `drive_folders`
- `user_email` (TEXT): User's email address
- `access_level` (TEXT): Permission level (e.g., 'owner', 'editor', 'viewer')
- `added_at` (TIMESTAMP): When user was granted access
- `created_at` (TIMESTAMP): Record creation timestamp

**Access Levels:**

- `owner`: Full control, can delete folder
- `editor`: Can add/edit/delete files
- `commenter`: Can comment but not edit
- `viewer`: Read-only access

### Activity Types

| `event_name`         | `action` (Korean) | Description                    |
| -------------------- | ----------------- | ------------------------------ |
| `create`             | 생성              | New file/folder created        |
| `edit`               | 편집              | Document edited                |
| `upload`             | 업로드            | File uploaded                  |
| `download`           | 다운로드          | File downloaded                |
| `delete`             | 삭제              | File deleted permanently       |
| `trash`              | 휴지통 이동       | File moved to trash            |
| `untrash`            | 복원              | File restored from trash       |
| `rename`             | 이름 변경         | File renamed                   |
| `move`               | 이동              | File moved to different folder |
| `copy`               | 복사              | File copied                    |
| `share`              | 공유              | File shared with user(s)       |
| `unshare`            | 공유 취소         | Sharing permissions removed    |
| `change_user_access` | 접근 권한 변경    | User permissions modified      |
| `add_to_folder`      | 폴더에 추가       | File added to folder           |
| `remove_from_folder` | 폴더에서 제거     | File removed from folder       |

### Document Types

| `doc_type` (API)     | Type (Korean) | Description                  |
| -------------------- | ------------- | ---------------------------- |
| `document`           | 문서          | Google Docs                  |
| `spreadsheet`        | 스프레드시트  | Google Sheets                |
| `presentation`       | 프레젠테이션  | Google Slides                |
| `folder`             | 폴더          | Drive folder                 |
| `file`               | 파일          | Other file types             |
| `drawing`            | 그림          | Google Drawings              |
| `form`               | 설문지        | Google Forms                 |
| `site`               | 사이트        | Google Sites                 |
| **Video Formats**    |               |                              |
| `mp4`                | 동영상(mp4)   | MP4 video files              |
| `mpeg`               | 동영상(mpeg)  | MPEG video files             |
| `mov`                | 동영상(mov)   | MOV video files              |
| `avi`                | 동영상(avi)   | AVI video files              |
| `video`              | 동영상        | Other video formats          |
| **Image Formats**    |               |                              |
| `png`                | 이미지(png)   | PNG images                   |
| `jpeg`/`jpg`         | 이미지(jpeg)  | JPEG images                  |
| **Document Formats** |               |                              |
| `pdf`                | PDF           | PDF documents                |
| `txt`                | 텍스트        | Text files                   |
| `msword`             | MS Word       | Microsoft Word documents     |
| `msexcel`            | MS Excel      | Microsoft Excel spreadsheets |
| `mspowerpoint`       | MS PowerPoint | Microsoft PowerPoint slides  |
| `html`               | HTML          | HTML files                   |

**Special Use Cases:**

- **Meeting Videos**: MP4/MPEG files uploaded after meetings
- **Meeting Transcripts**: Google Docs with "Gemini가 작성한 회의록" in title
- **Screenshots**: PNG/JPEG images shared for collaboration

### Common Queries

```sql
-- Get user's Drive activities for a period
SELECT
    timestamp,
    action,
    doc_title,
    doc_type
FROM drive_activities
WHERE LOWER(user_email) = LOWER(:email)
  AND date(timestamp) >= :start_date
  AND date(timestamp) <= :end_date
ORDER BY timestamp DESC;

-- Get activity statistics by user
SELECT
    user_email,
    COUNT(*) as total_activities,
    COUNT(DISTINCT doc_id) as unique_documents,
    COUNT(CASE WHEN action = '공유' THEN 1 END) as share_count,
    COUNT(CASE WHEN action = '편집' THEN 1 END) as edit_count
FROM drive_activities
WHERE date(timestamp) >= :start_date
GROUP BY user_email
ORDER BY total_activities DESC;

-- Get most active documents
SELECT
    d.doc_id,
    d.title,
    d.doc_type,
    COUNT(a.id) as activity_count,
    MAX(a.timestamp) as last_modified
FROM drive_documents d
JOIN drive_activities a ON d.doc_id = a.doc_id
WHERE date(a.timestamp) >= :start_date
GROUP BY d.doc_id
ORDER BY activity_count DESC
LIMIT 20;

-- Cross-reference with member index
SELECT
    m.name,
    COUNT(ma.id) as drive_activities
FROM members m
JOIN member_identifiers mi ON m.id = mi.member_id
JOIN member_activities ma ON m.id = ma.member_id
WHERE mi.source_type = 'google_drive'
  AND ma.source_type = 'google_drive'
  AND date(ma.timestamp) >= :start_date
GROUP BY m.name
ORDER BY drive_activities DESC;

-- Get meeting video activities
SELECT
    user_email,
    doc_title,
    action,
    timestamp
FROM drive_activities
WHERE doc_type IN ('mp4', 'mpeg', 'mov', 'avi')
  AND date(timestamp) >= :start_date
ORDER BY timestamp DESC;

-- Get meeting transcripts (Gemini-generated)
SELECT
    user_email,
    doc_title,
    action,
    timestamp
FROM drive_activities
WHERE doc_title LIKE '%Gemini가 작성한 회의록%'
  OR doc_title LIKE '%Meeting%'
ORDER BY timestamp DESC;

-- Meeting workflow analysis (video upload → transcript creation)
SELECT
    date(da_video.timestamp) as meeting_date,
    da_video.doc_title as video_title,
    da_video.user_email as uploader,
    da_transcript.doc_title as transcript_title,
    da_transcript.user_email as transcript_editor,
    da_transcript.timestamp as transcript_time
FROM drive_activities da_video
LEFT JOIN drive_activities da_transcript
    ON date(da_video.timestamp) = date(da_transcript.timestamp)
    AND da_transcript.doc_title LIKE '%Gemini가 작성한 회의록%'
WHERE da_video.doc_type IN ('mp4', 'mpeg')
  AND da_video.action = '업로드'
  AND date(da_video.timestamp) >= :start_date
ORDER BY da_video.timestamp DESC;

-- Get project folders and their activity
SELECT
    f.folder_name,
    f.project_key,
    COUNT(a.id) as total_activities,
    COUNT(DISTINCT a.user_email) as unique_users,
    MAX(a.timestamp) as last_activity
FROM drive_folders f
LEFT JOIN drive_activities a ON f.folder_name = a.doc_title
WHERE f.project_key = :project_key
  AND date(a.timestamp) >= :start_date
GROUP BY f.folder_id
ORDER BY total_activities DESC;

-- Get folder hierarchy for a project
WITH RECURSIVE folder_tree AS (
    -- Base case: root folders
    SELECT
        folder_id,
        folder_name,
        parent_folder_id,
        project_key,
        0 as depth,
        folder_name as path
    FROM drive_folders
    WHERE parent_folder_id IS NULL
      AND project_key = :project_key

    UNION ALL

    -- Recursive case: child folders
    SELECT
        f.folder_id,
        f.folder_name,
        f.parent_folder_id,
        f.project_key,
        ft.depth + 1,
        ft.path || '/' || f.folder_name
    FROM drive_folders f
    INNER JOIN folder_tree ft ON f.parent_folder_id = ft.folder_id
)
SELECT * FROM folder_tree ORDER BY path;

-- Get folder members and their access levels
SELECT
    f.folder_name,
    fm.user_email,
    fm.access_level,
    m.name as member_name
FROM drive_folders f
JOIN drive_folder_members fm ON f.folder_id = fm.folder_id
LEFT JOIN member_identifiers mi ON fm.user_email = mi.source_user_id
LEFT JOIN members m ON mi.member_id = m.id
WHERE f.project_key = :project_key
ORDER BY f.folder_name, fm.access_level;
```

---

## Troubleshooting

### Problem: Query returns 0 results despite data existing

**Check:**

1. Case sensitivity of identifiers (`SonYoungsung` vs `sonyoungsung`)
2. Timestamp format and comparison
3. Foreign key relationships
4. Null values in WHERE clauses

**Solution:**

```sql
-- Use LOWER() for case-insensitive comparison
WHERE LOWER(author_login) = LOWER(:value)

-- Debug timestamp comparison
SELECT committed_at, :start_date, committed_at >= :start_date
FROM github_commits LIMIT 1;
```

### Problem: Duplicate constraint violations

**Solution:**
Use `INSERT OR IGNORE` instead of `INSERT`:

```sql
INSERT OR IGNORE INTO table_name (...) VALUES (...);
```

---

**Remember**: Always consult this document before writing database queries!
