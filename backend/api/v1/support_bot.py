"""
ATI Support Ticket Bot

Separate Slack bot for handling bug reports, feature requests, and questions.
Uses a different Slack app from the main ATI chatbot.
"""

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Response
from typing import Dict, Any, Optional, List
import json
import httpx
import os
import hashlib
import hmac
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from bson import ObjectId

from src.utils.logger import get_logger

KST = ZoneInfo("Asia/Seoul")

logger = get_logger(__name__)
router = APIRouter()

# Slack API URLs
SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"
SLACK_UPDATE_MESSAGE_URL = "https://slack.com/api/chat.update"
SLACK_VIEWS_OPEN_URL = "https://slack.com/api/views.open"
SLACK_USERS_INFO_URL = "https://slack.com/api/users.info"


def get_mongo():
    """Get MongoDB manager from app state."""
    from backend.main import app
    return app.state.mongo_manager


def verify_slack_signature(timestamp: str, signature: str, body: bytes) -> bool:
    """Verify that the request is coming from Slack using support bot signing secret."""
    signing_secret = os.getenv("SLACK_SUPPORT_SIGNING_SECRET", "")
    if not signing_secret:
        logger.warning("SLACK_SUPPORT_SIGNING_SECRET not configured")
        return False

    if not timestamp or not signature:
        logger.warning(
            f"Missing Slack headers: timestamp='{timestamp}', signature='{signature[:20] if signature else ''}'"
        )
        return False

    try:
        if abs(time.time() - int(timestamp)) > 60 * 5:
            logger.warning(f"Slack request timestamp too old: {timestamp}")
            return False
    except ValueError:
        logger.error(f"Invalid timestamp format: '{timestamp}'")
        return False

    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    my_signature = (
        "v0="
        + hmac.new(
            signing_secret.encode("utf-8"),
            sig_basestring.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(my_signature, signature)


def get_bot_token() -> str:
    """Get support bot token."""
    return os.getenv("SLACK_SUPPORT_BOT_TOKEN", "")


def get_admin_id() -> str:
    """Get admin Slack User ID."""
    return os.getenv("SLACK_SUPPORT_ADMIN_ID", "")


def get_admin_channel_id() -> Optional[str]:
    """Get admin notification channel ID (optional)."""
    return os.getenv("SLACK_SUPPORT_CHANNEL_ID")


def get_claude_webhook_url() -> Optional[str]:
    """Get Claude Code webhook URL for auto-processing."""
    return os.getenv("CLAUDE_WEBHOOK_URL")


async def get_user_info(user_id: str) -> Dict[str, Any]:
    """Fetch user info from Slack API."""
    bot_token = get_bot_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            SLACK_USERS_INFO_URL,
            params={"user": user_id},
            headers={"Authorization": f"Bearer {bot_token}"},
        )
        data = resp.json()
        if data.get("ok"):
            user = data.get("user", {})
            return {
                "id": user.get("id"),
                "name": user.get("real_name") or user.get("name", "Unknown"),
                "display_name": user.get("profile", {}).get("display_name", ""),
            }
    return {"id": user_id, "name": "Unknown", "display_name": ""}


async def generate_ticket_id() -> str:
    """Generate the next ticket ID (TKT-001, TKT-002, etc.)."""
    mongo = get_mongo()
    db = mongo.get_database_async()
    collection = db["support_tickets"]

    # Find the highest ticket number
    latest = await collection.find_one(
        {},
        sort=[("created_at", -1)],
        projection={"ticket_id": 1}
    )

    if latest and latest.get("ticket_id"):
        try:
            num = int(latest["ticket_id"].split("-")[1])
            return f"TKT-{num + 1:03d}"
        except (IndexError, ValueError):
            pass

    return "TKT-001"


async def create_ticket(
    reporter_id: str,
    reporter_name: str,
    category: str,
    title: str,
    description: str,
) -> Dict[str, Any]:
    """Create a new support ticket in MongoDB."""
    mongo = get_mongo()
    db = mongo.get_database_async()
    collection = db["support_tickets"]

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
        "admin_notes": None,
        "messages": [
            {
                "from_type": "reporter",
                "content": description,
                "timestamp": now,
            }
        ],
        "created_at": now,
        "updated_at": now,
        "resolved_at": None,
    }

    result = await collection.insert_one(ticket)
    ticket["_id"] = result.inserted_id

    logger.info(f"Created support ticket {ticket_id} from {reporter_name}")
    return ticket


