#!/usr/bin/env python3
"""
Check MongoDB Data
Quick script to verify MongoDB collections and data counts
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings
from src.core.mongo_manager import get_mongo_manager


async def check_data():
    """Check MongoDB collections and data counts"""
    print("====================================================================")
    print("📊 MongoDB Data Check")
    print("====================================================================")
    
    # Load settings
    settings.load_env()
    
    # Initialize MongoDB Manager
    mongo_config = {
        'uri': settings.mongodb.uri,
        'database': settings.mongodb.database,
    }
    
    manager = get_mongo_manager(mongo_config)
    await manager.connect_async()
    
    try:
        db = manager.get_database_async()
        
        print(f"\n🔗 Connected to: {settings.mongodb.uri}")
        print(f"📂 Database: {settings.mongodb.database}")
        print("\n" + "=" * 60)
        print("Collections and Document Counts:")
        print("=" * 60)
        
        collections = await db.list_collection_names()
        total_docs = 0
        
        if not collections:
            print("⚠️  No collections found!")
        else:
            for coll_name in sorted(collections):
                count = await db[coll_name].count_documents({})
                if count > 0:
                    total_docs += count
                    print(f"  ✅ {coll_name:<40} {count:>10,} docs")
                else:
                    print(f"  ⚪ {coll_name:<40} {count:>10,} docs")
        
        print("=" * 60)
        print(f"Total documents: {total_docs:,}")
        print("=" * 60)
        
        # Sample data from a few collections
        if total_docs > 0:
            print("\n" + "=" * 60)
            print("Sample Data:")
            print("=" * 60)
            
            # Check GitHub commits
            commits_coll = db.github_commits
            commit_count = await commits_coll.count_documents({})
            if commit_count > 0:
                print(f"\n📝 GitHub Commits (sample):")
                async for commit in commits_coll.find().limit(3):
                    print(f"  - {commit.get('sha', '')[:10]}: {commit.get('message', '')[:50]}...")
                    print(f"    Author: {commit.get('author_login')}, Repo: {commit.get('repository_name')}")
            
            # Check Slack messages
            messages_coll = db.slack_messages
            message_count = await messages_coll.count_documents({})
            if message_count > 0:
                print(f"\n💬 Slack Messages (sample):")
                async for msg in messages_coll.find().limit(3):
                    print(f"  - {msg.get('user_name')}: {msg.get('text', '')[:50]}...")
                    print(f"    Channel: {msg.get('channel_name')}, Type: {msg.get('message_type')}")
            
            # Check Members
            members_coll = db.members
            member_count = await members_coll.count_documents({})
            if member_count > 0:
                print(f"\n👥 Members (sample):")
                async for member in members_coll.find().limit(5):
                    print(f"  - {member.get('name')}: {member.get('email')}")
        
        print("\n====================================================================")
        print("✅ Data check completed!")
        print("====================================================================")
        
    finally:
        await manager.disconnect_async()


if __name__ == "__main__":
    asyncio.run(check_data())

