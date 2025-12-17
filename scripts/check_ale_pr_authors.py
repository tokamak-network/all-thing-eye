#!/usr/bin/env python3
"""
Check authors of PRs where Ale left reviews
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

async def check_ale_pr_authors():
    """Check authors of PRs where Ale left reviews"""
    print("=" * 80)
    print("🔍 CHECKING PR AUTHORS WHERE ALE LEFT REVIEWS")
    print("=" * 80)
    
    config = Config()
    mongodb_config = {
        'uri': os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
        'database': os.getenv('MONGODB_DATABASE', config.get('mongodb.database', 'all_thing_eye_test'))
    }
    mongo_manager = get_mongo_manager(mongodb_config)
    db = mongo_manager.async_db
    
    try:
        # Find PRs where Ale (SonYoungsung) left reviews
        print("\n📋 PRs where SonYoungsung left reviews:")
        
        cursor = db['github_pull_requests'].find({
            'reviews.reviewer': 'SonYoungsung'
        })
        
        pr_count = 0
        async for pr in cursor:
            pr_count += 1
            author = pr.get('author', 'NO AUTHOR FIELD')
            repo = pr.get('repository', 'NO REPO FIELD')
            number = pr.get('number', 'NO NUMBER')
            title = pr.get('title', 'NO TITLE')
            
            # Count Ale's reviews
            ale_review_count = sum(1 for r in pr.get('reviews', []) if r.get('reviewer') == 'SonYoungsung')
            
            print(f"\n   PR #{number}: {title[:50]}...")
            print(f"      Repository: {repo}")
            print(f"      Author: '{author}' (type: {type(author).__name__})")
            print(f"      Ale's reviews: {ale_review_count}")
            
            # Check if author is in member_identifiers
            if author and author != 'NO AUTHOR FIELD':
                member_doc = await db['member_identifiers'].find_one({
                    'source': 'github',
                    'identifier_type': 'username',
                    'identifier_value': author
                })
                
                if member_doc:
                    print(f"      ✅ Author mapped to: {member_doc.get('member_name')}")
                else:
                    print(f"      ❌ Author NOT in member_identifiers")
        
        print(f"\n📊 Total PRs: {pr_count}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if hasattr(mongo_manager, 'close'):
            mongo_manager.close()

if __name__ == "__main__":
    asyncio.run(check_ale_pr_authors())

