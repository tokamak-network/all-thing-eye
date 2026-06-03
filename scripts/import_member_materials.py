#!/usr/bin/env python3
"""
Import member MATERIALS (retired members' vault docs, meetings, historical
artifacts) into a single `member_artifacts` collection in the live `ati` DB,
so custom-export can read them as one more source alongside live activities.

Reuses build() from import_archive_data.py (same normalization). Writes the
artifacts only (live activities stay in their own collections).

SAFETY:
  - `member_artifacts` is an ADDITIVE new collection -> rollback = drop it.
  - Each doc tagged import_origin="archive_unified".
  - Idempotent upsert by artifact_id.

Usage:
  python scripts/import_member_materials.py --dry-run
  python scripts/import_member_materials.py              # writes (run on server)
"""
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from import_archive_data import build  # reuse the exact same document builder

ORIGIN = "archive_unified"


def now():
    return datetime.now(timezone.utc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mongo-uri")
    ap.add_argument("--db", default=os.getenv("MONGODB_DATABASE", "ati"))
    args = ap.parse_args()

    _members, artifacts, _recordings = build()
    for a in artifacts:
        a["import_origin"] = ORIGIN
    print(f"📦 member_artifacts to import: {len(artifacts)}")
    from collections import Counter
    print("   by source:", dict(Counter(a["source"] for a in artifacts)))

    if args.dry_run:
        print("\n✅ DRY-RUN: no DB writes.")
        return

    from pymongo import MongoClient, UpdateOne
    uri = args.mongo_uri or os.getenv("MONGODB_URI")
    if not uri:
        try:
            from dotenv import load_dotenv
            for p in (ROOT / ".env", Path("/app/.env"), Path(".env")):
                if p.exists():
                    load_dotenv(p); break
        except Exception:
            pass
        uri = os.getenv("MONGODB_URI")
    if not uri:
        print("❌ No MONGODB_URI"); sys.exit(1)

    client = MongoClient(uri, serverSelectionTimeoutMS=8000)
    client.admin.command("ping")
    db = client[args.db]
    print(f"\n🔌 Connected: {args.db}")

    col = db["member_artifacts"]
    col.create_index("artifact_id", unique=True)
    col.create_index("member_name")
    col.create_index("member_key")
    col.create_index([("source", 1), ("type", 1)])
    col.create_index("date")

    ops = []
    for a in artifacts:
        created = a.pop("created_at", None)
        ops.append(UpdateOne({"artifact_id": a["artifact_id"]},
                             {"$set": a, "$setOnInsert": {"created_at": now()}},
                             upsert=True))
    BATCH = 2000
    ins = mod = 0
    for i in range(0, len(ops), BATCH):
        res = col.bulk_write(ops[i:i + BATCH], ordered=False)
        ins += res.upserted_count; mod += res.modified_count
    print(f"  member_artifacts: +{ins} new, ~{mod} updated  (sent {len(ops)})")
    print("\n✅ Done. Rollback: python scripts/rollback_unified_import.py")


if __name__ == "__main__":
    main()
