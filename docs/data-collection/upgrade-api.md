# Specification: Granular Data Collection for Google Drive & Notion

## 1. Project Goal

구글 드라이브(Docs)와 노션(Notion) API는 변경된 '내용(Diff)'을 직접 제공하지 않음. 본 프로젝트는 API를 통해 수집된 데이터의 노이즈를 제거하고, 이전 스냅샷과의 비교를 통해 '추가/삭제된 텍스트'를 정밀하게 추출하는 시스템 구현을 목표로 함.

---

## 2. Google Drive (Google Docs) Implementation Guide

### 2.1 핵심 메커니즘: Revision Comparison

구글 드라이브 API는 문서의 수정 이력을 `revisions` 리소스로 관리함.

1.  **Revision 탐색**: `drive.revisions.list`를 통해 파일의 버전 목록을 가져옴.
2.  **콘텐츠 추출**: `drive.revisions.get`을 사용하되, `exportLinks`에서 `text/plain` 타입을 선택하여 서식(Formatting) 노이즈를 제거한 순수 텍스트를 다운로드함.
3.  **차이점 분석(Diffing)**: 다운로드한 두 버전($V_{n-1}$, $V_n$)의 텍스트를 비교 엔진에 전달.

### 2.2 기술적 요구사항

- **Library**: Python의 `difflib` 또는 JS의 `jsdiff` 사용.
- **Workflow**:
  - `last_processed_revision_id`를 DB에 기록하여 중복 처리 방지.
  - 변경 알림(Webhook) 수신 시 최신 버전과 DB에 저장된 마지막 버전을 비교.

---

## 3. Notion Implementation Guide

### 3.1 핵심 메커니즘: Block-based Snapshot

노션은 페이지가 블록(Block)의 집합체임. API는 페이지 전체의 Diff를 제공하지 않으므로 블록 단위 추적이 필요함.

1.  **전체 블록 수집**: `blocks.children.list`를 사용하여 페이지 내 모든 블록 데이터를 재귀적으로 가져옴.
2.  **스냅샷 저장**: 각 블록의 `id`, `last_edited_time`, 그리고 `plain_text` 내용을 DB에 저장.
3.  **상태 비교 로직**:
    - **Added**: 새로운 `block_id` 발견.
    - **Deleted**: 기존 DB에는 있으나 API 응답에서 사라진 `block_id`.
    - **Updated**: `block_id`는 같으나 `last_edited_time`이 갱신된 경우 (내부 텍스트 비교 수행).

### 3.2 노이즈 필터링

- `rich_text` 배열 내의 `annotations`(색상, 볼드 처리 등) 정보는 무시하고 오직 `plain_text` 필드만 수집하여 데이터 순도를 높임.

---

## 4. Common Data Processing (Post-processing)

### 4.1 Diff Output Format

추출된 데이터는 아래와 같은 구조화된 JSON 형태로 저장되어야 함:

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

---

## 5. Database Schema (Test Implementation)

### 5.1 Google Drive Tables

```sql
-- Revision snapshots
CREATE TABLE drive_revisions (
    document_id TEXT NOT NULL,
    revision_id TEXT NOT NULL,
    plain_text TEXT,
    editor_email TEXT,
    modified_time TEXT,
    snapshot_time TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, revision_id)
);

-- Tracking state
CREATE TABLE drive_tracking (
    document_id TEXT PRIMARY KEY,
    document_title TEXT,
    last_processed_revision_id TEXT,
    last_check_time TEXT
);
```

### 5.2 Notion Tables

```sql
-- Block snapshots
CREATE TABLE notion_blocks (
    page_id TEXT NOT NULL,
    block_id TEXT NOT NULL,
    block_type TEXT,
    plain_text TEXT,
    last_edited_time TEXT,
    parent_block_id TEXT,
    snapshot_time TEXT,
    is_current INTEGER DEFAULT 1
);

-- Tracking state
CREATE TABLE notion_tracking (
    page_id TEXT PRIMARY KEY,
    page_title TEXT,
    last_snapshot_time TEXT,
    last_edited_time TEXT
);
```

### 5.3 Common Tables

```sql
-- Diff history for analysis
CREATE TABLE diff_history (
    platform TEXT NOT NULL,
    document_id TEXT NOT NULL,
    editor TEXT,
    timestamp TEXT,
    diff_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

## 6. Test Implementation

테스트 구현체는 `tests/diff_collection/` 디렉토리에 위치함.

### 6.1 Usage

```bash
# Notion 페이지 diff 수집
python tests/diff_collection/test_diff_collector.py --source notion --page-id <PAGE_ID>

# Google Drive 문서 diff 수집
python tests/diff_collection/test_diff_collector.py --source drive --doc-id <DOC_ID>

# 추적 중인 문서 목록
python tests/diff_collection/test_diff_collector.py --list-tracked

# Diff 히스토리 조회
python tests/diff_collection/test_diff_collector.py --history
```

### 6.2 Test Database

- 위치: `tests/diff_collection/test_diff.db` (SQLite)
- 프로덕션 DB와 분리되어 있어 안전하게 테스트 가능

### 6.3 Required Environment

```bash
# Notion
export NOTION_TOKEN="your_notion_integration_token"

# Google Drive (credentials.json 필요)
# config/google_drive/credentials.json
```

---

## 7. Future Enhancements

1. **Webhook Integration**: 실시간 변경 감지
2. **Batch Processing**: 다수의 문서를 한번에 처리
3. **MongoDB Integration**: 프로덕션용 MongoDB 스토리지
4. **Semantic Diff**: AI를 활용한 의미 기반 변경 분석
