#!/usr/bin/env python3
"""
Claude Code Webhook Server (Approval Mode)

Receives support ticket webhooks and:
- Simple tasks → Auto mode (immediate execution)
- Complex tasks → Slack notification with approval button

Usage:
    python scripts/claude_webhook_server.py

Environment Variables:
    CLAUDE_WEBHOOK_PORT: Port to listen on (default: 9999)
    CLAUDE_WORK_DIR: Directory where Claude Code should work (default: current dir)
    SLACK_SUPPORT_BOT_TOKEN: Slack bot token for notifications
    SLACK_SUPPORT_ADMIN_ID: Admin Slack User ID for notifications
"""

import os
import json
import subprocess
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from pathlib import Path

# Load .env file
from dotenv import load_dotenv
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

PORT = int(os.getenv("CLAUDE_WEBHOOK_PORT", "9999"))
WORK_DIR = os.getenv("CLAUDE_WORK_DIR", os.getcwd())
SLACK_BOT_TOKEN = os.getenv("SLACK_SUPPORT_BOT_TOKEN", "")
SLACK_ADMIN_ID = os.getenv("SLACK_SUPPORT_ADMIN_ID", "")

# Track active sessions and pending approvals
active_tickets = set()
pending_approvals = {}  # ticket_id -> ticket_data
completed_tickets = {}  # ticket_id -> ticket_data (for review)
running_servers = {}  # ticket_id -> {"frontend_pid": ..., "backend_pid": ...}


def send_slack_message(channel: str, text: str, blocks: list = None):
    """Send a Slack message."""
    if not SLACK_BOT_TOKEN:
        print(f"⚠️  No Slack token, skipping notification")
        return False

    url = "https://slack.com/api/chat.postMessage"
    data = {"channel": channel, "text": text}
    if blocks:
        data["blocks"] = blocks

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("ok"):
                print(f"✅ Slack notification sent")
            return result.get("ok", False)
    except Exception as e:
        print(f"❌ Slack notification failed: {e}")
        return False


def notify_completion(ticket_id: str, title: str, success: bool):
    """Send completion notification with review button."""
    if not SLACK_ADMIN_ID:
        print(f"⚠️  No admin ID, skipping completion notification")
        return

    if success:
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"✅ *[{ticket_id}]* 개발 완료!\n*{title}*",
                },
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "`git log -1` 또는 `git diff HEAD~1`로 변경사항 확인"}
                ],
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "🔍 Review in Browser", "emoji": True},
                        "style": "primary",
                        "action_id": f"review_{ticket_id}",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "🗑️ Revert", "emoji": True},
                        "style": "danger",
                        "action_id": f"revert_{ticket_id}",
                    },
                ],
            },
        ]
    else:
        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"❌ *[{ticket_id}]* 개발 실패\n*{title}*"},
            },
        ]

    send_slack_message(SLACK_ADMIN_ID, f"Ticket {ticket_id} completed", blocks)


def start_review_servers(ticket_id: str):
    """Start frontend and backend servers for review."""
    global running_servers

    # Stop any existing servers for this ticket
    stop_review_servers(ticket_id)

    frontend_port = 3099
    backend_port = 8099

    print(f"\n🚀 Starting review servers for {ticket_id}...")

    try:
        # Start backend (FastAPI)
        backend_process = subprocess.Popen(
            ["uvicorn", "backend.main:app", "--port", str(backend_port), "--reload"],
            cwd=WORK_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"   Backend: http://localhost:{backend_port}")

        # Start frontend (Next.js)
        frontend_env = os.environ.copy()
        frontend_env["PORT"] = str(frontend_port)
        frontend_process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=os.path.join(WORK_DIR, "frontend"),
            env=frontend_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"   Frontend: http://localhost:{frontend_port}")

        running_servers[ticket_id] = {
            "frontend_pid": frontend_process.pid,
            "backend_pid": backend_process.pid,
            "frontend_port": frontend_port,
            "backend_port": backend_port,
        }

        # Notify via Slack
        if SLACK_ADMIN_ID:
            send_slack_message(
                SLACK_ADMIN_ID,
                f"🔍 *[{ticket_id}]* Review servers started!\n\n"
                f"• Frontend: http://localhost:{frontend_port}\n"
                f"• Backend: http://localhost:{backend_port}/api/docs\n\n"
                f"_서버 종료: 다음 티켓 리뷰 시 자동 종료_",
            )

        return True

    except Exception as e:
        print(f"❌ Failed to start servers: {e}")
        return False


