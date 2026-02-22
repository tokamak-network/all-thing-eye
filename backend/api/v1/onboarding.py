"""
Onboarding API - Send welcome messages to new team members via Slack DM.

Uses SLACK_BOT_TOKEN for user lookup (users:read.email) and
SLACK_SUPPORT_BOT_TOKEN for DM delivery (im:write, chat:write).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId
import httpx
import os

from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Slack API URLs
SLACK_LOOKUP_BY_EMAIL_URL = "https://slack.com/api/users.lookupByEmail"
SLACK_CONVERSATIONS_OPEN_URL = "https://slack.com/api/conversations.open"
SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"


def get_mongo():
    """Get MongoDB manager from app state."""
    from backend.main import app
    return app.state.mongo_manager


def get_lookup_token() -> str:
    """Get token with users:read.email scope for lookupByEmail."""
    return os.getenv("SLACK_BOT_TOKEN", "")


def get_dm_token() -> str:
    """Get token with im:write and chat:write scopes for DM delivery."""
    return os.getenv("SLACK_SUPPORT_BOT_TOKEN", "")


class SendWelcomeRequest(BaseModel):
    member_id: str
    force: bool = False


def parse_member_id(raw_id: str):
    """Parse member ID, returning ObjectId if valid, otherwise the raw string."""
    try:
        return ObjectId(raw_id)
    except Exception:
        return raw_id


def build_welcome_blocks(member_name: str, email: str) -> list:
    """Build Block Kit blocks for the onboarding welcome message."""
    account_name = email.split("@")[0] if "@" in email else member_name.lower()

    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Welcome to Tokamak Network! :wave:",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"Hi *{member_name}*! :tada:\n\n"
                    "We're excited to have you on the team. "
                    "Below is your onboarding package to help you get started."
                ),
            },
        },
        {"type": "divider"},
        # Onboarding Video
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":movie_camera: *Onboarding Video*\n"
                    "Please watch the onboarding orientation video:\n"
                    "<https://drive.google.com/file/u/5/d/1WGKK7tmZyJrjOtkjcbH3wULrMSh3FNhv/view?usp=sharing|Watch Onboarding Video>"
                ),
            },
        },
        {"type": "divider"},
        # First-week Checklist
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":clipboard: *First-Week Checklist*\n\n"
                    ":one: *Set up 2FA* (Google, Slack, GitHub)\n"
                    "      <https://docs.google.com/presentation/d/1lZ1MjgkiJMm6nD_Ln4auBNyf2zF_44MkdyLlA-E9s1c/edit?slide=id.g25eac3a2538_3_87|View 2FA Setup Guide>\n\n"
                    ":two: *Set profile photo* on Google & Slack\n\n"
                    ":three: *Submit personal information consent form*\n"
                    "      <https://share.note.sx/op3a89uv#8riSv3+Tecs2qyZBzdC/kQJNDWZW2LtXK5CBFE0TJAc|Open Consent Form (Obsidian)>\n\n"
                    ":four: *Review the HR Guidebook*\n"
                    "      <https://docs.google.com/presentation/d/1Jg8I8YWXIr44O5tGgRhXvmI67hhzHom6-yI5zwRCMac/edit?slide=id.g2cf9870a132_1_3|Open HR Guidebook>"
                ),
            },
        },
        {"type": "divider"},
        # Account Information
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":key: *Your Account Information*\n\n"
                    f"*Account:* `{account_name}@tokamak.network`\n"
                    f"*Password:* `{os.getenv('ONBOARDING_DEFAULT_PASSWORD', 'hellotokamak')}`\n\n"
                    "_Please change your password after first login._"
                ),
            },
        },
        {"type": "divider"},
        # Contact Information
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":telephone_receiver: *Contact*\n\n"
                    "If you have any questions, feel free to reach out:\n"
                    "- *Managing Director:* Jaden (jaden@tokamak.network)\n"
                    "- *HR Manager:* Irene (irene@tokamak.network)"
                ),
            },
        },
    ]


@router.post("/send-welcome")
async def send_welcome_message(req: SendWelcomeRequest):
    """Send onboarding welcome message to a member via Slack DM."""
    lookup_token = get_lookup_token()
    dm_token = get_dm_token()
    if not lookup_token or not dm_token:
        raise HTTPException(status_code=500, detail="SLACK_BOT_TOKEN or SLACK_SUPPORT_BOT_TOKEN not configured")

    mongo = get_mongo()
    db = mongo.async_db

    # Look up member
    member_oid = parse_member_id(req.member_id)
    member = await db["members"].find_one({"_id": member_oid})

    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    member_name = member.get("name", "")
    member_email = member.get("email", "")

    if not member_email:
        raise HTTPException(status_code=400, detail="Member has no email address")

    # Check if already sent (unless force=True)
    if not req.force and member.get("onboarding_sent_at"):
        sent_at = member["onboarding_sent_at"]
        if isinstance(sent_at, datetime):
            sent_at = sent_at.isoformat()
        raise HTTPException(
            status_code=409,
            detail=f"Welcome message already sent at {sent_at}. Use force=true to resend.",
        )

    lookup_headers = {
        "Authorization": f"Bearer {lookup_token}",
        "Content-Type": "application/json",
    }
    dm_headers = {
        "Authorization": f"Bearer {dm_token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Step 1: Look up Slack user by email (uses main bot token with users:read.email)
        lookup_resp = await client.get(
            SLACK_LOOKUP_BY_EMAIL_URL,
            params={"email": member_email},
            headers=lookup_headers,
        )
        lookup_data = lookup_resp.json()

        if not lookup_data.get("ok"):
            error = lookup_data.get("error", "unknown")
            raise HTTPException(
                status_code=404,
                detail=f"Slack user not found for email {member_email}: {error}",
            )

        slack_user_id = lookup_data["user"]["id"]

        # Step 2: Open DM conversation (uses support bot token with im:write)
        conv_resp = await client.post(
            SLACK_CONVERSATIONS_OPEN_URL,
            json={"users": slack_user_id},
            headers=dm_headers,
        )
        conv_data = conv_resp.json()

        if not conv_data.get("ok"):
            error = conv_data.get("error", "unknown")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to open DM channel: {error}",
            )

        channel_id = conv_data["channel"]["id"]

        # Step 3: Send welcome message (uses support bot token with chat:write)
        blocks = build_welcome_blocks(member_name, member_email)
        msg_resp = await client.post(
            SLACK_POST_MESSAGE_URL,
            json={
                "channel": channel_id,
                "text": f"Welcome to Tokamak Network, {member_name}!",
                "blocks": blocks,
            },
            headers=dm_headers,
        )
        msg_data = msg_resp.json()

        if not msg_data.get("ok"):
            error = msg_data.get("error", "unknown")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send welcome message: {error}",
            )

    # Record that onboarding message was sent
    await db["members"].update_one(
        {"_id": member_oid},
        {"$set": {"onboarding_sent_at": datetime.utcnow()}},
    )

    logger.info(f"Welcome message sent to {member_name} ({member_email}) via Slack DM")

    return {
        "success": True,
        "message": f"Welcome message sent to {member_name}",
        "slack_user_id": slack_user_id,
    }
