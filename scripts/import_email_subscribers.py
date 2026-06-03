#!/usr/bin/env python3
"""
Import email subscribers into the `email_subscribers` MongoDB collection.

Reads a plaintext file of emails (one per line), validates / lowercases /
dedupes them, and upserts each as a subscriber with source="import". Existing
subscribers are left untouched (status is not overwritten).

Ported from biweekly-reporter (scripts/convert-emails.js), which produced a
subscribers.json; here we write straight into MongoDB instead.

Usage:
    python scripts/import_email_subscribers.py [--file PATH] [--dry-run]

Defaults to ../biweekly-reporter/emails.txt (sibling project).
"""

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.mongo_manager import get_mongo_manager

COLLECTION = "email_subscribers"
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

DEFAULT_FILE = project_root.parent / "biweekly-reporter" / "emails.txt"


def read_emails(file_path) -> list[str]:
    """Read, validate, lowercase, and dedupe emails from a file or stdin.

    Pass "-" as the path to read from stdin (avoids writing PII to disk).
    """
    if str(file_path) == "-":
        raw = sys.stdin.read()
    else:
        file_path = Path(file_path)
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            sys.exit(1)
        raw = file_path.read_text(encoding="utf-8")

    seen: set[str] = set()
    unique: list[str] = []
    total_lines = 0
    for line in raw.splitlines():
        total_lines += 1
        email = line.strip().lower()
        if EMAIL_RE.match(email) and email not in seen:
            seen.add(email)
            unique.append(email)

    print(f"📄 Read {total_lines} lines → {len(unique)} unique valid emails.")
    return unique


def main() -> None:
    parser = argparse.ArgumentParser(description="Import email subscribers into MongoDB.")
    parser.add_argument(
        "--file",
        type=str,
        default=str(DEFAULT_FILE),
        help=f'Path to emails.txt, or "-" for stdin (default: {DEFAULT_FILE})',
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report counts without writing to MongoDB.",
    )
    args = parser.parse_args()

    emails = read_emails(args.file)
    if not emails:
        print("Nothing to import.")
        return

    if args.dry_run:
        print(f"🟡 Dry run: would upsert {len(emails)} emails. Sample:")
        for e in emails[:5]:
            print(f"   - {e}")
        return

    mongodb_config = {
        "uri": os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        "database": os.getenv("MONGODB_DATABASE", "all_thing_eye"),
    }
    mongo_manager = get_mongo_manager(mongodb_config)
    db = mongo_manager.db  # sync database (auto-connects)
    col = db[COLLECTION]
    col.create_index("email", unique=True)

    inserted = 0
    existed = 0
    now = datetime.now(timezone.utc)
    for email in emails:
        result = col.update_one(
            {"email": email},
            {
                "$setOnInsert": {
                    "email": email,
                    "name": None,
                    "source": "import",
                    "status": "active",
                    "created_at": now,
                }
            },
            upsert=True,
        )
        if result.upserted_id is not None:
            inserted += 1
        else:
            existed += 1

    active_total = col.count_documents({"status": "active"})
    print(f"✅ Import complete: {inserted} new, {existed} already existed.")
    print(f"   Active subscribers now: {active_total}")
    mongo_manager.close()


if __name__ == "__main__":
    main()
