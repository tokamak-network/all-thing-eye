# Google Drive Plugin Setup Guide

This guide explains how to set up the Google Drive plugin for collecting Drive activity logs using Google Admin SDK.

## 📋 Prerequisites

- **Google Workspace Admin Account** (required)
- **Admin SDK API** enabled in Google Cloud Console
- Python packages (will be installed automatically)

---

## 🔧 Step 1: Google Cloud Project Setup

### 1.1 Create or Select a Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one

### 1.2 Enable Admin SDK API

1. Navigate to **APIs & Services** > **Library**
2. Search for **"Admin SDK API"**
3. Click **Enable**

**Direct link**: https://console.cloud.google.com/apis/library/admin.googleapis.com

---

## 🔑 Step 2: Create OAuth2 Credentials

### 2.1 Configure OAuth Consent Screen

1. Go to **APIs & Services** > **OAuth consent screen**
2. Select **Internal** (for Workspace users) or **External**
3. Fill in required fields:
   - App name: `All-Thing-Eye`
   - User support email: Your admin email
   - Developer contact: Your admin email
4. Click **Save and Continue**

### 2.2 Add Required Scopes

Click **Add or Remove Scopes** and add these scopes:

```
https://www.googleapis.com/auth/admin.reports.audit.readonly
https://www.googleapis.com/auth/admin.reports.usage.readonly
```

### 2.3 Create OAuth Client ID

1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth client ID**
3. Application type: **Desktop app**
4. Name: `All-Thing-Eye Desktop Client`
5. Click **Create**
6. **Download JSON** file (this is your `credentials.json`)

---

## 📁 Step 3: Place Credentials File

1. Copy the downloaded `credentials.json` to the project:

```bash
cp ~/Downloads/client_secret_*.json config/google_drive/credentials.json
```

2. The folder structure should look like:

```
all-thing-eye/
├── config/
│   └── google_drive/
│       ├── credentials.json       ← Place your credentials here
│       └── token_admin.pickle     ← Will be auto-generated on first run
```

---

## ⚙️ Step 4: Configure Plugin

Edit `config/config.yaml`:

```yaml
plugins:
  google_drive:
    enabled: true  # Set to true to enable
    credentials_path: "config/google_drive/credentials.json"
    token_path: "config/google_drive/token_admin.pickle"
    
    # Option 1: Collect for all users in organization
    target_users: []
    
    # Option 2: Collect for specific users only
    # target_users: 
    #   - "george@tokamak.network"
    #   - "kevin@tokamak.network"
    
    days_to_collect: 7  # Default: last 7 days
    
    # Member mapping (use same list as other plugins)
    member_list:
      - name: "George"
        email: "george@tokamak.network"
        google_email: "george@tokamak.network"  # If different from email
      - name: "Kevin"
        email: "kevin@tokamak.network"
```

---

## 🚀 Step 5: First Run & Authentication

### 5.1 Install Required Packages

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

Or install from requirements.txt:

```bash
pip install -r requirements.txt
```

### 5.2 Run Test Script

```bash
# Collect last 7 days for all users
python tests/test_google_drive_plugin.py

# Collect last 30 days
python tests/test_google_drive_plugin.py --days 30

# Collect for specific user
python tests/test_google_drive_plugin.py --user george@tokamak.network

# Collect for last complete week (Friday-Thursday KST)
python tests/test_google_drive_plugin.py --last-week
```

### 5.3 Complete OAuth Flow

1. A browser window will open automatically
2. **Sign in with a Google Workspace Admin account**
3. Review and grant the requested permissions
4. You'll see "The authentication flow has completed"
5. Close the browser and return to terminal

The token will be saved to `config/google_drive/token_admin.pickle` and reused for future runs.

---

## 📊 Collected Data

The plugin collects the following Drive activities:

### Activity Types