async def get_open_ticket_for_user(user_id: str) -> Optional[Dict[str, Any]]:
    """Get the user's open ticket if exists."""
    mongo = get_mongo()
    db = mongo.get_database_async()
    collection = db["support_tickets"]

    return await collection.find_one({
        "reporter_id": user_id,
        "status": {"$in": ["open", "in_progress"]}
    })


async def add_message_to_ticket(
    ticket_id: str,
    from_type: str,
    content: str,
) -> bool:
    """Add a message to an existing ticket."""
    mongo = get_mongo()
    db = mongo.get_database_async()
    collection = db["support_tickets"]

    result = await collection.update_one(
        {"ticket_id": ticket_id},
        {
            "$push": {
                "messages": {
                    "from_type": from_type,
                    "content": content,
                    "timestamp": datetime.utcnow(),
                }
            },
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    return result.modified_count > 0


async def update_ticket_status(
    ticket_id: str,
    status: str,
    admin_notes: Optional[str] = None,
) -> bool:
    """Update ticket status."""
    mongo = get_mongo()
    db = mongo.get_database_async()
    collection = db["support_tickets"]

    update_data = {
        "status": status,
        "updated_at": datetime.utcnow(),
    }

    if status in ["resolved", "closed"]:
        update_data["resolved_at"] = datetime.utcnow()

    if admin_notes:
        update_data["admin_notes"] = admin_notes

    result = await collection.update_one(
        {"ticket_id": ticket_id},
        {"$set": update_data}
    )
    return result.modified_count > 0


async def get_ticket_by_id(ticket_id: str) -> Optional[Dict[str, Any]]:
    """Get ticket by ticket_id."""
    mongo = get_mongo()
    db = mongo.get_database_async()
    collection = db["support_tickets"]
    return await collection.find_one({"ticket_id": ticket_id})


# =============================================================================
# Notification Functions
# =============================================================================

async def trigger_claude_webhook(ticket: Dict[str, Any]):
    """Send ticket to Claude Code webhook for auto-processing."""
    webhook_url = get_claude_webhook_url()
    if not webhook_url:
        return

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                webhook_url,
                json={
                    "ticket_id": ticket["ticket_id"],
                    "category": ticket["category"],
                    "title": ticket["title"],
                    "description": ticket["description"],
                    "reporter_name": ticket["reporter_name"],
                },
            )
            if resp.status_code == 200:
                logger.info(f"Claude webhook triggered for {ticket['ticket_id']}")
            else:
                logger.warning(f"Claude webhook returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"Failed to trigger Claude webhook: {e}")


async def notify_admin_new_ticket(ticket: Dict[str, Any]):
    """Send notification to admin about new ticket."""
    bot_token = get_bot_token()
    admin_id = get_admin_id()
    admin_channel = get_admin_channel_id()

    if not admin_id:
        logger.warning("SLACK_SUPPORT_ADMIN_ID not configured")
        return

    category_emoji = {
        "bug": ":bug:",
        "feature": ":sparkles:",
        "question": ":question:",
    }.get(ticket["category"], ":ticket:")

    category_display = {
        "bug": "Bug Report",
        "feature": "Feature Request",
        "question": "Question",
    }.get(ticket["category"], ticket["category"])

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":ticket: New Ticket [{ticket['ticket_id']}]",
                "emoji": True,
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*{category_emoji} Category:*\n{category_display}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*:bust_in_silhouette: Reporter:*\n<@{ticket['reporter_id']}>",
                },
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*:memo: Title:*\n{ticket['title']}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Description:*\n>{ticket['description'][:500]}{'...' if len(ticket['description']) > 500 else ''}",
            },
        },
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":speech_balloon: Reply", "emoji": True},
                    "style": "primary",
                    "action_id": f"support_reply_{ticket['ticket_id']}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":question: Ask Question", "emoji": True},
                    "action_id": f"support_ask_{ticket['ticket_id']}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":white_check_mark: Resolve", "emoji": True},
                    "style": "danger",
                    "action_id": f"support_resolve_{ticket['ticket_id']}",
                },
            ],
        },
    ]

    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        # Send to admin DM
        await client.post(
            SLACK_POST_MESSAGE_URL,
            json={"channel": admin_id, "blocks": blocks},
            headers=headers,
        )

        # Also send to admin channel if configured
        if admin_channel:
            await client.post(
                SLACK_POST_MESSAGE_URL,
                json={"channel": admin_channel, "blocks": blocks},
                headers=headers,
            )


