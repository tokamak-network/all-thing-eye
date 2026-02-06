#!/usr/bin/env python3
"""
ATI Support Bot (Socket Mode)

Slack bot for handling support tickets with Claude Code integration.
Runs locally without ngrok/tunnel.

Usage:
    python scripts/support_bot_socket.py

Environment Variables:
    SLACK_SUPPORT_BOT_TOKEN: Bot User OAuth Token (xoxb-...)
    SLACK_SUPPORT_APP_TOKEN: App-Level Token (xapp-...)
    SLACK_SUPPORT_ADMIN_ID: Admin Slack User ID
    CLAUDE_WEBHOOK_URL: Local webhook server URL (default: http://localhost:9999/ticket)
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env file
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import httpx
from motor.motor_asyncio import AsyncIOMotorClient

# Environment
BOT_TOKEN = os.environ.get("SLACK_SUPPORT_BOT_TOKEN", "")
APP_TOKEN = os.environ.get("SLACK_SUPPORT_APP_TOKEN", "")
ADMIN_ID = os.environ.get("SLACK_SUPPORT_ADMIN_ID", "")
CLAUDE_WEBHOOK_URL = os.environ.get("CLAUDE_WEBHOOK_URL", "http://localhost:9999/ticket")
MONGODB_URI = os.environ.get("MONGODB_URI", "")
MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "ati")

# Initialize Slack app
app = App(token=BOT_TOKEN)

# MongoDB client (lazy init)
_mongo_client = None
_db = None


def get_db():
    """Get MongoDB database."""
    global _mongo_client, _db
    if _db is None:
        _mongo_client = AsyncIOMotorClient(MONGODB_URI)
        _db = _mongo_client[MONGODB_DATABASE]
    return _db


async def generate_ticket_id() -> str:
    """Generate next ticket ID."""
    db = get_db()
    latest = await db.support_tickets.find_one(
        {}, sort=[("created_at", -1)], projection={"ticket_id": 1}
    )
    if latest and latest.get("ticket_id"):
        try:
            num = int(latest["ticket_id"].split("-")[1])
            return f"TKT-{num + 1:03d}"
        except:
            pass
    return "TKT-001"


async def create_ticket(reporter_id: str, reporter_name: str, category: str, title: str, description: str) -> dict:
    """Create a support ticket in MongoDB."""
    db = get_db()
    ticket_id = await generate_ticket_id()
    now = datetime.utcnow()

    ticket = {
        "ticket_id": ticket_id,
        "reporter_id": reporter_id,
        "reporter_name": reporter_name,
        "category": category,
        "title": title,
        "description": description,
        "status": "open",
        "messages": [{"from_type": "reporter", "content": description, "timestamp": now}],
        "created_at": now,
        "updated_at": now,
    }

    await db.support_tickets.insert_one(ticket)
    print(f"✅ Created ticket {ticket_id}")
    return ticket


async def get_open_ticket(user_id: str) -> dict:
    """Get user's open ticket."""
    db = get_db()
    return await db.support_tickets.find_one({
        "reporter_id": user_id,
        "status": {"$in": ["open", "in_progress"]}
    })


async def add_message_to_ticket(ticket_id: str, from_type: str, content: str):
    """Add message to existing ticket."""
    db = get_db()
    await db.support_tickets.update_one(
        {"ticket_id": ticket_id},
        {
            "$push": {"messages": {"from_type": from_type, "content": content, "timestamp": datetime.utcnow()}},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )


async def update_ticket_status(ticket_id: str, status: str):
    """Update ticket status."""
    db = get_db()
    update = {"status": status, "updated_at": datetime.utcnow()}
    if status in ["resolved", "closed"]:
        update["resolved_at"] = datetime.utcnow()
    await db.support_tickets.update_one({"ticket_id": ticket_id}, {"$set": update})


async def get_ticket(ticket_id: str) -> dict:
    """Get ticket by ID."""
    db = get_db()
    return await db.support_tickets.find_one({"ticket_id": ticket_id})


def send_to_claude_webhook(endpoint: str, data: dict):
    """Send request to Claude webhook server (sync for Slack handlers)."""
    url = CLAUDE_WEBHOOK_URL.replace("/ticket", endpoint)
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=data)
            return resp.status_code == 200
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return False


# =============================================================================
# Slash Command: /ati-support
# =============================================================================

