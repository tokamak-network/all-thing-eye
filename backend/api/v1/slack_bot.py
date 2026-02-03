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
import calendar
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from src.utils.logger import get_logger
from backend.api.v1.mcp_agent import run_mcp_agent, AgentRequest
import re
from slack_sdk import WebClient

KST = ZoneInfo("Asia/Seoul")

logger = get_logger(__name__)
router = APIRouter()

# Slack API URLs
SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"
SLACK_UPDATE_MESSAGE_URL = "https://slack.com/api/chat.update"
SLACK_VIEWS_OPEN_URL = "https://slack.com/api/views.open"
SLACK_VIEWS_PUBLISH_URL = "https://slack.com/api/views.publish"
SLACK_FILES_UPLOAD_URL = "https://slack.com/api/files.upload"


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


async def process_slack_mention(event: Dict[str, Any]):
    """Background task to process AI response and send back to Slack."""
    channel_id = event.get("channel")
    thread_ts = event.get("thread_ts") or event.get("ts")
    user_id = event.get("user")
    text = event.get("text", "")

    # 1. Clean the text (remove bot mention)
    cleaned_text = re.sub(r"<@U[A-Z0-9]+>", "", text).strip()
    if not cleaned_text:
        return

    bot_token = os.getenv("SLACK_CHATBOT_TOKEN", "")
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json",
    }

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
                            "text": "⏳ *Thinking...* I'm analyzing the data for you.",
                        },
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": "🤖 _This might take a few seconds depending on the data size._",
                            }
                        ],
                    },
                ],
            },
            headers=headers,
        )
        initial_data = initial_resp.json()
        message_ts = initial_data.get("ts")

        if not message_ts:
            logger.error(f"Failed to post initial Slack message: {initial_data}")
            return

        # 3. Call AI Agent
        try:
            agent_req = AgentRequest(
                messages=[{"role": "user", "content": cleaned_text}], model="qwen3-235b"
            )
            # Internal call to run_mcp_agent
            result = await run_mcp_agent(agent_req)
            answer = result.get(
                "answer", "죄송합니다. 답변을 생성하는 중에 오류가 발생했습니다."
            )

            # 4. Update Slack message with final answer
            await client.post(
                SLACK_UPDATE_MESSAGE_URL,
                json={
                    "channel": channel_id,
                    "ts": message_ts,
                    "text": answer,
                    "mrkdwn": True,
                },
                headers=headers,
            )
        except Exception as e:
            logger.error(f"Error processing Slack AI request: {e}")
            await client.post(
                SLACK_UPDATE_MESSAGE_URL,
                json={
                    "channel": channel_id,
                    "ts": message_ts,
                    "text": f"❌ 오류가 발생했습니다: {str(e)}",
                },
                headers=headers,
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
                "text": {
                    "type": "mrkdwn",
                    "text": "📅 *Set up a new recurring report.*",
                },
            },
            {
                "type": "input",
                "block_id": "name_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "name_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "e.g., Daily Activity Summary",
                    },
                },
                "label": {"type": "plain_text", "text": "Schedule Name"},
            },
            {
                "type": "input",
                "block_id": "type_block",
                "element": {
                    "type": "static_select",
                    "action_id": "type_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select content type",
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "📊 Daily Analysis (Last 24 Hours)",
                            },
                            "value": "daily_analysis",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "✍️ Custom AI Prompt",
                            },
                            "value": "custom_prompt",
                        },
                    ],
                    "initial_option": {
                        "text": {
                            "type": "plain_text",
                            "text": "📊 Daily Analysis (Last 24 Hours)",
                        },
                        "value": "daily_analysis",
                    },
                },
                "label": {"type": "plain_text", "text": "Content Type"},
            },
            {
                "type": "input",
                "block_id": "prompt_block",
                "optional": True,
                "element": {
                    "type": "plain_text_input",
                    "multiline": True,
                    "action_id": "prompt_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Enter the prompt to be sent to the AI Agent.",
                    },
                },
                "label": {"type": "plain_text", "text": "Custom Prompt (Optional)"},
            },
            {
                "type": "input",
                "block_id": "time_block",
                "element": {
                    "type": "timepicker",
                    "action_id": "time_input",
                    "initial_time": "09:00",
                    "placeholder": {"type": "plain_text", "text": "Select time"},
                },
                "label": {"type": "plain_text", "text": "Execution Time (Daily)"},
            },
            {
                "type": "input",
                "block_id": "channel_block",
                "element": {
                    "type": "conversations_select",
                    "action_id": "channel_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select channel or DM",
                    },
                },
                "label": {"type": "plain_text", "text": "Recipient"},
            },
        ],
    }

    bot_token = os.getenv("SLACK_CHATBOT_TOKEN")
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
            logger.error(f"Failed to open Slack modal: {resp.text}")


