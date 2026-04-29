"""
Phase B: Remove upstream commits from "disguised fork" repositories.

Disguised forks = repos where GitHub reports isFork: false, but are actually
clones of external projects. We keep only commits whose SHA does NOT appear
in the upstream repo's commit history.

Approach: Fetch ALL commit SHAs from upstream default branch via GraphQL
(paginated, 100/page), then filter out matching SHAs from the disguised fork
entries in the CSV.

Usage:
    python scripts/phase_b_disguised_fork_filter.py --dry     # stats only
    python scripts/phase_b_disguised_fork_filter.py --cache   # use/save SHA cache
    python scripts/phase_b_disguised_fork_filter.py           # write final CSV
    python scripts/phase_b_disguised_fork_filter.py --dry --cache
"""

import os
import sys
import csv
import json
import time
import argparse
import requests
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GRAPHQL_ENDPOINT = "https://api.github.com/graphql"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INPUT_CSV = DATA_DIR / "tokamak_commits_2019_2023_clean.csv"
OUTPUT_CSV = DATA_DIR / "tokamak_commits_2019_2023_final.csv"
CACHE_FILE = DATA_DIR / "upstream_shas_cache.json"

# Disguised fork -> upstream repo (owner/name)
DISGUISED_FORKS = {
    "tokamak-thanos":               "ethereum-optimism/optimism",
    "tokamak-thanos-geth":          "ethereum/go-ethereum",
    "tokamak-titan":                "ethereum-optimism/optimism",
    "tokamak-titan-explorer":       "blockscout/blockscout",
    "tokamak-optimism-blockscout":  "blockscout/blockscout",
    "cbdc-optimism":                "ethereum-optimism/optimism",
    "cbdc-optimism-old":            "ethereum-optimism/optimism",
    "tokamak-uniswap-v3-core":      "Uniswap/v3-core",
    "tokamak-uniswap-v3-periphery": "Uniswap/v3-periphery",
    "tokamak-uniswap-v3-interface": "Uniswap/interface",
    "tokamak-swap-router-contracts":"Uniswap/swap-router-contracts",
    "tokamak-uniswap-subgraph":     "Uniswap/v3-subgraph",
    "tokamak-graph-node":           "graphprotocol/graph-node",
    "plasma-evm":                   "ethereum/go-ethereum",
    "klaytn-for-testing":           "klaytn/klaytn",
}

# Unique upstreams (multiple forks may share an upstream)
UPSTREAM_REPOS = sorted(set(DISGUISED_FORKS.values()))

# Date range for upstream SHA collection (wider than CSV range to catch all upstream commits)
SINCE = "2018-01-01T00:00:00Z"
UNTIL = "2024-12-31T23:59:59Z"

session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Content-Type": "application/json",
})


def graphql_query(query: str, variables: dict, retries: int = 5) -> dict | None:
    for attempt in range(1, retries + 1):
        try:
            resp = session.post(
                GRAPHQL_ENDPOINT,
                json={"query": query, "variables": variables},
                timeout=60,
            )

            remaining = int(resp.headers.get("X-RateLimit-Remaining", 5000))
            if remaining < 50:
                reset_ts = int(resp.headers.get("X-RateLimit-Reset", 0))
                wait = max(reset_ts - time.time(), 0) + 5
                print(f"   Rate limit low ({remaining}). Waiting {wait:.0f}s...")
                time.sleep(wait)

            if not resp.ok:
                if resp.status_code in (502, 503, 504) and attempt < retries:
                    wait = min(2 ** (attempt - 1) * 2, 30)
                    print(f"   HTTP {resp.status_code}, retry in {wait}s...")
                    time.sleep(wait)
                    continue
                raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

            data = resp.json()
            if "errors" in data:
                error_msg = data["errors"][0].get("message", "")
                if "timeout" in error_msg.lower() and attempt < retries:
                    wait = min(2 ** (attempt - 1) * 2, 30)
                    print(f"   GraphQL timeout, retry in {wait}s...")
                    time.sleep(wait)
                    continue
                print(f"   GraphQL error: {error_msg}")

            return data.get("data")

        except requests.exceptions.RequestException as e:
            if attempt < retries:
                wait = min(2 ** (attempt - 1) * 2, 30)
                print(f"   Network error (attempt {attempt}): {e}. Retry in {wait}s...")
                time.sleep(wait)
                continue
            raise

    return None


COMMIT_HISTORY_QUERY = """
query($owner: String!, $name: String!, $since: GitTimestamp!, $until: GitTimestamp!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(since: $since, until: $until, first: 100, after: $cursor) {
            totalCount
            pageInfo { hasNextPage endCursor }
            nodes { oid }
          }
        }
      }
    }
  }
}
"""


def fetch_upstream_shas(upstream: str) -> set[str]:
    """Fetch all commit SHAs from an upstream repo's default branch."""
    owner, name = upstream.split("/", 1)
    print(f"  Fetching SHAs from {upstream}...")

    shas: set[str] = set()
    cursor = None
    page = 0

    while True:
        variables = {
            "owner": owner,
            "name": name,
            "since": SINCE,
            "until": UNTIL,
            "cursor": cursor,
        }
        data = graphql_query(COMMIT_HISTORY_QUERY, variables)

        if not data:
            print(f"    No data returned for {upstream}, stopping.")
            break

        repo = data.get("repository")
        if not repo:
            print(f"    Repository not found: {upstream}")
            break

        default_branch = repo.get("defaultBranchRef")
        if not default_branch:
            print(f"    No default branch for {upstream}")
            break

        history = default_branch["target"]["history"]
        nodes = history["nodes"]
        total = history["totalCount"]

        for node in nodes:
            shas.add(node["oid"])

        page += 1
        if page == 1:
            print(f"    Total commits in range: {total:,}")

        page_info = history["pageInfo"]
        if not page_info["hasNextPage"]:
            break

        cursor = page_info["endCursor"]

        if page % 10 == 0:
            print(f"    ... page {page}, fetched {len(shas):,} SHAs so far")

    print(f"    Done: {len(shas):,} unique SHAs")
    return shas


