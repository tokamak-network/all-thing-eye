"""
Test script for Google Drive Plugin (MongoDB Version)
"""

import asyncio
from datetime import datetime, timedelta, timezone
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from src.core.config import Config
from src.core.mongo_manager import get_mongo_manager
from src.plugins.google_drive_plugin_mongo import GoogleDrivePluginMongo


async def test_drive_plugin_mongo():
    print("====================================================================")
    print("🚀 Google Drive Plugin MongoDB Test")
    print("====================================================================")
    
    # 1. Load configuration
    print("\n====================================================================")
    print("🧪 Loading Configuration")
    print("====================================================================")
    
    # Load environment variables
    env_path = project_root / '.env'
    load_dotenv(dotenv_path=env_path)
    
    # Initialize config
    config = Config()
    
    # Get MongoDB configuration
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    mongodb_database = os.getenv("MONGODB_DATABASE", "all_thing_eye_test")
    
    print(f"✅ MongoDB URI: {mongodb_uri}")
    print(f"✅ MongoDB Database: {mongodb_database}")
    
    # Load drive config
    drive_config = config.get('plugins.google_drive', {})
    if not drive_config:
        print("❌ Google Drive plugin not configured")
        return
    
    print(f"✅ Google Drive credentials configured")
    
    # 2. Initialize MongoDB Manager
    print("\n====================================================================")
    print("🧪 Testing MongoDB Connection")
    print("====================================================================")
    try:
        mongo_config = {
            'uri': mongodb_uri,
            'database': mongodb_database,
        }
        mongo_manager = get_mongo_manager(mongo_config)
        mongo_manager.connect_async()
        db = mongo_manager.async_db
        server_info = await db.command("serverStatus")
        print(f"✅ MongoDB connection test successful")
        print(f"   Server version: {server_info['version']}")
        collections = await db.list_collection_names()
        print(f"   Database: {db.name}")
        print(f"   Collections: {len(collections)}")
        print("✅ MongoDB connection test passed")
    except Exception as e:
        print(f"❌ MongoDB connection test failed: {e}")
        return
    
    # 3. Initialize Drive Plugin
    print("\n====================================================================")
    print("🧪 Testing Google Drive Plugin (MongoDB)")
    print("====================================================================")
    print("\n1️⃣ Initializing Google Drive Plugin...")
    drive_plugin = GoogleDrivePluginMongo(drive_config, mongo_manager)
    print(f"   ✅ Drive plugin initialized")
    
    # 4. Validate configuration
    print("\n2️⃣ Validating configuration...")
    if not drive_plugin.validate_config():
        print("❌ Drive plugin configuration is invalid.")
        return
    print("   ✅ Configuration valid")
    
    # 5. Authenticate
    print("\n3️⃣ Authenticating with Google Drive...")
    if not drive_plugin.authenticate():
        print("❌ Google Drive authentication failed.")
        return
    
    # 6. Define collection period (last 30 days)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=30)
    print(f"\n4️⃣ Collecting data...")
    print(f"   📅 Period: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    print(f"   (Collecting 30 days of Drive activity data)")
    
    # 7. Collect data
    collected_data = drive_plugin.collect_data(start_date, end_date)
    
    # Debug: Check what was collected
    if collected_data:
        data = collected_data[0]
        print(f"\n📊 Collection Debug Info:")
        print(f"   Activities collected: {len(data.get('activities', []))}")
        print(f"   Folders collected: {len(data.get('folders', []))}")
        
        if data.get('activities'):
            print(f"\n   Sample activities:")
            for i, act in enumerate(data['activities'][:3], 1):
                print(f"      {i}. {act.get('action')} by {act.get('user_email')} - {act.get('doc_title', 'N/A')}")
    
    # 8. Save data to MongoDB
    if collected_data:
        await drive_plugin.save_data(collected_data[0])
    print("✅ Data collection completed")
    
    # 9. Verify data in MongoDB
    print("\n====================================================================")
    print("🧪 Verifying MongoDB Data")
    print("====================================================================")
    db = mongo_manager.async_db
    
    activities_collection = db["drive_activities"]
    files_collection = db["drive_files"]
    
    total_activities = await activities_collection.count_documents({})
    total_files = await files_collection.count_documents({})
    
    print(f"\n📊 Checking Drive activities collection...")
    print(f"   ✅ Total activities: {total_activities}")
    if total_activities > 0:
        sample_activity = await activities_collection.find_one()
        print(f"   📝 Sample activity:")
        print(f"      Actor: {sample_activity.get('actor_email', '')}")
        print(f"      Type: {sample_activity.get('type', '')}")
        print(f"      Time: {sample_activity.get('time', '')}")
    
    print(f"\n📊 Checking Drive files collection...")
    print(f"   ✅ Total files: {total_files}")
    if total_files > 0:
        sample_file = await files_collection.find_one()
        print(f"   📝 Sample file:")
        print(f"      Name: {sample_file.get('name', '')}")
        print(f"      Owner: {sample_file.get('owner', '')}")
        print(f"      Type: {sample_file.get('mime_type', '')}")
    
    # Count activities by actor
    print(f"\n📊 Activities by actor:")
    pipeline = [
        {"$group": {"_id": "$actor_email", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    async for doc in activities_collection.aggregate(pipeline):
        print(f"   {doc['_id']}: {doc['count']} activities")
    
    print("\n====================================================================")
    print("📈 Summary")
    print("====================================================================")
    print(f"Activities: {total_activities}")
    print(f"Files: {total_files}")
    print(f"Total records: {total_activities + total_files}")
    
    print("\n====================================================================")
    print("✅ Test completed successfully!")
    print("====================================================================")
    
    mongo_manager.close()


if __name__ == "__main__":
    asyncio.run(test_drive_plugin_mongo())