async def publish_app_home(user_id: str):
    """Publish the App Home view for the user."""
    view = {
        "type": "home",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🏠 All-Thing-Eye Analytics Home",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Welcome to All-Thing-Eye Bot!*\nManage your team's productivity and activities smartly.",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "📅 *Report Scheduling*\nReceive recurring reports at your preferred time.",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "action_id": "open_schedule_modal",
                        "text": {"type": "plain_text", "text": "Create Schedule 📅"},
                        "style": "primary",
                    }
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "💡 *Tip*: You can also use the `/ati-schedule` command anytime.",
                },
            },
        ],
    }

    bot_token = os.getenv("SLACK_CHATBOT_TOKEN")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            SLACK_VIEWS_PUBLISH_URL,
            json={"user_id": user_id, "view": view},
            headers={
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/json",
            },
        )
        if not resp.json().get("ok"):
            logger.error(f"Failed to publish App Home: {resp.text}")


def get_report_period_presets() -> list:
    """Get date presets for report generation."""
    now = datetime.now(KST)
    current_day = now.day
    current_month = now.month
    current_year = now.year

    presets = []

    # This month first half (1-15)
    this_month_first_half_start = now.replace(day=1).strftime("%Y-%m-%d")
    this_month_first_half_end = (
        now.replace(day=15).strftime("%Y-%m-%d")
        if current_day >= 15
        else now.strftime("%Y-%m-%d")
    )
    presets.append(
        {
            "name": "This month 1st half (1-15)",
            "start_date": this_month_first_half_start,
            "end_date": this_month_first_half_end,
        }
    )

    # This month second half (16-end) - only if past 15th
    if current_day > 15:
        last_day_of_month = calendar.monthrange(current_year, current_month)[1]
        this_month_second_half_start = now.replace(day=16).strftime("%Y-%m-%d")
        this_month_second_half_end = now.strftime("%Y-%m-%d")
        presets.append(
            {
                "name": "This month 2nd half (16-end)",
                "start_date": this_month_second_half_start,
                "end_date": this_month_second_half_end,
            }
        )

    # This quarter
    quarter = (current_month - 1) // 3
    quarter_start_month = quarter * 3 + 1
    this_quarter_start = datetime(
        current_year, quarter_start_month, 1, tzinfo=KST
    ).strftime("%Y-%m-%d")
    presets.append(
        {
            "name": "This quarter",
            "start_date": this_quarter_start,
            "end_date": now.strftime("%Y-%m-%d"),
        }
    )

    # Last quarter
    if quarter == 0:
        last_quarter_year = current_year - 1
        last_quarter_start_month = 10
        last_quarter_end_month = 12
    else:
        last_quarter_year = current_year
        last_quarter_start_month = (quarter - 1) * 3 + 1
        last_quarter_end_month = quarter * 3

    last_quarter_start = datetime(
        last_quarter_year, last_quarter_start_month, 1, tzinfo=KST
    ).strftime("%Y-%m-%d")
    last_quarter_end_day = calendar.monthrange(
        last_quarter_year, last_quarter_end_month
    )[1]
    last_quarter_end = datetime(
        last_quarter_year, last_quarter_end_month, last_quarter_end_day, tzinfo=KST
    ).strftime("%Y-%m-%d")
    presets.append(
        {
            "name": "Last quarter",
            "start_date": last_quarter_start,
            "end_date": last_quarter_end,
        }
    )

    return presets


async def open_report_modal(trigger_id: str, channel_id: str = None):
    """Open the Block Kit modal for generating biweekly reports."""
    presets = get_report_period_presets()

    # Build preset options
    preset_options = [
        {
            "text": {"type": "plain_text", "text": p["name"]},
            "value": f"{p['start_date']}|{p['end_date']}",
        }
        for p in presets
    ]

    view = {
        "type": "modal",
        "callback_id": "report_modal",
        "private_metadata": json.dumps({"channel_id": channel_id})
        if channel_id
        else "{}",
        "title": {"type": "plain_text", "text": "Generate Report"},
        "submit": {"type": "plain_text", "text": "Generate"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "📊 *Generate a biweekly ecosystem report*\nSelect a period and generate a comprehensive report with GitHub stats, staking data, and market information.",
                },
            },
            {"type": "divider"},
            {
                "type": "input",
                "block_id": "period_block",
                "element": {
                    "type": "static_select",
                    "action_id": "period_input",
                    "placeholder": {"type": "plain_text", "text": "Select period"},
                    "options": preset_options,
                    "initial_option": preset_options[0],
                },
                "label": {"type": "plain_text", "text": "📅 Report Period"},
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"_Selected: {presets[0]['start_date']} ~ {presets[0]['end_date']}_",
                    }
                ],
            },
            {"type": "divider"},
            {
                "type": "input",
                "block_id": "ai_block",
                "element": {
                    "type": "static_select",
                    "action_id": "ai_input",
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "✅ Yes - AI generates intelligent summaries",
                            },
                            "value": "true",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "❌ No - Basic summaries only",
                            },
                            "value": "false",
                        },
                    ],
                    "initial_option": {
                        "text": {
                            "type": "plain_text",
                            "text": "✅ Yes - AI generates intelligent summaries",
                        },
                        "value": "true",
                    },
                },
                "label": {"type": "plain_text", "text": "🤖 Use AI for Summaries"},
            },
            {
                "type": "input",
                "block_id": "channel_block",
                "element": {
                    "type": "conversations_select",
                    "action_id": "channel_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select channel to post report",
                    },
                    "default_to_current_conversation": True,
                },
                "label": {"type": "plain_text", "text": "📢 Post to Channel"},
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "⏱️ _Report generation may take 30-60 seconds depending on data size._",
                    }
                ],
            },
        ],
    }

    bot_token = os.getenv("SLACK_CHATBOT_TOKEN")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            SLACK_VIEWS_OPEN_URL,
            json={"trigger_id": trigger_id, "view": view},
            headers={
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/json",
            },
        )
        result = resp.json()
        if not result.get("ok"):
            logger.error(f"Failed to open report modal: {result}")


