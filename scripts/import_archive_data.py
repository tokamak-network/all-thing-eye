#!/usr/bin/env python3
"""
Import retired-members archive data (profiles + artifacts + recordings) from the
curated CSVs in data/ into the separate `ati_archive` MongoDB database.

Population = RETIRED employees only (status=퇴직), enriched from the identity map.
Artifacts are scoped to those retired members. Recordings are the full file catalog.

Collections (in ati_archive):
  archive_members    key=member_key (unique)
  archive_artifacts  key=artifact_id (unique)
  archive_recordings key=file_id (unique)

Usage:
  python scripts/import_archive_data.py --dry-run            # validate only, no DB
  python scripts/import_archive_data.py                      # upsert all
  python scripts/import_archive_data.py --only members       # one collection
  python scripts/import_archive_data.py --data-dir data
"""
import argparse
import csv
import hashlib
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MRI = DATA / "meeting-recordings-inventory"

# Curated retired-member artifact sources (already keyed to real members)
ARTIFACT_FILES = {
    "retired": DATA / "retired_members_all_artifacts.csv",
    "foreign": DATA / "foreign_members_all_artifacts.csv",
    "vault": DATA / "member_vault_artifacts.csv",
}
MEETINGS_FILE = MRI / "meeting_participants_by_member.csv"
RECORDINGS_FILE = MRI / "drive_recordings_full_inventory.csv"
IDMAP_FILE = DATA / "tokamak_member_identity_map.csv"


def now():
    return datetime.now(timezone.utc)


def slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s or "unknown"


def norm_name(s: str) -> str:
    s = re.sub(r"\s*\(alias[^)]*\)", "", s or "")
    return re.sub(r"\s+", " ", s).strip().lower()


def member_key_for(github_username: str, member_name: str) -> str:
    gh = (github_username or "").strip().lower()
    return gh if gh else slug(member_name)


def read_csv(path: Path):
    if not path.exists():
        print(f"  ⚠️  missing: {path}")
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def sha(*parts) -> str:
    return hashlib.sha1("|".join(str(p or "") for p in parts).encode()).hexdigest()[:20]


# ---------------------------------------------------------------------------
# Build documents
# ---------------------------------------------------------------------------
def load_idmap():
    by_gh, by_name = {}, {}
    for r in read_csv(IDMAP_FILE):
        rec = {
            "real_name_en": r.get("real_name_en") or "",
            "real_name_kr": r.get("real_name_kr") or "",
            "emails": [e.strip() for e in re.split(r"[;,]", r.get("emails", "")) if e.strip()],
            "active_era": r.get("active_era") or "",
            "vault_teams": [t.strip() for t in re.split(r"[;,]", r.get("vault_teams", "")) if t.strip()],
            "vault_periods": [t.strip() for t in re.split(r"[;,]", r.get("vault_periods", "")) if t.strip()],
            "vault_roles": [t.strip() for t in re.split(r"[;,]", r.get("vault_roles", "")) if t.strip()],
            "tier_final": r.get("tier_final") or "",
            "total_commits": int(r["total_commits"]) if (r.get("total_commits") or "").isdigit() else 0,
            "total_repos": int(r["total_repos"]) if (r.get("total_repos") or "").isdigit() else 0,
        }
        gh = (r.get("github_username") or "").strip().lower()
        if gh:
            by_gh[gh] = rec
        for nm in (rec["real_name_en"], rec["real_name_kr"]):
            if nm:
                by_name.setdefault(norm_name(nm), rec)
    return by_gh, by_name


