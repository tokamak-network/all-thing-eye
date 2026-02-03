# GitHub Issue Automation - Local CLI Tool

## TL;DR

> **Quick Summary**: `data-not-showing` 이슈가 등록되면 로컬에서 스크립트를 실행하여 MongoDB를 진단하고, Claude AI로 수정안을 도출하여 Draft PR을 자동 생성하는 CLI 도구
> 
> **Deliverables**:
> - `scripts/handle_github_issue.py` - 메인 CLI 진입점
> - `scripts/issue_automation/` - 모듈화된 컴포넌트들 (parser, diagnosis, ai_fixer, pr_creator)
> - `tests/test_issue_automation/` - TDD 테스트 스위트
> 
> **Estimated Effort**: Medium (2-3 days)
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 5 → Task 6

---

## Context

### Original Request
GitHub 이슈가 등록됐을 때 자동으로 가져와서 해결할 수 있도록 자동화 - `data-not-showing` 템플릿 이슈에 대해 진단 + 코드 수정 + Draft PR 생성

### Interview Summary
**Key Discussions**:
- **Execution Environment**: 로컬 CLI (MongoDB 접근을 위해 - Atlas IP 화이트리스트 제한)
- **AI Engine**: Claude API (Anthropic) - 코드 이해력 우수
- **Fix Scope**: `member_identifiers` 컬렉션만 (safest approach)
- **Member Identification**: GitHub 이슈 작성자 → member_identifiers 매핑
- **Human Review**: Draft PR로 생성하여 리뷰 후 머지

**Research Findings**:
- `backend/graphql/activity_filters.py:22-54` - `get_member_identifiers()` 함수가 member_identifiers 조회 패턴 제공
- `scripts/daily_data_collection_mongo.py` - 기존 CLI 스크립트 패턴 (argparse, async, logging)
- `member_identifiers` 컬렉션 구조: `{member_name, source, identifier_value}`
- 기존 issue template은 member name 필드가 없음 → GitHub author로 추론

### Metis Review
**Identified Gaps** (addressed):
- Issue template에 member_name 필드 없음 → GitHub author username으로 member_identifiers 조회
- Backend API 인증 문제 → 로컬 실행으로 해결 (MongoDB 직접 접근)
- Claude가 임의 코드 수정 가능 → member_identifiers만 수정 가능하도록 제한
- 무한 PR 루프 위험 → `auto-diagnosed` 라벨로 중복 방지

---

## Work Objectives

### Core Objective
`data-not-showing` 이슈를 자동으로 진단하고, member_identifiers 누락인 경우 수정 스크립트를 생성하여 Draft PR로 제출하는 로컬 CLI 도구 개발

### Concrete Deliverables
- `scripts/handle_github_issue.py` - 메인 CLI
- `scripts/issue_automation/__init__.py`
- `scripts/issue_automation/parser.py` - 이슈 본문 파싱
- `scripts/issue_automation/diagnosis.py` - MongoDB 진단
- `scripts/issue_automation/ai_fixer.py` - Claude 연동
- `scripts/issue_automation/pr_creator.py` - PR 생성
- `tests/test_issue_automation/test_parser.py`
- `tests/test_issue_automation/test_diagnosis.py`
- `tests/test_issue_automation/test_ai_fixer.py`

### Definition of Done
- [ ] `python scripts/handle_github_issue.py --help` 실행 시 usage 출력
- [ ] `--issue-number` 옵션으로 특정 이슈 처리 가능
- [ ] `--dry-run` 옵션으로 실제 PR 생성 없이 진단만 가능
- [ ] 모든 테스트 통과: `pytest tests/test_issue_automation/ -v`

### Must Have
- GitHub API로 이슈 조회 (`gh` CLI 또는 PyGithub)
- MongoDB 직접 조회 (member_identifiers, activities)
- Claude API 연동 (진단 결과 분석)
- Draft PR 자동 생성 (`gh pr create --draft`)
- 이슈에 진단 결과 코멘트

### Must NOT Have (Guardrails)
- ❌ GitHub Actions 실행 (MongoDB 접근 불가)
- ❌ 백엔드 코드 (`.py`) 자동 수정 - member_identifiers만
- ❌ 자동 머지 (Draft PR만 생성)
- ❌ 여러 이슈 동시 처리 (1 이슈 = 1 실행)
- ❌ Slack 알림 연동 (future enhancement)
- ❌ 스케줄링/cron 자동 실행 (수동 실행만)

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: YES (pytest 있음)
- **User wants tests**: TDD
- **Framework**: pytest

