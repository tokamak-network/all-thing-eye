#!/usr/bin/env python3
"""
Weekly Output Bot (Multi-Schedule)

Reads active schedules from MongoDB and runs them concurrently.
Each schedule defines its own channel, members, and timing.

Usage:
    python scripts/weekly_output_bot.py

    # Or via make
    make weekly

Recommended cron / systemd:
    Run as a long-lived process (APScheduler handles scheduling internally).
    Schedules are synced from DB every 5 minutes.
"""

import os
import sys
import signal
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env file
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# SSL fix for macOS - must be set before any imports that use SSL
import ssl
import certifi

cert_path = certifi.where()
os.environ['SSL_CERT_FILE'] = cert_path
os.environ['REQUESTS_CA_BUNDLE'] = cert_path
os.environ['WEBSOCKET_CLIENT_CA_BUNDLE'] = cert_path
os.environ['CURL_CA_BUNDLE'] = cert_path

ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=cert_path)

_original_create_default_context = ssl.create_default_context
def _patched_create_default_context(purpose=ssl.Purpose.SERVER_AUTH, *, cafile=None, capath=None, cadata=None):
    ctx = _original_create_default_context(purpose, cafile=cafile or cert_path, capath=capath, cadata=cadata)
    return ctx
ssl.create_default_context = _patched_create_default_context

import pymongo
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from bson import ObjectId

# ============================================================
# Configuration
# ============================================================

KST = ZoneInfo("Asia/Seoul")

BOT_TOKEN = os.environ.get("SLACK_WEEKLY_BOT_TOKEN", "")
MONGODB_URI = os.environ.get("MONGODB_URI", "")
MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "ati")

DAY_MAP = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3,
    "fri": 4, "sat": 5, "sun": 6,
}

# ============================================================
# Logging
# ============================================================

class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'

def log(level: str, message: str):
    timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    prefix = {
        "INFO": f"{Colors.CYAN}[INFO]{Colors.ENDC}",
        "OK": f"{Colors.GREEN}[OK]{Colors.ENDC}",
        "WARN": f"{Colors.YELLOW}[WARN]{Colors.ENDC}",
        "ERROR": f"{Colors.RED}[ERROR]{Colors.ENDC}",
    }.get(level, f"[{level}]")
    print(f"{timestamp} {prefix} {message}", flush=True)

# ============================================================
# MongoDB & Slack clients
# ============================================================

mongo_client: pymongo.MongoClient = None
db = None
slack: WebClient = None

def init_clients():
    global mongo_client, db, slack
    if not MONGODB_URI:
        log("ERROR", "MONGODB_URI is not set")
        sys.exit(1)
    if not BOT_TOKEN:
        log("ERROR", "SLACK_WEEKLY_BOT_TOKEN is not set")
        sys.exit(1)
    mongo_client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = mongo_client[MONGODB_DATABASE]
    mongo_client.admin.command("ping")
    slack = WebClient(token=BOT_TOKEN)
    log("OK", f"MongoDB connected: {MONGODB_DATABASE}")
    log("OK", f"Slack token loaded: {BOT_TOKEN[:8]}...")

# ============================================================
# Schedule loading from DB
# ============================================================

def load_schedules():
    """Load all active schedules from MongoDB."""
    return list(db["weekly_output_schedules"].find({"is_active": True}))


def reload_schedule(schedule_id):
    """Re-fetch a single schedule from DB (for freshness at execution time)."""
    return db["weekly_output_schedules"].find_one({"_id": ObjectId(schedule_id)})

# ============================================================
# Helper: resolve schedule members to Slack user IDs
# ============================================================

