# Drive Content Diffs Pipeline (Future Implementation)

## Overview

이 문서는 Google Drive의 스냅샷 기반 콘텐츠 변경 추적 파이프라인에 대한 설계 문서입니다.
Notion의 diff 기반 수집 방식과 유사하게, 문서의 실제 내용 변경을 추적합니다.

## Current State (2026-01)

### 현재 사용 중인 컬렉션
- `drive_activities`: Google Admin Reports API 기반 활동 로그 (586,408+ documents)
  - 편집, 조회, 공유 등의 이벤트 기록
  - 실제 콘텐츠 변경 내용은 포함하지 않음

### 준비된 컬렉션 (데이터 수집 대기 중)
- `drive_content_diffs`: 콘텐츠 diff 저장용 (현재 0 documents)
- `drive_revision_snapshots`: 리비전 스냅샷 저장 (989 documents)
- `drive_tracked_documents`: 추적 대상 문서 목록 (989 documents)

## Target Architecture

### 데이터 흐름
```
Google Drive API (Revisions)
         │
         ▼
┌─────────────────────┐
│ drive_tracked_      │  추적할 문서 목록
│ documents           │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ drive_revision_     │  각 리비전의 전체 콘텐츠
│ snapshots           │
└─────────────────────┘
         │
         ▼  (diff 계산)
┌─────────────────────┐
│ drive_content_      │  변경된 부분만 저장
│ diffs               │
└─────────────────────┘
```

### drive_content_diffs 스키마 (예상)

```javascript
{
  "_id": ObjectId,
  "document_id": "1abc...xyz",           // Google Drive file ID
  "document_title": "Project Spec",
  "document_url": "https://docs.google.com/...",
  "revision_id": "456",
  "previous_revision_id": "455",
  "editor_id": "user@tokamak.network",   // 편집자 이메일
  "editor_name": "Kevin",                 // 매핑된 멤버 이름
  "timestamp": "2026-01-15T10:30:00Z",   // ISO 문자열
  "diff_type": "revision",               // revision, create, delete
  "changes": {
    "added": ["new paragraph text...", "another addition..."],
    "deleted": ["removed text...", "another deletion..."],
    "modified": [
      {
        "before": "old text",
        "after": "new text"
      }
    ]
  },
  "stats": {
    "additions": 150,      // 추가된 문자 수
    "deletions": 30,       // 삭제된 문자 수
    "net_change": 120
  },
  "collected_at": ISODate("2026-01-15T10:35:00Z")
}
```

## Implementation Plan

### Phase 1: Baseline Collection
1. `drive_tracked_documents`에 추적 대상 문서 등록
2. 각 문서의 현재 버전을 `drive_revision_snapshots`에 저장 (baseline)

### Phase 2: Diff Collection
1. 주기적으로 (예: 매일) 추적 대상 문서의 새 리비전 확인
2. 이전 스냅샷과 비교하여 diff 계산
3. `drive_content_diffs`에 저장

### Phase 3: Integration
1. GraphQL activities 쿼리에서 `drive_content_diffs` 사용
2. 기존 `drive_activities`와 병합하여 표시

## Related Files

### 수집 스크립트 (참고용)
- `scripts/create_drive_baseline.py`: 베이스라인 생성
- `scripts/collect_drive_diff.py`: Diff 수집

### GraphQL 쿼리 (수정 필요)
- `backend/graphql/queries.py`: activities 쿼리의 Drive 섹션
  - 현재: `drive_activities` 사용
  - 향후: `drive_content_diffs` + `drive_activities` 병합

### 이전 구현 코드 (참고용)
아래는 `drive_content_diffs`를 사용하던 이전 코드입니다:

```python
# backend/graphql/queries.py - Drive content diffs section (비활성화됨)

if "drive" in sources:
    query = {}

    # Filter by member name (editor_name or editor_id/email)
    if member_name:
        emails = member_identifiers.get("email", []) or member_identifiers.get(
            "drive", []
        )
        or_conditions = []
        or_conditions.append(
            {"editor_name": {"$regex": f"^{member_name}", "$options": "i"}}
        )
        if emails:
            or_conditions.append({"editor_id": {"$in": emails}})
        query["$or"] = or_conditions

    # Date filters - timestamp is stored as ISO string
    if start_date:
        start_str = start_date.astimezone(tz.utc).isoformat()
        query["timestamp"] = {"$gte": start_str}
    if end_date:
        end_str = end_date.astimezone(tz.utc).isoformat()
        query["timestamp"] = query.get("timestamp", {})
        query["timestamp"]["$lte"] = end_str

    # Keyword search in document title
    if keyword:
        query["document_title"] = {"$regex": keyword, "$options": "i"}

    async for doc in (
        db["drive_content_diffs"]
        .find(query)
        .sort("timestamp", -1)
        .limit(limit * 2)
    ):
        # Get editor name
        doc_member_name = doc.get("editor_name", "Unknown")
        if not doc_member_name or doc_member_name == "Unknown":
            editor_id = doc.get("editor_id", "")
            if editor_id and "@" in editor_id:
                doc_member_name = editor_id.split("@")[0].capitalize()

        # Parse timestamp from ISO string
        timestamp_str = doc.get("timestamp", "")
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str[:-1] + "+00:00"
        timestamp = datetime.fromisoformat(timestamp_str)

        # Get changes for metadata
        changes = doc.get("changes", {})
        additions = len(changes.get("added", []))
        deletions = len(changes.get("deleted", []))

        activities.append(
            Activity(
                id=str(doc["_id"]),
                member_name=doc_member_name,
                source_type="drive",
                activity_type="drive_revision",
                timestamp=timestamp,
                metadata=sanitize_metadata({
                    "document_id": doc.get("document_id"),
                    "title": doc.get("document_title"),
                    "url": doc.get("document_url"),
                    "diff_type": doc.get("diff_type", "revision"),
                    "additions": additions,
                    "deletions": deletions,
                    "changes": changes,
                }),
            )
        )
```

## Notes

- Notion diff 파이프라인 구현 참고: `scripts/collect_notion_diff.py`, `scripts/create_notion_baseline.py`
- Google Drive Revisions API 문서: https://developers.google.com/drive/api/v3/reference/revisions
- Rate limit 주의: Google Drive API는 사용자당 일일 쿼터가 있음

## Changelog

- 2026-01-29: 문서 작성, 현재 상태 및 향후 계획 정리
