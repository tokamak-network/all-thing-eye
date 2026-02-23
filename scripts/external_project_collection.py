#!/usr/bin/env python3
"""
External Project Benchmark Data Collection Script

Collects daily aggregate statistics from external GitHub repositories
and internal Tokamak projects for benchmarking comparison.

Usage:
    # Collect yesterday's data for all registered external projects
    python scripts/external_project_collection.py

    # Collect specific date
    python scripts/external_project_collection.py --date 2026-02-22

    # Collect date range (backfill)
    python scripts/external_project_collection.py --start-date 2026-01-01 --end-date 2026-02-22

    # Collect for a specific repo (one-off, registers if not exists)
    python scripts/external_project_collection.py --repo paradigmxyz/reth --days 7

    # Collect only internal projects
    python scripts/external_project_collection.py --internal-only
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

from src.core.mongo_manager import get_mongo_manager
from src.plugins.external_github_collector import ExternalGitHubCollector

KST = ZoneInfo("Asia/Seoul")


def get_mongo():
    """Initialize MongoDB connection."""
    config = {
        "uri": os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        "database": os.getenv("MONGODB_DATABASE", "all_thing_eye"),
    }
    mongo = get_mongo_manager(config)
    return mongo


def ensure_indexes(db):
    """Ensure required indexes exist."""
    # Compound index on project_benchmarks
    db["project_benchmarks"].create_index(
        [("project_ref", 1), ("date", -1)],
        unique=True,
    )
    # Index on external_projects
    db["external_projects"].create_index("full_name", unique=True)


def register_project(db, collector: ExternalGitHubCollector, owner: str, repo: str) -> bool:
    """Register an external project if not already registered."""
    full_name = f"{owner}/{repo}"
    existing = db["external_projects"].find_one({"full_name": full_name})
    if existing:
        print(f"   Project {full_name} already registered")
        return True

    info = collector.get_repo_info(owner, repo)
    if not info:
        print(f"   Failed to fetch info for {full_name}")
        return False

    now = datetime.now(timezone.utc)
    db["external_projects"].insert_one({
        "owner": info["owner"],
        "repo": info["repo"],
        "full_name": info["full_name"],
        "display_name": info["repo"].replace("-", " ").title(),
        "category": "",
        "is_active": True,
        "stars": info["stars"],
        "language": info["language"],
        "description": info["description"],
        "created_at": now,
        "updated_at": now,
    })
    print(f"   Registered {full_name} ({info['stars']} stars, {info['language']})")
    return True


def collect_external_projects(db, collector: ExternalGitHubCollector, dates: list):
    """Collect daily stats for all active external projects."""
    projects = list(db["external_projects"].find({"is_active": True}))
    if not projects:
        print("   No active external projects found")
        return

    print(f"\n   Collecting data for {len(projects)} external projects over {len(dates)} day(s)")

    for project in projects:
        owner = project["owner"]
        repo = project["repo"]
        full_name = project["full_name"]
        print(f"\n   [{full_name}]")

        for date in dates:
            date_str = date.strftime("%Y-%m-%d")
            # Check if already collected
            existing = db["project_benchmarks"].find_one({
                "project_ref": full_name,
                "date": date_str,
            })
            if existing:
                print(f"      {date_str}: already collected, skipping")
                continue

            stats = collector.collect_daily_stats(owner, repo, date)
            if stats:
                db["project_benchmarks"].update_one(
                    {"project_ref": full_name, "date": date_str},
                    {"$set": stats},
                    upsert=True,
                )
                print(
                    f"      {date_str}: {stats['commits_count']} commits, "
                    f"+{stats['additions']}/-{stats['deletions']}, "
                    f"{stats['prs_opened']} PRs opened, "
                    f"{stats['unique_contributors']} contributors"
                )
            else:
                print(f"      {date_str}: failed to collect")

        # Update stars count
        info = collector.get_repo_info(owner, repo)
        if info:
            db["external_projects"].update_one(
                {"full_name": full_name},
                {"$set": {"stars": info["stars"], "updated_at": datetime.now(timezone.utc)}},
            )


def collect_internal_repos(db, collector: ExternalGitHubCollector, dates: list):
    """Collect daily stats for all non-archived internal repos."""
    repos = list(db["github_repositories"].find(
        {"is_archived": {"$ne": True}},
        {"name": 1, "_id": 0},
    ))
    if not repos:
        print("   No internal repos found")
        return

    repo_names = [r["name"] for r in repos]
    print(f"\n   Collecting data for {len(repo_names)} internal repos over {len(dates)} day(s)")

    for repo_name in repo_names:
        ref = f"internal:{repo_name}"
        collected_any = False

        for date in dates:
            date_str = date.strftime("%Y-%m-%d")
            existing = db["project_benchmarks"].find_one({
                "project_ref": ref,
                "date": date_str,
            })
            if existing:
                continue

            stats = collector.collect_internal_repo_daily_stats(db, repo_name, date)
            if stats and stats["commits_count"] > 0:
                db["project_benchmarks"].update_one(
                    {"project_ref": ref, "date": date_str},
                    {"$set": stats},
                    upsert=True,
                )
                if not collected_any:
                    print(f"\n   [{repo_name}]")
                    collected_any = True
                print(
                    f"      {date_str}: {stats['commits_count']} commits, "
                    f"+{stats['additions']}/-{stats['deletions']}, "
                    f"{stats['unique_contributors']} contributors"
                )


def main():
    parser = argparse.ArgumentParser(description="Collect external project benchmark data")
    parser.add_argument("--date", type=str, help="Specific date (YYYY-MM-DD)")
    parser.add_argument("--start-date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, help="Collect last N days")
    parser.add_argument("--repo", type=str, help="Specific repo (owner/repo), registers if new")
    parser.add_argument("--internal-only", action="store_true", help="Only collect internal projects")
    parser.add_argument("--external-only", action="store_true", help="Only collect external projects")
    args = parser.parse_args()

    print("=" * 60)
    print(f"External Project Benchmark Collection")
    print(f"Started: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')} KST")
    print("=" * 60)

    # Initialize
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        print("GITHUB_TOKEN not set")
        sys.exit(1)

    mongo = get_mongo()
    db = mongo.db
    collector = ExternalGitHubCollector(github_token)

    # Ensure indexes
    ensure_indexes(db)

    # Calculate dates
    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d")
        dates = [target]
    elif args.start_date:
        start = datetime.strptime(args.start_date, "%Y-%m-%d")
        end = datetime.strptime(args.end_date, "%Y-%m-%d") if args.end_date else datetime.now(KST).replace(tzinfo=None)
        dates = []
        current = start
        while current <= end:
            dates.append(current)
            current += timedelta(days=1)
    elif args.days:
        now = datetime.now(KST).replace(tzinfo=None)
        dates = [now - timedelta(days=i) for i in range(args.days, 0, -1)]
    else:
        # Default: yesterday
        yesterday = datetime.now(KST).replace(tzinfo=None) - timedelta(days=1)
        dates = [yesterday]

    print(f"\nDate range: {dates[0].strftime('%Y-%m-%d')} ~ {dates[-1].strftime('%Y-%m-%d')}")
    print(f"Total days: {len(dates)}")

    # Register specific repo if provided
    if args.repo:
        parts = args.repo.split("/")
        if len(parts) != 2:
            print(f"Invalid repo format: {args.repo}. Use owner/repo")
            sys.exit(1)
        owner, repo = parts
        if not register_project(db, collector, owner, repo):
            sys.exit(1)

    try:
        # Collect external projects
        if not args.internal_only:
            collect_external_projects(db, collector, dates)

        # Collect internal projects
        if not args.external_only:
            collect_internal_repos(db, collector, dates)

        print("\n" + "=" * 60)
        print(f"Collection completed: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')} KST")
        print("=" * 60)

    finally:
        mongo.close()


if __name__ == "__main__":
    main()
