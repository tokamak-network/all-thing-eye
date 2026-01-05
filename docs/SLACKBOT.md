# All-Thing-Eye Slackbot Documentation

## Overview

All-Thing-Eye Slackbot integrates the MCP AI Agent with Slack, allowing team members to query activity data and schedule reports directly from Slack.

---

## Command Prefix Convention

**All slash commands MUST start with `ati-` prefix** to avoid conflicts with other bots in the workspace.

| Command | Description |
|---------|-------------|
| `/ati-schedule` | Open the scheduling modal to create recurring reports |

---

## Bot Interaction Methods

### 1. Direct Message (DM)
Send a message directly to the bot. No @mention required.

```
User: Who is the most active contributor this week?
Bot: Based on the data...
```

### 2. Channel Mention
Mention the bot in any channel where it's invited.

```
@All-Thing-Eye Who worked on project-ooo last week?
```

### 3. Slash Commands
Use slash commands for specific actions.

```
/ati-schedule    → Opens scheduling modal
```

### 4. App Home
Click on the bot in the sidebar to access the App Home with quick actions.

---

## Scheduled Reports

Users can set up recurring reports that are delivered to a channel or DM.

### Report Types
- **Daily Analysis**: Automated summary of GitHub and Slack activities for the last 24 hours
- **Custom Prompt**: User-defined AI prompt executed on schedule

### Schedule Configuration
- **Name**: Identifier for the schedule
- **Content Type**: Daily Analysis or Custom Prompt
- **Custom Prompt**: (Optional) The prompt to send to the AI agent
- **Execution Time**: Daily time in HH:MM format (workspace timezone)
- **Recipient**: Channel or DM to receive the report

---

## Backend Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/slack/events` | POST | Receives Slack events (mentions, DMs, app_home_opened) |
| `/api/v1/slack/commands` | POST | Handles slash commands |
| `/api/v1/slack/interactive` | POST | Handles modal submissions and button clicks |

---

## Required Slack App Configuration

### OAuth Scopes (Bot Token Scopes)
```
app_mentions:read    - Read @mentions
chat:write           - Send messages
im:history           - Read DM history
im:read              - Access DM metadata
im:write             - Send DMs
users:read           - Read user info
commands             - Add slash commands
```

### Event Subscriptions
```
app_mention          - When bot is @mentioned in a channel
message.im           - When bot receives a DM
app_home_opened      - When user opens App Home tab
```

### Slash Commands
| Command | Request URL | Description |
|---------|-------------|-------------|
| `/ati-schedule` | `https://your-domain.com/api/v1/slack/commands` | Schedule recurring reports |

### Interactivity & Shortcuts
- **Request URL**: `https://your-domain.com/api/v1/slack/interactive`
- **Shortcut Callback ID**: `open_schedule_shortcut` (for global shortcut)

---

## Environment Variables

```bash
# Required for Slackbot
SLACK_BOT_TOKEN=xoxb-...        # Bot User OAuth Token
SLACK_SIGNING_SECRET=...         # Signing Secret for request verification

# Required for AI responses
AI_API_KEY=...                   # Tokamak AI API key
AI_API_URL=https://api.toka.ngrok.app  # AI API endpoint
```

---

## Database Collections

### `slack_schedules`
Stores scheduled report configurations.

```javascript
{
  _id: ObjectId,
  member_id: "U1234567",           // Slack user ID who created
  name: "Daily Activity Summary",  // Schedule name
  channel_id: "C1234567",          // Target channel/DM
  content_type: "daily_analysis",  // or "custom_prompt"
  prompt: "...",                   // Custom prompt (optional)
  cron_expression: "0 9 * * *",    // Cron format (9:00 AM daily)
  is_active: true,
  created_at: ISODate,
  updated_at: ISODate
}
```

---

## Adding New Commands

When adding a new slash command:

1. **Slack API Dashboard**: Create the command with `/ati-` prefix
2. **Backend Code**: Add handler in `slack_bot.py`:
   ```python
   if command in ["/ati-newcommand"]:
       # Handle command
       return ""
   ```
3. **Documentation**: Update this file

---

## Troubleshooting

### Bot doesn't respond
1. Check Event Subscriptions URL is verified
2. Verify `app_mention` and `message.im` events are subscribed
3. Check backend logs for incoming events

### Commands don't work
1. Verify Request URL in Slash Commands settings
2. Check command matches exactly (case-sensitive)
3. Ensure bot has `commands` scope

### Scheduled reports not sending
1. Check `slack_schedules` collection for active schedules
2. Verify `SLACK_BOT_TOKEN` has `chat:write` permission
3. Check APScheduler logs in backend

---

## Development (Local Testing)

```bash
# Start backend
python -m uvicorn backend.main:app --reload --port 8000

# Start ngrok
ngrok http 8000

# Update Slack URLs with ngrok address
# Events: https://xxxx.ngrok-free.app/api/v1/slack/events
# Commands: https://xxxx.ngrok-free.app/api/v1/slack/commands
# Interactive: https://xxxx.ngrok-free.app/api/v1/slack/interactive
```

---

**Last Updated**: 2026-01-05
**Maintainer**: All-Thing-Eye Development Team

