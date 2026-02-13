# AGENTS.md - All-Thing-Eye

Team member activity analytics data pipeline. Collects data from Slack, GitHub, Notion, and Google Drive, providing AI-powered analysis.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Nginx (Reverse Proxy)                    │
│                   nginx/nginx.prod.conf (HTTPS)                 │
└──────────┬──────────────────────────────┬───────────────────────┘
           │                              │
  ┌────────▼────────┐          ┌──────────▼──────────┐
  │  Frontend        │          │  Backend (FastAPI)   │
  │  Next.js 14      │          │  REST + GraphQL      │
  │  Port 3000       │          │  Port 8000           │
  └─────────────────┘          └──────────┬───────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
           ┌────────▼──────┐   ┌──────────▼──────┐   ┌────────▼────────┐
           │  MongoDB Atlas │   │  Slack API       │   │  External APIs   │
           │  DB: ati       │   │  Bot + Socket    │   │  GitHub, Notion  │
           └───────────────┘   └─────────────────┘   │  Drive, AI       │
                                                      └─────────────────┘
```

**Data Flow:**
1. **Collection** - Plugins (`src/plugins/`) → cron scripts (`scripts/`) → MongoDB
2. **Serving** - Backend REST/GraphQL (`backend/`) → Frontend (`frontend/`)
3. **Bots** - Slack bots (`scripts/`) ↔ Backend API ↔ MongoDB

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS, Apollo Client |
| Backend | FastAPI, Python 3.11+, Strawberry GraphQL |
| Database | MongoDB Atlas (DB: `ati`) |
| Auth | JWT + Web3 (wagmi/ethers) wallet login |
| AI | Tokamak AI API (qwen3-235b), Anthropic Claude |
| Infra | AWS EC2, Docker Compose, Nginx, Let's Encrypt |

## Key Environment Variables

```bash
MONGODB_URI          # MongoDB connection string
MONGODB_DATABASE=ati # Database name
SLACK_BOT_TOKEN      # Slack bot (data collection)
GITHUB_TOKEN         # GitHub API (Personal Access Token)
GITHUB_ORG           # GitHub org (tokamak-network)
AI_API_KEY           # Tokamak AI API key
JWT_SECRET_KEY       # JWT auth secret
```

## Scheduled Services (Production)

| Service | Schedule | Script | Purpose |
|---------|----------|--------|---------|
| data-collector | Every 4 hours (KST) | `daily_data_collection_mongo.py` | Collect GitHub/Slack/Drive data |
| notion-diff-collector | Every 1 minute | `collect_notion_diff.py` | Real-time Notion page tracking |
| weekly-bot | APScheduler | `weekly_output_bot.py` | Send weekly reports to Slack |
| weekly-catchup | Sundays 02:00 KST | `weekly_github_catchup.py` | Re-collect late-pushed commits (7-day window) |

## Member Name Resolution

Activity data → member mapping path:
1. Activity author field (e.g. `github_commits.author_name`)
2. Match via `identifier_type + identifier_value` in `member_identifiers` collection
3. Resolve actual member name via `members._id`

---

## Directory Guide

### `backend/` - FastAPI Backend

FastAPI application serving REST API + Strawberry GraphQL.

- **Entry point**: `main.py` (CORS, router registration, GraphQL mount)
- **API endpoints**: `api/v1/` (detailed below)
- **GraphQL**: `graphql/` (Strawberry schema, queries, mutations)
- **Auth**: `middleware/jwt_auth.py` (JWT Bearer), `middleware/tenant.py` (multi-tenant)

#### `backend/api/v1/` - REST Endpoints

| File | Endpoint | Description |
|------|----------|-------------|
| `activities_mongo.py` | `/api/v1/activities` | Activity list with filtering |
| `members_mongo.py` | `/api/v1/members` | Member CRUD |
| `projects_management.py` | `/api/v1/projects-management` | Projects, Grant Reports, Milestones |
| `stats_mongo.py` | `/api/v1/stats` | Statistics (commit counts, activity volume, etc.) |
| `exports_mongo.py` | `/api/v1/exports` | CSV/JSON export |
| `database_mongo.py` | `/api/v1/database` | Database viewer API |
| `weekly_output_schedules.py` | `/api/v1/weekly-output-schedules` | Weekly report schedule management |
| `mcp_agent.py` | `/api/v1/mcp-agent` | AI agent execution |
| `ai_proxy.py` | `/api/v1/ai` | AI API proxy |
| `slack_bot.py` | `/api/v1/slack` | Slack bot interactions |
| `support_bot.py` | `/api/v1/support-bot` | Support ticket API |
| `auth.py` | `/api/v1/auth` | Authentication (wallet login) |
| `reports.py` | `/api/v1/reports` | Report generation |
| `notion_diff.py` | `/api/v1/notion-diff` | Notion diff viewer |

**Legacy files** (deprecated, use `_mongo.py` versions): `activities.py`, `members.py`, `projects.py`, `exports.py`, `query.py`

#### `backend/graphql/` - GraphQL Layer

Strawberry GraphQL implementation, integrated with Apollo Client.

| File | Role |
|------|------|
| `schema.py` | Schema builder (combines Query + Mutation) |
| `queries.py` | Main queries (activities, members, projects, stats) |
| `mutations.py` | Mutations (member edits, project management, etc.) |
| `types.py` | GraphQL type definitions (Strawberry types) |
| `dataloaders.py` | DataLoader for N+1 prevention |
| `activity_filters.py` | Activity filtering logic |
| `extensions.py` | GraphQL extensions |

---

### `frontend/` - Next.js 14 Frontend

App Router based. Tailwind CSS + Apollo Client (GraphQL).

- **Config**: `next.config.js`, `tailwind.config.ts`, `tsconfig.json`
- **Package**: `package.json` (apollo, tailwind, wagmi, recharts)
- **Dockerfile**: Production build image

#### `frontend/src/app/` - Pages (App Router)

| Path | Page | Description |
|------|------|-------------|
| `/` | `page.tsx` | Dashboard (activity summary, top contributors) |
| `/activities` | `activities/page.tsx` | Activity list (filters, pagination) |
| `/members` | `members/page.tsx` | Member list |
| `/members/[id]` | `members/[id]/page.tsx` | Member detail (activity history) |
| `/projects` | `projects/page.tsx` | Project list |
| `/projects/[key]` | `projects/[key]/page.tsx` | Project detail (timeline, milestones) |
| `/database` | `database/page.tsx` | Database viewer |
| `/exports` | `exports/page.tsx` | Data export |
| `/custom-export` | `custom-export/page.tsx` | Custom export (with AI chat) |
| `/ai-chat` | `ai-chat/page.tsx` | AI chat |
| `/tools/weekly-output` | `tools/weekly-output/page.tsx` | Weekly report schedule UI |
| `/login` | `login/page.tsx` | Web3 wallet login |
| `/recordings` | `recordings/page.tsx` | Recordings (shared DB) |

#### `frontend/src/components/` - Shared Components

| Component | Role |
|-----------|------|
| `Navigation.tsx` | Sidebar navigation |
| `AuthGuard.tsx` | Auth guard (redirect to login if unauthenticated) |
| `ActivitiesList.tsx` | Activity list (infinite scroll) |
| `ActivitiesView.tsx` | Activity view (card/table modes) |
| `CodeStatsView.tsx` | Code statistics charts |
| `CollaborationNetwork.tsx` | Collaboration network graph |
| `DateRangePicker.tsx` | Date range selector |
| `FloatingAIChatbot.tsx` | Floating AI chatbot |
| `MemberActivityStats.tsx` | Per-member activity statistics |
| `Web3Provider.tsx` | Web3 Provider (wagmi) |
| `ApolloProvider.tsx` | Apollo Client Provider |

#### `frontend/src/graphql/` - GraphQL Client

| File | Role |
|------|------|
| `queries.ts` | GraphQL query strings |
| `mutations.ts` | GraphQL mutation strings |
| `types.ts` | Auto-generated TypeScript types |
| `hooks.ts` | Custom `useQuery`/`useMutation` hooks |
| `fragments.ts` | Shared fragments |

#### `frontend/src/lib/` - Utilities

| File | Role |
|------|------|
| `api.ts` | REST API client (axios) |
| `apollo-client.ts` | Apollo Client configuration |
| `auth.ts` | Auth utilities |
| `jwt.ts` | JWT handling |

---

### `src/` - Core Library

Core library for the data collection pipeline. Plugins, models, and schedulers.

#### `src/core/` - Infrastructure

| File | Role |
|------|------|
| `mongo_manager.py` | MongoDB connection manager (sync + async). `MongoManager` singleton |
| `config.py` | Loads `config/config.yaml`. Plugin/DB/scheduler settings |
| `member_index.py` | Member name resolution (identifier → member name) |
| `plugin_loader.py` | Dynamic plugin loader |
| `database.py` | Legacy SQL (unused) |

#### `src/plugins/` - Data Collection Plugins

Each plugin fetches data from an external API and stores it in MongoDB.

| Plugin | Source | Collections |
|--------|--------|-------------|
| `github_plugin_mongo.py` | GitHub REST + GraphQL API | `github_commits`, `github_pull_requests`, `github_issues` |
| `slack_plugin_mongo.py` | Slack API | `slack_messages`, `slack_reactions`, `slack_channels` |
| `notion_plugin_mongo.py` | Notion API | `notion_pages`, `notion_comments`, `notion_databases` |
| `google_drive_plugin_mongo.py` | Google Drive API | `drive_activities`, `drive_folders` |
| `ecosystem_plugin_mongo.py` | Ecosystem data | Ecosystem metrics |
| `drive_diff_plugin.py` | Drive content diff | Document change tracking |
| `notion_diff_plugin.py` | Notion content diff | Page change tracking |

**Base class**: `base.py` - Plugin interface definition
**Legacy** (files without `_mongo.py` suffix): Unused

#### `src/models/` - Data Models

| File | Role |
|------|------|
| `mongo_models.py` | Pydantic models: `MemberModel`, `ProjectModel`, `ActivityModel`, etc. |

Key fields:
- `MemberModel`: `name`, `email`, `role`, `is_active`, `resigned_at`
- `MemberIdentifierModel`: `member_id`, `identifier_type` (github/slack/notion), `identifier_value`
- `ProjectModel`: `key`, `name`, `member_ids`, `grant_reports`, `milestones`, `is_active`

#### `src/scheduler/` - Scheduler

| File | Role |
|------|------|
| `slack_scheduler.py` | APScheduler-based Slack message scheduler |

#### `src/integrations/` - AI Integration

| File | Role |
|------|------|
| `ai_formatter.py` | Format data into AI prompt structure |
| `query_engine.py` | Natural language → MongoDB query conversion |

#### `src/report/` - Report Generation

| File | Role |
|------|------|
| `ai_client.py` | AI API client |
| `templates/biweekly.py` | Biweekly report template |
| `external_data/` | Market data (market_cap, staking, transactions) |

#### `src/utils/` - Utilities

| File | Role |
|------|------|
| `date_helpers.py` | KST timezone handling, date range calculations |
| `logger.py` | Structured logging |
| `report_generator.py` | Report generator |

---

### `scripts/` - Utility Scripts

#### Data Collection

| Script | Usage | Description |
|--------|-------|-------------|
| `daily_data_collection_mongo.py` | 4-hour cron | Main collector: GitHub/Slack/Drive |
| `weekly_github_catchup.py` | Sunday cron | Re-collect late-pushed commits (7-day window) |
| `initial_data_collection_mongo.py` | One-time | Initial 14-day data collection |
| `collect_github_batch.py` | Manual | Batch GitHub collection |
| `collect_slack_batch.py` | Manual | Batch Slack collection |
| `collect_notion_90days.py` | Manual | 90-day Notion collection |
| `collect_notion_diff.py` | 1-min cron | Real-time Notion change tracking |
| `collect_drive_diff.py` | Manual | Drive change tracking |

#### Bots

| Script | Usage | Description |
|--------|-------|-------------|
| `support_bot_combined.py` | `make support` | Support bot (HTTP Events API + Socket Mode) |
| `weekly_output_bot.py` | `make weekly` | Weekly report bot (APScheduler) |
| `claude_executor.py` | `make executor` | Claude task executor (polls AWS) |

#### Database

| Script | Description |
|--------|-------------|
| `backup_mongodb.py` | MongoDB backup (local) |
| `backup_mongodb_to_s3.py` | MongoDB → S3 backup |
| `backup_mongodb_to_collection.py` | MongoDB → collection backup |
| `restore_mongodb_from_collection.py` | Restore from collection |

#### Deployment

| Script | Description |
|--------|-------------|
| `deploy.sh` | AWS deploy (git push → ssh → pull → build → restart) |
| `setup_cron.sh` | Cron job setup |
| `force-rebuild-frontend.sh` | Force frontend rebuild |
| `rebuild-services.sh` | Rebuild all services |

#### Issue Automation (`scripts/issue_automation/`)

| File | Role |
|------|------|
| `parser.py` | GitHub issue parser |
| `diagnosis.py` | Issue diagnosis |
| `ai_fixer.py` | AI-powered auto-fix |
| `pr_creator.py` | Automated PR creation |

---

### `config/` - Configuration

| File | Role |
|------|------|
| `config.yaml` | Main config (MongoDB URI, plugin settings, scheduler) |
| `google_drive/credentials.json` | Google OAuth2 credentials |
| `google_drive/token_*.pickle` | Google API tokens |

---

### `docs/` - Documentation

| Category | Key Files |
|----------|-----------|
| Architecture | `ARCHITECTURE.md`, `PROJECT_STRUCTURE.md` |
| Setup | `QUICK_START.md`, `ENV_SETUP.md`, `GITHUB_SETUP.md`, `SLACK_SETUP.md` |
| Database | `MONGODB_SCHEMA.md`, `MONGODB_COMPLETE_SCHEMA.md` |
| Deployment | `AWS_DEPLOYMENT.md`, `README_DOCKER.md` |
| GraphQL | `GRAPHQL_QUICKSTART.md`, `GRAPHQL_MIGRATION_PLAN.md` |
| Features | `MCP_INTEGRATION.md`, `CUSTOM_EXPORT_SPEC.md`, `SLACKBOT.md` |

---

### `tests/` - Test Suite

| Category | Files | Description |
|----------|-------|-------------|
| Plugin tests | `test_github_*.py`, `test_slack_*.py`, `test_notion_*.py`, `test_drive_*.py` | Unit tests for each plugin |
| DB tests | `test_remote_mongodb*.py` | MongoDB connection tests |
| Issue automation | `tests/test_issue_automation/` | Issue automation tests |
| Diff collection | `tests/diff_collection/` | Change tracking tests |
| Utils | `test_date_helpers.py` | Utility tests |

Run: `pytest tests/` (from project root)

---

### `mcp_server/` - MCP Server

| File | Role |
|------|------|
| `server.py` | MCP (Model Context Protocol) server |
| `config.json` | MCP configuration |

Interface allowing AI agents to directly query the database.

---

### Docker & Infrastructure

| File | Environment | Services |
|------|-------------|----------|
| `docker-compose.yml` | Local dev | mongodb, backend |
| `docker-compose.prod.yml` | Production | nginx, backend, frontend, data-collector, notion-diff-collector, weekly-bot |
| `Dockerfile.backend` | - | Backend image (Python 3.11) |
| `frontend/Dockerfile` | - | Frontend image (Node 18) |
| `nginx/nginx.prod.conf` | Production | HTTPS, Let's Encrypt, reverse proxy |

---

## MongoDB Collections Reference

### Core

| Collection | Key Fields | Index |
|------------|-----------|-------|
| `members` | `name`, `email`, `role`, `is_active`, `resigned_at` | `email` unique |
| `member_identifiers` | `member_id`, `identifier_type`, `identifier_value`, `source` | compound |
| `projects` | `key`, `name`, `member_ids[]`, `grant_reports[]`, `milestones[]`, `is_active` | `key` unique |

### Activity

| Collection | Key Fields | Date Field |
|------------|-----------|------------|
| `github_commits` | `repo`, `author_name`, `sha`, `message` | `date` |
| `github_pull_requests` | `repo`, `author`, `title`, `state` | `created_at` |
| `github_issues` | `repo`, `author`, `title`, `state` | `created_at` |
| `slack_messages` | `channel`, `user_name`, `text` | `posted_at` |
| `notion_pages` | `title`, `last_edited_by`, `database_id` | `last_edited_time` |
| `drive_activities` | `actor_email`, `target_name`, `action_type` | `time` |

### Inactive Member Query Pattern

Backwards-compatible inactive member filtering:
```python
{"is_active": {"$ne": False}}  # Includes both True and documents where field doesn't exist
```

---

## Common Patterns

### Adding a New API Endpoint
1. Create a new file in `backend/api/v1/`
2. Register the router in `backend/main.py` (`app.include_router`)
3. Optionally add GraphQL query in `backend/graphql/queries.py`

### Adding a New Data Plugin
1. Create `{source}_plugin_mongo.py` in `src/plugins/`
2. Implement the interface from `base.py`
3. Add plugin config to `config/config.yaml`
4. Add collection logic to `scripts/daily_data_collection_mongo.py`

### Adding a Frontend Page
1. Create `frontend/src/app/{route}/page.tsx`
2. Add menu item to `frontend/src/components/Navigation.tsx`
3. Optionally add query to `frontend/src/graphql/queries.ts`

### Deployment
```bash
# Local changes → git push → AWS deploy
git push origin main
bash scripts/deploy.sh
# Or use the Deploy button in the support bot
```
