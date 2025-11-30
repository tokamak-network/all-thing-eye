#!/usr/bin/env python3
"""
MongoDB Backup Script (Collection-based)

Creates a backup of MongoDB collections by copying them to backup collections
within the same database. This allows easy restoration from MongoDB itself.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

def get_mongodb_uri() -> str:
    """Get MongoDB URI from environment"""
    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise ValueError("MONGODB_URI environment variable not set")
    return uri

def get_mongodb_database() -> str:
    """Get MongoDB database name from environment"""
    return os.getenv("MONGODB_DATABASE", "ati")

def create_backup_to_collection():
    """Create MongoDB backup by copying collections to backup collections"""
    print("=" * 60)
    print("MongoDB Backup Script (Collection-based)")
    print("=" * 60)
    print(f"Started at: {datetime.now()}\n")
    
    # Get MongoDB connection info
    uri = get_mongodb_uri()
    database_name = get_mongodb_database()
    
    print(f"Database: {database_name}")
    print(f"URI: {uri.split('@')[-1] if '@' in uri else uri}\n")  # Hide credentials
    
    # Connect to MongoDB
    print("Connecting to MongoDB...")
    client = MongoClient(uri)
    db = client[database_name]
    
    # Collections to backup (important ones)
    important_collections = [
        "slack_messages",
        "slack_channels",
        "github_commits",
        "github_pull_requests",
        "notion_pages",
        "drive_activities",
        "members",
        "member_identifiers",
        "member_activities"
    ]
    
    # Create backup timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_suffix = f"_backup_{timestamp}"
    
    print(f"Backup suffix: {backup_suffix}\n")
    
    backed_up = []
    errors = []
    
    for collection_name in important_collections:
        try:
            source_collection = db[collection_name]
            backup_collection_name = f"{collection_name}{backup_suffix}"
            backup_collection = db[backup_collection_name]
            
            # Count documents
            count = source_collection.count_documents({})
            
            if count == 0:
                print(f"⏭️  Skipping {collection_name} (empty)")
                continue
            
            print(f"📦 Backing up {collection_name} ({count} documents)...")
            
            # Copy all documents
            documents = list(source_collection.find({}))
            if documents:
                backup_collection.insert_many(documents)
            
            backed_up.append({
                "source": collection_name,
                "backup": backup_collection_name,
                "count": count
            })
            
            print(f"   ✅ Created {backup_collection_name}")
            
        except Exception as e:
            errors.append({
                "collection": collection_name,
                "error": str(e)
            })
            print(f"   ❌ Error: {e}")
    
    # Create backup metadata document
    backup_metadata = {
        "backup_id": timestamp,
        "created_at": datetime.utcnow(),
        "collections": backed_up,
        "errors": errors,
        "database": database_name
    }
    
    metadata_collection = db["backup_metadata"]
    metadata_collection.insert_one(backup_metadata)
    
    print("\n" + "=" * 60)
    print("Backup Summary")
    print("=" * 60)
    print(f"Backup ID: {timestamp}")
    print(f"Collections backed up: {len(backed_up)}")
    print(f"Errors: {len(errors)}")
    
    if backed_up:
        print("\nBacked up collections:")
        for item in backed_up:
            print(f"  - {item['source']} → {item['backup']} ({item['count']} docs)")
    
    if errors:
        print("\nErrors:")
        for error in errors:
            print(f"  - {error['collection']}: {error['error']}")
    
    print(f"\nTo restore a collection, use:")
    print(f"  db.{backed_up[0]['backup']}.find().forEach(doc => db.{backed_up[0]['source']}.insertOne(doc))")
    print(f"\nOr use the restore script: scripts/restore_mongodb_from_collection.py")
    
    print(f"\n✅ Backup completed at: {datetime.now()}")
    
    return timestamp

if __name__ == "__main__":
    try:
        backup_id = create_backup_to_collection()
        if backup_id:
            print(f"\n✅ Backup ID: {backup_id}")
            sys.exit(0)
        else:
            print(f"\n⚠️  Backup failed")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Backup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

