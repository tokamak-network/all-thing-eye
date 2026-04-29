"""
Build the final tokamak member registry by combining:
  - data/committer_classification.csv (Tier A/B/C/D + domains + repos)
  - data/tokamak_team_rosters.csv (vault rosters: ECO/DRB/SYB/TRH/zk-EVM)
  - data/tokamak_commits_2019_2023_final.csv (Phase B output, post-disguised-fork)

Output: data/tokamak_members_registry.csv
"""

import csv
import re
from pathlib import Path
from collections import defaultdict, Counter

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CLASSIFICATION = DATA_DIR / "committer_classification.csv"
ROSTERS = DATA_DIR / "tokamak_team_rosters.csv"
FINAL_CSV = DATA_DIR / "tokamak_commits_2019_2023_final.csv"
OUTPUT = DATA_DIR / "tokamak_members_registry.csv"

# Explicit high-confidence vault ↔ committer_id mappings.
# These override heuristic matching.
MANUAL_MAP = {
    # vault_name: [committer_ids...]  (one vault person may have multiple GitHub accounts)
    "Jason": ["jason-h23"],
    "Suah": ["suahnkim", "Suah Kim"],
    "Zena": ["Zena-park", "zena", "Zena"],
    "Harry": ["harryoh"],
    "Wyatt": ["WyattPark", "Wyatt0318"],
    "Lakmi": ["Lakmi94"],
    "Jake": ["Jake-Song"],
    "Theo": ["Theo Lee", "Theo"],
    "Nam": ["nguyenzung"],  # Nguyen Zung is Nam
    "Suhyeon": ["eun-her"],  # speculative, leave empty if not confirmed
    "Jin": ["Jin", "jins", "jin.s", "jin.makerDao", "jin_Dockeer", "jinsDocker", "jinsMBP", "jins.docker"],
    "eric": ["eric"],
    "dCanyon": ["dCanyon"],
    "boohyung_lee": ["boohyung_lee"],
}

# Reverse index: committer_id -> vault name
COMMITTER_TO_VAULT_NAME = {}
for vname, cids in MANUAL_MAP.items():
    for cid in cids:
        COMMITTER_TO_VAULT_NAME[cid] = vname


def load_classification():
    rows = {}
    with open(CLASSIFICATION) as f:
        for r in csv.DictReader(f):
            rows[r["committer_id"]] = r
    return rows


def load_rosters():
    """Return {vault_name: {"teams": set, "periods": set, "roles": set}}."""
    d = defaultdict(lambda: {"teams": set(), "periods": set(), "roles": set()})
    with open(ROSTERS) as f:
        for r in csv.DictReader(f):
            name = r["member_name"].strip()
            d[name]["teams"].add(r.get("team", ""))
            d[name]["periods"].add(r.get("period", ""))
            role = r.get("role_hint", "").strip()
            if role:
                d[name]["roles"].add(role)
    return d


def load_final_commits_per_committer():
    counts = Counter()
    if not FINAL_CSV.exists():
        return counts
    with open(FINAL_CSV) as f:
        for r in csv.DictReader(f):
            counts[r["committer_id"]] += 1
    return counts


def determine_source_and_tier(cid: str, classification_row: dict, vault_match: str | None, final_commits: int) -> tuple[str, str]:
    """Return (source, tier_final)."""
    domains = classification_row.get("domains", "")
    orig_tier = classification_row.get("tier", "D")

    has_onther = "onther.io" in domains
    if cid == "SonYoungsung":
        return "user", "A_confirmed"
    if vault_match and has_onther:
        return "onther_email+vault_roster", "A_confirmed"
    if has_onther:
        return "onther_email", "A_confirmed"
    if vault_match:
        return "vault_roster", "A_confirmed"
    if orig_tier == "B":
        return "high_breadth", "B_likely"
    if orig_tier == "C":
        return "medium_breadth", "C_unknown"
    # D
    if "bot" in cid.lower():
        return "bot", "D_external"
    if final_commits == 0:
        return "all_upstream", "D_external"
    return "low_breadth", "D_external"


