# GitHub Plugin Setup Guide

## 🚀 Quick Start

### 1. GitHub Personal Access Token

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token" (classic)
3. Give it a descriptive name (e.g., "All-Thing-Eye Data Collection")
4. Select scopes:
   - ✅ `repo` (Full control of private repositories)
   - ✅ `read:org` (Read org and team membership)
   - ✅ `read:user` (Read user profile data)
5. Click "Generate token"
6. **Copy the token immediately** (you won't be able to see it again)

### 2. Environment Variables

Add to your `.env` file:

```env
# GitHub Configuration
GITHUB_ENABLED=true
GITHUB_TOKEN=ghp_your_github_personal_access_token
GITHUB_ORG=your-organization-name
```

### 3. Configure Team Members

**Easy Way**: Create `config/members.yaml` (recommended):

```bash
# Copy the example file
cp config/members.example.yaml config/members.yaml

# Edit with your team members
nano config/members.yaml
```

```yaml
- name: "John Doe"
  email: "john@company.com"
  github_id: "johndoe"
  slack_id: null
  notion_id: null

- name: "Jane Smith"
  email: "jane@company.com"
  github_id: "janesmith"
  slack_id: null
  notion_id: null
```

**Alternative**: You can also use `members.json` or `members.csv` format.

**Important**: The `github_id` must match the exact GitHub username.

For detailed member management guide, see [MEMBER_MANAGEMENT.md](MEMBER_MANAGEMENT.md)

### 4. Test the Plugin

```bash
# Run the test script
python tests/test_github_plugin.py
```

## 📊 What Data is Collected?

### By Default (Fast)

- **Commits**: SHA, message, author, timestamp, additions/deletions, changed files
- **Pull Requests**: Number, title, state, author, timestamps
- **Issues**: Number, title, state, author, timestamps
- **Repositories**: Name, description, last push date

### Optional: Code Diffs (Slow)

If you enable `include_diff: true`, the system will also collect:

- **File changes**: Which files were modified
- **Patches**: Actual code diffs (what lines were added/removed)

⚠️ **Warning**: Enabling diffs makes **MANY more API calls** and takes much longer!

```yaml
github:
  collection:
    include_diff: true  # Only enable if you need detailed code analysis
```

## 🔍 Data Structure

### Databases Created

1. **`data/databases/main.db`** - Member index and unified activities
2. **`data/databases/github.db`** - GitHub-specific data

### GitHub Database Tables

- `github_members` - Team members from your member_list
- `github_repositories` - Organization repositories
- `github_commits` - Individual commits with stats
- `github_commit_files` - File changes per commit (if include_diff enabled)
- `github_pull_requests` - Pull requests
- `github_issues` - Issues

### Member Index Tables

- `members` - Unified member list
- `member_identifiers` - Mapping of source-specific IDs to member IDs
- `member_activities` - Normalized activities from all sources

## 🎯 Usage Examples

### Collect Last 7 Days

```python
from datetime import datetime, timedelta
from src.core.config import get_config
from src.core.database import DatabaseManager
from src.core.plugin_loader import PluginLoader

# Setup
config = get_config()
db = DatabaseManager(config.database_url)
loader = PluginLoader(config, db)
plugins = loader.load_all_plugins()

# Get GitHub plugin
github = loader.get_plugin('github')
github.authenticate()

# Collect data
end_date = datetime.now()
start_date = end_date - timedelta(days=7)
data = github.collect_data(start_date, end_date)
```

### Query Member Activities

```python
from src.core.member_index import MemberIndex

# Get member activities
member_index = MemberIndex(db)
activities = member_index.get_member_activities(
    member_name="John Doe",
    source_type="github",
    start_date=start_date,
    end_date=end_date
)

for activity in activities:
    print(f"{activity['timestamp']}: {activity['activity_type']}")
    print(f"  {activity['metadata']}")
```

### SQL Queries

```bash
# Connect to GitHub database
sqlite3 data/databases/github.db

# Top committers
SELECT author_login, COUNT(*) as commit_count, SUM(additions) as total_additions
FROM github_commits
GROUP BY author_login
ORDER BY commit_count DESC;

# Recent pull requests
SELECT number, title, author_login, created_at
FROM github_pull_requests
ORDER BY created_at DESC
LIMIT 10;
```

## 🔧 Advanced Configuration

### Filter Specific Repositories

```yaml
github:
  collection:
    repositories:
      - "backend-api"
      - "frontend-app"
      - "mobile-app"
```

If empty (`[]`), collects from all organization repositories.

### Rate Limiting

GitHub API limits:

- **Authenticated**: 5,000 requests per hour
- **GraphQL**: 5,000 points per hour

The plugin automatically:

- ✅ Retries on temporary failures (502, 503, 504)
- ✅ Waits between requests to avoid hitting limits
- ✅ Uses exponential backoff on errors

### Member List vs. API

You can either:

1. **Use member_list** (recommended): Manually define team members

   - Faster, no extra API calls
   - You control who is tracked
   - Works with external contributors

2. **Use GitHub API**: Auto-fetch organization members
   - Leave `member_list` empty
   - Only gets official organization members
   - May miss external contributors

## 🐛 Troubleshooting

### Authentication Failed

```
❌ GitHub authentication failed
```

**Solutions**:

1. Check token is valid: `https://github.com/settings/tokens`
2. Verify token has correct scopes (repo, read:org, read:user)
3. Check token hasn't expired

### No Data Collected

```
📊 Collection Results:
   Commits: 0
   Pull Requests: 0
```

**Possible causes**:

1. **Date range**: No activity in selected period
2. **Organization name**: Check `GITHUB_ORG` is correct
3. **Member IDs**: Verify `githubId` matches exact GitHub usernames
4. **Archived repos**: Archived repositories are skipped

### Rate Limit Exceeded

```
⚠️  GitHub API 403 error: rate limit exceeded
```

**Solutions**:

1. Wait for rate limit to reset (check headers)
2. Reduce date range
3. Disable `include_diff` option
4. Use multiple tokens (rotate them)

### Repository Access Denied

```
❌ [repo-name] Failed to fetch commits: 404
```

**Causes**:

- Token doesn't have access to private repositories
- Repository was deleted or renamed
- Organization name is incorrect

## 📈 Performance Tips

### Faster Collection

1. ✅ **Disable diffs**: Set `include_diff: false`
2. ✅ **Shorter date ranges**: Collect 7 days instead of 30
3. ✅ **Filter repositories**: Only collect from active repos
4. ✅ **Use member_list**: Don't fetch org members via API

### Recommended Schedule

- **Daily collection**: Last 2 days (to catch late commits)
- **Weekly full sync**: Last 7 days
- **Monthly report**: Last 30 days

## 🔐 Security Best Practices

1. ✅ **Never commit `.env`** file (use `.env.example` as template)
2. ✅ **Use token with minimum required scopes**
3. ✅ **Rotate tokens periodically** (every 3-6 months)
4. ✅ **Revoke unused tokens** immediately
5. ✅ **Store databases securely** (they contain commit data)

## 📚 Related Documentation

- [GitHub GraphQL API](https://docs.github.com/en/graphql)
- [GitHub REST API](https://docs.github.com/en/rest)
- [Personal Access Tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
