#!/usr/bin/env python3
"""
Build Member Index for MongoDB

Creates unified member index from multiple data sources:
- members: Unified member list
- member_identifiers: Cross-platform identifier mapping
- member_activities: Unified activity log

This script only READS from source collections and CREATES new index collections.
Original data is never modified.
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import yaml
from bson import ObjectId

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from src.core.mongo_manager import get_mongo_manager


async def load_members_config() -> List[Dict[str, Any]]:
    """Load members from members.yaml"""
    members_path = project_root / "config" / "members.yaml"
    
    if not members_path.exists():
        raise FileNotFoundError(f"Members config not found: {members_path}")
    
    with open(members_path, 'r', encoding='utf-8') as f:
        members = yaml.safe_load(f)
    
    return members if members else []


async def build_members_collection(db, members_config: List[Dict[str, Any]]) -> Dict[str, ObjectId]:
    """
    Create members collection from config
    
    Returns:
        Dict mapping member name to MongoDB ObjectId
    """
    print("\n" + "="*70)
    print("1️⃣ Building Members Collection")
    print("="*70)
    
    members_col = db["members"]
    member_name_to_id = {}
    
    # Clear existing data
    await members_col.delete_many({})
    print(f"   🗑️  Cleared existing members")
    
    for member_config in members_config:
        name = member_config.get('name')
        if not name:
            continue
        
        member_doc = {
            'name': name,
            'email': member_config.get('email'),
            'role': member_config.get('role'),
            'team': member_config.get('project'),
            'is_active': True,
            'created_at': datetime.utcnow()
        }
        
        result = await members_col.insert_one(member_doc)
        member_name_to_id[name] = result.inserted_id
        print(f"   ✅ {name}")
    
    print(f"\n   📊 Total: {len(member_name_to_id)} members created")
    return member_name_to_id


async def build_identifiers_collection(
    db, 
    members_config: List[Dict[str, Any]], 
    member_name_to_id: Dict[str, ObjectId]
) -> Dict[str, Dict[str, ObjectId]]:
    """
    Create member_identifiers collection
    
    Maps external identifiers (GitHub username, Slack ID, etc.) to member ObjectId
    
    Returns:
        Dict with structure: {source: {identifier: member_id}}
    """
    print("\n" + "="*70)
    print("2️⃣ Building Member Identifiers Collection")
    print("="*70)
    
    identifiers_col = db["member_identifiers"]
    
    # Drop existing indexes (avoid conflicts)
    try:
        await identifiers_col.drop_indexes()
        print(f"   🗑️  Dropped existing indexes")
    except Exception as e:
        print(f"   ℹ️  No existing indexes to drop: {e}")
    
    # Clear existing data
    await identifiers_col.delete_many({})
    print(f"   🗑️  Cleared existing identifiers")
    
    # Maps for quick lookup: {source: {identifier: member_id}}
    identifier_maps = {
        'github': {},
        'slack': {},
        'notion': {},
        'drive': {}
    }
    
    identifier_count = 0
    
    for member_config in members_config:
        name = member_config.get('name')
        if not name or name not in member_name_to_id:
            continue
        
        member_id = member_name_to_id[name]
        
        # GitHub identifier
        if member_config.get('github_id'):
            github_id = member_config['github_id']
            await identifiers_col.insert_one({
                'member_id': member_id,
                'member_name': name,
                'source': 'github',
                'identifier_type': 'username',
                'identifier_value': github_id,
                'created_at': datetime.utcnow()
            })
            identifier_maps['github'][github_id.lower()] = member_id
            identifier_count += 1
        
        # Slack identifier
        if member_config.get('slack_id'):
            slack_id = member_config['slack_id']
            # Slack ID can be email or user ID
            id_type = 'email' if '@' in slack_id else 'user_id'
            await identifiers_col.insert_one({
                'member_id': member_id,
                'member_name': name,
                'source': 'slack',
                'identifier_type': id_type,
                'identifier_value': slack_id,
                'created_at': datetime.utcnow()
            })
            identifier_maps['slack'][slack_id.lower()] = member_id
            identifier_count += 1
        
        # Notion identifier
        if member_config.get('notion_id'):
            notion_id = member_config['notion_id']
            await identifiers_col.insert_one({
                'member_id': member_id,
                'member_name': name,
                'source': 'notion',
                'identifier_type': 'email',
                'identifier_value': notion_id,
                'created_at': datetime.utcnow()
            })
            identifier_maps['notion'][notion_id.lower()] = member_id
            identifier_count += 1
        
        # Drive identifier (using email)
        if member_config.get('email'):
            email = member_config['email']
            await identifiers_col.insert_one({
                'member_id': member_id,
                'member_name': name,
                'source': 'drive',
                'identifier_type': 'email',
                'identifier_value': email,
                'created_at': datetime.utcnow()
            })
            identifier_maps['drive'][email.lower()] = member_id
            identifier_count += 1
    
    print(f"   📊 Total: {identifier_count} identifiers created")
    
    # Create indexes
    await identifiers_col.create_index([('member_id', 1)])
    await identifiers_col.create_index([('source', 1), ('identifier_value', 1)], unique=True)
    print(f"   🔍 Created indexes")
    
    return identifier_maps


async def build_activities_collection(
    db,
    identifier_maps: Dict[str, Dict[str, ObjectId]]
):
    """
    Create member_activities collection by scanning all source collections
    """
    print("\n" + "="*70)
    print("3️⃣ Building Member Activities Collection")
    print("="*70)
    
    activities_col = db["member_activities"]
    
    # Clear existing data
    await activities_col.delete_many({})
    print(f"   🗑️  Cleared existing activities")
    
    total_activities = 0
    
    # Process GitHub Commits
    print("\n   📂 Processing GitHub Commits...")
    commits_col = db["github_commits"]
    commit_count = 0
    
    async for commit in commits_col.find({}):
        author_login = commit.get('author_login', '').lower()
        member_id = identifier_maps['github'].get(author_login)
        
        if member_id:
            activity = {
                'member_id': member_id,
                'source': 'github',
                'activity_type': 'commit',
                'activity_id': f"github:commit:{commit['sha']}",
                'timestamp': commit.get('committed_at'),
                'metadata': {
                    'repository': commit.get('repository_name'),
                    'message': commit.get('message'),
                    'sha': commit.get('sha'),
                    'additions': commit.get('additions', 0),
                    'deletions': commit.get('deletions', 0),
                    'url': commit.get('url')
                },
                'created_at': datetime.utcnow()
            }
            await activities_col.insert_one(activity)
            commit_count += 1
    
    print(f"      ✅ {commit_count} commits")
    total_activities += commit_count
    
    # Process GitHub Pull Requests
    print("   📂 Processing GitHub Pull Requests...")
    prs_col = db["github_pull_requests"]
    pr_count = 0
    
    async for pr in prs_col.find({}):
        author_login = pr.get('author_login', '').lower()
        member_id = identifier_maps['github'].get(author_login)
        
        if member_id:
            activity = {
                'member_id': member_id,
                'source': 'github',
                'activity_type': 'pull_request',
                'activity_id': f"github:pr:{pr.get('repository_name')}:{pr.get('number')}",
                'timestamp': pr.get('created_at'),
                'metadata': {
                    'repository': pr.get('repository_name'),
                    'title': pr.get('title'),
                    'number': pr.get('number'),
                    'state': pr.get('state'),
                    'url': pr.get('url')
                },
                'created_at': datetime.utcnow()
            }
            await activities_col.insert_one(activity)
            pr_count += 1
    
    print(f"      ✅ {pr_count} pull requests")
    total_activities += pr_count
    
    # Process GitHub Issues
    print("   📂 Processing GitHub Issues...")
    issues_col = db["github_issues"]
    issue_count = 0
    
    async for issue in issues_col.find({}):
        author_login = issue.get('author_login', '').lower()
        member_id = identifier_maps['github'].get(author_login)
        
        if member_id:
            activity = {
                'member_id': member_id,
                'source': 'github',
                'activity_type': 'issue',
                'activity_id': f"github:issue:{issue.get('repository_name')}:{issue.get('number')}",
                'timestamp': issue.get('created_at'),
                'metadata': {
                    'repository': issue.get('repository_name'),
                    'title': issue.get('title'),
                    'number': issue.get('number'),
                    'state': issue.get('state'),
                    'url': issue.get('url')
                },
                'created_at': datetime.utcnow()
            }
            await activities_col.insert_one(activity)
            issue_count += 1
    
    print(f"      ✅ {issue_count} issues")
    total_activities += issue_count
    
    # Process Slack Messages
    print("   📂 Processing Slack Messages...")
    messages_col = db["slack_messages"]
    message_count = 0
    unmatched_count = 0
    
    # First, try to build a Slack ID mapping from actual messages
    slack_id_to_email = {}
    async for msg in messages_col.find({}):
        if msg.get('user_id') and msg.get('user_email'):
            slack_id_to_email[msg['user_id']] = msg['user_email'].lower()
    
    # Reset cursor
    async for msg in messages_col.find({}):
        user_id = msg.get('user_id', '').lower()
        user_email = msg.get('user_email', '').lower()
        
        # Try to match by Slack ID first, then by email
        member_id = identifier_maps['slack'].get(user_id)
        if not member_id and user_email:
            member_id = identifier_maps['slack'].get(user_email)
        
        if member_id:
            activity = {
                'member_id': member_id,
                'source': 'slack',
                'activity_type': 'message',
                'activity_id': f"slack:message:{msg.get('channel_id')}:{msg.get('ts')}",
                'timestamp': msg.get('timestamp'),
                'metadata': {
                    'channel': msg.get('channel_name'),
                    'channel_id': msg.get('channel_id'),
                    'text': msg.get('text', '')[:200],  # Truncate for index
                    'message_type': msg.get('message_type'),
                    'thread_ts': msg.get('thread_ts')
                },
                'created_at': datetime.utcnow()
            }
            await activities_col.insert_one(activity)
            message_count += 1
        else:
            unmatched_count += 1
    
    print(f"      ✅ {message_count} messages")
    if unmatched_count > 0:
        print(f"      ⚠️  {unmatched_count} messages from unmatched users (bots or external)")
    total_activities += message_count
    
    print(f"\n   📊 Total: {total_activities} activities created")
    
    # Create indexes
    await activities_col.create_index([('member_id', 1)])
    await activities_col.create_index([('source', 1), ('activity_type', 1)])
    await activities_col.create_index([('timestamp', -1)])
    await activities_col.create_index([('activity_id', 1)], unique=True)
    print(f"   🔍 Created indexes")
    
    return total_activities


async def verify_member_index(db):
    """Verify the created member index"""
    print("\n" + "="*70)
    print("4️⃣ Verifying Member Index")
    print("="*70)
    
    members_col = db["members"]
    identifiers_col = db["member_identifiers"]
    activities_col = db["member_activities"]
    
    member_count = await members_col.count_documents({})
    identifier_count = await identifiers_col.count_documents({})
    activity_count = await activities_col.count_documents({})
    
    print(f"\n   ✅ Members: {member_count}")
    print(f"   ✅ Identifiers: {identifier_count}")
    print(f"   ✅ Activities: {activity_count}")
    
    # Show top 5 most active members
    print("\n   📊 Top 5 Most Active Members:")
    pipeline = [
        {'$group': {'_id': '$member_id', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}},
        {'$limit': 5}
    ]
    
    async for doc in activities_col.aggregate(pipeline):
        member_id = doc['_id']
        count = doc['count']
        
        # Get member name
        member = await members_col.find_one({'_id': member_id})
        if member:
            print(f"      {member['name']}: {count} activities")
    
    # Show activity breakdown by source
    print("\n   📊 Activities by Source:")
    pipeline = [
        {'$group': {'_id': '$source', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ]
    
    async for doc in activities_col.aggregate(pipeline):
        source = doc['_id']
        count = doc['count']
        print(f"      {source}: {count} activities")


async def main():
    print("====================================================================")
    print("🏗️  Building Member Index for MongoDB")
    print("====================================================================")
    
    # Load environment
    env_path = project_root / '.env'
    load_dotenv(dotenv_path=env_path)
    
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    mongodb_database = os.getenv("MONGODB_DATABASE", "all_thing_eye_test")
    
    print(f"\n✅ MongoDB URI: {mongodb_uri}")
    print(f"✅ Database: {mongodb_database}")
    
    # Initialize MongoDB
    mongo_config = {
        'uri': mongodb_uri,
        'database': mongodb_database,
    }
    mongo_manager = get_mongo_manager(mongo_config)
    mongo_manager.connect_async()
    db = mongo_manager.async_db
    
    try:
        # Step 1: Load members config
        members_config = await load_members_config()
        print(f"\n✅ Loaded {len(members_config)} members from config")
        
        # Step 2: Build members collection
        member_name_to_id = await build_members_collection(db, members_config)
        
        # Step 3: Build identifiers collection
        identifier_maps = await build_identifiers_collection(db, members_config, member_name_to_id)
        
        # Step 4: Build activities collection
        total_activities = await build_activities_collection(db, identifier_maps)
        
        # Step 5: Verify results
        await verify_member_index(db)
        
        print("\n" + "="*70)
        print("✅ Member Index Build Complete!")
        print("="*70)
        print(f"\n   Members: {len(member_name_to_id)}")
        print(f"   Activities: {total_activities}")
        print(f"   Database: {mongodb_database}")
        print("\n" + "="*70)
        
    except Exception as e:
        print(f"\n❌ Error building member index: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