### TDD Workflow

Each TODO follows RED-GREEN-REFACTOR:
1. **RED**: Write failing test first
2. **GREEN**: Implement minimum code to pass
3. **REFACTOR**: Clean up while keeping green

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately):
├── Task 1: Issue Parser (no dependencies)
└── Task 4: Tests setup (no dependencies)

Wave 2 (After Wave 1):
├── Task 2: Diagnosis Module (depends: 1)
└── Task 3: AI Fixer Module (depends: 1)

Wave 3 (After Wave 2):
└── Task 5: PR Creator + Main CLI (depends: 2, 3)

Wave 4 (After Wave 3):
└── Task 6: Integration Testing (depends: 5)

Critical Path: Task 1 → Task 2 → Task 5 → Task 6
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 2, 3 | 4 |
| 2 | 1 | 5 | 3 |
| 3 | 1 | 5 | 2 |
| 4 | None | None | 1 |
| 5 | 2, 3 | 6 | None |
| 6 | 5 | None | None |

---

## TODOs

### - [x] 1. Issue Parser Module

**What to do**:
- GitHub API로 이슈 조회 (gh CLI 사용)
- Issue body 파싱하여 구조화된 데이터 추출
- GitHub author username 추출
- 테스트 먼저 작성 (TDD)

**Must NOT do**:
- API rate limit 무시
- author가 없는 경우 처리 안함

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: 단일 모듈, 명확한 스펙, 외부 라이브러리 사용 최소화
- **Skills**: [`git-master`]
  - `git-master`: 커밋 생성에 필요

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Task 4)
- **Blocks**: Tasks 2, 3
- **Blocked By**: None

**References**:

**Pattern References**:
- `scripts/daily_data_collection_mongo.py:1-45` - CLI 스크립트 패턴 (argparse, path setup, imports)
- `.github/ISSUE_TEMPLATE/data-not-showing.yml` - 파싱해야 할 이슈 템플릿 구조

**API References**:
- GitHub CLI: `gh issue view <number> --json body,author,labels`

**Test References**:
- `tests/test_github_plugin.py` - 기존 테스트 패턴

**Acceptance Criteria**:

```bash
# RED Phase: Create test first
# File: tests/test_issue_automation/test_parser.py
# Test: test_parse_issue_body_extracts_data_source
pytest tests/test_issue_automation/test_parser.py::test_parse_issue_body_extracts_data_source -v
# Assert: FAIL (module doesn't exist yet)

# GREEN Phase: Implement
# After implementation:
pytest tests/test_issue_automation/test_parser.py -v
# Assert: PASS (3+ tests)

# Verification:
python -c "from scripts.issue_automation.parser import IssueParser; print('OK')"
# Assert: Output contains "OK"
```

**Commit**: YES
- Message: `feat(issue-automation): add issue parser module with tests`
- Files: `scripts/issue_automation/parser.py`, `tests/test_issue_automation/test_parser.py`

---

### - [x] 2. Diagnosis Module (MongoDB)

**What to do**:
- MongoDB 연결 (기존 MongoDBManager 사용)
- GitHub author → member_identifiers 조회
- 활동 컬렉션 조회 (github_commits, slack_messages 등)
- 진단 결과를 구조화된 형태로 반환
- 테스트 먼저 작성 (TDD, mock MongoDB)

**Must NOT do**:
- Production DB 직접 수정
- 비동기 처리 무시 (async/await 사용)

**Recommended Agent Profile**:
- **Category**: `unspecified-low`
  - Reason: MongoDB 쿼리 패턴이 이미 존재, 따라하면 됨
- **Skills**: [`git-master`]

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 2 (with Task 3)
- **Blocks**: Task 5
- **Blocked By**: Task 1

**References**:

**Pattern References**:
- `backend/graphql/activity_filters.py:22-54` - `get_member_identifiers()` 함수 - member_identifiers 조회 패턴
- `backend/graphql/activity_filters.py:57-77` - `build_identifier_mapping()` 함수 - 전체 매핑 조회
- `src/core/mongo_manager.py:296` - MongoDBManager의 identifiers 컬렉션 접근

**API/Type References**:
- `member_identifiers` 컬렉션 구조: `{member_name: str, source: str, identifier_value: str}`
- `github_commits` 컬렉션: `{author_name: str, date: datetime, ...}`
- `slack_messages` 컬렉션: `{user_id: str, posted_at: datetime, ...}`

