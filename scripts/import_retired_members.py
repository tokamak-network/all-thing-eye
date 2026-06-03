#!/usr/bin/env python3
"""
Import curated RETIRED/historical members into the live `members` collection
(is_active=false) + their identifiers into `member_identifiers`, so they become
first-class, selectable members in custom-export and all activity queries.

SAFETY:
  - NEVER overwrites existing members: uses $setOnInsert only (insert-if-absent).
  - Every inserted doc is tagged `import_origin="archive_unified"` for clean rollback
    (see scripts/rollback_unified_import.py).
  - Idempotent: re-running inserts nothing new.

Population = retired employees only (status=퇴직), enriched from the identity map.

Usage:
  python scripts/import_retired_members.py --dry-run
  python scripts/import_retired_members.py                 # writes (run on server)
  python scripts/import_retired_members.py --mongo-uri ... --db ati
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
    members = {}  # name -> member doc
    for path in CURATED:
        for r in read_csv(path):
            name = (r.get("member_name") or "").strip()
            if not name or (r.get("status") and r["status"] != "퇴직"):
                # curated foreign file has no status; treat as retired by inclusion
                if r.get("status") and r["status"] != "퇴직":
                    continue
            if not name or name in members:
                continue
            gh = (r.get("github_username") or "").strip()
            enrich = by_gh.get(gh.lower()) or by_name.get(norm_name(name)) or {}
            emails = enrich.get("emails", [])
            members[name] = {
                "name": name,
                "email": emails[0] if emails else "",
                "role": "; ".join(enrich.get("vault_roles", []))[:120] or None,
                "team": "; ".join(enrich.get("vault_teams", []))[:120] or None,
                "github_username": gh or enrich.get("github_username", "") or None,
                "is_active": False,
                "resignation_reason": "archived (2019-2023 era)",
                "active_era": enrich.get("active_era") or None,
                "real_name_en": enrich.get("real_name_en") or None,
                "real_name_kr": enrich.get("real_name_kr") or None,
                "import_origin": ORIGIN,
            }
    return list(members.values())


def build_identifiers(members):
    ids = []
    for m in members:
        gh = m.get("github_username")
        if gh:
            ids.append({
                "source": "github",
                "identifier_type": "username",
                "identifier_value": gh,
                "member_name": m["name"],
                "import_origin": ORIGIN,
            })
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mongo-uri")
    ap.add_argument("--db", default=os.getenv("MONGODB_DATABASE", "ati"))
    args = ap.parse_args()

    members = build_members()
    identifiers = build_identifiers(members)
    print(f"📦 retired members to import : {len(members)}")
    print(f"   github identifiers        : {len(identifiers)}")
    print("   sample:", ", ".join(m["name"] for m in members[:8]))

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

    # members — insert-if-absent only (never overwrite existing/active members)
    mops = [UpdateOne({"name": m["name"]},
                      {"$setOnInsert": {**m, "created_at": now(), "updated_at": now()}},
                      upsert=True) for m in members]
    mres = db["members"].bulk_write(mops, ordered=False)
    print(f"  members      : +{mres.upserted_count} inserted, {len(members) - mres.upserted_count} already existed (untouched)")

    iops = [UpdateOne({"source": i["source"], "identifier_value": i["identifier_value"]},
                      {"$setOnInsert": {**i, "created_at": now()}},
                      upsert=True) for i in identifiers]
    if iops:
        ires = db["member_identifiers"].bulk_write(iops, ordered=False)
        print(f"  identifiers  : +{ires.upserted_count} inserted, {len(identifiers) - ires.upserted_count} already existed")
    print("\n✅ Done. Rollback: python scripts/rollback_unified_import.py")


if __name__ == "__main__":
    main()
