"""
Generate per-committer profile from filtered commit data.

Helps infer past tokamak-network members by showing each committer's
activity pattern: total commits, repos worked on, email domains,
activity span.

Usage:
    python scripts/committer_profile.py                 # Use filtered CSV
    python scripts/committer_profile.py --raw           # Use raw CSV
"""

import csv
import argparse
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CLEAN_CSV = DATA_DIR / "tokamak_commits_2019_2023_clean.csv"
FILTERED_CSV = DATA_DIR / "tokamak_commits_2019_2023_filtered.csv"
RAW_CSV = DATA_DIR / "tokamak_commits_2019_2023.csv"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", action="store_true", help="Use unfiltered raw CSV")
    parser.add_argument("--filtered", action="store_true", help="Use fork-filtered CSV")
    parser.add_argument("--top", type=int, default=50, help="Print top N committers")
    args = parser.parse_args()

    if args.raw:
        src = RAW_CSV
    elif args.filtered:
        src = FILTERED_CSV
    else:
        src = CLEAN_CSV if CLEAN_CSV.exists() else FILTERED_CSV
    output_csv = DATA_DIR / f"committer_profiles_{src.stem.replace('tokamak_commits_2019_2023_', '') or 'raw'}.csv"
    if not src.exists():
        print(f"Input not found: {src}")
        if not args.raw:
            print("Run scripts/filter_fork_commits.py first.")
        return

    # Aggregate
    profile = defaultdict(lambda: {
        "commits": 0,
        "repos": defaultdict(int),
        "emails": defaultdict(int),
        "first_date": None,
        "last_date": None,
    })

    with open(src) as f:
        for row in csv.DictReader(f):
            cid = row["committer_id"]
            p = profile[cid]
            p["commits"] += 1
            p["repos"][row["repository"]] += 1
            email = row.get("committer_email", "") or ""
            if email:
                p["emails"][email] += 1
            date = row["commit_date"]
            if p["first_date"] is None or date < p["first_date"]:
                p["first_date"] = date
            if p["last_date"] is None or date > p["last_date"]:
                p["last_date"] = date

    # Build rows
    rows = []
    for cid, p in profile.items():
        email_list = [e for e, _ in sorted(p["emails"].items(), key=lambda x: -x[1])]
        domains = sorted({e.split("@", 1)[-1].lower() for e in email_list if "@" in e})
        repos = sorted(p["repos"].items(), key=lambda x: -x[1])
        rows.append({
            "committer_id": cid,
            "total_commits": p["commits"],
            "repo_count": len(p["repos"]),
            "top_repos": "; ".join(f"{r}({c})" for r, c in repos[:5]),
            "email_count": len(email_list),
            "emails": "; ".join(email_list[:3]),
            "email_domains": "; ".join(domains[:5]),
            "first_date": (p["first_date"] or "")[:10],
            "last_date": (p["last_date"] or "")[:10],
        })

    rows.sort(key=lambda r: -r["total_commits"])

    # Write CSV
    fieldnames = list(rows[0].keys())
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Print preview
    print(f"Source: {src.name}")
    print(f"Unique committers: {len(rows)}")
    print(f"Written: {output_csv}")
    print()
    print(f"Top {args.top} committers:")
    print(f"{'committer_id':<30} {'commits':>7} {'repos':>5}  {'span':<25}  domains")
    print("-" * 130)
    for r in rows[: args.top]:
        span = f"{r['first_date']} ~ {r['last_date']}"
        print(
            f"{r['committer_id']:<30} {r['total_commits']:>7} {r['repo_count']:>5}  "
            f"{span:<25}  {r['email_domains'][:50]}"
        )


if __name__ == "__main__":
    main()
