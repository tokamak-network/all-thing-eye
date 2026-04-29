"""
Filter out commits from EXTERNAL fork repositories in tokamak_commits_2019_2023.csv.

Phase A: Exclude commits from forks whose parent owner is NOT tokamak-network.
Internal forks (parent owner == tokamak-network) are kept.

Usage:
    python scripts/filter_fork_commits.py --dry     # Show stats only
    python scripts/filter_fork_commits.py           # Write filtered CSVs
"""

import os
import sys
import csv
import argparse
import requests
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_ORG = os.getenv("GITHUB_ORG", "tokamak-network")
GRAPHQL_ENDPOINT = "https://api.github.com/graphql"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INPUT_CSV = DATA_DIR / "tokamak_commits_2019_2023.csv"
OUTPUT_CSV = DATA_DIR / "tokamak_commits_2019_2023_filtered.csv"
EXCLUDED_CSV = DATA_DIR / "tokamak_commits_2019_2023_excluded.csv"


def fetch_forks() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (external_forks, internal_forks) as [(repo_name, parent_nameWithOwner), ...]."""
    query = """
    query($org: String!, $cursor: String) {
      organization(login: $org) {
        repositories(first: 100, after: $cursor, isFork: true) {
          nodes {
            name
            parent {
              nameWithOwner
              owner { login }
            }
          }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
    """
    external, internal = [], []
    cursor = None
    has_next = True

    while has_next:
        resp = requests.post(
            GRAPHQL_ENDPOINT,
            json={"query": query, "variables": {"org": GITHUB_ORG, "cursor": cursor}},
            headers={"Authorization": f"Bearer {GITHUB_TOKEN}"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()["data"]["organization"]["repositories"]
        for r in data["nodes"]:
            parent = r.get("parent") or {}
            parent_nwo = parent.get("nameWithOwner", "")
            parent_owner = (parent.get("owner") or {}).get("login", "") or ""
            entry = (r["name"], parent_nwo)
            if parent_owner.lower() == GITHUB_ORG.lower():
                internal.append(entry)
            else:
                external.append(entry)
        has_next = data["pageInfo"]["hasNextPage"]
        cursor = data["pageInfo"]["endCursor"]

    return external, internal


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="Stats only, no file output")
    args = parser.parse_args()

    if not GITHUB_TOKEN:
        print("GITHUB_TOKEN not set in .env")
        sys.exit(1)
    if not INPUT_CSV.exists():
        print(f"Input CSV not found: {INPUT_CSV}")
        sys.exit(1)

    print(f"Fetching fork metadata for {GITHUB_ORG}...")
    external, internal = fetch_forks()
    external_names = {n for n, _ in external}

    print(f"\nFork classification")
    print(f"  External (EXCLUDE): {len(external)}")
    for n, p in sorted(external):
        print(f"    - {n:40s} <- {p}")
    print(f"  Internal (KEEP):    {len(internal)}")
    for n, p in sorted(internal):
        print(f"    - {n:40s} <- {p}")

    print(f"\nReading {INPUT_CSV}...")
    repo_before = Counter()
    repo_after = Counter()
    committer_before = set()
    committer_after = set()
    excluded_rows = []
    kept_rows = []
    fieldnames = None

    with open(INPUT_CSV, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            repo = row["repository"]
            committer = row.get("committer_id", "")
            repo_before[repo] += 1
            committer_before.add(committer)
            if repo in external_names:
                excluded_rows.append(row)
            else:
                kept_rows.append(row)
                repo_after[repo] += 1
                committer_after.add(committer)

    total_before = sum(repo_before.values())
    total_after = len(kept_rows)
    total_excluded = len(excluded_rows)

    print(f"\nResults")
    print(f"  Commits before:    {total_before:>8,}  ({len(repo_before)} repos, {len(committer_before)} unique committers)")
    print(f"  Commits kept:      {total_after:>8,}  ({len(repo_after)} repos, {len(committer_after)} unique committers)")
    print(f"  Commits excluded:  {total_excluded:>8,}  ({100*total_excluded/total_before:.1f}%)")

    excluded_by_repo = Counter(row["repository"] for row in excluded_rows)
    print(f"\nTop excluded repos:")
    for name, cnt in excluded_by_repo.most_common(20):
        print(f"  {name:40s} {cnt:>8,}")

    # Top committers in kept vs excluded
    kept_committers = Counter(row["committer_id"] for row in kept_rows)
    excluded_committers = Counter(row["committer_id"] for row in excluded_rows)
    print(f"\nTop 15 committers in KEPT data:")
    for name, cnt in kept_committers.most_common(15):
        print(f"  {name:35s} {cnt:>6,}")
    print(f"\nTop 15 committers in EXCLUDED data (fork noise):")
    for name, cnt in excluded_committers.most_common(15):
        print(f"  {name:35s} {cnt:>6,}")

    if args.dry:
        print("\nDry run complete. No files written.")
        return

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept_rows)
    with open(EXCLUDED_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(excluded_rows)

    print(f"\nWritten:")
    print(f"  Filtered: {OUTPUT_CSV} ({total_after:,} rows)")
    print(f"  Excluded: {EXCLUDED_CSV} ({total_excluded:,} rows)")


if __name__ == "__main__":
    main()
