"""
Slack Bot Integration for All-Thing-Eye
Connects Slack events to the MCP AI Agent.
"""

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Form
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import httpx
import os
import hashlib
import hmac
import time
from src.utils.logger import get_logger
from backend.api.v1.mcp_agent import run_mcp_agent, AgentRequest
import re
from slack_sdk import WebClient

logger = get_logger(__name__)
router = APIRouter()

# Slack API URLs
SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"
SLACK_UPDATE_MESSAGE_URL = "https://slack.com/api/chat.update"
SLACK_VIEWS_OPEN_URL = "https://slack.com/api/views.open"
SLACK_VIEWS_PUBLISH_URL = "https://slack.com/api/views.publish"

def get_scheduler():
    """Get Slack scheduler from app state."""
    from backend.main import app
    return app.state.slack_scheduler

def verify_slack_signature(timestamp: str, signature: str, body: bytes) -> bool:
    """Verify that the request is coming from Slack."""
    signing_secret = os.getenv("SLACK_SIGNING_SECRET", "")
    if not signing_secret:
        logger.warning("SLACK_SIGNING_SECRET not configured")
        return False
        
    # Check for replay attacks (5 minute window)
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False
        
    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    my_signature = "v0=" + hmac.new(
        signing_secret.encode("utf-8"),
        sig_basestring.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(my_signature, signature)

async def process_slack_mention(event: Dict[str, Any]):
    """Background task to process AI response and send back to Slack."""
    channel_id = event.get("channel")
    thread_ts = event.get("thread_ts") or event.get("ts")
    user_id = event.get("user")
    text = event.get("text", "")
    
    # 1. Clean the text (remove bot mention)
    cleaned_text = re.sub(r'<@U[A-Z0-9]+>', '', text).strip()
    if not cleaned_text:
        return

    bot_token = os.getenv("SLACK_BOT_TOKEN", "")
    headers = {"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json"}

    # 2. Send "Thinking..." message using Block Kit for better UI
    async with httpx.AsyncClient() as client:
        initial_resp = await client.post(
            SLACK_POST_MESSAGE_URL,
            json={
                "channel": channel_id,
                "thread_ts": thread_ts,
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "⏳ *Thinking...* I'm analyzing the data for you."
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": "🤖 _This might take a few seconds depending on the data size._"
                            }
                        ]
                    }
                ]
            },
            headers=headers
        )
        initial_data = initial_resp.json()
        message_ts = initial_data.get("ts")

        if not message_ts:
            logger.error(f"Failed to post initial Slack message: {initial_data}")
            return

        # 3. Call AI Agent
        try:
            agent_req = AgentRequest(
                messages=[{"role": "user", "content": cleaned_text}],
                model="gpt-oss:120b"
            )
            # Internal call to run_mcp_agent
            result = await run_mcp_agent(agent_req)
            answer = result.get("answer", "죄송합니다. 답변을 생성하는 중에 오류가 발생했습니다.")
            
            # 4. Update Slack message with final answer
            await client.post(
                SLACK_UPDATE_MESSAGE_URL,
                json={
                    "channel": channel_id,
                    "ts": message_ts,
                    "text": answer,
                    "mrkdwn": True
                },
                headers=headers
            )
        except Exception as e:
            logger.error(f"Error processing Slack AI request: {e}")
            await client.post(
                SLACK_UPDATE_MESSAGE_URL,
                json={
                    "channel": channel_id,
                    "ts": message_ts,
                    "text": f"❌ 오류가 발생했습니다: {str(e)}"
                },
                headers=headers
            )

async def open_schedule_modal(trigger_id: str):
    """Open the Block Kit modal for scheduling reports."""
    view = {
        "type": "modal",
        "callback_id": "schedule_modal",
        "title": {"type": "plain_text", "text": "Report Scheduling"},
        "submit": {"type": "plain_text", "text": "Create"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "📅 *Set up a new recurring report.*"}
            },
            {
                "type": "input",
                "block_id": "name_block",
                "element": {"type": "plain_text_input", "action_id": "name_input", "placeholder": {"type": "plain_text", "text": "e.g., Daily Activity Summary"}},
                "label": {"type": "plain_text", "text": "Schedule Name"}
            },
            {
                "type": "input",
                "block_id": "type_block",
                "element": {
                    "type": "static_select",
                    "action_id": "type_input",
                    "placeholder": {"type": "plain_text", "text": "Select content type"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "📊 Daily Analysis (Last 24 Hours)"}, "value": "daily_analysis"},
                        {"text": {"type": "plain_text", "text": "✍️ Custom AI Prompt"}, "value": "custom_prompt"}
                    ],
                    "initial_option": {"text": {"type": "plain_text", "text": "📊 Daily Analysis (Last 24 Hours)"}, "value": "daily_analysis"}
                },
                "label": {"type": "plain_text", "text": "Content Type"}
            },
            {
                "type": "input",
                "block_id": "prompt_block",
                "optional": True,
                "element": {"type": "plain_text_input", "multiline": True, "action_id": "prompt_input", "placeholder": {"type": "plain_text", "text": "Enter the prompt to be sent to the AI Agent."}},
                "label": {"type": "plain_text", "text": "Custom Prompt (Optional)"}
            },
            {
                "type": "input",
                "block_id": "time_block",
                "element": {"type": "timepicker", "action_id": "time_input", "initial_time": "09:00", "placeholder": {"type": "plain_text", "text": "Select time"}},
                "label": {"type": "plain_text", "text": "Execution Time (Daily)"}
            },
            {
                "type": "input",
                "block_id": "channel_block",
                "element": {"type": "conversations_select", "action_id": "channel_input", "placeholder": {"type": "plain_text", "text": "Select channel or DM"}},
                "label": {"type": "plain_text", "text": "Recipient"}
            }
        ]
    }
    
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            SLACK_VIEWS_OPEN_URL,
            json={"trigger_id": trigger_id, "view": view},
            headers={"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json"}
        )
        if not resp.json().get("ok"):
            logger.error(f"Failed to open Slack modal: {resp.text}")

