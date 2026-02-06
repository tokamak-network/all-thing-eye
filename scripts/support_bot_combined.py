#!/usr/bin/env python3
"""
ATI Support Bot - Combined Server

Runs both the Support Bot (Socket Mode) and Claude Webhook Server
in a single process with unified monitoring.

Usage:
    python scripts/support_bot_combined.py

    # Or via make
    make support
"""

import os
import sys
import signal
import threading
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env file
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# SSL fix for macOS - must be set before any imports that use SSL
import ssl
import certifi

# Set all SSL-related environment variables
cert_path = certifi.where()
os.environ['SSL_CERT_FILE'] = cert_path
os.environ['REQUESTS_CA_BUNDLE'] = cert_path
os.environ['WEBSOCKET_CLIENT_CA_BUNDLE'] = cert_path
os.environ['CURL_CA_BUNDLE'] = cert_path

# Override default SSL context creation
ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=cert_path)

# Monkey-patch ssl module for libraries that create their own context
_original_create_default_context = ssl.create_default_context
def _patched_create_default_context(purpose=ssl.Purpose.SERVER_AUTH, *, cafile=None, capath=None, cadata=None):
    ctx = _original_create_default_context(purpose, cafile=cafile or cert_path, capath=capath, cadata=cadata)
    return ctx
ssl.create_default_context = _patched_create_default_context

# ============================================================
# Configuration
# ============================================================

BOT_TOKEN = os.environ.get("SLACK_SUPPORT_BOT_TOKEN", "")
APP_TOKEN = os.environ.get("SLACK_SUPPORT_APP_TOKEN", "")
ADMIN_ID = os.environ.get("SLACK_SUPPORT_ADMIN_ID", "")
WEBHOOK_PORT = int(os.environ.get("CLAUDE_WEBHOOK_PORT", "9999"))
MONGODB_URI = os.environ.get("MONGODB_URI", "")
MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "ati")

# ============================================================
# Shared State
# ============================================================

active_tickets = set()
pending_approvals = {}  # ticket_id -> ticket_data
completed_tickets = {}  # ticket_id -> ticket_data
running_servers = {}    # ticket_id -> {"frontend_pid": ..., "backend_pid": ...}

# ============================================================
# Logging
# ============================================================

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log(component: str, message: str, color: str = Colors.ENDC):
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefix = {
        "BOT": f"{Colors.CYAN}[BOT]{Colors.ENDC}",
        "WEBHOOK": f"{Colors.BLUE}[WEBHOOK]{Colors.ENDC}",
        "CLAUDE": f"{Colors.GREEN}[CLAUDE]{Colors.ENDC}",
        "SYSTEM": f"{Colors.YELLOW}[SYSTEM]{Colors.ENDC}",
        "ERROR": f"{Colors.RED}[ERROR]{Colors.ENDC}",
    }.get(component, f"[{component}]")
    print(f"{Colors.BOLD}{timestamp}{Colors.ENDC} {prefix} {color}{message}{Colors.ENDC}")

# ============================================================
# Webhook Server
# ============================================================

import json
import subprocess
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

def send_slack_message(channel: str, text: str, blocks: list = None):
    """Send a Slack message."""
    if not BOT_TOKEN:
        log("WEBHOOK", "No Slack token, skipping notification", Colors.YELLOW)
        return False

    url = "https://slack.com/api/chat.postMessage"
    data = {"channel": channel, "text": text}
    if blocks:
        data["blocks"] = blocks

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={
            "Authorization": f"Bearer {BOT_TOKEN}",
            "Content-Type": "application/json"
        }
    )

    try:
        context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, context=context, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            if not result.get("ok"):
                log("ERROR", f"Slack API error: {result.get('error')}")
                return False
            return True
    except Exception as e:
        log("ERROR", f"Failed to send Slack message: {e}")
        return False


