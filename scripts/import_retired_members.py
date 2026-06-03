#!/usr/bin/env python3
"""
Import curated RETIRED/historical members into a NEW, isolated `archive_members`
collection in the live `ati` DB. The existing `members` / `member_identifiers`
collections and ALL source collections (slack_messages, github_commits, ...) are
NEVER touched. custom-export reads `archive_members` for the member picker and
`member_artifacts` for their materials.

Population = retired employees only (status=퇴직), enriched from the identity map.

SAFETY:
  - Only writes the additive `archive_members` collection -> rollback = drop it.
  - Idempotent upsert by member_key.

Usage:
  python scripts/import_retired_members.py --dry-run
  python scripts/import_retired_members.py              # writes (run on server)
"""
import argparse
import csv
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ORIGIN = "archive_unified"

CURATED = [
    DATA / "retired_members_all_artifacts.csv",
    DATA / "foreign_members_all_artifacts.csv",
    DATA / "member_vault_artifacts.csv",
]
IDMAP_FILE = DATA / "tokamak_member_identity_map.csv"


def now():
    return datetime.now(timezone.utc)


def slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s or "unknown"


def norm_name(s):
    s = re.sub(r"\s*\(alias[^)]*\)", "", s or "")
    return re.sub(r"\s+", " ", s).strip().lower()


def read_csv(p):
    if not p.exists():
        print(f"  ⚠️  missing: {p}")
        return []
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_idmap():
    by_gh, by_name = {}, {}
    for r in read_csv(IDMAP_FILE):
        rec = {
            "real_name_en": r.get("real_name_en") or "",
            "real_name_kr": r.get("real_name_kr") or "",
            "emails": [e.strip() for e in re.split(r"[;,]", r.get("emails", "")) if e.strip()],
            "active_era": r.get("active_era") or "",
            "vault_teams": [t.strip() for t in re.split(r"[;,]", r.get("vault_teams", "")) if t.strip()],
            "vault_roles": [t.strip() for t in re.split(r"[;,]", r.get("vault_roles", "")) if t.strip()],
            "github_username": (r.get("github_username") or "").strip(),
        }
        gh = rec["github_username"].lower()
        if gh:
            by_gh[gh] = rec
        for nm in (rec["real_name_en"], rec["real_name_kr"]):
            if nm:
                by_name.setdefault(norm_name(nm), rec)
    return by_gh, by_name


def build_members():
    by_gh, by_name = load_idmap()
    members = {}  # member_key -> doc
    for path in CURATED:
        for r in read_csv(path):
            name = (r.get("member_name") or "").strip()
            if not name:
                continue
            if r.get("status") and r["status"] != "퇴직":
                continue
            gh = (r.get("github_username") or "").strip()
            key = gh.lower() if gh else slug(name)
            if key in members:
                continue
            enrich = by_gh.get(gh.lower()) or by_name.get(norm_name(name)) or {}
            members[key] = {
                "member_key": key,
                "name": name,
                "real_name_en": enrich.get("real_name_en") or None,
                "real_name_kr": enrich.get("real_name_kr") or None,
                "email": (enrich.get("emails") or [""])[0],
                "emails": enrich.get("emails", []),
                "github_username": gh or enrich.get("github_username", "") or None,
                "role": "; ".join(enrich.get("vault_roles", []))[:120] or None,
                "team": "; ".join(enrich.get("vault_teams", []))[:120] or None,
                "vault_teams": enrich.get("vault_teams", []),
                "vault_roles": enrich.get("vault_roles", []),
                "active_era": enrich.get("active_era") or None,
                "is_active": False,
                "status": "퇴직",
                "import_origin": ORIGIN,
            }
    return list(members.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mongo-uri")
    ap.add_argument("--db", default=os.getenv("MONGODB_DATABASE", "ati"))
    args = ap.parse_args()

    members = build_members()
    print(f"📦 retired members -> archive_members: {len(members)}")
    print("   sample:", ", ".join(m["name"] for m in members[:8]))

    if args.dry_run:
        print("\n✅ DRY-RUN: no DB writes. (writes only the new `archive_members` collection)")
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

    col = db["archive_members"]
    col.create_index("member_key", unique=True)
    col.create_index("status")
    col.create_index("active_era")

    ops = [UpdateOne({"member_key": m["member_key"]},
                     {"$set": m, "$setOnInsert": {"created_at": now()}},
                     upsert=True) for m in members]
    res = col.bulk_write(ops, ordered=False)
    print(f"  archive_members: +{res.upserted_count} new, ~{res.modified_count} updated  (sent {len(members)})")
    print("\n✅ Done. Rollback: python scripts/rollback_unified_import.py")


if __name__ == "__main__":
    main()
