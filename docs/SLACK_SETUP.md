# Slack Plugin Setup Guide

Complete guide for setting up the Slack data collection plugin.

---

## 📋 Prerequisites

- Slack workspace with Pro plan or higher
- Admin access to create Slack apps
- Bot will be invited to target channels

---

## 🔐 Required Bot Token Scopes

### Channel Access
| Scope | Description | Purpose |
|-------|-------------|---------|
| `channels:history` | Public channel messages | Team communication data |
| `channels:read` | Public channel list | Channel discovery |
| `groups:history` | Private channel messages | Project team channels |
| `groups:read` | Private channel list | Private channel discovery |

### User Information
| Scope | Description | Purpose |
|-------|-------------|---------|
| `users:read` | User information | Member activity analysis |
| `users:read.email` | User email addresses | Match with members.csv |

### Metadata
| Scope | Description | Purpose |
|-------|-------------|---------|
| `reactions:read` | Emoji reactions | Engagement analysis |
| `files:read` | File information | Shared resource tracking |

---

## 🚀 Step-by-Step Setup

### Step 1: Create Slack App

1. Go to https://api.slack.com/apps
2. Click **"Create New App"**
3. Select **"From scratch"**
4. App Name: `All-Thing-Eye Bot`
5. Choose your workspace
6. Click **"Create App"**

---

### Step 2: Add Bot Token Scopes

1. In the left sidebar, click **"OAuth & Permissions"**
2. Scroll to **"Scopes"** section
3. Under **"Bot Token Scopes"**, click **"Add an OAuth Scope"**
4. Add all required scopes:
   ```
   channels:history
   channels:read
   groups:history
   groups:read
   users:read
   users:read.email
   reactions:read
   files:read
   ```

---

### Step 3: Install App to Workspace

1. Scroll up to **"OAuth Tokens for Your Workspace"**
2. Click **"Install to Workspace"**
3. Review the permissions
4. Click **"Allow"**
5. Copy the **"Bot User OAuth Token"** (starts with `xoxb-`)

---

### Step 4: Configure Environment

Add the token to your `.env` file:

```bash
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_WORKSPACE=tokamak-network
SLACK_ENABLED=true
```

---

### Step 5: Invite Bot to Channels

The bot needs to be invited to each channel you want to collect data from.

#### For Public Channels:
```
/invite @all-thing-eye
```

#### For Private Channels:
1. Open the channel
2. Click the channel name at the top
3. Select "Integrations"
4. Click "Add apps"
5. Find and add "All-Thing-Eye Bot"

---

## 📊 Configure Target Channels

### Option A: Collect from All Channels (Default)

Leave `target_channels` empty in `config/config.yaml`:

```yaml
plugins:
  slack:
    enabled: true
    target_channels: []  # Collects from all channels bot is invited to
```

### Option B: Collect from Specific Channels

Specify channel names in `config/config.yaml`:

```yaml
plugins:
  slack:
    enabled: true
    target_channels:
      - general
      - dev
      - project-zkp
      - team-backend
```

**Recommended channels for HR analysis:**
- Development channels: `#dev`, `#backend`, `#frontend`
- Project channels: `#project-*`, `#team-*`
- General communication: `#general`, `#announcements`

---

## 🧪 Test the Setup

### Basic Test

```bash
# Test authentication and channel discovery
python tests/test_slack_plugin.py
```

### Test with Specific Channels

```bash
# Test with specific channels only
python tests/test_slack_plugin.py --channels general dev
```

### Test Last Week's Data

```bash
# Collect complete week data
python tests/test_slack_plugin.py --last-week
```

---

## 📅 Data Collection Period

Slack plugin follows the same weekly cycle as GitHub:

- **Weekly Cycle**: Friday 00:00:00 KST → Thursday 23:59:59 KST
- **Current Week**: Run anytime to collect current week data
- **Last Week**: Run with `--last-week` flag for complete week

```bash
# Current week (incomplete)
python tests/test_slack_plugin.py

# Last week (complete)
python tests/test_slack_plugin.py --last-week
```

---

## 🗄️ Database Schema

Data is stored in `slack.db` with the following tables:

### Main Tables

1. **slack_channels** - Channel information
2. **slack_users** - User profiles and emails
3. **slack_messages** - Message content and metadata
4. **slack_reactions** - Emoji reactions
5. **slack_links** - Extracted and classified links
6. **slack_files** - File metadata

### Query Examples

```sql
-- Get message count by channel
SELECT 
    c.name as channel_name,
    COUNT(m.ts) as message_count
FROM slack_messages m
JOIN slack_channels c ON m.channel_id = c.id
GROUP BY c.name
ORDER BY message_count DESC;

-- Find GitHub links shared in Slack
SELECT 
    l.url,
    l.link_type,
    l.repository_name,
    m.text,
    c.name as channel_name
FROM slack_links l
JOIN slack_messages m ON l.message_ts = m.ts
JOIN slack_channels c ON l.channel_id = c.id
WHERE l.link_type LIKE 'github%'
ORDER BY l.shared_at DESC;

-- Member message activity
SELECT 
    u.real_name,
    u.email,
    COUNT(m.ts) as messages,
    COUNT(DISTINCT m.channel_id) as channels
FROM slack_users u
JOIN slack_messages m ON u.id = m.user_id
WHERE u.is_bot = 0
GROUP BY u.id
ORDER BY messages DESC;
```