async def notify_reporter(
    reporter_id: str,
    ticket_id: str,
    message_type: str,  # "reply", "question", "resolved", "created"
    content: str,
):
    """Send notification to reporter."""
    bot_token = get_bot_token()

    emoji_map = {
        "reply": ":speech_balloon:",
        "question": ":question:",
        "resolved": ":white_check_mark:",
        "created": ":ticket:",
    }
    emoji = emoji_map.get(message_type, ":bell:")

    title_map = {
        "reply": "Admin Reply",
        "question": "Admin Question",
        "resolved": "Ticket Resolved",
        "created": "Ticket Created",
    }
    title = title_map.get(message_type, "Notification")

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji} *{title}* [{ticket_id}]\n\n{content}",
            },
        },
    ]

    # Add reply button for non-resolved tickets
    if message_type in ["reply", "question"]:
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":pencil2: Reply", "emoji": True},
                    "action_id": f"reporter_reply_{ticket_id}",
                },
            ],
        })

    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        await client.post(
            SLACK_POST_MESSAGE_URL,
            json={"channel": reporter_id, "blocks": blocks},
            headers=headers,
        )


# =============================================================================
# Modal Functions
# =============================================================================

async def open_ticket_modal(trigger_id: str, user_id: str):
    """Open the ticket creation modal."""
    bot_token = get_bot_token()

    view = {
        "type": "modal",
        "callback_id": "support_ticket_modal",
        "private_metadata": json.dumps({"user_id": user_id}),
        "title": {"type": "plain_text", "text": "ATI Support"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":ticket: *Submit a Support Ticket*\nDescribe your issue, suggestion, or question below.",
                },
            },
            {"type": "divider"},
            {
                "type": "input",
                "block_id": "category_block",
                "element": {
                    "type": "static_select",
                    "action_id": "category_input",
                    "placeholder": {"type": "plain_text", "text": "Select category"},
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": ":bug: Bug Report"},
                            "value": "bug",
                        },
                        {
                            "text": {"type": "plain_text", "text": ":sparkles: Feature Request"},
                            "value": "feature",
                        },
                        {
                            "text": {"type": "plain_text", "text": ":question: Question"},
                            "value": "question",
                        },
                    ],
                },
                "label": {"type": "plain_text", "text": "Category"},
            },
            {
                "type": "input",
                "block_id": "title_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "title_input",
                    "placeholder": {"type": "plain_text", "text": "Brief summary of the issue"},
                    "max_length": 150,
                },
                "label": {"type": "plain_text", "text": "Title"},
            },
            {
                "type": "input",
                "block_id": "description_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "description_input",
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": "Provide details about the issue..."},
                },
                "label": {"type": "plain_text", "text": "Description"},
            },
        ],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            SLACK_VIEWS_OPEN_URL,
            json={"trigger_id": trigger_id, "view": view},
            headers={
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/json",
            },
        )
        if not resp.json().get("ok"):
            logger.error(f"Failed to open ticket modal: {resp.text}")


