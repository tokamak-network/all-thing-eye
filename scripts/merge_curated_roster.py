"""
Merge the manually curated Onther/Tokamak roster (2019-2023 온더 개발자.csv)
into data/tokamak_member_identity_map.csv.

- Dry-run by default: prints proposed updates and new rows, writes nothing.
- Pass --apply to actually write the merged CSV (creates .bak backup).
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CURATED = Path("/Users/son-yeongseong/Downloads/2019-2023 온더 개발자.csv")
IDENTITY_MAP = REPO / "data" / "tokamak_member_identity_map.csv"


def norm(s: str) -> str:
    return (s or "").strip().lower()


def parse_curated(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for r in reader:
            r = r + [""] * (4 - len(r))
            kr, en, uore, period = (c.strip() for c in r[:4])
            if not (kr or en):
                continue
            username, email = "", ""
            if "@" in uore:
                email = uore
            else:
                username = uore
            rows.append({
                "real_name_kr": kr,
                "nickname_en": en,
                "username": username,
                "email": email,
                "active_era": period,
            })
    return rows


def load_identity_map(path: Path) -> tuple[list[dict], list[str]]:
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames or []


def match_curated_row(cur: dict, idmap: list[dict]) -> list[int]:
    """Return indices of identity_map rows plausibly matching this curated person.

    Two-phase strategy to avoid cross-contamination between people with the same
    English nickname (e.g. 송무복 Jake vs 장재혁 Jake):

      Phase 1 (strong): username exact, username-as-substring-in-emails,
                        email substring, korean name exact.
      Phase 2 (alias cluster): if phase 1 returned any hit, expand to other rows
                        whose real_name_en matches any strong-hit row's
                        real_name_en (so A_confirmed alias rows carry the same
                        korean name).
      Phase 3 (fallback nickname): ONLY if phase 1 was empty, match via
                        vault_short_name == nickname or a real_name_en token ==
                        nickname, restricted to A_confirmed tier.
    """
    u_norm = norm(cur["username"])
    e_norm = norm(cur["email"])
    nick = norm(cur["nickname_en"])
    kr = cur["real_name_kr"]

    strong: set[int] = set()
    for i, row in enumerate(idmap):
        gh = norm(row.get("github_username"))
        emails = norm(row.get("emails"))
        real_kr = row.get("real_name_kr", "").strip()

        if u_norm and gh == u_norm:
            strong.add(i); continue
        if u_norm and u_norm in emails:
            strong.add(i); continue
        if e_norm and e_norm in emails:
            strong.add(i); continue
        if kr and real_kr == kr:
            strong.add(i); continue

    if strong:
        cluster_names = {
            norm(idmap[i].get("real_name_en"))
            for i in strong
            if idmap[i].get("real_name_en")
        }
        hits = set(strong)
        for i, row in enumerate(idmap):
            if i in hits:
                continue
            real_en = norm(row.get("real_name_en"))
            if not real_en:
                continue
            # exact real_name_en equality forms the alias cluster
            if real_en in cluster_names:
                hits.add(i)
            # also include alias rows whose real_name_en explicitly references
            # one of the strong-hit usernames (e.g. "alias for Jake-Song").
            # Require explicit "alias for/of" phrasing to avoid substring hits
            # like "theo" ⊂ "theo butler".
            else:
                for s in strong:
                    gh = norm(idmap[s].get("github_username"))
                    if not gh:
                        continue
                    if f"alias for {gh}" in real_en or f"alias of {gh}" in real_en:
                        hits.add(i); break
        return sorted(hits)

    hits: set[int] = set()
    for i, row in enumerate(idmap):
        if row.get("tier_final") != "A_confirmed":
            continue
        real_en = norm(row.get("real_name_en"))
        vault_short = norm(row.get("vault_short_name"))
        if nick and vault_short == nick:
            hits.add(i); continue
        if nick and real_en:
            tokens = re.findall(r"[A-Za-z]+", real_en)
            if any(t.lower() == nick for t in tokens):
                hits.add(i); continue
    return sorted(hits)


def summarize_idrow(row: dict) -> str:
    gh = row.get("github_username", "")
    en = row.get("real_name_en", "")
    kr = row.get("real_name_kr", "")
    tier = row.get("tier_final", "")
    return f"[{tier}] {gh} | en={en!r} kr={kr!r}"


def main(apply: bool) -> int:
    curated = parse_curated(CURATED)
    idmap, fieldnames = load_identity_map(IDENTITY_MAP)

    print(f"Curated: {len(curated)} people")
    print(f"Identity map: {len(idmap)} rows, {len(fieldnames)} columns")
    print()

    plan_updates = []   # (row_index, field_changes_dict, curated_row)
    plan_new = []       # curated rows with no confident match
    plan_ambiguous = [] # curated rows matching multiple identity_map rows

    for cur in curated:
        hits = match_curated_row(cur, idmap)
        if not hits:
            plan_new.append(cur)
            continue

        # Propose setting real_name_kr and nickname_en for all matching rows
        # If there's only one hit we mark a clean update; multiple hits = ambiguous (still updatable)
        changes_per_hit = []
        for i in hits:
            row = idmap[i]
            changes = {}
            if cur["real_name_kr"] and not row.get("real_name_kr", "").strip():
                changes["real_name_kr"] = cur["real_name_kr"]
            # Use nickname as vault_short_name if missing
            if cur["nickname_en"] and not row.get("vault_short_name", "").strip():
                changes["vault_short_name"] = cur["nickname_en"]
            # active_era: fill only if empty
            if cur["active_era"] and not row.get("active_era", "").strip():
                changes["active_era"] = cur["active_era"]
            changes_per_hit.append((i, changes))

        if len(hits) == 1:
            plan_updates.append((hits[0], changes_per_hit[0][1], cur))
        else:
            plan_ambiguous.append((hits, changes_per_hit, cur))

    # Reports ----------------------------------------------------------------
    print(f"=== Section A: single-match updates ({len(plan_updates)}) ===")
    for i, changes, cur in plan_updates:
        row = idmap[i]
        tag = "NO-OP" if not changes else "UPDATE"
        print(f"  [{tag}] cur={cur['real_name_kr']} {cur['nickname_en']} ({cur['username'] or cur['email']})")
        print(f"      ↳ {summarize_idrow(row)}")
        if changes:
            for k, v in changes.items():
                print(f"        + {k}: {row.get(k,'')!r} → {v!r}")
    print()

    print(f"=== Section B: multi-match ambiguous ({len(plan_ambiguous)}) ===")
    for hits, changes_list, cur in plan_ambiguous:
        print(f"  cur={cur['real_name_kr']} {cur['nickname_en']} ({cur['username'] or cur['email']})")
        for (i, changes), hi in zip(changes_list, hits):
            row = idmap[hi]
            print(f"      ↳ {summarize_idrow(row)}")
            if changes:
                for k, v in changes.items():
                    print(f"        + {k}: {row.get(k,'')!r} → {v!r}")
    print()

    print(f"=== Section C: new rows to add ({len(plan_new)}) ===")
    for cur in plan_new:
        print(f"  + {cur['real_name_kr']} / {cur['nickname_en']} / user={cur['username']} / email={cur['email']} / era={cur['active_era']}")
    print()

    if not apply:
        print("(dry-run: nothing written. Rerun with --apply to commit.)")
        return 0

    # APPLY -------------------------------------------------------------------
    backup = IDENTITY_MAP.with_suffix(".csv.bak")
    shutil.copy2(IDENTITY_MAP, backup)
    print(f"Backup saved: {backup}")

    # 1) Apply single-match + ambiguous updates
    for i, changes, _ in plan_updates:
        idmap[i].update(changes)
    for hits, changes_list, _ in plan_ambiguous:
        for (i, changes) in changes_list:
            idmap[i].update(changes)

    # 2) Append new rows
    for cur in plan_new:
        new = {fn: "" for fn in fieldnames}
        new["github_username"] = cur["username"]
        new["real_name_kr"] = cur["real_name_kr"]
        new["real_name_en"] = cur["nickname_en"]
        new["emails"] = cur["email"]
        new["vault_short_name"] = cur["nickname_en"]
        new["tier_final"] = "A_confirmed"
        new["active_era"] = cur["active_era"]
        new["name_source"] = "curated_onther_roster_2019_2023"
        new["sources"] = "manual_curation"
        idmap.append(new)

    with IDENTITY_MAP.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(idmap)

    print(f"Wrote {len(idmap)} rows to {IDENTITY_MAP}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    sys.exit(main(ap.parse_args().apply))