---

## 🔗 Link Classification

The plugin automatically extracts and classifies links:

### GitHub Links
- `github_pr`: Pull requests
- `github_issue`: Issues
- `github_commit`: Commits
- `github_repo`: Repository links
- `github_discussion`: Discussions

### Google Drive Links
- `gdrive_doc`: Google Docs
- `gdrive_sheet`: Google Sheets
- `gdrive_slide`: Google Slides
- `gdrive_folder`: Folders

### Notion Links
- `notion_page`: Notion pages
- `notion_database`: Notion databases

### Cross-Reference Example

```sql
-- GitHub PRs discussed in Slack
SELECT 
    s.text as slack_message,
    s.posted_at,
    sl.url,
    g.title as pr_title,
    g.state as pr_state
FROM slack_links sl
JOIN slack_messages s ON sl.message_ts = s.ts
JOIN github_pull_requests g 
    ON sl.resource_id = g.number 
    AND sl.repository_name = g.repository_name
WHERE sl.link_type = 'github_pr'
ORDER BY s.posted_at DESC;
```

---

## ⚠️ Important Notes

### Rate Limiting

Slack has API rate limits:
- **Tier 3 methods** (conversations.history): 50+ requests/minute
- The plugin automatically handles pagination
- Large workspaces may take 10-30 minutes to collect

### Historical Data

**Pro Plan Benefits:**
- ✅ Unlimited message history
- ✅ Bot can access all messages after being invited
- ✅ Past messages available (before bot invitation)

**Limitations:**
- ❌ Bot must be invited to each channel
- ❌ Deleted messages not accessible
- ❌ Message edit history not available

### Privacy Considerations

**Collected Data:**
- ✅ Channel messages (public & private)
- ✅ Thread conversations
- ✅ Reactions and file metadata
- ✅ Extracted links

**NOT Collected:**
- ❌ Direct messages (DMs)
- ❌ Private conversations between users
- ❌ Channels where bot is not invited

---

## 🔧 Troubleshooting

### Bot Token Not Found

**Error**: `SLACK_BOT_TOKEN not found in environment`

**Solution**:
1. Check `.env` file exists in project root
2. Verify token format: `SLACK_BOT_TOKEN=xoxb-...`
3. Restart your terminal/IDE

---

### Missing Permissions

**Error**: `missing_scope` or permission denied

**Solution**:
1. Go to Slack App settings
2. Check "OAuth & Permissions" > "Bot Token Scopes"
3. Ensure all 8 required scopes are added
4. **Reinstall** the app to workspace
5. Get new token

---

### Channel Not Found

**Error**: Channel appears empty or not found

**Solution**:
1. Ensure bot is invited to the channel: `/invite @all-thing-eye`
2. For private channels, admin must manually add the bot
3. Check `target_channels` spelling in config.yaml

---

### No Historical Messages

**Issue**: Bot only sees recent messages

**Solution**:
- Pro plan: Should see all history after invitation
- Check date range parameters in test script
- Verify bot was invited before the target period

---

## 📊 Member Matching

Slack users are matched to `members.csv` by email:

### members.csv Format

```csv
name,email,github_id,slack_id,notion_id
Ale,ale@tokamak.network,SonYoungsung,U01ABC123,ale@tokamak.network
Kevin,kevin@tokamak.network,ggs134,U01XYZ789,kevin@tokamak.network
```

### Automatic Matching

The plugin matches Slack users to members by:
1. **Primary**: Slack User ID (`slack_id` column)
2. **Fallback**: Email address (`email` column)

**Email must match** between:
- Slack user profile email
- members.csv email column

---

## 🚀 Next Steps

After successful setup:

1. **Test with sample channels** (1-2 channels first)
2. **Verify data** in `data/databases/slack.db`
3. **Invite bot to all target channels**
4. **Run full collection** for last week
5. **Setup automated collection** (daily/weekly)

---

## 📖 Related Documentation

- [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) - Slack database schema
- [MEMBER_MANAGEMENT.md](./MEMBER_MANAGEMENT.md) - Member list configuration
- [WEEKLY_COLLECTION.md](./WEEKLY_COLLECTION.md) - Weekly collection cycle
- [QUERY_AND_AI.md](./QUERY_AND_AI.md) - Query and AI integration

---

## 🆘 Getting Help

If you encounter issues:

1. Check Slack API status: https://status.slack.com
2. Review Slack API docs: https://api.slack.com/methods
3. Check bot permissions in Slack app settings
4. Verify token is valid and not expired

---

**Remember**: The bot can only access channels it's invited to, and must have all required scopes!

