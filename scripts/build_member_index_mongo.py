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
    
    active_count = 0
    inactive_count = 0
    
    for member_config in members_config:
        name = member_config.get('name')
        if not name:
            continue
        
        # Parse is_active field (default True for backwards compatibility)
        is_active = member_config.get('is_active', True)
        
        # Parse resigned_at field (ISO format string or None)
        resigned_at_str = member_config.get('resigned_at')
        resigned_at = None
        if resigned_at_str:
            try:
                resigned_at = datetime.fromisoformat(resigned_at_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                print(f"   ⚠️  Invalid resigned_at date for {name}: {resigned_at_str}")
        
        # Parse project(s) - can be single string or array
        project_value = member_config.get('project')
        projects = []
        if project_value:
            if isinstance(project_value, list):
                projects = project_value
            elif isinstance(project_value, str):
                # Handle comma-separated projects
                projects = [p.strip() for p in project_value.split(',') if p.strip()]
        
        member_doc = {
            'name': name,
            'email': member_config.get('email'),
            'role': member_config.get('role'),
            'team': member_config.get('project') if isinstance(member_config.get('project'), str) else None,
            'projects': projects,  # Array of project keys
            'github_username': member_config.get('github_id'),
            'slack_id': member_config.get('slack_id'),
            'notion_id': member_config.get('notion_id'),
            'eoa_address': member_config.get('eoa_address'),
            'recording_name': member_config.get('recording_name'),
            'is_active': is_active,
            'resigned_at': resigned_at,
            'resignation_reason': member_config.get('resignation_reason'),
            'created_at': datetime.utcnow()
        }
        
        result = await members_col.insert_one(member_doc)
        member_name_to_id[name] = result.inserted_id
        
        # Status indicator
        if is_active:
            print(f"   ✅ {name}")
            active_count += 1
        else:
            print(f"   ⏸️  {name} (inactive)")
            inactive_count += 1
    
    print(f"\n   📊 Total: {len(member_name_to_id)} members created")
    print(f"      - Active: {active_count}")
    print(f"      - Inactive: {inactive_count}")
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
            
            # IMPORTANT: Also find and add actual Slack user_id from slack_messages
            # Because slack_messages may not have user_email populated
            if '@' in slack_id:  # If slack_id is an email, find the actual user_id
                slack_msg = await db['slack_messages'].find_one({
                    '$or': [
                        {'user_email': slack_id},
                        {'user_name': name.lower()}
                    ]
                })
                if slack_msg and slack_msg.get('user_id'):
                    actual_user_id = slack_msg['user_id']
                    # Add user_id identifier as well
                    await identifiers_col.insert_one({
                        'member_id': member_id,
                        'member_name': name,
                        'source': 'slack',
                        'identifier_type': 'user_id',
                        'identifier_value': actual_user_id,
                        'created_at': datetime.utcnow()
                    })
                    identifier_maps['slack'][actual_user_id] = member_id
                    identifier_count += 1
                    print(f"      ➕ Found Slack user_id: {actual_user_id} for {name}")
        
        # Notion identifier
        if member_config.get('notion_id'):
            notion_id = member_config['notion_id']
            
            # Try to find the actual Notion user UUID from notion_users collection
            # This is crucial because pages use UUIDs, not emails
            notion_user = await db["notion_users"].find_one({
                '$or': [
                    {'email': notion_id},
                    {'name': {'$regex': f'^{name}', '$options': 'i'}}
                ]
            })
            
            if notion_user and notion_user.get('user_id'):
                actual_notion_uuid = notion_user['user_id']
                await identifiers_col.insert_one({
                    'member_id': member_id,
                    'member_name': name,
                    'source': 'notion',
                    'identifier_type': 'user_id',
                    'identifier_value': actual_notion_uuid,
                    'created_at': datetime.utcnow()
                })
                identifier_maps['notion'][actual_notion_uuid] = member_id
                identifier_count += 1
                print(f"      ➕ Found Notion UUID: {actual_notion_uuid} for {name}")
            
            # Also add the notion_id from config (could be email or UUID)
            id_type = 'email' if '@' in notion_id else 'user_id'
            await identifiers_col.insert_one({
                'member_id': member_id,
                'member_name': name,
                'source': 'notion',
                'identifier_type': id_type,
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
        
        # Recording name identifier (for meeting recordings)
        if member_config.get('recording_name'):
            recording_name = member_config['recording_name']
            await identifiers_col.insert_one({
                'member_id': member_id,
                'member_name': name,
                'source': 'recordings',
                'identifier_type': 'recording_name',
                'identifier_value': recording_name,
                'created_at': datetime.utcnow()
            })
            identifier_count += 1
            print(f"      ➕ Added recording_name: '{recording_name}' for {name}")
    
    print(f"   📊 Total: {identifier_count} identifiers created")
    
    # Create indexes
    await identifiers_col.create_index([('member_id', 1)])
    await identifiers_col.create_index([('source', 1), ('identifier_value', 1)], unique=True)
    print(f"   🔍 Created indexes")
    
    return identifier_maps


# Note: build_activities_collection function removed
# member_activities collection is no longer used - activities are queried directly from source collections


async def verify_member_index(db):
    """Verify the created member index"""
    print("\n" + "="*70)
    print("4️⃣ Verifying Member Index")
    print("="*70)
    
    members_col = db["members"]
    identifiers_col = db["member_identifiers"]
    
    member_count = await members_col.count_documents({})
    identifier_count = await identifiers_col.count_documents({})
    
    print(f"\n   ✅ Members: {member_count}")
    print(f"   ✅ Identifiers: {identifier_count}")
    
    # Show identifier breakdown by source
    print("\n   📊 Identifiers by Source:")
    pipeline = [
        {'$group': {'_id': '$source', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ]
    
    async for doc in identifiers_col.aggregate(pipeline):
        source = doc['_id']
        count = doc['count']
        print(f"      {source}: {count} identifiers")


async def build_member_index(mongo_manager=None, incremental=False):
    """
    Build or update member index
    
    Args:
        mongo_manager: Optional MongoManager instance. If None, creates a new one.
        incremental: If True, only updates (currently not implemented - always does full rebuild)
    
    Note:
        This function always does a full rebuild by reading all source collections
        and recreating the member_activities collection. This ensures that:
        1. New members added to members.yaml are properly mapped to existing activities
        2. Member identifier changes are reflected in all activities
        3. All activities are re-mapped with the latest member information
    """
    if mongo_manager is None:
        # Load environment
        env_path = project_root / '.env'
        load_dotenv(dotenv_path=env_path)
        
        mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        mongodb_database = os.getenv("MONGODB_DATABASE", "all_thing_eye_test")
        
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
        
        # Step 4: Note - member_activities collection removed
        # Activities are now queried directly from source collections (github_commits, slack_messages, etc.)
        
        # Step 5: Verify results
        await verify_member_index(db)
        
        print("\n" + "="*70)
        print("✅ Member Index Build Complete!")
        print("="*70)
        print(f"\n   Members: {len(member_name_to_id)}")
        print(f"   Identifiers: {sum(len(m) for m in identifier_maps.values())}")
        print(f"   Database: {mongo_manager.async_db.name}")
        print("\n" + "="*70)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error building member index: {e}")
        import traceback
        traceback.print_exc()
        raise


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
    
    try:
        await build_member_index(mongo_manager)
        return 0
    except Exception as e:
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

