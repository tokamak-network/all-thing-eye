"""
Test script for Notion Plugin

Usage:
    python tests/test_notion_plugin.py --days 7
    python tests/test_notion_plugin.py --last-week
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import text

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import Config
from src.core.database import DatabaseManager
from src.core.member_index import MemberIndex
from src.plugins.notion_plugin import NotionPlugin
from src.utils.logger import get_logger
from src.utils.date_helpers import get_week_info

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Test Notion Plugin')
    parser.add_argument('--days', type=int, default=7, help='Number of days to collect')
    parser.add_argument('--last-week', action='store_true', help='Collect data for last week (Fri-Thu)')
    
    args = parser.parse_args()
    
    # Load configuration
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
    
    # Initialize Notion plugin
    logger.info("📂 Initializing Notion plugin...")
    plugin_config = config.get_plugin_config('notion')
    
    if not plugin_config:
        logger.error("❌ Notion plugin configuration not found in config.yaml")
        logger.info("Please add the following to your config.yaml:")
        logger.info("""
plugins:
  notion:
    enabled: true
    token: ${NOTION_TOKEN}
    days_to_collect: 7
        """)
        return
    
    notion_plugin = NotionPlugin(plugin_config)
    
    # Create Notion database
    logger.info("📂 Creating Notion database...")
    db_manager.create_source_database('notion', notion_plugin.get_db_schema())
    
    # Authenticate
    logger.info("\n🔐 Authenticating with Notion...")
    if not notion_plugin.authenticate():
        logger.error("❌ Authentication failed. Please check your NOTION_TOKEN in .env")
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
    logger.info("\n📥 Collecting Notion data...")
    data = notion_plugin.collect_data(start_date=start_date, end_date=end_date)
    
    users = data.get('users', [])
    pages = data.get('pages', [])
    databases = data.get('databases', [])
    comments = data.get('comments', [])
    
    logger.info(f"\n✅ Collected data:")
    logger.info(f"   Users: {len(users)}")
    logger.info(f"   Pages: {len(pages)}")
    logger.info(f"   Databases: {len(databases)}")
    logger.info(f"   Comments: {len(comments)}")
    
    if not users and not pages:
        logger.info("📭 No data found in the specified period")
        return
    
    # Save to database
    logger.info("\n💾 Saving to database...")
    
    # Save users
    if users:
        with db_manager.get_connection('notion') as conn:
            with conn.begin():
                for user in users:
                    conn.execute(
                        text('''
                            INSERT OR REPLACE INTO notion_users 
                            (id, name, email, type, avatar_url)
                            VALUES (:id, :name, :email, :type, :avatar_url)
                        '''),
                        {
                            'id': user['id'],
                            'name': user['name'],
                            'email': user.get('email'),
                            'type': user['type'],
                            'avatar_url': user.get('avatar_url')
                        }
                    )
        logger.info(f"   ✅ Saved {len(users)} users")
    
    # Save pages
    if pages:
        with db_manager.get_connection('notion') as conn:
            with conn.begin():
                for page in pages:
                    conn.execute(
                        text('''
                            INSERT OR REPLACE INTO notion_pages 
                            (id, title, created_time, last_edited_time, created_by, 
                             last_edited_by, archived, url, parent_type, parent_id)
                            VALUES (:id, :title, :created_time, :last_edited_time, 
                                    :created_by, :last_edited_by, :archived, :url, 
                                    :parent_type, :parent_id)
                        '''),
                        {
                            'id': page['id'],
                            'title': page.get('title', 'Untitled'),
                            'created_time': page['created_time'],
                            'last_edited_time': page['last_edited_time'],
                            'created_by': page.get('created_by'),
                            'last_edited_by': page.get('last_edited_by'),
                            'archived': page.get('archived', False),
                            'url': page.get('url'),
                            'parent_type': page.get('parent_type'),
                            'parent_id': page.get('parent_id')
                        }
                    )
        logger.info(f"   ✅ Saved {len(pages)} pages")
    
    # Save databases
    if databases:
        with db_manager.get_connection('notion') as conn:
            with conn.begin():
                for db in databases:
                    conn.execute(
                        text('''
                            INSERT OR REPLACE INTO notion_databases 
                            (id, title, created_time, last_edited_time, created_by, 
                             last_edited_by, archived, url)
                            VALUES (:id, :title, :created_time, :last_edited_time, 
                                    :created_by, :last_edited_by, :archived, :url)
                        '''),
                        {
                            'id': db['id'],
                            'title': db.get('title', 'Untitled'),
                            'created_time': db['created_time'],
                            'last_edited_time': db['last_edited_time'],
                            'created_by': db.get('created_by'),
                            'last_edited_by': db.get('last_edited_by'),
                            'archived': db.get('archived', False),
                            'url': db.get('url')
                        }
                    )
        logger.info(f"   ✅ Saved {len(databases)} databases")
    
    # Save comments
    if comments:
        with db_manager.get_connection('notion') as conn:
            with conn.begin():
                for comment in comments:
                    conn.execute(
                        text('''
                            INSERT OR REPLACE INTO notion_comments 
                            (id, page_id, created_time, last_edited_time, created_by, rich_text)
                            VALUES (:id, :page_id, :created_time, :last_edited_time, 
                                    :created_by, :rich_text)
                        '''),
                        {
                            'id': comment['id'],
                            'page_id': comment.get('page_id'),
                            'created_time': comment['created_time'],
                            'last_edited_time': comment.get('last_edited_time'),
                            'created_by': comment.get('created_by'),
                            'rich_text': comment.get('rich_text', '')
                        }
                    )
        logger.info(f"   ✅ Saved {len(comments)} comments")
    
    # Sync to member index
    logger.info("\n🔄 Syncing to member index...")
    
    member_activities = notion_plugin.extract_member_activities(data)
    member_details = notion_plugin.get_member_details()
    
    synced = member_index.sync_from_plugin(
        source_type='notion',
        activities=member_activities,
        member_mapping=notion_plugin.get_member_mapping(),
        member_details=member_details
    )
    
    logger.info(f"✅ Synced {synced} member activities")
    
    # Show some examples
    if pages:
        logger.info("\n📝 Sample Pages (latest 5):")
        for i, page in enumerate(pages[:5], 1):
            logger.info(f"\n  {i}. {page.get('title', 'Untitled')}")
            logger.info(f"     Created: {page.get('created_time', 'Unknown')}")
            logger.info(f"     Last edited: {page.get('last_edited_time', 'Unknown')}")
            logger.info(f"     URL: {page.get('url', 'N/A')}")
    
    logger.info("\n✨ Test completed!")


if __name__ == '__main__':
    main()

