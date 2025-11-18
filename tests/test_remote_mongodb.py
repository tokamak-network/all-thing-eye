#!/usr/bin/env python3
"""
Test remote MongoDB connection
"""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
import sys


def test_mongodb_connection():
    """Test connection to remote MongoDB"""
    
    # Connection details
    host = "43.201.95.192"
    port = 27017
    username = "ale"
    password = "aleson123#"
    auth_db = "ati"
    
    # Build MongoDB URI
    mongodb_uri = f"mongodb://{username}:{password}@{host}:{port}/?authSource={auth_db}"
    
    print("=" * 80)
    print("🔍 Testing Remote MongoDB Connection")
    print("=" * 80)
    print(f"Host: {host}:{port}")
    print(f"User: {username}")
    print(f"Auth DB: {auth_db}")
    print()
    
    try:
        # 1. Test connection
        print("1️⃣ Testing connection...")
        client = MongoClient(
            mongodb_uri,
            serverSelectionTimeoutMS=5000,  # 5 seconds timeout
            connectTimeoutMS=5000
        )
        
        # Force connection
        client.admin.command('ping')
        print("   ✅ Connection successful!")
        
        # 2. List databases
        print("\n2️⃣ Listing databases...")
        db_list = client.list_database_names()
        print(f"   ✅ Found {len(db_list)} databases:")
        for db_name in db_list:
            print(f"      - {db_name}")
        
        # 3. Test read access on 'ati' database
        print("\n3️⃣ Testing read access on 'ati' database...")
        db = client['ati']
        collections = db.list_collection_names()
        print(f"   ✅ Found {len(collections)} collections:")
        for coll_name in collections[:10]:  # Show first 10
            count = db[coll_name].count_documents({})
            print(f"      - {coll_name}: {count} documents")
        if len(collections) > 10:
            print(f"      ... and {len(collections) - 10} more")
        
        # 4. Test write access (insert and delete)
        print("\n4️⃣ Testing write access...")
        test_collection = db['_test_connection']
        
        # Insert test document
        test_doc = {'test': 'connection', 'timestamp': 'now'}
        result = test_collection.insert_one(test_doc)
        print(f"   ✅ Insert successful! ID: {result.inserted_id}")
        
        # Read back
        found_doc = test_collection.find_one({'_id': result.inserted_id})
        print(f"   ✅ Read successful! Doc: {found_doc}")
        
        # Delete test document
        test_collection.delete_one({'_id': result.inserted_id})
        print(f"   ✅ Delete successful!")
        
        # 5. Test on 'all_thing_eye' database (our target database)
        print("\n5️⃣ Testing 'all_thing_eye' database...")
        target_db = client['all_thing_eye']
        
        # Check if it exists
        if 'all_thing_eye' in db_list:
            collections = target_db.list_collection_names()
            print(f"   ✅ Database exists with {len(collections)} collections")
            if collections:
                for coll_name in collections[:5]:
                    count = target_db[coll_name].count_documents({})
                    print(f"      - {coll_name}: {count} documents")
        else:
            print("   ⚠️  Database 'all_thing_eye' does not exist yet")
            print("      Will be created on first write operation")
        
        # Test write to all_thing_eye
        print("\n6️⃣ Testing write to 'all_thing_eye' database...")
        test_coll = target_db['_test_connection']
        test_doc = {'test': 'write_access', 'timestamp': 'now'}
        result = test_coll.insert_one(test_doc)
        print(f"   ✅ Insert successful! ID: {result.inserted_id}")
        
        # Cleanup
        test_coll.delete_one({'_id': result.inserted_id})
        print(f"   ✅ Cleanup successful!")
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)
        print("\n📋 Summary:")
        print(f"   ✅ Connection: OK")
        print(f"   ✅ Read access: OK")
        print(f"   ✅ Write access: OK")
        print(f"   ✅ Target database 'all_thing_eye': {'EXISTS' if 'all_thing_eye' in db_list else 'READY TO CREATE'}")
        print()
        
        client.close()
        return True
        
    except ConnectionFailure as e:
        print(f"\n❌ Connection failed: {e}")
        print("\n💡 Possible issues:")
        print("   - Firewall blocking connection")
        print("   - MongoDB not running on remote host")
        print("   - Incorrect host/port")
        return False
        
    except OperationFailure as e:
        print(f"\n❌ Authentication failed: {e}")
        print("\n💡 Possible issues:")
        print("   - Incorrect username/password")
        print("   - User doesn't have required permissions")
        print("   - Incorrect authentication database")
        return False
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_mongodb_connection()
    sys.exit(0 if success else 1)

