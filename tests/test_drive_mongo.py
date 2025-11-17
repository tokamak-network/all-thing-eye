"""
Test script for Google Drive Plugin (MongoDB Version)
"""

import asyncio
from datetime import datetime, timedelta
import os
from src.config import settings
from src.core.mongo_manager import mongo_manager
from src.plugins.google_drive_plugin_mongo import GoogleDrivePluginMongo


async def test_drive_plugin_mongo():
    print("====================================================================")
    print("🚀 Google Drive Plugin MongoDB Test")
    print("====================================================================")
    
    # 1. Load configuration
    print("\n====================================================================")
    print("🧪 Loading Configuration")
    print("====================================================================")
    settings.load_env()
    
    # Load drive config
    drive_config = settings.plugins.google_drive.model_dump()
    
    # Override MongoDB connection from environment
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    mongodb_database = os.getenv("MONGODB_DATABASE", "all_thing_eye")
    
    settings.mongodb.uri = mongodb_uri
    settings.mongodb.database = mongodb_database
    
    print(f"✅ Loaded environment variables from: {settings.env_file}")
    print(f"✅ MongoDB URI: {settings.mongodb.uri}")
    print(f"✅ MongoDB Database: {settings.mongodb.database}")
    
    # 2. Test MongoDB Connection
    print("\n====================================================================")
    print("🧪 Testing MongoDB Connection")
    print("====================================================================")
    try:
        await mongo_manager.connect_async()
        db = mongo_manager.get_database_async()
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
    finally:
        await mongo_manager.disconnect_async()
    
    # 3. Initialize Drive Plugin
    print("\n====================================================================")
    print("🧪 Testing Google Drive Plugin (MongoDB)")
    print("====================================================================")
    print("\n1️⃣ Initializing Google Drive Plugin...")
    drive_plugin = GoogleDrivePluginMongo(drive_config)
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
    
    # 6. Define collection period (last 7 days)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)
    print(f"\n4️⃣ Collecting data...")
    print(f"   📅 Period: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    
    # 7. Collect data
    collected_data = await drive_plugin.collect_data(start_date, end_date)
    
    # 8. Save data to MongoDB
    await drive_plugin.save_data(collected_data[0])
    print("✅ Data collection completed")
    
    # 9. Verify data in MongoDB
    print("\n====================================================================")
    print("🧪 Verifying MongoDB Data")
    print("====================================================================")
    await mongo_manager.connect_async()
    db = mongo_manager.get_database_async()
    
    activities_collection = db[mongo_manager._collections_config["drive_activities"]]
    folders_collection = db[mongo_manager._collections_config["drive_folders"]]
    
    total_activities = await activities_collection.count_documents({})
    total_folders = await folders_collection.count_documents({})
    
    print(f"\n📊 Checking Drive activities collection...")
    print(f"   ✅ Total activities: {total_activities}")
    if total_activities > 0:
        sample_activity = await activities_collection.find_one()
        print(f"   📝 Sample activity:")
        print(f"      User: {sample_activity.get('user_email', '')}")
        print(f"      Action: {sample_activity.get('action', '')}")
        print(f"      Document: {sample_activity.get('doc_title', '')}")
        print(f"      Type: {sample_activity.get('doc_type', '')}")
        print(f"      Timestamp: {sample_activity.get('timestamp', '')}")
    
    print(f"\n📊 Checking Drive folders collection...")
    print(f"   ✅ Total folders: {total_folders}")
    if total_folders > 0:
        sample_folder = await folders_collection.find_one()
        print(f"   📝 Sample folder:")
        print(f"      Name: {sample_folder.get('folder_name', '')}")
        print(f"      Created by: {sample_folder.get('created_by', '')}")
        print(f"      Members: {len(sample_folder.get('members', []))}")
    
    # Count activities by user
    print(f"\n📊 Activities by user:")
    pipeline = [
        {"$group": {"_id": "$user_email", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    async for doc in activities_collection.aggregate(pipeline):
        print(f"   {doc['_id']}: {doc['count']} activities")
    
    print("\n====================================================================")
    print("📈 Summary")
    print("====================================================================")
    print(f"Activities: {total_activities}")
    print(f"Folders: {total_folders}")
    print(f"Total records: {total_activities + total_folders}")
    
    print("\n====================================================================")
    print("✅ Test completed successfully!")
    print("====================================================================")
    
    await mongo_manager.disconnect_async()


if __name__ == "__main__":
    asyncio.run(test_drive_plugin_mongo())

