"""
Test script for Slack Plugin (MongoDB Version)
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
from src.plugins.slack_plugin_mongo import SlackPluginMongo


async def test_slack_plugin_mongo():
    print("====================================================================")
    print("🚀 Slack Plugin MongoDB Test")
    print("====================================================================")
    
    # 1. Load configuration
    print("\n====================================================================")
    print("🧪 Loading Configuration")
    print("====================================================================")
    
    # Load environment variables
    env_path = project_root / '.env'
    load_dotenv(dotenv_path=env_path)
    
    # Load config
    config = Config()
    slack_config = config.get('plugins.slack', {})
    
    # Get MongoDB connection info
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    mongodb_database = os.getenv("MONGODB_DATABASE", "all_thing_eye_test")
    
    print(f"✅ Loaded environment variables from: {env_path}")
    print(f"✅ MongoDB URI: {mongodb_uri}")
    print(f"✅ MongoDB Database: {mongodb_database}")
    print(f"✅ Slack Workspace: {slack_config.get('workspace')}")
    
    # 2. Initialize MongoDB Manager
    mongo_config = {
        'uri': mongodb_uri,
        'database': mongodb_database,
    }
    mongo_manager = get_mongo_manager(mongo_config)
    
    # 3. Test MongoDB Connection
    print("\n====================================================================")
    print("🧪 Testing MongoDB Connection")
    print("====================================================================")
    try:
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
    
    # 4. Initialize Slack Plugin
    print("\n====================================================================")
    print("🧪 Testing Slack Plugin (MongoDB)")
    print("====================================================================")
    print("\n1️⃣ Initializing Slack Plugin...")
    slack_plugin = SlackPluginMongo(slack_config, mongo_manager)
    print(f"   ✅ Slack plugin initialized")
    
    # 4. Validate configuration
    print("\n2️⃣ Validating configuration...")
    if not slack_plugin.validate_config():
        print("❌ Slack plugin configuration is invalid.")
        return
    print("   ✅ Configuration valid")
    
    # 5. Authenticate
    print("\n3️⃣ Authenticating with Slack...")
    if not slack_plugin.authenticate():
        print("❌ Slack authentication failed.")
        return
    
    # 6. Define collection period (last week)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)
    print(f"\n4️⃣ Collecting data...")
    print(f"   📅 Period: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    
    # 7. Collect data
    collected_data = slack_plugin.collect_data(start_date, end_date)
    
    # 8. Save data to MongoDB
    await slack_plugin.save_data(collected_data[0])
    print("✅ Data collection completed")
    
    # 9. Verify data in MongoDB
    print("\n====================================================================")
    print("🧪 Verifying MongoDB Data")
    print("====================================================================")
    # Reconnect to verify data
    mongo_manager = get_mongo_manager(mongo_config)
    mongo_manager.connect_async()
    db = mongo_manager.async_db
    
    messages_collection = db["slack_messages"]
    channels_collection = db["slack_channels"]
    
    total_messages = await messages_collection.count_documents({})
    total_channels = await channels_collection.count_documents({})
    
    print(f"\n📊 Checking Slack messages collection...")
    print(f"   ✅ Total messages: {total_messages}")
    if total_messages > 0:
        sample_message = await messages_collection.find_one()
        print(f"   📝 Sample message:")
        print(f"      Channel: {sample_message.get('channel_name', '')}")
        print(f"      User: {sample_message.get('user_name', '')}")
        print(f"      Text: {sample_message.get('text', '')[:50]}...")
        print(f"      Posted: {sample_message.get('posted_at', '')}")
        print(f"      Reactions: {len(sample_message.get('reactions', []))}")
        print(f"      Links: {len(sample_message.get('links', []))}")
        print(f"      Files: {len(sample_message.get('files', []))}")
    
    print(f"\n📊 Checking Slack channels collection...")
    print(f"   ✅ Total channels: {total_channels}")
    
    # Count messages by channel
    print(f"\n📊 Messages by channel:")
    pipeline = [
        {"$group": {"_id": "$channel_name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    async for doc in messages_collection.aggregate(pipeline):
        print(f"   #{doc['_id']}: {doc['count']} messages")
    
    print("\n====================================================================")
    print("📈 Summary")
    print("====================================================================")
    print(f"Channels: {total_channels}")
    print(f"Messages: {total_messages}")
    print(f"Total records: {total_channels + total_messages}")
    
    print("\n====================================================================")
    print("✅ Test completed successfully!")
    print("====================================================================")


if __name__ == "__main__":
    asyncio.run(test_slack_plugin_mongo())

