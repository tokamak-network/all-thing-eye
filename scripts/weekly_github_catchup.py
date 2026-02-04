#!/usr/bin/env python3
"""
Weekly GitHub Catch-up Script

Re-collects GitHub data for the past 7 days to catch late-pushed commits.

Problem: If someone commits on Monday but pushes on Friday, the daily collector
(which runs at midnight) would miss that commit because it only looks at
"yesterday's" commits based on committedDate.

Solution: Run this script weekly to re-scan the past 7 days and catch any
commits that were pushed later than they were committed.

Usage:
    python scripts/weekly_github_catchup.py
    python scripts/weekly_github_catchup.py --days 14
    python scripts/weekly_github_catchup.py --dry-run

Recommended cron (Sunday 2 AM KST):
    0 2 * * 0 cd /home/ubuntu/all-thing-eye && docker exec all-thing-eye-backend python scripts/weekly_github_catchup.py
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

from src.core.config import Config
from src.core.mongo_manager import get_mongo_manager
from src.plugins.github_plugin_mongo import GitHubPluginMongo
from src.utils.logger import get_logger

logger = get_logger(__name__)
KST = ZoneInfo("Asia/Seoul")


def main():
    parser = argparse.ArgumentParser(
        description="Weekly GitHub catch-up for late-pushed commits"
    )
    parser.add_argument(
        "--days", type=int, default=7, help="Number of days to look back (default: 7)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be collected without actually collecting",
    )
    args = parser.parse_args()

    now_kst = datetime.now(KST)
    end_date = now_kst.replace(hour=23, minute=59, second=59, microsecond=999999)
    start_date = (now_kst - timedelta(days=args.days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    print(f"🔄 Weekly GitHub Catch-up")
    print(
        f"   Period: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')} KST"
    )
    print(f"   Days: {args.days}")
    print()

    if args.dry_run:
        print("🔍 DRY RUN - No data will be collected")
        print(
            f"   Would collect GitHub data from {start_date.isoformat()} to {end_date.isoformat()}"
        )
        return

    config = Config()
    mongo_manager = get_mongo_manager()

    github_config = {
        "token": os.getenv("GITHUB_TOKEN"),
        "organization": config.get("sources.github.organization", "tokamak-network"),
        "collection": config.get("sources.github.collection", {}),
    }

    plugin = GitHubPluginMongo(github_config, mongo_manager)

    if not plugin.authenticate():
        print("❌ GitHub authentication failed")
        sys.exit(1)

    print(f"🚀 Starting GitHub catch-up collection...")
    start_time = datetime.now()

    try:
        result = plugin.collect_data(start_date, end_date)

        duration = datetime.now() - start_time

        print()
        print(f"✅ Catch-up collection completed!")
        print(f"   Duration: {duration}")
        print(f"   Commits: {result.get('commits_count', 0)}")
        print(f"   PRs: {result.get('prs_count', 0)}")
        print(f"   Issues: {result.get('issues_count', 0)}")

    except Exception as e:
        logger.error(f"Error during catch-up collection: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
