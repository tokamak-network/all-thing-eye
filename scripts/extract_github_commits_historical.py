"""
Extract all GitHub commits from tokamak-network organization (2019-2023).

Output fields: repository, committer_id, committer_email, commit_hash,
               commit_date, commit_message, commit_url, additions, deletions

Usage:
    python scripts/extract_github_commits_historical.py
    python scripts/extract_github_commits_historical.py --test          # test with 3 repos
    python scripts/extract_github_commits_historical.py --resume        # resume interrupted run
    python scripts/extract_github_commits_historical.py --year 2023     # specific year only
"""

import os
import sys
import csv
import json
import time
import argparse
import requests
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_ORG = os.getenv("GITHUB_ORG", "tokamak-network")
GRAPHQL_ENDPOINT = "https://api.github.com/graphql"

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_CSV = OUTPUT_DIR / f"tokamak_commits_2019_2023.csv"
PROGRESS_FILE = OUTPUT_DIR / f"tokamak_commits_progress.json"

CSV_FIELDS = [
    "repository",
    "committer_id",
    "committer_email",
    "commit_hash",
    "commit_date",
    "commit_message",
    "commit_url",
    "additions",
    "deletions",
]

session = requests.Session()
session.headers.update(
    {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }
)


def graphql_query(query: str, variables: dict, retries: int = 5) -> dict | None:
    for attempt in range(1, retries + 1):
        try:
            resp = session.post(
                GRAPHQL_ENDPOINT,
                json={"query": query, "variables": variables},
                timeout=30,
            )

            # Rate limit check
            remaining = int(resp.headers.get("X-RateLimit-Remaining", 5000))
            if remaining < 50:
                reset_ts = int(resp.headers.get("X-RateLimit-Reset", 0))
                wait = max(reset_ts - time.time(), 0) + 5
                print(f"\n   ⏳ Rate limit low ({remaining}). Waiting {wait:.0f}s...")
                time.sleep(wait)

            if not resp.ok:
                if resp.status_code in (502, 503, 504) and attempt < retries:
                    wait = min(2 ** (attempt - 1) * 2, 30)
                    print(f"   ⚠️  HTTP {resp.status_code}, retry in {wait}s...")
                    time.sleep(wait)
                    continue
                raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

            data = resp.json()
            if "errors" in data:
                error_msg = data["errors"][0].get("message", "")
                # Timeout errors - retry
                if "timeout" in error_msg.lower() and attempt < retries:
                    wait = min(2 ** (attempt - 1) * 2, 30)
                    print(f"   ⚠️  GraphQL timeout, retry in {wait}s...")
                    time.sleep(wait)
                    continue
                print(f"   ⚠️  GraphQL error: {error_msg}")

            return data.get("data")

        except requests.exceptions.RequestException as e:
            if attempt < retries:
                wait = min(2 ** (attempt - 1) * 2, 30)
                print(f"   ⚠️  Network error (attempt {attempt}): {e}. Retry in {wait}s...")
                time.sleep(wait)
                continue
            raise

    return None


def fetch_all_repos() -> list[dict]:
    """Fetch all repos in the org."""
    query = """
        query($org: String!, $cursor: String) {
            organization(login: $org) {
                repositories(first: 100, after: $cursor, orderBy: {field: PUSHED_AT, direction: DESC}) {
                    nodes {
                        name
                        isArchived
                        pushedAt
                        createdAt
                        defaultBranchRef { name }
                    }
                    pageInfo { hasNextPage endCursor }
                }
            }
        }
    """
    repos = []
    cursor = None
    has_next = True

    while has_next:
        result = graphql_query(query, {"org": GITHUB_ORG, "cursor": cursor})
        if not result or "organization" not in result:
            break
        data = result["organization"]["repositories"]
        repos.extend(data["nodes"])
        has_next = data["pageInfo"]["hasNextPage"]
        cursor = data["pageInfo"]["endCursor"]

    return repos


def filter_repos(repos: list[dict], start_date: str, end_date: str) -> list[dict]:
    """Filter repos that might have commits in the date range."""
    filtered = []
    for r in repos:
        if not r.get("defaultBranchRef"):
            continue
        created = r.get("createdAt", "")
        pushed = r.get("pushedAt", "")
        # Include if repo was created before end_date and had activity after start_date
        if created <= end_date and pushed >= start_date:
            filtered.append(r)
    return filtered


