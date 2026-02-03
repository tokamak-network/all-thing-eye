# Recording Name Filter Enhancement

## TL;DR

> **Quick Summary**: Activities API의 recordings 필터링 시 멤버의 `recording_name` 필드도 함께 검색하도록 수정
> 
> **Deliverables**:
> - `activities_mongo.py` 수정: recordings/recordings_daily 필터링 로직 개선
> 
> **Estimated Effort**: Quick
> **Parallel Execution**: NO - sequential
> **Critical Path**: Task 1 → Task 2 (테스트)

---

## Context

### Original Request
멤버 필터링 시 recording 데이터의 경우, 멤버 이름과 레코딩에 녹화되는 이름이 다른 경우가 있음. 예: Zena의 recording_name은 "Suah Kim". 현재는 "Zena"로 필터링하면 recordings에서 아무것도 나오지 않음.

### Interview Summary
**Key Discussions**:
- Zena의 `members.recording_name` = "Suah Kim" (이미 업데이트됨)
- 레코딩 `participants` 필드에는 풀네임이 사용됨 (예: "Suah Kim", "Kevin Jeong")
- 현재 필터링은 `filter_member_name`만 검색하므로 매칭 안 됨

**Research Findings**:
- `recordings` source (line 765-895): `gemini_recordings_col.participants` 필드로 필터링
- `recordings_daily` source (line 897-1019): `analysis.participants[].name` 필드로 필터링
- 두 곳 모두 수정 필요

---

## Work Objectives

### Core Objective
Activities API에서 recordings 관련 소스 필터링 시 `members.recording_name` 필드도 함께 검색하여 이름이 다른 경우에도 올바르게 필터링되도록 함

### Concrete Deliverables
- `backend/api/v1/activities_mongo.py` 수정

### Definition of Done
- [ ] Zena + recordings 필터로 API 호출 시 Suah Kim이 참석한 레코딩이 반환됨
- [ ] Zena + recordings_daily 필터로 API 호출 시 Suah Kim이 참석한 daily analysis가 반환됨

### Must Have
- `filter_member_name`으로 검색 시 해당 멤버의 `recording_name`도 함께 검색
- 기존 필터링 로직 유지 (recording_name이 없는 멤버는 기존대로 동작)

### Must NOT Have (Guardrails)
- 다른 source type (github, slack, notion, drive) 필터링 로직 변경 금지
- 성능에 큰 영향을 주는 추가 DB 쿼리 최소화

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: YES (pytest 존재)
- **User wants tests**: Manual-only (API 호출로 검증)
- **Framework**: curl/httpie

### Automated Verification

**For API changes** (using Bash curl):
```bash
# 1. Start backend server (if not running)
# 2. Test Zena + recordings filter
curl -s "http://localhost:8000/api/v1/activities?member_name=Zena&source_type=recordings&limit=5" | jq '.total, .activities[0].metadata.name'
# Expected: total > 0, recordings with Suah Kim as participant

# 3. Test Zena + recordings_daily filter  
curl -s "http://localhost:8000/api/v1/activities?member_name=Zena&source_type=recordings_daily&limit=5" | jq '.total, .activities[0].metadata.participants'
# Expected: total > 0, participants include Suah Kim
```

---

## TODOs