def determine_era(first_date: str, last_date: str) -> str:
    if not first_date or not last_date:
        return ""
    first_year = int(first_date[:4])
    last_year = int(last_date[:4])
    if first_year <= 2020 and last_year <= 2021:
        return "2019-2020 (plasma/early)"
    if first_year <= 2020:
        return "long-tenure (2019-{})".format(last_year)
    if first_year >= 2022:
        return "2022+ (L2 era)"
    return "2021-2023"


def main():
    classification = load_classification()
    rosters = load_rosters()
    final_counts = load_final_commits_per_committer()

    rows = []
    for cid, cr in classification.items():
        vault_name = COMMITTER_TO_VAULT_NAME.get(cid)
        vault_info = rosters.get(vault_name, {}) if vault_name else {}

        total_commits = int(cr.get("commits", 0))
        final_commits = final_counts.get(cid, 0)
        source, tier_final = determine_source_and_tier(cid, cr, vault_name, final_commits)

        rows.append({
            "committer_id": cid,
            "confirmed_name": vault_name or "",
            "vault_teams": "; ".join(sorted(vault_info.get("teams", set()))) if vault_info else "",
            "vault_periods": "; ".join(sorted(vault_info.get("periods", set()))) if vault_info else "",
            "vault_roles": "; ".join(sorted(vault_info.get("roles", set()))) if vault_info else "",
            "source": source,
            "tier_final": tier_final,
            "total_commits": total_commits,
            "final_commits": final_commits,
            "total_repos": int(cr.get("total_repos", 0)),
            "non_fork_repos": int(cr.get("non_fork_repos", 0)),
            "domains": cr.get("domains", ""),
            "first_date": cr.get("first_date", ""),
            "last_date": cr.get("last_date", ""),
            "era": determine_era(cr.get("first_date", ""), cr.get("last_date", "")),
            "top_repos": cr.get("top_repos", ""),
        })

    # Sort: confirmed names first, then by final_commits desc
    tier_order = {"A_confirmed": 0, "B_likely": 1, "C_unknown": 2, "D_external": 3}
    rows.sort(key=lambda r: (tier_order.get(r["tier_final"], 9), -r["final_commits"]))

    # Write CSV
    fieldnames = list(rows[0].keys())
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Stats
    tier_counts = Counter(r["tier_final"] for r in rows)
    print(f"Written: {OUTPUT}")
    print(f"Total committers: {len(rows)}")
    print()
    print("Tier breakdown:")
    for t in ("A_confirmed", "B_likely", "C_unknown", "D_external"):
        commits_sum = sum(r["final_commits"] for r in rows if r["tier_final"] == t)
        print(f"  {t:<15} {tier_counts.get(t, 0):>5} people, {commits_sum:>7,} final commits")

    print()
    # Find unmapped vault names (vault name but no committer_id)
    mapped_names = set(COMMITTER_TO_VAULT_NAME.values())
    unmapped = [n for n in rosters if n not in mapped_names]
    print(f"Vault names WITHOUT committer match ({len(unmapped)}):")
    for name in sorted(unmapped):
        info = rosters[name]
        teams = "; ".join(sorted(info["teams"]))
        print(f"  {name:15s}  teams={teams}")

    print()
    print("Top 40 Tier A_confirmed + B_likely:")
    print(f"{'name':<20} {'cid':<28} {'src':<25} {'finalC':>6} {'totalC':>6} {'repo':>4} {'era':<25}")
    print("-" * 130)
    for r in rows:
        if r["tier_final"] not in ("A_confirmed", "B_likely"):
            continue
        if r["total_commits"] < 50:
            continue
        name = r["confirmed_name"] or "-"
        print(
            f"{name:<20} {r['committer_id']:<28} {r['source']:<25} "
            f"{r['final_commits']:>6} {r['total_commits']:>6} {r['total_repos']:>4} {r['era']}"
        )


if __name__ == "__main__":
    main()
