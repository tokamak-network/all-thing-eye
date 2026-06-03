# All-Thing-Eye Project Reference

팀 멤버 활동 분석 데이터 파이프라인 시스템. Slack, GitHub, Notion, Google Drive 등 다양한 소스에서 데이터를 수집하고 AI 기반 분석을 제공.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| Backend | FastAPI (Python 3.11+), GraphQL (Strawberry) |
| Database | MongoDB (Atlas) |
| AI | Tokamak AI API (qwen3-235b), Anthropic Claude |
| Infra | AWS EC2, Docker, Nginx |

## Directory Structure

```
all-thing-eye/
├── backend/                 # FastAPI 백엔드
│   ├── api/v1/             # REST API 엔드포인트
│   │   ├── activities_mongo.py   # 활동 조회 API
│   │   ├── exports_mongo.py      # CSV/JSON 내보내기
│   │   ├── members_mongo.py      # 멤버 관리
│   │   ├── projects_management.py # 프로젝트 & Grant Reports
│   │   ├── mcp_agent.py          # AI 에이전트
│   │   └── slack_bot.py          # Slack 봇
│   ├── graphql/            # GraphQL 스키마 & 리졸버
│   │   └── queries.py      # 메인 GraphQL 쿼리
│   └── main.py             # FastAPI 앱 진입점
├── frontend/               # Next.js 프론트엔드
│   └── src/
│       ├── app/            # App Router 페이지
│       │   ├── activities/ # 활동 목록 페이지
│       │   ├── members/    # 멤버 관리 페이지
│       │   ├── projects/   # 프로젝트 상세 페이지
│       │   └── admin/      # 관리자 페이지
│       ├── components/     # React 컴포넌트
│       ├── graphql/        # GraphQL 쿼리 & 타입
│       └── lib/            # API 클라이언트, 유틸리티
├── src/                    # 코어 라이브러리
│   ├── core/               # 설정, MongoDB 매니저
│   ├── plugins/            # 데이터 수집 플러그인
│   │   ├── slack_plugin_mongo.py
│   │   ├── github_plugin_mongo.py
│   │   ├── notion_plugin_mongo.py
│   │   └── google_drive_plugin_mongo.py
│   └── scheduler/          # 스케줄러 (Slack 봇)
├── scripts/                # 유틸리티 스크립트
│   └── daily_data_collection_mongo.py  # 일일 데이터 수집
├── docs/                   # 문서
│   └── ai-reference/       # AI 참조 문서
└── config/                 # 설정 파일
```

## Database (MongoDB)

**Connection:** `MONGODB_URI` 환경변수 사용, DB명: `ati`

### Core Collections

| Collection | Description | Key Fields |
|------------|-------------|------------|
| `members` | 팀 멤버 정보 | name, email, role, projects |
| `member_identifiers` | 플랫폼 ID 매핑 | member_id, identifier_type, identifier_value |
| `projects` | 프로젝트 설정 | key, name, member_ids, grant_reports, milestones |

### Activity Collections

| Collection | Description | Date Field |
|------------|-------------|------------|
| `github_commits` | GitHub 커밋 | `date` |
| `github_pull_requests` | PR | `created_at` |
| `github_issues` | 이슈 | `created_at` |
| `slack_messages` | Slack 메시지 | `posted_at` |
| `notion_pages` | Notion 페이지 | `last_edited_time` |
| `drive_activities` | Drive 활동 | `time` |

### Member Name Resolution

활동 데이터의 사용자를 멤버 이름으로 매핑:
1. `github_commits.author_name` → GitHub username
2. `member_identifiers`에서 `identifier_type='github'`, `identifier_value=username` 조회
3. `members._id`로 멤버 이름 조회

## API Endpoints

### REST API (FastAPI)

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/members` | 멤버 목록 |
| `GET /api/v1/activities` | 활동 목록 |
| `GET /api/v1/projects-management/projects` | 프로젝트 목록 |
| `GET /api/v1/projects-management/projects/{key}` | 프로젝트 상세 |
| `GET /api/v1/exports/activities` | 활동 CSV/JSON 내보내기 |
| `POST /api/v1/mcp-agent/run` | AI 에이전트 실행 |

### GraphQL

```graphql
# 활동 조회
query GetActivities($limit: Int, $projectKey: String) {
  activities(limit: $limit, projectKey: $projectKey) {
    memberName
    sourceType
    activityType
    timestamp
  }
}

# 프로젝트 조회
query GetProjects {
  projects {
    key
    name
    memberCount
  }
}
```

## Environment Variables

```bash
# MongoDB
MONGODB_URI=mongodb://user:pass@host:27017/db?authSource=db
MONGODB_DATABASE=ati

# Slack
SLACK_BOT_TOKEN=xoxb-...

# GitHub
GITHUB_TOKEN=ghp_...
GITHUB_ORG=tokamak-network

# AI
AI_API_KEY=sk-...
AI_API_URL=https://api.ai.tokamak.network
AI_MODEL=qwen3-235b

# JWT Auth
JWT_SECRET_KEY=your-secret-key

# Admin (지갑 주소 화이트리스트, comma-separated) - report distribution 등 admin 게이트
ADMIN_ADDRESSES=0x...,0x...

# AWS (S3 리포트 업로드 + SES 이메일 발송 - Report Distribution)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=ap-northeast-2
SENDER_EMAIL_ADDRESS=hello@tokamak.network   # SES 검증된 발신자
S3_REPORTS_BUCKET=tokamak-reports            # 백업용 S3_BACKUP_BUCKET과 분리
```

## Development Commands

```bash
# Backend (FastAPI)
cd backend && uvicorn main:app --reload --port 8000

