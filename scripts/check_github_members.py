#!/usr/bin/env python3
"""
Check GitHub username mappings in member_identifiers
"""

import sys
import asyncio
from pathlib import Path
import os

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.core.config import Config
from src.core.mongo_manager import get_mongo_manager

async def check_github_members():
    """Check GitHub username mappings"""
    print("=" * 80)
    print("🔍 CHECKING GITHUB USERNAME MAPPINGS")
    print("=" * 80)
    
    config = Config()
    mongodb_config = {
        'uri': os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
        'database': os.getenv('MONGODB_DATABASE', config.get('mongodb.database', 'all_thing_eye_test'))
    }
    mongo_manager = get_mongo_manager(mongodb_config)
    db = mongo_manager.async_db
    
    try:
        # Get all GitHub identifiers
        print("\n📋 GitHub username mappings:")
        cursor = db['member_identifiers'].find({
            'source': 'github',
            'identifier_type': 'username'
        })
        
        mappings = []
        async for doc in cursor:
            mappings.append({
                'member': doc.get('member_name'),
                'github': doc.get('identifier_value')
            })
        
        # Sort by member name
        mappings.sort(key=lambda x: x['member'])
        
        for m in mappings:
            print(f"   {m['member']:20} → {m['github']}")
        
        print(f"\n   Total: {len(mappings)} GitHub usernames mapped")
        
        # Check specific usernames from the PR
        print("\n🔍 Checking specific usernames from sample PR:")
        test_usernames = ['cy00r', '0x6e616d', 'SonYoungsung']
        
        for username in test_usernames:
            doc = await db['member_identifiers'].find_one({
                'source': 'github',
                'identifier_type': 'username',
                'identifier_value': username
            })
            
            if doc:
                print(f"   ✅ {username:20} → {doc.get('member_name')}")
            else:
                print(f"   ❌ {username:20} → NOT FOUND")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if hasattr(mongo_manager, 'close'):
            mongo_manager.close()

if __name__ == "__main__":
    asyncio.run(check_github_members())

