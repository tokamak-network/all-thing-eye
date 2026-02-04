# Weekly GitHub Catch-up Script

## TL;DR

> **Quick Summary**: 뒤늦게 푸쉬된 GitHub 커밋을 잡기 위한 주간 보정 스크립트 생성
> 
> **Deliverables**:
> - `scripts/weekly_github_catchup.py` - 주간 보정 스크립트
> - crontab 설정 가이드
> 
> **Estimated Effort**: Quick
> **Parallel Execution**: NO - sequential

---

## Context

### Original Request
뒤늦게 푸쉬된 커밋(예: 3일 전에 커밋하고 오늘 푸쉬)이 daily collector에서 누락되는 문제 해결

### Problem Analysis
- GitHub API의 `since` 파라미터는 `committedDate` 기준으로 필터링
- Daily collector는 "어제" 날짜만 수집
- 커밋 후 며칠 뒤에 푸쉬하면 해당 커밋이 누락됨

### Solution
일주일에 한 번 지난 7일간의 GitHub 데이터를 다시 수집하는 catch-up 스크립트

---

## TODOs

- [ ] 1. Create weekly_github_catchup.py script

  **What to do**:
  - `scripts/weekly_github_catchup.py` 파일 생성
  - 기본 7일 lookback, `--days` 옵션으로 조정 가능
  - `--dry-run` 옵션 지원
  - 기존 `daily_data_collection_mongo.py`의 GitHub 수집 로직 재사용
  - 실행 결과 요약 출력 (수집된 commits, PRs, issues 수)

  **Must NOT do**:
  - 다른 소스(Slack, Notion 등)는 포함하지 않음 - GitHub만
  - 기존 daily collector 수정하지 않음

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **References**:
  - `scripts/daily_data_collection_mongo.py` - 기존 수집 스크립트 패턴
  - `src/plugins/github_plugin_mongo.py` - GitHub 플러그인

  **Acceptance Criteria**:
  ```bash
  # 스크립트 실행 테스트
  cd /Users/son-yeongseong/Desktop/dev/all-thing-eye
  python scripts/weekly_github_catchup.py --dry-run
  # Expected: "DRY RUN" 메시지와 수집 기간 출력
  
  python scripts/weekly_github_catchup.py --help
  # Expected: --days, --dry-run 옵션 설명 표시
  ```

  **Commit**: YES
  - Message: `feat(scripts): add weekly github catch-up for late-pushed commits`
  - Files: `scripts/weekly_github_catchup.py`

---

- [ ] 2. Update documentation with cron setup guide

  **What to do**:
  - CLAUDE.md 또는 README에 crontab 설정 가이드 추가
  - 권장: 매주 일요일 새벽 2시 KST 실행
  
  **Crontab example**:
  ```
  # Weekly GitHub catch-up (Sunday 2 AM KST)
  0 2 * * 0 cd /home/ubuntu/all-thing-eye && docker exec all-thing-eye-backend python scripts/weekly_github_catchup.py >> /var/log/ati-weekly-catchup.log 2>&1
  ```

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Acceptance Criteria**:
  - CLAUDE.md에 "Weekly Catch-up" 섹션 추가됨
  - crontab 명령어 예시 포함

  **Commit**: YES
  - Message: `docs: add weekly github catch-up cron setup guide`

---

## Success Criteria

### Verification Commands
```bash
# 스크립트 존재 확인
ls -la scripts/weekly_github_catchup.py

# 도움말 출력
python scripts/weekly_github_catchup.py --help

# Dry run 테스트
python scripts/weekly_github_catchup.py --dry-run --days 3
```

### Final Checklist
- [ ] `scripts/weekly_github_catchup.py` 생성됨
- [ ] `--days`, `--dry-run` 옵션 작동
- [ ] 문서에 cron 설정 가이드 추가
