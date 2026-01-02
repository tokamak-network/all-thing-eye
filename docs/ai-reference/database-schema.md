# Database Schema Reference

This document describes the MongoDB collections used in All-Thing-Eye platform.

## Collections Overview

| Collection             | Description                  | Key Fields                                      |
| ---------------------- | ---------------------------- | ----------------------------------------------- |
| `members`              | Team member information      | name, email, role, projects                     |
| `member_identifiers`   | Maps platform IDs to members | member_id, identifier_type, identifier_value    |
| `projects`             | Project configuration        | key, name, lead, repositories, slack_channel_id |
| `github_commits`       | GitHub commit history        | author_name, repository, date, message          |
| `github_pull_requests` | Pull requests                | author, repository, state, created_at           |
| `slack_messages`       | Slack messages               | user_name, channel_id, text, posted_at          |
| `slack_channels`       | Slack channel info           | channel_id, channel_name                        |
| `notion_pages`         | Notion page activities       | title, last_edited_time, created_by             |
| `drive_activities`     | Google Drive activities      | ⚠️ NOT READY - Do not use                       |

---

## Detailed Schemas

### members

```json
{
  "_id": "ObjectId",
  "name": "string (display name, e.g., 'Ale')",
  "email": "string (e.g., 'ale@tokamak.network')",
  "role": "string (e.g., 'Project Lead', 'Developer')",
  "projects": ["string (project keys, e.g., 'project-ooo')"],
  "eoa_address": "string (Ethereum address)",
  "github_username": "string (optional, stored directly)",
  "slack_id": "string (optional, stored directly)",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### member_identifiers

Maps external platform IDs to member records.

```json
{
  "_id": "ObjectId",
  "member_id": "string (references members._id)",
  "identifier_type": "string (github | slack_id | slack_name | email | notion)",
  "identifier_value": "string (the actual ID/username)",
  "created_at": "datetime"
}
```

**Common identifier_type values:**

- `github`: GitHub username (e.g., "SonYoungsung")
- `slack_id`: Slack user ID (e.g., "U079GNX54MT")
- `slack_name`: Slack display name (e.g., "ale")
- `email`: Email address
- `notion`: Notion user ID

### projects

```json
{
  "_id": "ObjectId",
  "key": "string (unique key, e.g., 'project-ooo')",
  "name": "string (display name, e.g., 'Ooo')",
  "description": "string",
  "lead": "string (member name)",
  "repositories": ["string (GitHub repo names)"],
  "slack_channel": "string (channel name)",
  "slack_channel_id": "string (Slack channel ID)",
  "member_ids": ["string (member ObjectId references)"],
  "is_active": "boolean",
  "created_at": "datetime"
}
```

### github_commits

```json
{
  "_id": "ObjectId",
  "sha": "string (commit hash)",
  "author_name": "string (GitHub username, NOT member name)",
  "author_email": "string",
  "repository": "string (repo name without org)",
  "message": "string (commit message)",
  "date": "datetime (commit date - USE THIS for date filtering)",
  "additions": "integer",
  "deletions": "integer",
  "total_changes": "integer",
  "url": "string (GitHub commit URL)",
  "files": ["object (changed files)"],
  "collected_at": "datetime"
}
```

**Important:**

- `author_name` contains GitHub username (e.g., "SonYoungsung"), not the display name
- Use `member_identifiers` to map GitHub username to member name
- Date field is `date`, not `committed_at` or `timestamp`

### github_pull_requests

```json
{
  "_id": "ObjectId",
  "number": "integer",
  "title": "string",
  "author": "string (GitHub username)",
  "repository": "string",
  "state": "string (open | closed | merged)",
  "created_at": "datetime",
  "merged_at": "datetime (null if not merged)",
  "url": "string"
}
```

### slack_messages

```json
{
  "_id": "ObjectId",
  "ts": "string (Slack timestamp ID)",
  "user_id": "string (Slack user ID)",
  "user_name": "string (lowercase name, e.g., 'ale')",
  "channel_id": "string (Slack channel ID)",
  "channel_name": "string",
  "text": "string (message content)",
  "posted_at": "datetime (USE THIS for date filtering)",
  "thread_ts": "string (parent message for threads)",
  "reply_count": "integer",
  "reactions": ["object"],
  "files": ["object (attached files)"],
  "links": ["object (shared links)"],
  "collected_at": "datetime"
}
```

**Important:**

- `user_name` is lowercase (e.g., "ale", "jake")
- Date field is `posted_at`, not `timestamp`
- Use case-insensitive matching for member names

### slack_channels

```json
{
  "_id": "ObjectId",
  "channel_id": "string (Slack channel ID)",
  "channel_name": "string (e.g., 'project-ooo')",
  "is_private": "boolean",
  "member_count": "integer"
}
```

### notion_pages

```json
{
  "_id": "ObjectId",
  "page_id": "string (Notion page ID)",
  "title": "string",
  "created_by": "string (user name or ID)",
  "last_edited_by": "string",
  "created_time": "datetime",
  "last_edited_time": "datetime",
  "parent_type": "string (database | page | workspace)",
  "url": "string"
}
```

### drive_activities

⚠️ **NOT READY FOR USE** - Google Drive data collection is still being refined. Do not query this collection.

```json
{
  "_id": "ObjectId",
  "user_email": "string",
  "action": "string (e.g., 'edit', 'view', 'create')",
  "doc_title": "string",
  "doc_type": "string",
  "file_id": "string",
  "timestamp": "datetime",
  "url": "string"
}
```

---

## Key Relationships

### Member → Activities Mapping

To find activities for a member:

1. **GitHub**:

   - Find `identifier_value` where `identifier_type='github'` for the member
   - Query `github_commits` where `author_name` matches the GitHub username

2. **Slack**:

   - Find `identifier_value` where `identifier_type='slack_name'` or use lowercase member name
   - Query `slack_messages` where `user_name` matches

3. **General pattern**:
   ```
   members.name → member_identifiers.identifier_value → activity.author_field
   ```

### Project → Activities Mapping

To find activities for a project:

1. **GitHub**: Query `github_commits` where `repository` is in `projects.repositories`
2. **Slack**: Query `slack_messages` where `channel_id` equals `projects.slack_channel_id`

---

## Common Query Patterns

### Get member's GitHub commits (last 30 days)

```python
# 1. Get GitHub username from member_identifiers
identifier = db.member_identifiers.find_one({
    'member_id': member_id,
    'identifier_type': 'github'
})
github_username = identifier['identifier_value']

# 2. Query commits
commits = db.github_commits.find({
    'author_name': github_username,
    'date': {'$gte': start_date}
})
```

### Get member's Slack messages

```python
# user_name is lowercase member name
messages = db.slack_messages.find({
    'user_name': member_name.lower(),
    'posted_at': {'$gte': start_date}
})
```

### Get project activity

```python
project = db.projects.find_one({'key': project_key})

# GitHub
commits = db.github_commits.find({
    'repository': {'$in': project['repositories']},
    'date': {'$gte': start_date}
})

# Slack
messages = db.slack_messages.find({
    'channel_id': project['slack_channel_id'],
    'posted_at': {'$gte': start_date}
})
```
