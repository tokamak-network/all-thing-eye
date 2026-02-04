"""
Slack Bot Integration for All-Thing-Eye
Connects Slack events to the MCP AI Agent.
"""

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Form, Response
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


async def get_user_timezone(user_id: str) -> str:
    bot_token = os.getenv("SLACK_CHATBOT_TOKEN")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://slack.com/api/users.info",
                params={"user": user_id},
                headers={"Authorization": f"Bearer {bot_token}"},
            )
            data = resp.json()
            if data.get("ok"):
                return data.get("user", {}).get("tz", "Asia/Seoul")
    except Exception as e:
        logger.error(f"Failed to fetch user timezone: {e}")
    return "Asia/Seoul"


async def open_schedule_modal(trigger_id: str, user_id: str = None):
    user_tz = await get_user_timezone(user_id) if user_id else "Asia/Seoul"

    view = {
        "type": "modal",
        "callback_id": "schedule_modal",
        "private_metadata": user_tz,
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
    scheduler = get_scheduler()
    user_schedules = await scheduler.get_user_schedules(user_id) if scheduler else []

    blocks = [
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
    ]

    if user_schedules:
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📋 *Your Schedules* ({len(user_schedules)})",
                },
            }
        )

        for schedule in user_schedules:
            schedule_id = str(schedule["_id"])
            name = schedule.get("name", "Unnamed")
            content_type = schedule.get("content_type", "custom_prompt")
            cron = schedule.get("cron_expression", "")
            channel_id = schedule.get("channel_id", "")
            timezone = schedule.get("timezone", "Asia/Seoul")
            is_active = schedule.get("is_active", True)

            parts = cron.split()
            time_str = f"{parts[1]}:{parts[0]}" if len(parts) >= 2 else cron

            tz_short = {
                "Asia/Seoul": "KST",
                "Asia/Tokyo": "JST",
                "Asia/Kolkata": "IST",
                "Europe/London": "GMT",
                "Europe/Berlin": "CET",
                "America/New_York": "EST",
                "America/Los_Angeles": "PST",
                "Australia/Sydney": "AEST",
                "UTC": "UTC",
            }.get(timezone, timezone)

            content_display = (
                "📊 Daily Analysis" if content_type == "daily_analysis" else "✍️ Custom"
            )
            status_emoji = "🟢" if is_active else "⏸️"

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{status_emoji} *{name}*\n{content_display} • {time_str} ({tz_short}) daily • <#{channel_id}>",
                    },
                    "accessory": {
                        "type": "button",
                        "action_id": f"delete_schedule_{schedule_id}",
                        "text": {"type": "plain_text", "text": "🗑️ Delete"},
                        "style": "danger",
                        "confirm": {
                            "title": {"type": "plain_text", "text": "Delete Schedule?"},
                            "text": {
                                "type": "mrkdwn",
                                "text": f"Are you sure you want to delete *{name}*?",
                            },
                            "confirm": {"type": "plain_text", "text": "Delete"},
                            "deny": {"type": "plain_text", "text": "Cancel"},
                        },
                    },
                }
            )
    else:
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "📋 *Your Schedules*\n_No schedules yet. Create one above!_",
                },
            }
        )

    blocks.append({"type": "divider"})
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "💡 You can also use `/ati-schedule` command anytime.",
                }
            ],
        }
    )

    view = {"type": "home", "blocks": blocks}

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


def get_code_stats_presets() -> list:
    """Get date presets for code statistics."""
    now = datetime.now(KST)
    current_day = now.day
    current_month = now.month
    current_year = now.year

    presets = []

    # This week
    days_since_monday = now.weekday()
    this_week_start = (now - timedelta(days=days_since_monday)).strftime("%Y-%m-%d")
    presets.append({
        "name": "This week",
        "start_date": this_week_start,
        "end_date": now.strftime("%Y-%m-%d"),
    })

    # Last 7 days
    last_7_days_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    presets.append({
        "name": "Last 7 days",
        "start_date": last_7_days_start,
        "end_date": now.strftime("%Y-%m-%d"),
    })

    # Last 14 days
    last_14_days_start = (now - timedelta(days=14)).strftime("%Y-%m-%d")
    presets.append({
        "name": "Last 14 days",
        "start_date": last_14_days_start,
        "end_date": now.strftime("%Y-%m-%d"),
    })

    # This month
    this_month_start = now.replace(day=1).strftime("%Y-%m-%d")
    presets.append({
        "name": "This month",
        "start_date": this_month_start,
        "end_date": now.strftime("%Y-%m-%d"),
    })

    # Last month
    last_month_end = now.replace(day=1) - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1).strftime("%Y-%m-%d")
    presets.append({
        "name": "Last month",
        "start_date": last_month_start,
        "end_date": last_month_end.strftime("%Y-%m-%d"),
    })

    return presets