# Frontend (Next.js)
cd frontend && npm run dev

# Data Collection (manual)
python scripts/daily_data_collection_mongo.py

# Docker
docker-compose up -d
```

## Scheduled Tasks (Cron)

### Data Collection (Every 4 Hours)
4시간 주기(KST)로 데이터 수집 (0시, 4시, 8시, 12시, 16시, 20시):
```bash
# AWS EC2 crontab
0 0,4,8,12,16,20 * * * docker exec all-thing-eye-backend python scripts/daily_data_collection_mongo.py
```

### Weekly GitHub Catch-up
뒤늦게 푸쉬된 커밋을 잡기 위해 매주 일요일 새벽 2시(KST)에 지난 7일 데이터 재수집:
```bash
# AWS EC2 crontab
0 2 * * 0 docker exec all-thing-eye-backend python scripts/weekly_github_catchup.py
```

**왜 필요한가?**: 커밋을 만들고 며칠 뒤에 푸쉬하면, daily collector가 놓칠 수 있음 (GitHub API가 `committedDate` 기준으로 필터링하기 때문)

## Key Patterns

### 프로젝트 필터링
프로젝트로 활동을 필터링할 때:
1. `projects.member_ids`에서 해당 프로젝트의 멤버 ID 목록 조회
2. `members`에서 멤버 이름 조회
3. 활동의 `member_name`이 해당 목록에 있는지 확인

### Grant Reports
프로젝트의 분기별 그란트 리포트:
- Google Drive에서 PDF 다운로드
- AI로 요약 생성 (key_achievements, challenges, next_quarter_goals)
- `projects.grant_reports` 배열에 저장

### Milestones
프로젝트 마일스톤 추적:
- `is_major: true` = 주요 마일스톤 (타임라인 표시)
- `status`: achieved, delayed, planned, added, cancelled
- `planned_quarter` vs `achieved_quarter`로 진행 상황 추적

## Common Issues

### Slack 데이터 수집 안됨
1. `SLACK_BOT_TOKEN` 확인
2. Bot에 `channels:read`, `users:read` 권한 필요
3. 권한 추가 후 앱 재설치 (Reinstall to Workspace)

### 멤버 이름이 'Unknown'으로 표시
1. `member_identifiers`에 해당 플랫폼 ID 매핑 확인
2. Admin 페이지에서 멤버의 GitHub/Slack ID 설정

### GraphQL 쿼리 실패
1. `projectKey` 파라미터가 프로젝트 key 형식인지 확인 (예: `project-ooo`)
2. Date 필터는 ISO 형식 사용 (예: `2026-01-01T00:00:00Z`)

## Report Distribution (Biweekly 리포트 배포·이메일 발송)

biweekly 리포트 HTML을 S3에 올리고, 요약 이메일을 만들어 구독자에게 AWS SES로 발송.
별도 `biweekly-reporter` 프로젝트에서 FastAPI/Next.js로 포팅됨. admin 게이트는 기존 `require_admin` 재사용.

### 핵심 파일
- `backend/api/v1/report_distribution.py` - 라우터 (`/api/v1/report-distribution`)
  - `POST /upload` (HTML→S3+파싱), `POST /preview-email`, `POST /send-test`, `POST /send-all` (BackgroundTasks 배치), `GET/POST/DELETE /subscribers`
- `src/integrations/aws_s3.py` - S3 업로드 (`upload_report_html`)
- `src/integrations/aws_email.py` - SES 발송 (`send_email`, `send_bulk`: 10건/배치 + 1초 지연)
- `src/report/summary_email.py` - 요약 이메일 빌더 + KPI/메타 파서
- `frontend/.../custom-export/components/ReportDistributionPanel.tsx` - UI ("Report Distribution" 탭)
- `scripts/import_email_subscribers.py` - emails.txt → `email_subscribers` 컬렉션 임포트 (`--dry-run` 지원)

### MongoDB
- `email_subscribers`: `{ email(unique), name?, source(import|manual), status(active|unsubscribed), created_at }`
- send-all은 `status:"active"`만 발송 대상.

### 주의
- SES 샌드박스 상태에서는 발신자·수신자 모두 검증 필요. 전체 발송 전 프로덕션 액세스 확인.
- `emails.txt`(~2,800건 외부 구독자 PII)는 git 커밋 금지, MongoDB에만 저장.
- 다음 단계(미구현): custom-export 리포트 **생성** 결과를 업로드 없이 바로 배포 흐름으로 연결.

## Support Bot (ATI Support)

티켓 기반 지원 봇. 버그/기능 요청을 받아 Claude Code로 자동 처리.

### 핵심 파일
- `scripts/support_bot_combined.py` - 메인 봇 (Socket Mode + Webhook Server 통합)
- `Makefile` - 실행 명령어 (`make support`)

### 실행
```bash
make support     # 봇 시작
make stop        # 봇 중지
```

### 환경 변수
```bash
SLACK_SUPPORT_BOT_TOKEN=xoxb-...   # Bot OAuth Token
SLACK_SUPPORT_APP_TOKEN=xapp-...   # Socket Mode Token
SLACK_SUPPORT_ADMIN_ID=U...        # 관리자 Slack ID
GITHUB_ACCOUNT_TOKEN=...           # AWS 배포용 GitHub 토큰
```

### 워크플로우
1. `/ati-support` 또는 DM → 티켓 생성
2. 관리자 승인 → Claude 작업 시작
3. 완료 → 리뷰/배포/Revert 버튼

### 배포 (deploy 버튼)
1. `git push`
2. `ssh all-thing-eye` → `cd all-thing-eye`
3. `git pull` → `docker compose build` → `docker compose up -d`
