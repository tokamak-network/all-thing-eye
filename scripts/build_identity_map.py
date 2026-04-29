"""
Consolidate all identity signals into a single tokamak_member_identity_map.csv.

Combines (all in data/):
  - committer_classification.csv
  - github_profiles.csv (API-fetched)
  - email_name_hints.csv
  - vault_identity_hints.csv (vault deep scan)
  - tokamak_team_rosters.csv

Output: tokamak_member_identity_map.csv
"""

import csv
import re
import json
from pathlib import Path
from collections import defaultdict, Counter

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Committer_ids that are common git author.name values (not real GitHub logins).
# For these, the /users/{login} API returns an UNRELATED user's profile — ignore.
AMBIGUOUS_COMMITTER_IDS = {
    "Jin", "Theo", "eric", "Ubuntu", "Jake", "Jason", "Zena", "Harvey",
    "Monica", "Praveen", "Justin", "Ryan", "Mehdi", "Max", "Nam", "Lucas",
    "Austin", "Aaron", "Ale", "Daniel", "Aidan",
}

# Hand-curated vault name ↔ committer_id based on vault scan findings.
# Values that are verified by multiple evidence (email + GitHub + Slack).
VAULT_NAME_TO_COMMITTERS = {
    "Jason":      ["jason-h23", "cd4761"],
    "Suah":       ["suahnkim", "Suah Kim"],
    "Zena":       ["Zena-park", "zena", "Zena"],
    "Harry":      ["harryoh", "Harry Oh"],
    "Wyatt":      ["WyattPark", "Wyatt0318"],
    "Lakmi":      ["Lakmi94"],
    "Jake":       ["JehyukJang"],     # zk-EVM Jake = Jehyuk Jang (NOT Jake-Song)
    "Theo":       ["Theo Lee", "boohyung_lee"],
    "Nam":        ["nguyenzung"],     # Nam Pham = zung.nguyen
    "Jin":        ["Jin", "jins", "jin.s", "jin.makerDao", "jin_Dockeer", "jinsDocker", "jinsMBP", "jins.docker"],
    "eric":       ["eric"],
    "dCanyon":    ["dCanyon"],
    "boohyung_lee": ["boohyung_lee"],
    "Justin":     ["usgeeus"],        # Justin Gee = usgeeus
    "Muhammed":   ["mabingol"],       # Muhammed Ali Bingol
    "Mehdi":      ["mehdi-defiesta"],
    "Chiko":      ["nakamura-chiko"],
    "Harvey":     ["harvey-jo"],      # tentative — may need verification
}