def normalize_artifact_row(source_tag, r):
    """Map a source-specific row -> common artifact fields."""
    if source_tag == "vault":
        return dict(
            member_name=r.get("member_name", ""), github_username=r.get("github_username", ""),
            status=r.get("status", "퇴직"), source=r.get("source", "vault"),
            project=r.get("project", "Other"), date=(r.get("last_modified") or "")[:10],
            type="document", title=r.get("file_basename", ""), url=r.get("file_path", ""),
            script_url="", role=r.get("role", "author"),
        )
    if source_tag == "meeting":
        return dict(
            member_name=r.get("member_name", ""), github_username=r.get("github_username", ""),
            status="퇴직", source=r.get("source", "google_meet"),
            project=r.get("project", "Other"), date=(r.get("date") or "")[:10],
            type=r.get("type", "meeting"), title=r.get("title", ""),
            url=r.get("meeting_url", ""), script_url=r.get("script_url", ""),
            role=r.get("role", "participant"),
        )
    # retired / foreign artifact files
    return dict(
        member_name=r.get("member_name", ""), github_username=r.get("github_username", ""),
        status=r.get("status", "퇴직"), source=r.get("source", source_tag),
        project=r.get("project", "Other"), date=(r.get("date") or "")[:10],
        type=r.get("type", "document"), title=r.get("title", ""),
        url=r.get("reference_url") or r.get("reference") or "", script_url="",
        role=r.get("role", "author"),
    )


def build():
    by_gh, by_name = load_idmap()

    # 1) retired roster from curated artifact files (status=퇴직 or foreign file)
    roster = {}  # member_key -> member doc
    roster_gh, roster_names = set(), set()

    def ensure_member(member_name, github_username, status):
        key = member_key_for(github_username, member_name)
        if key not in roster:
            enrich = by_gh.get((github_username or "").strip().lower()) or by_name.get(norm_name(member_name)) or {}
            roster[key] = {
                "member_key": key,
                "member_name": member_name,
                "github_username": (github_username or "").strip(),
                "status": status or "퇴직",
                **{k: enrich.get(k, "" if k.startswith("real") or k in ("active_era", "tier_final") else [])
                   for k in ("real_name_en", "real_name_kr", "emails", "active_era",
                             "vault_teams", "vault_periods", "vault_roles", "tier_final")},
                "total_commits": enrich.get("total_commits", 0),
                "total_repos": enrich.get("total_repos", 0),
                "artifact_count": 0, "meeting_count": 0,
                "first_seen": None, "last_seen": None,
                "updated_at": now(),
            }
            if github_username:
                roster_gh.add(github_username.strip().lower())
            roster_names.add(norm_name(member_name))
        return key

    artifacts = {}  # artifact_id -> doc

    def add_artifact(member_key, a):
        aid = sha(member_key, a["source"], a["type"], a["title"], a["date"], a["url"])
        if aid in artifacts:
            return
        artifacts[aid] = {
            "artifact_id": aid, "member_key": member_key, **a, "created_at": now(),
        }
        m = roster[member_key]
        m["artifact_count"] += 1
        if a["source"] == "google_meet":
            m["meeting_count"] += 1
        d = a["date"]
        if d:
            m["first_seen"] = min(m["first_seen"] or d, d)
            m["last_seen"] = max(m["last_seen"] or d, d)

    # curated artifact files define the roster + their artifacts
    for tag, path in ARTIFACT_FILES.items():
        for r in read_csv(path):
            mn = r.get("member_name", "")
            if not mn:
                continue
            gh = r.get("github_username", "")
            a = normalize_artifact_row(tag, r)
            key = ensure_member(mn, gh, a.get("status"))
            add_artifact(key, a)

    # meetings: only for members already in the retired roster (match by gh or name)
    for r in read_csv(MEETINGS_FILE):
        mn = r.get("member_name", "")
        gh = (r.get("github_username") or "").strip().lower()
        key = None
        if gh and gh in roster_gh:
            key = gh
        elif norm_name(mn) in roster_names:
            # find the member_key whose name matches
            key = next((k for k, m in roster.items() if norm_name(m["member_name"]) == norm_name(mn)), None)
        if not key:
            continue
        add_artifact(key, normalize_artifact_row("meeting", r))

    # 3) recordings — full catalog
    recordings = {}
    for r in read_csv(RECORDINGS_FILE):
        fid = r.get("file_id")
        if not fid:
            continue
        recordings[fid] = {
            "file_id": fid, "date": r.get("date", ""), "category": r.get("category", ""),
            "title": r.get("title", ""), "owner": r.get("owner", ""),
            "mime": r.get("mime", ""), "size_mb": float(r["size_mb"]) if r.get("size_mb") else None,
            "view_url": r.get("view_url", ""), "created_at": now(),
        }

    return list(roster.values()), list(artifacts.values()), list(recordings.values())


