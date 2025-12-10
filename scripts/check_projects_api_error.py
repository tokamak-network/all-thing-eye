#!/usr/bin/env python3
"""
Script to check projects API error logs - Run inside Docker container
Usage: docker exec -it all-thing-eye-backend python scripts/check_projects_api_error.py
"""

import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, '/app')

def check_mongodb_connection():
    """Check MongoDB connection and document structure"""
    print("=" * 50)
    print("1. Checking MongoDB connection...")
    print("=" * 50)
    
    try:
        from backend.main import mongo_manager
        
        mongo_manager.connect_sync()
        db = mongo_manager.get_database_sync()
        projects_collection = db['projects']
        
        count = projects_collection.count_documents({})
        print(f"✅ MongoDB connection: OK")
        print(f"📊 Projects collection count: {count}")
        
        # Check sample document structure
        sample = projects_collection.find_one({})
        if sample:
            print(f"\n📄 Sample document keys: {list(sample.keys())}")
            print(f"   created_at: {sample.get('created_at')} (type: {type(sample.get('created_at'))})")
            print(f"   updated_at: {sample.get('updated_at')} (type: {type(sample.get('updated_at'))})")
            print(f"   repositories_synced_at: {sample.get('repositories_synced_at')} (type: {type(sample.get('repositories_synced_at'))})")
            
            # Show all datetime fields
            print(f"\n🔍 All datetime fields in sample:")
            for key, value in sample.items():
                if isinstance(value, datetime):
                    print(f"   {key}: {value} (datetime)")
                elif value is None:
                    print(f"   {key}: None")
        else:
            print("⚠️  No documents found in projects collection")
        
        return True
        
    except Exception as e:
        print(f"❌ MongoDB connection error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_datetime_handling():
    """Test the datetime handling logic from the API"""
    print("\n" + "=" * 50)
    print("2. Testing datetime handling logic...")
    print("=" * 50)
    
    try:
        from backend.api.v1.projects_management import get_mongo
        
        mongo = get_mongo()
        db = mongo.get_database_sync()
        projects_collection = db['projects']
        
        query = {'is_active': True}
        cursor = projects_collection.find(query).sort('name', 1)
        
        projects = []
        errors = []
        
        for doc in cursor:
            try:
                # Test the same logic as in the API
                created_at = doc.get('created_at')
                if not isinstance(created_at, datetime):
                    created_at = datetime.utcnow()
                
                updated_at = doc.get('updated_at')
                if not isinstance(updated_at, datetime):
                    updated_at = datetime.utcnow()
                
                repositories_synced_at = doc.get('repositories_synced_at')
                if repositories_synced_at is not None and not isinstance(repositories_synced_at, datetime):
                    repositories_synced_at = None
                
                print(f"\n✅ Processing project: {doc.get('key')}")
                print(f"   created_at: {created_at} (type: {type(created_at).__name__})")
                print(f"   updated_at: {updated_at} (type: {type(updated_at).__name__})")
                print(f"   repositories_synced_at: {repositories_synced_at} (type: {type(repositories_synced_at).__name__ if repositories_synced_at else 'NoneType'})")
                
                # Try to create ProjectResponse-like structure
                project_data = {
                    'key': doc.get('key'),
                    'name': doc.get('name'),
                    'created_at': created_at,
                    'updated_at': updated_at,
                    'repositories_synced_at': repositories_synced_at
                }
                
                projects.append(project_data)
                
            except Exception as e:
                error_msg = f"Error processing project {doc.get('key', 'unknown')}: {e}"
                print(f"\n❌ {error_msg}")
                errors.append(error_msg)
                import traceback
                traceback.print_exc()
        
        print(f"\n📊 Summary:")
        print(f"   Successfully processed: {len(projects)} projects")
        if errors:
            print(f"   Errors: {len(errors)}")
            for error in errors:
                print(f"     - {error}")
        else:
            print(f"   ✅ No errors found")
        
        return len(errors) == 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_endpoint():
    """Test the actual API endpoint"""
    print("\n" + "=" * 50)
    print("3. Testing API endpoint (if server is running)...")
    print("=" * 50)
    
    try:
        import requests
        
        url = "http://localhost:8000/api/v1/projects-management/projects?active_only=true"
        response = requests.get(url, timeout=5)
        
        print(f"   URL: {url}")
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success! Found {data.get('total', 0)} projects")
        else:
            print(f"   ❌ Error: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
        
        return response.status_code == 200
        
    except requests.exceptions.ConnectionError:
        print("   ⚠️  Backend server is not running or not accessible")
        return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    """Main function"""
    print("\n" + "=" * 50)
    print("Projects API Error Debugging Script")
    print("=" * 50)
    print("\nRunning inside Docker container...")
    
    # Check MongoDB
    mongo_ok = check_mongodb_connection()
    
    if not mongo_ok:
        print("\n❌ MongoDB check failed. Please check your connection.")
        sys.exit(1)
    
    # Test datetime handling
    datetime_ok = test_datetime_handling()
    
    # Test API endpoint (optional)
    api_ok = test_api_endpoint()
    
    # Summary
    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    print(f"MongoDB Connection: {'✅ OK' if mongo_ok else '❌ FAILED'}")
    print(f"Datetime Handling: {'✅ OK' if datetime_ok else '❌ FAILED'}")
    if api_ok is not None:
        print(f"API Endpoint: {'✅ OK' if api_ok else '❌ FAILED'}")
    else:
        print(f"API Endpoint: ⚠️  Not tested (server not running)")
    
    print("\n" + "=" * 50)
    print("Debugging complete")
    print("=" * 50)


if __name__ == "__main__":
    main()

