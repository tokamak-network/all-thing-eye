#!/usr/bin/env python3
"""
Test GraphQL query for recordings and drive date filtering
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

async def test_recordings_date_filter():
    """Test recordings date filtering"""
    config = Config()
    mongo_config = {
        'uri': config.get('mongodb.uri', os.getenv('MONGODB_URI', 'mongodb://localhost:27017')),
        'database': config.get('mongodb.database', os.getenv('MONGODB_DATABASE', 'all_thing_eye'))
    }
    mongo_manager = get_mongo_manager(mongo_config)
    mongo_manager.connect_async()
    
    try:
        # Use shared_async_db for recordings (like GraphQL does)
        shared_db = mongo_manager.shared_async_db
        db = mongo_manager.async_db
        
        # Test date range: This Year (2025-01-01 to 2025-12-31)
        start_date = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        
        print("=" * 80)
        print("🔍 TESTING RECORDINGS DATE FILTER")
        print("=" * 80)
        print(f"Start Date: {start_date}")
        print(f"End Date: {end_date}")
        print()
        
        # Test recordings
        print("📹 Testing Recordings (shared.recordings):")
        print("-" * 80)
        
        # Use shared_db for recordings (like GraphQL does)
        recordings_col = shared_db["recordings"]
        
        # Check what date fields exist
        sample_doc = await recordings_col.find_one()
        if sample_doc:
            print(f"Sample document fields: {list(sample_doc.keys())}")
            if 'modifiedTime' in sample_doc:
                print(f"  modifiedTime: {sample_doc['modifiedTime']} (type: {type(sample_doc['modifiedTime'])})")
            if 'createdTime' in sample_doc:
                print(f"  createdTime: {sample_doc['createdTime']} (type: {type(sample_doc['createdTime'])})")
            if 'timestamp' in sample_doc:
                print(f"  timestamp: {sample_doc['timestamp']} (type: {type(sample_doc['timestamp'])})")
        print()
        
        # Query with date filter
        # modifiedTime is stored as ISO string, so convert datetime to ISO string
        query = {
            'modifiedTime': {
                '$gte': start_date.isoformat(),
                '$lte': end_date.isoformat()
            }
        }
        
        print(f"Query: {query}")
        print()
        
        # Count total documents
        total_count = await recordings_col.count_documents({})
        print(f"Total recordings: {total_count}")
        
        # Count filtered documents
        filtered_count = await recordings_col.count_documents(query)
        print(f"Filtered recordings (2025): {filtered_count}")
        print()
        
        # Get sample documents
        print("Sample documents (first 5):")
        async for doc in recordings_col.find(query).sort('modifiedTime', -1).limit(5):
            modified_time = doc.get('modifiedTime')
            name = doc.get('name', 'N/A')
            print(f"  - {name[:60]}")
            print(f"    modifiedTime: {modified_time} (type: {type(modified_time)})")
        print()
        
        # Test with ISO string format (should work the same)
        print("Testing with ISO string format:")
        start_iso = start_date.isoformat()
        end_iso = end_date.isoformat()
        
        query_iso = {
            'modifiedTime': {
                '$gte': start_iso,
                '$lte': end_iso
            }
        }
        
        filtered_count_iso = await recordings_col.count_documents(query_iso)
        print(f"Filtered recordings (ISO string): {filtered_count_iso}")
        print()
        
        # Test drive
        print("📁 Testing Drive (drive_activities):")
        print("-" * 80)
        
        drive_col = db['drive_activities']
        sample_drive = await drive_col.find_one()
        if sample_drive:
            print(f"Sample document fields: {list(sample_drive.keys())}")
            if 'time' in sample_drive:
                print(f"  time: {sample_drive['time']} (type: {type(sample_drive['time'])})")
            if 'timestamp' in sample_drive:
                print(f"  timestamp: {sample_drive['timestamp']} (type: {type(sample_drive['timestamp'])})")
            if 'created_at' in sample_drive:
                print(f"  created_at: {sample_drive['created_at']} (type: {type(sample_drive['created_at'])})")
        print()
        
        # Query drive with date filter
        # Drive uses 'timestamp' field (not 'time'), and it's timezone-naive
        # Convert timezone-aware datetime to timezone-naive UTC
        start_date_naive = start_date.astimezone(timezone.utc).replace(tzinfo=None)
        end_date_naive = end_date.astimezone(timezone.utc).replace(tzinfo=None)
        
        drive_query = {
            'timestamp': {
                '$gte': start_date_naive,
                '$lte': end_date_naive
            }
        }
        
        print(f"Query: {drive_query}")
        print()
        
        total_drive = await drive_col.count_documents({})
        print(f"Total drive activities: {total_drive}")
        
        filtered_drive = await drive_col.count_documents(drive_query)
        print(f"Filtered drive activities (2025): {filtered_drive}")
        print()
        
        # Get sample documents
        print("Sample documents (first 5):")
        async for doc in drive_col.find(drive_query).sort('timestamp', -1).limit(5):
            time_field = doc.get('time')
            doc_title = doc.get('doc_title', 'N/A')
            print(f"  - {doc_title[:60]}")
            print(f"    time: {time_field} (type: {type(time_field)})")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        mongo_manager.close()

if __name__ == "__main__":
    asyncio.run(test_recordings_date_filter())

