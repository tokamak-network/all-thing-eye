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

import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List

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


async def record_collection_status(
    mongo_manager: MongoDBManager,
    source: str,
    start_time: datetime,
    status: str,
    items_collected: int,
    error_message: str = None
):
    """
    Record collection status to MongoDB for tracking collector execution.
    
    Args:
        mongo_manager: MongoDB manager instance
        source: Data source name (github, slack, notion, drive)
        start_time: When the collection started
        status: success, failed, disabled
        items_collected: Number of items collected
        error_message: Error message if failed
    """
    try:
        db = mongo_manager.async_db
        collection = db['collection_status']
        
        end_time = datetime.utcnow()
        duration_seconds = (end_time - start_time).total_seconds()
        
        status_doc = {
            'source': source,
            'started_at': start_time,
            'completed_at': end_time,
            'duration_seconds': duration_seconds,
            'status': status,  # success, failed, disabled
            'items_collected': items_collected,
            'error_message': error_message
        }
        
        await collection.insert_one(status_doc)
        logger.debug(f"   📝 Recorded {source} collection status: {status}, {items_collected} items")
        
    except Exception as e:
        logger.warning(f"   ⚠️  Failed to record collection status for {source}: {e}")


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


async def collect_github(mongo_manager: MongoDBManager, start_date: datetime, end_date: datetime, target_members: List[str] = None):
    """Collect GitHub data for the specified date range"""
    start_time = datetime.utcnow()
    status = "failed"
    items_collected = 0
    error_message = None
    
    try:
        logger.info("📂 Collecting GitHub data...")
        
        config = Config()
        plugin_config = config.get_plugin_config('github')
        
        if not plugin_config or not plugin_config.get('enabled', False):
            logger.info("   ⏭️  GitHub plugin disabled, skipping")
            status = "disabled"
            return
        
        # If target members specified, add to plugin config
        if target_members:
            plugin_config['target_members'] = target_members
            logger.info(f"   🎯 Targeting specific members: {', '.join(target_members)}")
        
        plugin = GitHubPluginMongo(plugin_config, mongo_manager)
        
        if not plugin.authenticate():
            logger.error("   ❌ GitHub authentication failed")
            error_message = "Authentication failed"
            return
        
        # Collect data (GitHub plugin saves data internally during collect_data)
        data_list = plugin.collect_data(start_date=start_date, end_date=end_date)
        
        # GitHub plugin returns a list with one dict
        data = data_list[0] if data_list else {}
        
        # Note: GitHub plugin already saves data to MongoDB during collect_data
        # No need to call save_data separately
        
        commits_count = len(data.get('commits', []))
        prs_count = len(data.get('pull_requests', []))
        issues_count = len(data.get('issues', []))
        items_collected = commits_count + prs_count + issues_count
        
        logger.info(f"   ✅ GitHub: {commits_count} commits, {prs_count} PRs, {issues_count} issues")
        status = "success"
        
    except Exception as e:
        logger.error(f"   ❌ GitHub collection failed: {e}", exc_info=True)
        error_message = str(e)
    finally:
        # Record collection status
        await record_collection_status(
            mongo_manager, "github", start_time, status, items_collected, error_message
        )


async def collect_slack(mongo_manager: MongoDBManager, start_date: datetime, end_date: datetime):
    """Collect Slack data for the specified date range"""
    start_time = datetime.utcnow()
    status = "failed"
    items_collected = 0
    error_message = None
    
    try:
        logger.info("📂 Collecting Slack data...")
        
        config = Config()
        plugin_config = config.get_plugin_config('slack')
        
        if not plugin_config or not plugin_config.get('enabled', False):
            logger.info("   ⏭️  Slack plugin disabled, skipping")
            status = "disabled"
            return
        
        plugin = SlackPluginMongo(plugin_config, mongo_manager)
        
        if not plugin.authenticate():
            logger.error("   ❌ Slack authentication failed")
            error_message = "Authentication failed"
            return
        
        # Collect data (returns a list with one dict)
        data_list = plugin.collect_data(start_date=start_date, end_date=end_date)
        
        # Save to MongoDB (extract the dict from the list)
        if data_list:
            data = data_list[0]
            await plugin.save_data(data)
            messages_count = len(data.get('messages', []))
            items_collected = messages_count
            logger.info(f"   ✅ Slack: {messages_count} messages")
            status = "success"
        else:
            logger.warning("   ⚠️  Slack collection returned empty data")
            status = "success"  # Still success even if no data
        
    except Exception as e:
        logger.error(f"   ❌ Slack collection failed: {e}", exc_info=True)
        error_message = str(e)
    finally:
        # Record collection status
        await record_collection_status(
            mongo_manager, "slack", start_time, status, items_collected, error_message
        )