| Event Type | Description (Korean) |
|------------|---------------------|
| `create` | 생성 |
| `edit` | 편집 |
| `upload` | 업로드 |
| `download` | 다운로드 |
| `delete` | 삭제 |
| `trash` | 휴지통 이동 |
| `share` | 공유 |
| `move` | 이동 |
| `copy` | 복사 |
| `change_user_access` | 접근 권한 변경 |

### Document Types

| Type | Description (Korean) |
|------|---------------------|
| `document` | 문서 (Google Docs) |
| `spreadsheet` | 스프레드시트 (Google Sheets) |
| `presentation` | 프레젠테이션 (Google Slides) |
| `folder` | 폴더 |
| `file` | 파일 (other) |

### Database Schema

Data is stored in `data/databases/google_drive.db`:

#### Table: `drive_activities`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `timestamp` | TIMESTAMP | Activity time (UTC) |
| `user_email` | TEXT | User's email address |
| `action` | TEXT | Activity type (Korean) |
| `event_name` | TEXT | Raw event name from API |
| `doc_title` | TEXT | Document title |
| `doc_type` | TEXT | Document type (Korean) |
| `doc_id` | TEXT | Google Drive file ID |
| `raw_event` | TEXT | Full event JSON |
| `created_at` | TIMESTAMP | Record creation time |

---

## 🔒 Security Best Practices

### Protect Sensitive Files

Add these to `.gitignore` (already included):

```gitignore
# Google Drive OAuth credentials
config/google_drive/credentials.json
config/google_drive/token_admin.pickle
config/google_drive/*.json
config/google_drive/*.pickle
```

### Limit Access

- Only share `credentials.json` with authorized team members
- Store tokens securely (do not commit to version control)
- Use environment variables for sensitive paths if needed

---

## ❌ Troubleshooting

### Error: "403 Forbidden"

**Cause**: Not using a Google Workspace Admin account

**Solution**: 
1. Ensure you're logging in with an admin account
2. Check that the account has Admin SDK permissions
3. Delete `token_admin.pickle` and re-authenticate

### Error: "API not found"

**Cause**: Admin SDK API not enabled

**Solution**:
1. Go to https://console.cloud.google.com/apis/library/admin.googleapis.com
2. Click **Enable**
3. Wait a few minutes for the API to propagate

### Error: "Invalid credentials"

**Cause**: Wrong `credentials.json` file or expired token

**Solution**:
1. Re-download `credentials.json` from Google Cloud Console
2. Ensure it's placed in `config/google_drive/`
3. Delete `token_admin.pickle` and re-authenticate

### Error: "No activities found"

**Possible causes**:
1. Users had no Drive activity in the specified period
2. Target user email is incorrect
3. Not enough time has passed since activity (can take a few minutes to appear in logs)

---

## 📚 Related Documentation

- [Google Admin SDK Reports API](https://developers.google.com/admin-sdk/reports/v1/guides/overview)
- [OAuth 2.0 for Desktop Apps](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Drive Activity Event Names](https://developers.google.com/admin-sdk/reports/v1/appendix/activity/drive)

---

## 🔄 Integration with Other Plugins

Google Drive activities are automatically integrated with the member index:

```python
# Activities are stored in main.db with unified member IDs
SELECT 
    m.name,
    ma.activity_type,
    ma.timestamp,
    json_extract(ma.metadata, '$.doc_title') as doc_title
FROM member_activities ma
JOIN members m ON ma.member_id = m.id
WHERE ma.source_type = 'google_drive'
ORDER BY ma.timestamp DESC;
```

This allows cross-platform analysis (GitHub + Slack + Drive) in reports.

---

## 💡 Tips

1. **First Run**: Start with a small time range (e.g., 7 days) to test
2. **Large Organizations**: Use `target_users` to limit scope and reduce API calls
3. **Token Expiration**: Tokens last for ~7 days; they will auto-refresh when expired
4. **Rate Limits**: Admin SDK has generous limits, but for very large organizations, consider spreading collection over time

---

**Questions or Issues?** Check the [main README](../README.md) or consult with the project team.

