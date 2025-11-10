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

Unified activity log across all sources.

```sql
CREATE TABLE IF NOT EXISTS member_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    activity_id TEXT,
    activity_data TEXT,
    occurred_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_id) REFERENCES members(id),
    UNIQUE(source_type, activity_id)
)
```

**Columns:**
- `id` (INTEGER): Primary key, auto-increment
- `member_id` (INTEGER): Foreign key to `members.id`
- `source_type` (TEXT): Data source (`'github'`, `'slack'`, etc.)
- `activity_type` (TEXT): Type of activity (`'commit'`, `'pr'`, `'message'`, etc.)
- `activity_id` (TEXT): Unique ID of the activity in the source
- `activity_data` (TEXT): JSON-serialized activity details
- `occurred_at` (TIMESTAMP): When the activity occurred
- `created_at` (TIMESTAMP): When it was recorded

**Important Notes:**
- Use ISO 8601 format for timestamps: `YYYY-MM-DDTHH:MM:SSZ`
- Composite unique constraint prevents duplicate activities

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

### Version 1.0 (2025-11-10)
- Initial schema definition
- Main database: members, member_identifiers, member_activities, data_collections
- GitHub database: github_members, github_commits, github_commit_files, github_pull_requests, github_issues
- Added `added_lines` and `deleted_lines` to `github_commit_files`
- Added unique constraints for duplicate prevention

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