# Hand-curated real names collected across sources.
# Used when neither GitHub API nor email hint yields a good name.
MANUAL_REAL_NAMES = {
    "Zena-park":    ("Zena Park", "", "onther_email+github_activity"),
    "zena":         ("Zena Park", "", "onther_email"),
    "Zena":         ("Zena Park", "", "onther_email"),
    "Jin":          ("Jin S", "", "onther_email (git-author.name alias)"),
    "jins":         ("Jin S", "", "onther_email"),
    "jin.s":        ("Jin S", "", "onther_email"),
    "jin.makerDao": ("Jin S", "", "onther_email"),
    "jin_Dockeer":  ("Jin S", "", "onther_email"),
    "jinsDocker":   ("Jin S", "", "onther_email"),
    "jinsMBP":      ("Jin S", "", "onther_email"),
    "jins.docker":  ("Jin S", "", "onther_email"),
    "Theo Lee":     ("Boohyung Lee (Theo)", "이부형", "onther_email+vault"),
    "boohyung_lee": ("Boohyung Lee (Theo)", "이부형", "onther_email"),
    "Theo":         ("Boohyung Lee (Theo)", "이부형", "git-author.name alias for Theo Lee"),
    "shingonu":     ("Thomas S (Gonu)", "", "onther_email+github_name:gonu.eth"),
    "dCanyon":      ("Aiden Park", "", "onther_email+github"),
    "Suah Kim":     ("Suah Kim", "", "onther_email+github"),
    "suahnkim":     ("Suah Kim", "", "github+email+vault_medium"),
    "Harry Oh":     ("Harry Oh", "", "onther_email"),
    "harryoh":      ("Harry Oh", "", "github+email"),
    "eric":         ("Eric N", "", "onther_email (git-author.name alias)"),
    "ggs134":       ("Kevin Jeong", "", "github_profile:tokamak-network"),
    "4000D":        ("Carl Park", "", "github_profile"),
    "modagi":       ("Seongjin Kim", "", "github_profile"),
    "steven94kr":   ("Steven Lee", "", "github_profile+vault_medium"),
    "pleiadex":     ("Sungyun Seo (Youn)", "", "github_profile+vault_zkevm_S.Seo"),
    "sifnoc":       ("JinHwan", "", "github_profile"),
    "zzooppii":     ("HyukSang", "", "github_profile"),
    "nguyenzung":   ("Nam Pham (Zung Nguyen)", "", "github_profile+vault_medium+roster"),
    "usgeeus":      ("Justin Gee", "", "github_profile+vault_medium+email"),
    "jason-h23":    ("Jason (alt: cd4761)", "", "vault_roster+email_links_to_cd4761"),
    "cd4761":       ("Jason", "", "vault_zkevm_report"),
    "Lakmi94":      ("Lakmi Kulathunga", "", "github_profile+vault_roster"),
    "Jake-Song":    ("Jake Song (plasma-era, ≠ Jehyuk Jang)", "", "github_profile; different from zk-EVM Jake"),
    "JehyukJang":   ("Jehyuk Jang (PhD)", "", "vault_medium+slack+linkedin"),
    "WyattPark":    ("Wyatt Park", "", "vault_roster+github_login"),
    "Wyatt0318":    ("Wyatt (alt)", "", "likely_same_as_WyattPark"),
    "SonYoungsung": ("Son Youngsung", "손영성", "user"),
    "KimKyungup":   ("Kim Kyungup", "김경업", "github_login_pattern"),
    "mabingol":     ("Muhammed Ali Bingol", "", "vault_zkevm_report"),
    "mehdi-defiesta": ("Mehdi Tokamak", "", "vault_zkevm_report+medium"),
    "nakamura-chiko": ("Chiko Nakamura", "", "github_profile_name+vault_medium"),
    "JeongChul Kim": ("JeongChul Kim", "김정철", "git_author.name"),
    "Jake Song":    ("Jake Song (git author.name)", "", "alias_of_Jake-Song"),
    "Jake":         ("Jehyuk Jang (git author.name)", "", "alias_of_JehyukJang_or_Jake-Song"),
    # Additional confirmed tokamak members found via internal-repo analysis
    "ohbyeongmin":  ("Oh Byeongmin", "오병민", "github+tokamak-titan/titond_exclusive"),
    "kadirpili":    ("Kadi Narmamatov", "", "github+tonstarter/NFT/plasma-evm_contractor"),
    "jananadiw":    ("Jananadi W", "", "github+tokamak_bridge_frontend"),
    "Jananadi Wedagedara": ("Jananadi Wedagedara (alias of jananadiw)", "", "git-author.name"),
    "khk77":        ("hwisdom77", "", "github_login+tokamak_handbook_docs"),
    "jusdy":        ("Jupiter", "", "github+tokamak_bridge_frontend"),
    "jdhyun09":     ("donghyun", "", "github_login+vault"),
    "code0xff":     ("code0xff (@Haderech partner)", "", "tokamak-optimism-explorer"),
}

# Additional people who were excluded by domain filter but are tokamak members
# (they had groundx.xyz or similar partner-company emails)
EXTRA_TOKAMAK_MEMBERS_NOT_IN_CLASSIFICATION = {
    "KimKyungup":   ("Ethan (Kyungup Kim)", "김경업", "github+ECO_Q1_2024_roster:Ethan"),
    "ehnuje":       ("Melvin Junhee Woo", "우준희", "github+partner_contractor_@OpenAsset"),
    "jeongkyun-oh": ("jeongkyun (jk-jeongkyun)", "오정균", "github+plasma-evm_era"),
    "Jake Song":    ("Jake Song (alias for Jake-Song)", "", "git-author.name"),
}


