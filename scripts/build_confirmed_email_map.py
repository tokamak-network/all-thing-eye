"""
Produce an email-keyed CSV of confirmed Tokamak/Onther members.

One row = one email. Each email is linked to exactly one confirmed member
(real name + committer_id + vault short). Pulls commit stats from
tokamak_commits_2019_2023_final.csv so we can see how active each email was.

Usage:
  python scripts/build_confirmed_email_map.py
    → writes data/tokamak_confirmed_emails.csv (all emails of A_confirmed)
    → writes data/tokamak_confirmed_emails_no_placeholder.csv
      (excludes +user@users.noreply.github.com GitHub privacy placeholders)
  Pass --report to also print conflicts (email mapped to 2+ members).
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
IDENTITY_MAP = REPO / "data" / "tokamak_member_identity_map.csv"
COMMITS = REPO / "data" / "tokamak_commits_2019_2023.csv"

OUT_ALL = REPO / "data" / "tokamak_confirmed_emails.csv"
OUT_NO_PLACEHOLDER = REPO / "data" / "tokamak_confirmed_emails_no_placeholder.csv"


def split_emails(cell: str) -> list[str]:
    if not cell:
        return []
    return [e.strip() for e in cell.split(";") if e.strip()]


def is_privacy_placeholder(email: str) -> bool:
    return email.lower().endswith("@users.noreply.github.com")


def domain_of(email: str) -> str:
    return email.split("@", 1)[1].lower() if "@" in email else ""


def main(report: bool) -> int:
    # 1) Build email→A_confirmed lookup from identity_map ---------------------
    with IDENTITY_MAP.open(encoding="utf-8") as f:
        id_rows = [r for r in csv.DictReader(f) if r["tier_final"] == "A_confirmed"]

    email_to_members: dict[str, list[dict]] = defaultdict(list)
    for row in id_rows:
        for e in split_emails(row.get("emails", "")):
            email_to_members[e.lower()].append(row)

    # 2) Anchor on commits file — iterate every committer_email --------------
    commits_per_email: dict[str, dict] = defaultdict(lambda: {
        "count": 0, "repos": set(), "first": "", "last": "",
        "author_names": set(),
    })
    with COMMITS.open(encoding="utf-8") as f:
        for c in csv.DictReader(f):
            e = (c.get("committer_email") or "").strip().lower()
            if not e:
                continue
            bucket = commits_per_email[e]
            bucket["count"] += 1
            bucket["repos"].add(c.get("repository", ""))
            bucket["author_names"].add(c.get("committer_id", ""))
            d = c.get("commit_date", "")
            if d:
                if not bucket["first"] or d < bucket["first"]:
                    bucket["first"] = d
                if not bucket["last"] or d > bucket["last"]:
                    bucket["last"] = d

    # 3) For each commit email, look up A_confirmed mapping ------------------
    cols = [
        "email", "real_name_kr", "real_name_en", "github_username",
        "vault_short_name", "active_era", "is_privacy_placeholder",
        "commits_in_raw", "repos_in_raw", "first_commit_date", "last_commit_date",
        "git_author_names", "conflict_members",
    ]

    rows_all = []
    conflicts = []
    for email in sorted(commits_per_email.keys()):
        members = email_to_members.get(email, [])
        if not members:
            continue  # email has no A_confirmed mapping → drop
        primary = members[0]
        conflict_names = ""
        distinct_names = {m.get("real_name_en", "") for m in members if m.get("real_name_en")}
        if len(distinct_names) > 1:
            conflict_names = " | ".join(
                f"{m.get('github_username','')}={m.get('real_name_en','')}" for m in members
            )
            conflicts.append((email, conflict_names))

        cstats = commits_per_email[email]
        rows_all.append({
            "email": email,
            "real_name_kr": primary.get("real_name_kr", ""),
            "real_name_en": primary.get("real_name_en", ""),
            "github_username": primary.get("github_username", ""),
            "vault_short_name": primary.get("vault_short_name", ""),
            "active_era": primary.get("active_era", ""),
            "is_privacy_placeholder": is_privacy_placeholder(email),
            "commits_in_raw": cstats["count"],
            "repos_in_raw": len(cstats["repos"]),
            "first_commit_date": cstats["first"],
            "last_commit_date": cstats["last"],
            "git_author_names": "; ".join(sorted(n for n in cstats["author_names"] if n)),
            "conflict_members": conflict_names,
        })

    # Group rows by person so multi-email accounts stay adjacent.
    # Group key: real_name_kr if present, else real_name_en without parenthesised
    # suffix (keeps alias rows like "Jake Song (alias for Jake-Song)" together
    # with "Jake Song (plasma-era, ...)").
    def group_key(r: dict) -> str:
        kr = r["real_name_kr"].strip()
        if kr:
            return kr
        en = r["real_name_en"].strip()
        return en.split("(")[0].strip().lower() or r["github_username"].lower()

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows_all:
        groups[group_key(r)].append(r)

    rows_all = []
    for key in sorted(groups, key=lambda k: (-sum(r["commits_in_raw"] for r in groups[k]), k)):
        members = sorted(groups[key], key=lambda r: (-r["commits_in_raw"], r["email"]))
        rows_all.extend(members)

    with OUT_ALL.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows_all)

    rows_clean = [r for r in rows_all if not r["is_privacy_placeholder"]]
    with OUT_NO_PLACEHOLDER.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows_clean)

    # 4) Summary --------------------------------------------------------------
    total = len(rows_all)
    no_ph = len(rows_clean)
    onther = sum(1 for r in rows_clean if r["email"].endswith("@onther.io"))
    tokamak = sum(1 for r in rows_clean if r["email"].endswith("@tokamak.network"))
    unique_commit_emails = len(commits_per_email)
    unmapped = unique_commit_emails - total

    print(f"A_confirmed rows in identity_map:    {len(id_rows)}")
    print(f"Unique emails in raw commits:        {unique_commit_emails}")
    print(f"  ↳ mapped to A_confirmed:           {total}")
    print(f"  ↳ unmapped (non-member):           {unmapped}")
    print(f"Confirmed emails:                    {total}")
    print(f"  ↳ privacy placeholder (@users.n.): {total - no_ph}")
    print(f"  ↳ real emails after placeholder:   {no_ph}")
    print(f"     · @onther.io:                   {onther}")
    print(f"     · @tokamak.network:             {tokamak}")
    print(f"Wrote:")
    print(f"  {OUT_ALL.relative_to(REPO)}")
    print(f"  {OUT_NO_PLACEHOLDER.relative_to(REPO)}")

    if conflicts:
        print(f"\n⚠️  {len(conflicts)} email(s) map to multiple members with different real_name_en:")
        for e, names in conflicts:
            print(f"  {e} → {names}")

    if report:
        print("\n=== Top 30 (by commit count) ===")
        for r in rows_clean[:30]:
            print(f"  {r['commits_in_raw']:>5}  {r['email']:40s}  kr={r['real_name_kr']!r:>10}  en={r['real_name_en']}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    main(ap.parse_args().report)
