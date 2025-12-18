#!/usr/bin/env python3
"""
Debug script to check Kevin's recordings with gemini.recordings join
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime
from bson import ObjectId

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import Config
from src.core.mongo_manager import MongoDBManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def debug_kevin_recordings():
    print("=" * 80)
    print("🔍 DEBUGGING KEVIN'S RECORDINGS JOIN")
    print("=" * 80)
    
    config = Config()
    mongo_config = {
        'uri': config.get('mongodb.uri', 'mongodb://localhost:27017'),
        'database': config.get('mongodb.database', 'all_thing_eye_test')
    }
    mongo_manager = MongoDBManager(mongo_config)
    mongo_manager.connect_async()  # Returns client, doesn't need await
    
    try:
        # Get shared DB (main)
        shared_db = mongo_manager.async_db
        shared_recordings_col = shared_db["recordings"]
        
        # Get gemini DB
        from backend.api.v1.ai_processed import get_gemini_db
        gemini_db = get_gemini_db()
        gemini_recordings_col = gemini_db["recordings"]
        
        member_name = "Kevin"
        
        # Step 1: Check gemini.recordings structure
        print(f"\n1️⃣ Checking gemini.recordings structure")
        sample_gemini = gemini_recordings_col.find_one()
        if sample_gemini:
            print(f"   Sample document keys: {list(sample_gemini.keys())}")
            print(f"   Sample document:")
            print(json.dumps({k: str(v)[:100] if len(str(v)) > 100 else v 
                            for k, v in sample_gemini.items() if k != '_id'}, 
                           indent=2, default=str))
            
            # Check if meeting_id field exists
            if 'meeting_id' in sample_gemini:
                print(f"   ✅ 'meeting_id' field exists: {sample_gemini['meeting_id']}")
            else:
                print(f"   ⚠️  'meeting_id' field NOT found. Available fields: {list(sample_gemini.keys())}")
        else:
            print(f"   ❌ No documents in gemini.recordings")
            return
        
        # Step 2: Find Kevin in gemini.recordings participants
        print(f"\n2️⃣ Searching for '{member_name}' in gemini.recordings participants")
        
        # participants is a simple string array, not nested objects
        participant_query = {
            'participants': {'$regex': f'\\b{member_name}\\b', '$options': 'i'}
        }
        
        print(f"   Query: {json.dumps(participant_query, indent=2)}")
        
        gemini_docs = list(gemini_recordings_col.find(participant_query))
        print(f"   Found {len(gemini_docs)} documents")
        
        if not gemini_docs:
            print(f"   ❌ No documents found. Let's check what participant names exist:")
            
            # Sample 10 documents and show participant names
            sample_docs = list(gemini_recordings_col.find().limit(10))
            all_participant_names = set()
            for doc in sample_docs:
                analysis = doc.get('analysis', {})
                participants = analysis.get('participants', [])
                for p in participants:
                    if isinstance(p, dict) and 'name' in p:
                        all_participant_names.add(p['name'])
            
            print(f"   Sample participant names: {sorted(list(all_participant_names))}")
            return
        
        # Step 3: Extract meeting_ids
        print(f"\n3️⃣ Extracting meeting_ids from gemini.recordings")
        meeting_ids = []
        for doc in gemini_docs:
            mid = doc.get('meeting_id')
            if mid:
                meeting_ids.append(mid)
                print(f"   - meeting_id: {mid} (type: {type(mid).__name__})")
        
        print(f"   Total meeting_ids: {len(meeting_ids)}")
        
        if not meeting_ids:
            print(f"   ❌ No meeting_ids found in documents")
            print(f"   Available fields in first doc: {list(gemini_docs[0].keys())}")
            return
        
        # Step 4: Convert to ObjectIds
        print(f"\n4️⃣ Converting meeting_ids to ObjectIds")
        object_ids = []
        for mid in meeting_ids:
            try:
                if isinstance(mid, str):
                    oid = ObjectId(mid)
                    object_ids.append(oid)
                    print(f"   ✅ Converted '{mid}' to ObjectId")
                elif isinstance(mid, ObjectId):
                    object_ids.append(mid)
                    print(f"   ✅ Already ObjectId: {mid}")
                else:
                    print(f"   ⚠️  Unknown type for meeting_id: {type(mid)}")
            except Exception as e:
                print(f"   ❌ Failed to convert '{mid}': {e}")
        
        print(f"   Total valid ObjectIds: {len(object_ids)}")
        
        if not object_ids:
            print(f"   ❌ No valid ObjectIds")
            return
        
        # Step 5: Query shared.recordings with ObjectIds
        print(f"\n5️⃣ Querying shared.recordings with ObjectIds")
        
        query = {'_id': {'$in': object_ids}}
        print(f"   Query: {query}")
        
        matching_recordings = []
        async for rec in shared_recordings_col.find(query):
            matching_recordings.append(rec)
            print(f"   ✅ Found recording: {rec.get('name', 'Unknown')}")
            print(f"      - _id: {rec['_id']}")
            print(f"      - created_by: {rec.get('created_by')}")
            print(f"      - modifiedTime: {rec.get('modifiedTime')}")
        
        print(f"\n   Total matching recordings in shared.recordings: {len(matching_recordings)}")
        
        if not matching_recordings:
            print(f"   ❌ No matching recordings found in shared.recordings")
            print(f"\n   Let's check if these _ids exist at all:")
            
            for oid in object_ids[:3]:  # Check first 3
                exists = await shared_recordings_col.find_one({'_id': oid})
                if exists:
                    print(f"   ✅ ObjectId {oid} EXISTS in shared.recordings")
                else:
                    print(f"   ❌ ObjectId {oid} NOT FOUND in shared.recordings")
        
        # Step 6: Check if field name is different
        print(f"\n6️⃣ Checking alternative field names in gemini.recordings")
        first_gemini_doc = gemini_docs[0]
        possible_id_fields = [k for k in first_gemini_doc.keys() if 'id' in k.lower()]
        print(f"   Fields containing 'id': {possible_id_fields}")
        
        for field in possible_id_fields:
            value = first_gemini_doc.get(field)
            print(f"   - {field}: {value} (type: {type(value).__name__})")
    
    finally:
        if mongo_manager:
            mongo_manager.close()
    
    print(f"\n" + "=" * 80)
    print(f"✅ DEBUG COMPLETE")
    print(f"=" * 80)


if __name__ == "__main__":
    asyncio.run(debug_kevin_recordings())

