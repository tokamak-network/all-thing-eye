#!/usr/bin/env python3
"""
Check Recordings and Daily Analysis Participants Data Structure

This script checks the actual data structure of recordings and daily analysis
to see if participant filtering is possible.
"""

import sys
from pathlib import Path
from pymongo import MongoClient
from datetime import datetime
import json
from bson import ObjectId
from bson.json_util import dumps

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

import os
from src.core.config import Config

config = Config()

# MongoDB connection
mongodb_uri = os.getenv('MONGODB_URI', config.get('mongodb.uri', 'mongodb://localhost:27017'))
shared_uri = os.getenv('MONGODB_SHARED_URI', mongodb_uri)
main_db_name = os.getenv('MONGODB_DATABASE', config.get('mongodb.database', 'ati'))
shared_db_name = os.getenv('MONGODB_SHARED_DATABASE', 'shared')
gemini_db_name = 'gemini'

print("=" * 80)
print("🔍 Checking Recordings and Daily Analysis Participants Data Structure")
print("=" * 80)
print(f"\n📊 MongoDB URI: {mongodb_uri}")
print(f"📊 Shared DB: {shared_db_name}")
print(f"📊 Gemini DB: {gemini_db_name}")
print()

try:
    # Connect to MongoDB (increase timeout for remote connections)
    client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=30000, connectTimeoutMS=30000)
    client.admin.command('ping')
    print("✅ Connected to MongoDB\n")
    
    # Check shared.recordings collection
    print("=" * 80)
    print("1️⃣ Checking shared.recordings collection")
    print("=" * 80)
    shared_db = client[shared_db_name]
    recordings_col = shared_db['recordings']
    
    total_recordings = recordings_col.count_documents({})
    print(f"📊 Total recordings: {total_recordings}")
    
    if total_recordings > 0:
        # Get one sample recording
        sample = recordings_col.find_one({}, {'content': 0})  # Exclude large content field
        if sample:
            print("\n📄 Sample recording fields:")
            for key in sample.keys():
                value = sample[key]
                if isinstance(value, (list, dict)):
                    print(f"   - {key}: {type(value).__name__} (length: {len(value) if isinstance(value, list) else 'N/A'})")
                    if key == 'participants' and isinstance(value, list):
                        print(f"     → First participant: {value[0] if value else 'N/A'}")
                else:
                    print(f"   - {key}: {type(value).__name__} = {str(value)[:100]}")
            
            # Check if participants field exists
            if 'participants' in sample:
                print(f"\n✅ Found 'participants' field: {sample['participants']}")
            else:
                print("\n⚠️  No 'participants' field in shared.recordings")
                
            # Check createdBy field
            if 'createdBy' in sample:
                print(f"\n📝 createdBy field: {sample['createdBy']}")
    
    # Check gemini.recordings collection
    print("\n" + "=" * 80)
    print("2️⃣ Checking gemini.recordings collection")
    print("=" * 80)
    gemini_db = client[gemini_db_name]
    gemini_recordings_col = gemini_db['recordings']
    
    total_gemini_recordings = gemini_recordings_col.count_documents({})
    print(f"📊 Total gemini recordings: {total_gemini_recordings}")
    
    if total_gemini_recordings > 0:
        # Get one sample
        sample = gemini_recordings_col.find_one({})
        if sample:
            print("\n📄 Sample gemini recording fields:")
            for key in sample.keys():
                value = sample[key]
                if isinstance(value, (list, dict)):
                    print(f"   - {key}: {type(value).__name__} (length: {len(value) if isinstance(value, list) else 'N/A'})")
                    if key == 'participants' and isinstance(value, list):
                        print(f"     → Participants: {value}")
                else:
                    print(f"   - {key}: {type(value).__name__} = {str(value)[:100]}")
            
            # Check if participants field exists
            if 'participants' in sample:
                print(f"\n✅ Found 'participants' field: {sample['participants']}")
            else:
                print("\n⚠️  No 'participants' field in gemini.recordings")
    
    # Check gemini.recordings_daily collection
    print("\n" + "=" * 80)
    print("3️⃣ Checking gemini.recordings_daily collection")
    print("=" * 80)
    recordings_daily_col = gemini_db['recordings_daily']
    
    total_daily = recordings_daily_col.count_documents({})
    print(f"📊 Total daily analyses: {total_daily}")
    
    if total_daily > 0:
        # Get one sample
        sample = recordings_daily_col.find_one({})
        if sample:
            print("\n📄 Sample daily analysis structure:")
            
            # Check analysis.participants
            if 'analysis' in sample and isinstance(sample['analysis'], dict):
                analysis = sample['analysis']
                if 'participants' in analysis:
                    participants = analysis['participants']
                    print(f"\n✅ Found 'analysis.participants' field")
                    print(f"   📊 Number of participants: {len(participants)}")
                    
                    if len(participants) > 0:
                        print(f"\n   📝 First participant structure:")
                        first_participant = participants[0]
                        for key, value in first_participant.items():
                            print(f"      - {key}: {type(value).__name__} = {str(value)[:100]}")
                        
                        # Show all participant names
                        print(f"\n   👥 All participant names:")
                        for i, p in enumerate(participants[:10], 1):  # Show first 10
                            name = p.get('name', 'N/A')
                            print(f"      {i}. {name}")
                        if len(participants) > 10:
                            print(f"      ... and {len(participants) - 10} more")
                else:
                    print("\n⚠️  No 'participants' field in analysis")
            else:
                print("\n⚠️  No 'analysis' field or it's not a dict")
    
    # Summary
    print("\n" + "=" * 80)
    print("📋 SUMMARY")
    print("=" * 80)
    
    can_filter_recordings = False
    can_filter_daily = False
    
    # Check recordings
    if total_recordings > 0:
        sample = recordings_col.find_one({}, {'participants': 1, 'createdBy': 1})
        if sample and 'participants' in sample:
            can_filter_recordings = True
            print("✅ Recordings: Can filter by participants (field exists in shared.recordings)")
        elif sample and 'createdBy' in sample:
            print("⚠️  Recordings: No 'participants' field, but has 'createdBy' field")
            print("   → May need to check gemini.recordings for participants")
            if total_gemini_recordings > 0:
                gemini_sample = gemini_recordings_col.find_one({}, {'participants': 1})
                if gemini_sample and 'participants' in gemini_sample:
                    can_filter_recordings = True
                    print("   ✅ Found participants in gemini.recordings")
        else:
            print("❌ Recordings: Cannot filter by participants (no participants field found)")
    
    # Check daily analysis
    if total_daily > 0:
        sample = recordings_daily_col.find_one({}, {'analysis.participants': 1})
        if sample and 'analysis' in sample and 'participants' in sample.get('analysis', {}):
            can_filter_daily = True
            print("✅ Daily Analysis: Can filter by participants (analysis.participants exists)")
        else:
            print("❌ Daily Analysis: Cannot filter by participants (no analysis.participants field found)")
    
    print("\n" + "=" * 80)
    if can_filter_recordings and can_filter_daily:
        print("✅ RESULT: Participant filtering is POSSIBLE for both recordings and daily analysis!")
    elif can_filter_recordings:
        print("⚠️  RESULT: Participant filtering is POSSIBLE for recordings only")
    elif can_filter_daily:
        print("⚠️  RESULT: Participant filtering is POSSIBLE for daily analysis only")
    else:
        print("❌ RESULT: Participant filtering is NOT POSSIBLE with current data structure")
    print("=" * 80)
    
    client.close()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

