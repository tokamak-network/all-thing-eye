#!/usr/bin/env python3
"""
Check PR structure in MongoDB
"""

import sys
import asyncio
from pathlib import Path
import os
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.core.config import Config
from src.core.mongo_manager import get_mongo_manager

async def check_pr_structure():
    """Check actual PR structure"""
    print("=" * 80)
    print("🔍 CHECKING PR STRUCTURE IN DB")
    print("=" * 80)
    
    config = Config()
    mongodb_config = {
        'uri': os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
        'database': os.getenv('MONGODB_DATABASE', config.get('mongodb.database', 'all_thing_eye_test'))
    }
    mongo_manager = get_mongo_manager(mongodb_config)
    db = mongo_manager.async_db
    
    try:
        # Get a PR with reviews
        pr = await db['github_pull_requests'].find_one({
            'reviews': {'$exists': True, '$ne': []}
        })
        
        if pr:
            print("\n📋 Sample PR Document:")
            print(f"   Number: {pr.get('number')}")
            print(f"   Title: {pr.get('title', 'No title')}")
            print(f"\n   🔑 All keys in document:")
            for key in pr.keys():
                value = pr[key]
                if key == '_id':
                    print(f"      {key}: {value}")
                elif key == 'reviews':
                    print(f"      {key}: {len(value)} reviews")
                else:
                    print(f"      {key}: {value}")
            
            print(f"\n   📊 Full document (JSON):")
            # Remove _id for cleaner output
            pr_dict = {k: v for k, v in pr.items() if k != '_id'}
            print(json.dumps(pr_dict, indent=2, default=str))
        else:
            print("   ❌ No PRs found")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if hasattr(mongo_manager, 'close'):
            mongo_manager.close()

if __name__ == "__main__":
    asyncio.run(check_pr_structure())

