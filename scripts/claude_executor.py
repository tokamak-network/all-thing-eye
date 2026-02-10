#!/usr/bin/env python3
"""
Claude Code Executor - Local Mac Polling Agent

Polls the ATI API for approved tickets and executes Claude Code locally.
Designed to tolerate Mac sleep/wake cycles gracefully.

Usage:
    python scripts/claude_executor.py

    # Or via make
    make executor
"""

import os
import sys
import re
import signal
import subprocess
import time
import threading
import requests
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env file
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# =============================================================================
# Configuration
# =============================================================================

ATI_API_URL = os.getenv("ATI_API_URL", "https://all.thing.eye.tokamak.network")
EXECUTOR_SECRET = os.getenv("EXECUTOR_SECRET", "")
POLL_INTERVAL = int(os.getenv("EXECUTOR_POLL_INTERVAL", "30"))
HEARTBEAT_INTERVAL = int(os.getenv("EXECUTOR_HEARTBEAT_INTERVAL", "60"))
PROJECT_DIR = str(project_root)
DEPLOY_SSH_HOST = "all-thing-eye"

# Git commit hash pattern (e.g. "commit abc1234" or "[abc1234]")
GIT_COMMIT_RE = re.compile(
    r'(?:commit\s+|[\[\(])([0-9a-f]{7,40})(?:[\]\)]|$|\s)', re.IGNORECASE
)

shutdown_event = threading.Event()


def log(msg: str):
    """Print timestamped log message."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def signal_handler(sig, frame):
    log("Shutting down executor...")
    shutdown_event.set()


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# =============================================================================
# API Client
# =============================================================================

def api_headers():
    return {
        "Authorization": f"Bearer {EXECUTOR_SECRET}",
        "Content-Type": "application/json",
    }


def api_get(path: str):
    """Make authenticated GET request to ATI API."""
    url = f"{ATI_API_URL}/api/v1/support{path}"
    resp = requests.get(url, headers=api_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, data: dict):
    """Make authenticated POST request to ATI API."""
    url = f"{ATI_API_URL}/api/v1/support{path}"
    resp = requests.post(url, json=data, headers=api_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


# =============================================================================
# Heartbeat Thread
# =============================================================================

def heartbeat_loop():
    """Background thread that sends heartbeat to API."""
    while not shutdown_event.is_set():
        try:
            api_post("/executor-heartbeat", {})
        except Exception as e:
            log(f"Heartbeat failed: {e}")
        shutdown_event.wait(timeout=HEARTBEAT_INTERVAL)


# =============================================================================
# Ticket Execution
# =============================================================================

def build_claude_prompt(ticket: dict) -> str:
    """Build the prompt for Claude Code CLI based on ticket data."""
    status = ticket.get("status", "approved")
    ticket_id = ticket.get("ticket_id", "")

    if status == "approved":
        # Normal ticket execution
        category = ticket.get("category", "question")
        title = ticket.get("title", "")
        description = ticket.get("description", "")

        # Collect all reporter messages
        messages = ticket.get("messages", [])
        reporter_msgs = [m["content"] for m in messages if m.get("from_type") == "reporter"]
        full_context = "\n\n".join(reporter_msgs) if reporter_msgs else description

        prompt = f"""You are working on the all-thing-eye project.

A support ticket [{ticket_id}] has been filed:
- Category: {category}
- Title: {title}
- Description: {full_context}

Please analyze the request and implement the necessary changes.
After making changes, provide a brief summary of what you did.
If you created any commits, mention the commit hash."""

    elif status == "review_requested":
        prompt = f"""You are working on the all-thing-eye project.

Ticket [{ticket_id}] has completed Claude Code execution and needs review.
Please start the development servers so the admin can review the changes:
- Backend: cd backend && uvicorn main:app --reload --port 8099
- Frontend: cd frontend && PORT=3099 npm run dev

Start both servers and report back that they are running."""

    elif status == "deploy_requested":
        prompt = f"""You are working on the all-thing-eye project.

Ticket [{ticket_id}] has been approved for deployment. Execute the deployment:
1. git push origin main
2. SSH to the server and pull + rebuild:
   ssh {DEPLOY_SSH_HOST} 'cd all-thing-eye && git pull && docker compose -f docker-compose.prod.yml build && docker compose -f docker-compose.prod.yml up -d'

Report the deployment result."""

    elif status == "revert_requested":
        prompt = f"""You are working on the all-thing-eye project.

Ticket [{ticket_id}] needs to be reverted. Execute:
1. git revert HEAD --no-edit
2. git push origin main

