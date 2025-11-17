"""
Test script for Notion Plugin (MongoDB Version)
"""

import asyncio
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from src.core.config import Config
from src.core.mongo_manager import get_mongo_manager
from src.plugins.notion_plugin_mongo import NotionPluginMongo


async def test_notion_plugin_mongo():
    print("====================================================================")
    print("🚀 Notion Plugin MongoDB Test")
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
    
    # Load notion config
    notion_config = config.get('plugins.notion', {})
    if not notion_config:
        print("❌ Notion plugin not configured")
        return
    
    print(f"✅ Notion Token: {'*' * 20}...{os.getenv('NOTION_API_TOKEN', '')[-10:]}")
    
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
    
    # 3. Initialize Notion Plugin
    print("\n====================================================================")
    print("🧪 Testing Notion Plugin (MongoDB)")
    print("====================================================================")
    print("\n1️⃣ Initializing Notion Plugin...")
    notion_plugin = NotionPluginMongo(notion_config, mongo_manager)
    print(f"   ✅ Notion plugin initialized")
    
    # 4. Validate configuration
    print("\n2️⃣ Validating configuration...")
    if not notion_plugin.validate_config():
        print("❌ Notion plugin configuration is invalid.")
        return
    print("   ✅ Configuration valid")
    
    # 5. Authenticate
    print("\n3️⃣ Authenticating with Notion...")
    if not notion_plugin.authenticate():
        print("❌ Notion authentication failed.")
        return
    
    # 6. Define collection period (last 7 days)
    from datetime import timezone
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=7)
    print(f"\n4️⃣ Collecting data...")
    print(f"   📅 Period: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    
    # 7. Collect data
    collected_data = notion_plugin.collect_data(start_date, end_date)
    
    # 8. Save data to MongoDB
    await notion_plugin.save_data(collected_data[0])
    print("✅ Data collection completed")
    
    # 9. Verify data in MongoDB
    print("\n====================================================================")
    print("🧪 Verifying MongoDB Data")
    print("====================================================================")
    db = mongo_manager.async_db
    
    pages_collection = db["notion_pages"]
    databases_collection = db["notion_databases"]
    
    total_pages = await pages_collection.count_documents({})
    total_databases = await databases_collection.count_documents({})
    
    print(f"\n📊 Checking Notion pages collection...")
    print(f"   ✅ Total pages: {total_pages}")
    if total_pages > 0:
        sample_page = await pages_collection.find_one()
        print(f"   📝 Sample page:")
        print(f"      Title: {sample_page.get('title', '')}")
        print(f"      Created: {sample_page.get('created_time', '')}")
        print(f"      Last Edited: {sample_page.get('last_edited_time', '')}")
        print(f"      Comments: {sample_page.get('comments_count', 0)}")
    
    print(f"\n📊 Checking Notion databases collection...")
    print(f"   ✅ Total databases: {total_databases}")
    if total_databases > 0:
        sample_db = await databases_collection.find_one()
        print(f"   📝 Sample database:")
        print(f"      Title: {sample_db.get('title', '')}")
        print(f"      Created: {sample_db.get('created_time', '')}")
    
    # Count pages by created_by
    print(f"\n📊 Pages by creator:")
    pipeline = [
        {"$group": {"_id": "$created_by.name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    async for doc in pages_collection.aggregate(pipeline):
        print(f"   {doc['_id']}: {doc['count']} pages")
    
    print("\n====================================================================")
    print("📈 Summary")
    print("====================================================================")
    print(f"Pages: {total_pages}")
    print(f"Databases: {total_databases}")
    print(f"Total records: {total_pages + total_databases}")
    
    print("\n====================================================================")
    print("✅ Test completed successfully!")
    print("====================================================================")
    
    mongo_manager.close()


if __name__ == "__main__":
    asyncio.run(test_notion_plugin_mongo())