def stop_review_servers(ticket_id: str = None):
    """Stop review servers."""
    global running_servers

    if ticket_id and ticket_id in running_servers:
        servers = running_servers[ticket_id]
        try:
            os.kill(servers["frontend_pid"], 9)
        except:
            pass
        try:
            os.kill(servers["backend_pid"], 9)
        except:
            pass
        del running_servers[ticket_id]
        print(f"🛑 Stopped servers for {ticket_id}")
    elif not ticket_id:
        # Stop all
        for tid in list(running_servers.keys()):
            stop_review_servers(tid)


def revert_last_commit(ticket_id: str):
    """Revert the last commit."""
    try:
        result = subprocess.run(
            ["git", "revert", "--no-edit", "HEAD"],
            cwd=WORK_DIR,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"✅ Reverted last commit for {ticket_id}")
            if SLACK_ADMIN_ID:
                send_slack_message(
                    SLACK_ADMIN_ID,
                    f"🗑️ *[{ticket_id}]* 마지막 커밋이 되돌려졌습니다.\n`git log -2`로 확인하세요.",
                )
            return True
        else:
            print(f"❌ Revert failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Revert error: {e}")
        return False


def assess_complexity(category: str, title: str, description: str) -> dict:
    """Assess ticket complexity using heuristics."""
    title_lower = title.lower()
    desc_lower = description.lower()
    combined = f"{title_lower} {desc_lower}"

    # Keywords that indicate complexity (need approval)
    complex_keywords = [
        "multi-tenant", "architecture", "refactor", "migration", "security",
        "authentication", "authorization", "database schema", "api design",
        "integration", "infrastructure", "deploy", "scale", "performance",
        "새로운 기능", "아키텍처", "리팩토링", "마이그레이션", "보안",
    ]

    # Keywords that indicate simplicity (auto-execute)
    simple_keywords = [
        "typo", "오타", "color", "색상", "text", "텍스트", "label", "레이블",
        "spacing", "간격", "margin", "padding", "font", "폰트", "icon", "아이콘",
        "tooltip", "placeholder", "button text", "버튼 텍스트",
    ]

    is_complex = any(kw in combined for kw in complex_keywords)
    is_simple = any(kw in combined for kw in simple_keywords)

    # Feature requests default to complex
    if category == "feature" and not is_simple:
        is_complex = True

    if is_complex:
        return {"mode": "approval", "reason": "Complex task - needs approval"}
    if is_simple:
        return {"mode": "auto", "reason": "Simple task - auto execute"}

    # Default: approval for safety
    return {"mode": "approval", "reason": "Uncertain - requesting approval"}


def notify_for_approval(ticket_id: str, category: str, title: str, description: str, reason: str):
    """Send Slack notification with approval button."""
    if not SLACK_ADMIN_ID:
        print(f"⚠️  No admin ID configured, cannot send approval request")
        return

    category_emoji = {"bug": "🐛", "feature": "✨", "question": "❓"}.get(category, "🎫")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🎫 New Ticket: {ticket_id}", "emoji": True},
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*{category_emoji} Category:*\n{category}"},
                {"type": "mrkdwn", "text": f"*📋 Status:*\nPending Approval"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*📝 Title:*\n{title}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Description:*\n>{description[:300]}{'...' if len(description) > 300 else ''}"},
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"_Assessment: {reason}_"}],
        },
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Approve & Start", "emoji": True},
                    "style": "primary",
                    "action_id": f"claude_approve_{ticket_id}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Reject", "emoji": True},
                    "style": "danger",
                    "action_id": f"claude_reject_{ticket_id}",
                },
            ],
        },
    ]

    send_slack_message(SLACK_ADMIN_ID, f"New ticket pending approval: {ticket_id}", blocks)


