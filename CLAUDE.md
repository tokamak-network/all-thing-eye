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