def notify_for_approval(ticket_id: str, category: str, title: str, description: str, reason: str):
    """Send approval request to admin via Slack."""
    if not ADMIN_ID:
        log("WEBHOOK", "No admin ID configured", Colors.YELLOW)
        return

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🎫 승인 대기: {ticket_id}"}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*유형:* {category}"},
                {"type": "mrkdwn", "text": f"*판단:* {reason}"}
            ]
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*제목:* {title}"}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*내용:*\n```{description[:500]}```"}
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ 승인"},
                    "style": "primary",
                    "action_id": f"approve_{ticket_id}",
                    "value": ticket_id
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ 거절"},
                    "style": "danger",
                    "action_id": f"reject_{ticket_id}",
                    "value": ticket_id
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "💬 답변"},
                    "action_id": f"reply_{ticket_id}",
                    "value": ticket_id
                }
            ]
        }
    ]

    send_slack_message(ADMIN_ID, f"승인 대기: {ticket_id} - {title}", blocks)
    log("WEBHOOK", f"Sent approval request to admin for {ticket_id}")


def notify_completion(ticket_id: str, success: bool, summary: str = ""):
    """Notify admin that Claude has completed the task."""
    if not ADMIN_ID:
        return

    status_emoji = "✅" if success else "❌"
    status_text = "완료" if success else "실패"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{status_emoji} Claude 작업 {status_text}: {ticket_id}"}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": summary[:2000] if summary else "작업이 완료되었습니다."}
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔍 리뷰 (서버 시작)"},
                    "action_id": f"review_{ticket_id}",
                    "value": ticket_id
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ 배포"},
                    "style": "primary",
                    "action_id": f"deploy_{ticket_id}",
                    "value": ticket_id
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "↩️ Revert"},
                    "style": "danger",
                    "action_id": f"revert_{ticket_id}",
                    "value": ticket_id
                }
            ]
        }
    ]

    send_slack_message(ADMIN_ID, f"Claude 작업 {status_text}: {ticket_id}", blocks)


