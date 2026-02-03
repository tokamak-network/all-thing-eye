# GitHub Issue Automation

`data-not-showing` 이슈를 자동으로 진단하고 수정안을 제안하는 CLI 도구입니다.

## 개요

팀 멤버가 "내 활동이 보이지 않습니다" 이슈를 등록하면, 이 도구가:
1. 이슈 본문을 파싱하여 영향받는 데이터 소스 파악
2. MongoDB에서 멤버 식별자 및 활동 데이터 조회
3. 문제 원인 진단 (예: 누락된 identifier 매핑)
4. 자동 진단 리포트를 이슈에 코멘트
5. 필요시 Draft PR 생성

## 사전 요구사항

### 환경 변수

프로젝트 `.env` 파일에 다음 변수가 설정되어 있어야 합니다:

```bash
# MongoDB 연결 (필수)
MONGODB_URI=mongodb://...

# AI API (선택 - Claude 분석 기능 사용시)
AI_API_KEY=sk-...
AI_API_URL=https://api.ai.tokamak.network
```

### GitHub CLI

`gh` CLI가 설치되어 있고 인증되어 있어야 합니다:

```bash
# 설치 확인
gh --version

# 인증 확인
gh auth status

# 인증 안 되어 있으면
gh auth login
```

## 사용법

### 기본 명령어

```bash
# 특정 이슈 처리
python scripts/handle_github_issue.py --issue-number <이슈번호>

# 또는 단축 옵션
python scripts/handle_github_issue.py -n <이슈번호>
```

### Dry Run 모드 (권장: 첫 사용시)

실제 변경 없이 진단 결과만 확인:

```bash
python scripts/handle_github_issue.py --issue-number 123 --dry-run
```

Dry run 모드에서는:
- ✅ 이슈 조회 및 파싱
- ✅ MongoDB 진단
- ✅ 진단 리포트 생성 (출력만)
- ❌ 이슈 코멘트 작성 안 함
- ❌ PR 생성 안 함
- ❌ 라벨 추가 안 함

### 실제 실행

```bash
# 이슈 #42 처리 (실제로 코멘트, PR 생성)
python scripts/handle_github_issue.py --issue-number 42
```

## 실행 흐름

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Fetching issue...                                   │
│   - GitHub API로 이슈 본문, 작성자, 라벨 조회               │
│   - 이미 'auto-diagnosed' 라벨이 있으면 스킵                │
├─────────────────────────────────────────────────────────────┤
│ Step 2: Running diagnosis...                                │
│   - 이슈 작성자의 GitHub username으로 member_identifiers 조회│
│   - 해당 멤버의 활동 데이터 존재 여부 확인                   │
├─────────────────────────────────────────────────────────────┤
│ Step 3: Generating fix...                                   │
│   - 문제 원인 분석 (누락된 identifier, 빈 활동 등)          │
│   - 자동 진단 리포트 생성                                   │
├─────────────────────────────────────────────────────────────┤
│ Step 4: Creating Draft PR (if actionable fix exists)        │
│   - fix/issue-{N}-data-not-showing 브랜치 생성              │
│   - MongoDB 수정 스크립트 저장                              │
│   - Draft PR 생성                                           │
├─────────────────────────────────────────────────────────────┤
│ Step 5: Commenting on issue                                 │
│   - 진단 리포트를 이슈에 코멘트로 게시                      │
├─────────────────────────────────────────────────────────────┤
│ Step 6: Adding 'auto-diagnosed' label                       │
│   - 재처리 방지를 위해 라벨 추가                            │
└─────────────────────────────────────────────────────────────┘
```

## 예시 출력

### Dry Run 예시

```
$ python scripts/handle_github_issue.py -n 123 --dry-run

*** DRY RUN MODE - No changes will be made ***

============================================================
Processing Issue #123
============================================================

