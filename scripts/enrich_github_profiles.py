"""
Fetch GitHub user profile data for each committer_id.

Calls GET /users/{login} and captures:
  name, bio, company, email, blog, twitter_username, location, created_at

Skips obvious non-GitHub-login committer_ids (those with spaces or dots that look like git author.name).

Input:  data/committer_classification.csv
Output: data/github_profiles.csv
Cache:  data/github_profiles_cache.json (resume-safe)

Usage:
    python scripts/enrich_github_profiles.py              # all committers
    python scripts/enrich_github_profiles.py --tiers A B  # only specified tiers
    python scripts/enrich_github_profiles.py --min-commits 50
"""

import os
import sys
import csv
import json
import time
import argparse
import re
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INPUT = DATA_DIR / "committer_classification.csv"
OUTPUT = DATA_DIR / "github_profiles.csv"
CACHE = DATA_DIR / "github_profiles_cache.json"

FIELDS = ["committer_id", "tier", "commits", "login", "name", "email",
          "bio", "company", "blog", "twitter_username", "location",
          "created_at", "http_status"]


def looks_like_github_login(s: str) -> bool:
    if not s:
        return False
    if " " in s:  # git author.name like "Will Cory"
        return False
    if s.endswith("[bot]"):  # keep bots for completeness, but skip API
        return False
    # GitHub username rules: alphanumeric + hyphen, 1-39 chars, cannot start/end with hyphen
    return bool(re.match(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}$", s))


def fetch_profile(login: str, session: requests.Session) -> tuple[dict, int]:
    url = f"https://api.github.com/users/{login}"
    resp = session.get(url, timeout=15)
    if resp.status_code == 200:
        return resp.json(), 200
    return {}, resp.status_code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tiers", nargs="+", default=["A", "B", "C", "D"])
    parser.add_argument("--min-commits", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if not GITHUB_TOKEN:
        print("GITHUB_TOKEN not set")
        sys.exit(1)

    # Load cache
    cache = {}
    if CACHE.exists():
        cache = json.loads(CACHE.read_text())
    print(f"Cache has {len(cache)} entries")

    # Load input
    inputs = []
    with open(INPUT) as f:
        for row in csv.DictReader(f):
            if row["tier"] not in args.tiers:
                continue
            if int(row["commits"]) < args.min_commits:
                continue
            inputs.append(row)

    if args.limit:
        inputs = inputs[: args.limit]

    # Separate GitHub-loginnable from non-loginnable
    processable = [r for r in inputs if looks_like_github_login(r["committer_id"])]
    skipped = [r for r in inputs if not looks_like_github_login(r["committer_id"])]

    print(f"Input: {len(inputs)}  processable: {len(processable)}  skipped: {len(skipped)}")

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    })

    results = []
    # Include skipped (non-loginnable) as-is
    for r in skipped:
        results.append({
            "committer_id": r["committer_id"], "tier": r["tier"], "commits": r["commits"],
            "login": "", "name": "", "email": "", "bio": "", "company": "", "blog": "",
            "twitter_username": "", "location": "", "created_at": "", "http_status": "SKIP_NOT_LOGIN",
        })

    total = len(processable)
    for i, r in enumerate(processable, 1):
        login = r["committer_id"]
        cached = cache.get(login)
        if cached is not None:
            profile_data, status = cached.get("data", {}), cached.get("status", 0)
        else:
            try:
                profile_data, status = fetch_profile(login, session)
            except Exception as e:
                profile_data, status = {}, f"ERR:{e}"
            cache[login] = {"data": profile_data, "status": status}
            if i % 25 == 0:
                # persist cache periodically
                CACHE.write_text(json.dumps(cache, ensure_ascii=False))
                print(f"  [{i}/{total}] {login:30s} status={status}  name={profile_data.get('name', '') if profile_data else ''}")

        results.append({
            "committer_id": login, "tier": r["tier"], "commits": r["commits"],
            "login": profile_data.get("login", "") if profile_data else "",
            "name": profile_data.get("name", "") or "" if profile_data else "",
            "email": profile_data.get("email", "") or "" if profile_data else "",
            "bio": (profile_data.get("bio", "") or "").replace("\n", " ").replace("\r", " ") if profile_data else "",
            "company": profile_data.get("company", "") or "" if profile_data else "",
            "blog": profile_data.get("blog", "") or "" if profile_data else "",
            "twitter_username": profile_data.get("twitter_username", "") or "" if profile_data else "",
            "location": profile_data.get("location", "") or "" if profile_data else "",
            "created_at": profile_data.get("created_at", "") or "" if profile_data else "",
            "http_status": status,
        })

    # Save cache
    CACHE.write_text(json.dumps(cache, ensure_ascii=False))

    # Write output CSV
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(results)

    # Stats
    have_name = sum(1 for r in results if r["name"])
    have_company = sum(1 for r in results if r["company"])
    have_email = sum(1 for r in results if r["email"])
    status_404 = sum(1 for r in results if r["http_status"] == 404)
    status_200 = sum(1 for r in results if r["http_status"] == 200)

    print()
    print(f"Written: {OUTPUT} ({len(results)} rows)")
    print(f"  200 OK: {status_200}")
    print(f"  404 not found: {status_404}")
    print(f"  Skipped (non-login): {len(skipped)}")
    print(f"  Has real name:    {have_name}")
    print(f"  Has company:      {have_company}")
    print(f"  Has public email: {have_email}")

    # Print sample of Tier A/B with real names
    print()
    print("Tier A/B/C with real names (sample):")
    for r in results:
        if r["tier"] in ("A", "B", "C") and r["name"]:
            print(f"  {r['tier']} {r['committer_id']:<25} -> name='{r['name']}'  company='{r['company']}'  email='{r['email']}'")


if __name__ == "__main__":
    main()