- [x] 1. recordings source 필터링 로직 수정 ✅ DONE

  **What to do**:
  1. `filter_member_name`이 주어지면 `members` 컬렉션에서 해당 멤버의 `recording_name` 조회
  2. `recording_name`이 존재하면 검색 조건에 추가 (OR 조건)
  3. `$regexMatch`의 regex 패턴을 `filter_member_name|recording_name` 형태로 변경
  4. Python fallback 로직도 동일하게 수정

  **Must NOT do**:
  - 다른 source type 로직 변경
  - 불필요한 추가 쿼리

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 2
  - **Blocked By**: None

  **References**:
  - `backend/api/v1/activities_mongo.py:765-895` - recordings source 필터링 로직
  - `backend/api/v1/activities_mongo.py:773-823` - 현재 participant 필터링 코드

  **Code Changes**:
  ```python
  # Line 773 이후, filter_member_name 블록 내부에 추가:
  
  # Get recording_name from members collection if exists
  search_names = [filter_member_name]
  member_doc = await db["members"].find_one(
      {"name": {"$regex": f"^{filter_member_name}$", "$options": "i"}}
  )
  if member_doc and member_doc.get("recording_name"):
      search_names.append(member_doc["recording_name"])
  
  # Build regex pattern for all search names (OR condition)
  search_pattern = "|".join(search_names)
  
  # 기존 participant_query의 regex를 filter_member_name에서 search_pattern으로 변경
  # Line 794: "regex": filter_member_name → "regex": search_pattern
  
  # Python fallback (line 815-823)도 수정:
  # filter_member_name.lower() in p.lower() 
  # → any(name.lower() in p.lower() for name in search_names)
  ```

  **Acceptance Criteria**:
  - [x] `recordings` source에서 Zena 필터 시 Suah Kim 참석 레코딩 반환 ✅
  - [x] recording_name이 없는 멤버는 기존대로 동작 ✅

  **Commit**: YES
  - Message: `fix(activities): include recording_name in recordings participant filter`
  - Files: `backend/api/v1/activities_mongo.py`

---

- [x] 2. recordings_daily source 필터링 로직 수정 ✅ DONE

  **What to do**:
  1. `filter_member_name`이 주어지면 `members` 컬렉션에서 해당 멤버의 `recording_name` 조회
  2. participant 필터링 시 `recording_name`도 함께 검색

  **Must NOT do**:
  - 다른 source type 로직 변경

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: None
  - **Blocked By**: Task 1

  **References**:
  - `backend/api/v1/activities_mongo.py:897-1019` - recordings_daily source 로직
  - `backend/api/v1/activities_mongo.py:949-964` - 현재 participant 필터링 코드

  **Code Changes**:
  ```python
  # Line 949 이전에 recording_name 조회 추가 (recordings source와 동일한 로직 재사용)
  # 또는 함수 시작 부분에서 한 번만 조회하여 변수에 저장
  
  # Line 949-964의 필터링 로직 수정:
  # 기존:
  # if not any(filter_member_name.lower() in name.lower() for name in participant_names):
  #     continue
  
  # 변경:
  # search_names = [filter_member_name]
  # if recording_name:  # 위에서 조회한 recording_name
  #     search_names.append(recording_name)
  # if not any(
  #     any(search.lower() in name.lower() for search in search_names)
  #     for name in participant_names
  # ):
  #     continue
  ```

  **Acceptance Criteria**:
  - [ ] `recordings_daily` source에서 Zena 필터 시 Suah Kim 참석 daily analysis 반환
  - [ ] recording_name이 없는 멤버는 기존대로 동작

  **Commit**: YES (grouped with Task 1)
  - Message: `fix(activities): include recording_name in recordings participant filter`
  - Files: `backend/api/v1/activities_mongo.py`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1, 2 | `fix(activities): include recording_name in recordings participant filter` | activities_mongo.py | curl API test |

---

## Success Criteria

### Verification Commands
```bash
# Backend가 실행 중인 상태에서:
curl -s "http://localhost:8000/api/v1/activities?member_name=Zena&source_type=recordings&limit=5" | jq '.total'
# Expected: > 0

curl -s "http://localhost:8000/api/v1/activities?member_name=Zena&source_type=recordings_daily&limit=5" | jq '.total'  
# Expected: > 0
```

### Final Checklist
- [ ] Zena + recordings 필터 작동
- [ ] Zena + recordings_daily 필터 작동
- [ ] 다른 멤버 필터링 기존대로 작동 (regression 없음)
- [ ] recording_name 없는 멤버 필터링 정상 작동
