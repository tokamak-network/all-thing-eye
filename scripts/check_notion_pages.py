#!/usr/bin/env python3
"""
Check Notion pages collection status
Usage: docker exec -it all-thing-eye-backend python scripts/check_notion_pages.py
"""

import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, '/app')

def check_notion_pages():
    """Check Notion pages in MongoDB and identify potential issues"""
    print("=" * 60)
    print("Notion Pages Collection Analysis")
    print("=" * 60)
    
    try:
        from backend.main import mongo_manager
        
        if mongo_manager is None:
            print("❌ mongo_manager is None. Backend may not be initialized.")
            print("   This script should be run inside the backend container.")
            sys.exit(1)
        
        # Connect to MongoDB
        mongo_manager.connect_sync()
        db = mongo_manager.db
        pages_collection = db["notion_pages"]
        
        # Get total count
        total_count = pages_collection.count_documents({})
        print(f"\n📊 Total pages in database: {total_count}")
        
        # Check pages by parent
        print("\n" + "=" * 60)
        print("Pages grouped by parent")
        print("=" * 60)
        
        pipeline = [
            {
                "$group": {
                    "_id": {
                        "parent_type": "$parent_type",
                        "parent_id": "$parent_id"
                    },
                    "count": {"$sum": 1},
                    "pages": {
                        "$push": {
                            "id": "$id",
                            "title": "$title",
                            "last_edited_time": "$last_edited_time"
                        }
                    }
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 20}
        ]
        
        parent_groups = list(pages_collection.aggregate(pipeline))
        
        for group in parent_groups:
            parent_info = group["_id"]
            count = group["count"]
            pages = group["pages"]
            
            parent_str = f"{parent_info['parent_type']}"
            if parent_info.get('parent_id'):
                parent_str += f" ({parent_info['parent_id'][:8]}...)"
            else:
                parent_str += " (workspace/root)"
            
            print(f"\n📁 {parent_str}: {count} pages")
            
            # Show first 5 pages
            for page in pages[:5]:
                title = page.get('title', 'Untitled')[:50]
                last_edited = page.get('last_edited_time')
                if isinstance(last_edited, datetime):
                    last_edited_str = last_edited.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    last_edited_str = str(last_edited)
                print(f"   - {title} (edited: {last_edited_str})")
            
            if len(pages) > 5:
                print(f"   ... and {len(pages) - 5} more")
        
        # Check for archived pages
        print("\n" + "=" * 60)
        print("Archived pages")
        print("=" * 60)
        
        archived_count = pages_collection.count_documents({"is_archived": True})
        print(f"Archived pages: {archived_count}")
        
        # Check pages by last_edited_time
        print("\n" + "=" * 60)
        print("Pages by last_edited_time (recent)")
        print("=" * 60)
        
        now = datetime.utcnow()
        last_7_days = now - timedelta(days=7)
        last_30_days = now - timedelta(days=30)
        
        recent_7d = pages_collection.count_documents({
            "last_edited_time": {"$gte": last_7_days}
        })
        recent_30d = pages_collection.count_documents({
            "last_edited_time": {"$gte": last_30_days}
        })
        
        print(f"Pages edited in last 7 days: {recent_7d}")
        print(f"Pages edited in last 30 days: {recent_30d}")
        
        # Check for pages with same parent but different collection dates
        print("\n" + "=" * 60)
        print("Potential missing pages (same parent, different collection dates)")
        print("=" * 60)
        
        # Find parent groups with varying collection dates
        pipeline2 = [
            {
                "$group": {
                    "_id": {
                        "parent_type": "$parent_type",
                        "parent_id": "$parent_id"
                    },
                    "pages": {
                        "$push": {
                            "id": "$id",
                            "title": "$title",
                            "collected_at": "$collected_at",
                            "last_edited_time": "$last_edited_time"
                        }
                    },
                    "collection_dates": {"$addToSet": "$collected_at"},
                    "count": {"$sum": 1}
                }
            },
            {
                "$match": {
                    "$expr": {"$gt": [{"$size": "$collection_dates"}, 1]}
                }
            },
            {"$limit": 10}
        ]
        
        varying_groups = list(pages_collection.aggregate(pipeline2))
        
        if varying_groups:
            print(f"Found {len(varying_groups)} parent groups with pages collected at different times")
            for group in varying_groups[:5]:
                parent_info = group["_id"]
                pages = group["pages"]
                collection_dates = sorted(set(
                    p.get('collected_at') for p in pages 
                    if isinstance(p.get('collected_at'), datetime)
                ))
                
                parent_str = f"{parent_info['parent_type']}"
                if parent_info.get('parent_id'):
                    parent_str += f" ({parent_info['parent_id'][:8]}...)"
                
                print(f"\n📁 {parent_str}: {len(pages)} pages")
                print(f"   Collection dates: {len(collection_dates)} different dates")
                if collection_dates:
                    print(f"   First: {collection_dates[0]}")
                    print(f"   Last: {collection_dates[-1]}")
        else:
            print("No parent groups with varying collection dates found")
        
        # Check for pages with errors in content fetch
        print("\n" + "=" * 60)
        print("Pages with empty content (potential fetch errors)")
        print("=" * 60)
        
        empty_content = pages_collection.count_documents({
            "$or": [
                {"content": {"$exists": False}},
                {"content": ""},
                {"content_length": 0}
            ]
        })
        
        print(f"Pages with empty/missing content: {empty_content}")
        
        if empty_content > 0:
            sample_empty = list(pages_collection.find({
                "$or": [
                    {"content": {"$exists": False}},
                    {"content": ""},
                    {"content_length": 0}
                ]
            }).limit(5))
            
            print("\nSample pages with empty content:")
            for page in sample_empty:
                title = page.get('title', 'Untitled')[:50]
                page_id = page.get('id', 'unknown')[:8]
                print(f"   - {title} (ID: {page_id}...)")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    check_notion_pages()