Step 1: Fetching issue...
  Author: john-doe
  Data sources: ['GitHub', 'Slack']
  Date range: Jan 28 - Feb 3, 2026

Step 2: Running diagnosis...
  Member found: True
  Member name: John Doe
  Identifiers: {'github': ['john-doe'], 'slack': ['U12345678']}
  Activities: {'GitHub': 15, 'Slack': 42}
  Issues: []

Step 3: Generating fix...
  Summary: Member: John Doe; GitHub: 15 activities found; Slack: 42 activities found
  Actions: ['no_action']

Step 4: No PR needed (no actionable fix)

Step 5: Commenting on issue...
[DRY RUN] Would comment on issue #123:
## Automated Diagnosis Report
...

Step 6: Adding 'auto-diagnosed' label...
[DRY RUN] Would add label 'auto-diagnosed' to issue #123

============================================================
Issue #123 processing complete!
============================================================
```

### 멤버를 찾지 못한 경우

```
Step 2: Running diagnosis...
  Member found: False
  Issues: ["No member found with GitHub username 'unknown-user'"]

Step 3: Generating fix...
  Summary: Member not found for GitHub user 'unknown-user'
  Actions: ['manual_check']
```

## 진단 리포트 형식

이슈에 게시되는 코멘트 예시:

```markdown
## Automated Diagnosis Report

**Member identified:** John Doe
**GitHub username:** john-doe

**Registered identifiers:**
- github: john-doe
- slack: U12345678

**Activity check (last 30 days):**
- GitHub: 15 activities found [+]
- Slack: 42 activities found [+]

**Suggested actions:**
- [-] No automated fix needed - data may need manual investigation

---
*This report was generated automatically by issue-automation.*
```

## 문제 해결

### "gh: command not found"

GitHub CLI 설치 필요:
```bash
# macOS
brew install gh

# Ubuntu
sudo apt install gh
```

### "Error fetching issue"

1. `gh auth status`로 인증 확인
2. 이슈 번호가 올바른지 확인
3. 레포지토리 접근 권한 확인

### "Error during diagnosis"

1. `.env` 파일에 `MONGODB_URI` 설정 확인
2. MongoDB Atlas IP 화이트리스트에 현재 IP 추가 확인
3. 네트워크 연결 확인

### 이슈가 이미 처리됨

`auto-diagnosed` 라벨이 있는 이슈는 재처리하지 않습니다.
재처리하려면 이슈에서 해당 라벨을 먼저 제거하세요.

## 모듈 구조

```
scripts/
├── handle_github_issue.py    # 메인 CLI 진입점
└── issue_automation/
    ├── __init__.py           # 패키지 exports
    ├── parser.py             # 이슈 본문 파싱 (IssueParser)
    ├── diagnosis.py          # MongoDB 진단 (IssueDiagnoser)
    ├── ai_fixer.py           # AI 기반 수정안 생성 (AIFixer)
    └── pr_creator.py         # Git/GitHub 작업 (PRCreator)
```

## API 사용 (프로그래매틱)

CLI 외에 Python에서 직접 모듈을 사용할 수도 있습니다:

```python
from scripts.issue_automation import (
    IssueParser, 
    IssueDiagnoser, 
    AIFixer, 
    PRCreator
)

# 이슈 파싱
parser = IssueParser()
issue_data = parser.fetch_issue(123)
parsed = parser.parse_issue_body(issue_data["body"])
author = parser.get_author_username(issue_data)

# 진단
diagnoser = IssueDiagnoser()
diagnosis = diagnoser.diagnose_by_github_author(
    author,
    sources=parsed.data_sources,
    date_range_str=parsed.date_range
)

# 수정안 생성
fixer = AIFixer()
fix_result = fixer.generate_fix_without_ai(diagnosis)

# PR 생성 (dry_run=True로 테스트)
pr_creator = PRCreator(dry_run=True)
pr_creator.add_issue_comment(123, fix_result.comment_body)
```