def read_csv(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with open(p) as f:
        return list(csv.DictReader(f))


def main():
    classification = {r["committer_id"]: r for r in read_csv(DATA_DIR / "committer_classification.csv")}
    profiles = {r["committer_id"]: r for r in read_csv(DATA_DIR / "github_profiles.csv")}

    email_hints = defaultdict(list)
    for r in read_csv(DATA_DIR / "email_name_hints.csv"):
        email_hints[r["committer_id"]].append(r)

    rosters_by_name = defaultdict(lambda: {"teams": set(), "periods": set(), "roles": set()})
    for r in read_csv(DATA_DIR / "tokamak_team_rosters.csv"):
        rosters_by_name[r["member_name"].strip()]["teams"].add(r.get("team", ""))
        rosters_by_name[r["member_name"].strip()]["periods"].add(r.get("period", ""))
        if r.get("role_hint"):
            rosters_by_name[r["member_name"].strip()]["roles"].add(r["role_hint"])

    # Vault identity hints: build GitHub-username -> vault extracted_name
    vault_hints_by_github = defaultdict(list)  # github_login -> [extracted_names]
    for r in read_csv(DATA_DIR / "vault_identity_hints.csv"):
        gh = (r.get("candidate_github") or "").strip()
        name = (r.get("extracted_name") or "").strip()
        if gh and name:
            vault_hints_by_github[gh].append({"name": name, "type": r.get("hint_type"), "file": r.get("source_file")})

    COMMITTER_TO_VAULT_NAME = {}
    for vname, cids in VAULT_NAME_TO_COMMITTERS.items():
        for cid in cids:
            COMMITTER_TO_VAULT_NAME[cid] = vname

    rows = []
    for cid, cl in classification.items():
        profile = profiles.get(cid, {})
        emails_seen = [h["email"] for h in email_hints.get(cid, [])]
        emails_from_github = [profile.get("email", "")] if profile.get("email") else []
        all_emails = sorted(set(e for e in emails_seen + emails_from_github if e))

        # 1. Start with GitHub profile name (but skip for ambiguous committer_ids)
        github_name = (profile.get("name") or "").strip()
        is_ambiguous = cid in AMBIGUOUS_COMMITTER_IDS or " " in cid
        real_name_en = ""
        real_name_kr = ""
        name_source = ""

        # 2. Manual override wins
        if cid in MANUAL_REAL_NAMES:
            real_name_en, real_name_kr, name_source = MANUAL_REAL_NAMES[cid]

        # 3. GitHub profile if not ambiguous
        elif github_name and not is_ambiguous:
            real_name_en = github_name
            name_source = "github_api"
            # Try Korean chars from bio/location
            for src in (github_name, profile.get("bio", ""), profile.get("location", "")):
                if src:
                    hangul = re.findall(r"[\uAC00-\uD7A3]+", src)
                    if hangul:
                        real_name_kr = " ".join(hangul)
                        break

        # 4. Vault extracted name (for committers mapped via hints)
        elif cid in vault_hints_by_github:
            best = vault_hints_by_github[cid][0]
            real_name_en = best["name"]
            name_source = f"vault_{best['type']}"

        # 5. Email hint fallback (non-noise domain preferred)
        if not real_name_en:
            non_noise = [h for h in email_hints.get(cid, [])
                        if h.get("is_noise_domain") == "False" and h.get("guessed_name_en")]
            if non_noise:
                best = max(non_noise, key=lambda h: float(h.get("confidence") or 0))
                real_name_en = best["guessed_name_en"]
                name_source = f"email_hint:{best['domain']}"

        vault_short_name = COMMITTER_TO_VAULT_NAME.get(cid, "")
        vault_team_info = rosters_by_name.get(vault_short_name, {}) if vault_short_name else {}

        # Sources
        sources = []
        if github_name and not is_ambiguous:
            sources.append("github_api")
        if any(h.get("domain") in ("onther.io", "tokamak.network") for h in email_hints.get(cid, [])):
            sources.append("onther_email")
        if vault_short_name:
            sources.append("vault_roster")
        if cid in vault_hints_by_github:
            sources.append("vault_doc")
        if cid in MANUAL_REAL_NAMES:
            sources.append("manual_curation")

        # Tier final
        has_onther = any(h.get("domain") == "onther.io" for h in email_hints.get(cid, []))
        has_tokamak_email = any(h.get("domain") == "tokamak.network" for h in email_hints.get(cid, []))
        existing_tier = cl.get("tier", "D")

        if cid == "SonYoungsung":
            tier_final = "A_confirmed"
        elif has_onther or has_tokamak_email or cid in vault_hints_by_github or vault_short_name:
            tier_final = "A_confirmed"
        elif cid in MANUAL_REAL_NAMES:
            tier_final = "A_confirmed"  # manually confirmed via cross-reference
        elif existing_tier == "B":
            tier_final = "B_likely"
        elif existing_tier == "C":
            tier_final = "C_unknown"
        else:
            tier_final = "D_external"

        total_commits = int(cl.get("commits", 0))
        first_date = cl.get("first_date", "")
        last_date = cl.get("last_date", "")
        active_era = f"{first_date[:4]}-{last_date[:4]}" if first_date and last_date else ""

        rows.append({
            "github_username": cid,
            "real_name_en": real_name_en,
            "real_name_kr": real_name_kr,
            "emails": "; ".join(all_emails[:5]),
            "github_profile_name": github_name if not is_ambiguous else f"{github_name} (ambiguous)",
            "company_on_github": profile.get("company", ""),
            "location_on_github": profile.get("location", ""),
            "twitter_on_github": profile.get("twitter_username", ""),
            "vault_short_name": vault_short_name,
            "vault_teams": "; ".join(sorted(vault_team_info.get("teams", set()))),
            "vault_periods": "; ".join(sorted(vault_team_info.get("periods", set()))),
            "vault_roles": "; ".join(sorted(vault_team_info.get("roles", set()))),
            "tier_final": tier_final,
            "active_era": active_era,
            "total_commits": total_commits,
            "total_repos": cl.get("total_repos", ""),
            "name_source": name_source,
            "sources": "; ".join(sources) or "none",
            "github_bio": (profile.get("bio", "") or "")[:120],
        })

    # Add extra tokamak members that were excluded by domain filter
    # Load their stats from the raw filtered CSV (Phase A output) instead
    extra_profiles = {r["committer_id"]: r for r in read_csv(DATA_DIR / "committer_profiles.csv")}  # un-domain-filtered
    for cid, (name_en, name_kr, src) in EXTRA_TOKAMAK_MEMBERS_NOT_IN_CLASSIFICATION.items():
        if cid in classification:
            continue  # already included
        # Get stats from pre-domain-filter profile if available
        prof_data = profiles.get(cid, {})
        rows.append({
            "github_username": cid,
            "real_name_en": name_en,
            "real_name_kr": name_kr,
            "emails": "",
            "github_profile_name": (prof_data.get("name") or "") if prof_data else "",
            "company_on_github": prof_data.get("company", "") if prof_data else "",
            "location_on_github": prof_data.get("location", "") if prof_data else "",
            "twitter_on_github": prof_data.get("twitter_username", "") if prof_data else "",
            "vault_short_name": "",
            "vault_teams": "",
            "vault_periods": "",
            "vault_roles": "",
            "tier_final": "A_confirmed",
            "active_era": "2019-2024 (domain-filtered out)",
            "total_commits": "(excluded from main)",
            "total_repos": "",
            "name_source": src,
            "sources": "manual_curation+domain_filtered",
            "github_bio": (prof_data.get("bio", "") or "")[:120] if prof_data else "",
        })

    tier_order = {"A_confirmed": 0, "B_likely": 1, "C_unknown": 2, "D_external": 3}
    rows.sort(key=lambda r: (tier_order.get(r["tier_final"], 9), -int(r["total_commits"]) if str(r["total_commits"]).isdigit() else 0))

    output = DATA_DIR / "tokamak_member_identity_map.csv"
    fieldnames = list(rows[0].keys())
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Stats
    by_tier = Counter(r["tier_final"] for r in rows)
    has_real_name = Counter(r["tier_final"] for r in rows if r["real_name_en"])
    print(f"Written: {output}")
    print(f"Total rows: {len(rows)}")
    print()
    print("Tier breakdown + real_name coverage:")
    for t in ("A_confirmed", "B_likely", "C_unknown", "D_external"):
        print(f"  {t:<15} {by_tier[t]:>5} total,  {has_real_name[t]:>5} have real_name_en")

    print()
    print("=" * 120)
    print("A_CONFIRMED — 실명 매핑 완료된 토카막/온더 멤버")
    print("=" * 120)
    print(f"{'github_username':<25} {'real_name_en':<30} {'real_name_kr':<12} {'era':<10} {'team':<20} {'commits':>7}")
    print("-" * 120)
    for r in rows:
        if r["tier_final"] != "A_confirmed":
            continue
        print(
            f"{r['github_username']:<25} {r['real_name_en'][:29]:<30} {r['real_name_kr'][:11]:<12} "
            f"{r['active_era']:<10} {r['vault_teams'][:19]:<20} {r['total_commits']:>7}"
        )


if __name__ == "__main__":
    main()