def fetch_repo_commits(
    repo_name: str, since: str, until: str
) -> list[dict]:
    """Fetch all commits from default branch of a repo in the date range."""
    query = """
        query($owner: String!, $name: String!, $since: GitTimestamp!, $until: GitTimestamp!, $cursor: String) {
            repository(owner: $owner, name: $name) {
                defaultBranchRef {
                    target {
                        ... on Commit {
                            history(since: $since, until: $until, first: 100, after: $cursor) {
                                totalCount
                                pageInfo { hasNextPage endCursor }
                                nodes {
                                    oid
                                    message
                                    url
                                    committedDate
                                    additions
                                    deletions
                                    author {
                                        name
                                        email
                                        user { login }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    """

    all_commits = []
    cursor = None
    has_next = True
    seen_shas = set()
    page = 0

    while has_next:
        page += 1
        result = graphql_query(
            query,
            {
                "owner": GITHUB_ORG,
                "name": repo_name,
                "since": since,
                "until": until,
                "cursor": cursor,
            },
        )

        if not result or not result.get("repository"):
            break

        ref = result["repository"].get("defaultBranchRef")
        if not ref or not ref.get("target"):
            break

        history = ref["target"].get("history")
        if not history:
            break

        total = history.get("totalCount", "?")
        if page == 1:
            print(f"({total} commits in range) ", end="", flush=True)

        for node in history["nodes"]:
            sha = node["oid"]
            if sha in seen_shas:
                continue
            seen_shas.add(sha)

            author = node.get("author") or {}
            user = author.get("user") or {}

            all_commits.append(
                {
                    "repository": repo_name,
                    "committer_id": user.get("login", author.get("name", "")),
                    "committer_email": author.get("email", ""),
                    "commit_hash": sha,
                    "commit_date": node["committedDate"],
                    "commit_message": node.get("message", "").replace("\n", " ").strip(),
                    "commit_url": node.get("url", ""),
                    "additions": node.get("additions", 0),
                    "deletions": node.get("deletions", 0),
                }
            )

        has_next = history["pageInfo"]["hasNextPage"]
        cursor = history["pageInfo"]["endCursor"]

        # Progress for large repos
        if page % 50 == 0:
            print(f"[p{page}/{(total//100)+1 if isinstance(total,int) else '?'}] ", end="", flush=True)

    return all_commits


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"completed_repos": [], "total_commits": 0}


def save_progress(progress: dict):
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Extract tokamak-network GitHub commits")
    parser.add_argument("--test", action="store_true", help="Test mode: process only 3 repos")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--year", type=int, help="Extract specific year only (e.g. 2023)")
    args = parser.parse_args()

    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN not set in .env")
        sys.exit(1)

    # Date range
    if args.year:
        since = f"{args.year}-01-01T00:00:00Z"
        until = f"{args.year + 1}-01-01T00:00:00Z"
        print(f"📅 Extracting year {args.year}")
    else:
        since = "2019-01-01T00:00:00Z"
        until = "2024-01-01T00:00:00Z"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Progress tracking
    progress = load_progress() if args.resume else {"completed_repos": [], "total_commits": 0}
    completed = set(progress["completed_repos"])

    # Auth check
    print(f"🔐 Authenticating with GitHub API...")
    auth_result = graphql_query("query { viewer { login } }", {})
    if not auth_result or "viewer" not in auth_result:
        print("❌ Authentication failed")
        sys.exit(1)
    print(f"   ✅ Authenticated as {auth_result['viewer']['login']}")

    # Fetch repos
    print(f"\n📦 Fetching repositories for {GITHUB_ORG}...")
    all_repos = fetch_all_repos()
    print(f"   Found {len(all_repos)} total repositories")

    # Filter
    repos = filter_repos(all_repos, since, until)
    print(f"   {len(repos)} repos with potential commits in range")

    if args.test:
        repos = repos[:3]
        print(f"   🧪 Test mode: processing {len(repos)} repos only")

    # Skip completed
    if completed:
        repos = [r for r in repos if r["name"] not in completed]
        print(f"   ⏩ Resuming: {len(completed)} repos already done, {len(repos)} remaining")

    # CSV setup
    csv_mode = "a" if args.resume and OUTPUT_CSV.exists() else "w"
    csv_file = open(OUTPUT_CSV, csv_mode, newline="", encoding="utf-8")
    writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
    if csv_mode == "w":
        writer.writeheader()

    total_commits = progress["total_commits"]
    start_time = time.time()

    print(f"\n🚀 Starting extraction ({since[:10]} ~ {until[:10]})")
    print(f"{'='*60}")

    for i, repo in enumerate(repos, 1):
        repo_name = repo["name"]
        print(f"\n[{i}/{len(repos)}] {repo_name}...", end=" ", flush=True)

        try:
            commits = fetch_repo_commits(repo_name, since, until)
            if commits:
                writer.writerows(commits)
                csv_file.flush()
                total_commits += len(commits)
                print(f"✅ {len(commits)} commits (total: {total_commits})")
            else:
                print(f"- 0 commits")

            # Save progress
            completed.add(repo_name)
            progress["completed_repos"] = list(completed)
            progress["total_commits"] = total_commits
            save_progress(progress)

        except Exception as e:
            print(f"❌ Error: {e}")
            continue

    csv_file.close()
    elapsed = time.time() - start_time

    print(f"\n{'='*60}")
    print(f"✅ Extraction complete!")
    print(f"   Total commits: {total_commits}")
    print(f"   Output: {OUTPUT_CSV}")
    print(f"   Elapsed: {elapsed/60:.1f} minutes")

    # Cleanup progress file on full completion
    if not args.test and PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
        print(f"   Progress file cleaned up")


if __name__ == "__main__":
    main()
