#!/usr/bin/env python3
"""
MongoDB Restore Script (Collection-based)

Restores MongoDB collections from backup collections created by backup_mongodb_to_collection.py
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

def list_backups():
    """List available backups"""
    uri = get_mongodb_uri()
    database_name = get_mongodb_database()
    
    client = MongoClient(uri)
    db = client[database_name]
    metadata_collection = db["backup_metadata"]
    
    backups = list(metadata_collection.find().sort("created_at", -1))
    
    if not backups:
        print("No backups found")
        return []
    
    print("Available backups:")
    for i, backup in enumerate(backups, 1):
        print(f"  {i}. {backup['backup_id']} - {backup['created_at']} ({len(backup['collections'])} collections)")
    
    return backups

def restore_backup(backup_id: str, confirm: bool = True):
    """Restore from a backup"""
    print("=" * 60)
    print("MongoDB Restore Script")
    print("=" * 60)
    print(f"Started at: {datetime.now()}\n")
    
    uri = get_mongodb_uri()
    database_name = get_mongodb_database()
    
    print(f"Database: {database_name}")
    print(f"Backup ID: {backup_id}\n")
    
    client = MongoClient(uri)
    db = client[database_name]
    metadata_collection = db["backup_metadata"]
    
    # Find backup metadata
    backup_meta = metadata_collection.find_one({"backup_id": backup_id})
    if not backup_meta:
        print(f"❌ Backup '{backup_id}' not found")
        return False
    
    print(f"Backup created at: {backup_meta['created_at']}")
    print(f"Collections to restore: {len(backup_meta['collections'])}\n")
    
    if confirm:
        response = input("⚠️  This will overwrite existing collections. Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Restore cancelled")
            return False
    
    restored = []
    errors = []
    
    for item in backup_meta['collections']:
        try:
            source_collection = db[item['source']]
            backup_collection = db[item['backup']]
            
            # Check if backup collection exists
            if backup_collection.count_documents({}) == 0:
                print(f"⚠️  Skipping {item['source']} (backup collection is empty)")
                continue
            
            print(f"📦 Restoring {item['source']}...")
            
            # Clear existing collection (optional - comment out if you want to merge)
            # source_collection.delete_many({})
            
            # Copy documents from backup
            documents = list(backup_collection.find({}))
            if documents:
                source_collection.delete_many({})  # Clear first
                source_collection.insert_many(documents)
            
            restored.append(item['source'])
            print(f"   ✅ Restored {len(documents)} documents")
            
        except Exception as e:
            errors.append({
                "collection": item['source'],
                "error": str(e)
            })
            print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("Restore Summary")
    print("=" * 60)
    print(f"Collections restored: {len(restored)}")
    print(f"Errors: {len(errors)}")
    
    if restored:
        print("\nRestored collections:")
        for name in restored:
            print(f"  - {name}")
    
    if errors:
        print("\nErrors:")
        for error in errors:
            print(f"  - {error['collection']}: {error['error']}")
    
    print(f"\n✅ Restore completed at: {datetime.now()}")
    
    return len(errors) == 0

if __name__ == "__main__":
    if len(sys.argv) > 1:
        backup_id = sys.argv[1]
        restore_backup(backup_id)
    else:
        print("Usage: python scripts/restore_mongodb_from_collection.py <backup_id>")
        print("\nAvailable backups:")
        list_backups()