def run_claude(ticket_id: str, prompt: str) -> tuple[bool, str]:
    """Run Claude Code with the given prompt - streams output in real-time."""
    log("CLAUDE", f"Starting Claude for {ticket_id}...")
    print(f"\n{'='*60}")
    print(f"  CLAUDE OUTPUT [{ticket_id}]")
    print(f"{'='*60}\n")
    active_tickets.add(ticket_id)

    output_lines = []

    try:
        process = subprocess.Popen(
            ["claude", "-p", prompt, "--dangerously-skip-permissions"],
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Stream output in real-time
        for line in iter(process.stdout.readline, ''):
            if line:
                print(f"  {line}", end='')
                output_lines.append(line)

        process.wait(timeout=600)
        output = ''.join(output_lines)
        success = process.returncode == 0

        print(f"\n{'='*60}")
        log("CLAUDE", f"Claude finished for {ticket_id} (success={success})")

        # Store for review
        completed_tickets[ticket_id] = {
            "success": success,
            "output": output[-2000:] if output else ""
        }

        return success, output[-1000:] if output else ""

    except subprocess.TimeoutExpired:
        process.kill()
        log("ERROR", f"Claude timed out for {ticket_id}")
        return False, "Timeout after 10 minutes"
    except Exception as e:
        log("ERROR", f"Claude failed for {ticket_id}: {e}")
        return False, str(e)
    finally:
        active_tickets.discard(ticket_id)


def process_ticket(ticket_id: str, category: str, title: str, description: str):
    """Process incoming ticket - always require approval."""
    log("WEBHOOK", f"New ticket: {ticket_id} ({category})")

    pending_approvals[ticket_id] = {
        "category": category,
        "title": title,
        "description": description,
        "timestamp": datetime.now().isoformat()
    }

    notify_for_approval(ticket_id, category, title, description, "승인 대기")


def execute_approved_ticket(ticket_id: str):
    """Execute an approved ticket with Claude."""
    if ticket_id not in pending_approvals:
        log("ERROR", f"Ticket {ticket_id} not found in pending")
        return

    ticket = pending_approvals.pop(ticket_id)

    prompt = f"""[Support Ticket: {ticket_id}]
Category: {ticket['category']}
Title: {ticket['title']}

Description:
{ticket['description']}

Please fix/implement this. After completion, commit with a clear message.
"""

    def run_async():
        success, output = run_claude(ticket_id, prompt)
        notify_completion(ticket_id, success, output)

    thread = threading.Thread(target=run_async, daemon=True)
    thread.start()

    log("WEBHOOK", f"Started Claude for {ticket_id}")


class WebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging

    def send_json(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {
                "status": "ok",
                "active": list(active_tickets),
                "pending": list(pending_approvals.keys())
            })
        elif self.path == "/pending":
            self.send_json(200, {"pending": pending_approvals})
        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode() if content_length else "{}"

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        if self.path == "/ticket":
            ticket_id = data.get("ticket_id", f"TKT-{int(time.time())}")
            category = data.get("category", "bug")
            title = data.get("title", "No title")
            description = data.get("description", "")

            process_ticket(ticket_id, category, title, description)
            self.send_json(200, {"status": "pending_approval", "ticket_id": ticket_id})

        elif self.path == "/approve":
            ticket_id = data.get("ticket_id")
            if ticket_id and ticket_id in pending_approvals:
                execute_approved_ticket(ticket_id)
                self.send_json(200, {"status": "executing", "ticket_id": ticket_id})
            else:
                self.send_json(404, {"error": "Ticket not found"})

        elif self.path == "/reject":
            ticket_id = data.get("ticket_id")
            if ticket_id and ticket_id in pending_approvals:
                pending_approvals.pop(ticket_id)
                log("WEBHOOK", f"Rejected ticket: {ticket_id}")
                self.send_json(200, {"status": "rejected", "ticket_id": ticket_id})
            else:
                self.send_json(404, {"error": "Ticket not found"})

        elif self.path == "/review":
            ticket_id = data.get("ticket_id")
            # Start review servers
            log("WEBHOOK", f"Starting review servers for {ticket_id}")
            try:
                frontend = subprocess.Popen(
                    ["npm", "run", "dev"],
                    cwd=str(project_root / "frontend"),
                    env={**os.environ, "PORT": "3099"},
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                backend = subprocess.Popen(
                    ["uvicorn", "backend.main:app", "--port", "8099"],
                    cwd=str(project_root),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                running_servers[ticket_id] = {
                    "frontend_pid": frontend.pid,
                    "backend_pid": backend.pid
                }
                self.send_json(200, {
                    "status": "servers_started",
                    "frontend": "http://localhost:3099",
                    "backend": "http://localhost:8099"
                })
            except Exception as e:
                self.send_json(500, {"error": str(e)})

        elif self.path == "/revert":
            ticket_id = data.get("ticket_id")
            log("WEBHOOK", f"Reverting changes for {ticket_id}")
            try:
                result = subprocess.run(
                    ["git", "reset", "--hard", "HEAD~1"],
                    cwd=str(project_root),
                    capture_output=True,
                    text=True
                )
                self.send_json(200, {"status": "reverted", "output": result.stdout})
            except Exception as e:
                self.send_json(500, {"error": str(e)})

        elif self.path == "/stop-servers":
            ticket_id = data.get("ticket_id")
            if ticket_id in running_servers:
                servers = running_servers.pop(ticket_id)
                for pid in [servers.get("frontend_pid"), servers.get("backend_pid")]:
                    if pid:
                        try:
                            os.kill(pid, signal.SIGTERM)
                        except:
                            pass
                self.send_json(200, {"status": "stopped"})
            else:
                self.send_json(404, {"error": "No servers found"})
        else:
            self.send_json(404, {"error": "Not found"})


def run_webhook_server():
    """Run the webhook server."""
    server = HTTPServer(("0.0.0.0", WEBHOOK_PORT), WebhookHandler)
    log("SYSTEM", f"Webhook server running on port {WEBHOOK_PORT}")
    server.serve_forever()


# ============================================================
# Slack Bot (Socket Mode)
# ============================================================

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.web import WebClient
import httpx
from motor.motor_asyncio import AsyncIOMotorClient

# Create SSL context for Slack
ssl_context = ssl.create_default_context(cafile=certifi.where())

# Create WebClient with SSL
web_client = WebClient(token=BOT_TOKEN, ssl=ssl_context)
slack_app = App(token=BOT_TOKEN, client=web_client)

_mongo_client = None
_db = None

def get_db():
    global _mongo_client, _db
    if _db is None:
        _mongo_client = AsyncIOMotorClient(MONGODB_URI)
        _db = _mongo_client[MONGODB_DATABASE]
    return _db


def generate_ticket_id_sync() -> str:
    """Generate next ticket ID (sync version)."""
    import pymongo
    client = pymongo.MongoClient(MONGODB_URI)
    db = client[MONGODB_DATABASE]

    last = db.support_tickets.find_one(sort=[("created_at", -1)])
    if last and "ticket_id" in last:
        try:
            num = int(last["ticket_id"].split("-")[1]) + 1
        except:
            num = 1
    else:
        num = 1

    client.close()
    return f"TKT-{num:03d}"


def detect_category(text: str) -> str:
    """Auto-detect category from text."""
    text_lower = text.lower()
    bug_keywords = ['bug', 'error', 'fix', 'broken', 'crash', '버그', '오류', '에러', '안됨', '안돼', '문제', '수정']
    feature_keywords = ['feature', 'add', 'new', 'implement', '기능', '추가', '개선', '만들어', '넣어']

    if any(kw in text_lower for kw in bug_keywords):
        return "bug"
    elif any(kw in text_lower for kw in feature_keywords):
        return "feature"
    return "question"


@slack_app.command("/ati-support")
def handle_support_command(ack, body, client):
    """Handle /ati-support command - open modal."""
    ack()

    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "support_ticket_modal",
            "title": {"type": "plain_text", "text": "Support Ticket"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "description_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "description",
                        "multiline": True,
                        "placeholder": {"type": "plain_text", "text": "버그 리포트, 기능 요청, 질문 등 자유롭게 작성하세요..."}
                    },
                    "label": {"type": "plain_text", "text": "무엇을 도와드릴까요?"}
                }
            ]
        }
    )
    log("BOT", f"Opened ticket modal for {body['user_id']}")