def get_schedule_members(schedule):
    """
    Returns members list for a schedule.
    members_list: [{"member_id": str, "name": str, "slack_user_id": str}, ...]
    """
    member_ids = schedule.get("member_ids", [])
    if not member_ids:
        return []

    # Convert string IDs to ObjectId
    obj_ids = []
    for mid in member_ids:
        try:
            obj_ids.append(ObjectId(mid))
        except Exception:
            pass

    members_cursor = db["members"].find({
        "_id": {"$in": obj_ids},
        "is_active": {"$ne": False},
    })

    result = []
    for m in members_cursor:
        member_id = str(m["_id"])
        name = m.get("name", "Unknown")

        # Resolve Slack user ID (3-step fallback)
        # Step 1: member_identifiers collection (most reliable - has actual Slack user IDs)
        slack_user_id = None
        ident = db["member_identifiers"].find_one({
            "member_name": name,
            "source": "slack",
            "identifier_type": "user_id",
        })
        if ident:
            slack_user_id = ident.get("identifier_value")

        # Step 2: members.slack_id field (only if it looks like a Slack user ID)
        if not slack_user_id:
            candidate = m.get("slack_id")
            if candidate and candidate.startswith("U"):
                slack_user_id = candidate

        # Step 3: embedded identifiers on member document
        if not slack_user_id:
            for ident in m.get("identifiers", []):
                if ident.get("source_type") == "slack":
                    slack_user_id = ident.get("source_user_id")
                    break

        if slack_user_id:
            result.append({
                "member_id": member_id,
                "name": name,
                "slack_user_id": slack_user_id,
            })
        else:
            log("WARN", f"No Slack ID for member '{name}' ({member_id}) - skipping")

    return result

# ============================================================
# Helper: compute week label and deadline
# ============================================================

