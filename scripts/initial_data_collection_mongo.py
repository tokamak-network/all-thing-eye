#!/usr/bin/env python3
"""
Initial Data Collection Script for MongoDB

Collects 2 weeks of historical data when first deploying the system.
This should be run once after initial deployment.

Usage:
    python scripts/initial_data_collection_mongo.py
    python scripts/initial_data_collection_mongo.py --days 14
    python scripts/initial_data_collection_mongo.py --sources github slack
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
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


async def collect_github(mongo_manager: MongoDBManager, days: int = 14):
    """Collect GitHub data for the past N days"""
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
        
        # Calculate date range (past N days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        logger.info(f"   📅 Date range: {start_date.date()} to {end_date.date()}")
        
        # Collect data
        data = plugin.collect_data(start_date=start_date, end_date=end_date)
        
        # Save to MongoDB
        await plugin.save_data(data)
        
        logger.info(f"   ✅ GitHub: Collection completed")
        
    except Exception as e:
        logger.error(f"   ❌ GitHub collection failed: {e}", exc_info=True)


async def collect_slack(mongo_manager: MongoDBManager, days: int = 14):
    """Collect Slack data for the past N days"""
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
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        logger.info(f"   📅 Date range: {start_date.date()} to {end_date.date()}")
        
        # Collect data
        data = plugin.collect_data(start_date=start_date, end_date=end_date)
        
        # Save to MongoDB
        await plugin.save_data(data)
        
        logger.info(f"   ✅ Slack: Collection completed")
        
    except Exception as e:
        logger.error(f"   ❌ Slack collection failed: {e}", exc_info=True)


async def collect_notion(mongo_manager: MongoDBManager, days: int = 14):
    """Collect Notion data for the past N days"""
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
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        logger.info(f"   📅 Date range: {start_date.date()} to {end_date.date()}")
        
        # Collect data
        data = plugin.collect_data(start_date=start_date, end_date=end_date)
        
        # Save to MongoDB
        await plugin.save_data(data)
        
        logger.info(f"   ✅ Notion: Collection completed")
        
    except Exception as e:
        logger.error(f"   ❌ Notion collection failed: {e}", exc_info=True)


async def collect_google_drive(mongo_manager: MongoDBManager, days: int = 14):
    """Collect Google Drive data for the past N days"""
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
        
        logger.info(f"   📅 Collecting last {days} days of data")
        
        # Collect data
        data = plugin.collect_data(days=days)
        
        # Save to MongoDB
        await plugin.save_data(data)
        
        logger.info(f"   ✅ Google Drive: Collection completed")
        
    except Exception as e:
        logger.error(f"   ❌ Google Drive collection failed: {e}", exc_info=True)


async def main():
    """Main collection function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Collect initial historical data (default: 14 days)'
    )
    parser.add_argument(
        '--days', 
        type=int, 
        default=14, 
        help='Number of days to collect (default: 14)'
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
    logger.info(f"🚀 Starting INITIAL data collection - {datetime.utcnow().isoformat()}")
    logger.info(f"📅 Collection period: Last {args.days} days")
    logger.info(f"📦 Sources: {', '.join(args.sources)}")
    logger.info("=" * 80)
    
    # Initialize MongoDB connection
    config = Config()
    mongo_manager = get_mongo_manager(config.mongodb)
    mongo_manager.connect_async()  # Synchronous call
    
    try:
        # Determine which sources to collect
        sources = args.sources if 'all' not in args.sources else ['github', 'slack', 'notion', 'drive']
        
        # Collect from each source
        if 'github' in sources:
            await collect_github(mongo_manager, args.days)
        
        if 'slack' in sources:
            await collect_slack(mongo_manager, args.days)
        
        if 'notion' in sources:
            await collect_notion(mongo_manager, args.days)
        
        if 'drive' in sources:
            await collect_google_drive(mongo_manager, args.days)
        
        # Show summary
        logger.info("\n" + "=" * 80)
        logger.info("📊 Collection Summary")
        logger.info("=" * 80)
        
        db = mongo_manager.async_db
        
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
                count = await db[collection_name].count_documents({})
                logger.info(f"   {display_name:25s}: {count:,} documents")
            except Exception as e:
                logger.warning(f"   {display_name:25s}: Error counting - {e}")
        
        logger.info("=" * 80)
        logger.info(f"✅ Initial collection completed - {datetime.utcnow().isoformat()}")
        logger.info("=" * 80)
        logger.info("\n🎯 Next steps:")
        logger.info("   1. Build member index: python scripts/build_member_index_mongo.py")
        logger.info("   2. Verify data on web interface")
        logger.info("   3. Set up daily cron job for ongoing collection")
        
    finally:
        mongo_manager.close()


if __name__ == '__main__':
    asyncio.run(main())