@slack_app.view("support_ticket_modal")
def handle_modal_submission(ack, body, client, view):
    """Handle modal submission."""
    ack()

    values = view["state"]["values"]
    description = values["description_block"]["description"]["value"]
    user_id = body["user"]["id"]

    # Auto-detect category and generate title
    category = detect_category(description)
    title = description.split('\n')[0][:50] if description else "No description"

    ticket_id = generate_ticket_id_sync()

    log("BOT", f"New ticket from modal: {ticket_id}")

    # Save to MongoDB
    import pymongo
    mongo_client = pymongo.MongoClient(MONGODB_URI)
    db = mongo_client[MONGODB_DATABASE]
    db.support_tickets.insert_one({
        "ticket_id": ticket_id,
        "reporter_id": user_id,
        "category": category,
        "title": title,
        "description": description,
        "status": "open",
        "created_at": datetime.utcnow()
    })
    mongo_client.close()

    # Send to webhook server
    process_ticket(ticket_id, category, title, description)

    # Confirm to user
    client.chat_postMessage(
        channel=user_id,
        text=f"✅ 티켓이 생성되었습니다: *{ticket_id}*\n카테고리: {category}\n제목: {title}"
    )


@slack_app.event("message")
def handle_dm_message(event, client, say):
    """Handle direct messages to create tickets."""
    # Only handle DMs (channel_type: im)
    if event.get("channel_type") != "im":
        return

    # Ignore bot messages
    if event.get("bot_id") or event.get("subtype"):
        return

    user_id = event.get("user")
    text = event.get("text", "").strip()

    if not text:
        return

    # Auto-detect category and generate title
    category = detect_category(text)
    title = text.split('\n')[0][:50]

    ticket_id = generate_ticket_id_sync()

    log("BOT", f"New ticket from DM: {ticket_id}")

    # Save to MongoDB
    import pymongo
    mongo_client = pymongo.MongoClient(MONGODB_URI)
    db = mongo_client[MONGODB_DATABASE]
    db.support_tickets.insert_one({
        "ticket_id": ticket_id,
        "reporter_id": user_id,
        "category": category,
        "title": title,
        "description": text,
        "status": "open",
        "created_at": datetime.utcnow()
    })
    mongo_client.close()

    # Send to webhook for approval
    process_ticket(ticket_id, category, title, text)

    # Confirm to user
    say(f"✅ 티켓이 생성되었습니다: *{ticket_id}*\n카테고리: {category}\n내용: {title}")


