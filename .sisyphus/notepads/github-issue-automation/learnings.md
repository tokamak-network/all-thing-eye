# Learnings - GitHub Issue Automation

## Session ses_3de29b486ffeISylO4e61s0i0I (2026-02-03)

### Initial Context
- Plan: github-issue-automation
- Goal: `data-not-showing` 이슈 자동 진단 + Claude AI로 수정안 도출 + Draft PR 생성
- Execution: 로컬 CLI (MongoDB Atlas IP 화이트리스트 제한으로 GitHub Actions 불가)

### Key Patterns Discovered
- `backend/graphql/activity_filters.py:22-54` - `get_member_identifiers()` 함수
- `scripts/daily_data_collection_mongo.py:1-45` - CLI 스크립트 패턴
- `member_identifiers` 컬렉션 구조: `{member_name, source, identifier_value}`
