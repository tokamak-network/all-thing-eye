---
id: slack-socket-mode-offline-recovery
name: Slack Socket Mode Offline Message Recovery
description: Handle messages sent while Socket Mode bot was offline by checking conversation history on startup
source: ATI Support Bot missed message feature
triggers:
  - "socket mode offline"
  - "slack bot missed messages"
  - "DM not received"
  - "slack events lost"
  - "socket mode event queue"
quality: high
---

# Slack Socket Mode Offline Message Recovery

## The Insight

Unlike HTTP-based Event Subscriptions where Slack retries delivery, **Socket Mode events are NOT queued**. When your bot disconnects, events during that window are lost forever - but the messages themselves are still stored in Slack's conversation history. You can recover them by proactively checking history on startup.

## Why This Matters

Users expect their messages to be processed even if the bot had temporary downtime. Without recovery logic:
- User sends DM while bot is down
- User sees their message in chat history
- Bot never responds - user thinks it's broken

## Recognition Pattern

You need this skill when:
- Building a Slack bot with Socket Mode
- Bot runs on local machine (not 24/7 server)
- Bot processes DMs or specific messages that shouldn't be lost

## The Approach

**Principle**: On bot startup, check recent conversation history and process any messages that weren't handled.

### Implementation Steps:

1. **Track processed messages** - Store `slack_ts` (message timestamp) in your database when creating tickets/processing messages

2. **On startup, scan DM channels**:
```python
def check_missed_messages():
    # Get all DM conversations
    result = client.conversations_list(types="im", limit=100)

    # For each DM channel, get recent messages (last 24h)
    oldest = time.time() - (24 * 60 * 60)

    for channel in result["channels"]:
        history = client.conversations_history(
            channel=channel["id"],
            oldest=str(oldest),
            limit=50
        )

        for msg in history["messages"]:
            # Skip bot messages
            if msg.get("bot_id") or msg.get("subtype"):
                continue

            # Check if already processed (by slack_ts)
            existing = db.find_one({"slack_ts": msg["ts"]})
            if existing:
                continue

            # Process the missed message
            process_message(msg)

            # Notify user their message was handled
            client.chat_postMessage(
                channel=msg["user"],
                text="Your message sent while I was offline has been processed!"
            )
```

3. **Call on startup before starting the handler**:
```python
def run_slack_bot():
    check_missed_messages()  # Recover first
    handler = SocketModeHandler(app, APP_TOKEN)
    handler.start()
```

### Key Fields to Track:
- `slack_ts`: Message timestamp (unique identifier)
- `missed_while_offline: true`: Flag for analytics

## Example

```python
# In message handler - save slack_ts
db.support_tickets.insert_one({
    "ticket_id": ticket_id,
    "slack_ts": event.get("ts"),  # Critical for deduplication
    "created_at": datetime.utcnow()
})

# On startup - check and process missed
existing = db.support_tickets.find_one({"slack_ts": msg_ts})
if not existing:
    # This message was missed - process it now
```

The `slack_ts` field serves dual purpose: deduplication and enabling offline recovery.