import re

@slack_app.action(re.compile(r"approve_.*"))
def handle_approve(ack, body, client):
    """Handle approve button click."""
    ack()
    action_id = body["actions"][0]["action_id"]
    ticket_id = action_id.replace("approve_", "")

    log("BOT", f"Approve clicked for {ticket_id}")
    execute_approved_ticket(ticket_id)

    client.chat_postMessage(
        channel=ADMIN_ID,
        text=f"✅ {ticket_id} 승인됨. Claude가 작업을 시작합니다..."
    )


@slack_app.action(re.compile(r"reject_.*"))
def handle_reject(ack, body, client):
    """Handle reject button click."""
    ack()
    action_id = body["actions"][0]["action_id"]
    ticket_id = action_id.replace("reject_", "")

    log("BOT", f"Reject clicked for {ticket_id}")

    if ticket_id in pending_approvals:
        pending_approvals.pop(ticket_id)

    client.chat_postMessage(
        channel=ADMIN_ID,
        text=f"❌ {ticket_id} 거절됨."
    )


@slack_app.action(re.compile(r"reply_.*"))
def handle_reply(ack, body, client):
    """Handle reply button click - open reply modal."""
    ack()
    action_id = body["actions"][0]["action_id"]
    ticket_id = action_id.replace("reply_", "")

    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": f"reply_modal_{ticket_id}",
            "title": {"type": "plain_text", "text": "Reply"},
            "submit": {"type": "plain_text", "text": "Send"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "reply_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "reply_text",
                        "multiline": True
                    },
                    "label": {"type": "plain_text", "text": "Message"}
                }
            ]
        }
    )