@app.command("/ati-support")
def handle_support_command(ack, body, client):
    """Open ticket creation modal."""
    ack()

    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "ticket_modal",
            "title": {"type": "plain_text", "text": "ATI Support"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "🎫 *Submit a Support Ticket*"},
                },
                {"type": "divider"},
                {
                    "type": "input",
                    "block_id": "category",
                    "element": {
                        "type": "static_select",
                        "action_id": "input",
                        "options": [
                            {"text": {"type": "plain_text", "text": "🐛 Bug Report"}, "value": "bug"},
                            {"text": {"type": "plain_text", "text": "✨ Feature Request"}, "value": "feature"},
                            {"text": {"type": "plain_text", "text": "❓ Question"}, "value": "question"},
                        ],
                    },
                    "label": {"type": "plain_text", "text": "Category"},
                },
                {
                    "type": "input",
                    "block_id": "title",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "input",
                        "placeholder": {"type": "plain_text", "text": "Brief summary"},
                        "max_length": 150,
                    },
                    "label": {"type": "plain_text", "text": "Title"},
                },
                {
                    "type": "input",
                    "block_id": "description",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "input",
                        "multiline": True,
                        "placeholder": {"type": "plain_text", "text": "Describe in detail..."},
                    },
                    "label": {"type": "plain_text", "text": "Description"},
                },
            ],
        },
    )


# =============================================================================
# Modal Submit: Ticket Creation
# =============================================================================

@app.view("ticket_modal")
def handle_ticket_submit(ack, body, client, view):
    """Handle ticket modal submission."""
    ack()

    user_id = body["user"]["id"]
    values = view["state"]["values"]

    category = values["category"]["input"]["selected_option"]["value"]
    title = values["title"]["input"]["value"]
    description = values["description"]["input"]["value"]

    # Get user info
    user_info = client.users_info(user=user_id)
    reporter_name = user_info["user"]["real_name"] or user_info["user"]["name"]

    # Create ticket (async in thread)
    import threading

    def create_and_notify():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        ticket = loop.run_until_complete(
            create_ticket(user_id, reporter_name, category, title, description)
        )

        # Notify reporter
        client.chat_postMessage(
            channel=user_id,
            text=f"🎫 Ticket *{ticket['ticket_id']}* created!\n\n*{title}*\n\nWaiting for admin approval.",
        )

        # Notify admin
        if ADMIN_ID:
            notify_admin_new_ticket(client, ticket)

        # Send to Claude webhook
        send_to_claude_webhook("/ticket", {
            "ticket_id": ticket["ticket_id"],
            "category": category,
            "title": title,
            "description": description,
            "reporter_name": reporter_name,
        })

    threading.Thread(target=create_and_notify).start()


def notify_admin_new_ticket(client, ticket):
    """Send admin notification with approval buttons."""
    emoji = {"bug": "🐛", "feature": "✨", "question": "❓"}.get(ticket["category"], "🎫")

    client.chat_postMessage(
        channel=ADMIN_ID,
        text=f"New ticket: {ticket['ticket_id']}",
        blocks=[
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🎫 New Ticket: {ticket['ticket_id']}", "emoji": True},
            },
            {"type": "divider"},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*{emoji} Category:*\n{ticket['category']}"},
                    {"type": "mrkdwn", "text": f"*👤 Reporter:*\n<@{ticket['reporter_id']}>"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*📝 Title:*\n{ticket['title']}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Description:*\n>{ticket['description'][:300]}"},
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Approve", "emoji": True},
                        "style": "primary",
                        "action_id": f"approve_{ticket['ticket_id']}",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Reject", "emoji": True},
                        "style": "danger",
                        "action_id": f"reject_{ticket['ticket_id']}",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "💬 Reply", "emoji": True},
                        "action_id": f"reply_{ticket['ticket_id']}",
                    },
                ],
            },
        ],
    )


# =============================================================================
# Button Actions
# =============================================================================

@app.action({"action_id": "approve_"})
def handle_approve(ack, body, client, action):
    """Handle approve button."""
    ack()
    ticket_id = action["action_id"].replace("approve_", "")

    # Send to Claude webhook
    if send_to_claude_webhook("/approve", {"ticket_id": ticket_id}):
        client.chat_postMessage(
            channel=ADMIN_ID,
            text=f"🚀 *[{ticket_id}]* Development started!",
        )
    else:
        client.chat_postMessage(
            channel=ADMIN_ID,
            text=f"❌ Failed to start development for {ticket_id}. Is webhook server running?",
        )


@app.action({"action_id": "reject_"})
def handle_reject(ack, body, client, action):
    """Handle reject button."""
    ack()
    ticket_id = action["action_id"].replace("reject_", "")

    send_to_claude_webhook("/reject", {"ticket_id": ticket_id})

    # Update ticket status
    loop = asyncio.new_event_loop()
    loop.run_until_complete(update_ticket_status(ticket_id, "closed"))

    client.chat_postMessage(
        channel=ADMIN_ID,
        text=f"❌ *[{ticket_id}]* Rejected",
    )


