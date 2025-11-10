# Member Management Guide

## Overview

Team members can be managed separately from the main configuration file for easier maintenance and collaboration.

## 📁 Member File Location

Place your member list file in the `config/` directory:

```
config/
├── config.yaml
├── members.yaml        # Preferred format
├── members.json        # Alternative format
└── members.csv         # Alternative format
```

The system automatically detects and loads the members file in this priority order:
1. `members.yaml` / `members.yml`
2. `members.json`
3. `members.csv`

## 📝 File Formats

### Option 1: YAML (Recommended)

**File**: `config/members.yaml`

```yaml
# Team members with their platform identifiers

- name: "John Doe"
  email: "john@company.com"
  github_id: "johndoe"
  slack_id: "U123ABC456"
  notion_id: "notion_user_id"

- name: "Jane Smith"
  email: "jane@company.com"
  github_id: "janesmith"
  slack_id: "U789XYZ012"
  notion_id: "notion_user_id"

# Add more members here
```

**Pros**:
- ✅ Human-readable and easy to edit
- ✅ Supports comments
- ✅ Clean syntax

### Option 2: JSON

**File**: `config/members.json`

```json
[
  {
    "name": "John Doe",
    "email": "john@company.com",
    "github_id": "johndoe",
    "slack_id": "U123ABC456",
    "notion_id": "notion_user_id"
  },
  {
    "name": "Jane Smith",
    "email": "jane@company.com",
    "github_id": "janesmith",
    "slack_id": "U789XYZ012",
    "notion_id": "notion_user_id"
  }
]
```

**Pros**:
- ✅ Programmatically easy to generate/parse
- ✅ Widely supported

### Option 3: CSV

**File**: `config/members.csv`

```csv
name,email,github_id,slack_id,notion_id
John Doe,john@company.com,johndoe,U123ABC456,notion_user_id
Jane Smith,jane@company.com,janesmith,U789XYZ012,notion_user_id
```

**Pros**:
- ✅ Easy to edit in Excel/Google Sheets
- ✅ Simple import/export
- ✅ Good for bulk updates

**Cons**:
- ❌ No support for comments
- ❌ All values are strings

## 🔧 Field Descriptions

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `name` | ✅ Yes | Display name (primary identifier) | "John Doe" |
| `email` | ⚠️ Recommended | Email address for identification | "john@company.com" |
| `github_id` | Optional | GitHub username | "johndoe" |
| `slack_id` | Optional | Slack user ID (starts with U) | "U123ABC456" |
| `notion_id` | Optional | Notion user ID | "notion_user_id" |

**Note**: At least one platform identifier (github_id, slack_id, or notion_id) should be provided.

## 🚀 Quick Start

### Using YAML (Recommended)

```bash
# 1. Copy the example file
cp config/members.example.yaml config/members.yaml

# 2. Edit with your team members
nano config/members.yaml

# 3. Test the configuration
python test_github.py
```

### Using CSV (Easiest for Bulk)

```bash
# 1. Create or edit CSV file
nano config/members.csv

# Or edit in Excel/Google Sheets and save as CSV

# 2. Ensure proper encoding (UTF-8)
# 3. Test the configuration
python test_github.py
```

## 📋 How It Works

1. **Auto-Detection**: The system automatically looks for member files in `config/` directory
2. **Auto-Loading**: Members are loaded when the configuration is initialized
3. **Plugin Integration**: Members are automatically distributed to relevant plugins:
   - GitHub plugin gets members with `github_id`
   - Slack plugin gets members with `slack_id`
   - Notion plugin gets members with `notion_id`

## 🔄 Updating Members

### Adding a New Member

**YAML**:
```yaml
- name: "New Member"
  email: "newmember@company.com"
  github_id: "newmember_github"
  slack_id: "U999NEW999"
  notion_id: null
```

**CSV**:
```csv
New Member,newmember@company.com,newmember_github,U999NEW999,
```

### Removing a Member

Simply delete or comment out their entry:

**YAML**:
```yaml
# - name: "Former Member"  # Commented out
#   email: "former@company.com"
#   github_id: "formermember"
```

**CSV**: Delete the entire row

### Updating Member Information

Just edit the relevant fields and save the file.

## 🔍 Finding Slack User IDs

To get Slack user IDs:

1. Open Slack
2. Click on the person's profile
3. Click "More" → "Copy member ID"
4. The ID looks like: `U123ABC456`

Or use Slack API:
```bash
curl -H "Authorization: Bearer YOUR_SLACK_TOKEN" \
  https://slack.com/api/users.list
```

## 🔍 Finding GitHub Usernames

GitHub username is the part after `github.com/`:
- Profile URL: `https://github.com/johndoe`
- Username: `johndoe`

## 🔍 Finding Notion User IDs

1. Open Notion
2. Share a page with the user
3. Use Notion API to get user list
4. Or check the Notion developer console

## 🛠 Fallback to config.yaml

If no external members file is found, you can still define members directly in `config.yaml`:

```yaml
plugins:
  github:
    member_list:
      - name: "John Doe"
        githubId: "johndoe"
        email: "john@company.com"
```

**Note**: The external file takes precedence if both exist.

## 🔐 Security Best Practices

1. ✅ **Keep member files in version control** (they don't contain secrets)
2. ✅ **Use consistent naming** across platforms
3. ✅ **Validate email formats** before adding
4. ✅ **Review changes** before committing
5. ⚠️ **Be careful with PII** (Personal Identifiable Information)

## 📊 Member List Statistics

You can check loaded members programmatically:

```python
from src.core.config import get_config

config = get_config()
members = config.get_members()

print(f"Total members: {len(members)}")
for member in members:
    print(f"  - {member['name']}: GitHub={member.get('github_id')}, Slack={member.get('slack_id')}")
```

## 🐛 Troubleshooting

### Members not loading

**Problem**: "⚠️ Loaded 0 members"

**Solutions**:
1. Check file exists: `ls -la config/members.*`
2. Check file format is valid (YAML/JSON syntax)
3. Check file permissions: `chmod 644 config/members.yaml`
4. Check encoding is UTF-8

### GitHub plugin not finding members

**Problem**: No commits collected despite members defined

**Solutions**:
1. Verify `github_id` matches exact GitHub username (case-sensitive)
2. Check GitHub token has access to the organization
3. Ensure members have commits in the date range
4. Check organization name is correct

### Duplicate members

**Problem**: Same member appears multiple times

**Solutions**:
1. Use unique `name` for each member
2. Check for duplicate entries in members file
3. Ensure one member = one entry

## 💡 Tips & Best Practices

1. **Use YAML for human editing** - Easy to read and maintain
2. **Use CSV for bulk operations** - Edit in spreadsheet software
3. **Use JSON for automation** - Easy to generate programmatically
4. **Keep it sorted** - Alphabetically by name for easy lookup
5. **Add comments** - Document special cases or temporary members
6. **Version control** - Track member changes over time
7. **Regular reviews** - Update when people join/leave

## 🔄 Migration from config.yaml

If you have members defined in `config.yaml`, migrate them:

```bash
# 1. Create new members.yaml file
cat > config/members.yaml << 'EOF'
# Migrated from config.yaml
EOF

# 2. Copy member entries (manually or with script)

# 3. Remove member_list from config.yaml

# 4. Test
python test_github.py
```

## 📚 Related Documentation

- [GitHub Setup Guide](GITHUB_SETUP.md)
- [Configuration Guide](../config/config.yaml)
- [Quick Start Guide](QUICK_START.md)