def load_cache() -> dict[str, list[str]]:
    if CACHE_FILE.exists():
        print(f"Loading SHA cache from {CACHE_FILE}...")
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict[str, list[str]]) -> None:
    print(f"Saving SHA cache to {CACHE_FILE}...")
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f)
    size_mb = CACHE_FILE.stat().st_size / 1_048_576
    print(f"Cache saved ({size_mb:.1f} MB)")


def get_all_upstream_shas(use_cache: bool) -> dict[str, set[str]]:
    """Returns {upstream_repo: set_of_shas}."""
    cache: dict[str, list[str]] = {}
    if use_cache:
        cache = load_cache()

    result: dict[str, set[str]] = {}

    for upstream in UPSTREAM_REPOS:
        if use_cache and upstream in cache:
            print(f"  {upstream}: loaded {len(cache[upstream]):,} SHAs from cache")
            result[upstream] = set(cache[upstream])
        else:
            shas = fetch_upstream_shas(upstream)
            result[upstream] = shas
            if use_cache:
                cache[upstream] = list(shas)

    if use_cache:
        save_cache(cache)

    return result


def main():
    parser = argparse.ArgumentParser(description="Phase B: Filter upstream commits from disguised forks")
    parser.add_argument("--dry", action="store_true", help="Stats only, no file output")
    parser.add_argument("--cache", action="store_true", help="Cache upstream SHAs to disk")
    args = parser.parse_args()

    if not GITHUB_TOKEN:
        print("GITHUB_TOKEN not set in .env")
        sys.exit(1)
    if not INPUT_CSV.exists():
        print(f"Input CSV not found: {INPUT_CSV}")
        sys.exit(1)

    print("=" * 60)
    print("Phase B: Disguised Fork Upstream Commit Filter")
    print("=" * 60)
    print(f"\nDisguised fork repos: {len(DISGUISED_FORKS)}")
    print(f"Unique upstreams:     {len(UPSTREAM_REPOS)}")
    print()

    # --- Step 1: Collect upstream SHAs ---
    print("Step 1: Fetching upstream commit SHAs")
    print("-" * 40)
    upstream_shas = get_all_upstream_shas(use_cache=args.cache)

    # Build per-fork SHA lookup: fork_repo -> upstream_sha_set
    fork_to_upstream_shas: dict[str, set[str]] = {}
    for fork_repo, upstream in DISGUISED_FORKS.items():
        fork_to_upstream_shas[fork_repo] = upstream_shas.get(upstream, set())

    total_upstream_shas = sum(len(s) for s in upstream_shas.values())
    print(f"\nTotal upstream SHAs collected: {total_upstream_shas:,}")

    # --- Step 2: Filter CSV ---
    print("\nStep 2: Filtering CSV")
    print("-" * 40)
    print(f"Reading {INPUT_CSV}...")

    kept_rows: list[dict] = []
    removed_rows: list[dict] = []
    fieldnames = None

    # Per-fork stats
    fork_before: Counter = Counter()
    fork_after: Counter = Counter()
    fork_removed_committers: dict[str, set] = defaultdict(set)

    with open(INPUT_CSV, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            repo = row["repository"]
            sha = row["commit_hash"]
            committer = row.get("committer_id", "")

            if repo in fork_to_upstream_shas:
                fork_before[repo] += 1
                upstream_set = fork_to_upstream_shas[repo]
                if sha in upstream_set:
                    # This is an upstream commit — remove it
                    removed_rows.append(row)
                    fork_removed_committers[repo].add(committer)
                else:
                    # Tokamak-original commit — keep it
                    kept_rows.append(row)
                    fork_after[repo] += 1
            else:
                # Non-disguised-fork repo — always keep
                kept_rows.append(row)

    # --- Step 3: Stats report ---
    total_in_csv = sum(fork_before.values()) + sum(
        1 for row in kept_rows if row["repository"] not in fork_to_upstream_shas
    )

    # Recount non-fork rows
    non_fork_count = len(kept_rows) - sum(fork_after.values())

    total_before = len(kept_rows) + len(removed_rows)
    total_kept = len(kept_rows)
    total_removed = len(removed_rows)

    removed_committers_all: set[str] = set()
    for s in fork_removed_committers.values():
        removed_committers_all.update(s)

    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Total commits before:  {total_before:>8,}")
    print(f"Total commits kept:    {total_kept:>8,}")
    print(f"Total commits removed: {total_removed:>8,}  ({100*total_removed/max(total_before,1):.1f}%)")
    print(f"Removed unique committers: {len(removed_committers_all):,}")

    print(f"\n{'Per disguised fork breakdown':}")
    print(f"  {'Repo':<45} {'Before':>8} {'Kept':>8} {'Removed':>8} {'%Removed':>9}")
    print(f"  {'-'*45} {'-'*8} {'-'*8} {'-'*8} {'-'*9}")
    for repo in sorted(fork_before.keys(), key=lambda r: -(fork_before[r] - fork_after[r])):
        before = fork_before[repo]
        after = fork_after[repo]
        removed = before - after
        pct = 100 * removed / max(before, 1)
        print(f"  {repo:<45} {before:>8,} {after:>8,} {removed:>8,} {pct:>8.1f}%")

    if args.dry:
        print("\nDry run complete. No files written.")
        return

    # --- Step 4: Write output ---
    print(f"\nWriting {OUTPUT_CSV}...")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept_rows)

    print(f"Done. Written {total_kept:,} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
