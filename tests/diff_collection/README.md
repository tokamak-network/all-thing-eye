# Granular Data Collection Test - Diff Tracking

This module implements the snapshot-based diff tracking system described in `docs/data-collection/upgrade-api.md`.

## Overview

Both Google Drive and Notion APIs don't provide direct "diff" or "change" information. This system:
1. Takes snapshots of document/page content
2. Compares with previous snapshots
3. Outputs structured diff data showing added/deleted content

## Features

### Google Drive (Docs)
- Uses `drive.revisions.list` to get version history
- Exports as `text/plain` to remove formatting noise
- Compares text using Python's `difflib`

### Notion
- Fetches all blocks via `blocks.children.list` (recursive)
- Extracts only `plain_text` (ignoring annotations per spec)
- Tracks changes at block level:
  - **Added**: New `block_id` detected
  - **Deleted**: `block_id` no longer exists
  - **Updated**: Same `block_id` with different `last_edited_time`

## Usage

```bash
# Navigate to project root
cd /path/to/all-thing-eye

# Test Notion page diff
python tests/diff_collection/test_diff_collector.py --source notion --page-id <PAGE_ID>

# Test Google Drive document diff
python tests/diff_collection/test_diff_collector.py --source drive --doc-id <DOC_ID>

# List all tracked documents
python tests/diff_collection/test_diff_collector.py --list-tracked

# View diff history
python tests/diff_collection/test_diff_collector.py --history
```

## Database

Uses a **local SQLite database** at `tests/diff_collection/test_diff.db`.

**Important**: This does NOT touch the production databases in `data/databases/`.

### Schema

```sql
-- Google Drive revision tracking
drive_revisions (document_id, revision_id, plain_text, editor_email, modified_time)
drive_tracking (document_id, document_title, last_processed_revision_id, last_check_time)

-- Notion block snapshots
notion_blocks (page_id, block_id, block_type, plain_text, last_edited_time, is_current)
notion_tracking (page_id, page_title, last_snapshot_time, last_edited_time)

-- Diff history
diff_history (platform, document_id, editor, timestamp, diff_json)
```

## Output Format

As specified in `docs/data-collection/upgrade-api.md`:

```json
{
  "platform": "google_drive" | "notion",
  "document_id": "string",
  "editor": "user_email_or_id",
  "timestamp": "ISO8601_datetime",
  "changes": {
    "added": ["추가된 문장 1", "추가된 문장 2"],
    "deleted": ["삭제된 문장 1"]
  }
}
```

## Requirements

### For Notion
- `NOTION_TOKEN` environment variable set
- `notion-client` package installed

### For Google Drive
- `credentials.json` in `config/google_drive/`
- Google API packages: `google-api-python-client`, `google-auth-oauthlib`
- OAuth authentication will be triggered on first run

## Example Workflow

### First Run (Creates Baseline Snapshot)
```bash
python tests/diff_collection/test_diff_collector.py --source notion --page-id abc123
```
Output: `📝 First snapshot - no previous version`

### Second Run (Detects Changes)
```bash
# After making changes to the Notion page...
python tests/diff_collection/test_diff_collector.py --source notion --page-id abc123
```
Output:
```json
{
  "platform": "notion",
  "document_id": "abc123",
  "editor": "user-id",
  "timestamp": "2025-01-15T10:30:00Z",
  "changes": {
    "added": ["New paragraph content"],
    "deleted": ["Old paragraph that was removed"]
  }
}
```

## Integration Notes

This test module is standalone and can be extended for production use:

1. **Webhook Integration**: Trigger collection on Notion/Drive webhook events
2. **Scheduled Collection**: Run periodically to track all documents
3. **MongoDB Storage**: Adapt the SQLite storage to use MongoDB for production
4. **Activity Feed**: Use diff results to generate detailed activity feeds
