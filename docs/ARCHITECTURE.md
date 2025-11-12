# All-Thing-Eye Web Platform Architecture

**Version:** 1.0.0  
**Last Updated:** 2025-11-12  
**Status:** Planning Phase

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Technology Stack](#technology-stack)
3. [Architecture Diagram](#architecture-diagram)
4. [Container Architecture](#container-architecture)
5. [API Design](#api-design)
6. [Frontend Design](#frontend-design)
7. [Database Schema](#database-schema)
8. [Deployment Strategy](#deployment-strategy)
9. [Security Considerations](#security-considerations)
10. [Development Roadmap](#development-roadmap)

---

## 🎯 System Overview

### Purpose
Provide a **web-based interface** for non-technical users to:
- ✅ View team activity data from multiple sources (GitHub, Slack, Google Drive)
- ✅ Generate reports with filtering options
- ✅ Download data in CSV/JSON formats
- ✅ Track team performance metrics

### Key Features
- 📊 **Dashboard**: Real-time overview of team activities
- 👥 **Member View**: Individual member activity details
- 📁 **Project View**: Project-specific data filtering
- 📈 **Reports**: Weekly/monthly activity reports
- 💾 **Export**: CSV/JSON download with custom queries
- 🔐 **Authentication**: Role-based access control

---

## 🛠 Technology Stack

### Backend (Data Collection & API)
- **Language**: Python 3.12+
- **Framework**: FastAPI (async REST API)
- **Database**: 
  - **Development**: SQLite (existing)
  - **Production**: PostgreSQL (for better concurrency)
- **ORM**: SQLAlchemy 2.0
- **Task Queue**: Celery + Redis (for scheduled data collection)
- **Containerization**: Docker

### Frontend (Web Interface)
- **Framework**: Next.js 14+ (React with SSR)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **UI Components**: shadcn/ui
- **State Management**: React Query (TanStack Query)
- **Charts**: Recharts or Chart.js
- **Containerization**: Docker

### Infrastructure
- **Container Orchestration**: Docker Compose (development/staging)
- **Reverse Proxy**: Nginx (SSL termination, load balancing)
- **Monitoring**: Prometheus + Grafana (optional)
- **Logging**: ELK Stack (optional)

---

## 🏗 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          User Browser                            │
│                     (Non-technical users)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Nginx (Reverse Proxy)                      │
│                    SSL Termination / Load Balancer              │
└───────────────┬─────────────────────────┬───────────────────────┘
                │                         │
                │ /                       │ /api
                ▼                         ▼
┌───────────────────────────┐  ┌──────────────────────────────────┐
│   Frontend Container      │  │    Backend API Container         │
│   (Next.js / React)       │  │    (FastAPI)                     │
│                           │  │                                  │
│  - Dashboard              │  │  - REST API Endpoints            │
│  - Member View            │  │  - Data Aggregation              │
│  - Report Generator       │  │  - Export Services               │
│  - Data Export UI         │  │  - Authentication                │
│                           │  │                                  │
│  Port: 3000               │  │  Port: 8000                      │
└───────────────────────────┘  └─────────────┬────────────────────┘
                                              │
                                              ▼
                            ┌──────────────────────────────────────┐
                            │   Database Container                 │
                            │   (PostgreSQL)                       │
                            │                                      │
                            │  - main.db (members, activities)     │
                            │  - github.db → postgresql            │
                            │  - slack.db → postgresql             │
                            │  - google_drive.db → postgresql      │
                            │                                      │
                            │  Port: 5432                          │
                            └──────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                 Data Collection Container                        │
│                 (Background Workers)                             │
│                                                                  │
│  - Celery Workers                                                │
│  - Scheduled Tasks (GitHub, Slack, Drive data collection)       │
│  - Report Generation                                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                             ▲
                             │
                    ┌────────┴────────┐
                    │  Redis          │
                    │  (Task Queue)   │
                    │  Port: 6379     │
                    └─────────────────┘
```

---

## 🐳 Container Architecture

### 1. **Frontend Container** (`frontend`)
```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

**Environment Variables:**
```env
NEXT_PUBLIC_API_URL=http://backend:8000
NEXT_PUBLIC_APP_NAME=All-Thing-Eye
```

---

### 2. **Backend API Container** (`backend`)
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY config/ ./config/
EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Environment Variables:**
```env
DATABASE_URL=postgresql://user:password@db:5432/allthingeye
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com
```

---

### 3. **Database Container** (`db`)
```yaml
image: postgres:16-alpine
volumes:
  - postgres_data:/var/lib/postgresql/data
environment:
  POSTGRES_DB: allthingeye
  POSTGRES_USER: admin
  POSTGRES_PASSWORD: secure_password
```

---

### 4. **Data Collection Worker** (`worker`)
```dockerfile
FROM python:3.12-slim
# Same base as backend
CMD ["celery", "-A", "src.tasks.celery_app", "worker", "--loglevel=info"]
```

---

### 5. **Redis Container** (`redis`)
```yaml
image: redis:7-alpine
volumes:
  - redis_data:/data
```

---

### 6. **Nginx Container** (`nginx`)
```nginx
upstream frontend {
    server frontend:3000;
}

upstream backend {
    server backend:8000;
}

server {
    listen 80;
    server_name localhost;

    location / {
        proxy_pass http://frontend;
    }

    location /api {
        proxy_pass http://backend;
    }
}
```

---

## 🔌 API Design

### Base URL
```
Development: http://localhost:8000/api/v1
Production: https://api.allthingeye.yourdomain.com/v1
```

### Authentication
```
POST /auth/login
POST /auth/logout
GET  /auth/me
```

### Members
```
GET    /members                          # List all members
GET    /members/{member_id}              # Get member details
GET    /members/{member_id}/activities   # Get member activities
```

### Activities
```
GET    /activities                       # List all activities (with filters)
GET    /activities/stats                 # Activity statistics
POST   /activities/export                # Export to CSV/JSON
```

**Query Parameters:**
```
?source_type=github,slack,google_drive
?member_id=1,2,3
?start_date=2025-10-01
?end_date=2025-11-01
?activity_type=commit,message,edit
?format=json|csv
```

### Projects
```
GET    /projects                         # List all projects
GET    /projects/{project_key}           # Get project details
GET    /projects/{project_key}/report    # Generate project report
```

### Reports
```
GET    /reports/weekly                   # Weekly report
GET    /reports/monthly                  # Monthly report
POST   /reports/custom                   # Custom report with filters
GET    /reports/{report_id}/download     # Download generated report
```

### GitHub
```
GET    /github/commits                   # List commits
GET    /github/pull-requests             # List PRs
GET    /github/repositories              # List repositories
```

### Slack
```
GET    /slack/channels                   # List channels
GET    /slack/messages                   # List messages
GET    /slack/threads                    # List thread conversations
```

### Google Drive
```
GET    /drive/activities                 # List drive activities
GET    /drive/folders                    # List folders
GET    /drive/documents                  # List documents
```

### Export
```
POST   /export/csv                       # Export to CSV
POST   /export/json                      # Export to JSON
GET    /export/{export_id}/download      # Download export file
```

**Request Body Example:**
```json
{
  "query": {
    "source_types": ["github", "slack"],
    "member_ids": [1, 2, 3],
    "start_date": "2025-10-01",
    "end_date": "2025-11-01",
    "activity_types": ["commit", "message"]
  },
  "fields": ["member_name", "timestamp", "activity_type", "metadata"],
  "format": "csv"
}
```

---

## 🎨 Frontend Design

### Pages

#### 1. **Dashboard** (`/`)
- Overview metrics (total activities, active members, etc.)
- Recent activity timeline
- Top contributors chart
- Activity heatmap by source

#### 2. **Members** (`/members`)
- Member list with search/filter
- Member card view with quick stats
- Click to view detailed profile

#### 3. **Member Profile** (`/members/[id]`)
- Member information
- Activity breakdown by source
- Contribution timeline
- Export member data button

#### 4. **Projects** (`/projects`)
- Project list with filter by key
- Project stats overview
- Recent activities per project

#### 5. **Project Detail** (`/projects/[key]`)
- Project information
- Active members
- Activity timeline
- Repository/channel links
- Generate report button

#### 6. **Reports** (`/reports`)
- Report generator with filters
- Pre-defined templates (Weekly, Monthly)
- Report history
- Download/share options

#### 7. **Activities** (`/activities`)
- Activity log with advanced filters
- Source type tabs (GitHub, Slack, Drive)
- Search functionality
- Export selected activities

#### 8. **Export** (`/export`)
- Custom export builder
- Query preview
- Format selection (CSV/JSON)
- Download history

---

## 🗄 Database Schema

### Migration from SQLite to PostgreSQL

**Current Structure:**
```
data/databases/
  ├── main.db          → PostgreSQL: allthingeye (main schema)
  ├── github.db        → PostgreSQL: allthingeye_github (schema)
  ├── slack.db         → PostgreSQL: allthingeye_slack (schema)
  └── google_drive.db  → PostgreSQL: allthingeye_drive (schema)
```

**PostgreSQL Schema:**
```sql
-- Main database
CREATE SCHEMA main;
CREATE SCHEMA github;
CREATE SCHEMA slack;
CREATE SCHEMA drive;

-- Use schemas for separation
SELECT * FROM main.members;
SELECT * FROM github.commits;
SELECT * FROM slack.messages;
SELECT * FROM drive.activities;
```

**Migration Script:**
```bash
# Convert SQLite to PostgreSQL
./scripts/migrate_to_postgres.sh
```

---

## 🚀 Deployment Strategy

### Development
```bash
docker-compose -f docker-compose.dev.yml up
```

### Staging
```bash
docker-compose -f docker-compose.staging.yml up -d
```

### Production
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Docker Compose File Structure
```yaml
# docker-compose.yml (base)
version: '3.8'

services:
  db:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: allthingeye
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    networks:
      - backend

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    networks:
      - backend

  backend:
    build:
      context: .
      dockerfile: docker/backend.Dockerfile
    depends_on:
      - db
      - redis
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/allthingeye
      REDIS_URL: redis://redis:6379/0
    volumes:
      - ./src:/app/src
      - ./config:/app/config
    networks:
      - backend
      - frontend

  worker:
    build:
      context: .
      dockerfile: docker/worker.Dockerfile
    depends_on:
      - db
      - redis
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/allthingeye
      REDIS_URL: redis://redis:6379/0
    networks:
      - backend

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    depends_on:
      - backend
    environment:
      NEXT_PUBLIC_API_URL: http://backend:8000
    networks:
      - frontend

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./certs:/etc/nginx/certs
    depends_on:
      - frontend
      - backend
    networks:
      - frontend

networks:
  frontend:
  backend:

volumes:
  postgres_data:
  redis_data:
```

---

## 🔐 Security Considerations

### 1. **Authentication & Authorization**
- JWT-based authentication
- Role-based access control (Admin, Team Lead, Member)
- API key for programmatic access

### 2. **Data Protection**
- HTTPS only (SSL/TLS)
- Environment variable for secrets
- Database encryption at rest
- Input validation and sanitization

### 3. **Rate Limiting**
- API rate limiting (e.g., 100 requests/minute)
- Export file size limits
- Query complexity limits

### 4. **CORS Configuration**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://allthingeye.yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 5. **Database Security**
- Separate read-only user for exports
- Connection pooling
- Query timeouts

---

## 📅 Development Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Set up FastAPI backend structure
- [ ] Create PostgreSQL migration scripts
- [ ] Design API endpoints
- [ ] Set up Docker development environment
- [ ] Create basic Next.js frontend structure

### Phase 2: Core Features (Week 3-4)
- [ ] Implement authentication system
- [ ] Build member and activity APIs
- [ ] Create dashboard UI
- [ ] Implement member list and detail pages
- [ ] Add basic filtering and search

### Phase 3: Advanced Features (Week 5-6)
- [ ] Implement export functionality (CSV/JSON)
- [ ] Create report generator
- [ ] Add project-based filtering
- [ ] Build activity timeline visualization
- [ ] Implement data caching

### Phase 4: Background Tasks (Week 7)
- [ ] Set up Celery workers
- [ ] Schedule data collection tasks
- [ ] Implement automated report generation
- [ ] Add email notifications (optional)

### Phase 5: Testing & Polish (Week 8)
- [ ] Write API tests
- [ ] Frontend E2E tests
- [ ] Performance optimization
- [ ] UI/UX improvements
- [ ] Documentation

### Phase 6: Deployment (Week 9-10)
- [ ] Set up production Docker Compose
- [ ] Configure Nginx with SSL
- [ ] Deploy to staging environment
- [ ] User acceptance testing
- [ ] Deploy to production
- [ ] Monitor and iterate

---

## 📚 File Structure

```
all-thing-eye/
├── frontend/                    # Next.js frontend
│   ├── src/
│   │   ├── app/                # Next.js app directory
│   │   ├── components/         # React components
│   │   ├── lib/                # Utilities
│   │   └── types/              # TypeScript types
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   └── Dockerfile
│
├── src/                        # Backend Python code
│   ├── api/                    # FastAPI routes
│   │   ├── main.py            # FastAPI app
│   │   ├── routes/
│   │   │   ├── members.py
│   │   │   ├── activities.py
│   │   │   ├── projects.py
│   │   │   ├── reports.py
│   │   │   └── export.py
│   │   ├── models/            # Pydantic models
│   │   └── middleware/
│   │
│   ├── core/                  # Existing core logic
│   │   ├── database.py
│   │   ├── member_index.py
│   │   └── query_engine.py
│   │
│   ├── plugins/               # Existing plugins
│   │   ├── github_plugin.py
│   │   ├── slack_plugin.py
│   │   └── google_drive_plugin.py
│   │
│   ├── services/              # Business logic
│   │   ├── export_service.py
│   │   ├── report_service.py
│   │   └── stats_service.py
│   │
│   └── tasks/                 # Celery tasks
│       ├── celery_app.py
│       ├── collection_tasks.py
│       └── report_tasks.py
│
├── docker/
│   ├── backend.Dockerfile
│   ├── worker.Dockerfile
│   └── nginx.Dockerfile
│
├── scripts/
│   ├── migrate_to_postgres.sh
│   ├── init_db.sh
│   └── deploy.sh
│
├── tests/
│   ├── api/                   # API tests
│   └── integration/           # Integration tests
│
├── docs/
│   ├── ARCHITECTURE.md        # This file
│   ├── API.md                 # API documentation
│   └── DEPLOYMENT.md          # Deployment guide
│
├── docker-compose.yml
├── docker-compose.dev.yml
├── docker-compose.prod.yml
├── .env.example
└── README.md
```

---

## 🎯 Success Metrics

- ✅ Non-technical users can access data without CLI
- ✅ Export functionality works reliably
- ✅ Page load time < 2 seconds
- ✅ API response time < 500ms (95th percentile)
- ✅ 99.9% uptime
- ✅ Support 50+ concurrent users

---

## 📞 Questions & Feedback

For questions or suggestions about this architecture:
1. Review existing documentation
2. Check API.md for endpoint details
3. Consult DEPLOYMENT.md for deployment procedures
4. Contact the development team

---

**Status:** Planning Complete ✅  
**Next Step:** Phase 1 Implementation

---
