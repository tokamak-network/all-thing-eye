#!/usr/bin/env python3
"""
Check Data Date Range for All Sources

This script queries MongoDB to find the earliest and latest data points
for each data source (GitHub, Slack, Notion, Drive).

Usage:
    python scripts/check_data_date_range.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

def get_mongodb_uri() -> str:
    """Get MongoDB URI from environment"""
    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise ValueError("MONGODB_URI environment variable not set")
    return uri

def get_mongodb_database() -> str:
    """Get MongoDB database name from environment"""
    return os.getenv("MONGODB_DATABASE", "ati")

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

def main():
    print("=" * 80)
    print("📅 Data Date Range Checker")
    print("=" * 80)
    print(f"Started at: {datetime.now()}\n")
    
    # Get MongoDB connection info
    uri = get_mongodb_uri()
    database_name = get_mongodb_database()
    
    print(f"Database: {database_name}")
    print(f"URI: {uri.split('@')[-1] if '@' in uri else uri}\n")
    
    try:
        # Connect to MongoDB
        client = MongoClient(uri)
        db = client[database_name]
        
        # Define sources and their collections with timestamp fields
        sources = {
            "GitHub": {
                "collections": {
                    "github_commits": ["committed_at", "collected_at"],
                    "github_pull_requests": ["created_at", "collected_at"],
                    "github_issues": ["created_at", "collected_at"],
                }
            },
            "Slack": {
                "collections": {
                    "slack_messages": ["posted_at", "collected_at"],
                }
            },
            "Notion": {
                "collections": {
                    "notion_pages": ["created_time", "last_edited_time", "collected_at"],
                }
            },
            "Drive": {
                "collections": {
                    "drive_activities": ["timestamp", "collected_at"],
                    "drive_files": ["created_time", "modified_time", "collected_at"],
                }
            }
        }
        
        print("=" * 80)
        print("📊 Data Date Ranges by Source")
        print("=" * 80)
        print()
        
        for source_name, source_config in sources.items():
            print(f"🔍 {source_name}")
            print("-" * 80)
            
            source_earliest = None
            source_latest = None
            total_docs = 0
            
            for collection_name, timestamp_fields in source_config["collections"].items():
                try:
                    collection = db[collection_name]
                    doc_count = collection.count_documents({})
                    
                    if doc_count == 0:
                        print(f"   📦 {collection_name}: No documents")
                        continue
                    
                    print(f"   📦 {collection_name}: {doc_count:,} documents")
                    
                    results = check_collection_date_range(collection, timestamp_fields, collection_name)
                    
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
                    
                    total_docs += doc_count
                    
                except Exception as e:
                    print(f"   ❌ Error checking {collection_name}: {e}")
                    continue
            
            # Print source summary
            if source_earliest and source_latest:
                print()
                print(f"   📊 {source_name} Summary:")
                print(f"      - Earliest data: {source_earliest.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                print(f"      - Latest data:   {source_latest.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                
                # Check if 2025 data exists
                year_2025_start = datetime(2025, 1, 1)
                year_2025_end = datetime(2025, 12, 31, 23, 59, 59)
                
                has_2025_data = source_earliest <= year_2025_end and source_latest >= year_2025_start
                
                if has_2025_data:
                    # Calculate coverage
                    if source_earliest < year_2025_start:
                        coverage_start = year_2025_start
                    else:
                        coverage_start = source_earliest
                    
                    if source_latest > year_2025_end:
                        coverage_end = year_2025_end
                    else:
                        coverage_end = source_latest
                    
                    coverage_days = (coverage_end - coverage_start).days + 1
                    total_2025_days = 365
                    coverage_percent = (coverage_days / total_2025_days) * 100
                    
                    print(f"      - 2025 Coverage: {coverage_days}/{total_2025_days} days ({coverage_percent:.1f}%)")
                    
                    if source_earliest > year_2025_start:
                        missing_days = (year_2025_start - source_earliest).days
                        print(f"      - ⚠️  Missing: {abs(missing_days)} days from start of 2025")
                    if source_latest < year_2025_end:
                        missing_days = (year_2025_end - source_latest).days
                        print(f"      - ⚠️  Missing: {missing_days} days until end of 2025")
                else:
                    print(f"      - ❌ No 2025 data found")
            
            print()
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

