#!/usr/bin/env python3
"""
Check PR reviews in MongoDB for a specific member.
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.core.config import Config
from src.core.mongo_manager import MongoDBManager, get_mongo_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)
UTC = ZoneInfo("UTC")

async def check_pr_reviews(member_name: str = "Ale"):
    """Check PR reviews for a specific member"""
    print("=" * 80)
    print(f"🔍 CHECKING PR REVIEWS FOR {member_name}")
    print("=" * 80)
    
    config = Config()
    mongodb_config = {
        'uri': os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
        'database': os.getenv('MONGODB_DATABASE', config.get('mongodb.database', 'all_thing_eye_test'))
    }
    mongo_manager = get_mongo_manager(mongodb_config)
    db = mongo_manager.async_db
    
    try:
        # 1. Get GitHub username for the member
        print(f"\n1️⃣ Finding GitHub username for {member_name}")
        member_id_doc = await db['member_identifiers'].find_one({
            'member_name': member_name,
            'source': 'github',
            'identifier_type': 'username'
        })
        
        if not member_id_doc:
            print(f"   ❌ No GitHub identifier found for {member_name}")
            return
        
        github_username = member_id_doc.get('identifier_value')
        print(f"   ✅ GitHub username: {github_username}")
        
        # 2. Find PRs where member is author or reviewer
        print(f"\n2️⃣ Searching for PRs involving {github_username}")
        
        # PRs authored by member
        prs_authored = await db['github_pull_requests'].count_documents({
            'author_login': github_username
        })
        print(f"   📝 PRs authored: {prs_authored}")
        
        # PRs with any reviews
        prs_with_reviews = await db['github_pull_requests'].count_documents({
            'reviews': {'$exists': True, '$ne': []}
        })
        print(f"   💬 PRs with reviews (total): {prs_with_reviews}")
        
        # 3. Sample a PR with reviews to check structure
        print(f"\n3️⃣ Examining PR review structure")
        sample_pr = await db['github_pull_requests'].find_one({
            'reviews': {'$exists': True, '$ne': []}
        })
        
        if sample_pr:
            print(f"   📋 Sample PR #{sample_pr.get('number')} in {sample_pr.get('repository_name')}")
            print(f"   👤 Author: {sample_pr.get('author_login')}")
            print(f"   💬 Reviews count: {len(sample_pr.get('reviews', []))}")
            
            # Check review structure
            if sample_pr.get('reviews'):
                first_review = sample_pr['reviews'][0]
                print(f"\n   📊 First review structure:")
                print(f"      Keys: {list(first_review.keys())}")
                
                # Pretty print the review structure
                review_json = json.dumps(first_review, indent=6, default=str)
                print(f"      Data:\n{review_json}")
        else:
            print("   ⚠️ No PRs with reviews found in database")
        
        # 4. Find PRs where member left reviews
        print(f"\n4️⃣ Searching for reviews BY {github_username}")
        
        # Try different possible field structures
        queries = [
            {'reviews.user.login': github_username},
            {'reviews.reviewer': github_username},
            {'reviews.author.login': github_username},
        ]
        
        for idx, query in enumerate(queries, 1):
            count = await db['github_pull_requests'].count_documents(query)
            print(f"   Query {idx} {query}: {count} PRs")
            
            if count > 0:
                # Show a sample
                sample = await db['github_pull_requests'].find_one(query)
                print(f"      ✅ Sample PR: #{sample.get('number')} in {sample.get('repository_name')}")
                print(f"      ✅ PR Author: {sample.get('author_login')}")
        
        # 5. Find PRs where member is the author (to see who reviewed their PRs)
        print(f"\n5️⃣ PRs authored by {github_username} (to see reviewers)")
        
        prs_by_member = db['github_pull_requests'].find({
            'author_login': github_username,
            'reviews': {'$exists': True, '$ne': []}
        }).limit(5)
        
        async for pr in prs_by_member:
            print(f"\n   📝 PR #{pr.get('number')}: {pr.get('title')}")
            print(f"      Repository: {pr.get('repository_name')}")
            print(f"      Reviews: {len(pr.get('reviews', []))}")
            
            for review in pr.get('reviews', [])[:3]:  # Show first 3 reviews
                # Try different field structures
                reviewer = (
                    review.get('user', {}).get('login') or
                    review.get('reviewer') or
                    review.get('author', {}).get('login') or
                    'Unknown'
                )
                state = review.get('state', 'unknown')
                print(f"         - {reviewer}: {state}")
        
        print("\n" + "=" * 80)
        print("✅ CHECK COMPLETE")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {e}", exc_info=True)
    finally:
        if hasattr(mongo_manager, 'close'):
            mongo_manager.close()


if __name__ == "__main__":
    member = sys.argv[1] if len(sys.argv) > 1 else "Ale"
    asyncio.run(check_pr_reviews(member))

