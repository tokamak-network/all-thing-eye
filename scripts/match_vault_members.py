"""
Extract GitHub usernames for known tokamak team members from the Obsidian vault,
then cross-match with committer_classification.csv.

For each personal progress-report folder, we scan all .md files for:
  - github.com/USERNAME/* links (filtered to exclude known orgs/upstreams)
  - email addresses

Then for each (team_member_name, extracted_username_candidates), we check:
  - Is that username present in the CSV committer list?
  - What's its current Tier?

Output: data/vault_member_matches.csv

Usage:
    python scripts/match_vault_members.py
"""

import csv
import re
import sys
from pathlib import Path
from collections import defaultdict

VAULT_ROOT = Path("/Users/son-yeongseong/Desktop/obsidian/Tokamak Network/Migration from Notion")
ZK_EVM_FOLDER = VAULT_ROOT / "OOO Tokamak zk-EVM/Archive Personal progress reports"
TRH_FOLDER = VAULT_ROOT / "TRH/TRH Tokamak Rollup Hub"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CLASSIFICATION_CSV = DATA_DIR / "committer_classification.csv"
OUTPUT_CSV = DATA_DIR / "vault_member_matches.csv"

# zk-EVM team members (current + previous)
ZK_EVM_MEMBERS = {
    "current": ["Mehdi", "Monica", "Ale", "Aamir", "Jake"],
    "previous": ["Daniel", "Kyros", "Mohammad", "Dragan", "Jason", "Jeff", "Luca", "Nil", "Muhammed"],
}

# TRH team members (from team-structure.md)
TRH_MEMBERS = ["Praveen", "Max", "Lucas", "Theo", "Victor", "Nam"]

# GitHub orgs/upstreams that are NOT personal usernames
KNOWN_ORGS = {
    "tokamak-network", "onther-tech", "Onther-Tech",
    "ethereum", "ethereum-optimism", "ethereumjs", "ethereum-attestation-service",
    "openzeppelin", "OpenZeppelin",
    "ingonyama-zk", "0xPolygonHermez", "Consensys", "matter-labs", "scroll-tech",
    "zkonduit", "lambdaclass", "DelphinusLab", "Foodchain1028", "FoodChain1028",
    "ringcentral", "web3", "leapdao", "MetaMask", "NomicFoundation",
    "ethpandaops", "snapshot-labs", "safe-fndn",
    "l2beat", "mpashkovskiy", "cubedro", "puppeth", "arminvoid", "bayram98",
    "Shivansh070707", "cryptoecc", "gochain", "MyEtherWallet", "cryptocopycats",
    "haderech", "eth-infinitism", "anomalyco", "wildmouse", "trustwallet",
    "jdhyun09", "machulav", "kobigurk",
    "uniswap", "Uniswap", "usgeeus",
    "modagi",
    "graphprotocol", "edgeandnode",
    "blockscout-labs", "blockscout",
    # Tokamak individual tokens we already know as internal members but not own org
    # Zena-park, shingonu, etc. — don't exclude, they might appear as personal linked repos
}

# Regex patterns
GITHUB_USER_RE = re.compile(r"github\.com/([A-Za-z0-9][A-Za-z0-9_-]*)(?:/|$|\s|\))")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def scan_folder_for_signals(folder: Path) -> tuple[set[str], set[str]]:
    """Return (github_usernames, emails) found in any .md under folder."""
    usernames = set()
    emails = set()
    if not folder.exists():
        return usernames, emails
    for md in folder.rglob("*.md"):
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in GITHUB_USER_RE.finditer(text):
            u = m.group(1)
            if u.lower() in {o.lower() for o in KNOWN_ORGS}:
                continue
            if u.lower() in {"settings", "search", "about", "features", "pricing"}:
                continue
            usernames.add(u)
        for m in EMAIL_RE.finditer(text):
            emails.add(m.group(0).lower())
    return usernames, emails


def load_classification() -> dict[str, dict]:
    """Return {committer_id: row_dict} for quick lookup."""
    out = {}
    with open(CLASSIFICATION_CSV) as f:
        for row in csv.DictReader(f):
            out[row["committer_id"]] = row
    return out


def main():
    if not ZK_EVM_FOLDER.exists():
        print(f"Vault not found: {ZK_EVM_FOLDER}")
        sys.exit(1)
    if not CLASSIFICATION_CSV.exists():
        print(f"CSV not found: {CLASSIFICATION_CSV}")
        print("Run scripts/classify_committers.py first.")
        sys.exit(1)

    classification = load_classification()
    # lowercase lookup for case-insensitive matching
    classification_lower = {k.lower(): v for k, v in classification.items()}

    results = []

    def scan_member(team: str, status: str, name: str, folder: Path):
        usernames, emails = scan_folder_for_signals(folder)
        # Try to find matches in CSV
        matches = []
        for u in usernames:
            if u in classification:
                matches.append((u, classification[u]))
            elif u.lower() in classification_lower:
                matches.append((classification_lower[u.lower()]["committer_id"], classification_lower[u.lower()]))
        # Also try member name itself (e.g., "Mehdi" as committer_id)
        if name in classification:
            matches.append((name, classification[name]))
        elif name.lower() in classification_lower:
            matches.append((classification_lower[name.lower()]["committer_id"], classification_lower[name.lower()]))
        results.append({
            "team": team,
            "status": status,
            "name": name,
            "folder_exists": folder.exists(),
            "candidate_usernames": "; ".join(sorted(usernames)),
            "emails_seen": "; ".join(sorted(emails)[:5]),
            "csv_matches": "; ".join(sorted({m[0] for m in matches})),
            "matched_tiers": "; ".join(sorted({m[1]["tier"] for m in matches})),
            "matched_commits": "; ".join(sorted({f"{m[0]}({m[1]['commits']})" for m in matches})),
        })

    # zk-EVM members
    for status in ("current", "previous"):
        for name in ZK_EVM_MEMBERS[status]:
            folder = ZK_EVM_FOLDER / name
            scan_member("zk-EVM", status, name, folder)

    # TRH members — folder structure is different
    for name in TRH_MEMBERS:
        scan_member("TRH", "current", name, TRH_FOLDER)

    # Write CSV
    fieldnames = list(results[0].keys())
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # Print report
    print(f"Written: {OUTPUT_CSV}")
    print()
    print(f"{'team':<7} {'status':<8} {'name':<12} {'candidates':<50} {'matches':<30} {'tiers'}")
    print("-" * 140)
    for r in results:
        print(
            f"{r['team']:<7} {r['status']:<8} {r['name']:<12} "
            f"{r['candidate_usernames'][:48]:<50} "
            f"{r['csv_matches'][:28]:<30} "
            f"{r['matched_tiers']}"
        )


if __name__ == "__main__":
    main()
