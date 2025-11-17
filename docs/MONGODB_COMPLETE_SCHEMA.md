# Complete MongoDB Schema Design for All Plugins

**Version:** 1.0  
**Last Updated:** 2025-11-17  
**Status:** Design Document

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Design Principles](#design-principles)
3. [Main Collections](#main-collections)
4. [Plugin Collections](#plugin-collections)
   - [GitHub Plugin](#1-github-plugin-✅-implemented)
   - [Slack Plugin](#2-slack-plugin)
   - [Notion Plugin](#3-notion-plugin)
   - [Google Drive Plugin](#4-google-drive-plugin)
5. [Cross-Plugin Integration](#cross-plugin-integration)
6. [Indexing Strategy](#indexing-strategy)
7. [Migration Considerations](#migration-considerations)

---

## Overview

This document outlines the complete MongoDB schema design for migrating all data source plugins from SQL (PostgreSQL/SQLite) to MongoDB.

### Current Status
- ✅ **GitHub Plugin**: MongoDB implementation complete and tested
- 🔄 **Slack Plugin**: Design complete, implementation pending
- 🔄 **Notion Plugin**: Design complete, implementation pending
- 🔄 **Google Drive Plugin**: Design complete, implementation pending

---

## Design Principles

### 1. Embedding vs Referencing

| Strategy | Use When | Example |
|----------|----------|---------|
| **Embedding** | 1:Few, Frequently accessed together | Commit files in commit document |
| **Referencing** | 1:Many, Independently accessed | User reference in activities |

### 2. Denormalization

**Denormalize frequently accessed fields** to avoid JOINs:
- Member names in activity documents
- Repository names in commit documents
- Channel names in message documents

### 3. Document Size Limits

MongoDB document size limit: **16MB**
- Be cautious with embedded arrays
- Use referencing for potentially large arrays (e.g., many reactions)

---

## Main Collections

### `members` Collection

**Purpose:** Unified member index across all data sources

```json
{
  "_id": ObjectId("..."),
  "name": "John Doe",
  "email": "john.doe@company.com",
  "role": "developer",
  "team": "backend",
  
  // Denormalized identifiers for quick access
  "github_username": "johndoe",
  "slack_id": "U1234567890",
  "notion_id": "abc-123-def-456",
  "google_email": "john.doe@company.com",
  
  // Embedded identifiers (replaces member_identifiers table)
  "identifiers": [
    {
      "source_type": "github",
      "source_user_id": "johndoe",
      "source_user_name": "John Doe",
      "metadata": {}
    },
    {
      "source_type": "slack",
      "source_user_id": "U1234567890",
      "source_user_name": "John Doe",
      "metadata": { "timezone": "Asia/Seoul" }
    }
  ],
  
  // Timestamps
  "created_at": ISODate("2025-01-01T00:00:00Z"),
  "updated_at": ISODate("2025-11-17T00:00:00Z")
}
```

**Indexes:**
```javascript
db.members.createIndex({ "email": 1 }, { unique: true })
db.members.createIndex({ "github_username": 1 }, { sparse: true })
db.members.createIndex({ "slack_id": 1 }, { sparse: true })
db.members.createIndex({ "identifiers.source_user_id": 1, "identifiers.source_type": 1 })
```

---

### `member_activities` Collection

**Purpose:** Unified activity log from all data sources

```json
{
  "_id": ObjectId("..."),
  "activity_id": "github_commit_abc123",  // Unique hash for deduplication
  
  // Member reference (denormalized for display)
  "member_id": ObjectId("..."),
  "member_name": "John Doe",
  
  // Activity details
  "source_type": "github",  // github, slack, notion, google_drive
  "activity_type": "commit",  // commit, message, page_edit, file_share, etc.
  "timestamp": ISODate("2025-11-17T10:00:00Z"),
  
  // Flexible metadata (varies by source_type and activity_type)
  "metadata": {
    "repository": "tokamak-network/Tokamak-zk-EVM",
    "sha": "abc123...",
    "message": "Fix bug in verifier",
    "additions": 10,
    "deletions": 5,
    "url": "https://github.com/..."
  },
  
  "created_at": ISODate("2025-11-17T10:05:00Z")
}
```

**Indexes:**
```javascript
db.member_activities.createIndex({ "activity_id": 1 }, { unique: true })
db.member_activities.createIndex({ "member_id": 1, "timestamp": -1 })
db.member_activities.createIndex({ "source_type": 1, "activity_type": 1 })
db.member_activities.createIndex({ "timestamp": -1 })
```

---

## Plugin Collections

## 1. GitHub Plugin ✅ (Implemented)

### `github_commits`

```json
{
  "_id": ObjectId("..."),
  "sha": "abc123def456...",  // Unique
  "message": "Fix bug in verifier",
  "url": "https://github.com/...",
  "committed_at": ISODate("2025-11-17T10:00:00Z"),
  "author_login": "johndoe",
  "repository_name": "Tokamak-zk-EVM",
  "additions": 10,
  "deletions": 5,
  "changed_files": 3,
  "branch": "main",
  
  // Embedded file changes (1:Few, always accessed together)
  "files": [
    {
      "filename": "src/verifier.rs",
      "additions": 5,
      "deletions": 2,
      "changes": 7,
      "status": "modified",
      "patch": "@@ -10,7 +10,10 @@...",
      "added_lines": ["line 1", "line 2"],
      "deleted_lines": ["old line 1"]
    }
  ],
  
  "created_at": ISODate("2025-11-17T10:05:00Z")
}
```

**Indexes:**
```javascript
db.github_commits.createIndex({ "sha": 1 }, { unique: true })
db.github_commits.createIndex({ "author_login": 1 })
db.github_commits.createIndex({ "repository_name": 1 })
db.github_commits.createIndex({ "committed_at": -1 })
db.github_commits.createIndex({ "message": "text" })  // Full-text search
```

### `github_pull_requests`

```json
{
  "_id": ObjectId("..."),
  "number": 137,
  "repository_name": "Tokamak-zk-EVM",
  "title": "Groth16 circom/snarkjs/solidity verifier",
  "state": "MERGED",  // OPEN, MERGED, CLOSED
  "author_login": "mehdi-defiesta",
  "created_at": ISODate("2025-11-10T00:00:00Z"),
  "updated_at": ISODate("2025-11-15T00:00:00Z"),
  "merged_at": ISODate("2025-11-15T12:00:00Z"),
  "closed_at": ISODate("2025-11-15T12:00:00Z"),
  "url": "https://github.com/.../pull/137",
  "body": "Implementation details...",
  "additions": 500,
  "deletions": 100,
  "changed_files": 15,
  "commits_count": 12,
  
  // Embedded reviews (1:Few)
  "reviews": [
    {
      "author_login": "reviewer1",
      "state": "APPROVED",
      "submitted_at": ISODate("2025-11-14T10:00:00Z"),
      "body": "LGTM"
    }
  ],
  
  // Embedded labels
  "labels": ["enhancement", "zk-proof"],
  
  "created_at_db": ISODate("2025-11-17T10:05:00Z")
}
```

**Indexes:**
```javascript
db.github_pull_requests.createIndex({ "repository_name": 1, "number": 1 }, { unique: true })
db.github_pull_requests.createIndex({ "author_login": 1 })
db.github_pull_requests.createIndex({ "state": 1 })
db.github_pull_requests.createIndex({ "created_at": -1 })
db.github_pull_requests.createIndex({ "merged_at": -1 }, { sparse: true })
```

### `github_issues`

```json
{
  "_id": ObjectId("..."),
  "number": 8,
  "repository_name": "trh-platform-ui",
  "title": "Bug: Integration installation failed",
  "state": "OPEN",  // OPEN, CLOSED
  "author_login": "theo-learner",
  "created_at": ISODate("2025-11-12T00:00:00Z"),
  "updated_at": ISODate("2025-11-13T00:00:00Z"),
  "closed_at": null,
  "url": "https://github.com/.../issues/8",
  "body": "Description...",
  
  // Embedded labels
  "labels": ["bug", "ui"],
  
  // Embedded assignees
  "assignees": ["johndoe", "janedoe"],
  
  "comments_count": 3,
  
  "created_at_db": ISODate("2025-11-17T10:05:00Z")
}
```

**Indexes:**
```javascript
db.github_issues.createIndex({ "repository_name": 1, "number": 1 }, { unique: true })
db.github_issues.createIndex({ "author_login": 1 })
db.github_issues.createIndex({ "state": 1 })
db.github_issues.createIndex({ "created_at": -1 })
```

### `github_repositories`

```json
{
  "_id": ObjectId("..."),
  "name": "Tokamak-zk-EVM",
  "full_name": "tokamak-network/Tokamak-zk-EVM",
  "description": "Zero-knowledge EVM implementation",
  "url": "https://github.com/tokamak-network/Tokamak-zk-EVM",
  "is_private": false,
  "is_archived": false,
  "language": "Rust",
  "stars_count": 42,
  "forks_count": 5,
  "open_issues_count": 3,
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "updated_at": ISODate("2025-11-17T00:00:00Z"),
  "pushed_at": ISODate("2025-11-17T00:00:00Z"),
  
  "created_at_db": ISODate("2025-11-17T10:05:00Z")
}
```

**Indexes:**
```javascript
db.github_repositories.createIndex({ "full_name": 1 }, { unique: true })
db.github_repositories.createIndex({ "is_archived": 1 })
db.github_repositories.createIndex({ "language": 1 })
db.github_repositories.createIndex({ "pushed_at": -1 })
```

---

## 2. Slack Plugin

### Design Strategy
- **Embed reactions**: Usually few per message
- **Embed thread structure**: Parent/reply relationship
- **Reference channels and users**: Accessed independently
- **Denormalize user names**: Avoid lookup for display

### `slack_channels`

```json
{
  "_id": ObjectId("..."),
  "slack_id": "C06TY9X8XNQ",  // Slack's channel ID
  "name": "project-ooo",
  "is_private": true,
  "is_archived": false,
  "member_count": 11,
  "topic": "Zero-knowledge proof project",
  "purpose": "Discussion and coordination",
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "updated_at": ISODate("2025-11-17T00:00:00Z")
}
```

**Indexes:**
```javascript
db.slack_channels.createIndex({ "slack_id": 1 }, { unique: true })
db.slack_channels.createIndex({ "name": 1 })
db.slack_channels.createIndex({ "is_archived": 1 })
```

### `slack_users`

```json
{
  "_id": ObjectId("..."),
  "slack_id": "U04E2KL62RZ",  // Slack's user ID
  "name": "kevin",
  "real_name": "Kevin Jeong",
  "email": "kevin@tokamak.network",
  "is_bot": false,
  "is_deleted": false,
  "timezone": "Asia/Seoul",
  "created_at": ISODate("2025-01-01T00:00:00Z"),
  "updated_at": ISODate("2025-11-17T00:00:00Z")
}
```

**Indexes:**
```javascript
db.slack_users.createIndex({ "slack_id": 1 }, { unique: true })
db.slack_users.createIndex({ "email": 1 }, { sparse: true })
db.slack_users.createIndex({ "is_bot": 1 })
```

### `slack_messages`

```json
{
  "_id": ObjectId("..."),
  "ts": "1731753118.188409",  // Slack's message timestamp (unique)
  "channel_id": "C06TY9X8XNQ",
  "channel_name": "project-ooo",  // Denormalized
  "user_id": "U04DNT2QS31",
  "user_name": "Ale",  // Denormalized
  "text": "Great work on the verifier!",
  
  // Thread information
  "thread_ts": "1731753000.123456",  // Parent message ts (null if not in thread)
  "reply_count": 3,
  "reply_users_count": 2,
  "is_thread_parent": false,
  
  // Content flags
  "has_links": true,
  "has_files": false,
  
  // Embedded reactions (1:Few, always displayed with message)
  "reactions": [
    {
      "emoji": "thumbsup",
      "count": 3,
      "users": ["U04E2KL62RZ", "U087WJHRVEW", "U04DNT2QS31"]
    },
    {
      "emoji": "raised_hands",
      "count": 1,
      "users": ["U04E2KL62RZ"]
    }
  ],
  
  // Embedded links (1:Few)
  "links": [
    {
      "url": "https://github.com/tokamak-network/Tokamak-zk-EVM/pull/137",
      "link_type": "github_pr",
      "resource_id": "137",
      "repository_name": "tokamak-network/Tokamak-zk-EVM"
    }
  ],
  
  // Embedded files (1:Few)
  "files": [
    {
      "file_id": "F123456",
      "name": "diagram.png",
      "title": "Architecture Diagram",
      "filetype": "png",
      "size": 102400,
      "url_private": "https://files.slack.com/..."
    }
  ],
  
  "posted_at": ISODate("2025-11-06T13:24:08.188Z"),
  "created_at": ISODate("2025-11-17T10:05:00Z")
}
```

**Indexes:**
```javascript
db.slack_messages.createIndex({ "ts": 1 }, { unique: true })
db.slack_messages.createIndex({ "channel_id": 1, "posted_at": -1 })
db.slack_messages.createIndex({ "user_id": 1, "posted_at": -1 })
db.slack_messages.createIndex({ "thread_ts": 1 }, { sparse: true })
db.slack_messages.createIndex({ "text": "text" })  // Full-text search
db.slack_messages.createIndex({ "posted_at": -1 })
```

**Why Embed Reactions?**
- Usually few reactions per message (typically < 10)
- Always displayed with the message
- Rarely queried independently
- Simplifies message display logic

**Alternative (if many reactions):**
Separate `slack_reactions` collection with reference:
```json
{
  "_id": ObjectId("..."),
  "message_ts": "1731753118.188409",
  "emoji": "thumbsup",
  "user_id": "U04E2KL62RZ",
  "user_name": "Kevin",  // Denormalized
  "created_at": ISODate("2025-11-17T10:05:00Z")
}
```

---

## 3. Notion Plugin

### Design Strategy
- **Embed comments**: Usually few per page
- **Reference users**: Accessed independently
- **Denormalize user names**: For display
- **Embed page properties**: Frequently accessed together

### `notion_users`

```json
{
  "_id": ObjectId("..."),
  "notion_id": "abc-123-def-456",  // Notion's user ID
  "name": "John Doe",
  "email": "john.doe@company.com",
  "type": "person",  // person, bot
  "avatar_url": "https://...",
  "created_at": ISODate("2025-01-01T00:00:00Z")
}
```

**Indexes:**
```javascript
db.notion_users.createIndex({ "notion_id": 1 }, { unique: true })
db.notion_users.createIndex({ "email": 1 }, { sparse: true })
```

### `notion_pages`

```json
{
  "_id": ObjectId("..."),
  "notion_id": "page-uuid-here",  // Notion's page ID
  "title": "ZK-EVM Architecture Design",
  "created_time": ISODate("2025-10-01T00:00:00Z"),
  "last_edited_time": ISODate("2025-11-15T10:00:00Z"),
  
  // User references (denormalized names for display)
  "created_by": "abc-123-def-456",
  "created_by_name": "John Doe",
  "last_edited_by": "xyz-789-abc-012",
  "last_edited_by_name": "Jane Smith",
  
  "archived": false,
  "url": "https://www.notion.so/...",
  
  // Parent information
  "parent_type": "database_id",  // page_id, database_id, workspace
  "parent_id": "database-uuid-here",
  
  // Embedded properties (Notion's flexible schema)
  "properties": {
    "Status": {
      "type": "select",
      "select": { "name": "In Progress" }
    },
    "Priority": {
      "type": "select",
      "select": { "name": "High" }
    },
    "Assignee": {
      "type": "people",
      "people": [
        { "id": "abc-123", "name": "John Doe" }
      ]
    }
  },
  
  // Embedded comments (1:Few, usually < 20)
  "comments": [
    {
      "comment_id": "comment-uuid-1",
      "created_time": ISODate("2025-11-10T10:00:00Z"),
      "last_edited_time": ISODate("2025-11-10T10:00:00Z"),
      "created_by": "abc-123-def-456",
      "created_by_name": "John Doe",
      "rich_text": "Great design! Let's proceed."
    }
  ],
  
  "created_at": ISODate("2025-11-17T10:05:00Z")
}
```

**Indexes:**
```javascript
db.notion_pages.createIndex({ "notion_id": 1 }, { unique: true })
db.notion_pages.createIndex({ "created_by": 1 })
db.notion_pages.createIndex({ "last_edited_time": -1 })
db.notion_pages.createIndex({ "parent_id": 1 })
db.notion_pages.createIndex({ "archived": 1 })
db.notion_pages.createIndex({ "title": "text" })  // Full-text search
```

**Alternative (if many comments):**
Separate `notion_comments` collection:
```json
{
  "_id": ObjectId("..."),
  "notion_id": "comment-uuid-1",
  "page_id": "page-uuid-here",
  "created_time": ISODate("2025-11-10T10:00:00Z"),
  "last_edited_time": ISODate("2025-11-10T10:00:00Z"),
  "created_by": "abc-123-def-456",
  "created_by_name": "John Doe",
  "rich_text": "Great design! Let's proceed.",
  "created_at": ISODate("2025-11-17T10:05:00Z")
}
```

### `notion_databases`

```json
{
  "_id": ObjectId("..."),
  "notion_id": "database-uuid-here",
  "title": "Project Tasks",
  "created_time": ISODate("2025-10-01T00:00:00Z"),
  "last_edited_time": ISODate("2025-11-15T00:00:00Z"),
  "created_by": "abc-123-def-456",
  "created_by_name": "John Doe",
  "last_edited_by": "xyz-789-abc-012",
  "last_edited_by_name": "Jane Smith",
  "archived": false,
  "url": "https://www.notion.so/...",
  
  // Database schema (Notion's flexible schema definition)
  "properties_schema": {
    "Name": { "type": "title" },
    "Status": {
      "type": "select",
      "select": {
        "options": [
          { "name": "Not Started", "color": "gray" },
          { "name": "In Progress", "color": "blue" },
          { "name": "Completed", "color": "green" }
        ]
      }
    },
    "Priority": {
      "type": "select",
      "select": {
        "options": [
          { "name": "High", "color": "red" },
          { "name": "Medium", "color": "yellow" },
          { "name": "Low", "color": "green" }
        ]
      }
    },
    "Assignee": { "type": "people" },
    "Due Date": { "type": "date" }
  },
  
  "created_at": ISODate("2025-11-17T10:05:00Z")
}
```

**Indexes:**
```javascript
db.notion_databases.createIndex({ "notion_id": 1 }, { unique: true })
db.notion_databases.createIndex({ "created_by": 1 })
db.notion_databases.createIndex({ "last_edited_time": -1 })
db.notion_databases.createIndex({ "archived": 1 })
```

---

## 4. Google Drive Plugin

### Design Strategy
- **Embed folder members**: Usually few per folder
- **Reference folders**: Hierarchical structure
- **Denormalize user emails**: For display
- **Separate activities**: High volume, queried independently

### `drive_activities`

```json
{
  "_id": ObjectId("..."),
  "timestamp": ISODate("2025-11-15T10:30:00Z"),
  "user_email": "john.doe@company.com",
  "user_name": "John Doe",  // Denormalized from members
  
  // Action details
  "action": "edit",  // create, edit, delete, move, share, comment
  "event_name": "EDIT",  // Google Drive event type
  
  // Document information (denormalized)
  "doc_id": "1abc2def3ghi",
  "doc_title": "Project Proposal",
  "doc_type": "document",  // document, spreadsheet, presentation, folder
  
  // Raw event data (for detailed analysis)
  "raw_event": {
    "primaryActionDetail": { ... },
    "actors": [ ... ],
    "targets": [ ... ]
  },
  
  "created_at": ISODate("2025-11-17T10:05:00Z")
}
```

**Indexes:**
```javascript
db.drive_activities.createIndex({ "timestamp": -1 })
db.drive_activities.createIndex({ "user_email": 1, "timestamp": -1 })
db.drive_activities.createIndex({ "doc_id": 1, "timestamp": -1 })
db.drive_activities.createIndex({ "action": 1 })
db.drive_activities.createIndex({ "doc_type": 1 })
```

### `drive_documents`

```json
{
  "_id": ObjectId("..."),
  "doc_id": "1abc2def3ghi",  // Google Drive document ID
  "title": "Project Proposal",
  "doc_type": "document",  // document, spreadsheet, presentation
  "first_seen": ISODate("2025-11-01T00:00:00Z"),
  "last_activity": ISODate("2025-11-15T10:30:00Z"),
  "created_at": ISODate("2025-11-17T10:05:00Z")
}
```

**Indexes:**
```javascript
db.drive_documents.createIndex({ "doc_id": 1 }, { unique: true })
db.drive_documents.createIndex({ "doc_type": 1 })
db.drive_documents.createIndex({ "last_activity": -1 })
```

### `drive_folders`

```json
{
  "_id": ObjectId("..."),
  "folder_id": "folder-abc-123",  // Google Drive folder ID
  "folder_name": "Project OOO",
  "parent_folder_id": "parent-folder-xyz-789",  // null if root
  "project_key": "project-ooo",  // Mapped to Slack channel
  "is_project_root": true,
  "created_by": "john.doe@company.com",
  "first_seen": ISODate("2025-01-01T00:00:00Z"),
  "last_activity": ISODate("2025-11-15T00:00:00Z"),
  
  // Embedded folder members (1:Few, typically < 20)
  "members": [
    {
      "user_email": "john.doe@company.com",
      "user_name": "John Doe",  // Denormalized
      "access_level": "writer",  // reader, writer, owner
      "added_at": ISODate("2025-01-01T00:00:00Z")
    },
    {
      "user_email": "jane.smith@company.com",
      "user_name": "Jane Smith",
      "access_level": "reader",
      "added_at": ISODate("2025-02-01T00:00:00Z")
    }
  ],
  
  "created_at": ISODate("2025-11-17T10:05:00Z")
}
```

**Indexes:**
```javascript
db.drive_folders.createIndex({ "folder_id": 1 }, { unique: true })
db.drive_folders.createIndex({ "parent_folder_id": 1 }, { sparse: true })
db.drive_folders.createIndex({ "project_key": 1 })
db.drive_folders.createIndex({ "is_project_root": 1 })
db.drive_folders.createIndex({ "members.user_email": 1 })
```

**Alternative (if many members):**
Separate `drive_folder_members` collection:
```json
{
  "_id": ObjectId("..."),
  "folder_id": "folder-abc-123",
  "user_email": "john.doe@company.com",
  "user_name": "John Doe",
  "access_level": "writer",
  "added_at": ISODate("2025-01-01T00:00:00Z"),
  "created_at": ISODate("2025-11-17T10:05:00Z")
}
```

---

## Cross-Plugin Integration

### Link Resolution

When a Slack message contains a GitHub PR link:

```json
// In slack_messages
{
  "links": [
    {
      "url": "https://github.com/tokamak-network/Tokamak-zk-EVM/pull/137",
      "link_type": "github_pr",
      "resource_id": "137",
      "repository_name": "tokamak-network/Tokamak-zk-EVM"
    }
  ]
}

// Can query github_pull_requests:
db.github_pull_requests.find({
  repository_name: "tokamak-network/Tokamak-zk-EVM",
  number: 137
})
```

### Member Activity Aggregation

```javascript
// Get all activities for a member
db.member_activities.find({ member_id: ObjectId("...") })
  .sort({ timestamp: -1 })

// Get member activities by type
db.member_activities.aggregate([
  { $match: { member_id: ObjectId("...") } },
  { $group: {
      _id: "$activity_type",
      count: { $sum: 1 }
    }
  },
  { $sort: { count: -1 } }
])
```

---

## Indexing Strategy

### General Principles

1. **Unique Identifiers**: Always index source-specific IDs (e.g., `slack_id`, `notion_id`)
2. **Query Patterns**: Index fields used in `find()` and `sort()`
3. **Compound Indexes**: For common query combinations
4. **Text Indexes**: For full-text search on messages, titles, etc.
5. **Sparse Indexes**: For optional fields (e.g., `thread_ts`)

### Index Naming Convention

```javascript
// Single field
{ "field_name": 1 }  // Ascending
{ "field_name": -1 }  // Descending

// Compound
{ "field1": 1, "field2": -1 }

// Text
{ "field_name": "text" }

// Unique
{ "field_name": 1 }, { unique: true }

// Sparse (for nullable fields)
{ "field_name": 1 }, { sparse: true }
```

### Performance Considerations

**Index Size:**
- Monitor index size vs document size
- Too many indexes slow down writes
- Too few indexes slow down reads

**Index Selection:**
```javascript
// Explain query to verify index usage
db.collection.find({ ... }).explain("executionStats")
```

---

## Migration Considerations

### 1. Data Migration Script

**Order of Migration:**
1. `members` (no dependencies)
2. Plugin-specific users (github users, slack users, notion users)
3. Plugin-specific content (commits, messages, pages, activities)
4. `member_activities` (unified log)

### 2. Incremental Migration

```javascript
// Example: Migrate GitHub commits in batches
const BATCH_SIZE = 1000;
let offset = 0;

while (true) {
  const commits = await sqlDb.query(`
    SELECT * FROM github_commits
    ORDER BY id
    LIMIT ${BATCH_SIZE} OFFSET ${offset}
  `);
  
  if (commits.length === 0) break;
  
  const mongoDocuments = commits.map(transformCommitToMongo);
  await mongoDb.github_commits.insertMany(mongoDocuments);
  
  offset += BATCH_SIZE;
}
```

### 3. Dual-Write Period

During migration, write to both SQL and MongoDB:
```python
# In plugin collect_data
def save_data(self, data):
    # Write to SQL (existing)
    self._save_to_sql(data)
    
    # Write to MongoDB (new)
    self._save_to_mongo(data)
```

### 4. Validation

```javascript
// Compare record counts
SELECT COUNT(*) FROM github_commits;
db.github_commits.countDocuments();

// Compare sample records
SELECT * FROM github_commits WHERE sha = 'abc123';
db.github_commits.findOne({ sha: 'abc123' });
```

---

## Document Size Monitoring

### Potential Issues

**Messages with Many Reactions:**
- If >100 reactions, consider separate `reactions` collection
- Monitor with: `db.slack_messages.stats()`

**Pages with Many Comments:**
- If >50 comments, consider separate `comments` collection
- Monitor with: `db.notion_pages.find({}).forEach(d => print(Object.bsonsize(d)))`

### Mitigation Strategies

1. **Array Size Limits**: Cap embedded arrays at reasonable size
2. **Reference Pattern**: Switch to referencing when arrays grow large
3. **Archiving**: Move old data to separate collections
4. **Sharding**: For very large datasets

---

## Query Patterns

### Example: Get Member Weekly Report

```javascript
// All activities for a member in a week
db.member_activities.find({
  member_id: ObjectId("..."),
  timestamp: {
    $gte: ISODate("2025-11-10T00:00:00Z"),
    $lte: ISODate("2025-11-16T23:59:59Z")
  }
}).sort({ timestamp: -1 })

// Aggregated by type
db.member_activities.aggregate([
  {
    $match: {
      member_id: ObjectId("..."),
      timestamp: {
        $gte: ISODate("2025-11-10T00:00:00Z"),
        $lte: ISODate("2025-11-16T23:59:59Z")
      }
    }
  },
  {
    $group: {
      _id: {
        source: "$source_type",
        type: "$activity_type"
      },
      count: { $sum: 1 }
    }
  },
  {
    $sort: { count: -1 }
  }
])
```

### Example: Project Activity Timeline

```javascript
// All Slack messages in a channel
db.slack_messages.find({
  channel_id: "C06TY9X8XNQ",
  posted_at: {
    $gte: ISODate("2025-11-10T00:00:00Z"),
    $lte: ISODate("2025-11-16T23:59:59Z")
  }
}).sort({ posted_at: -1 })

// With linked GitHub PRs
db.slack_messages.aggregate([
  {
    $match: {
      channel_id: "C06TY9X8XNQ",
      "links.link_type": "github_pr"
    }
  },
  { $unwind: "$links" },
  {
    $match: { "links.link_type": "github_pr" }
  },
  {
    $lookup: {
      from: "github_pull_requests",
      let: {
        repo: "$links.repository_name",
        pr_num: { $toInt: "$links.resource_id" }
      },
      pipeline: [
        {
          $match: {
            $expr: {
              $and: [
                { $eq: ["$repository_name", "$$repo"] },
                { $eq: ["$number", "$$pr_num"] }
              ]
            }
          }
        }
      ],
      as: "pr_details"
    }
  }
])
```

---

## Summary

### Collection Count

| Plugin | Collections | Total |
|--------|-------------|-------|
| **Main** | `members`, `member_activities` | 2 |
| **GitHub** | `commits`, `pull_requests`, `issues`, `repositories` | 4 |
| **Slack** | `channels`, `users`, `messages` | 3 |
| **Notion** | `users`, `pages`, `databases` | 3 |
| **Google Drive** | `activities`, `documents`, `folders` | 3 |
| **Total** | | **15** |

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Embed reactions in messages** | Few per message, always displayed together |
| **Embed comments in pages** | Few per page (usually < 20) |
| **Embed folder members** | Few per folder (usually < 20) |
| **Embed commit files** | Few per commit (usually < 30) |
| **Reference users** | Accessed independently, updated infrequently |
| **Reference channels/repos** | Accessed independently, large count |
| **Denormalize names** | Avoid JOINs for display |

---

**Next Steps:**
1. ✅ GitHub plugin - Complete
2. 🔄 Slack plugin - Implementation
3. 🔄 Notion plugin - Implementation
4. 🔄 Google Drive plugin - Implementation
5. 🔄 FastAPI endpoints - Update for MongoDB
6. 🔄 Dynamic query API - Redesign for MongoDB

---

**Questions or Feedback?**

This is a living document. Please update as we discover new patterns or requirements during implementation.