async def open_code_stats_modal(trigger_id: str, channel_id: str = None):
    """Open the Block Kit modal for viewing code statistics."""
    presets = get_code_stats_presets()

    preset_options = [
        {
            "text": {"type": "plain_text", "text": p["name"]},
            "value": f"{p['start_date']}|{p['end_date']}",
        }
        for p in presets
    ]

    view = {
        "type": "modal",
        "callback_id": "code_stats_modal",
        "private_metadata": json.dumps({"channel_id": channel_id}) if channel_id else "{}",
        "title": {"type": "plain_text", "text": "Code Statistics"},
        "submit": {"type": "plain_text", "text": "Get Stats"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "📊 *View Code Change Statistics*\nGet insights on code additions, deletions, top contributors, and active repositories.",
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
                    "initial_option": preset_options[3],  # This month by default
                },
                "label": {"type": "plain_text", "text": "📅 Period"},
            },
            {
                "type": "input",
                "block_id": "channel_block",
                "element": {
                    "type": "conversations_select",
                    "action_id": "channel_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select channel to post stats",
                    },
                    "default_to_current_conversation": True,
                },
                "label": {"type": "plain_text", "text": "📢 Post to Channel"},
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
            logger.error(f"Failed to open code stats modal: {result}")


async def generate_and_send_code_stats(
    channel_id: str, start_date: str, end_date: str, user_id: str
):
    """Generate code statistics and send to Slack channel."""
    from backend.api.v1.mcp_agent import MCPToolManager

    bot_token = os.getenv("SLACK_CHATBOT_TOKEN", "")
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Send "Loading..." message
        initial_resp = await client.post(
            SLACK_POST_MESSAGE_URL,
            json={
                "channel": channel_id,
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"⏳ *Loading code statistics...*\n📅 Period: {start_date} ~ {end_date}",
                        },
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
            # 2. Get code stats using MCPToolManager
            result = await MCPToolManager.get_code_stats({
                "start_date": start_date,
                "end_date": end_date,
            })

            if not result.get("success"):
                raise Exception("Failed to fetch code stats")

            data = result["data"]
            total = data["total"]
            contributors = data["top_contributors"][:5]
            repositories = data["top_repositories"][:5]

            # 3. Build Slack blocks
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "📊 Code Statistics",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"📅 {start_date} ~ {end_date} | Requested by <@{user_id}>",
                        }
                    ],
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*📈 Summary*",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Lines Added:*\n+{total['additions']:,}"},
                        {"type": "mrkdwn", "text": f"*Lines Deleted:*\n-{total['deletions']:,}"},
                        {"type": "mrkdwn", "text": f"*Net Change:*\n{'+' if total['net_change'] >= 0 else ''}{total['net_change']:,}"},
                        {"type": "mrkdwn", "text": f"*Total Commits:*\n{total['commits']:,}"},
                    ],
                },
            ]

            # Top Contributors
            if contributors:
                contributor_text = "*🏆 Top Contributors*\n"
                for i, c in enumerate(contributors, 1):
                    medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
                    contributor_text += f"{medal} *{c['name']}*: +{c['additions']:,} / -{c['deletions']:,} ({c['commits']} commits)\n"
                blocks.append({"type": "divider"})
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": contributor_text},
                })

            # Top Repositories
            if repositories:
                repo_text = "*📁 Active Repositories*\n"
                for i, r in enumerate(repositories, 1):
                    repo_text += f"{i}. *{r['name']}*: +{r['additions']:,} / -{r['deletions']:,} ({r['commits']} commits)\n"
                blocks.append({"type": "divider"})
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": repo_text},
                })

            # 4. Update message with stats
            await client.post(
                SLACK_UPDATE_MESSAGE_URL,
                json={
                    "channel": channel_id,
                    "ts": message_ts,
                    "blocks": blocks,
                },
                headers=headers,
            )

            logger.info(f"✅ Code stats sent to {channel_id}")

        except Exception as e:
            logger.error(f"Error generating code stats: {e}", exc_info=True)
            await client.post(
                SLACK_UPDATE_MESSAGE_URL,
                json={
                    "channel": channel_id,
                    "ts": message_ts,
                    "text": f"❌ Failed to generate code stats: {str(e)}",
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
    user_id = form_data.get("user_id")

    if command == "/ati-schedule":
        await open_schedule_modal(trigger_id, user_id)
        return Response(status_code=200)

    elif command == "/ati-report":
        await open_report_modal(trigger_id, channel_id)
        return Response(status_code=200)

    elif command == "/ati-code-stats":
        await open_code_stats_modal(trigger_id, channel_id)
        return Response(status_code=200)

    return {"text": f"Unknown command: {command}"}


@router.post("/interactive")
async def slack_interactive(request: Request, background_tasks: BackgroundTasks):
    """Handle Slack interactive components (modals, buttons)."""
    form_data = await request.form()
    payload_str = form_data.get("payload")
    if not payload_str:
        print("🔴 No payload in interactive request")
        return {"ok": False, "error": "No payload"}

    payload = json.loads(payload_str)
    print(f"🟢 Interactive payload type: {payload.get('type')}")

    if payload.get("type") == "view_submission":
        view = payload.get("view", {})
        print(f"🟢 View submission callback_id: {view.get('callback_id')}")

        if view.get("callback_id") == "schedule_modal":
            try:
                values = view["state"]["values"]
                timezone = view.get("private_metadata", "Asia/Seoul")
                print(f"🟢 Schedule modal values: {json.dumps(values, default=str)}")

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

                print(
                    f"🟢 Parsed schedule: name={name}, type={content_type}, time={time_str}, tz={timezone}, channel={channel_id}"
                )

                hour, minute = time_str.split(":")
                cron_expression = f"{minute} {hour} * * *"

                schedule_data = {
                    "member_id": user_id,
                    "name": name,
                    "channel_id": channel_id,
                    "content_type": content_type,
                    "prompt": prompt,
                    "cron_expression": cron_expression,
                    "timezone": timezone,
                    "is_active": True,
                }

                print(f"🟢 Schedule data to save: {schedule_data}")

                # Save to scheduler (Background task)
                background_tasks.add_task(save_schedule_to_db, schedule_data)

                # Return empty 200 response to close modal (Slack requires this)
                return Response(status_code=200)
            except Exception as e:
                print(f"🔴 Error processing schedule_modal: {e}")
                return {"response_action": "errors", "errors": {"name_block": str(e)}}

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

            return Response(status_code=200)

        elif view.get("callback_id") == "code_stats_modal":
            # Extract values for code stats
            values = view["state"]["values"]
            period_value = values["period_block"]["period_input"]["selected_option"][
                "value"
            ]
            channel_id = values["channel_block"]["channel_input"][
                "selected_conversation"
            ]
            user_id = payload["user"]["id"]

            # Parse period (format: "start_date|end_date")
            start_date, end_date = period_value.split("|")

            # Generate code stats in background
            background_tasks.add_task(
                generate_and_send_code_stats,
                channel_id,
                start_date,
                end_date,
                user_id,
            )

            return Response(status_code=200)

    elif payload.get("type") == "block_actions":
        for action in payload.get("actions", []):
            action_id = action.get("action_id", "")

            if action_id == "open_schedule_modal":
                trigger_id = payload.get("trigger_id")
                background_tasks.add_task(open_schedule_modal, trigger_id)
                return {"ok": True}

            if action_id.startswith("delete_schedule_"):
                schedule_id = action_id.replace("delete_schedule_", "")
                user_id = payload.get("user", {}).get("id")
                background_tasks.add_task(
                    delete_schedule_and_notify, schedule_id, user_id
                )
                return {"ok": True}

    elif payload.get("type") == "shortcut":
        if payload.get("callback_id") == "open_schedule_shortcut":
            trigger_id = payload.get("trigger_id")
            background_tasks.add_task(open_schedule_modal, trigger_id)
            return {"ok": True}

    return {"ok": True}


async def save_schedule_to_db(schedule_data: Dict[str, Any]):
    """Save schedule to MongoDB and update APScheduler."""
    user_id = schedule_data.get("member_id")
    schedule_name = schedule_data.get("name", "Unnamed")

    try:
        scheduler = get_scheduler()
        await scheduler.add_schedule(schedule_data)
        logger.info(
            f"✅ Schedule '{schedule_name}' saved and activated for user {user_id}"
        )

        await send_schedule_notification(
            user_id=user_id,
            success=True,
            schedule_name=schedule_name,
            schedule_data=schedule_data,
        )
        await publish_app_home(user_id)

    except Exception as e:
        logger.error(f"Failed to save schedule: {e}")
        await send_schedule_notification(
            user_id=user_id,
            success=False,
            schedule_name=schedule_name,
            error_message=str(e),
        )


async def send_schedule_notification(
    user_id: str,
    success: bool,
    schedule_name: str,
    schedule_data: Dict[str, Any] = None,
    error_message: str = None,
):
    bot_token = os.getenv("SLACK_CHATBOT_TOKEN")

    if success and schedule_data:
        cron = schedule_data.get("cron_expression", "")
        content_type = schedule_data.get("content_type", "custom_prompt")
        channel_id = schedule_data.get("channel_id", "")
        timezone = schedule_data.get("timezone", "Asia/Seoul")

        parts = cron.split()
        time_str = f"{parts[1]}:{parts[0]}" if len(parts) >= 2 else cron

        tz_short = {
            "Asia/Seoul": "KST",
            "Asia/Tokyo": "JST",
            "Asia/Kolkata": "IST",
            "Europe/London": "GMT",
            "Europe/Berlin": "CET",
            "America/New_York": "EST",
            "America/Los_Angeles": "PST",
            "Australia/Sydney": "AEST",
            "UTC": "UTC",
        }.get(timezone, timezone)

        content_display = (
            "📊 Daily Analysis"
            if content_type == "daily_analysis"
            else "✍️ Custom Prompt"
        )

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"✅ *Schedule Created Successfully!*\n\nYour recurring report has been set up.",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Name:*\n{schedule_name}"},
                    {"type": "mrkdwn", "text": f"*Type:*\n{content_display}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Time:*\n{time_str} ({tz_short}) daily",
                    },
                    {"type": "mrkdwn", "text": f"*Recipient:*\n<#{channel_id}>"},
                ],
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "💡 Manage your schedules in the *App Home* tab.",
                    }
                ],
            },
        ]
    else:
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"❌ *Failed to Create Schedule*\n\nSchedule: {schedule_name}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Error:*\n```{error_message or 'Unknown error'}```",
                },
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "Please try again or contact support."}
                ],
            },
        ]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            SLACK_POST_MESSAGE_URL,
            json={"channel": user_id, "blocks": blocks},
            headers={
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/json",
            },
        )
        if not resp.json().get("ok"):
            logger.error(f"Failed to send schedule notification: {resp.text}")


async def delete_schedule_and_notify(schedule_id: str, user_id: str):
    try:
        scheduler = get_scheduler()
        if not scheduler:
            raise Exception("Scheduler not initialized")

        schedule = await scheduler.collection.find_one(
            {"_id": __import__("bson").ObjectId(schedule_id)}
        )
        schedule_name = schedule.get("name", "Unnamed") if schedule else "Unknown"

        await scheduler.delete_schedule(schedule_id)
        logger.info(f"🗑️ Schedule '{schedule_name}' deleted by user {user_id}")

        bot_token = os.getenv("SLACK_CHATBOT_TOKEN")
        async with httpx.AsyncClient() as client:
            await client.post(
                SLACK_POST_MESSAGE_URL,
                json={
                    "channel": user_id,
                    "text": f"🗑️ Schedule *{schedule_name}* has been deleted.",
                },
                headers={
                    "Authorization": f"Bearer {bot_token}",
                    "Content-Type": "application/json",
                },
            )

        await publish_app_home(user_id)

    except Exception as e:
        logger.error(f"Failed to delete schedule {schedule_id}: {e}")