def get_week_info(schedule, now=None):
    """
    Returns (week_label, deadline) based on the schedule's thread day.
    week_label: "YYYY-MM-DD ~ MM-DD" (thread_day to thread_day+6)
    deadline: final_schedule day/time of the same week
    """
    if now is None:
        now = datetime.now(KST)

    thread_day_num = DAY_MAP.get(schedule.get("thread_schedule", {}).get("day_of_week", "thu"), 3)

    # Find the most recent thread_day (including today)
    days_since = (now.weekday() - thread_day_num) % 7
    start = (now - timedelta(days=days_since)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end = start + timedelta(days=6)

    week_label = f"{start.strftime('%Y-%m-%d')} ~ {end.strftime('%m-%d')}"

    final_sched = schedule.get("final_schedule", {})
    final_day_num = DAY_MAP.get(final_sched.get("day_of_week", "fri"), 4)
    days_to_final = (final_day_num - thread_day_num) % 7
    deadline = (start + timedelta(days=days_to_final)).replace(
        hour=final_sched.get("hour", 17),
        minute=final_sched.get("minute", 0),
        second=0, microsecond=0,
    )

    return week_label, deadline

# ============================================================
# Default message templates
# ============================================================

DEFAULT_THREAD_MSG = (
    ":memo: *[{week_label}] Weekly Output*\n\n"
    "Please share your work updates for this week in this thread.\n"
    "Deadline: *{deadline}*\n\n"
    "{mentions}"
)

DEFAULT_REMINDER_MSG = (
    ":bell: *Weekly Output Reminder*\n\n"
    "Your [{week_label}] Weekly Output hasn't been submitted yet.\n"
    "Please share your work updates in the <{thread_link}|thread> by {deadline}!"
)

DEFAULT_FINAL_MSG = (
    ":rotating_light: *Weekly Output - Final Notice*\n\n"
    "The [{week_label}] Weekly Output deadline has arrived.\n"
    "If you haven't submitted yet, please post in the <{thread_link}|thread> now!"
)


def build_thread_link(channel_id: str, thread_ts: str) -> str:
    """Build a Slack deep-link URL to a thread."""
    ts_no_dot = thread_ts.replace(".", "")
    return f"https://slack.com/archives/{channel_id}/p{ts_no_dot}"


def render_message(template, week_label, mentions, deadline, thread_link=""):
    """Render a message template with variables."""
    deadline_str = deadline.strftime("%A %I:%M %p KST") if isinstance(deadline, datetime) else str(deadline)
    return template.format(
        week_label=week_label,
        mentions=mentions,
        deadline=deadline_str,
        thread_link=thread_link,
    )

# ============================================================
# Job 1: Create weekly output thread
# ============================================================

def create_thread(schedule_id: str):
    schedule = reload_schedule(schedule_id)
    if not schedule or not schedule.get("is_active"):
        log("WARN", f"Schedule {schedule_id} not found or inactive - skipping thread creation")
        return

    schedule_name = schedule.get("name", "Unknown")
    now = datetime.now(KST)
    week_label, deadline = get_week_info(schedule, now)
    log("INFO", f"[{schedule_name}] Creating thread: {week_label}")

    # Duplicate check (per schedule)
    existing = db["weekly_output_threads"].find_one({
        "schedule_id": str(schedule["_id"]),
        "week_label": week_label,
    })
    if existing:
        log("WARN", f"[{schedule_name}] Thread for '{week_label}' already exists (ts={existing.get('thread_ts')})")
        return

    channel_id = schedule.get("channel_id")
    if not channel_id:
        log("ERROR", f"[{schedule_name}] No channel_id configured")
        return

    members = get_schedule_members(schedule)
    if not members:
        log("WARN", f"[{schedule_name}] No members with Slack IDs found - posting thread without mentions")

    mentions = " ".join(f"<@{m['slack_user_id']}>" for m in members)
    template = schedule.get("thread_message") or DEFAULT_THREAD_MSG
    text = render_message(template, week_label, mentions, deadline)

    try:
        resp = slack.chat_postMessage(channel=channel_id, text=text)
        thread_ts = resp["ts"]
        log("OK", f"[{schedule_name}] Thread posted: ts={thread_ts}")
    except SlackApiError as e:
        log("ERROR", f"[{schedule_name}] Failed to post thread: {e.response['error']}")
        return

    try:
        db["weekly_output_threads"].insert_one({
            "schedule_id": str(schedule["_id"]),
            "week_label": week_label,
            "channel_id": channel_id,
            "thread_ts": thread_ts,
            "created_at": datetime.now(KST),
            "deadline": deadline,
            "reminder_sent": False,
            "final_sent": False,
            "members": members,
            "replied_user_ids": [],
        })
        log("OK", f"[{schedule_name}] Thread record saved for '{week_label}'")
    except pymongo.errors.DuplicateKeyError:
        log("WARN", f"[{schedule_name}] Thread for '{week_label}' was created concurrently - skipping")

# ============================================================
# Helper: get replied user IDs from thread
# ============================================================

def get_replied_user_ids(channel_id: str, thread_ts: str) -> set:
    """Fetch all user IDs who replied in the thread (excluding bot)."""
    replied = set()
    try:
        cursor = None
        while True:
            kwargs = {
                "channel": channel_id,
                "ts": thread_ts,
                "limit": 200,
            }
            if cursor:
                kwargs["cursor"] = cursor
            resp = slack.conversations_replies(**kwargs)
            for msg in resp.get("messages", []):
                if msg.get("ts") == thread_ts:
                    continue
                user = msg.get("user")
                if user:
                    replied.add(user)
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
    except SlackApiError as e:
        log("ERROR", f"Failed to fetch thread replies: {e.response['error']}")
    return replied

# ============================================================
# Helper: send DM to a user
# ============================================================

def send_dm(user_id: str, text: str):
    try:
        conv = slack.conversations_open(users=[user_id])
        dm_channel = conv["channel"]["id"]
        slack.chat_postMessage(channel=dm_channel, text=text)
        return True
    except SlackApiError as e:
        log("ERROR", f"Failed to DM <@{user_id}>: {e.response['error']}")
        return False

# ============================================================
# Job 2: Reminder DM
# ============================================================

def send_reminders(schedule_id: str):
    schedule = reload_schedule(schedule_id)
    if not schedule or not schedule.get("is_active"):
        log("WARN", f"Schedule {schedule_id} not found or inactive - skipping reminders")
        return

    schedule_name = schedule.get("name", "Unknown")
    now = datetime.now(KST)
    week_label, deadline = get_week_info(schedule, now)
    log("INFO", f"[{schedule_name}] Checking reminders for '{week_label}'")

    doc = db["weekly_output_threads"].find_one({
        "schedule_id": str(schedule["_id"]),
        "week_label": week_label,
    })
    if not doc:
        log("WARN", f"[{schedule_name}] No thread found for '{week_label}' - skipping reminders")
        return
    if doc.get("reminder_sent"):
        log("WARN", f"[{schedule_name}] Reminders already sent for '{week_label}'")
        return

    channel_id = doc["channel_id"]
    thread_ts = doc["thread_ts"]
    members = doc.get("members", [])

    replied = get_replied_user_ids(channel_id, thread_ts)
    log("INFO", f"[{schedule_name}] Replied users: {replied}")

    db["weekly_output_threads"].update_one(
        {"_id": doc["_id"]},
        {"$set": {"replied_user_ids": list(replied)}},
    )

    non_responders = [m for m in members if m["slack_user_id"] not in replied]
    if not non_responders:
        log("OK", f"[{schedule_name}] All members have responded - no reminders needed")
        db["weekly_output_threads"].update_one(
            {"_id": doc["_id"]}, {"$set": {"reminder_sent": True}}
        )
        return

    log("INFO", f"[{schedule_name}] Sending reminders to {len(non_responders)} member(s)")
    template = schedule.get("reminder_message") or DEFAULT_REMINDER_MSG
    thread_link = build_thread_link(channel_id, thread_ts)
    for m in non_responders:
        text = render_message(template, week_label, "", deadline, thread_link=thread_link)
        if send_dm(m["slack_user_id"], text):
            log("OK", f"[{schedule_name}] Reminder sent to {m['name']} (<@{m['slack_user_id']}>)")

    db["weekly_output_threads"].update_one(
        {"_id": doc["_id"]}, {"$set": {"reminder_sent": True}}
    )

# ============================================================
# Job 3: Final DM
# ============================================================

def send_final_reminders(schedule_id: str):
    schedule = reload_schedule(schedule_id)
    if not schedule or not schedule.get("is_active"):
        log("WARN", f"Schedule {schedule_id} not found or inactive - skipping final reminders")
        return

    schedule_name = schedule.get("name", "Unknown")
    now = datetime.now(KST)
    week_label, deadline = get_week_info(schedule, now)
    log("INFO", f"[{schedule_name}] Checking final reminders for '{week_label}'")

    doc = db["weekly_output_threads"].find_one({
        "schedule_id": str(schedule["_id"]),
        "week_label": week_label,
    })
    if not doc:
        log("WARN", f"[{schedule_name}] No thread found for '{week_label}' - skipping final reminders")
        return
    if doc.get("final_sent"):
        log("WARN", f"[{schedule_name}] Final reminders already sent for '{week_label}'")
        return

    channel_id = doc["channel_id"]
    thread_ts = doc["thread_ts"]
    members = doc.get("members", [])

    replied = get_replied_user_ids(channel_id, thread_ts)
    log("INFO", f"[{schedule_name}] Replied users (final check): {replied}")

    db["weekly_output_threads"].update_one(
        {"_id": doc["_id"]},
        {"$set": {"replied_user_ids": list(replied)}},
    )

    non_responders = [m for m in members if m["slack_user_id"] not in replied]
    if not non_responders:
        log("OK", f"[{schedule_name}] All members have responded - no final reminders needed")
        db["weekly_output_threads"].update_one(
            {"_id": doc["_id"]}, {"$set": {"final_sent": True}}
        )
        return

    log("INFO", f"[{schedule_name}] Sending final reminders to {len(non_responders)} member(s)")
    template = schedule.get("final_message") or DEFAULT_FINAL_MSG
    thread_link = build_thread_link(channel_id, thread_ts)
    for m in non_responders:
        text = render_message(template, week_label, "", deadline, thread_link=thread_link)
        if send_dm(m["slack_user_id"], text):
            log("OK", f"[{schedule_name}] Final reminder sent to {m['name']} (<@{m['slack_user_id']}>)")

    db["weekly_output_threads"].update_one(
        {"_id": doc["_id"]}, {"$set": {"final_sent": True}}
    )

# ============================================================
# Recovery per schedule
# ============================================================

def recover_for_schedule(schedule):
    """Check if any jobs were missed for a given schedule and run them."""
    schedule_id = str(schedule["_id"])
    schedule_name = schedule.get("name", "Unknown")
    now = datetime.now(KST)
    week_label, deadline = get_week_info(schedule, now)

    # Determine the thread creation time
    ts = schedule.get("thread_schedule", {})
    thread_day_num = DAY_MAP.get(ts.get("day_of_week", "thu"), 3)
    days_since = (now.weekday() - thread_day_num) % 7
    thread_time = (now - timedelta(days=days_since)).replace(
        hour=ts.get("hour", 17), minute=ts.get("minute", 0), second=0, microsecond=0,
    )

    if now < thread_time:
        log("INFO", f"[{schedule_name}] Thread not yet due")
        return

    doc = db["weekly_output_threads"].find_one({
        "schedule_id": schedule_id,
        "week_label": week_label,
    })

    # Thread time passed but no thread?
    if not doc:
        log("WARN", f"[{schedule_name}] Missed thread creation - creating now")
        create_thread(schedule_id)
        doc = db["weekly_output_threads"].find_one({
            "schedule_id": schedule_id,
            "week_label": week_label,
        })

    if not doc:
        return

    # Reminder check
    rs = schedule.get("reminder_schedule", {})
    reminder_day_num = DAY_MAP.get(rs.get("day_of_week", "fri"), 4)
    days_to_reminder = (reminder_day_num - thread_day_num) % 7
    reminder_time = (thread_time.replace(hour=0, minute=0) + timedelta(days=days_to_reminder)).replace(
        hour=rs.get("hour", 16), minute=rs.get("minute", 0),
    )

    if now >= reminder_time and not doc.get("reminder_sent"):
        log("WARN", f"[{schedule_name}] Missed reminder - sending now")
        send_reminders(schedule_id)
        doc = db["weekly_output_threads"].find_one({
            "schedule_id": schedule_id,
            "week_label": week_label,
        })

    # Final check
    fs = schedule.get("final_schedule", {})
    final_day_num = DAY_MAP.get(fs.get("day_of_week", "fri"), 4)
    days_to_final = (final_day_num - thread_day_num) % 7
    final_time = (thread_time.replace(hour=0, minute=0) + timedelta(days=days_to_final)).replace(
        hour=fs.get("hour", 17), minute=fs.get("minute", 0),
    )

    if now >= final_time and not doc.get("final_sent"):
        log("WARN", f"[{schedule_name}] Missed final reminder - sending now")
        send_final_reminders(schedule_id)

# ============================================================
# Job synchronization
# ============================================================

# Track which schedule IDs currently have jobs registered
_registered_schedule_ids = set()

def sync_jobs(scheduler):
    """
    Sync APScheduler jobs with active schedules from DB.
    Adds new, updates changed, removes deleted/inactive schedules.
    """
    global _registered_schedule_ids
    schedules = load_schedules()
    active_ids = set()

    for schedule in schedules:
        sid = str(schedule["_id"])
        active_ids.add(sid)
        sname = schedule.get("name", "Unknown")

        ts = schedule.get("thread_schedule", {})
        rs = schedule.get("reminder_schedule", {})
        fs = schedule.get("final_schedule", {})

        # Job IDs per schedule
        thread_job_id = f"thread_{sid}"
        reminder_job_id = f"reminder_{sid}"
        final_job_id = f"final_{sid}"

        # Remove existing jobs to re-add with potentially updated times
        for job_id in [thread_job_id, reminder_job_id, final_job_id]:
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)

        # Add thread creation job
        scheduler.add_job(
            create_thread,
            CronTrigger(
                day_of_week=ts.get("day_of_week", "thu"),
                hour=ts.get("hour", 17),
                minute=ts.get("minute", 0),
                timezone=KST,
            ),
            args=[sid],
            id=thread_job_id,
            name=f"[{sname}] Create Thread",
        )

        # Add reminder job
        scheduler.add_job(
            send_reminders,
            CronTrigger(
                day_of_week=rs.get("day_of_week", "fri"),
                hour=rs.get("hour", 16),
                minute=rs.get("minute", 0),
                timezone=KST,
            ),
            args=[sid],
            id=reminder_job_id,
            name=f"[{sname}] Reminder DMs",
        )

        # Add final reminder job
        scheduler.add_job(
            send_final_reminders,
            CronTrigger(
                day_of_week=fs.get("day_of_week", "fri"),
                hour=fs.get("hour", 17),
                minute=fs.get("minute", 0),
                timezone=KST,
            ),
            args=[sid],
            id=final_job_id,
            name=f"[{sname}] Final DMs",
        )

    # Remove jobs for schedules no longer active
    removed_ids = _registered_schedule_ids - active_ids
    for sid in removed_ids:
        for prefix in ["thread_", "reminder_", "final_"]:
            job_id = f"{prefix}{sid}"
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
                log("INFO", f"Removed job {job_id} (schedule deleted/inactive)")

    _registered_schedule_ids = active_ids
    log("INFO", f"Synced {len(active_ids)} active schedule(s), {len(removed_ids)} removed")

