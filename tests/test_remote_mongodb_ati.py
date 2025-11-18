#!/usr/bin/env python3
"""
Test remote MongoDB connection using 'ati' database
"""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
import sys


def test_ati_database():
    """Test connection to remote MongoDB using ati database"""
    
    # Connection details
    host = "43.201.95.192"
    port = 27017
    username = "ale"
    password = "aleson123#"
    auth_db = "ati"
    
    # Build MongoDB URI
    mongodb_uri = f"mongodb://{username}:{password}@{host}:{port}/?authSource={auth_db}"
    
    print("=" * 80)
    print("🔍 Testing with 'ati' Database (Temporary)")
    print("=" * 80)
    
    try:
        client = MongoClient(
            mongodb_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000
        )
        
        # Use 'ati' database instead of 'all_thing_eye'
        db = client['ati']
        
        print("\n1️⃣ Testing collections in 'ati' database...")
        print("   We can create collections with prefixes to avoid conflicts:")
        print()
        
        # Example collections with prefix
        test_collections = [
            'ate_members',  # 'ate' = All Thing Eye
            'ate_github_commits',
            'ate_github_pull_requests',
            'ate_slack_messages',
            'ate_notion_pages',
        ]
        
        print("   Suggested collection names:")
        for coll_name in test_collections:
            print(f"      - {coll_name}")
        
        print("\n2️⃣ Testing write to prefixed collection...")
        test_coll = db['ate_test_connection']
        
        # Insert
        result = test_coll.insert_one({'test': 'prefixed_collection', 'timestamp': 'now'})
        print(f"   ✅ Insert successful! ID: {result.inserted_id}")
        
        # Read
        doc = test_coll.find_one({'_id': result.inserted_id})
        print(f"   ✅ Read successful! Doc: {doc}")
        
        # Cleanup
        test_coll.delete_one({'_id': result.inserted_id})
        print(f"   ✅ Cleanup successful!")
        
        print("\n" + "=" * 80)
        print("✅ 'ati' DATABASE CAN BE USED AS TEMPORARY SOLUTION")
        print("=" * 80)
        print("\n📋 Recommendation:")
        print("   Use collection prefix 'ate_' to avoid conflicts")
        print("   Example: ate_members, ate_github_commits, etc.")
        print()
        
        client.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_ati_database()
    sys.exit(0 if success else 1)