@app.action({"action_id": "reply_"})
def handle_reply_button(ack, body, client, action):
    """Open reply modal."""
    ack()
    ticket_id = action["action_id"].replace("reply_", "")

    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "reply_modal",
            "private_metadata": ticket_id,
            "title": {"type": "plain_text", "text": "Reply to Ticket"},
            "submit": {"type": "plain_text", "text": "Send"},
            "blocks": [
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": f"*Ticket:* {ticket_id}"}],
                },
                {
                    "type": "input",
                    "block_id": "message",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "input",
                        "multiline": True,
                    },
                    "label": {"type": "plain_text", "text": "Message"},
                },
            ],
        },
    )


@app.view("reply_modal")
def handle_reply_submit(ack, body, client, view):
    """Handle reply modal submission."""
    ack()

    ticket_id = view["private_metadata"]
    message = view["state"]["values"]["message"]["input"]["value"]

    def send_reply():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        ticket = loop.run_until_complete(get_ticket(ticket_id))
        if ticket:
            loop.run_until_complete(add_message_to_ticket(ticket_id, "admin", message))

            # Notify reporter
            client.chat_postMessage(
                channel=ticket["reporter_id"],
                text=f"💬 *Admin reply on [{ticket_id}]*\n\n{message}",
            )

    import threading
    threading.Thread(target=send_reply).start()


# Review/Revert buttons (from completion notification)
@app.action({"action_id": "review_"})
def handle_review(ack, body, client, action):
    """Start review servers."""
    ack()
    ticket_id = action["action_id"].replace("review_", "")

    if send_to_claude_webhook("/review", {"ticket_id": ticket_id}):
        client.chat_postMessage(
            channel=ADMIN_ID,
            text=f"🔍 *[{ticket_id}]* Review servers starting...\n\n• Frontend: http://localhost:3099\n• Backend: http://localhost:8099",
        )


@app.action({"action_id": "revert_"})
def handle_revert(ack, body, client, action):
    """Revert last commit."""
    ack()
    ticket_id = action["action_id"].replace("revert_", "")

    if send_to_claude_webhook("/revert", {"ticket_id": ticket_id}):
        client.chat_postMessage(
            channel=ADMIN_ID,
            text=f"🗑️ *[{ticket_id}]* Reverted!",
        )


# =============================================================================
# DM Messages
# =============================================================================

@app.event("message")
def handle_dm(event, client, say):
    """Handle DM messages - create ticket or add to existing."""
    # Ignore bot messages
    if event.get("bot_id") or event.get("subtype"):
        return

    # Only handle DMs
    channel_type = event.get("channel_type", "")
    if channel_type != "im":
        return

    user_id = event.get("user")
    text = event.get("text", "").strip()

    if not text:
        return

    def process_dm():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Get user info
        user_info = client.users_info(user=user_id)
        reporter_name = user_info["user"]["real_name"] or user_info["user"]["name"]

        # Check for existing ticket
        existing = loop.run_until_complete(get_open_ticket(user_id))

        if existing:
            # Add to existing ticket
            loop.run_until_complete(add_message_to_ticket(existing["ticket_id"], "reporter", text))
            say(f"✅ Message added to *{existing['ticket_id']}*")

            # Notify admin
            if ADMIN_ID:
                client.chat_postMessage(
                    channel=ADMIN_ID,
                    text=f"💬 New message on *{existing['ticket_id']}* from {reporter_name}:\n>{text[:200]}",
                )
        else:
            # Create new ticket from DM
            title = text[:100]
            ticket = loop.run_until_complete(
                create_ticket(user_id, reporter_name, "question", title, text)
            )
            say(f"🎫 Ticket *{ticket['ticket_id']}* created!\n\nYou can add more details by sending messages here.")

            if ADMIN_ID:
                notify_admin_new_ticket(client, ticket)

            send_to_claude_webhook("/ticket", {
                "ticket_id": ticket["ticket_id"],
                "category": "question",
                "title": title,
                "description": text,
                "reporter_name": reporter_name,
            })

    import threading
    threading.Thread(target=process_dm).start()


# =============================================================================
# Main
# =============================================================================

def main():
    if not BOT_TOKEN:
        print("❌ SLACK_SUPPORT_BOT_TOKEN not set")
        sys.exit(1)
    if not APP_TOKEN:
        print("❌ SLACK_SUPPORT_APP_TOKEN not set")
        sys.exit(1)

    print(f"""
╔════════════════════════════════════════════════════════════╗
║            ATI Support Bot (Socket Mode)                   ║
╠════════════════════════════════════════════════════════════╣
║  Admin: {ADMIN_ID or 'Not set'}
║  Claude Webhook: {CLAUDE_WEBHOOK_URL}
║  MongoDB: {'Connected' if MONGODB_URI else 'Not set'}
║                                                            ║
║  Commands:                                                 ║
║  • /ati-support - Create ticket via modal                 ║
║  • DM the bot - Create ticket via message                 ║
╚════════════════════════════════════════════════════════════╝
    """)

    handler = SocketModeHandler(app, APP_TOKEN)
    handler.start()


if __name__ == "__main__":
    main()
