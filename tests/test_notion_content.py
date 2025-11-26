"""
Test Notion content collection

Tests the new content collection feature for Notion pages
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
import os
from dotenv import load_dotenv

from src.plugins.notion_plugin_mongo import NotionPluginMongo
from src.core.mongo_manager import MongoDBManager
from src.utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)


async def test_notion_content_collection():
    """Test collecting Notion pages with full content"""
    
    print("="*70)
    print("🧪 Testing Notion Content Collection")
    print("="*70)
    
    # Initialize MongoDB
    mongo_config = {
        'uri': os.getenv('MONGODB_URI'),
        'database': os.getenv('MONGODB_DATABASE'),
        'max_pool_size': 100,
        'min_pool_size': 10
    }
    
    print(f"\n1️⃣ Connecting to MongoDB: {mongo_config['database']}")
    mongo_manager = MongoDBManager(mongo_config)
    mongo_manager.connect_async()  # No await needed - just initializes connection
    
    # Initialize Notion plugin
    notion_config = {
        'token': os.getenv('NOTION_TOKEN'),
        'workspace_id': os.getenv('NOTION_WORKSPACE_ID'),
        'days_to_collect': 7,  # Collect last 7 days
        'rate_limit': 3  # 3 requests per second
    }
    
    print(f"\n2️⃣ Initializing Notion plugin")
    notion_plugin = NotionPluginMongo(notion_config, mongo_manager)
    
    # Authenticate
    print(f"\n3️⃣ Authenticating with Notion API")
    if not notion_plugin.authenticate():
        print("❌ Authentication failed")
        return
    
    # Collect data
    print(f"\n4️⃣ Collecting Notion data (last 7 days)")
    print("⏳ This may take a few minutes with content collection...")
    
    start_date = datetime.now(timezone.utc) - timedelta(days=7)
    end_date = datetime.now(timezone.utc)
    
    collected_data_list = notion_plugin.collect_data(start_date, end_date)
    collected_data = collected_data_list[0] if collected_data_list else {}
    
    # Display results
    print("\n" + "="*70)
    print("📊 Collection Results")
    print("="*70)
    
    pages_count = len(collected_data.get('pages', []))
    print(f"\n✅ Collected {pages_count} pages")
    
    # Show sample pages with content
    if pages_count > 0:
        print("\n📄 Sample Pages:")
        for i, page in enumerate(collected_data['pages'][:5], 1):
            print(f"\n{i}. {page.get('title', 'Untitled')}")
            print(f"   Created by: {page.get('created_by', {}).get('name', 'Unknown')}")
            print(f"   Created: {page.get('created_time')}")
            print(f"   Content length: {page.get('content_length', 0)} characters")
            
            # Show content preview (first 200 chars)
            content = page.get('content', '')
            if content:
                preview = content[:200].replace('\n', ' ')
                print(f"   Preview: {preview}...")
            else:
                print(f"   ⚠️ No content collected")
    
    # Save to database
    print(f"\n5️⃣ Saving to MongoDB")
    await notion_plugin.save_data(collected_data)
    
    # Verify in database
    print(f"\n6️⃣ Verifying in database")
    db = mongo_manager.async_db
    
    # Check if content field exists
    sample_page = await db['notion_pages'].find_one({})
    if sample_page:
        print(f"\n✅ Sample page from DB:")
        print(f"   Title: {sample_page.get('title')}")
        print(f"   Has content field: {'content' in sample_page}")
        print(f"   Content length: {sample_page.get('content_length', 0)}")
        
        if sample_page.get('content'):
            preview = sample_page['content'][:200].replace('\n', ' ')
            print(f"   Content preview: {preview}...")
    else:
        print("⚠️ No pages found in database")
    
    # Statistics
    total_pages = await db['notion_pages'].count_documents({})
    pages_with_content = await db['notion_pages'].count_documents({'content': {'$ne': ''}})
    
    print(f"\n📈 Database Statistics:")
    print(f"   Total pages: {total_pages}")
    print(f"   Pages with content: {pages_with_content}")
    print(f"   Pages without content: {total_pages - pages_with_content}")
    
    if pages_with_content > 0:
        # Show pages with longest content
        longest_pages = db['notion_pages'].find(
            {},
            {'title': 1, 'content_length': 1, 'created_by.name': 1}
        ).sort('content_length', -1).limit(5)
        
        print(f"\n📚 Pages with most content:")
        async for page in longest_pages:
            title = page.get('title', 'Untitled')
            length = page.get('content_length', 0)
            author = page.get('created_by', {}).get('name', 'Unknown')
            print(f"   - {title}: {length:,} chars (by {author})")
    
    print("\n" + "="*70)
    print("✅ Test Complete!")
    print("="*70)
    
    mongo_manager.close()  # Close all connections


if __name__ == "__main__":
    asyncio.run(test_notion_content_collection())