# ============================================================
# Ensure indexes
# ============================================================

def ensure_indexes():
    # Drop the old single-field unique index if it exists
    existing_indexes = db["weekly_output_threads"].index_information()
    if "week_label_1" in existing_indexes:
        db["weekly_output_threads"].drop_index("week_label_1")
        log("OK", "Dropped old unique index on week_label")

    # Create composite unique index
    db["weekly_output_threads"].create_index(
        [("schedule_id", 1), ("week_label", 1)],
        unique=True,
    )
    log("OK", "Ensured unique index on (schedule_id, week_label)")

# ============================================================
# Main
# ============================================================

def main():
    log("INFO", "=" * 50)
    log("INFO", "Weekly Output Bot (Multi-Schedule) starting...")
    log("INFO", "=" * 50)

    init_clients()
    ensure_indexes()

    # Initial schedule load and recovery
    schedules = load_schedules()
    log("INFO", f"Loaded {len(schedules)} active schedule(s)")
    for s in schedules:
        log("INFO", f"  - {s.get('name', 'Unknown')} (#{s.get('channel_name', '?')})")
        recover_for_schedule(s)

    scheduler = BlockingScheduler(timezone=KST)

    # Initial job sync
    sync_jobs(scheduler)

    # Re-sync from DB every 5 minutes (pick up new/changed/deleted schedules)
    scheduler.add_job(
        sync_jobs,
        "interval",
        minutes=5,
        args=[scheduler],
        id="sync_jobs",
        name="Sync schedules from DB",
    )

    log("OK", "Bot is running. Schedules sync every 5 minutes.")
    log("INFO", "Press Ctrl+C to stop.")

    def shutdown(signum, frame):
        log("INFO", "Shutting down...")
        scheduler.shutdown(wait=False)
        if mongo_client:
            mongo_client.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log("INFO", "Bot stopped.")


if __name__ == "__main__":
    main()
