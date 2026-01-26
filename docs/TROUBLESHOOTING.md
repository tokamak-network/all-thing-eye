# Troubleshooting Guide

This document contains known issues and their solutions for the All-Thing-Eye platform.

---

## Table of Contents

1. [Project Members Display Issues](#project-members-display-issues)

---

## Project Members Display Issues

### Issue: Members show as "Unknown (xxxxxxxx...)" or "Orphaned (xxxxxxxx...)"

**Symptoms:**
- In the Edit Project modal, project members display as `Unknown (6970eb50...)×` or `Orphaned (6970eb50...)×`
- Member names showed correctly when first added, but later appear as Unknown/Orphaned
- The issue persists after page refresh

**Root Causes:**

#### Cause 1: Inactive Members (Fixed in commit 3ac09b4)

The `useMembers` query was filtering out inactive members by default. When a member was deactivated, their ID remained in the project's `member_ids`, but couldn't be resolved to a name.

**Solution Applied:**
- Changed `useMembers({ limit: 1000 })` to `useMembers({ limit: 1000, includeInactive: true })`
- Added visual indicators: active (green), inactive (gray strikethrough), orphaned (red)

**Files Modified:**
- `frontend/src/app/projects/page.tsx`
- `backend/graphql/types.py`

#### Cause 2: Orphaned Member IDs (Database Mismatch)

Member IDs stored in `projects.member_ids` no longer exist in the `members` collection. This happens when:

1. **`build_member_index_mongo.py` was executed** - This script:
   - Deletes ALL documents from `members` collection
   - Recreates members from `config/members.yaml` with NEW ObjectIds
   - All previously stored `member_ids` in projects become orphaned

2. **Members were manually deleted from MongoDB**

3. **Database was restored from a backup with different member IDs**

**How to Verify:**
```bash
# Check if member ID exists in database
mongosh
use all_thing_eye
db.members.findOne({_id: ObjectId("6970eb50...")})  # Replace with actual ID
```

**How to Fix:**
1. In the Edit Project modal, click the × button next to each orphaned member
2. Search and select the correct members from the dropdown
3. Save the project

The new member selection will store valid ObjectIds that exist in the current database.

**Prevention:**
- **Do NOT run `build_member_index_mongo.py`** on production after projects have members assigned
- The comment in `daily_data_collection_mongo.py` (line 541-542) states: "Member index is now managed exclusively through the frontend UI"
- Use the Admin panel to manage members instead of the script

---

## Data Flow Reference

### Project Members Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Edit Project Modal                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. Load Members                                                         │
│     useMembers({ limit: 1000, includeInactive: true })                  │
│           │                                                              │
│           ▼                                                              │
│     GraphQL: members(includeInactive: true)                             │
│           │                                                              │
│           ▼                                                              │
│     MongoDB: db.members.find({})  ← Returns all members with ObjectIds  │
│           │                                                              │
│           ▼                                                              │
│     allMembers = [{ id: "abc123", name: "John", is_active: true }, ...] │
│                                                                          │
│  2. Load Project                                                         │
│     project.member_ids = ["abc123", "def456", "6970eb50..."]            │
│                                                                          │
│  3. Display Members                                                      │
│     for each memberId in project.member_ids:                            │
│       member = allMembers.find(m => m.id === memberId)                  │
│       if (!member) → Show "Orphaned (id...)" (red)                      │
│       else if (!member.is_active) → Show "Name (inactive)" (gray)       │
│       else → Show "Name" (green)                                        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Visual Indicators

| Status | Style | Description |
|--------|-------|-------------|
| Active | Green badge | Member exists and is active |
| Inactive | Gray badge, strikethrough, "(inactive)" label | Member exists but is inactive |
| Orphaned | Red badge, "Orphaned (id...)" | Member ID doesn't exist in database |

---

## Related Files

- `frontend/src/app/projects/page.tsx` - Edit Project modal with member selection
- `backend/graphql/types.py` - Project.members resolver with orphaned ID logging
- `backend/graphql/queries.py` - Members query with `include_inactive` filter
- `scripts/build_member_index_mongo.py` - Script that rebuilds member index (CAUTION)

---

## Logging

When orphaned member_ids are detected, the backend logs a warning:

```
[Project.members] ORPHANED_MEMBER_IDS DETECTED - Project: project-xxx, Orphaned count: 4, Orphaned IDs: ['6970eb50...', ...]. These member IDs no longer exist in the members collection.
```

Check backend logs when debugging member display issues.