def run_claude_auto(ticket_id: str, category: str, title: str, description: str):
    """Run Claude in auto mode (immediate execution)."""
    print(f"\n🤖 AUTO mode for {ticket_id}...")

    if category == "bug":
        prompt = f"""[{ticket_id}] Bug Fix

Title: {title}
Description: {description}

1. Find the relevant code
2. Fix the bug
3. Commit: "fix: {title} [{ticket_id}]"

Keep changes minimal and focused."""
    else:
        prompt = f"""[{ticket_id}] Feature

Title: {title}
Description: {description}

1. Understand requirements
2. Implement the feature
3. Commit: "feat: {title} [{ticket_id}]"

Keep changes minimal and focused."""

    try:
        result = subprocess.run(
            ["claude", "--dangerously-skip-permissions", "-p", prompt],
            cwd=WORK_DIR,
            capture_output=True,
            text=True,
            timeout=600,
        )

        if result.returncode == 0:
            print(f"✅ Completed {ticket_id}")
            completed_tickets[ticket_id] = {"title": title, "category": category}
            notify_completion(ticket_id, title, success=True)
        else:
            print(f"❌ Failed {ticket_id}: {result.stderr[:200]}")
            notify_completion(ticket_id, title, success=False)

    except subprocess.TimeoutExpired:
        print(f"⏰ Timeout {ticket_id}")
        notify_completion(ticket_id, title, success=False)
    except Exception as e:
        print(f"❌ Error {ticket_id}: {e}")
        notify_completion(ticket_id, title, success=False)
    finally:
        active_tickets.discard(ticket_id)


def run_claude_approved(ticket_id: str):
    """Run Claude after approval."""
    ticket = pending_approvals.get(ticket_id)
    if not ticket:
        print(f"❌ Ticket {ticket_id} not found in pending approvals")
        return

    category = ticket["category"]
    title = ticket["title"]
    description = ticket["description"]

    print(f"\n🚀 APPROVED: Starting {ticket_id}...")

    if category == "bug":
        prompt = f"""[{ticket_id}] Bug Fix (Approved)

Title: {title}
Description: {description}

1. Analyze the bug
2. Search codebase for relevant code
3. Implement the fix
4. Test if possible
5. Commit: "fix: {title} [{ticket_id}]"
"""
    else:
        prompt = f"""[{ticket_id}] Feature (Approved)

Title: {title}
Description: {description}

1. Understand requirements fully
2. Search codebase for related code
3. Plan the implementation
4. Implement the feature
5. Commit: "feat: {title} [{ticket_id}]"
"""

    try:
        result = subprocess.run(
            ["claude", "--dangerously-skip-permissions", "-p", prompt],
            cwd=WORK_DIR,
            capture_output=True,
            text=True,
            timeout=900,  # 15 min for approved tasks
        )

        if result.returncode == 0:
            print(f"✅ Completed {ticket_id}")
            completed_tickets[ticket_id] = {"title": title, "category": category}
            notify_completion(ticket_id, title, success=True)
        else:
            print(f"❌ Failed {ticket_id}")
            notify_completion(ticket_id, title, success=False)

    except subprocess.TimeoutExpired:
        print(f"⏰ Timeout {ticket_id}")
        notify_completion(ticket_id, title, success=False)
    except Exception as e:
        print(f"❌ Error {ticket_id}: {e}")
        notify_completion(ticket_id, title, success=False)
    finally:
        active_tickets.discard(ticket_id)
        pending_approvals.pop(ticket_id, None)


