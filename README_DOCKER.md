# Docker Quick Start Guide

This guide will help you run All-Thing-Eye with Docker.

---

## 🚀 Quick Start

### 1. Prepare Environment Variables

Create `.env` file in the project root:

```bash
# PostgreSQL Database
POSTGRES_DB=allthingeye
POSTGRES_USER=allthingeye
POSTGRES_PASSWORD=your_secure_password_here

# Application
APP_ENV=production
APP_DEBUG=false
SECRET_KEY=generate_a_random_secret_key_here

# API
API_WORKERS=4
CORS_ORIGINS=http://localhost:3000

# GitHub
GITHUB_ENABLED=true
GITHUB_TOKEN=ghp_your_token
GITHUB_ORG=your_org

# Slack
SLACK_ENABLED=true
SLACK_BOT_TOKEN=xoxb_your_token
SLACK_WORKSPACE=your_workspace

# Notion (optional)
NOTION_ENABLED=false
NOTION_TOKEN=secret_your_token

# Logging
LOG_LEVEL=INFO
```

### 2. Start Services

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f backend

# Check status
docker-compose ps
```

### 3. Access API

- **API Documentation**: http://localhost/api/docs
- **Health Check**: http://localhost/health
- **PostgreSQL**: localhost:5432

### 4. Test API

```bash
# Run test script
bash scripts/test_api.sh

# Or manually test
curl http://localhost/api/v1/members
```

---

## 📊 Services

| Service | Port | Description |
|---------|------|-------------|
| nginx | 80, 443 | Reverse proxy |
| backend | 8000 | FastAPI application |
| postgres | 5432 | PostgreSQL database |
| redis | 6379 | Cache & queue |

---

## 🛠️ Management

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f postgres
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart backend
```

### Stop Services

```bash
# Stop (keep data)
docker-compose stop

# Stop and remove containers
docker-compose down

# Remove everything including volumes (⚠️ DELETES DATA!)
docker-compose down -v
```

### Access Database

```bash
# Access PostgreSQL shell
docker-compose exec postgres psql -U allthingeye -d allthingeye

# Run SQL query
docker-compose exec postgres psql -U allthingeye -d allthingeye -c "SELECT COUNT(*) FROM members;"
```

### Execute Commands in Container

```bash
# Access backend container shell
docker-compose exec backend bash

# Run Python script
docker-compose exec backend python tests/test_github_plugin.py
```

---

## 🔧 Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs backend

# Rebuild without cache
docker-compose build --no-cache backend
docker-compose up -d
```

### Database connection error

```bash
# Check if database is ready
docker-compose exec postgres pg_isready

# Check credentials
cat .env | grep POSTGRES

# Restart database
docker-compose restart postgres
```

### API returns error

```bash
# Check backend logs
docker-compose logs --tail=50 backend

# Check if all services are running
docker-compose ps

# Restart backend
docker-compose restart backend
```

---

## 📚 More Information

- [API Development Guide](docs/API_DEVELOPMENT.md)
- [Architecture Document](docs/ARCHITECTURE.md)

---

**Need help?** Check the logs first: `docker-compose logs -f`

