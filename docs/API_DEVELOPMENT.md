# API Development Guide

This guide covers the backend API development for All-Thing-Eye.

---

## 📋 Table of Contents

1. [Architecture](#architecture)
2. [Quick Start](#quick-start)
3. [API Endpoints](#api-endpoints)
4. [Development Workflow](#development-workflow)
5. [Docker Setup](#docker-setup)
6. [Testing](#testing)
7. [Deployment](#deployment)

---

## 🏗️ Architecture

### Tech Stack

- **Framework**: FastAPI 0.104.1
- **Database**: PostgreSQL 16 (SQLAlchemy 2.0)
- **Cache**: Redis 7
- **Web Server**: Nginx (reverse proxy)
- **Container**: Docker + Docker Compose

### Project Structure

```
all-thing-eye/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── __init__.py
│   └── api/
│       └── v1/
│           ├── members.py    # Member endpoints
│           ├── activities.py # Activity endpoints
│           ├── projects.py   # Project endpoints
│           └── exports.py    # Export endpoints
├── src/
│   ├── core/                # Core modules
│   ├── plugins/             # Data source plugins
│   └── utils/               # Utility functions
├── docker-compose.yml       # Docker orchestration
├── Dockerfile.backend       # Backend container
└── nginx/
    └── nginx.conf           # Nginx configuration
```

---

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local development)
- PostgreSQL client (optional)

### 1. Clone and Setup

```bash
cd /Users/son-yeongseong/Desktop/dev/all-thing-eye

# Copy environment variables
cp .env.example .env

# Edit .env with your credentials
nano .env
```

### 2. Start with Docker Compose

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f backend
```

### 3. Access API

- **API Docs**: http://localhost/api/docs
- **ReDoc**: http://localhost/api/redoc
- **Health Check**: http://localhost/health

### 4. Stop Services

```bash
docker-compose down

# Remove volumes (WARNING: deletes data!)
docker-compose down -v
```

---

## 📡 API Endpoints

### Members API

#### `GET /api/v1/members`
Get list of all members

**Query Parameters:**
- `limit` (int): Max results (1-1000, default: 100)
- `offset` (int): Skip results (default: 0)

**Response:**
```json
{
  "total": 24,
  "members": [
    {
      "id": 1,
      "name": "Kevin",
      "email": "kevin@tokamak.network",
      "created_at": "2025-11-01T00:00:00"
    }
  ]
}
```

#### `GET /api/v1/members/{member_id}`
Get detailed member information

**Response:**
```json
{
  "id": 1,
  "name": "Kevin",
  "email": "kevin@tokamak.network",
  "identifiers": [
    {"source_type": "github", "source_user_id": "ggs134"},
    {"source_type": "slack", "source_user_id": "U075F3T4MRB"}
  ],
  "activity_summary": {
    "github": {
      "github_commit": {"count": 42, "first_activity": "...", "last_activity": "..."}
    }
  },
  "created_at": "2025-11-01T00:00:00"
}
```

#### `GET /api/v1/members/{member_id}/activities`
Get member activities with filters

**Query Parameters:**
- `source_type` (str): Filter by source
- `activity_type` (str): Filter by activity type
- `start_date` (str): ISO date
- `end_date` (str): ISO date
- `limit` (int): Max results
- `offset` (int): Skip results

---

### Activities API

#### `GET /api/v1/activities`
Get activities with filters

**Query Parameters:**
- `source_type` (str): github, slack, notion, google_drive
- `activity_type` (str): Specific activity type
- `member_id` (int): Filter by member
- `start_date` (str): ISO date
- `end_date` (str): ISO date
- `limit` (int): Max results (1-1000)
- `offset` (int): Skip results

#### `GET /api/v1/activities/summary`
Get activity statistics

**Response:**
```json
{
  "summary": {
    "github": {
      "total_activities": 150,
      "activity_types": {
        "github_commit": {
          "count": 100,
          "unique_members": 5,
          "first_activity": "...",
          "last_activity": "..."
        }
      }
    }
  }
}
```

#### `GET /api/v1/activities/types`
Get available activity types grouped by source

---

### Projects API

#### `GET /api/v1/projects`
Get all projects

**Response:**
```json
{
  "total": 4,
  "projects": [
    {
      "key": "project-ooo",
      "name": "Project OOO (Zero-Knowledge Proof)",
      "slack_channel": "project-ooo",
      "slack_channel_id": "C07JN9XR570",
      "lead": "Jake",
      "repositories": ["Tokamak-zk-EVM", "tokamak-zk-evm-docs"],
      "drive_folders": ["Meet Recordings", "Project OOO"],
      "description": "Zero-knowledge proof implementation"
    }
  ]
}
```

#### `GET /api/v1/projects/{project_key}`
Get project details with statistics

#### `GET /api/v1/projects/{project_key}/members`
Get active members in project

---

### Exports API

#### `GET /api/v1/exports/tables`
Get list of all available tables from all data sources

**Response:**
```json
{
  "sources": {
    "main": ["members", "member_identifiers", "member_activities"],
    "github": ["github_commits", "github_pull_requests", "github_issues"],
    "slack": ["slack_channels", "slack_messages", "slack_reactions"],
    "google_drive": ["drive_activities", "drive_documents", "drive_folders"],
    "notion": ["notion_pages", "notion_databases", "notion_comments"]
  },
  "total_sources": 5,
  "total_tables": 15
}
```

#### `GET /api/v1/exports/tables/{source}/{table}/csv`
Export any table as CSV

**Path Parameters:**
- `source`: Database source (main, github, slack, google_drive, notion)
- `table`: Table name

**Query Parameters:**
- `limit` (int): Maximum rows to export (1-100000, optional)

**Response:** CSV file download

**Example:**
```bash
# Export main.members table
curl "http://localhost:8000/api/v1/exports/tables/main/members/csv" -o members.csv

# Export slack messages (limit 1000 rows)
curl "http://localhost:8000/api/v1/exports/tables/slack/slack_messages/csv?limit=1000" -o slack_messages.csv
```

#### `GET /api/v1/export/members?format=csv|json`
Export members data (legacy)

#### `GET /api/v1/export/activities?format=csv|json`
Export activities with filters (legacy)

**Query Parameters:** Same as activities endpoint + `format`

#### `GET /api/v1/export/projects/{project_key}?format=csv|json`
Export project-specific data (legacy)

**Query Parameters:**
- `format` (str): csv or json
- `data_type` (str): all, slack, github, google_drive

---

## 💻 Development Workflow

### Local Development (without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL=sqlite:///data/databases/main.db
export GITHUB_TOKEN=your_token
export SLACK_BOT_TOKEN=your_token

# Run development server
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Hot Reload

The development server automatically reloads on code changes:

```bash
# Watch logs
docker-compose logs -f backend
```

### Database Migrations (Future)

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## 🐳 Docker Setup

### Build Images

```bash
# Build backend only
docker-compose build backend

# Build all services
docker-compose build
```

### Environment Variables

Create `.env` file:

```bash
# Database
POSTGRES_DB=allthingeye
POSTGRES_USER=allthingeye
POSTGRES_PASSWORD=your_secure_password

# Application
APP_ENV=production
SECRET_KEY=your_secret_key_here

# API
API_WORKERS=4
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com

# Plugins
GITHUB_TOKEN=your_github_token
SLACK_BOT_TOKEN=xoxb-your-slack-token
NOTION_TOKEN=secret_your_notion_token
```

### Docker Compose Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f [service_name]

# Restart service
docker-compose restart backend

# Execute command in container
docker-compose exec backend python --version

# Access PostgreSQL
docker-compose exec postgres psql -U allthingeye -d allthingeye
```

---

## 🧪 Testing

### Manual API Testing

Use the interactive API documentation:
- **Swagger UI**: http://localhost/api/docs
- **ReDoc**: http://localhost/api/redoc

### cURL Examples

```bash
# Get members
curl http://localhost/api/v1/members

# Get member detail
curl http://localhost/api/v1/members/1

# Get activities with filters
curl "http://localhost/api/v1/activities?source_type=github&limit=10"

# Export data
curl "http://localhost/api/v1/export/members?format=csv" -o members.csv
```

### Python Requests

```python
import requests

# Get members
response = requests.get('http://localhost/api/v1/members')
members = response.json()

# Get activities
response = requests.get('http://localhost/api/v1/activities', params={
    'source_type': 'github',
    'start_date': '2025-11-01',
    'limit': 100
})
activities = response.json()
```

---

## 🚀 Deployment

### Production Checklist

- [ ] Set strong `SECRET_KEY` and database passwords
- [ ] Update `CORS_ORIGINS` to your domain
- [ ] Enable HTTPS (SSL certificates in nginx)
- [ ] Set `APP_ENV=production` and `APP_DEBUG=false`
- [ ] Configure firewall (only expose 80/443)
- [ ] Set up backup for PostgreSQL
- [ ] Configure log rotation
- [ ] Monitor API performance
- [ ] Set up alerts for errors

### SSL/HTTPS Setup

1. Get SSL certificate (Let's Encrypt, CloudFlare, etc.)
2. Place cert files in `nginx/ssl/`
3. Uncomment HTTPS server block in `nginx/nginx.conf`
4. Update docker-compose to expose port 443

### Performance Tuning

#### PostgreSQL
```yaml
# docker-compose.yml
postgres:
  command: postgres -c 'max_connections=200' -c 'shared_buffers=256MB'
```

#### Backend API
```yaml
backend:
  environment:
    API_WORKERS: 8  # Adjust based on CPU cores
```

---

## 📊 Monitoring

### Health Checks

```bash
# API health
curl http://localhost/health

# Backend health
curl http://localhost:8000/health

# Database health
docker-compose exec postgres pg_isready
```

### Logs

```bash
# All logs
docker-compose logs -f

# Backend only
docker-compose logs -f backend

# Last 100 lines
docker-compose logs --tail=100 backend
```

### Metrics (Future)

- API response times
- Request counts per endpoint
- Error rates
- Database query performance
- Cache hit rates

---

## 🔧 Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs backend

# Rebuild image
docker-compose build --no-cache backend
docker-compose up -d
```

### Database connection error

```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Check database credentials in .env
cat .env | grep POSTGRES

# Access database directly
docker-compose exec postgres psql -U allthingeye -d allthingeye
```

### API returns 500 error

```bash
# Check backend logs
docker-compose logs backend | tail -50

# Check if databases exist
ls -la data/databases/

# Restart backend
docker-compose restart backend
```

---

## 📚 Related Documentation

- [Architecture Document](./ARCHITECTURE.md)
- [Database Schema](./DATABASE_SCHEMA.md)
- [Report Guidelines](./REPORT_GUIDELINES.md)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

---

**Last Updated:** 2025-11-12  
**Version:** 1.0.0  
**Maintained by:** All-Thing-Eye Development Team

