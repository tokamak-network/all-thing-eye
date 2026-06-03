#!/usr/bin/env python3
"""
Roll back the unified-export data import.

Deletes ONLY the documents this project inserted (tagged import_origin="archive_unified")
and drops the additive material collections. Original/active data is never touched.

Usage:
  python scripts/rollback_unified_import.py --dry-run     # show what would be removed
  python scripts/rollback_unified_import.py               # actually remove
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORIGIN = "archive_unified"

# Collections we INSERT tagged docs into (deleted by marker, originals preserved)
TAGGED_COLLECTIONS = ["members", "member_identifiers"]
# Additive collections we CREATE (dropped entirely on rollback)
NEW_COLLECTIONS = ["member_artifacts"]


def get_db(args):
    from pymongo import MongoClient
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
    return client[args.db]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mongo-uri")
    ap.add_argument("--db", default=os.getenv("MONGODB_DATABASE", "ati"))
    args = ap.parse_args()

    db = get_db(args)
    print(f"🔌 {args.db}  (rollback target: import_origin='{ORIGIN}')\n")

    for coll in TAGGED_COLLECTIONS:
        n = db[coll].count_documents({"import_origin": ORIGIN})
        if args.dry_run:
            print(f"  would delete from {coll:20}: {n} tagged docs")
        else:
            res = db[coll].delete_many({"import_origin": ORIGIN})
            print(f"  deleted from {coll:20}: {res.deleted_count}")

    existing = set(db.list_collection_names())
    for coll in NEW_COLLECTIONS:
        if coll in existing:
            n = db[coll].count_documents({})
            if args.dry_run:
                print(f"  would drop collection {coll:18}: {n} docs")
            else:
                db[coll].drop()
                print(f"  dropped collection {coll:18}: ({n} docs)")
        else:
            print(f"  (collection {coll} not present)")

    print("\n" + ("✅ DRY-RUN only." if args.dry_run else "✅ Rollback complete."))


if __name__ == "__main__":
    main()