def process_ticket(ticket_id: str, category: str, title: str, description: str):
    """Process a ticket - always request approval first."""
    assessment = assess_complexity(category, title, description)
    reason = assessment["reason"]

    print(f"📊 Assessment: {reason}")

    # Always require approval
    pending_approvals[ticket_id] = {
        "category": category,
        "title": title,
        "description": description,
        "timestamp": datetime.now().isoformat(),
    }
    notify_for_approval(ticket_id, category, title, description, reason)
    active_tickets.discard(ticket_id)


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Handle ticket submission
        if self.path == "/ticket":
            try:
                ticket = json.loads(body.decode("utf-8"))
                ticket_id = ticket.get("ticket_id")
                category = ticket.get("category")
                title = ticket.get("title")
                description = ticket.get("description")

                print(f"\n{'='*50}")
                print(f"🎫 {ticket_id} | {category} | {title}")
                print(f"{'='*50}")

                if ticket_id in active_tickets or ticket_id in pending_approvals:
                    self._respond(200, {"status": "already_processing"})
                    return

                if category in ["bug", "feature"]:
                    active_tickets.add(ticket_id)
                    thread = threading.Thread(
                        target=process_ticket,
                        args=(ticket_id, category, title, description),
                    )
                    thread.start()
                    self._respond(200, {"status": "started"})
                else:
                    self._respond(200, {"status": "skipped"})

            except Exception as e:
                print(f"❌ Error: {e}")
                self._respond(500, {"error": str(e)})
            return

        # Handle approval from Slack (simplified - real implementation would be in support_bot.py)
        if self.path == "/approve":
            try:
                data = json.loads(body.decode("utf-8"))
                ticket_id = data.get("ticket_id")

                if ticket_id in pending_approvals:
                    active_tickets.add(ticket_id)
                    thread = threading.Thread(target=run_claude_approved, args=(ticket_id,))
                    thread.start()
                    self._respond(200, {"status": "approved", "ticket_id": ticket_id})
                else:
                    self._respond(404, {"error": "Ticket not found"})

            except Exception as e:
                self._respond(500, {"error": str(e)})
            return

        # Handle rejection
        if self.path == "/reject":
            try:
                data = json.loads(body.decode("utf-8"))
                ticket_id = data.get("ticket_id")
                pending_approvals.pop(ticket_id, None)
                self._respond(200, {"status": "rejected"})
            except Exception as e:
                self._respond(500, {"error": str(e)})
            return

        # Handle review (start servers)
        if self.path == "/review":
            try:
                data = json.loads(body.decode("utf-8"))
                ticket_id = data.get("ticket_id")
                if start_review_servers(ticket_id):
                    self._respond(200, {
                        "status": "started",
                        "frontend": f"http://localhost:{running_servers[ticket_id]['frontend_port']}",
                        "backend": f"http://localhost:{running_servers[ticket_id]['backend_port']}",
                    })
                else:
                    self._respond(500, {"error": "Failed to start servers"})
            except Exception as e:
                self._respond(500, {"error": str(e)})
            return

        # Handle revert
        if self.path == "/revert":
            try:
                data = json.loads(body.decode("utf-8"))
                ticket_id = data.get("ticket_id")
                if revert_last_commit(ticket_id):
                    self._respond(200, {"status": "reverted"})
                else:
                    self._respond(500, {"error": "Failed to revert"})
            except Exception as e:
                self._respond(500, {"error": str(e)})
            return

        # Handle stop servers
        if self.path == "/stop-servers":
            try:
                data = json.loads(body.decode("utf-8"))
                ticket_id = data.get("ticket_id")
                stop_review_servers(ticket_id)
                self._respond(200, {"status": "stopped"})
            except Exception as e:
                self._respond(500, {"error": str(e)})
            return

        self._respond(404, {"error": "Not found"})

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {
                "status": "ok",
                "active": list(active_tickets),
                "pending": list(pending_approvals.keys()),
            })
            return

        if self.path == "/pending":
            self._respond(200, {"pending": pending_approvals})
            return

        self._respond(404, {"error": "Not found"})

    def _respond(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        pass


def main():
    slack_status = "✅" if SLACK_BOT_TOKEN and SLACK_ADMIN_ID else "❌"

    print(f"""
╔════════════════════════════════════════════════════════════╗
║         Claude Code Webhook Server (Approval Mode)         ║
╠════════════════════════════════════════════════════════════╣
║  Port: {PORT}                                                 ║
║  Slack: {slack_status}                                               ║
║                                                            ║
║  Flow:                                                     ║
║  • Simple bug/typo → Auto execute                         ║
║  • Complex feature → Slack approval → Execute             ║
║                                                            ║
║  Endpoints:                                                ║
║  • POST /ticket   - New ticket                            ║
║  • POST /approve  - Approve pending ticket                ║
║  • POST /reject   - Reject pending ticket                 ║
║  • GET  /health   - Status                                ║
║  • GET  /pending  - List pending approvals                ║
╚════════════════════════════════════════════════════════════╝
    """)

    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Bye!")
        server.shutdown()


if __name__ == "__main__":
    main()