async def open_reply_modal(trigger_id: str, ticket_id: str, modal_type: str):
    """Open the admin reply/question modal."""
    bot_token = get_bot_token()

    title_map = {
        "reply": "Reply to Ticket",
        "ask": "Ask Question",
        "resolve": "Resolve Ticket",
    }

    placeholder_map = {
        "reply": "Type your response to the reporter...",
        "ask": "Type your question for the reporter...",
        "resolve": "Add a resolution note (optional)...",
    }

    view = {
        "type": "modal",
        "callback_id": f"support_{modal_type}_modal",
        "private_metadata": json.dumps({"ticket_id": ticket_id}),
        "title": {"type": "plain_text", "text": title_map.get(modal_type, "Respond")},
        "submit": {"type": "plain_text", "text": "Send"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f":ticket: Ticket: *{ticket_id}*"},
                ],
            },
            {
                "type": "input",
                "block_id": "message_block",
                "optional": modal_type == "resolve",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "message_input",
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": placeholder_map.get(modal_type, "...")},
                },
                "label": {"type": "plain_text", "text": "Message"},
            },
        ],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            SLACK_VIEWS_OPEN_URL,
            json={"trigger_id": trigger_id, "view": view},
            headers={
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/json",
            },
        )
        if not resp.json().get("ok"):
            logger.error(f"Failed to open reply modal: {resp.text}")


async def open_reporter_reply_modal(trigger_id: str, ticket_id: str):
    """Open the reporter reply modal."""
    bot_token = get_bot_token()

    view = {
        "type": "modal",
        "callback_id": "support_reporter_reply_modal",
        "private_metadata": json.dumps({"ticket_id": ticket_id}),
        "title": {"type": "plain_text", "text": "Reply to Ticket"},
        "submit": {"type": "plain_text", "text": "Send"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f":ticket: Ticket: *{ticket_id}*"},
                ],
            },
            {
                "type": "input",
                "block_id": "message_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "message_input",
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": "Add more details or respond to admin..."},
                },
                "label": {"type": "plain_text", "text": "Message"},
            },
        ],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            SLACK_VIEWS_OPEN_URL,
            json={"trigger_id": trigger_id, "view": view},
            headers={
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/json",
            },
        )
        if not resp.json().get("ok"):
            logger.error(f"Failed to open reporter reply modal: {resp.text}")


# =============================================================================
# Event Handlers
# =============================================================================

async def process_dm_message(event: Dict[str, Any]):
    """Process DM message - create ticket or add to existing."""
    user_id = event.get("user")
    text = event.get("text", "").strip()

    if not text:
        return

    # Get user info
    user_info = await get_user_info(user_id)
    reporter_name = user_info.get("name", "Unknown")

    # Check for existing open ticket
    existing_ticket = await get_open_ticket_for_user(user_id)

    if existing_ticket:
        # Add message to existing ticket
        await add_message_to_ticket(
            existing_ticket["ticket_id"],
            "reporter",
            text,
        )

        # Notify admin of new message
        await notify_admin_ticket_update(existing_ticket["ticket_id"], text, reporter_name)

        # Confirm to user
        bot_token = get_bot_token()
        async with httpx.AsyncClient() as client:
            await client.post(
                SLACK_POST_MESSAGE_URL,
                json={
                    "channel": user_id,
                    "text": f":white_check_mark: Message added to your ticket [{existing_ticket['ticket_id']}]",
                },
                headers={
                    "Authorization": f"Bearer {bot_token}",
                    "Content-Type": "application/json",
                },
            )
    else:
        # Create new ticket from DM
        # Use first line as title, rest as description
        lines = text.split("\n", 1)
        title = lines[0][:150]
        description = text

        ticket = await create_ticket(
            reporter_id=user_id,
            reporter_name=reporter_name,
            category="question",  # Default for DM tickets
            title=title,
            description=description,
        )

        # Notify admin
        await notify_admin_new_ticket(ticket)

        # Trigger Claude Code webhook for auto-processing
        await trigger_claude_webhook(ticket)

        # Confirm to user
        await notify_reporter(
            user_id,
            ticket["ticket_id"],
            "created",
            f"Your support ticket has been created.\n\n*Title:* {title}\n\nAn admin will respond shortly. You can add more details by sending additional messages here.",
        )