@slack_app.action(re.compile(r"review_.*"))
def handle_review(ack, body, client):
    """Handle review button click - start servers."""
    ack()
    action_id = body["actions"][0]["action_id"]
    ticket_id = action_id.replace("review_", "")

    log("BOT", f"Review clicked for {ticket_id}")

    # Start review servers
    try:
        frontend = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(project_root / "frontend"),
            env={**os.environ, "PORT": "3099"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        backend = subprocess.Popen(
            ["uvicorn", "backend.main:app", "--port", "8099"],
            cwd=str(project_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        running_servers[ticket_id] = {
            "frontend_pid": frontend.pid,
            "backend_pid": backend.pid
        }

        client.chat_postMessage(
            channel=ADMIN_ID,
            text=f"🚀 Review servers started for {ticket_id}:\n• Frontend: http://localhost:3099\n• Backend: http://localhost:8099"
        )
    except Exception as e:
        client.chat_postMessage(
            channel=ADMIN_ID,
            text=f"❌ Failed to start servers: {e}"
        )


@slack_app.action(re.compile(r"revert_.*"))
def handle_revert(ack, body, client):
    """Handle revert button click."""
    ack()
    action_id = body["actions"][0]["action_id"]
    ticket_id = action_id.replace("revert_", "")

    log("BOT", f"Revert clicked for {ticket_id}")

    try:
        result = subprocess.run(
            ["git", "reset", "--hard", "HEAD~1"],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )
        client.chat_postMessage(
            channel=ADMIN_ID,
            text=f"↩️ Reverted changes for {ticket_id}\n```{result.stdout}```"
        )
    except Exception as e:
        client.chat_postMessage(
            channel=ADMIN_ID,
            text=f"❌ Revert failed: {e}"
        )


@slack_app.action(re.compile(r"deploy_.*"))
def handle_deploy(ack, body, client):
    """Handle deploy button click - push and deploy to server."""
    ack()
    action_id = body["actions"][0]["action_id"]
    ticket_id = action_id.replace("deploy_", "")

    log("BOT", f"Deploy clicked for {ticket_id}")

    client.chat_postMessage(
        channel=ADMIN_ID,
        text=f"🚀 배포 시작: {ticket_id}..."
    )

    def deploy_async():
        try:
            # Step 1: Git push
            log("BOT", "Step 1: Git push...")
            push_result = subprocess.run(
                ["git", "push"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=60
            )
            if push_result.returncode != 0:
                raise Exception(f"Git push failed: {push_result.stderr}")

            client.chat_postMessage(
                channel=ADMIN_ID,
                text=f"✅ Git push 완료"
            )

            # Step 2: SSH and deploy
            log("BOT", "Step 2: SSH deploy...")
            github_token = os.environ.get("GITHUB_ACCOUNT_TOKEN", "")
            # AUTO_DEPLOY=1 triggers automatic deployment in post-merge hook
            ssh_commands = f"""
cd all-thing-eye && \
git config --global credential.helper 'cache --timeout=86400' && \
echo -e 'protocol=https\\nhost=github.com\\nusername=SonYoungsung\\npassword={github_token}' | git credential-cache store && \
AUTO_DEPLOY=1 git pull
"""
            ssh_result = subprocess.run(
                ["ssh", "all-thing-eye", ssh_commands],
                capture_output=True,
                text=True,
                timeout=600
            )
            if ssh_result.returncode != 0 and "fatal" in ssh_result.stderr.lower():
                raise Exception(f"SSH deploy failed: {ssh_result.stderr}")

            # Step 3: Stop local review servers if running
            if ticket_id in running_servers:
                servers = running_servers.pop(ticket_id)
                for pid in [servers.get("frontend_pid"), servers.get("backend_pid")]:
                    if pid:
                        try:
                            os.kill(pid, signal.SIGTERM)
                        except:
                            pass

            client.chat_postMessage(
                channel=ADMIN_ID,
                text=f"✅ 배포 완료: {ticket_id}\n\n```{ssh_result.stdout[-1000:] if ssh_result.stdout else 'Success'}```"
            )
            log("BOT", f"Deploy completed for {ticket_id}")

        except Exception as e:
            log("ERROR", f"Deploy failed: {e}")
            client.chat_postMessage(
                channel=ADMIN_ID,
                text=f"❌ 배포 실패: {ticket_id}\n```{str(e)}```"
            )

    # Run deployment in background thread
    thread = threading.Thread(target=deploy_async, daemon=True)
    thread.start()


def run_slack_bot():
    """Run the Slack bot."""
    log("SYSTEM", "Starting Slack bot (Socket Mode)...")
    handler = SocketModeHandler(app=slack_app, app_token=APP_TOKEN)
    handler.start()


# ============================================================
# Main
# ============================================================

def print_banner():
    print(f"""
{Colors.BOLD}{Colors.CYAN}╔════════════════════════════════════════════════════════════╗
║            ATI Support Bot - Combined Server               ║
╠════════════════════════════════════════════════════════════╣
║  Webhook: http://localhost:{WEBHOOK_PORT:<5}                           ║
║  Slack:   Socket Mode                                      ║
║  Admin:   {ADMIN_ID or 'Not configured':<20}                       ║
╠════════════════════════════════════════════════════════════╣
║  Commands:                                                 ║
║  • /ati-support - Create a ticket                         ║
║  • Approve/Reject buttons for admin                       ║
║  • Review/Revert buttons after completion                 ║
╚════════════════════════════════════════════════════════════╝{Colors.ENDC}
""")


def main():
    print_banner()

    # Validate config
    if not BOT_TOKEN:
        log("ERROR", "SLACK_SUPPORT_BOT_TOKEN not set!")
        sys.exit(1)
    if not APP_TOKEN:
        log("ERROR", "SLACK_SUPPORT_APP_TOKEN not set!")
        sys.exit(1)

    # Start webhook server in background thread
    webhook_thread = threading.Thread(target=run_webhook_server, daemon=True)
    webhook_thread.start()
    log("SYSTEM", "Webhook server started")

    # Run Slack bot in main thread
    try:
        run_slack_bot()
    except KeyboardInterrupt:
        log("SYSTEM", "Shutting down...")

        # Kill any running review servers
        for ticket_id, servers in running_servers.items():
            for pid in [servers.get("frontend_pid"), servers.get("backend_pid")]:
                if pid:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except:
                        pass

        print("\n👋 Bye!")


if __name__ == "__main__":
    main()
