"""
Test script for Google Drive Plugin

Usage:
    python tests/test_google_drive_plugin.py [--days N] [--user EMAIL]
"""

import sys
import os
import argparse
import json
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import text

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import Config
from src.core.database import DatabaseManager
from src.core.member_index import MemberIndex
from src.plugins.google_drive_plugin import GoogleDrivePlugin
from src.utils.logger import get_logger
from src.utils.date_helpers import get_week_info

logger = get_logger(__name__)


def main():
    """Main test function"""
    parser = argparse.ArgumentParser(
        description='Test Google Drive Plugin'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days to collect (default: 7)'
    )
    parser.add_argument(
        '--user',
        type=str,
        help='Specific user email to collect (optional)'
    )
    parser.add_argument(
        '--last-week',
        action='store_true',
        help='Collect data for last complete week (Fri-Thu KST)'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("🧪 Google Drive Plugin Test")
    logger.info("=" * 80)
    
    # Load configuration
    logger.info("\n📋 Loading configuration...")
    config = Config()
    
    # Initialize database
    main_db_url = config.get('database', {}).get(
        'main_db', 
        'sqlite:///data/databases/main.db'
    )
    db_manager = DatabaseManager(main_db_url)
    
    # Create main database schema manually
    logger.info("📂 Creating main database schema...")
    main_schema = {
        'members': '''
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''',
        'member_identifiers': '''
            CREATE TABLE IF NOT EXISTS member_identifiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER NOT NULL,
                source_type TEXT NOT NULL,
                source_user_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (member_id) REFERENCES members(id),
                UNIQUE(source_type, source_user_id)
            )
        ''',
        'member_activities': '''
            CREATE TABLE IF NOT EXISTS member_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER NOT NULL,
                source_type TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                metadata TEXT,
                activity_id TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (member_id) REFERENCES members(id)
            )
        '''
    }
    
    with db_manager.get_connection() as conn:
        with conn.begin():
            for table_name, create_sql in main_schema.items():
                conn.execute(text(create_sql))
                logger.info(f"   ✅ Created table: {table_name}")
    
    # Initialize MemberIndex
    logger.info("📂 Initializing member index...")
    member_index = MemberIndex(db_manager)
    
    # Register or create Google Drive database
    drive_db_path = Path(__file__).parent.parent / 'data' / 'databases' / 'google_drive.db'
    
    if drive_db_path.exists():
        logger.info(f"📂 Using existing database: {drive_db_path}")
        db_manager.register_existing_source_database('google_drive', f'sqlite:///{drive_db_path}')
    else:
        logger.info(f"📂 Creating new database: {drive_db_path}")
        # We'll create it after loading plugin
    
    # Load Google Drive plugin
    logger.info("\n🔌 Loading Google Drive plugin...")
    plugin_config = config.get_plugin_config('google_drive')
    
    # Debug: Print config
    logger.info(f"📋 Plugin config keys: {list(plugin_config.keys()) if plugin_config else 'None'}")
    if plugin_config:
        logger.info(f"   credentials_path: {plugin_config.get('credentials_path')}")
        logger.info(f"   token_path: {plugin_config.get('token_path')}")
    
    if not plugin_config:
        logger.error("❌ Google Drive plugin not configured in config.yaml")
        logger.info("\n💡 Please add google_drive section to config/config.yaml")
        return
    
    # Override days if specified
    if args.days:
        plugin_config['days_to_collect'] = args.days
    
    # Override target users if specified
    if args.user:
        plugin_config['target_users'] = [args.user]
    
    drive_plugin = GoogleDrivePlugin(plugin_config)
    
    # Create database if needed
    if not drive_db_path.exists():
        db_manager.create_source_database('google_drive', drive_plugin.get_db_schema())
    
    # Authenticate
    logger.info("\n🔐 Authenticating with Google...")
    if not drive_plugin.authenticate():
        logger.error("❌ Authentication failed")
        return
    
    # Calculate date range
    start_date = None
    end_date = None
    
    if args.last_week:
        week_info = get_week_info(week_offset=-1)
        start_date = week_info['start_date']
        end_date = week_info['end_date']
        logger.info(f"\n📅 Collecting for {week_info['week_title']}")
        logger.info(f"   Period: {week_info['formatted_range']}")
    else:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days)
        logger.info(f"\n📅 Collecting for last {args.days} days")
        logger.info(f"   From: {start_date.strftime('%Y-%m-%d')}")
        logger.info(f"   To: {end_date.strftime('%Y-%m-%d')}")
    
    # Collect data
    logger.info("\n📥 Collecting Google Drive activities...")
    data = drive_plugin.collect_data(start_date=start_date, end_date=end_date)
    
    activities = data.get('activities', [])
    folders = data.get('folders', [])
    logger.info(f"\n✅ Collected {len(activities)} activities and {len(folders)} folders")
    
    if not activities and not folders:
        logger.info("📭 No data found")
        return
    
    # Show summary
    logger.info("\n📊 Activity Summary:")
    
    # By user
    user_counts = {}
    for activity in activities:
        user = activity['user_email']
        user_counts[user] = user_counts.get(user, 0) + 1
    
    logger.info(f"\n  By User:")
    for user, count in sorted(user_counts.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"    {user}: {count} activities")
    
    # By action
    action_counts = {}
    for activity in activities:
        action = activity['action']
        action_counts[action] = action_counts.get(action, 0) + 1
    
    logger.info(f"\n  By Action Type:")
    for action, count in sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        logger.info(f"    {action}: {count}")
    
    # Save to database
    logger.info("\n💾 Saving to database...")
    
    with db_manager.get_connection('google_drive') as conn:
        with conn.begin():
            for activity in activities:
                conn.execute(
                    text('''
                        INSERT INTO drive_activities 
                        (timestamp, user_email, action, event_name, doc_title, doc_type, doc_id, raw_event)
                        VALUES (:timestamp, :user_email, :action, :event_name, :doc_title, :doc_type, :doc_id, :raw_event)
                    '''),
                    {
                        'timestamp': activity['timestamp'].isoformat(),
                        'user_email': activity['user_email'],
                        'action': activity['action'],
                        'event_name': activity['event_name'],
                        'doc_title': activity['doc_title'],
                        'doc_type': activity['doc_type'],
                        'doc_id': activity['doc_id'],
                        'raw_event': activity['raw_event']
                    }
                )
    
    logger.info(f"✅ Saved {len(activities)} activities to database")
    
    # Save folders to database
    if folders:
        logger.info("\n💾 Saving folders to database...")
        
        with db_manager.get_connection('google_drive') as conn:
            with conn.begin():
                for folder in folders:
                    # Insert folder
                    conn.execute(
                        text('''
                            INSERT OR REPLACE INTO drive_folders 
                            (folder_id, folder_name, parent_folder_id, project_key, created_by, first_seen, last_activity)
                            VALUES (:folder_id, :folder_name, :parent_id, :project_key, :created_by, :created_time, :modified_time)
                        '''),
                        {
                            'folder_id': folder['folder_id'],
                            'folder_name': folder['folder_name'],
                            'parent_id': folder.get('parent_id'),
                            'project_key': folder.get('project_key'),
                            'created_by': folder.get('created_by'),
                            'created_time': folder.get('created_time'),
                            'modified_time': folder.get('modified_time')
                        }
                    )
                    
                    # Insert folder members
                    for member in folder.get('members', []):
                        conn.execute(
                            text('''
                                INSERT OR REPLACE INTO drive_folder_members 
                                (folder_id, user_email, access_level, added_at)
                                VALUES (:folder_id, :user_email, :access_level, :added_at)
                            '''),
                            {
                                'folder_id': folder['folder_id'],
                                'user_email': member['email'],
                                'access_level': member['role'],
                                'added_at': folder.get('created_time')
                            }
                        )
        
        logger.info(f"✅ Saved {len(folders)} folders to database")
    
    # Sync to member index
    logger.info("\n🔄 Syncing to member index...")
    
    member_activities = drive_plugin.extract_member_activities(data)
    member_details = drive_plugin.get_member_details()
    
    synced = member_index.sync_from_plugin(
        source_type='google_drive',
        activities=member_activities,
        member_mapping=drive_plugin.get_member_mapping(),
        member_details=member_details
    )
    
    logger.info(f"✅ Synced {synced} member activities")
    
    # Show some examples
    logger.info("\n📝 Sample Activities (latest 5):")
    for i, activity in enumerate(activities[:5], 1):
        logger.info(
            f"\n  {i}. [{activity['timestamp'].strftime('%Y-%m-%d %H:%M')}] "
            f"{activity['user_email']}"
        )
        logger.info(f"     Action: {activity['action']}")
        logger.info(f"     Document: {activity['doc_title']} ({activity['doc_type']})")
    
    logger.info("\n✨ Test completed!")


if __name__ == '__main__':
    main()