async def generate_and_send_report(
    channel_id: str, start_date: str, end_date: str, use_ai: bool, user_id: str
):
    """Generate report and send to Slack channel with file attachment."""
    bot_token = os.getenv("SLACK_CHATBOT_TOKEN", "")
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Send "Generating..." message
        initial_resp = await client.post(
            SLACK_POST_MESSAGE_URL,
            json={
                "channel": channel_id,
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"⏳ *Generating report...*\n📅 Period: {start_date} ~ {end_date}\n🤖 AI: {'Enabled' if use_ai else 'Disabled'}",
                        },
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"_Requested by <@{user_id}>. This may take 30-60 seconds._",
                            }
                        ],
                    },
                ],
            },
            headers=headers,
        )
        initial_data = initial_resp.json()
        message_ts = initial_data.get("ts")

        if not message_ts:
            logger.error(f"Failed to post initial message: {initial_data}")
            return

        try:
            # 2. Call Report Generation API
            from backend.api.v1.reports import (
                get_github_stats,
                get_active_projects,
                generate_project_summaries,
                generate_highlight,
                format_tech_stats_table,
                get_mongo,
            )
            from src.report.external_data import (
                get_staking_data,
                get_staking_summary_text,
                get_ton_wton_tx_counts,
                get_transactions_summary_text,
                get_market_cap_data,
                get_market_cap_summary_text,
            )
            from src.report.templates.biweekly import (
                BIWEEKLY_REPORT_TEMPLATE,
                COMMUNITY_TEMPLATE,
            )

            # Parse dates
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=KST)
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=KST)
            start_utc = start_dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
            end_utc = end_dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

            mongo = get_mongo()

            # Fetch data
            staking_data = await get_staking_data(mongo_manager=mongo)
            staking_summary = get_staking_summary_text(staking_data)

            market_data = await get_market_cap_data(mongo_manager=mongo)
            market_summary = get_market_cap_summary_text(market_data)

            try:
                tx_data = await get_ton_wton_tx_counts(
                    start_utc, end_utc, mongo_manager=mongo
                )
                tx_summary = get_transactions_summary_text(tx_data)
            except Exception:
                tx_summary = "Transaction data is currently being collected."

            github_stats = await get_github_stats(mongo, start_utc, end_utc)
            active_projects = await get_active_projects(mongo)

            project_summaries = await generate_project_summaries(
                github_stats["commits_list"],
                active_projects=active_projects,
                use_ai=use_ai,
            )

            highlight = await generate_highlight(
                github_stats, staking_summary, market_summary, use_ai=use_ai
            )

            tech_table = format_tech_stats_table(github_stats["by_category"])

            # Build report
            report = BIWEEKLY_REPORT_TEMPLATE.format(
                staking_summary=staking_summary,
                transactions_summary=tx_summary,
                market_cap_summary=market_summary,
                tech_stats_table=tech_table,
                total_commits=github_stats["total_commits"],
                total_repos=github_stats["total_repos"],
                ooo_summary=project_summaries.get("ooo", "- No updates"),
                eco_summary=project_summaries.get("eco", "- No updates"),
                trh_summary=project_summaries.get("trh", "- No updates"),
            )

            report = report.replace(
                "This week, our primary focus centered on the Tokamak Rollup Hub (TRH) infrastructure upgrade and the ongoing Staking V2 integration. Notable progress includes advanced chain configuration, internal audits for L1 Contract verification, and preparations for UI service deployment.",
                highlight,
            )
            report = report + COMMUNITY_TEMPLATE

            # 3. Convert markdown to Slack mrkdwn (simplified)
            slack_text = convert_markdown_to_slack(report)

            # 4. Update message with report summary
            stats_text = (
                f"📊 *Biweekly Report Generated!*\n"
                f"📅 Period: {start_date} ~ {end_date}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📈 *Stats*\n"
                f"• Commits: {github_stats['total_commits']}\n"
                f"• Repositories: {github_stats['total_repos']}\n"
                f"• Pull Requests: {github_stats['total_prs']}\n"
                f"• Staked TON: {staking_data.get('latest_staked', 0):,.0f}\n"
                f"• Market Cap: ${market_data.get('market_cap', 0):,.0f}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📄 _Full report attached as file below._"
            )

            await client.post(
                SLACK_UPDATE_MESSAGE_URL,
                json={
                    "channel": channel_id,
                    "ts": message_ts,
                    "blocks": [
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": stats_text},
                        },
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": f"_Generated by <@{user_id}> using {'AI' if use_ai else 'basic'} summaries_",
                                }
                            ],
                        },
                    ],
                },
                headers=headers,
            )

            # 5. Upload report as file
            filename = f"biweekly-report-{end_date}.md"

            # Use files.upload API
            upload_resp = await client.post(
                SLACK_FILES_UPLOAD_URL,
                data={
                    "channels": channel_id,
                    "content": report,
                    "filename": filename,
                    "filetype": "markdown",
                    "title": f"Biweekly Report ({start_date} ~ {end_date})",
                    "thread_ts": message_ts,
                },
                headers={"Authorization": f"Bearer {bot_token}"},
            )

            upload_result = upload_resp.json()
            if not upload_result.get("ok"):
                logger.error(f"Failed to upload file: {upload_result}")
            else:
                logger.info(f"✅ Report file uploaded successfully to {channel_id}")

        except Exception as e:
            logger.error(f"Error generating report: {e}", exc_info=True)
            await client.post(
                SLACK_UPDATE_MESSAGE_URL,
                json={
                    "channel": channel_id,
                    "ts": message_ts,
                    "text": f"❌ Failed to generate report: {str(e)}",
                },
                headers=headers,
            )


