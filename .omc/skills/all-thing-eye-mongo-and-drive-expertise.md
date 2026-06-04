---
name: all-thing-eye-mongo-and-drive-expertise
description: Two infra facts that shape data work here — the app mongo user can only write the `ati` DB, and Google Drive shared-drive content needs allDrives flags
triggers:
  - not authorized on ati_archive
  - separate database mongo permission
  - ale mongo user readWrite
  - grantRolesToUser
  - corpora allDrives
  - supportsAllDrives includeItemsFromAllDrives
  - Meet Recordings mp4 invisible
  - member_artifacts archive_members
  - export member tenure
---

# all-thing-eye — Mongo Permissions & Google Drive Shared-Drive Access

## The Insight
Two hard limits decide HOW you can add data/features here. Both look like "permission denied / not found" but have specific, different causes.

## 1. The app mongo user `ale` can only WRITE the `ati` database
- `connectionStatus` on the prod mongo shows: `ale` has `readWrite` on **`ati`** only, plus `read` on `shared` and `gemini`, and **no access to any other DB**.
- Consequence: you **cannot** create/populate a *separate* database (e.g. `ati_archive`) with the app credentials — writes fail with `not authorized on ati_archive`. The runtime app also connects as `ale`, so even reads from a new DB would fail.
- The mongo root (`admin`) password is **rotated** — it is NOT the docker-compose default `changeme`, and NOT the value in the container's `MONGO_INITDB_ROOT_PASSWORD` env (INITDB vars are init-time only). So you can't self-grant roles.
- **The Approach:** keep new data as new COLLECTIONS inside `ati` (which `ale` can write), not a new DB. This session put retired-member data in `ati.archive_members` + `ati.member_artifacts` (additive collections, rollback = drop them). Source/activity collections (`github_commits`, `slack_messages`, ...) are never modified. A truly separate DB requires a DBA to run `db.getSiblingDB("ati").grantRolesToUser("ale",[{role:"readWrite",db:"<newdb>"}])`.

## 2. Google Drive shared-drive content is INVISIBLE without the allDrives flags
- Meet recordings (mp4) and `... – Transcript` docs live in **Shared Drives** with participant-scoped ACLs. They appear permission-blocked but are not — it's a missing-flag problem.
- The claude.ai Drive MCP search AND the project's `src/plugins/google_drive_plugin*.py` both OMIT the shared-drive flags, so they return empty for those folders.
- **The Approach:** with the project's `drive.readonly` token (`config/google_drive/token_diff.pickle`, account `ale@tokamak.network`), pass **`supportsAllDrives=True, includeItemsFromAllDrives=True, corpora="allDrives"`** to `files().list()`. That surfaces ~4,000 recordings/transcripts org-wide back to 2018. Folder-by-`'<id>' in parents` queries still return empty for these — use a **global name/mimeType search** (`mimeType='video/mp4'`, `name contains 'Transcript'`), not folder traversal.

## Recognition Pattern
- "not authorized on X" where X != ati → it's the user-scope limit, not a bug. Use `ati`.
- Drive folder shows in UI but API returns 0 children, or mp4/transcripts "missing" → add the allDrives flags.

## Example
```python
# Drive: reach shared-drive recordings/transcripts
svc.files().list(q="mimeType='video/mp4' and trashed=false",
                 corpora="allDrives", supportsAllDrives=True,
                 includeItemsFromAllDrives=True, fields="files(id,name,createdTime)")
```
Related: `scripts/import_member_materials.py` (CSV -> ati.member_artifacts, idempotent, --dry-run), `scripts/rollback_unified_import.py` (drops the additive collections), and `GET /api/v1/custom-export/member-tenure?member=NAME` (all of a member's data across every source as one artifact-format CSV, grouped by source).
