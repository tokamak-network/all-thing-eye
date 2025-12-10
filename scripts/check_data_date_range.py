#!/usr/bin/env python3
"""
Check Data Date Range for All Sources

This script queries MongoDB to find the earliest and latest data points
for each data source (GitHub, Slack, Notion, Drive, Recordings).

It also checks November 2025 data collection status.

Usage:
    python scripts/check_data_date_range.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from dotenv import load_dotenv
from pymongo import MongoClient

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

from src.core.config import Config

config = Config()

def get_mongodb_uri() -> str:
    """Get MongoDB URI from environment"""
    uri = os.getenv("MONGODB_URI", config.get('mongodb.uri', 'mongodb://localhost:27017'))
    return uri

def get_mongodb_database() -> str:
    """Get MongoDB database name from environment"""
    return os.getenv("MONGODB_DATABASE", config.get('mongodb.database', 'ati'))

def get_shared_database() -> str:
    """Get shared database name"""
    return os.getenv("MONGODB_SHARED_DATABASE", 'shared')

def check_collection_date_range(collection, timestamp_fields, collection_name):
    """Check date range for a collection"""
    results = []
    
    for field in timestamp_fields:
        try:
            # Find earliest document
            earliest = collection.find_one(
                {field: {"$exists": True}},
                sort=[(field, 1)]
            )
            
            # Find latest document
            latest = collection.find_one(
                {field: {"$exists": True}},
                sort=[(field, -1)]
            )
            
            if earliest and latest and field in earliest and field in latest:
                earliest_time = earliest[field]
                latest_time = latest[field]
                
                # Convert to datetime if needed
                if isinstance(earliest_time, str):
                    try:
                        earliest_time = datetime.fromisoformat(earliest_time.replace('Z', '+00:00'))
                    except:
                        pass
                if isinstance(latest_time, str):
                    try:
                        latest_time = datetime.fromisoformat(latest_time.replace('Z', '+00:00'))
                    except:
                        pass
                
                results.append({
                    'field': field,
                    'earliest': earliest_time,
                    'latest': latest_time,
                    'count': collection.count_documents({field: {"$exists": True}})
                })
        except Exception as e:
            print(f"   ⚠️  Error checking {field} in {collection_name}: {e}")
            continue
    
    return results

def check_november_data(collection, timestamp_field, collection_name, year=2025, month=11):
    """Check November data collection status"""
    try:
        # November date range (UTC: 2025-11-01 00:00:00 ~ 2025-11-30 23:59:59)
        # MongoDB stores dates as UTC (timezone-naive) or as strings
        from datetime import timedelta
        nov_start = datetime(year, month, 1, 0, 0, 0)
        nov_end = datetime(year, month, 30, 23, 59, 59)
        
        # For string date fields (like target_date in recordings_daily), use string comparison
        # Check if field is string or datetime by sampling
        sample = collection.find_one({timestamp_field: {"$exists": True}})
        is_string_field = False
        
        if sample and timestamp_field in sample:
            field_value = sample[timestamp_field]
            if isinstance(field_value, str):
                is_string_field = True
                # Use string comparison for date strings (format: YYYY-MM-DD)
                query = {
                    timestamp_field: {
                        "$gte": f"{year}-{month:02d}-01",
                        "$lte": f"{year}-{month:02d}-30"
                    }
                }
            else:
                # Use datetime comparison
                query = {
                    timestamp_field: {
                        "$gte": nov_start,
                        "$lte": nov_end
                    }
                }
        else:
            # Default to datetime query
            query = {
                timestamp_field: {
                    "$gte": nov_start,
                    "$lte": nov_end
                }
            }
        
        total_nov = collection.count_documents(query)
        
        # Count by day
        daily_counts = {}
        try:
            if is_string_field:
                # For string dates, extract date part and group
                pipeline = [
                    {"$match": query},
                    {
                        "$group": {
                            "_id": {"$substr": [f"${timestamp_field}", 0, 10]},  # Extract YYYY-MM-DD
                            "count": {"$sum": 1}
                        }
                    },
                    {"$sort": {"_id": 1}}
                ]
            else:
                # For datetime fields, use $dateToString
                pipeline = [
                    {"$match": query},
                    {
                        "$group": {
                            "_id": {
                                "$dateToString": {
                                    "format": "%Y-%m-%d",
                                    "date": f"${timestamp_field}"
                                }
                            },
                            "count": {"$sum": 1}
                        }
                    },
                    {"$sort": {"_id": 1}}
                ]
            
            for doc in collection.aggregate(pipeline):
                daily_counts[doc["_id"]] = doc["count"]
        except Exception as e:
            # Fallback: count manually if aggregation fails
            print(f"        ⚠️  Aggregation failed: {e}")
            pass
        
        return {
            'total': total_nov,
            'daily_counts': daily_counts,
            'start_date': nov_start,
            'end_date': nov_end
        }
    except Exception as e:
        print(f"   ⚠️  Error checking November data for {collection_name}: {e}")
        return None

def main():
    print("=" * 80)
    print("📅 Data Date Range Checker")
    print("=" * 80)
    print(f"Started at: {datetime.now()}\n")
    
    # Get MongoDB connection info
    uri = get_mongodb_uri()
    database_name = get_mongodb_database()
    shared_db_name = get_shared_database()
    
    print(f"Main Database: {database_name}")
    print(f"Shared Database: {shared_db_name}")
    print(f"URI: {uri.split('@')[-1] if '@' in uri else uri}\n")
    
    try:
        # Connect to MongoDB
        client = MongoClient(uri, serverSelectionTimeoutMS=30000, connectTimeoutMS=30000)
        client.admin.command('ping')
        db = client[database_name]
        shared_db = client[shared_db_name]
        gemini_db = client['gemini']
        
        # Define sources and their collections with timestamp fields
        sources = {
            "GitHub": {
                "db": db,
                "collections": {
                    "github_commits": ["date", "collected_at"],
                    "github_pull_requests": ["created_at", "collected_at"],
                    "github_issues": ["created_at", "collected_at"],
                }
            },
            "Slack": {
                "db": db,
                "collections": {
                    "slack_messages": ["posted_at", "collected_at"],
                }
            },
            "Notion": {
                "db": db,
                "collections": {
                    "notion_pages": ["created_time", "last_edited_time", "collected_at"],
                }
            },
            "Drive": {
                "db": db,
                "collections": {
                    "drive_activities": ["timestamp", "collected_at"],
                    "drive_files": ["created_time", "modified_time", "collected_at"],
                }
            },
            "Recordings (Shared)": {
                "db": shared_db,
                "collections": {
                    "recordings": ["createdTime", "modifiedTime"],
                }
            },
            "Recordings (Gemini)": {
                "db": gemini_db,
                "collections": {
                    "recordings": ["meeting_date", "timestamp"],
                    "recordings_daily": ["target_date", "timestamp"],
                }
            }
        }
        
        print("=" * 80)
        print("📊 Data Date Ranges by Source")
        print("=" * 80)
        print()
        
        all_november_data = defaultdict(dict)
        
        for source_name, source_config in sources.items():
            print(f"🔍 {source_name}")
            print("-" * 80)
            
            source_db = source_config["db"]
            source_earliest = None
            source_latest = None
            total_docs = 0
            
            for collection_name, timestamp_fields in source_config["collections"].items():
                try:
                    collection = source_db[collection_name]
                    doc_count = collection.count_documents({})
                    
                    if doc_count == 0:
                        print(f"   📦 {collection_name}: No documents")
                        continue
                    
                    print(f"   📦 {collection_name}: {doc_count:,} documents")
                    
                    results = check_collection_date_range(collection, timestamp_fields, collection_name)
                    
                    # Use the primary timestamp field (first one) for November check
                    primary_field = timestamp_fields[0] if timestamp_fields else None
                    
                    for result in results:
                        earliest = result['earliest']
                        latest = result['latest']
                        count = result['count']
                        
                        # Format dates
                        if isinstance(earliest, datetime):
                            earliest_str = earliest.strftime("%Y-%m-%d %H:%M:%S UTC")
                            earliest_dt = earliest
                        else:
                            earliest_str = str(earliest)
                            earliest_dt = None
                        
                        if isinstance(latest, datetime):
                            latest_str = latest.strftime("%Y-%m-%d %H:%M:%S UTC")
                            latest_dt = latest
                        else:
                            latest_str = str(latest)
                            latest_dt = None
                        
                        print(f"      • {result['field']}:")
                        print(f"        - Earliest: {earliest_str} ({count:,} docs)")
                        print(f"        - Latest:   {latest_str}")
                        
                        # Track source-wide earliest/latest
                        if earliest_dt:
                            if source_earliest is None or earliest_dt < source_earliest:
                                source_earliest = earliest_dt
                        if latest_dt:
                            if source_latest is None or latest_dt > source_latest:
                                source_latest = latest_dt
                    
                    # Check November data for primary field
                    if primary_field:
                        nov_data = check_november_data(collection, primary_field, collection_name)
                        if nov_data:
                            all_november_data[source_name][collection_name] = nov_data
                            print(f"      📅 November 2025: {nov_data['total']:,} documents")
                            
                            # Show missing days if any
                            if nov_data['daily_counts']:
                                missing_days = []
                                for day in range(1, 31):
                                    date_str = f"2025-11-{day:02d}"
                                    if date_str not in nov_data['daily_counts']:
                                        missing_days.append(day)
                                
                                if missing_days:
                                    print(f"        ⚠️  Missing days: {missing_days}")
                                else:
                                    print(f"        ✅ All days covered")
                    
                    total_docs += doc_count
                    
                except Exception as e:
                    print(f"   ❌ Error checking {collection_name}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            # Print source summary
            if source_earliest and source_latest:
                print()
                print(f"   📊 {source_name} Summary:")
                print(f"      - Earliest data: {source_earliest.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                print(f"      - Latest data:   {source_latest.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                print(f"      - Total documents: {total_docs:,}")
            
            print()
            print()
        
        # November 2025 Summary
        print("=" * 80)
        print("📅 November 2025 Data Collection Status")
        print("=" * 80)
        print()
        
        for source_name, collections_data in all_november_data.items():
            print(f"🔍 {source_name}")
            print("-" * 80)
            
            for collection_name, nov_data in collections_data.items():
                print(f"   📦 {collection_name}:")
                print(f"      Total November documents: {nov_data['total']:,}")
                
                if nov_data['daily_counts']:
                    # Show daily breakdown
                    print(f"      Daily breakdown:")
                    for date_str in sorted(nov_data['daily_counts'].keys()):
                        count = nov_data['daily_counts'][date_str]
                        print(f"        - {date_str}: {count:,} documents")
                    
                    # Check for missing days
                    missing_days = []
                    for day in range(1, 31):
                        date_str = f"2025-11-{day:02d}"
                        if date_str not in nov_data['daily_counts']:
                            missing_days.append(day)
                    
                    if missing_days:
                        print(f"      ⚠️  Missing days: {missing_days}")
                    else:
                        print(f"      ✅ All 30 days have data")
                else:
                    print(f"      ⚠️  Could not get daily breakdown")
            
            print()
        
        print("=" * 80)
        print("✅ Check completed!")
        print("=" * 80)
        
        client.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
