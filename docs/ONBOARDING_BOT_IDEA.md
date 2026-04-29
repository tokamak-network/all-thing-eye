# Member Onboarding Checklist Bot

Status: **Idea** | Created: 2026-02-10

## Overview

새 멤버가 추가되면 Slack DM으로 온보딩 체크리스트를 자동 전송하고, 진행 상황을 트래킹하는 봇.
관리자에게는 신규 멤버의 셋업 완료율을 리포트.

## Problem

- 신규 멤버 합류 시 GitHub org 초대, Slack 채널 가입, Notion 접근 등 수동 안내 필요
- 누락되는 항목이 생기면 데이터 수집에서 해당 멤버가 빠짐
- `member_identifiers` 미등록으로 활동이 "Unknown"으로 표시되는 문제 반복

## Core Features

### 1. 자동 체크리스트 DM
멤버가 `members` 컬렉션에 추가되면 봇이 Slack DM으로 체크리스트 전송:

```
Welcome to Tokamak Network!

Please complete the following setup:
[ ] GitHub - Accept org invitation (tokamak-network)
[ ] Slack - Join required channels (#general, #dev, ...)
[ ] Notion - Verify workspace access
[ ] Google Drive - Verify shared drive access
[ ] Admin page - Confirm your identifiers are linked
```

### 2. 자동 검증 (가능한 항목)
- **GitHub**: GitHub API로 org membership 확인
- **Slack**: `member_identifiers`에 slack source 등록 여부 확인
- **Notion**: Notion API로 user 목록 조회
- **Identifiers**: `member_identifiers` 컬렉션에서 해당 멤버의 등록 현황 체크

### 3. 관리자 리포트
- 주기적으로 미완료 체크리스트 현황을 관리자에게 DM 또는 채널에 공유
- 7일 이상 미완료 시 리마인더 발송

## Data Model

### MongoDB Collection: `onboarding_checklists`

```json
{
  "_id": ObjectId,
  "member_id": "ObjectId string",
  "member_name": "string",
  "slack_user_id": "string",
  "items": [
    {
      "key": "github_org",
      "label": "GitHub org membership",
      "completed": false,
      "completed_at": null,
      "auto_verified": true
    },
    {
      "key": "slack_channels",
      "label": "Join required Slack channels",
      "completed": false,
      "completed_at": null,
      "auto_verified": false
    }
  ],
  "started_at": "datetime",
  "completed_at": null,
  "reminder_count": 0,
  "last_reminder_at": null
}
```

## Architecture

- **Trigger**: `members` 컬렉션 변경 감지 (polling 또는 Change Stream)
- **Bot**: 기존 `All-Thing-Eye Scheduler` 봇에 기능 추가 or 별도 스크립트
- **Frontend**: Tools > Onboarding 페이지에서 체크리스트 현황 조회/관리
- **Slack Scopes**: 추가 필요 없음 (DM 전송은 기존 scope로 가능)

## Checklist Items (Draft)

| Key | Label | Auto-verify | Method |
|-----|-------|-------------|--------|
| `github_org` | GitHub org 멤버십 | Yes | GitHub API `orgs/{org}/members` |
| `github_identifier` | GitHub ID 등록 | Yes | `member_identifiers` 조회 |
| `slack_identifier` | Slack ID 등록 | Yes | `member_identifiers` 조회 |
| `slack_channels` | 필수 채널 가입 | Partial | `conversations.members` API |
| `notion_access` | Notion 접근 확인 | Manual | 본인 확인 후 체크 |
| `drive_access` | Google Drive 접근 | Manual | 본인 확인 후 체크 |

## Existing Infrastructure to Leverage

- `members` collection - 멤버 정보
- `member_identifiers` collection - 플랫폼 ID 매핑
- `weekly_output_bot.py` - APScheduler + Slack DM 패턴 재활용
- `weekly_output_schedules` API - CRUD 패턴 재활용
- Tools UI framework - 기존 Weekly Output 페이지 구조 재활용

## Open Questions

- [ ] Change Stream vs polling으로 신규 멤버 감지?
- [ ] 체크리스트 항목을 프로젝트별로 커스텀 가능하게 할 것인지?
- [ ] 기존 Scheduler 봇에 합칠 것인지, 별도 봇으로 만들 것인지?
- [ ] 리마인더 주기 (3일? 7일?)