**Test References**:
- `tests/test_notion_plugin.py:58-80` - 테스트용 DB 모킹 패턴

**Acceptance Criteria**:

```bash
# RED Phase
pytest tests/test_issue_automation/test_diagnosis.py::test_find_member_by_github_username -v
# Assert: FAIL

# GREEN Phase
pytest tests/test_issue_automation/test_diagnosis.py -v
# Assert: PASS (4+ tests)

# Verification (requires local MongoDB connection):
python -c "
import asyncio
from scripts.issue_automation.diagnosis import IssueDiagnoser
async def test():
    d = IssueDiagnoser()
    result = await d.diagnose_by_github_author('SonYoungsung')
    print('member_found:', result.get('member_found', False))
asyncio.run(test())
"
# Assert: Output shows "member_found: True" or "member_found: False"
```

**Commit**: YES
- Message: `feat(issue-automation): add diagnosis module for MongoDB queries`
- Files: `scripts/issue_automation/diagnosis.py`, `tests/test_issue_automation/test_diagnosis.py`

---

### - [x] 3. AI Fixer Module (Claude Integration)

**What to do**:
- Claude API 연동 (anthropic 패키지)
- 진단 결과를 Claude에게 전달
- Claude 응답 파싱하여 수정 액션 추출
- member_identifiers insert 스크립트 생성
- 테스트 먼저 작성 (TDD, mock Claude API)

**Must NOT do**:
- API 키를 코드에 하드코딩
- Claude가 제안한 임의 코드 수정 적용 (member_identifiers만)
- Rate limit 무시

**Recommended Agent Profile**:
- **Category**: `unspecified-low`
  - Reason: Claude API 연동은 표준 패턴
- **Skills**: [`git-master`]

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 2 (with Task 2)
- **Blocks**: Task 5
- **Blocked By**: Task 1

**References**:

**Pattern References**:
- `backend/api/v1/mcp_agent.py:303-445` - 기존 AI API 연동 패턴 (httpx, tool-based agent)
- `.env` 또는 환경변수에서 `ANTHROPIC_API_KEY` 사용

**External References**:
- Anthropic Python SDK: https://docs.anthropic.com/en/api/client-sdks

**Acceptance Criteria**:

```bash
# RED Phase
pytest tests/test_issue_automation/test_ai_fixer.py::test_generate_fix_for_missing_identifier -v
# Assert: FAIL

# GREEN Phase
pytest tests/test_issue_automation/test_ai_fixer.py -v
# Assert: PASS (3+ tests)

# Verification (requires ANTHROPIC_API_KEY):
python -c "
from scripts.issue_automation.ai_fixer import AIFixer
fixer = AIFixer()
print('initialized:', fixer is not None)
"
# Assert: Output shows "initialized: True"
```

**Commit**: YES
- Message: `feat(issue-automation): add Claude AI fixer module`
- Files: `scripts/issue_automation/ai_fixer.py`, `tests/test_issue_automation/test_ai_fixer.py`

---

### - [x] 4. Test Infrastructure Setup

**What to do**:
- `tests/test_issue_automation/` 디렉토리 생성
- `conftest.py` with fixtures (mock MongoDB, mock Claude)
- pytest 설정 확인

**Must NOT do**:
- 실제 API 호출 (mock 사용)

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: 디렉토리 생성 및 기본 설정만
- **Skills**: [`git-master`]

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Task 1)
- **Blocks**: None (다른 태스크들이 이것 없이도 테스트 작성 가능)
- **Blocked By**: None

**References**:

**Pattern References**:
- `tests/conftest.py` - 기존 conftest 패턴 (있다면)
- `tests/test_github_plugin.py` - 기존 테스트 패턴

**Acceptance Criteria**:

```bash
# Verification:
ls tests/test_issue_automation/
# Assert: Shows __init__.py, conftest.py

pytest tests/test_issue_automation/ --collect-only
# Assert: Shows collected tests (after other tasks add them)
```

**Commit**: YES (groups with Task 1)
- Message: `test(issue-automation): setup test infrastructure`
- Files: `tests/test_issue_automation/__init__.py`, `tests/test_issue_automation/conftest.py`

---

### - [ ] 5. PR Creator + Main CLI

**What to do**:
- Git branch 생성 (`fix/issue-{N}-data-not-showing`)
- MongoDB 수정 스크립트를 파일로 저장
- `gh pr create --draft` 실행
- 이슈에 진단 결과 코멘트 (`gh issue comment`)
- 메인 CLI 통합 (`handle_github_issue.py`)
- argparse로 옵션 처리 (`--issue-number`, `--dry-run`, `--all-open`)