async def notify_admin_ticket_update(ticket_id: str, message: str, reporter_name: str):
    """Notify admin of ticket update from reporter."""
    bot_token = get_bot_token()
    admin_id = get_admin_id()
    admin_channel = get_admin_channel_id()

    if not admin_id:
        return

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":speech_balloon: *New message on [{ticket_id}]* from {reporter_name}\n\n>{message[:500]}{'...' if len(message) > 500 else ''}",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":speech_balloon: Reply", "emoji": True},
                    "style": "primary",
                    "action_id": f"support_reply_{ticket_id}",
                },
            ],
        },
    ]

    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        await client.post(
            SLACK_POST_MESSAGE_URL,
            json={"channel": admin_id, "blocks": blocks},
            headers=headers,
        )

        if admin_channel:
            await client.post(
                SLACK_POST_MESSAGE_URL,
                json={"channel": admin_channel, "blocks": blocks},
                headers=headers,
            )


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/events")
async def support_events(request: Request, background_tasks: BackgroundTasks):
    """Handle incoming Slack events for support bot."""
    body_bytes = await request.body()
    headers = request.headers

    timestamp = headers.get("X-Slack-Request-Timestamp", "")
    signature = headers.get("X-Slack-Signature", "")

    # Verify signature
    if not verify_slack_signature(timestamp, signature, body_bytes):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")

    data = json.loads(body_bytes.decode("utf-8"))

    # Handle URL verification
    if data.get("type") == "url_verification":
        return {"challenge": data.get("challenge")}

    # Handle event callbacks
    if data.get("type") == "event_callback":
        event = data.get("event", {})
        event_type = event.get("type")

        if event_type == "message":
            # Ignore bot messages
            if event.get("bot_id") or event.get("subtype") == "bot_message":
                return {"ok": True}

            # Handle DMs
            channel = event.get("channel", "")
            is_im = event.get("channel_type") == "im" or channel.startswith("D")

            if is_im:
                background_tasks.add_task(process_dm_message, event)
                return {"ok": True}

    return {"ok": True}


@router.post("/commands")
async def support_commands(request: Request, background_tasks: BackgroundTasks):
    """Handle Slack slash commands for support bot."""
    body_bytes = await request.body()
    headers = request.headers

    timestamp = headers.get("X-Slack-Request-Timestamp", "")
    signature = headers.get("X-Slack-Signature", "")

    # Verify signature
    if not verify_slack_signature(timestamp, signature, body_bytes):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")

    form_data = await request.form()
    command = form_data.get("command")
    trigger_id = form_data.get("trigger_id")
    user_id = form_data.get("user_id")

    if command == "/ati-support":
        await open_ticket_modal(trigger_id, user_id)
        return Response(status_code=200)

    return {"text": f"Unknown command: {command}"}


