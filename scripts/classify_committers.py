"""
Classify committers by likelihood of being a tokamak-network member.

Tiers:
  A - Confirmed: has an @onther.io email (Onther is tokamak's parent company)
  B - High likelihood: committed to 15+ distinct repos (breadth signal)
  C - Medium: 5-14 repos, no external-domain hits, not bot
  D - Low: <=4 repos OR bot OR single-repo disguised-fork committer

Known "disguised fork" repos (not marked isFork=true on GitHub but clearly
upstream copies). Committers who ONLY touch these are almost certainly
upstream contributors, not tokamak members.

Usage:
    python scripts/classify_committers.py
    python scripts/classify_committers.py --tier A     # print only tier A
"""

import csv
import argparse
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CLEAN_CSV = DATA_DIR / "tokamak_commits_2019_2023_clean.csv"
OUTPUT_CSV = DATA_DIR / "committer_classification.csv"

# Repos that are upstream copies (not isFork=true, but clearly forked content).
# Committers whose work is entirely within these repos are very likely
# external upstream developers, not tokamak members.
DISGUISED_FORKS = {
    "tokamak-thanos",
    "tokamak-thanos-geth",
    "tokamak-titan",
    "tokamak-titan-explorer",
    "tokamak-optimism-blockscout",
    "tokamak-graph-node",
    "cbdc-optimism",
    "cbdc-optimism-old",
    "tokamak-uniswap-v3-core",
    "tokamak-uniswap-v3-periphery",
    "tokamak-uniswap-v3-interface",
    "tokamak-swap-router-contracts",
    "tokamak-uniswap-subgraph",
    "plasma-evm",
    "klaytn-for-testing",
}


def classify(cid: str, commits: int, repos: set[str], domains: set[str]) -> tuple[str, str]:
    """Return (tier, reason)."""
    is_bot = "[bot]" in cid.lower() or cid.lower().endswith("-bot") or cid in {"OptimismBot", "crowdin-bot", "Automated Version Bump", "actions-user"}
    if is_bot:
        return "D", "bot account"

    if "onther.io" in domains:
        return "A", "onther.io email (confirmed tokamak)"

    repo_count = len(repos)
    non_fork_repos = repos - DISGUISED_FORKS

    if len(non_fork_repos) >= 15:
        return "B", f"{len(non_fork_repos)} non-fork repos (high breadth)"
    if repo_count >= 15:
        return "B", f"{repo_count} repos (high breadth, some disguised forks)"

    if repo_count >= 5 and len(non_fork_repos) >= 3:
        return "C", f"{repo_count} repos, {len(non_fork_repos)} genuine tokamak repos"

    if not non_fork_repos:
        return "D", "only committed to disguised-fork repos"

    if repo_count <= 4:
        return "D", f"only {repo_count} repos, narrow scope"

    return "C", f"{repo_count} repos"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", choices=["A", "B", "C", "D"], help="Filter by tier")
    parser.add_argument("--top", type=int, default=150, help="Print top N")
    args = parser.parse_args()

    if not CLEAN_CSV.exists():
        print(f"Input not found: {CLEAN_CSV}")
        return

    profile = defaultdict(lambda: {"commits": 0, "repos": set(), "emails": set(), "first": None, "last": None})
    with open(CLEAN_CSV) as f:
        for row in csv.DictReader(f):
            cid = row["committer_id"]
            p = profile[cid]
            p["commits"] += 1
            p["repos"].add(row["repository"])
            email = (row.get("committer_email") or "").lower()
            if "@" in email:
                p["emails"].add(email)
            d = row["commit_date"]
            if p["first"] is None or d < p["first"]:
                p["first"] = d
            if p["last"] is None or d > p["last"]:
                p["last"] = d

    rows = []
    for cid, p in profile.items():
        domains = {e.split("@", 1)[1] for e in p["emails"]}
        tier, reason = classify(cid, p["commits"], p["repos"], domains)
        non_fork_repos = p["repos"] - DISGUISED_FORKS
        rows.append({
            "tier": tier,
            "committer_id": cid,
            "commits": p["commits"],
            "total_repos": len(p["repos"]),
            "non_fork_repos": len(non_fork_repos),
            "reason": reason,
            "domains": "; ".join(sorted(domains)),
            "top_repos": "; ".join(sorted(p["repos"], key=lambda r: r)[:8]),
            "first_date": (p["first"] or "")[:10],
            "last_date": (p["last"] or "")[:10],
        })

    tier_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    rows.sort(key=lambda r: (tier_order[r["tier"]], -r["commits"]))

    if args.tier:
        rows = [r for r in rows if r["tier"] == args.tier]

    # Write CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    # Tier counts
    tier_counts = defaultdict(lambda: {"committers": 0, "commits": 0})
    for r in rows:
        t = r["tier"]
        tier_counts[t]["committers"] += 1
        tier_counts[t]["commits"] += r["commits"]

    print(f"Written: {OUTPUT_CSV}")
    print()
    print("Tier breakdown:")
    for t in ["A", "B", "C", "D"]:
        info = tier_counts[t]
        print(f"  {t}: {info['committers']:>5} committers, {info['commits']:>7,} commits")

    print()
    print(f"Top {args.top}{'  (tier=' + args.tier + ')' if args.tier else ''}:")
    print(f"{'tier':<4} {'committer_id':<28} {'cm':>5} {'rp':>3} {'nfrp':>4}  {'span':<23}  {'reason'}")
    print("-" * 140)
    for r in rows[: args.top]:
        span = f"{r['first_date']}~{r['last_date']}"
        print(
            f"{r['tier']:<4} {r['committer_id']:<28} {r['commits']:>5} {r['total_repos']:>3} {r['non_fork_repos']:>4}  "
            f"{span:<23}  {r['reason']}"
        )


if __name__ == "__main__":
    main()