# ---------------------------------------------------------------------------
# Persist
# ---------------------------------------------------------------------------
def upsert(collection, docs, key_field):
    from pymongo import UpdateOne
    if not docs:
        return 0, 0
    ops = []
    for d in docs:
        created = d.pop("created_at", None) or d.pop("updated_at", None)
        ops.append(UpdateOne(
            {key_field: d[key_field]},
            {"$set": d, "$setOnInsert": {"created_at": now()}},
            upsert=True,
        ))
    res = collection.bulk_write(ops, ordered=False)
    return res.upserted_count, res.modified_count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="validate only, no DB writes")
    ap.add_argument("--only", choices=["members", "artifacts", "recordings"], help="one collection only")
    ap.add_argument("--mongo-uri", help="override MongoDB URI (default: env MONGODB_URI / .env)")
    ap.add_argument("--archive-db", help="archive database name (default: env MONGODB_ARCHIVE_DATABASE or ati_archive)")
    args = ap.parse_args()

    print("📦 Building archive documents from CSVs...")
    members, artifacts, recordings = build()
    print(f"  archive_members   : {len(members)}  (퇴사 직원)")
    print(f"  archive_artifacts : {len(artifacts)}")
    print(f"  archive_recordings: {len(recordings)}")
    # quick sanity sample
    if members:
        s = sorted(members, key=lambda m: -m["artifact_count"])[0]
        print(f"  top member: {s['member_name']} (key={s['member_key']}) "
              f"artifacts={s['artifact_count']} meetings={s['meeting_count']} "
              f"era={s['active_era']}")

    if args.dry_run:
        print("\n✅ DRY-RUN: no DB writes. Counts above validated from CSVs.")
        return

    # real run — connect to ati_archive via plain pymongo (self-contained, no app deps)
    from pymongo import MongoClient

    uri = args.mongo_uri or os.getenv("MONGODB_URI")
    if not uri:
        try:
            from dotenv import load_dotenv
            for p in (ROOT / ".env", Path("/app/.env"), Path(".env")):
                if p.exists():
                    load_dotenv(p)
                    break
        except Exception:
            pass
        uri = os.getenv("MONGODB_URI")
    if not uri:
        print("❌ No MongoDB URI (pass --mongo-uri or set MONGODB_URI).")
        sys.exit(1)

    archive_db_name = args.archive_db or os.getenv("MONGODB_ARCHIVE_DATABASE", "ati_archive")
    client = MongoClient(uri, serverSelectionTimeoutMS=8000)
    client.admin.command("ping")
    db = client[archive_db_name]
    print(f"\n🔌 Connected. Archive DB: {archive_db_name}")

    # ensure indexes (idempotent)
    db["archive_members"].create_index("member_key", unique=True)
    db["archive_members"].create_index("status")
    db["archive_artifacts"].create_index("artifact_id", unique=True)
    db["archive_artifacts"].create_index("member_key")
    db["archive_artifacts"].create_index([("source", 1), ("type", 1)])
    db["archive_recordings"].create_index("file_id", unique=True)

    plan = {"members": (members, "archive_members", "member_key"),
            "artifacts": (artifacts, "archive_artifacts", "artifact_id"),
            "recordings": (recordings, "archive_recordings", "file_id")}
    for name, (docs, coll, key) in plan.items():
        if args.only and args.only != name:
            continue
        ins, mod = upsert(db[coll], docs, key)
        print(f"  {coll:18}: +{ins} new, ~{mod} updated  (total docs sent: {len(docs)})")
    print("\n✅ Import complete.")


if __name__ == "__main__":
    main()
