# All-Thing-Eye 👁️

HR Member Performance Analysis Data Pipeline System

## 🎯 Project Overview

A comprehensive data pipeline system that collects, integrates, and analyzes team member activities from various sources for AI-powered performance insights.

### Key Features

- 📊 **Multi-Source Data Collection**: Slack, GitHub, Notion, Google Drive, and more
- 🗄️ **Source-Specific Database Management**: Dedicated database for each data source
- 👥 **Member-Centric Integration**: Unified query system with member names as keys
- 🔌 **Plugin Architecture**: Automatic integration when adding new data sources
- 🤖 **AI Integration**: Optimized data formatting for AI-powered analysis

## 🏗 Architecture

```
Data Sources (Slack, GitHub, Notion, Drive)
    ↓
Plugin Collectors
    ↓
Source-Specific DBs
    ↓
Member-Centric Integration Layer
    ↓
AI Prompt Formatter
```

For detailed information, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- GitHub Personal Access Token (required)
- Slack, Notion, Google Drive API keys (optional)

### 5-Minute Setup Guide

```bash
# 1. Navigate to project directory
cd /Users/son-yeongseong/Desktop/dev/all-thing-eye

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
nano .env  # Or use your preferred editor

# Minimum configuration (GitHub only):
# GITHUB_ENABLED=true
# GITHUB_TOKEN=ghp_your_token
# GITHUB_ORG=your-org-name

# 5. Run initial setup
python scripts/setup.py

# 6. Test GitHub plugin
python tests/test_github_plugin.py
```

**✅ Success!** Your data is now collected in the `data/databases/` folder.

For detailed guide: [**QUICK_START.md**](docs/QUICK_START.md)

### Using Docker

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f
```

## 📖 Usage

### 1. Data Collection

```bash
# Test GitHub data collection (single member)
python tests/test_github_plugin.py --single-member Kevin

# Collect for all members (current week)
python tests/test_github_plugin.py

# Collect last week's data
python tests/test_github_plugin.py --last-week
```

### 2. Query and Analysis

```bash
# Analyze single member (generates AI prompts)
python tests/test_query_and_ai.py --member Kevin

# Team summary
python tests/test_query_and_ai.py --team-summary

# Export specific format
python tests/test_query_and_ai.py --member Kevin --format json
```

**Output files saved to**: `output/reports/`

### 3. Member Management

```bash
# List all members
python -m src.cli members list

# Query member activities
python -m src.cli members activity --name "John Doe" --days 30
```

### API Server

```bash
# Development mode
uvicorn src.api.main:app --reload --port 8000

# Production mode
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

API Documentation: http://localhost:8000/docs

## 🔧 Configuration

### config.yaml

Main configuration is managed in `config/config.yaml`:

```yaml
database:
  main_db: "sqlite:///data/databases/main.db"

plugins:
  slack:
    enabled: true
    token: ${SLACK_BOT_TOKEN}

  github:
    enabled: true
    token: ${GITHUB_TOKEN}

scheduler:
  enabled: true
  interval_hours: 24
```

### Environment Variables

Manage sensitive information in `.env` file:

```env
SLACK_BOT_TOKEN=xoxb-your-token
GITHUB_TOKEN=ghp_your-token
NOTION_TOKEN=secret_your-token
GOOGLE_CREDENTIALS_PATH=./credentials/google-credentials.json
```

## 🔌 Adding New Data Sources

Easily add new data sources using the plugin system:

1. Create new plugin file in `src/plugins/` (e.g., `jira_plugin.py`)
2. Inherit from `DataSourcePlugin` class
3. Implement required methods
4. Add configuration to `config.yaml`

Detailed guide: [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md)

## 📊 Data Structure

### Source-Specific Databases

- `slack_db`: Messages, reactions, channel activities
- `github_db`: Commits, PRs, issues, code reviews
- `notion_db`: Pages, edit history
- `google_drive_db`: Files, shares, comments

### Unified Member Index

Member-centric index across all sources for efficient querying

## 🛠 Development

### Project Structure

```
all-thing-eye/
├── docs/              # Documentation
├── src/               # Source code
│   ├── core/         # Core system
│   ├── plugins/      # Data source plugins
│   ├── models/       # Data models
│   ├── integrations/ # Integration layer
│   ├── api/          # REST API
│   └── scheduler/    # Scheduler
├── tests/            # Tests
├── scripts/          # Utility scripts
└── config/           # Configuration files
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test
pytest tests/unit/test_plugins.py

# With coverage
pytest --cov=src tests/
```

## 🔐 Security

- API keys managed via environment variables
- Sensitive data encrypted in storage
- RBAC-based access control
- GDPR and privacy law compliant

## 📚 Documentation

- [Architecture Design](docs/ARCHITECTURE.md)
- [Implementation Plan](docs/IMPLEMENTATION_PLAN.md)
- [GitHub Setup Guide](docs/GITHUB_SETUP.md)
- [Quick Start Guide](docs/QUICK_START.md)
- [Environment Setup](docs/ENV_SETUP.md)
- [Member Management](docs/MEMBER_MANAGEMENT.md)
- [Weekly Data Collection](docs/WEEKLY_COLLECTION.md)
- [Query & AI Formatter](docs/QUERY_AND_AI.md) ⭐ New!
- [API Reference](docs/API_REFERENCE.md) (Coming soon)

## 🤝 Contributing

Issues and Pull Requests are always welcome!

### Contribution Guidelines

1. All code, comments, and documentation must be in English
2. Follow the project rules in `.cursorrules`
3. Write tests for new features
4. Update documentation when needed
5. Use conventional commit messages

## 📝 License

MIT License

## 👥 Team

HR Data Analysis Team