@router.post("/interactive")
async def support_interactive(request: Request, background_tasks: BackgroundTasks):
    """Handle Slack interactive components (modals, buttons)."""
    body_bytes = await request.body()
    headers = request.headers

    timestamp = headers.get("X-Slack-Request-Timestamp", "")
    signature = headers.get("X-Slack-Signature", "")

    # Verify signature
    if not verify_slack_signature(timestamp, signature, body_bytes):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")

    form_data = await request.form()
    payload_str = form_data.get("payload")
    if not payload_str:
        return {"ok": False, "error": "No payload"}

    payload = json.loads(payload_str)

    if payload.get("type") == "view_submission":
        view = payload.get("view", {})
        callback_id = view.get("callback_id", "")

        if callback_id == "support_ticket_modal":
            # Handle ticket creation from modal
            values = view["state"]["values"]
            private_metadata = json.loads(view.get("private_metadata", "{}"))
            user_id = payload["user"]["id"]

            category = values["category_block"]["category_input"]["selected_option"]["value"]
            title = values["title_block"]["title_input"]["value"]
            description = values["description_block"]["description_input"]["value"]

            user_info = await get_user_info(user_id)
            reporter_name = user_info.get("name", "Unknown")

            ticket = await create_ticket(
                reporter_id=user_id,
                reporter_name=reporter_name,
                category=category,
                title=title,
                description=description,
            )

            # Notify admin
            background_tasks.add_task(notify_admin_new_ticket, ticket)

            # Trigger Claude Code webhook for auto-processing
            background_tasks.add_task(trigger_claude_webhook, ticket)

            # Notify reporter
            background_tasks.add_task(
                notify_reporter,
                user_id,
                ticket["ticket_id"],
                "created",
                f"Your support ticket has been created.\n\n*Title:* {title}\n*Category:* {category}\n\nAn admin will respond shortly.",
            )

            return Response(status_code=200)

        elif callback_id == "support_reply_modal":
            # Handle admin reply
            values = view["state"]["values"]
            private_metadata = json.loads(view.get("private_metadata", "{}"))
            ticket_id = private_metadata.get("ticket_id")
            message = values["message_block"]["message_input"]["value"]

            if ticket_id and message:
                ticket = await get_ticket_by_id(ticket_id)
                if ticket:
                    await add_message_to_ticket(ticket_id, "admin", message)
                    await update_ticket_status(ticket_id, "in_progress")
                    background_tasks.add_task(
                        notify_reporter,
                        ticket["reporter_id"],
                        ticket_id,
                        "reply",
                        message,
                    )

            return Response(status_code=200)

        elif callback_id == "support_ask_modal":
            # Handle admin question
            values = view["state"]["values"]
            private_metadata = json.loads(view.get("private_metadata", "{}"))
            ticket_id = private_metadata.get("ticket_id")
            message = values["message_block"]["message_input"]["value"]

            if ticket_id and message:
                ticket = await get_ticket_by_id(ticket_id)
                if ticket:
                    await add_message_to_ticket(ticket_id, "admin", message)
                    background_tasks.add_task(
                        notify_reporter,
                        ticket["reporter_id"],
                        ticket_id,
                        "question",
                        message,
                    )

            return Response(status_code=200)

        elif callback_id == "support_resolve_modal":
            # Handle ticket resolution
            values = view["state"]["values"]
            private_metadata = json.loads(view.get("private_metadata", "{}"))
            ticket_id = private_metadata.get("ticket_id")
            message = values["message_block"]["message_input"].get("value", "")

            if ticket_id:
                ticket = await get_ticket_by_id(ticket_id)
                if ticket:
                    await update_ticket_status(ticket_id, "resolved", message)
                    resolution_text = message if message else "Your ticket has been resolved. Thank you for your report!"
                    background_tasks.add_task(
                        notify_reporter,
                        ticket["reporter_id"],
                        ticket_id,
                        "resolved",
                        resolution_text,
                    )

            return Response(status_code=200)

        elif callback_id == "support_reporter_reply_modal":
            # Handle reporter reply
            values = view["state"]["values"]
            private_metadata = json.loads(view.get("private_metadata", "{}"))
            ticket_id = private_metadata.get("ticket_id")
            message = values["message_block"]["message_input"]["value"]
            user_id = payload["user"]["id"]

            if ticket_id and message:
                ticket = await get_ticket_by_id(ticket_id)
                if ticket:
                    user_info = await get_user_info(user_id)
                    reporter_name = user_info.get("name", "Unknown")
                    await add_message_to_ticket(ticket_id, "reporter", message)
                    background_tasks.add_task(
                        notify_admin_ticket_update,
                        ticket_id,
                        message,
                        reporter_name,
                    )

            return Response(status_code=200)

    elif payload.get("type") == "block_actions":
        for action in payload.get("actions", []):
            action_id = action.get("action_id", "")
            trigger_id = payload.get("trigger_id")

            if action_id.startswith("support_reply_"):
                ticket_id = action_id.replace("support_reply_", "")
                await open_reply_modal(trigger_id, ticket_id, "reply")
                return {"ok": True}

            elif action_id.startswith("support_ask_"):
                ticket_id = action_id.replace("support_ask_", "")
                await open_reply_modal(trigger_id, ticket_id, "ask")
                return {"ok": True}

            elif action_id.startswith("support_resolve_"):
                ticket_id = action_id.replace("support_resolve_", "")
                await open_reply_modal(trigger_id, ticket_id, "resolve")
                return {"ok": True}

            elif action_id.startswith("reporter_reply_"):
                ticket_id = action_id.replace("reporter_reply_", "")
                await open_reporter_reply_modal(trigger_id, ticket_id)
                return {"ok": True}

            # Claude Code approval buttons
            elif action_id.startswith("claude_approve_"):
                ticket_id = action_id.replace("claude_approve_", "")
                background_tasks.add_task(approve_claude_ticket, ticket_id)
                return {"ok": True}

            elif action_id.startswith("claude_reject_"):
                ticket_id = action_id.replace("claude_reject_", "")
                background_tasks.add_task(reject_claude_ticket, ticket_id)
                return {"ok": True}

            # Claude Code review buttons (after completion)
            elif action_id.startswith("claude_review_"):
                ticket_id = action_id.replace("claude_review_", "")
                background_tasks.add_task(start_claude_review, ticket_id)
                return {"ok": True}

            elif action_id.startswith("claude_revert_"):
                ticket_id = action_id.replace("claude_revert_", "")
                background_tasks.add_task(revert_claude_commit, ticket_id)
                return {"ok": True}

    return {"ok": True}


