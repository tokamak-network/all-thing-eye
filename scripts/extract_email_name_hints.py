"""
Extract real-name hints from committer emails.

Parses email local parts (before @) with patterns like:
  firstname.lastname@  -> "Firstname Lastname"
  first_last@          -> same
  firstname@           -> "Firstname" (weak)
  firstnameYY@         -> strip trailing digits
  name123.email@       -> first segment

Also extracts Korean names if present.

Input:  data/committer_profiles_clean.csv
Output: data/email_name_hints.csv
"""

import csv
import re
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INPUT = DATA_DIR / "committer_profiles_clean.csv"
OUTPUT = DATA_DIR / "email_name_hints.csv"

NOISE_DOMAINS = {
    "users.noreply.github.com",
    "gmail.com",
    "naver.com",
    "hanmail.net",
    "daum.net",
    "hotmail.com",
    "outlook.com",
    "yahoo.com",
    "icloud.com",
    "proton.me",
    "protonmail.com",
    "localhost",
}


def extract_name_from_local(local: str) -> tuple[str, float]:
    """Return (guessed_name, confidence 0-1)."""
    if not local:
        return "", 0
    # Strip trailing digits
    m = re.match(r"^([A-Za-z._-]+?)([0-9]*)$", local)
    if m:
        base = m.group(1)
    else:
        base = local

    # Replace separators with space
    parts = re.split(r"[._-]+", base)
    parts = [p for p in parts if p and len(p) > 1]
    if not parts:
        return "", 0

    if len(parts) == 1:
        # Single word
        name = parts[0].capitalize()
        # Low confidence if short
        return name, 0.3 if len(name) <= 4 else 0.5
    elif len(parts) >= 2:
        # firstname.lastname pattern
        name = " ".join(p.capitalize() for p in parts[:2])
        return name, 0.7
    return "", 0


def extract_korean_chars(text: str) -> str:
    """Return any Hangul characters found."""
    hangul = re.findall(r"[\uAC00-\uD7A3]+", text)
    return " ".join(hangul)


def main():
    hints = []
    with open(INPUT) as f:
        for row in csv.DictReader(f):
            cid = row["committer_id"]
            emails = (row.get("emails") or "").split(";")
            emails = [e.strip().lower() for e in emails if e.strip()]
            for email in emails:
                if "@" not in email:
                    continue
                local, domain = email.split("@", 1)
                is_noise = domain in NOISE_DOMAINS
                name, conf = extract_name_from_local(local)
                korean = extract_korean_chars(local)
                hints.append({
                    "committer_id": cid,
                    "email": email,
                    "local_part": local,
                    "domain": domain,
                    "guessed_name_en": name,
                    "guessed_korean": korean,
                    "confidence": round(conf, 2),
                    "is_noise_domain": is_noise,
                    "total_commits": row.get("total_commits", ""),
                })

    # Write
    fieldnames = list(hints[0].keys())
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(hints)

    # Stats
    by_cid = defaultdict(list)
    for h in hints:
        by_cid[h["committer_id"]].append(h)

    high_conf = [h for h in hints if h["confidence"] >= 0.5]
    print(f"Written: {OUTPUT} ({len(hints)} email rows)")
    print(f"Unique committers: {len(by_cid)}")
    print(f"High-confidence name hints: {len(high_conf)}")
    print()
    print("Sample high-confidence hints (non-noise domains first):")
    non_noise = [h for h in high_conf if not h["is_noise_domain"]]
    for h in non_noise[:30]:
        print(f"  {h['committer_id']:<25} <- {h['email']:<50} => '{h['guessed_name_en']}'  conf={h['confidence']}")


if __name__ == "__main__":
    main()
