#!/usr/bin/env python
"""
Test script for GitHub plugin

This script demonstrates how to use the GitHub plugin to collect data.
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import get_config
from src.core.database import DatabaseManager
from src.core.member_index import MemberIndex
from src.core.plugin_loader import PluginLoader
from src.utils.date_helpers import get_current_week_range, get_last_week_range, get_week_info


def main(use_last_week: bool = False, single_member: str = None):
    print("=" * 70)
    print("🧪 GitHub Plugin Test")
    print("=" * 70)
    
    # 1. Load configuration
    print("\n1️⃣ Loading configuration...")
    config = get_config()
    print(f"   Environment: {config.app_env}")
    print(f"   Database: {config.database_url}")
    
    # Debug: Check if GitHub token is loaded
    github_config = config.get('plugins', {}).get('github', {})
    token = github_config.get('token', '')
    if token:
        print(f"   ✅ GitHub token loaded: {token[:4]}***{token[-4:] if len(token) > 8 else '***'}")
    else:
        print(f"   ❌ GitHub token NOT loaded!")
        print(f"   🔍 Token value: '{token}'")
        print(f"   💡 Check .env file: {project_root / '.env'}")
        import sys
        sys.exit(1)
    
    # 2. Initialize database
    print("\n2️⃣ Initializing database...")
    db_manager = DatabaseManager(config.database_url)
    db_manager.initialize_main_schema()
    
    # 3. Initialize member index
    print("\n3️⃣ Initializing member index...")
    member_index = MemberIndex(db_manager)
    
    # 4. Load plugins (with optional single member filter)
    print("\n4️⃣ Loading plugins...")
    
    # Filter member list if single_member flag is set
    if single_member:
        print(f"   🔍 Filtering to single member: {single_member}")
        github_config = config.get('plugins', {}).get('github', {})
        member_list = github_config.get('member_list', [])
        
        # Find matching member (by name or GitHub ID)
        filtered_members = [
            m for m in member_list 
            if m.get('name') == single_member or m.get('githubId') == single_member
        ]
        
        if not filtered_members:
            print(f"   ⚠️  Member '{single_member}' not found! Available members:")
            for m in member_list[:5]:
                print(f"      • {m.get('name')} ({m.get('githubId')})")
            if len(member_list) > 5:
                print(f"      ... and {len(member_list) - 5} more")
            print("   Using first member instead...")
            filtered_members = [member_list[0]] if member_list else []
        
        if filtered_members:
            config._config['plugins']['github']['member_list'] = filtered_members
            print(f"   ✅ Testing with: {filtered_members[0].get('name')} ({filtered_members[0].get('githubId')})")
    
    plugin_loader = PluginLoader(config, db_manager)
    plugins = plugin_loader.load_all_plugins()
    
    if not plugins:
        print("❌ No plugins loaded. Check your configuration.")
        return
    
    # 5. Get GitHub plugin
    try:
        github_plugin = plugin_loader.get_plugin('github')
    except KeyError:
        print("❌ GitHub plugin not found or not enabled.")
        print("   Make sure GITHUB_ENABLED=true and GITHUB_TOKEN is set in .env")
        return
    
    # 6. Authenticate
    print("\n5️⃣ Authenticating with GitHub...")
    if not github_plugin.authenticate():
        print("❌ GitHub authentication failed")
        return
    
    # 7. Collect data
    print("\n6️⃣ Collecting GitHub data...")
    
    # Collection period
    if use_last_week:
        # Last complete week (previous Friday 00:00 ~ last Thursday 23:59 KST)
        start_date, end_date = get_last_week_range()
        print("   🔙 Using LAST WEEK (complete week)")
    else:
        # Current week (Friday 00:00 ~ Thursday 23:59 or now KST)
        start_date, end_date = get_current_week_range()
        print("   📍 Using CURRENT WEEK (may be incomplete)")
    
    week_info = get_week_info(start_date, end_date)
    
    print(f"   📅 Week: {week_info['week_title']}")
    print(f"   📅 Period: {week_info['formatted_range']} KST")
    print(f"   🕐 Full Range: {week_info['formatted_range_with_time']}")
    
    try:
        data = github_plugin.collect_data(start_date, end_date)
        
        if data:
            github_data = data[0]
            print(f"\n📊 Collection Results:")
            print(f"   Members: {len(github_data.get('members', []))}")
            print(f"   Repositories: {len(github_data.get('repositories', []))}")
            print(f"   Commits: {len(github_data.get('commits', []))}")
            print(f"   Pull Requests: {len(github_data.get('pull_requests', []))}")
            print(f"   Issues: {len(github_data.get('issues', []))}")
            
            # 8. Save to database
            print("\n7️⃣ Saving to database...")
            
            # Save commits (and extract file details)
            if github_data.get('commits'):
                all_commit_files = []
                
                # Separate commits from files
                commits_without_files = []
                for commit in github_data['commits']:
                    # Extract files if present
                    files = commit.pop('files', [])  # Remove 'files' key
                    commits_without_files.append(commit)
                    
                    # Store files with commit_sha reference
                    for file in files:
                        # Parse patch to extract added/deleted lines
                        patch = file.get('patch')
                        parsed = github_plugin._parse_patch(patch)
                        
                        all_commit_files.append({
                            'commit_sha': commit['sha'],
                            'filename': file.get('filename'),
                            'additions': file.get('additions', 0),
                            'deletions': file.get('deletions', 0),
                            'changes': file.get('changes', 0),
                            'status': file.get('status'),
                            'patch': patch,
                            'added_lines': json.dumps(parsed['added_lines'], ensure_ascii=False),
                            'deleted_lines': json.dumps(parsed['deleted_lines'], ensure_ascii=False)
                        })
                
                # Save commits
                commit_count = db_manager.insert_data(
                    'github_commits',
                    commits_without_files,
                    source_name='github'
                )
                print(f"   ✅ Saved {commit_count} commits")
                
                # Save commit files
                if all_commit_files:
                    file_count = db_manager.insert_data(
                        'github_commit_files',
                        all_commit_files,
                        source_name='github'
                    )
                    print(f"   ✅ Saved {file_count} commit files (diffs)")
            
            # Save PRs
            if github_data.get('pull_requests'):
                count = db_manager.insert_data(
                    'github_pull_requests',
                    github_data['pull_requests'],
                    source_name='github'
                )
                print(f"   ✅ Saved {count} pull requests")
            
            # Save issues
            if github_data.get('issues'):
                count = db_manager.insert_data(
                    'github_issues',
                    github_data['issues'],
                    source_name='github'
                )
                print(f"   ✅ Saved {count} issues")
            
            # 9. Sync to member index
            print("\n8️⃣ Syncing to member index...")
            
            # Extract member mapping, details, and activities
            member_mapping = github_plugin.get_member_mapping()
            member_details = github_plugin.get_member_details()
            activities = github_plugin.extract_member_activities(data)
            
            print(f"   📋 Member mapping: {len(member_mapping)} members")
            print(f"   📋 Sample mapping: {list(member_mapping.items())[:2]}")
            
            # Sync
            stats = member_index.sync_from_plugin(
                source_type='github',
                member_mapping=member_mapping,
                activities=activities,
                member_details=member_details
            )
            
            print(f"   ✅ Members registered: {stats['members_registered']}")
            print(f"   ✅ Activities added: {stats['activities_added']}")
            if stats['errors'] > 0:
                print(f"   ⚠️  Errors: {stats['errors']}")
            
            # 10. Query member activities
            print("\n9️⃣ Querying member activities...")
            
            all_members = member_index.get_all_members()
            print(f"\n   📋 Total members: {len(all_members)}")
            
            if all_members:
                # Show activities for first member
                first_member = all_members[0]
                print(f"\n   👤 Sample activities for {first_member['name']}:")
                
                activities = member_index.get_member_activities(
                    member_name=first_member['name'],
                    source_type='github',
                    limit=5
                )
                
                for activity in activities:
                    timestamp = activity['timestamp']
                    activity_type = activity['activity_type']
                    metadata = activity.get('metadata', {})
                    
                    if activity_type == 'github_commit':
                        repo = metadata.get('repository', 'unknown')
                        msg = metadata.get('message', '')[:50]
                        print(f"      • [{timestamp}] Commit in {repo}: {msg}")
                    elif activity_type == 'github_pull_request':
                        repo = metadata.get('repository', 'unknown')
                        title = metadata.get('title', '')[:50]
                        print(f"      • [{timestamp}] PR in {repo}: {title}")
                    elif activity_type == 'github_issue':
                        repo = metadata.get('repository', 'unknown')
                        title = metadata.get('title', '')[:50]
                        print(f"      • [{timestamp}] Issue in {repo}: {title}")
        
    except Exception as e:
        print(f"❌ Error during data collection: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 70)
    print("✅ Test completed successfully!")
    print("=" * 70)
    print("\nDatabase files created:")
    print(f"   • data/databases/main.db (member index)")
    print(f"   • data/databases/github.db (GitHub data)")
    print("\nYou can explore the data using:")
    print(f"   sqlite3 data/databases/github.db")
    print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test GitHub plugin data collection')
    parser.add_argument(
        '--last-week',
        action='store_true',
        help='Collect data for LAST complete week (previous Friday ~ last Thursday) instead of current week'
    )
    parser.add_argument(
        '--single-member',
        type=str,
        metavar='NAME_OR_ID',
        help='Test with a single member only (by name or GitHub ID). E.g., --single-member Kevin or --single-member SonYoungsung'
    )
    
    args = parser.parse_args()
    main(use_last_week=args.last_week, single_member=args.single_member)