async def approve_claude_ticket(ticket_id: str):
    """Send approval to Claude webhook server."""
    webhook_url = get_claude_webhook_url()
    if not webhook_url:
        logger.warning("CLAUDE_WEBHOOK_URL not configured")
        return

    # Convert /ticket to /approve
    approve_url = webhook_url.replace("/ticket", "/approve")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                approve_url,
                json={"ticket_id": ticket_id},
            )
            if resp.status_code == 200:
                logger.info(f"Claude approved for {ticket_id}")
                # Notify admin
                bot_token = get_bot_token()
                admin_id = get_admin_id()
                if admin_id:
                    await httpx.AsyncClient().post(
                        "https://slack.com/api/chat.postMessage",
                        json={
                            "channel": admin_id,
                            "text": f"🚀 *[{ticket_id}]* 개발 시작됨! 완료되면 알려드릴게요.",
                        },
                        headers={"Authorization": f"Bearer {bot_token}"},
                    )
            else:
                logger.warning(f"Claude approval failed: {resp.status_code}")
    except Exception as e:
        logger.error(f"Failed to approve Claude ticket: {e}")


async def reject_claude_ticket(ticket_id: str):
    """Send rejection to Claude webhook server."""
    webhook_url = get_claude_webhook_url()
    if not webhook_url:
        return

    reject_url = webhook_url.replace("/ticket", "/reject")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                reject_url,
                json={"ticket_id": ticket_id},
            )
            if resp.status_code == 200:
                logger.info(f"Claude rejected for {ticket_id}")
                # Notify admin
                bot_token = get_bot_token()
                admin_id = get_admin_id()
                if admin_id:
                    await httpx.AsyncClient().post(
                        "https://slack.com/api/chat.postMessage",
                        json={
                            "channel": admin_id,
                            "text": f"❌ *[{ticket_id}]* 자동 개발 거부됨.",
                        },
                        headers={"Authorization": f"Bearer {bot_token}"},
                    )
    except Exception as e:
        logger.error(f"Failed to reject Claude ticket: {e}")


async def start_claude_review(ticket_id: str):
    """Start review servers via Claude webhook."""
    webhook_url = get_claude_webhook_url()
    if not webhook_url:
        return

    review_url = webhook_url.replace("/ticket", "/review")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                review_url,
                json={"ticket_id": ticket_id},
            )
            if resp.status_code == 200:
                logger.info(f"Review servers started for {ticket_id}")
            else:
                logger.warning(f"Failed to start review servers: {resp.status_code}")
    except Exception as e:
        logger.error(f"Failed to start review: {e}")


async def revert_claude_commit(ticket_id: str):
    """Revert last commit via Claude webhook."""
    webhook_url = get_claude_webhook_url()
    if not webhook_url:
        return

    revert_url = webhook_url.replace("/ticket", "/revert")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                revert_url,
                json={"ticket_id": ticket_id},
            )
            if resp.status_code == 200:
                logger.info(f"Reverted commit for {ticket_id}")
            else:
                logger.warning(f"Failed to revert: {resp.status_code}")
    except Exception as e:
        logger.error(f"Failed to revert: {e}")