**Must NOT do**:
- 자동 머지 (Draft만)
- main 브랜치 직접 수정
- 이미 `auto-diagnosed` 라벨이 있는 이슈 재처리

**Recommended Agent Profile**:
- **Category**: `unspecified-high`
  - Reason: 여러 모듈 통합, git/gh 명령어 조합
- **Skills**: [`git-master`]
  - `git-master`: 브랜치 생성, PR 생성에 필수

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Wave 3 (Sequential)
- **Blocks**: Task 6
- **Blocked By**: Tasks 2, 3

**References**:

**Pattern References**:
- `scripts/daily_data_collection_mongo.py:1-45` - CLI 진입점 패턴 (argparse, main)

**External References**:
- `gh pr create --draft --title "..." --body "..."`
- `gh issue comment <number> --body "..."`
- `gh issue edit <number> --add-label "auto-diagnosed"`

**Acceptance Criteria**:

```bash
# CLI help 확인:
python scripts/handle_github_issue.py --help
# Assert: Shows usage with --issue-number, --dry-run, --all-open options

# Dry run 테스트 (실제 PR 생성 안함):
python scripts/handle_github_issue.py --issue-number 999 --dry-run 2>&1 | head -20
# Assert: Shows diagnosis output without creating PR

# Unit tests:
pytest tests/test_issue_automation/test_pr_creator.py -v
# Assert: PASS
```

**Commit**: YES
- Message: `feat(issue-automation): add PR creator and main CLI entry point`
- Files: `scripts/handle_github_issue.py`, `scripts/issue_automation/pr_creator.py`, `tests/test_issue_automation/test_pr_creator.py`

---

### - [ ] 6. Integration Testing & Documentation

**What to do**:
- End-to-end 테스트 (mock 환경)
- README 또는 docstring에 사용법 문서화
- 실제 테스트 이슈로 전체 flow 검증 (optional)

**Must NOT do**:
- 문서만 작성하고 테스트 skip

**Recommended Agent Profile**:
- **Category**: `writing`
  - Reason: 문서화 + 통합 테스트 검증
- **Skills**: [`git-master`]

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Wave 4 (Final)
- **Blocks**: None
- **Blocked By**: Task 5

**References**:

**Pattern References**:
- `scripts/daily_data_collection_mongo.py:1-15` - 스크립트 docstring 패턴
- `README.md` - 프로젝트 문서 스타일

**Acceptance Criteria**:

```bash
# All tests pass:
pytest tests/test_issue_automation/ -v
# Assert: All tests PASS

# Integration test (with mock):
pytest tests/test_issue_automation/test_integration.py -v
# Assert: PASS

# Documentation check:
python scripts/handle_github_issue.py --help | grep -E "(issue-number|dry-run|all-open)"
# Assert: All options documented
```

**Commit**: YES
- Message: `docs(issue-automation): add integration tests and usage documentation`
- Files: `tests/test_issue_automation/test_integration.py`, updated docstrings

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 + 4 | `feat(issue-automation): add issue parser module with tests` | parser.py, test_parser.py, conftest.py | pytest |
| 2 | `feat(issue-automation): add diagnosis module for MongoDB queries` | diagnosis.py, test_diagnosis.py | pytest |
| 3 | `feat(issue-automation): add Claude AI fixer module` | ai_fixer.py, test_ai_fixer.py | pytest |
| 5 | `feat(issue-automation): add PR creator and main CLI entry point` | handle_github_issue.py, pr_creator.py, test_pr_creator.py | pytest + CLI |
| 6 | `docs(issue-automation): add integration tests and documentation` | test_integration.py, docstrings | pytest |

---

## Success Criteria

### Verification Commands
```bash
# All tests pass
pytest tests/test_issue_automation/ -v --tb=short
# Expected: All tests PASS

# CLI works
python scripts/handle_github_issue.py --help
# Expected: Shows usage

# Dry run works (requires GitHub CLI login)
python scripts/handle_github_issue.py --issue-number 1 --dry-run
# Expected: Shows diagnosis without creating PR
```

### Final Checklist
- [ ] All "Must Have" features implemented
- [ ] All "Must NOT Have" guardrails respected
- [ ] All tests pass
- [ ] CLI help shows all options
- [ ] Dry run mode works without side effects
