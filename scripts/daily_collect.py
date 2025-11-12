#!/usr/bin/env python3
"""
Daily Data Collection Script

Automatically collects data from all sources (GitHub, Slack, Google Drive, Notion)
Can be run manually or scheduled via cron/systemd timer
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import text

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import Config
from src.core.database import DatabaseManager
from src.core.member_index import MemberIndex
from src.plugins.github_plugin import GitHubPlugin
from src.plugins.slack_plugin import SlackPlugin
from src.plugins.google_drive_plugin import GoogleDrivePlugin
from src.plugins.notion_plugin import NotionPlugin
from src.utils.logger import get_logger
from src.utils.date_helpers import get_week_info

logger = get_logger(__name__)


def collect_github(config, db_manager, member_index, days=7):
    """Collect GitHub data"""
    try:
        logger.info("📂 Collecting GitHub data...")
        
        plugin_config = config.get_plugin_config('github')
        if not plugin_config or not plugin_config.get('enabled', False):
            logger.info("   ⏭️  GitHub plugin disabled, skipping")
            return
        
        github_plugin = GitHubPlugin(plugin_config)
        
        # Register database
        db_manager.create_source_database('github', github_plugin.get_db_schema())
        
        if not github_plugin.authenticate():
            logger.error("   ❌ GitHub authentication failed")
            return
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Collect data
        github_data = github_plugin.collect_data(start_date=start_date, end_date=end_date)
        
        # Sync to member index
        member_activities = github_plugin.extract_member_activities(github_data)
        member_details = github_plugin.get_member_details()
        
        synced = member_index.sync_from_plugin(
            source_type='github',
            activities=member_activities,
            member_mapping=github_plugin.get_member_mapping(),
            member_details=member_details
        )
        
        logger.info(f"   ✅ GitHub: Synced {synced} activities")
        
    except Exception as e:
        logger.error(f"   ❌ GitHub collection failed: {e}", exc_info=True)


def collect_slack(config, db_manager, member_index, days=7):
    """Collect Slack data"""
    try:
        logger.info("📂 Collecting Slack data...")
        
        plugin_config = config.get_plugin_config('slack')
        if not plugin_config or not plugin_config.get('enabled', False):
            logger.info("   ⏭️  Slack plugin disabled, skipping")
            return
        
        slack_plugin = SlackPlugin(plugin_config)
        
        # Register database
        db_manager.create_source_database('slack', slack_plugin.get_db_schema())
        
        if not slack_plugin.authenticate():
            logger.error("   ❌ Slack authentication failed")
            return
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Collect data
        slack_data = slack_plugin.collect_data(start_date=start_date, end_date=end_date)
        
        # Sync to member index
        member_activities = slack_plugin.extract_member_activities(slack_data)
        member_details = slack_plugin.get_member_details()
        
        synced = member_index.sync_from_plugin(
            source_type='slack',
            activities=member_activities,
            member_mapping=slack_plugin.get_member_mapping(),
            member_details=member_details
        )
        
        logger.info(f"   ✅ Slack: Synced {synced} activities")
        
    except Exception as e:
        logger.error(f"   ❌ Slack collection failed: {e}", exc_info=True)


def collect_google_drive(config, db_manager, member_index, days=7):
    """Collect Google Drive data"""
    try:
        logger.info("📂 Collecting Google Drive data...")
        
        plugin_config = config.get_plugin_config('google_drive')
        if not plugin_config or not plugin_config.get('enabled', False):
            logger.info("   ⏭️  Google Drive plugin disabled, skipping")
            return
        
        drive_plugin = GoogleDrivePlugin(plugin_config)
        
        # Register database
        db_manager.create_source_database('google_drive', drive_plugin.get_db_schema())
        
        if not drive_plugin.authenticate():
            logger.error("   ❌ Google Drive authentication failed")
            return
        
        # Collect data
        drive_data = drive_plugin.collect_data(days=days)
        
        # Sync to member index
        member_activities = drive_plugin.extract_member_activities(drive_data)
        member_details = drive_plugin.get_member_details()
        
        synced = member_index.sync_from_plugin(
            source_type='google_drive',
            activities=member_activities,
            member_mapping=drive_plugin.get_member_mapping(),
            member_details=member_details
        )
        
        logger.info(f"   ✅ Google Drive: Synced {synced} activities")
        
    except Exception as e:
        logger.error(f"   ❌ Google Drive collection failed: {e}", exc_info=True)


def collect_notion(config, db_manager, member_index, days=7):
    """Collect Notion data"""
    try:
        logger.info("📂 Collecting Notion data...")
        
        plugin_config = config.get_plugin_config('notion')
        if not plugin_config or not plugin_config.get('enabled', False):
            logger.info("   ⏭️  Notion plugin disabled, skipping")
            return
        
        notion_plugin = NotionPlugin(plugin_config)
        
        # Register database
        db_manager.create_source_database('notion', notion_plugin.get_db_schema())
        
        if not notion_plugin.authenticate():
            logger.error("   ❌ Notion authentication failed")
            return
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Collect data
        notion_data = notion_plugin.collect_data(start_date=start_date, end_date=end_date)
        
        # Sync to member index
        member_activities = notion_plugin.extract_member_activities(notion_data)
        member_details = notion_plugin.get_member_details()
        
        synced = member_index.sync_from_plugin(
            source_type='notion',
            activities=member_activities,
            member_mapping=notion_plugin.get_member_mapping(),
            member_details=member_details
        )
        
        logger.info(f"   ✅ Notion: Synced {synced} activities")
        
    except Exception as e:
        logger.error(f"   ❌ Notion collection failed: {e}", exc_info=True)


def main():
    """Main collection function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Collect data from all sources')
    parser.add_argument('--days', type=int, default=7, help='Number of days to collect (default: 7)')
    parser.add_argument('--sources', nargs='+', 
                       choices=['github', 'slack', 'google_drive', 'notion', 'all'],
                       default=['all'],
                       help='Sources to collect from')
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info(f"🚀 Starting daily data collection - {datetime.now().isoformat()}")
    logger.info(f"📅 Collection period: Last {args.days} days")
    logger.info("=" * 80)
    
    # Load configuration
    config = Config()
    
    # Initialize database
    main_db_url = config.get('database', {}).get(
        'main_db', 
        'sqlite:///data/databases/main.db'
    )
    db_manager = DatabaseManager(main_db_url)
    
    # Initialize member index
    member_index = MemberIndex(db_manager)
    
    # Collect from each source
    sources = args.sources if 'all' not in args.sources else ['github', 'slack', 'google_drive', 'notion']
    
    for source in sources:
        if source == 'github':
            collect_github(config, db_manager, member_index, args.days)
        elif source == 'slack':
            collect_slack(config, db_manager, member_index, args.days)
        elif source == 'google_drive':
            collect_google_drive(config, db_manager, member_index, args.days)
        elif source == 'notion':
            collect_notion(config, db_manager, member_index, args.days)
    
    # Show summary
    logger.info("\n" + "=" * 80)
    logger.info("📊 Collection Summary")
    logger.info("=" * 80)
    
    with db_manager.get_connection() as conn:
        result = conn.execute(text("""
            SELECT source_type, COUNT(*) as count
            FROM member_activities
            GROUP BY source_type
            ORDER BY source_type
        """))
        
        for row in result:
            logger.info(f"   {row[0]:20s}: {row[1]:,} activities")
    
    logger.info("=" * 80)
    logger.info(f"✅ Collection completed - {datetime.now().isoformat()}")
    logger.info("=" * 80)
    
    db_manager.close_all()


if __name__ == '__main__':
    main()

