#!/usr/bin/env python3
"""
Test Notion date filtering in MongoDB
"""

import asyncio
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import Config
from src.core.mongo_manager import get_mongo_manager

async def test_notion_date_filter():
    """Test Notion date filtering"""
    config = Config()
    mongo_config = {
        'uri': config.get('mongodb.uri', os.getenv('MONGODB_URI', 'mongodb://localhost:27017')),
        'database': config.get('mongodb.database', os.getenv('MONGODB_DATABASE', 'all_thing_eye'))
    }
    mongo_manager = get_mongo_manager(mongo_config)
    mongo_manager.connect_async()
    
    try:
        db = mongo_manager.async_db
        
        # Test date range: This Year (2025-01-01 to 2025-12-31)
        start_date = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        
        print("=" * 80)
        print("🔍 TESTING NOTION DATE FILTER")
        print("=" * 80)
        print(f"Start Date: {start_date}")
        print(f"End Date: {end_date}")
        print()
        
        # Test Notion
        print("📝 Testing Notion (notion_pages):")
        print("-" * 80)
        
        notion_col = db['notion_pages']
        
        # Check what date fields exist
        sample_doc = await notion_col.find_one()
        if sample_doc:
            print(f"Sample document fields: {list(sample_doc.keys())}")
            if 'last_edited_time' in sample_doc:
                print(f"  last_edited_time: {sample_doc['last_edited_time']} (type: {type(sample_doc['last_edited_time'])})")
            if 'created_time' in sample_doc:
                print(f"  created_time: {sample_doc['created_time']} (type: {type(sample_doc['created_time'])})")
        print()
        
        # Query with date filter (same as GraphQL does)
        query = {}
        if start_date:
            query['last_edited_time'] = {'$gte': start_date}
        if end_date:
            query['last_edited_time'] = query.get('last_edited_time', {})
            query['last_edited_time']['$lte'] = end_date
        
        print(f"Query: {query}")
        print()
        
        # Count total documents
        total_count = await notion_col.count_documents({})
        print(f"Total notion pages: {total_count}")
        
        # Count filtered documents
        filtered_count = await notion_col.count_documents(query)
        print(f"Filtered notion pages (2025): {filtered_count}")
        print()
        
        # Get sample documents
        print("Sample documents (first 5):")
        async for doc in notion_col.find(query).sort('last_edited_time', -1).limit(5):
            last_edited = doc.get('last_edited_time')
            title = doc.get('title', 'N/A')
            print(f"  - {title[:60]}")
            print(f"    last_edited_time: {last_edited} (type: {type(last_edited)})")
        print()
        
        # Test with timezone-naive datetime
        print("Testing with timezone-naive datetime:")
        start_date_naive = start_date.astimezone(timezone.utc).replace(tzinfo=None)
        end_date_naive = end_date.astimezone(timezone.utc).replace(tzinfo=None)
        
        query_naive = {
            'last_edited_time': {
                '$gte': start_date_naive,
                '$lte': end_date_naive
            }
        }
        
        filtered_count_naive = await notion_col.count_documents(query_naive)
        print(f"Filtered notion pages (naive datetime): {filtered_count_naive}")
        print()
        
        # Check date range of all documents
        print("Checking date range of all documents:")
        oldest_doc = await notion_col.find_one(sort=[('last_edited_time', 1)])
        newest_doc = await notion_col.find_one(sort=[('last_edited_time', -1)])
        
        if oldest_doc and newest_doc:
            oldest_time = oldest_doc.get('last_edited_time')
            newest_time = newest_doc.get('last_edited_time')
            print(f"  Oldest: {oldest_time}")
            print(f"  Newest: {newest_time}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        mongo_manager.close()

if __name__ == "__main__":
    asyncio.run(test_notion_date_filter())

