#!/usr/bin/env python3
"""
Inactive Members GitHub Permission Audit

Audits GitHub repository permissions for inactive (resigned) members
in the tokamak-network organization. Reports any admin/write/maintain
access that should be revoked.

Usage:
    # Default table output (audit only)
    python scripts/audit_github_permissions.py

    # JSON output
    python scripts/audit_github_permissions.py --format json

    # Save to file
    python scripts/audit_github_permissions.py --output report.txt

    # Specific member only
    python scripts/audit_github_permissions.py --member "Alice"

    # Include archived repos
    python scripts/audit_github_permissions.py --include-archived

    # Downgrade all admin permissions to write (after audit)
    python scripts/audit_github_permissions.py --downgrade-admin

    # Remove all write/admin/maintain permissions entirely
    python scripts/audit_github_permissions.py --remove-all
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

import pymongo
from src.utils.logger import setup_logger, get_logger

logger = setup_logger("audit-github-permissions")

# GitHub API
GITHUB_API_BASE = "https://api.github.com"
REQUEST_DELAY = 0.3  # seconds between API calls


def get_db():
    """Connect to MongoDB and return database instance."""
    uri = os.getenv("MONGODB_URI")
    database = os.getenv("MONGODB_DATABASE", "ati")

    if not uri:
        logger.error("MONGODB_URI environment variable not set")
        sys.exit(1)

    try:
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        logger.info(f"MongoDB connected: {database}")
        return client[database]
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        sys.exit(1)


def get_inactive_members(db, member_filter=None):
    """
    Get inactive members with their GitHub usernames.

    Returns list of dicts: [{"name": ..., "github_username": ..., "resigned_at": ...}]
    """
    query = {"is_active": False}
    if member_filter:
        query["name"] = {"$regex": member_filter, "$options": "i"}

    members = list(db["members"].find(query, {
        "name": 1, "github_username": 1, "resigned_at": 1
    }))

    results = []
    for member in members:
        name = member["name"]
        github_username = member.get("github_username")

        # Fallback: check member_identifiers collection
        if not github_username:
            ident = db["member_identifiers"].find_one({
                "member_name": name,
                "source": "github",
            })
            if ident:
                github_username = ident.get("identifier_value")

        if github_username:
            results.append({
                "name": name,
                "github_username": github_username,
                "resigned_at": member.get("resigned_at"),
            })
        else:
            logger.warning(f"No GitHub username found for inactive member: {name}")

    return results


def github_request(method, path, token, params=None):
    """
    Make a GitHub API request with retry logic.

    Returns (response, None) on success or (None, error_msg) on failure.
    """
    import requests

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    url = f"{GITHUB_API_BASE}{path}"
    last_error = None

    for attempt in range(3):
        try:
            resp = requests.request(method, url, headers=headers, params=params, timeout=30)

            # Log rate limit info
            remaining = resp.headers.get("X-RateLimit-Remaining")
            if remaining and int(remaining) < 100:
                reset_time = resp.headers.get("X-RateLimit-Reset", "")
                logger.warning(f"Rate limit low: {remaining} remaining (resets at {reset_time})")

            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                reset_ts = int(resp.headers.get("X-RateLimit-Reset", 0))
                reset_dt = datetime.fromtimestamp(reset_ts) if reset_ts else "unknown"
                return None, f"Rate limit exceeded. Resets at {reset_dt}"

            return resp, None

        except requests.exceptions.RequestException as e:
            last_error = str(e)
            if attempt < 2:
                time.sleep(1 * (attempt + 1))

    return None, f"Network error after 3 retries: {last_error}"


def validate_token(token, org):
    """Validate GitHub token and check org access."""
    resp, err = github_request("GET", "/user", token)
    if err:
        logger.error(f"GitHub API error: {err}")
        sys.exit(1)
    if resp.status_code == 401:
        logger.error("GitHub token is invalid or expired")
        sys.exit(1)

    # Check org access
    resp, err = github_request("GET", f"/orgs/{org}", token)
    if err or resp.status_code != 200:
        logger.error(f"Cannot access organization '{org}'. Check token permissions.")
        sys.exit(1)

    logger.info(f"GitHub token validated for org: {org}")


def get_org_repos(token, org, include_archived=False):
    """Get all repositories in the organization."""
    repos = []
    page = 1

    while True:
        params = {"per_page": 100, "page": page, "type": "all"}
        resp, err = github_request("GET", f"/orgs/{org}/repos", token, params=params)

        if err:
            logger.error(f"Failed to fetch repos: {err}")
            break

        if resp.status_code != 200:
            logger.error(f"Failed to fetch repos: {resp.status_code} {resp.text[:200]}")
            break

        batch = resp.json()
        if not batch:
            break

        for repo in batch:
            if not include_archived and repo.get("archived"):
                continue
            repos.append(repo["name"])

        page += 1
        time.sleep(REQUEST_DELAY)

    return repos


def check_org_membership(token, org, username):
    """
    Check if a user is still a member of the organization.

    Returns True if member, False if not.
    """
    resp, err = github_request("GET", f"/orgs/{org}/members/{username}", token)

    if err:
        logger.warning(f"Could not check org membership for {username}: {err}")
        return None  # unknown

    if resp.status_code == 204:
        return True
    elif resp.status_code == 404:
        return False
    else:
        logger.warning(f"Unexpected status checking membership for {username}: {resp.status_code}")
        return None


def check_user_permission(token, org, repo, username):
    """
    Check a user's permission level on a specific repository.

    Returns permission string (admin/write/maintain/read/none) or None on error.
    """
    resp, err = github_request(
        "GET", f"/repos/{org}/{repo}/collaborators/{username}/permission", token
    )

    if err:
        return None

    if resp.status_code == 200:
        data = resp.json()
        return data.get("permission", "none")
    elif resp.status_code == 404:
        return "none"
    else:
        return None


def set_user_permission(token, org, repo, username, permission):
    """
    Set a user's permission level on a specific repository.

    Args:
        permission: "push" (write), "pull" (read), "admin", "maintain", "triage"

    Returns (success: bool, message: str)
    """
    import requests

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    url = f"{GITHUB_API_BASE}/repos/{org}/{repo}/collaborators/{username}"
    resp = requests.put(url, headers=headers, json={"permission": permission}, timeout=30)
    time.sleep(REQUEST_DELAY)

    if resp.status_code in (200, 201, 204):
        return True, "OK"
    else:
        return False, f"{resp.status_code} {resp.text[:100]}"


def remove_collaborator(token, org, repo, username):
    """
    Remove a user as a collaborator from a repository.

    Returns (success: bool, message: str)
    """
    import requests

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    url = f"{GITHUB_API_BASE}/repos/{org}/{repo}/collaborators/{username}"
    resp = requests.delete(url, headers=headers, timeout=30)
    time.sleep(REQUEST_DELAY)

    if resp.status_code in (204, 404):
        return True, "OK"
    else:
        return False, f"{resp.status_code} {resp.text[:100]}"


def format_table_report(org, members_results, scan_date):
    """Format results as a human-readable table report."""
    lines = []
    lines.append("")
    lines.append("=" * 60)
    lines.append("  Inactive Members GitHub Permission Audit")
    lines.append("=" * 60)
    lines.append(f"  Organization: {org}")
    lines.append(f"  Date: {scan_date}")
    lines.append("")

    total_members = len(members_results)
    in_org_count = sum(1 for m in members_results if m["in_org"])
    total_issues = sum(len(m["issues"]) for m in members_results)

    lines.append(f"  Found {total_members} inactive members with GitHub identifiers")
    lines.append("")

    for i, member in enumerate(members_results, 1):
        name = member["name"]
        username = member["github_username"]
        in_org = member["in_org"]

        if in_org is True:
            org_status = "org member: YES"
        elif in_org is False:
            org_status = "org member: NO (already removed)"
        else:
            org_status = "org member: UNKNOWN"

        lines.append(f"  [{i}/{total_members}] {name} ({username}) - {org_status}")

        if member["issues"]:
            for issue in member["issues"]:
                lines.append(f"    ! {issue['repo']}: {issue['permission']}")
        else:
            lines.append(f"    OK No access issues")

        lines.append("")

    lines.append("=" * 60)
    lines.append("  SUMMARY")
    lines.append("=" * 60)
    lines.append(f"  Members scanned: {total_members}")
    lines.append(f"  Members still in org: {in_org_count}")
    lines.append(f"  Permission issues found: {total_issues}")

    if total_issues > 0:
        perm_counts = {}
        for m in members_results:
            for issue in m["issues"]:
                p = issue["permission"]
                perm_counts[p] = perm_counts.get(p, 0) + 1
        detail = ", ".join(f"{k}: {v}" for k, v in sorted(perm_counts.items()))
        lines.append(f"    {detail}")

    lines.append("")

    return "\n".join(lines)


def format_json_report(org, members_results, scan_date):
    """Format results as JSON."""
    total_issues = sum(len(m["issues"]) for m in members_results)

    report = {
        "organization": org,
        "scan_date": scan_date,
        "total_members_scanned": len(members_results),
        "members_still_in_org": sum(1 for m in members_results if m["in_org"]),
        "total_permission_issues": total_issues,
        "members": members_results,
    }

    return json.dumps(report, indent=2, default=str)


def main():
    parser = argparse.ArgumentParser(
        description="Audit GitHub permissions for inactive members"
    )
    parser.add_argument(
        "--format", choices=["table", "json"], default="table",
        help="Output format (default: table)"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Save report to file"
    )
    parser.add_argument(
        "--member", type=str, default=None,
        help="Filter by specific member name (partial match)"
    )
    parser.add_argument(
        "--include-archived", action="store_true",
        help="Include archived repositories in the scan"
    )
    parser.add_argument(
        "--downgrade-admin", action="store_true",
        help="After audit, downgrade all admin permissions to write"
    )
    parser.add_argument(
        "--remove-all", action="store_true",
        help="After audit, remove all dangerous permissions (admin/write/maintain)"
    )
    args = parser.parse_args()

    # Load config
    github_token = os.getenv("GITHUB_TOKEN")
    github_org = os.getenv("GITHUB_ORG", "tokamak-network")

    if not github_token:
        logger.error("GITHUB_TOKEN environment variable not set")
        sys.exit(1)

    # Validate token
    validate_token(github_token, github_org)

    # Connect to MongoDB
    db = get_db()

    # Get inactive members
    inactive_members = get_inactive_members(db, member_filter=args.member)

    if not inactive_members:
        logger.info("No inactive members with GitHub identifiers found.")
        return

    logger.info(f"Found {len(inactive_members)} inactive members with GitHub identifiers")

    # Get org repos
    logger.info("Fetching organization repositories...")
    repos = get_org_repos(github_token, github_org, include_archived=args.include_archived)
    logger.info(f"Found {len(repos)} repositories to scan")

    # Check each member
    members_results = []
    dangerous_permissions = {"admin", "write", "maintain"}

    for i, member in enumerate(inactive_members, 1):
        name = member["name"]
        username = member["github_username"]
        logger.info(f"[{i}/{len(inactive_members)}] Checking {name} ({username})...")

        time.sleep(REQUEST_DELAY)
        in_org = check_org_membership(github_token, github_org, username)

        result = {
            "name": name,
            "github_username": username,
            "resigned_at": member.get("resigned_at"),
            "in_org": in_org,
            "issues": [],
        }

        if in_org is False:
            logger.info(f"  {username} is not in the org, but checking direct repo access...")

        # Scan repos for permissions
        for j, repo in enumerate(repos):
            time.sleep(REQUEST_DELAY)
            permission = check_user_permission(github_token, github_org, repo, username)

            if permission in dangerous_permissions:
                logger.warning(f"  ! {repo}: {permission}")
                result["issues"].append({
                    "repo": repo,
                    "permission": permission,
                })

            # Progress log every 50 repos
            if (j + 1) % 50 == 0:
                logger.info(f"  ... scanned {j + 1}/{len(repos)} repos")

        if not result["issues"]:
            logger.info(f"  No access issues found")

        members_results.append(result)

    # Format output
    scan_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if args.format == "json":
        output = format_json_report(github_org, members_results, scan_date)
    else:
        output = format_table_report(github_org, members_results, scan_date)

    # Output
    print(output)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        logger.info(f"Report saved to {args.output}")

    # Post-audit actions
    if args.downgrade_admin or args.remove_all:
        action_label = "Removing all permissions" if args.remove_all else "Downgrading admin -> write"
        print(f"\n{'=' * 60}")
        print(f"  ACTION: {action_label}")
        print(f"{'=' * 60}\n")

        success_count = 0
        fail_count = 0

        for member in members_results:
            username = member["github_username"]
            for issue in member["issues"]:
                repo = issue["repo"]
                perm = issue["permission"]

                if args.remove_all:
                    ok, msg = remove_collaborator(github_token, github_org, repo, username)
                    action = f"{perm} -> REMOVED"
                elif args.downgrade_admin and perm == "admin":
                    ok, msg = set_user_permission(github_token, github_org, repo, username, "push")
                    action = "admin -> write"
                else:
                    continue

                if ok:
                    print(f"  OK   {username} @ {repo}: {action}")
                    success_count += 1
                else:
                    print(f"  FAIL {username} @ {repo}: {msg}")
                    fail_count += 1

        print(f"\n  Done: {success_count} succeeded, {fail_count} failed\n")


if __name__ == "__main__":
    main()
