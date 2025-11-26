"""
Collect 90 days of Notion pages with full content

This script collects Notion pages from the last 90 days including full content.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv

from src.plugins.notion_plugin_mongo import NotionPluginMongo
from src.core.mongo_manager import MongoDBManager
from src.utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)


async def collect_90_days():
    """Collect Notion data for the last 90 days"""
    
    print("="*70)
    print("📥 Collecting 90 Days of Notion Pages with Content")
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
    mongo_manager.connect_async()
    
    # Initialize Notion plugin
    notion_config = {
        'token': os.getenv('NOTION_TOKEN'),
        'workspace_id': os.getenv('NOTION_WORKSPACE_ID'),
        'days_to_collect': 90,  # Collect last 90 days
        'rate_limit': 3
    }
    
    print(f"\n2️⃣ Initializing Notion plugin")
    notion_plugin = NotionPluginMongo(notion_config, mongo_manager)
    
    # Authenticate
    print(f"\n3️⃣ Authenticating with Notion API")
    if not notion_plugin.authenticate():
        print("❌ Authentication failed")
        return
    
    # Calculate date range
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=90)
    
    print(f"\n4️⃣ Collecting Notion data")
    print(f"   📅 Period: {start_date.date()} ~ {end_date.date()}")
    print(f"   ⏳ This will take a while with content collection...")
    print(f"   💡 Estimated time: ~10-30 minutes depending on page count")
    
    # Collect data
    collected_data_list = notion_plugin.collect_data(start_date, end_date)
    collected_data = collected_data_list[0] if collected_data_list else {}
    
    # Display results
    print("\n" + "="*70)
    print("📊 Collection Results")
    print("="*70)
    
    pages_count = len(collected_data.get('pages', []))
    users_count = len(collected_data.get('users', []))
    dbs_count = len(collected_data.get('databases', []))
    
    print(f"\n✅ Collected:")
    print(f"   📄 Pages: {pages_count}")
    print(f"   👥 Users: {users_count}")
    print(f"   🗄️  Databases: {dbs_count}")
    
    # Show content statistics
    if pages_count > 0:
        total_chars = sum(p.get('content_length', 0) for p in collected_data['pages'])
        pages_with_content = sum(1 for p in collected_data['pages'] if p.get('content'))
        
        print(f"\n📝 Content Statistics:")
        print(f"   Pages with content: {pages_with_content}/{pages_count} ({pages_with_content/pages_count*100:.1f}%)")
        print(f"   Total characters: {total_chars:,}")
        print(f"   Average per page: {total_chars//pages_count:,} chars")
    
    # Save to database
    print(f"\n5️⃣ Saving to MongoDB...")
    await notion_plugin.save_data(collected_data)
    
    # Verify in database
    print(f"\n6️⃣ Verifying in database...")
    db = mongo_manager.async_db
    
    total_pages = await db['notion_pages'].count_documents({})
    pages_with_content = await db['notion_pages'].count_documents({'content': {'$ne': ''}})
    pages_without_content = total_pages - pages_with_content
    
    print(f"\n📈 Database Statistics:")
    print(f"   Total pages: {total_pages}")
    print(f"   With content: {pages_with_content} ({pages_with_content/total_pages*100:.1f}%)")
    print(f"   Without content: {pages_without_content} ({pages_without_content/total_pages*100:.1f}%)")
    
    # Show content distribution by author
    print(f"\n👤 Content by Author:")
    pipeline = [
        {'$match': {'content': {'$ne': ''}}},
        {'$group': {
            '_id': '$created_by.name',
            'page_count': {'$sum': 1},
            'total_chars': {'$sum': '$content_length'}
        }},
        {'$sort': {'total_chars': -1}},
        {'$limit': 10}
    ]
    
    async for result in db['notion_pages'].aggregate(pipeline):
        author = result['_id'] or 'Unknown'
        pages = result['page_count']
        chars = result['total_chars']
        print(f"   {author}: {pages} pages, {chars:,} chars")
    
    # Show longest pages
    print(f"\n📚 Longest Pages:")
    longest = db['notion_pages'].find(
        {'content': {'$ne': ''}},
        {'title': 1, 'content_length': 1, 'created_by.name': 1}
    ).sort('content_length', -1).limit(10)
    
    async for page in longest:
        title = page.get('title', 'Untitled')[:50]
        length = page.get('content_length', 0)
        author = page.get('created_by', {}).get('name', 'Unknown')
        print(f"   {title}: {length:,} chars (by {author})")
    
    print("\n" + "="*70)
    print("✅ Collection Complete!")
    print("="*70)
    print(f"\n💡 Next step: Use the custom export UI to search and export")
    print(f"   - Filter by title keywords")
    print(f"   - Filter by author")
    print(f"   - Export with full content for AI training")
    
    mongo_manager.close()


if __name__ == "__main__":
    asyncio.run(collect_90_days())

