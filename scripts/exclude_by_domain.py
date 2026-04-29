"""
Second-stage filter: exclude committers whose emails match known external domains.

Input:  data/tokamak_commits_2019_2023_filtered.csv  (after fork exclusion)
Output: data/tokamak_commits_2019_2023_clean.csv     (final clean dataset)
        data/excluded_committers_by_domain.csv        (who was excluded and why)

A committer is excluded if ANY of their commit emails has a domain in
EXTERNAL_DOMAINS. This is conservative (false negatives) but avoids
wrongly excluding tokamak members who occasionally used personal emails.

Usage:
    python scripts/exclude_by_domain.py --dry
    python scripts/exclude_by_domain.py
"""

import csv
import argparse
from pathlib import Path
from collections import defaultdict, Counter

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INPUT_CSV = DATA_DIR / "tokamak_commits_2019_2023_filtered.csv"
OUTPUT_CSV = DATA_DIR / "tokamak_commits_2019_2023_clean.csv"
EXCLUDED_CSV = DATA_DIR / "excluded_committers_by_domain.csv"

# Known external organization domains. Any committer with an email at one
# of these domains is NOT a tokamak member.
EXTERNAL_DOMAINS = {
    # OP Labs / Optimism
    "oplabs.co",
    "optimism.io",
    "matthewslipper.com",
    "protolambda.com",
    "clab.by",
    "karlfloersch.com",
    "pseudonym.party",
    # Uniswap
    "uniswap.org",
    # The Graph / Edge & Node
    "edgeandnode.com",
    "thegraph.com",
    "watzmann.net",
    # GroundX / Klaytn / Krust (Kakao)
    "groundx.xyz",
    "krustuniverse.com",
    # Individual external crypto engineers
    "lightning.engineering",
    "gakonst.com",
    "comma.ai",
    "swende.se",
    "liamhorne.com",
    "lihorne.com",
    "symphonious.net",
    "altoros.com",
    "arenabg.com",
    "twurst.com",
    # Blockscout
    "blockscout.com",
    # Bot/automation
    "crowdin.com",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()

    if not INPUT_CSV.exists():
        print(f"Input not found: {INPUT_CSV}")
        print("Run scripts/filter_fork_commits.py first.")
        return

    committer_emails = defaultdict(set)
    committer_commits = Counter()
    rows_by_committer = defaultdict(list)
    fieldnames = None

    with open(INPUT_CSV, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            cid = row["committer_id"]
            email = (row.get("committer_email") or "").lower()
            if "@" in email:
                committer_emails[cid].add(email.split("@", 1)[1])
            committer_commits[cid] += 1
            rows_by_committer[cid].append(row)

    excluded_committers = {}
    for cid, domains in committer_emails.items():
        hit = domains & EXTERNAL_DOMAINS
        if hit:
            excluded_committers[cid] = sorted(hit)

    kept_count = sum(c for cid, c in committer_commits.items() if cid not in excluded_committers)
    excluded_count = sum(c for cid, c in committer_commits.items() if cid in excluded_committers)

    print(f"Committers before: {len(committer_commits):,}")
    print(f"Committers excluded (domain match): {len(excluded_committers):,}")
    print(f"Committers kept: {len(committer_commits) - len(excluded_committers):,}")
    print(f"Commits before: {sum(committer_commits.values()):,}")
    print(f"Commits kept:   {kept_count:,}")
    print(f"Commits excluded: {excluded_count:,}")
    print()
    print("Top 25 excluded committers:")
    for cid, _ in Counter({c: committer_commits[c] for c in excluded_committers}).most_common(25):
        domains = ", ".join(excluded_committers[cid])
        print(f"  {cid:30s} {committer_commits[cid]:>6,}  <- {domains}")

    if args.dry:
        print("\nDry run complete.")
        return

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for cid, rows in rows_by_committer.items():
            if cid not in excluded_committers:
                writer.writerows(rows)

    with open(EXCLUDED_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["committer_id", "commit_count", "matched_domains"])
        for cid in sorted(excluded_committers, key=lambda c: -committer_commits[c]):
            writer.writerow([cid, committer_commits[cid], "; ".join(excluded_committers[cid])])

    print(f"\nWritten:")
    print(f"  Clean:    {OUTPUT_CSV} ({kept_count:,} rows)")
    print(f"  Excluded: {EXCLUDED_CSV} ({len(excluded_committers):,} committers)")


if __name__ == "__main__":
    main()