async def publish_app_home(user_id: str):
    """Publish the App Home view for the user."""
    view = {
        "type": "home",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🏠 All-Thing-Eye Analytics Home"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Welcome to All-Thing-Eye Bot!*\nManage your team's productivity and activities smartly."}
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "📅 *Report Scheduling*\nReceive recurring reports at your preferred time."}
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "action_id": "open_schedule_modal",
                        "text": {"type": "plain_text", "text": "Create Schedule 📅"},
                        "style": "primary"
                    }
                ]
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "💡 *Tip*: You can also use the `/ati-schedule` command anytime."}
            }
        ]
    }
    
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            SLACK_VIEWS_PUBLISH_URL,
            json={"user_id": user_id, "view": view},
            headers={"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json"}
        )
        if not resp.json().get("ok"):
            logger.error(f"Failed to publish App Home: {resp.text}")

@router.post("/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    """Handle incoming Slack events."""
    body_bytes = await request.body()
    headers = request.headers
    
    timestamp = headers.get("X-Slack-Request-Timestamp", "")
    signature = headers.get("X-Slack-Signature", "")
    
    # 1. Verify Signature
    if not verify_slack_signature(timestamp, signature, body_bytes):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")
        
    data = json.loads(body_bytes.decode("utf-8"))
    
    # 2. Handle URL Verification (Challenge)
    if data.get("type") == "url_verification":
        return {"challenge": data.get("challenge")}
        
    # 3. Handle Event Callbacks
    if data.get("type") == "event_callback":
        event = data.get("event", {})
        event_type = event.get("type")
        
        # app_mention (mention in channel) or message (DM)
        if event_type == "app_mention":
            background_tasks.add_task(process_slack_mention, event)
            return {"ok": True}
            
        elif event_type == "message":
            # Ignore messages from bots to prevent infinite loops
            if event.get("bot_id") or event.get("subtype") == "bot_message":
                return {"ok": True}
            
            # Respond to Direct Messages (IM)
            # DMs have channel starting with 'D' and channel_type is 'im'
            channel = event.get("channel", "")
            is_im = event.get("channel_type") == "im" or channel.startswith("D")
            
            if is_im:
                background_tasks.add_task(process_slack_mention, event)
                return {"ok": True}
        
        elif event_type == "app_home_opened":
            user_id = event.get("user")
            background_tasks.add_task(publish_app_home, user_id)
            return {"ok": True}
            
    return {"ok": True}

@router.post("/commands")
async def slack_commands(request: Request, background_tasks: BackgroundTasks):
    """Handle Slack slash commands."""
    form_data = await request.form()
    command = form_data.get("command")
    trigger_id = form_data.get("trigger_id")
    
    # All commands use 'ati-' prefix to avoid conflicts with other bots
    if command == "/ati-schedule":
        await open_schedule_modal(trigger_id)
        return "" # Acknowledge immediately
        
    return {"text": f"Unknown command: {command}"}

@router.post("/interactive")
async def slack_interactive(request: Request, background_tasks: BackgroundTasks):
    """Handle Slack interactive components (modals, buttons)."""
    form_data = await request.form()
    payload_str = form_data.get("payload")
    if not payload_str:
        return {"ok": False, "error": "No payload"}
        
    payload = json.loads(payload_str)
    
    if payload.get("type") == "view_submission":
        view = payload.get("view", {})
        if view.get("callback_id") == "schedule_modal":
            # Extract values
            values = view["state"]["values"]
            name = values["name_block"]["name_input"]["value"]
            content_type = values["type_block"]["type_input"]["selected_option"]["value"]
            prompt = values["prompt_block"]["prompt_input"].get("value")
            time_str = values["time_block"]["time_input"]["selected_time"]
            channel_id = values["channel_block"]["channel_input"]["selected_conversation"]
            user_id = payload["user"]["id"]
            
            # Convert time to cron expression (Daily at HH:mm)
            # Slack timepicker provides HH:mm
            hour, minute = time_str.split(":")
            cron_expression = f"{minute} {hour} * * *"
            
            schedule_data = {
                "member_id": user_id,
                "name": name,
                "channel_id": channel_id,
                "content_type": content_type,
                "prompt": prompt,
                "cron_expression": cron_expression,
                "is_active": True
            }
            
            # Save to scheduler (Background task)
            background_tasks.add_task(save_schedule_to_db, schedule_data)
            
            # Return empty response to close modal
            return ""
            
    elif payload.get("type") == "block_actions":
        for action in payload.get("actions", []):
            if action.get("action_id") == "open_schedule_modal":
                trigger_id = payload.get("trigger_id")
                background_tasks.add_task(open_schedule_modal, trigger_id)
                return {"ok": True}

    elif payload.get("type") == "shortcut":
        if payload.get("callback_id") == "open_schedule_shortcut":
            trigger_id = payload.get("trigger_id")
            background_tasks.add_task(open_schedule_modal, trigger_id)
            return {"ok": True}

    return {"ok": True}

async def save_schedule_to_db(schedule_data: Dict[str, Any]):
    """Save schedule to MongoDB and update APScheduler."""
    try:
        scheduler = get_scheduler()
        await scheduler.add_schedule(schedule_data)
        logger.info(f"✅ Schedule '{schedule_data['name']}' saved and activated for user {schedule_data['member_id']}")
    except Exception as e:
        logger.error(f"Failed to save schedule: {e}")
