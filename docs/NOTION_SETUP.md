# Notion Plugin Setup Guide

This guide will help you set up the Notion plugin for All-Thing-Eye to collect team activity data from your Notion workspace.

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Create Notion Integration](#create-notion-integration)
3. [Configure Integration](#configure-integration)
4. [Share Pages with Integration](#share-pages-with-integration)
5. [Update Configuration](#update-configuration)
6. [Test Connection](#test-connection)
7. [Troubleshooting](#troubleshooting)

---

## ✅ Prerequisites

- Admin access to your Notion workspace
- Python 3.12+ installed
- `notion-client` package installed (included in `requirements.txt`)

---

## 🔧 Create Notion Integration

### Step 1: Go to Notion Integrations Page

1. Visit [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **"+ New integration"** button

### Step 2: Configure Integration Settings

Fill in the following information:

- **Name**: `All-Thing-Eye` (or any name you prefer)
- **Logo**: Optional
- **Associated workspace**: Select your workspace
- **Type**: **Internal Integration**

### Step 3: Set Capabilities

Under **Capabilities**, enable:

- ✅ **Read content**
- ✅ **Read comments**
- ✅ **Read user information including email addresses**
- ❌ **Update content** (not needed)
- ❌ **Insert content** (not needed)

### Step 4: Get Integration Token

1. After creating the integration, you'll see a **"Internal Integration Token"**
2. Click **"Show"** and **copy the token**
3. It will look like: `secret_aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890`

⚠️ **Keep this token secure!** Never commit it to version control.

---

## 🔐 Configure Integration

### Step 1: Add Token to Environment Variables

Add the following to your `.env` file:

```bash
# Notion Plugin
NOTION_ENABLED=true
NOTION_TOKEN=secret_your_actual_token_here
NOTION_WORKSPACE_ID=your_workspace_id  # Optional
```

### Step 2: Update `config/config.yaml`

The Notion plugin configuration should already be in `config/config.yaml`:

```yaml
plugins:
  notion:
    enabled: ${NOTION_ENABLED:true}
    token: ${NOTION_TOKEN}
    workspace_id: ${NOTION_WORKSPACE_ID}  # Optional
    days_to_collect: 7
    rate_limit: 3  # requests per second
    collection:
      pages: true
      databases: true
      comments: true
    member_list:
```

---

## 📤 Share Pages with Integration

**Important:** Notion integrations can only access pages that are explicitly shared with them.

### Option 1: Share Specific Pages

1. Open a page you want to track in Notion
2. Click **"..."** (more options) in the top right
3. Scroll to **"Connections"** or **"Add connections"**
4. Select **"All-Thing-Eye"** (or your integration name)
5. Repeat for each page/database you want to track

### Option 2: Share Parent Page (Recommended)

If you share a parent page, all its child pages will also be accessible:

1. Share your workspace's **main team page** with the integration
2. All nested pages will automatically be included

### Option 3: Share Entire Workspace (Advanced)

Some Notion plans allow workspace-wide integration access. Check your plan's documentation.

---

## ⚙️ Update Configuration

### Step 1: Update `members.yaml`

Add Notion user IDs for each team member:

```yaml
members:
  - name: "Kevin"
    email: "kevin@tokamak.network"
    github_id: "ggs134"
    slack_id: "U075F3T4MRB"
    notion_id: "kevin@tokamak.network"  # Use email or Notion user ID
    google_email: "kevin@tokamak.network"

  - name: "Monica"
    email: "monica@tokamak.network"
    slack_id: "monica@tokamak.network"
    notion_id: "monica@tokamak.network"
    
  # Add all team members...
```

**Finding Notion User IDs:**

Option A: Use email addresses (recommended)
- Notion API can match by email
- Simply use the same email as in `email` field

Option B: Use Notion user IDs
- Run the test script to see all workspace users
- Copy the user IDs from the output

---

## 🧪 Test Connection

### Step 1: Run Test Script

```bash
python tests/test_notion_plugin.py --days 7
```

### Step 2: Verify Output

You should see:

```
✅ Notion authentication successful: Your Name
📊 Collecting Notion data
   Period: 2025-11-05T00:00:00 ~ 2025-11-12T00:00:00

1️⃣ Fetching users...
   ✅ Found 10 users

2️⃣ Searching pages...
   ✅ Found 25 pages

3️⃣ Fetching databases...
   ✅ Found 5 databases

4️⃣ Fetching comments...
   ✅ Found 12 comments

✨ Test completed!
```

### Step 3: Check Database

```bash
sqlite3 data/databases/notion.db "SELECT * FROM notion_pages LIMIT 5;"
```

---

## 🔍 What Data is Collected

### Pages
- Page title
- Creation time and author
- Last edit time and editor
- Page URL
- Parent page/database
- Archive status

### Databases
- Database title
- Creation and edit information
- Database URL
- Properties schema (future feature)

### Comments
- Comment text
- Author and timestamp
- Parent page reference

### Users
- User name and email
- User type (person/bot)
- Avatar URL

---

## 📊 Collected Activities

The plugin tracks the following member activities:

| Activity Type | Description |
|---------------|-------------|
| `page_created` | Member created a new page |
| `page_edited` | Member edited an existing page |
| `database_created` | Member created a new database |
| `comment_added` | Member added a comment |

These activities are stored in the `member_activities` table for unified reporting.

---

## 🐛 Troubleshooting

### Error: "Authentication failed"

**Cause:** Invalid or missing Notion token

**Solution:**
1. Check that `NOTION_TOKEN` is set in `.env`
2. Verify the token is correct (starts with `secret_`)
3. Ensure the integration is still active in Notion settings

### Error: "No pages found"

**Cause:** Integration doesn't have access to any pages

**Solution:**
1. Share at least one page with the integration
2. Wait a few minutes for permissions to propagate
3. Ensure the page was updated within the collection period

### Error: "Rate limit exceeded"

**Cause:** Too many API requests

**Solution:**
1. Reduce `rate_limit` in `config.yaml`
2. Increase delay between requests
3. Collect data for shorter periods

### Warning: "Could not resolve member"

**Cause:** Notion user ID not found in `members.yaml`

**Solution:**
1. Run test script to see all workspace users
2. Add missing members to `members.yaml`
3. Use email addresses for automatic matching

---

## 📈 API Rate Limits

Notion API has rate limits:
- **3 requests per second** (default in our config)
- Longer delays for complex queries
- 429 error if exceeded

Our plugin automatically handles rate limiting, but you can adjust `rate_limit` in `config.yaml` if needed.

---

## 🔒 Security Best Practices

1. ✅ **Never commit `.env` file** to version control
2. ✅ **Use environment variables** for the token
3. ✅ **Limit integration capabilities** to read-only
4. ✅ **Share only necessary pages** with the integration
5. ✅ **Regularly audit** integration access
6. ✅ **Rotate tokens** periodically (e.g., every 6 months)

---

## 📚 Related Documentation

- [Notion API Documentation](https://developers.notion.com/)
- [Database Schema Reference](./DATABASE_SCHEMA.md)
- [Members Configuration](../config/members.yaml)
- [Project Rules](../README.md)

---

## 📞 Questions or Issues?

If you encounter problems:
1. Check this documentation
2. Review Notion API status page
3. Check application logs: `logs/app.log`
4. Consult with the development team

---

**Last Updated:** 2025-11-12  
**Version:** 1.0.0  
**Maintained by:** All-Thing-Eye Development Team

