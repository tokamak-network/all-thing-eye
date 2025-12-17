#!/usr/bin/env python3
"""
Test the collaboration calculation logic directly
"""

import sys
import asyncio
from pathlib import Path
import os
from datetime import datetime, timedelta
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.core.config import Config
from src.core.mongo_manager import get_mongo_manager

async def test_collaboration():
    """Test collaboration calculation for Ale"""
    print("=" * 80)
    print("🔍 TESTING COLLABORATION LOGIC FOR ALE")
    print("=" * 80)
    
    config = Config()
    mongodb_config = {
        'uri': os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
        'database': os.getenv('MONGODB_DATABASE', config.get('mongodb.database', 'all_thing_eye_test'))
    }
    mongo_manager = get_mongo_manager(mongodb_config)
    db = mongo_manager.async_db
    
    try:
        member_name = "Ale"
        days = 90
        
        # 1. Get GitHub username
        print(f"\n1️⃣ Getting GitHub username for {member_name}")
        member_id_doc = await db['member_identifiers'].find_one({
            'member_name': member_name,
            'source': 'github',
            'identifier_type': 'username'
        })
        
        if not member_id_doc:
            print(f"   ❌ No GitHub identifier found")
            return
        
        github_username = member_id_doc.get('identifier_value')
        print(f"   ✅ GitHub username: {github_username}")
        
        # 2. Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        print(f"\n2️⃣ Date range: {start_date.date()} to {end_date.date()}")
        
        # 3. Find PRs where member left reviews
        print(f"\n3️⃣ Finding PRs where {github_username} left reviews")
        
        prs = db['github_pull_requests'].find({
            'created_at': {'$gte': start_date, '$lte': end_date},
            '$or': [
                {'author': github_username},
                {'reviews.reviewer': github_username}
            ]
        })
        
        collaborations = defaultdict(lambda: {
            'name': '',
            'total_score': 0.0,
            'interaction_count': 0,
            'details': [],
            'common_projects': set(),
            'first_interaction': None,
            'last_interaction': None
        })
        
        pr_count = 0
        async for pr in prs:
            pr_count += 1
            author = pr.get('author', '')
            reviewers = set()
            
            for review in pr.get('reviews', []):
                reviewer = review.get('reviewer')
                if reviewer:
                    reviewers.add(reviewer)
            
            print(f"\n   PR #{pr.get('number')}: {pr.get('title', '')[:40]}...")
            print(f"      Author: {author}")
            print(f"      Reviewers: {reviewers}")
            
            # If member is reviewer, collaborator is author
            if github_username in reviewers and author != github_username:
                print(f"      → Ale reviewed this PR")
                
                # Convert GitHub username to member name
                author_member_doc = await db['member_identifiers'].find_one({
                    'source': 'github',
                    'identifier_type': 'username',
                    'identifier_value': author
                })
                
                if author_member_doc:
                    author_member_name = author_member_doc.get('member_name')
                    print(f"      → Author '{author}' mapped to '{author_member_name}'")
                    
                    # Add collaboration
                    collab = collaborations[author_member_name]
                    if not collab['name']:
                        collab['name'] = author_member_name
                    collab['total_score'] += 3.0
                    collab['interaction_count'] += 1
                    
                else:
                    print(f"      ⚠️ Author '{author}' NOT in member_identifiers")
        
        print(f"\n4️⃣ Collaboration Results:")
        print(f"   Total PRs found: {pr_count}")
        print(f"   Total collaborators: {len(collaborations)}")
        
        for name, data in collaborations.items():
            print(f"\n   Collaborator: '{name}'")
            print(f"      Total score: {data['total_score']}")
            print(f"      Interactions: {data['interaction_count']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if hasattr(mongo_manager, 'close'):
            mongo_manager.close()

if __name__ == "__main__":
    asyncio.run(test_collaboration())

