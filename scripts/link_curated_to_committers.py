"""
Second-pass linker: anchor curated rows (sources=curated_onther_roster_2019_2023)
to real committer rows in identity_map where possible.

Primary key is the committer_id (github_username / emails) from the commits
dataset. When a curated person has a known committer row, we merge the Korean
name and vault_short into the existing row and drop the standalone curated row.

Dry-run by default. Pass --apply to write.
"""
from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
IDENTITY_MAP = REPO / "data" / "tokamak_member_identity_map.csv"
COMMITTER_PROFILES = REPO / "data" / "committer_profiles_clean.csv"

# (github_username of committer row, curated nickname, korean name to stamp)
# Only add pairs where evidence is strong.
EXPLICIT_LINKS: list[tuple[str, str, str]] = [
    # kyle-heo @ leinger@gmail.com, 27 commits 2022, Seoul → 허복재 Kyle 2022
    ("kyle-heo", "Kyle", "허복재"),
    # shlee-lab @ yale9870@gmail.com, 55 commits 2023 Randomness-Beacon → 이수현
    # (vault "Suhyeon" = 이수현 Lee Suhyeon, confirmed by user 2026-04-23)
    ("shlee-lab", "shlee-lab", "이수현"),
]


def norm(s: str) -> str:
    return (s or "").strip().lower()


def load_csv(path: Path):
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames or []


def index_by(rows: list[dict], field: str) -> dict[str, int]:
    return {norm(r.get(field, "")): i for i, r in enumerate(rows) if r.get(field)}


def find_candidates(curated_rows: list[dict], committer_rows: list[dict]) -> list[dict]:
    """For each curated row (nickname only, no committer row yet), look for
    plausible committer_ids by nickname or Korean-name tokens."""
    out = []
    for cur in curated_rows:
        nick = norm(cur["real_name_en"])
        kr = cur["real_name_kr"].strip()
        cand = []
        for c in committer_rows:
            cid = c["committer_id"]
            if nick and (norm(cid) == nick or nick in norm(cid)):
                cand.append(c)
                continue
            if kr and kr in cid:
                cand.append(c)
        if cand:
            out.append({"curated": cur, "candidates": cand})
    return out


def main(apply: bool) -> int:
    idmap, fieldnames = load_csv(IDENTITY_MAP)
    committers, _ = load_csv(COMMITTER_PROFILES)

    gh_index = index_by(idmap, "github_username")

    curated_rows = [r for r in idmap if r.get("name_source") == "curated_onther_roster_2019_2023"]
    print(f"Curated-sourced rows in identity_map: {len(curated_rows)}")

    # 1) Apply explicit links ------------------------------------------------
    merges = []
    for gh, nick, kr in EXPLICIT_LINKS:
        committer_idx = gh_index.get(norm(gh))
        if committer_idx is None:
            print(f"  [skip] committer row {gh!r} not found in identity_map")
            continue
        # Find the curated row to drop
        cur_idx = None
        for i, r in enumerate(idmap):
            if (r.get("name_source") == "curated_onther_roster_2019_2023"
                and norm(r.get("real_name_en")) == norm(nick)
                and r.get("real_name_kr", "").strip() == kr):
                cur_idx = i
                break
        if cur_idx is None:
            print(f"  [skip] no curated row for ({gh}, {nick}, {kr})")
            continue
        merges.append((committer_idx, cur_idx, gh, nick, kr))

    print()
    print("=== Explicit committer links (merge + drop curated row) ===")
    for c_i, cur_i, gh, nick, kr in merges:
        c = idmap[c_i]
        print(f"  merge curated#{cur_i} ({nick}/{kr}) INTO committer#{c_i} [{gh}]")
        print(f"      before: tier={c['tier_final']} kr={c['real_name_kr']!r} vault={c['vault_short_name']!r}")
        print(f"      after : tier=A_confirmed kr={kr!r} vault={nick!r}")

    # 2) Fuzzy candidates for remaining curated rows -------------------------
    remaining = [
        r for r in curated_rows
        if not any(norm(r.get("real_name_en")) == norm(m[3])
                   and r.get("real_name_kr", "").strip() == m[4]
                   for m in merges)
    ]

    print()
    print(f"=== Fuzzy committer suggestions for {len(remaining)} remaining curated rows ===")
    for r in remaining:
        nick = r["real_name_en"]
        kr = r["real_name_kr"]
        cand = []
        for c in committers:
            cid = c["committer_id"]
            ncid = norm(cid)
            if nick and ncid == norm(nick):
                cand.append((c, "exact-nickname"))
            elif nick and norm(nick) in ncid:
                cand.append((c, "nickname-substring"))
            elif kr and kr in cid:
                cand.append((c, "korean-in-id"))
        cand = cand[:5]
        label = f"{kr}/{nick}"
        if not cand:
            print(f"  {label}: no plausible committer_id. (never committed under this name.)")
        else:
            print(f"  {label}:")
            for c, how in cand:
                print(f"     [{how}] {c['committer_id']} — {c['total_commits']}commits {c['first_date']}~{c['last_date']} emails={c['emails']}")

    if not apply:
        print()
        print("(dry-run: nothing written. Rerun with --apply to commit explicit merges.)")
        return 0

    # APPLY -------------------------------------------------------------------
    backup = IDENTITY_MAP.with_suffix(".csv.bak2")
    shutil.copy2(IDENTITY_MAP, backup)
    print(f"Backup saved: {backup}")

    drop_indices = set()
    for c_i, cur_i, gh, nick, kr in merges:
        c = idmap[c_i]
        if not c["real_name_kr"].strip():
            c["real_name_kr"] = kr
        if not c["vault_short_name"].strip():
            c["vault_short_name"] = nick
        c["tier_final"] = "A_confirmed"
        note = c.get("name_source", "")
        c["name_source"] = (note + "+curated" if note else "curated_onther_roster_2019_2023")
        drop_indices.add(cur_i)

    kept = [r for i, r in enumerate(idmap) if i not in drop_indices]
    with IDENTITY_MAP.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)

    print(f"Merged {len(merges)} pair(s). Rows: {len(idmap)} → {len(kept)}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    sys.exit(main(ap.parse_args().apply))
