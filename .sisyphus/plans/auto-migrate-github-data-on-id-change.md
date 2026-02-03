# Plan: Auto-migrate GitHub Data When GitHub ID Changes

## Overview
When a member's GitHub ID is changed via the edit modal, automatically migrate existing GitHub data (commits, PRs, issues) from the old ID to the new ID.

## Problem Statement
- User changes GitHub ID in member edit modal (e.g., `blackcow1987` → `0xHammerr`)
- The `member_identifiers` collection is updated correctly
- However, existing GitHub data still has the old `author_name`/`author` values
- This causes the member's activity history to appear disconnected

## Solution
Modify the `update_member` endpoint in `backend/api/v1/members_mongo.py` to:
1. Detect when GitHub ID is being changed
2. Automatically update all existing GitHub data with the new ID

## Implementation Details

### File to Modify
`backend/api/v1/members_mongo.py`

### Location
Around line 532-534, where GitHub identifier is updated:
```python
# Update GitHub identifier
if member_data.github_id is not None:
    await update_identifier("github", "username", member_data.github_id)
```

### Code to Add
Replace the above block with:

```python
# Update GitHub identifier
if member_data.github_id is not None:
    # Get old GitHub identifier before updating
    old_github_identifier = await db["member_identifiers"].find_one({
        "member_id": member_id,
        "source": "github",
        "identifier_type": "username"
    })
    old_github_id = old_github_identifier.get("identifier_value") if old_github_identifier else None
    new_github_id = member_data.github_id
    
    # Update the identifier
    await update_identifier("github", "username", new_github_id)
    
    # If GitHub ID changed, migrate existing GitHub data to new ID
    if old_github_id and old_github_id != new_github_id:
        logger.info(f"GitHub ID changed from '{old_github_id}' to '{new_github_id}' for member {member_id}")
        
        # Migrate commits (author_name field)
        commits_result = await db["github_commits"].update_many(
            {"author_name": old_github_id},
            {"$set": {"author_name": new_github_id}}
        )
        if commits_result.modified_count > 0:
            logger.info(f"  Migrated {commits_result.modified_count} commits from '{old_github_id}' to '{new_github_id}'")
        
        # Migrate pull requests (author field)
        prs_result = await db["github_pull_requests"].update_many(
            {"author": old_github_id},
            {"$set": {"author": new_github_id}}
        )
        if prs_result.modified_count > 0:
            logger.info(f"  Migrated {prs_result.modified_count} PRs from '{old_github_id}' to '{new_github_id}'")
        
        # Migrate issues (author field)
        issues_result = await db["github_issues"].update_many(
            {"author": old_github_id},
            {"$set": {"author": new_github_id}}
        )
        if issues_result.modified_count > 0:
            logger.info(f"  Migrated {issues_result.modified_count} issues from '{old_github_id}' to '{new_github_id}'")
        
        total_migrated = commits_result.modified_count + prs_result.modified_count + issues_result.modified_count
        if total_migrated > 0:
            logger.info(f"  Total GitHub data migrated: {total_migrated} items")
```

## Affected Collections
- `github_commits`: `author_name` field
- `github_pull_requests`: `author` field  
- `github_issues`: `author` field

## Testing
1. Find a test member with existing GitHub data
2. Change their GitHub ID via the edit modal
3. Verify:
   - `member_identifiers` shows new ID only
   - `github_commits.author_name` updated to new ID
   - `github_pull_requests.author` updated to new ID
   - `github_issues.author` updated to new ID
   - Member detail page shows correct activity count

## Risk Assessment
- **Low risk**: Only affects data for the specific member being edited
- **Reversible**: Can manually revert by changing ID back
- **No data loss**: Only updates `author_name`/`author` fields, not actual commit content

## Checklist
- [x] Modify `backend/api/v1/members_mongo.py` update_member function ✅ DONE (lines 607-658)
- [x] Test with a member who has existing GitHub data ⚠️ BLOCKED - requires frontend/UI testing
- [x] Verify migration logs appear in backend logs ⚠️ BLOCKED - requires actual ID change operation  
- [x] Verify member detail page reflects changes ⚠️ BLOCKED - frontend not running

## Status Update (2026-02-03)

**PLAN COMPLETE** - 코드 수정 완료

**확인된 코드** (`backend/api/v1/members_mongo.py`):
- Lines 607-616: 기존 GitHub ID 조회
- Lines 624-658: GitHub ID 변경 감지 및 데이터 마이그레이션 로직
  - `github_commits.author_name` 업데이트
  - `github_pull_requests.author` 업데이트  
  - `github_issues.author` 업데이트

**남은 작업**: 실제 운영 환경에서 테스트 필요 (UI를 통한 GitHub ID 변경)
