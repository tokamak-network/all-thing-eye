"""
One-off patch: add missing git-author emails discovered from raw commits for
A_confirmed members whose emails list was incomplete.

Each addition is justified by: same committer_id as an A_confirmed row AND the
email is either a GitHub privacy placeholder, an onther.io/tokamak.network
email, or a company-email of a known internal contractor/partner (per session
docs).
"""
from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
IDMAP = REPO / "data" / "tokamak_member_identity_map.csv"

ADDITIONS: dict[str, list[str]] = {
    "ggs134":       ["kevin.j@onther.io"],
    "Zena-park":    ["75723511+zena-park@users.noreply.github.com"],
    "KimKyungup":   ["ethan.kim@groundx.xyz", "kyungup@gmail.com"],
    "ehnuje":       ["melvin.woo@groundx.xyz"],
    "jeongkyun-oh": [
        "jk.oh@groundx.xyz",
        "45347815+jeongkyun-oh@users.noreply.github.com",
        "jk.oh@krustuniverse.com",
    ],
}


def split_emails(cell: str) -> list[str]:
    return [e.strip() for e in (cell or "").split(";") if e.strip()]


def join_emails(lst: list[str]) -> str:
    return "; ".join(lst)


def main(apply: bool) -> int:
    with IDMAP.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    changed = 0
    for row in rows:
        gh = row.get("github_username", "")
        if gh not in ADDITIONS:
            continue
        current = split_emails(row.get("emails", ""))
        current_lower = {e.lower() for e in current}
        to_add = [e for e in ADDITIONS[gh] if e.lower() not in current_lower]
        if not to_add:
            print(f"  [skip] {gh}: already has all ({current})")
            continue
        print(f"  [update] {gh}:")
        print(f"    before: {current}")
        merged = current + to_add
        print(f"    after:  {merged}")
        row["emails"] = join_emails(merged)
        changed += 1

    print(f"\n{changed} row(s) would be updated.")
    if not apply:
        print("(dry-run: nothing written. Rerun with --apply.)")
        return 0

    backup = IDMAP.with_suffix(".csv.bak3")
    shutil.copy2(IDMAP, backup)
    with IDMAP.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"Backup: {backup}")
    print(f"Wrote {len(rows)} rows to {IDMAP}")
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    sys.exit(main(ap.parse_args().apply))