Report the revert result."""

    else:
        prompt = f"Ticket [{ticket_id}] has unknown status: {status}"

    return prompt


def execute_claude(ticket: dict) -> dict:
    """Execute Claude Code CLI for a ticket."""
    ticket_id = ticket.get("ticket_id", "")
    prompt = build_claude_prompt(ticket)

    log(f"Executing Claude for {ticket_id}...")

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--dangerously-skip-permissions"],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            cwd=PROJECT_DIR,
        )

        output = result.stdout or ""
        stderr = result.stderr or ""
        success = result.returncode == 0

        # Try to extract commit hash from output
        commit_hash = ""
        for line in output.split("\n"):
            match = GIT_COMMIT_RE.search(line)
            if match:
                commit_hash = match.group(1)
                break

        # Build summary (last meaningful lines of output)
        output_lines = [l for l in output.strip().split("\n") if l.strip()]
        summary = "\n".join(output_lines[-20:]) if output_lines else "No output"

        if not success:
            summary = f"Exit code: {result.returncode}\n{stderr[-500:]}\n{summary}"

        return {
            "success": success,
            "summary": summary[:2000],
            "commit_hash": commit_hash,
            "output": output[:5000],
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "summary": "Claude execution timed out (10 minutes)",
            "commit_hash": "",
            "output": "",
        }
    except FileNotFoundError:
        return {
            "success": False,
            "summary": "claude CLI not found. Make sure Claude Code is installed.",
            "commit_hash": "",
            "output": "",
        }
    except Exception as e:
        return {
            "success": False,
            "summary": f"Execution error: {str(e)}",
            "commit_hash": "",
            "output": "",
        }


def report_result_with_retry(ticket_id: str, result: dict, max_retries: int = 3):
    """Report execution result with retry logic."""
    payload = {
        "ticket_id": ticket_id,
        "success": result["success"],
        "summary": result["summary"],
        "commit_hash": result.get("commit_hash", ""),
        "output": result.get("output", ""),
    }
    for attempt in range(max_retries):
        try:
            api_post("/execution-result", payload)
            return True
        except Exception as e:
            log(f"Result report attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
    return False


def process_ticket(ticket: dict):
    """Claim and process a single ticket."""
    ticket_id = ticket.get("ticket_id", "")
    status = ticket.get("status", "")

    log(f"Processing {ticket_id} (status: {status})")

    # Claim the ticket atomically
    try:
        api_post("/claim-ticket", {"ticket_id": ticket_id})
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 409:
            log(f"{ticket_id} already claimed by another executor")
            return
        log(f"Failed to claim {ticket_id}: HTTP {e.response.status_code if e.response else 'unknown'}")
        return
    except Exception as e:
        log(f"Failed to claim {ticket_id}: {e}")
        return

    # Execute Claude
    result = execute_claude(ticket)

    # Report result with retry
    if report_result_with_retry(ticket_id, result):
        log(f"{ticket_id} completed: {'success' if result['success'] else 'failed'}")
    else:
        log(f"CRITICAL: Failed to report result for {ticket_id} after retries")


# =============================================================================
# Main Loop
# =============================================================================

def main():
    if not EXECUTOR_SECRET:
        log("FATAL: EXECUTOR_SECRET not set in environment")
        sys.exit(1)

    log(f"Claude Executor starting...")
    log(f"API URL: {ATI_API_URL}")
    log(f"Poll interval: {POLL_INTERVAL}s")
    log(f"Heartbeat interval: {HEARTBEAT_INTERVAL}s")
    log(f"Project dir: {PROJECT_DIR}")

    # Start heartbeat thread
    heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    heartbeat_thread.start()
    log("Heartbeat thread started")

    # Send initial heartbeat
    try:
        api_post("/executor-heartbeat", {})
        log("Initial heartbeat sent")
    except Exception as e:
        log(f"WARNING: Initial heartbeat failed: {e}")

    log("Polling for tickets...")

    while not shutdown_event.is_set():
        try:
            data = api_get("/queue")
            tickets = data.get("tickets", [])

            if tickets:
                log(f"Found {len(tickets)} ticket(s) in queue")
                for ticket in tickets:
                    if shutdown_event.is_set():
                        break
                    process_ticket(ticket)

        except requests.ConnectionError:
            log("API connection failed - server may be down")
        except requests.Timeout:
            log("API request timed out")
        except Exception as e:
            log(f"Poll error: {e}")

        # Sleep in small intervals so we can respond to shutdown quickly
        shutdown_event.wait(timeout=POLL_INTERVAL)

    log("Executor stopped")


if __name__ == "__main__":
    main()
