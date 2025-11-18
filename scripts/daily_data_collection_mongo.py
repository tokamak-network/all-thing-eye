#!/usr/bin/env python3
"""
Daily Data Collection Script for MongoDB

Collects data from the previous day (KST timezone).
Should be run daily at midnight KST.

Example:
    - Runs at Friday 00:00:00 KST
    - Collects Thursday's data (00:00:00 ~ 23:59:59 KST)

Usage:
    python scripts/daily_data_collection_mongo.py
    python scripts/daily_data_collection_mongo.py --date 2025-11-17
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.core.config import Config
from src.core.mongo_manager import MongoDBManager, get_mongo_manager
from src.plugins.github_plugin_mongo import GitHubPluginMongo
from src.plugins.slack_plugin_mongo import SlackPluginMongo
from src.plugins.notion_plugin_mongo import NotionPluginMongo
from src.plugins.google_drive_plugin_mongo import GoogleDrivePluginMongo
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Korea Standard Time
KST = ZoneInfo("Asia/Seoul")


def get_previous_day_range_kst():
    """
    Get the date range for the previous day in KST.
    
    Returns:
        tuple: (start_datetime_utc, end_datetime_utc)
    
    Example:
        If run at 2025-11-18 00:00:00 KST,
        returns:
            start: 2025-11-17 00:00:00 KST (2025-11-16 15:00:00 UTC)
            end:   2025-11-17 23:59:59 KST (2025-11-17 14:59:59 UTC)
    """
    # Get current time in KST
    now_kst = datetime.now(KST)
    
    # Get yesterday's date
    yesterday_kst = now_kst - timedelta(days=1)
    
    # Start of yesterday (00:00:00 KST)
    start_kst = yesterday_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # End of yesterday (23:59:59 KST)
    end_kst = yesterday_kst.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Convert to UTC for API calls
    start_utc = start_kst.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    end_utc = end_kst.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    
    logger.info(f"📅 Previous day (KST): {yesterday_kst.date()}")
    logger.info(f"   Start: {start_kst.isoformat()} ({start_utc.isoformat()} UTC)")
    logger.info(f"   End:   {end_kst.isoformat()} ({end_utc.isoformat()} UTC)")
    
    return start_utc, end_utc


async def collect_github(mongo_manager: MongoDBManager, start_date: datetime, end_date: datetime):
    """Collect GitHub data for the specified date range"""
    try:
        logger.info("📂 Collecting GitHub data...")
        
        config = Config()
        plugin_config = config.get_plugin_config('github')
        
        if not plugin_config or not plugin_config.get('enabled', False):
            logger.info("   ⏭️  GitHub plugin disabled, skipping")
            return
        
        plugin = GitHubPluginMongo(plugin_config, mongo_manager)
        
        if not plugin.authenticate():
            logger.error("   ❌ GitHub authentication failed")
            return
        
        # Collect data
        data = plugin.collect_data(start_date=start_date, end_date=end_date)
        
        # Save to MongoDB
        await plugin.save_data(data)
        
        commits_count = len(data.get('commits', []))
        prs_count = len(data.get('pull_requests', []))
        issues_count = len(data.get('issues', []))
        
        logger.info(f"   ✅ GitHub: {commits_count} commits, {prs_count} PRs, {issues_count} issues")
        
    except Exception as e:
        logger.error(f"   ❌ GitHub collection failed: {e}", exc_info=True)


async def collect_slack(mongo_manager: MongoDBManager, start_date: datetime, end_date: datetime):
    """Collect Slack data for the specified date range"""
    try:
        logger.info("📂 Collecting Slack data...")
        
        config = Config()
        plugin_config = config.get_plugin_config('slack')
        
        if not plugin_config or not plugin_config.get('enabled', False):
            logger.info("   ⏭️  Slack plugin disabled, skipping")
            return
        
        plugin = SlackPluginMongo(plugin_config, mongo_manager)
        
        if not plugin.authenticate():
            logger.error("   ❌ Slack authentication failed")
            return
        
        # Collect data
        data = plugin.collect_data(start_date=start_date, end_date=end_date)
        
        # Save to MongoDB
        await plugin.save_data(data)
        
        messages_count = len(data.get('messages', []))
        logger.info(f"   ✅ Slack: {messages_count} messages")
        
    except Exception as e:
        logger.error(f"   ❌ Slack collection failed: {e}", exc_info=True)


async def collect_notion(mongo_manager: MongoDBManager, start_date: datetime, end_date: datetime):
    """Collect Notion data for the specified date range"""
    try:
        logger.info("📂 Collecting Notion data...")
        
        config = Config()
        plugin_config = config.get_plugin_config('notion')
        
        if not plugin_config or not plugin_config.get('enabled', False):
            logger.info("   ⏭️  Notion plugin disabled, skipping")
            return
        
        plugin = NotionPluginMongo(plugin_config, mongo_manager)
        
        if not plugin.authenticate():
            logger.error("   ❌ Notion authentication failed")
            return
        
        # Collect data
        data = plugin.collect_data(start_date=start_date, end_date=end_date)
        
        # Save to MongoDB
        await plugin.save_data(data)
        
        pages_count = len(data.get('pages', []))
        logger.info(f"   ✅ Notion: {pages_count} pages")
        
    except Exception as e:
        logger.error(f"   ❌ Notion collection failed: {e}", exc_info=True)


async def collect_google_drive(mongo_manager: MongoDBManager):
    """
    Collect Google Drive data for the past 1 day.
    
    Note: Google Drive API works with 'days' parameter, not specific date ranges.
    We collect last 1 day to capture yesterday's activities.
    """
    try:
        logger.info("📂 Collecting Google Drive data...")
        
        config = Config()
        plugin_config = config.get_plugin_config('google_drive')
        
        if not plugin_config or not plugin_config.get('enabled', False):
            logger.info("   ⏭️  Google Drive plugin disabled, skipping")
            return
        
        plugin = GoogleDrivePluginMongo(plugin_config, mongo_manager)
        
        if not plugin.authenticate():
            logger.error("   ❌ Google Drive authentication failed")
            return
        
        # Collect last 1 day
        data = plugin.collect_data(days=1)
        
        # Save to MongoDB
        await plugin.save_data(data)
        
        activities_count = len(data.get('activities', []))
        logger.info(f"   ✅ Google Drive: {activities_count} activities")
        
    except Exception as e:
        logger.error(f"   ❌ Google Drive collection failed: {e}", exc_info=True)


async def main():
    """Main collection function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Collect previous day data (KST timezone)'
    )
    parser.add_argument(
        '--date',
        type=str,
        help='Specific date to collect (YYYY-MM-DD in KST). Default: yesterday'
    )
    parser.add_argument(
        '--sources',
        nargs='+',
        choices=['github', 'slack', 'notion', 'drive', 'all'],
        default=['all'],
        help='Sources to collect from (default: all)'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info(f"🚀 Starting DAILY data collection - {datetime.now(KST).isoformat()}")
    logger.info("=" * 80)
    
    # Calculate date range
    if args.date:
        # Parse specific date
        target_date = datetime.strptime(args.date, '%Y-%m-%d')
        start_kst = target_date.replace(hour=0, minute=0, second=0, tzinfo=KST)
        end_kst = target_date.replace(hour=23, minute=59, second=59, tzinfo=KST)
        start_utc = start_kst.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        end_utc = end_kst.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        logger.info(f"📅 Target date (KST): {target_date.date()}")
    else:
        # Use previous day
        start_utc, end_utc = get_previous_day_range_kst()
    
    # Initialize MongoDB connection
    mongo_manager = get_mongo_manager()
    mongo_manager.connect_async()
    
    try:
        # Determine which sources to collect
        sources = args.sources if 'all' not in args.sources else ['github', 'slack', 'notion', 'drive']
        
        logger.info(f"📦 Collecting from: {', '.join(sources)}")
        logger.info("=" * 80)
        
        # Collect from each source
        if 'github' in sources:
            await collect_github(mongo_manager, start_utc, end_utc)
        
        if 'slack' in sources:
            await collect_slack(mongo_manager, start_utc, end_utc)
        
        if 'notion' in sources:
            await collect_notion(mongo_manager, start_utc, end_utc)
        
        if 'drive' in sources:
            await collect_google_drive(mongo_manager)
        
        # Show summary
        logger.info("\n" + "=" * 80)
        logger.info("📊 Today's Collection Summary")
        logger.info("=" * 80)
        
        db = mongo_manager.async_db
        
        # Count documents collected today
        today_start = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_utc = today_start.astimezone(ZoneInfo("UTC"))
        
        collections_to_check = {
            'github_commits': 'GitHub Commits',
            'github_pull_requests': 'GitHub PRs',
            'github_issues': 'GitHub Issues',
            'slack_messages': 'Slack Messages',
            'notion_pages': 'Notion Pages',
            'drive_activities': 'Drive Activities'
        }
        
        for collection_name, display_name in collections_to_check.items():
            try:
                # Count documents with collected_at >= today
                count = await db[collection_name].count_documents({
                    'collected_at': {'$gte': today_start_utc}
                })
                logger.info(f"   {display_name:25s}: {count:,} new documents")
            except Exception as e:
                logger.warning(f"   {display_name:25s}: Error counting - {e}")
        
        logger.info("=" * 80)
        logger.info(f"✅ Daily collection completed - {datetime.now(KST).isoformat()}")
        logger.info("=" * 80)
        
        # Update member index
        logger.info("\n🔄 Updating member index...")
        try:
            from scripts.build_member_index_mongo import build_member_index
            await build_member_index(mongo_manager, incremental=True)
            logger.info("✅ Member index updated")
        except Exception as e:
            logger.error(f"❌ Member index update failed: {e}")
        
    finally:
        mongo_manager.close()


if __name__ == '__main__':
    asyncio.run(main())