async def collect_notion(mongo_manager: MongoDBManager, start_date: datetime, end_date: datetime):
    """Collect Notion data for the specified date range"""
    start_time = datetime.utcnow()
    status = "failed"
    items_collected = 0
    error_message = None
    
    try:
        logger.info("📂 Collecting Notion data...")
        
        config = Config()
        plugin_config = config.get_plugin_config('notion')
        
        if not plugin_config or not plugin_config.get('enabled', False):
            logger.info("   ⏭️  Notion plugin disabled, skipping")
            status = "disabled"
            return
        
        plugin = NotionPluginMongo(plugin_config, mongo_manager)
        
        if not plugin.authenticate():
            logger.error("   ❌ Notion authentication failed")
            error_message = "Authentication failed"
            return
        
        # Ensure start_date and end_date are timezone-aware
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=ZoneInfo("UTC"))
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=ZoneInfo("UTC"))
        
        # Collect data (returns a list with one dict)
        data_list = plugin.collect_data(start_date=start_date, end_date=end_date)
        
        # Save to MongoDB (extract the dict from the list)
        if data_list:
            data = data_list[0]
            await plugin.save_data(data)
            pages_count = len(data.get('pages', []))
            items_collected = pages_count
            logger.info(f"   ✅ Notion: {pages_count} pages")
            status = "success"
        else:
            logger.warning("   ⚠️  Notion collection returned empty data")
            status = "success"  # Still success even if no data
        
    except Exception as e:
        logger.error(f"   ❌ Notion collection failed: {e}", exc_info=True)
        error_message = str(e)
    finally:
        # Record collection status
        await record_collection_status(
            mongo_manager, "notion", start_time, status, items_collected, error_message
        )


async def collect_google_drive(mongo_manager: MongoDBManager, start_date: datetime, end_date: datetime):
    """
    Collect Google Drive data for the specified date range.
    """
    start_time = datetime.utcnow()
    status = "failed"
    items_collected = 0
    error_message = None
    
    try:
        logger.info("📂 Collecting Google Drive data...")
        
        config = Config()
        plugin_config = config.get_plugin_config('google_drive')
        
        if not plugin_config or not plugin_config.get('enabled', False):
            logger.info("   ⏭️  Google Drive plugin disabled, skipping")
            status = "disabled"
            return
        
        plugin = GoogleDrivePluginMongo(plugin_config, mongo_manager)
        
        if not plugin.authenticate():
            logger.error("   ❌ Google Drive authentication failed")
            error_message = "Authentication failed"
            return
        
        # Ensure dates are timezone-aware (Google Drive plugin expects UTC)
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=ZoneInfo("UTC"))
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=ZoneInfo("UTC"))
        
        # Collect data (returns a list with one dict)
        data_list = plugin.collect_data(start_date=start_date, end_date=end_date)
        
        # Save to MongoDB (extract the dict from the list)
        if data_list:
            data = data_list[0]
            await plugin.save_data(data)
            activities_count = len(data.get('activities', []))
            items_collected = activities_count
            logger.info(f"   ✅ Google Drive: {activities_count} activities")
            status = "success"
        else:
            logger.warning("   ⚠️  Google Drive collection returned empty data")
            status = "success"  # Still success even if no data
        
    except Exception as e:
        logger.error(f"   ❌ Google Drive collection failed: {e}", exc_info=True)
        error_message = str(e)
    finally:
        # Record collection status
        await record_collection_status(
            mongo_manager, "drive", start_time, status, items_collected, error_message
        )


async def collect_ecosystem(mongo_manager: MongoDBManager, start_date: datetime, end_date: datetime):
    """
    Collect ecosystem data (staking, transactions, market cap) for the specified date range.
    
    This data is used for biweekly reports and ecosystem dashboards.
    """
    start_time = datetime.utcnow()
    status = "failed"
    items_collected = 0
    error_message = None
    
    try:
        logger.info("📂 Collecting Ecosystem data (staking, transactions, market cap)...")
        
        from src.plugins.ecosystem_plugin_mongo import EcosystemPluginMongo
        
        # Ecosystem plugin doesn't need special config, uses env vars
        plugin_config = {
            'enabled': True,
            'subgraph_api_key': os.getenv('SUBGRAPH_API_KEY', ''),
            'etherscan_api_key': os.getenv('ETHERSCAN_API_KEY', '')
        }
        
        plugin = EcosystemPluginMongo(plugin_config, mongo_manager)
        
        if not plugin.authenticate():
            logger.warning("   ⚠️  Some ecosystem APIs may not be configured")
        
        # Collect all ecosystem data
        results = await plugin.collect_all(start_date, end_date)
        
        # Count items
        staking_count = results.get("staking", {}).get("count", 0)
        tx_success = results.get("transactions", {}).get("success", False)
        market_success = results.get("market_cap", {}).get("success", False)
        
        items_collected = staking_count + (1 if tx_success else 0) + (1 if market_success else 0)
        
        logger.info(f"   ✅ Ecosystem: {staking_count} staking records, "
                   f"TX={'✓' if tx_success else '✗'}, "
                   f"Market={'✓' if market_success else '✗'}")
        status = "success"
        
    except Exception as e:
        logger.error(f"   ❌ Ecosystem collection failed: {e}", exc_info=True)
        error_message = str(e)
    finally:
        # Record collection status
        await record_collection_status(
            mongo_manager, "ecosystem", start_time, status, items_collected, error_message
        )