def convert_markdown_to_slack(markdown: str) -> str:
    """Convert standard markdown to Slack mrkdwn format."""
    text = markdown

    # Headers: # -> *bold*
    text = re.sub(r"^### (.+)$", r"*\1*", text, flags=re.MULTILINE)
    text = re.sub(r"^## (.+)$", r"*\1*", text, flags=re.MULTILINE)
    text = re.sub(r"^# (.+)$", r"*\1*", text, flags=re.MULTILINE)

    # Bold: **text** -> *text*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)

    # Italic: *text* or _text_ -> _text_ (Slack uses single underscore)
    # Skip this to avoid conflicts with bold

    # Links: [text](url) -> <url|text>
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)

    # Tables: Convert to simple format (Slack doesn't support tables well)
    # Just keep as-is for now

    return text


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
    channel_id = form_data.get("channel_id")

    # All commands use 'ati-' prefix to avoid conflicts with other bots
    if command == "/ati-schedule":
        await open_schedule_modal(trigger_id)
        return ""  # Acknowledge immediately

    elif command == "/ati-report":
        await open_report_modal(trigger_id, channel_id)
        return ""  # Acknowledge immediately

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
            content_type = values["type_block"]["type_input"]["selected_option"][
                "value"
            ]
            prompt = values["prompt_block"]["prompt_input"].get("value")
            time_str = values["time_block"]["time_input"]["selected_time"]
            channel_id = values["channel_block"]["channel_input"][
                "selected_conversation"
            ]
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
                "is_active": True,
            }

            # Save to scheduler (Background task)
            background_tasks.add_task(save_schedule_to_db, schedule_data)

            # Return empty response to close modal
            return ""

        elif view.get("callback_id") == "report_modal":
            # Extract values for report generation
            values = view["state"]["values"]
            period_value = values["period_block"]["period_input"]["selected_option"][
                "value"
            ]
            use_ai_value = values["ai_block"]["ai_input"]["selected_option"]["value"]
            channel_id = values["channel_block"]["channel_input"][
                "selected_conversation"
            ]
            user_id = payload["user"]["id"]

            # Parse period (format: "start_date|end_date")
            start_date, end_date = period_value.split("|")
            use_ai = use_ai_value == "true"

            # Generate report in background
            background_tasks.add_task(
                generate_and_send_report,
                channel_id,
                start_date,
                end_date,
                use_ai,
                user_id,
            )

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
        logger.info(
            f"✅ Schedule '{schedule_data['name']}' saved and activated for user {schedule_data['member_id']}"
        )
    except Exception as e:
        logger.error(f"Failed to save schedule: {e}")
