"""
Test script for Slack Plugin

This script tests the Slack data collection functionality including:
- Authentication
- Channel discovery
- Message collection
- Link extraction
- Database storage
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import argparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import Config
from src.core.database import DatabaseManager
from src.core.member_index import MemberIndex
from src.plugins.slack_plugin import SlackPlugin
from src.utils.date_helpers import get_current_week_range, get_last_week_range, get_week_info


def main(use_last_week: bool = False, target_channels: list = None):
    """
    Test Slack plugin data collection
    
    Args:
        use_last_week: If True, collect last week's data. If False, current week.
        target_channels: List of specific channels to collect (None = all)
    """
    print("=" * 70)
    print("🧪 Slack Plugin Test")
    print("=" * 70)
    
    try:
        # 1. Load configuration
        print("\n1️⃣ Loading configuration...")
        config = Config()
        
        # Get database URL
        main_db_url = config.get('database', {}).get('main_db', 'sqlite:///data/databases/main.db')
        print(f"   Environment: {config.get('app', {}).get('environment', 'development')}")
        print(f"   Database: {main_db_url}")
        
        # Check Slack token
        slack_token = os.getenv('SLACK_BOT_TOKEN')
        if slack_token:
            print(f"   ✅ Slack token loaded: {slack_token[:12]}...")
        else:
            print(f"   ⚠️  SLACK_BOT_TOKEN not found in environment")
            print(f"   💡 Add SLACK_BOT_TOKEN to your .env file")
            return
        
        # 2. Initialize database
        print("\n2️⃣ Initializing database...")
        db_manager = DatabaseManager(main_db_url)
        db_manager.initialize_main_schema()
        
        # 3. Initialize member index
        print("\n3️⃣ Initializing member index...")
        member_index = MemberIndex(db_manager)
        
        # 4. Load Slack plugin
        print("\n4️⃣ Loading Slack plugin...")
        
        # Get Slack plugin config
        slack_config = config.get_plugin_config('slack')
        
        # Override target_channels if specified
        if target_channels:
            slack_config['target_channels'] = target_channels
            print(f"   🔍 Filtering to channels: {', '.join(target_channels)}")
        
        # Directly instantiate SlackPlugin
        slack_plugin = SlackPlugin(slack_config)
        
        # Create database schema for Slack
        db_manager.create_source_database('slack', slack_plugin.get_db_schema())
        
        print(f"   ✅ Slack plugin loaded")
        
        # 5. Authenticate
        print("\n5️⃣ Authenticating with Slack...")
        if not slack_plugin.authenticate():
            print("   ❌ Authentication failed!")
            return
        
        # 6. Determine date range
        print("\n6️⃣ Determining collection period...")
        
        if use_last_week:
            print("   🔙 Using LAST WEEK (complete week)")
            start_date, end_date = get_last_week_range()
        else:
            print("   📅 Using CURRENT WEEK (up to now)")
            start_date, end_date = get_current_week_range()
        
        week_info = get_week_info(start_date, end_date)
        print(f"   📅 Week: {week_info['week_title']}")
        print(f"   📅 Period: {week_info['formatted_range']}")
        print(f"   🕐 Full Range: {week_info['formatted_range_with_time']}")
        
        # 7. Collect data
        print("\n7️⃣ Collecting Slack data...")
        data = slack_plugin.collect_data(start_date, end_date)
        
        # 8. Save to database
        print("\n8️⃣ Saving to database...")
        
        # Save users
        if data['users']:
            count = db_manager.insert_data(
                'slack_users',
                data['users'],
                source_name='slack'
            )
            print(f"   ✅ Saved {count} users")
        
        # Save channels
        if data['channels']:
            count = db_manager.insert_data(
                'slack_channels',
                data['channels'],
                source_name='slack'
            )
            print(f"   ✅ Saved {count} channels")
        
        # Save messages
        if data['messages']:
            # Remove reactions and files from messages before saving
            messages_to_save = []
            for msg in data['messages']:
                msg_copy = msg.copy()
                msg_copy.pop('reactions', None)
                msg_copy.pop('files', None)
                messages_to_save.append(msg_copy)
            
            count = db_manager.insert_data(
                'slack_messages',
                messages_to_save,
                source_name='slack'
            )
            print(f"   ✅ Saved {count} messages")
        
        # Save reactions
        if data['reactions']:
            count = db_manager.insert_data(
                'slack_reactions',
                data['reactions'],
                source_name='slack'
            )
            print(f"   ✅ Saved {count} reactions")
        
        # Save links
        if data['links']:
            count = db_manager.insert_data(
                'slack_links',
                data['links'],
                source_name='slack'
            )
            print(f"   ✅ Saved {count} links")
            
            # Show link type breakdown
            link_types = {}
            for link in data['links']:
                link_type = link.get('link_type', 'unknown')
                link_types[link_type] = link_types.get(link_type, 0) + 1
            
            print(f"   📊 Link breakdown:")
            for link_type, count in sorted(link_types.items(), key=lambda x: x[1], reverse=True):
                print(f"      - {link_type}: {count}")
        
        # Save files
        if data['files']:
            count = db_manager.insert_data(
                'slack_files',
                data['files'],
                source_name='slack'
            )
            print(f"   ✅ Saved {count} files")
        
        # 9. Sync to member index
        print("\n9️⃣ Syncing to member index...")
        
        member_mapping = slack_plugin.get_member_mapping()
        member_details = slack_plugin.get_member_details()
        activities = slack_plugin.extract_member_activities(data)
        
        print(f"   📋 Member mapping: {len(member_mapping)} members")
        if member_mapping:
            print(f"   📋 Sample mapping: {list(member_mapping.items())[:2]}")
        
        stats = member_index.sync_from_plugin(
            source_type='slack',
            member_mapping=member_mapping,
            activities=activities,
            member_details=member_details
        )
        
        print(f"   ✅ Members registered: {stats['members_registered']}")
        print(f"   ✅ Activities added: {stats['activities_added']}")
        if stats['errors'] > 0:
            print(f"   ⚠️  Errors: {stats['errors']}")
        
        # 10. Query results
        print("\n🔟 Querying member activities...")
        
        all_members = member_index.get_all_members()
        print(f"\n   📋 Total members: {len(all_members)}")
        
        if all_members:
            # Show activities for first member with Slack data
            for member in all_members:
                activities = member_index.get_member_activities(
                    member_name=member['name'],
                    source_type='slack',
                    limit=5
                )
                
                if activities:
                    print(f"\n   👤 Sample activities for {member['name']}:")
                    for activity in activities[:5]:
                        activity_type = activity['activity_type']
                        timestamp = activity['timestamp']
                        metadata = activity.get('metadata', {})
                        
                        if activity_type == 'message':
                            channel = metadata.get('channel_id', 'unknown')
                            print(f"      • [{timestamp}] Message in {channel}")
                        elif activity_type == 'reaction':
                            emoji = metadata.get('emoji', '?')
                            print(f"      • [{timestamp}] Reaction: :{emoji}:")
                    break
        
        print("\n" + "=" * 70)
        print("✅ Test completed successfully!")
        print("=" * 70)
        print("\nDatabase files created:")
        print("   • data/databases/main.db (member index)")
        print("   • data/databases/slack.db (Slack data)")
        print("\nYou can explore the data using:")
        print("   sqlite3 data/databases/slack.db")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        try:
            db_manager.close_all()
        except:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test Slack plugin')
    parser.add_argument(
        '--last-week',
        action='store_true',
        help='Collect last week data instead of current week'
    )
    parser.add_argument(
        '--channels',
        nargs='+',
        help='Specific channels to collect (e.g., --channels general dev)'
    )
    
    args = parser.parse_args()
    
    main(
        use_last_week=args.last_week,
        target_channels=args.channels
    )