async def main():
    """Main collection function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Collect data for date range (KST timezone)'
    )
    parser.add_argument(
        '--date',
        type=str,
        help='Specific date to collect (YYYY-MM-DD in KST). Default: yesterday'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date for collection range (YYYY-MM-DD in KST). Use with --end-date or alone (collects until today)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='End date for collection range (YYYY-MM-DD in KST). Use with --start-date. Default: today if --start-date is specified'
    )
    parser.add_argument(
        '--sources',
        nargs='+',
        choices=['github', 'slack', 'notion', 'drive', 'ecosystem', 'all'],
        default=['all'],
        help='Sources to collect from (default: all)'
    )
    parser.add_argument(
        '--members',
        nargs='+',
        help='Specific members to collect GitHub data for (e.g., "Thomas Shin" "Eugenie Nguyen")'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info(f"🚀 Starting DAILY data collection - {datetime.now(KST).isoformat()}")
    logger.info("=" * 80)
    
    # Calculate date range
    if args.start_date:
        # Date range mode
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        start_kst = start_date.replace(hour=0, minute=0, second=0, tzinfo=KST)
        
        if args.end_date:
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
            end_kst = end_date.replace(hour=23, minute=59, second=59, tzinfo=KST)
        else:
            # If only --start-date is specified, collect until today
            today = datetime.now(KST)
            end_kst = today.replace(hour=23, minute=59, second=59, tzinfo=KST)
        
        start_utc = start_kst.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        end_utc = end_kst.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        logger.info(f"📅 Date range (KST): {start_date.date()} ~ {end_kst.date()}")
    elif args.date:
        # Single date mode
        target_date = datetime.strptime(args.date, '%Y-%m-%d')
        start_kst = target_date.replace(hour=0, minute=0, second=0, tzinfo=KST)
        end_kst = target_date.replace(hour=23, minute=59, second=59, tzinfo=KST)
        start_utc = start_kst.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        end_utc = end_kst.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        logger.info(f"📅 Target date (KST): {target_date.date()}")
    else:
        # Use previous day (default)
        start_utc, end_utc = get_previous_day_range_kst()
    
    # Initialize MongoDB connection
    import os
    mongodb_config = {
        'uri': os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
        'database': os.getenv('MONGODB_DATABASE', 'all_thing_eye')
    }
    mongo_manager = get_mongo_manager(mongodb_config)
    mongo_manager.connect_async()
    
    # Load Config for plugin configurations
    config = Config()
    
    try:
        # Determine which sources to collect
        sources = args.sources if 'all' not in args.sources else ['github', 'slack', 'notion', 'drive', 'ecosystem']
        
        logger.info(f"📦 Collecting from: {', '.join(sources)}")
        logger.info("=" * 80)
        
        # Collect from each source
        if 'github' in sources:
            await collect_github(mongo_manager, start_utc, end_utc, args.members)
        
        if 'slack' in sources:
            await collect_slack(mongo_manager, start_utc, end_utc)
        
        if 'notion' in sources:
            await collect_notion(mongo_manager, start_utc, end_utc)
        
        if 'drive' in sources:
            await collect_google_drive(mongo_manager, start_utc, end_utc)
        
        if 'ecosystem' in sources:
            await collect_ecosystem(mongo_manager, start_utc, end_utc)
        
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
            'drive_activities': 'Drive Activities',
            'ecosystem_staking': 'Ecosystem Staking',
            'ecosystem_transactions': 'Ecosystem Transactions',
            'ecosystem_market_cap': 'Ecosystem Market Cap'
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
        
        # Note: Member index is now managed exclusively through the frontend UI
        # No longer syncing from members.yaml to preserve database changes (is_active, resigned_at, etc.)
        
    finally:
        mongo_manager.close()


if __name__ == '__main__':
    asyncio.run(main())

