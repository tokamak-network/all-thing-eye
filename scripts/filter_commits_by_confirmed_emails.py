"""
Filter tokamak_commits_2019_2023.csv down to commits whose committer_email is
in tokamak_confirmed_emails.csv (the A_confirmed-member email list).

Output: data/tokamak_confirmed_commits.csv, with real_name_kr / real_name_en /
github_username appended next to each commit row so you can read it directly.
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COMMITS = REPO / "data" / "tokamak_commits_2019_2023.csv"
CONFIRMED = REPO / "data" / "tokamak_confirmed_emails.csv"
OUT = REPO / "data" / "tokamak_confirmed_commits.csv"


def main() -> int:
    with CONFIRMED.open(encoding="utf-8") as f:
        confirmed = {r["email"].lower(): r for r in csv.DictReader(f)}

    print(f"Confirmed emails: {len(confirmed)}")

    with COMMITS.open(encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)
        src_fields = reader.fieldnames or []
        out_fields = src_fields + ["real_name_kr", "real_name_en", "member_github_username"]

        total_in = kept = 0
        per_person = Counter()

        with OUT.open("w", encoding="utf-8", newline="") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=out_fields)
            writer.writeheader()
            for c in reader:
                total_in += 1
                e = (c.get("committer_email") or "").strip().lower()
                m = confirmed.get(e)
                if not m:
                    continue
                kept += 1
                c["real_name_kr"] = m.get("real_name_kr", "")
                c["real_name_en"] = m.get("real_name_en", "")
                c["member_github_username"] = m.get("github_username", "")
                writer.writerow(c)
                per_person[m.get("real_name_kr") or m.get("real_name_en") or e] += 1

    print(f"Read {total_in} commits, kept {kept} ({kept/total_in*100:.1f}%)")
    print(f"Wrote {OUT.relative_to(REPO)}")
    print("\nTop 20 by commits:")
    for name, cnt in per_person.most_common(20):
        print(f"  {cnt:>5}  {name}")
    return 0


if __name__ == "__main__":
    main()
