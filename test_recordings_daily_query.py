#!/usr/bin/env python3
"""
Test script to directly query MongoDB for recordings_daily with Ale Son
"""
import asyncio
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

async def test_recordings_daily():
    # Load environment
    load_dotenv()
    mongo_uri = os.getenv("MONGODB_URI")
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(mongo_uri)
    gemini_db = client["gemini"]
    recordings_daily_col = gemini_db["recordings_daily"]
    
    print("=" * 80)
    print("TEST 1: Check recent documents (12/12, 12/11, 12/10)")
    print("=" * 80)
    
    # Check specific dates
    target_dates = ["2025-12-12", "2025-12-11", "2025-12-10"]
    
    for date in target_dates:
        doc = await recordings_daily_col.find_one({"target_date": date})
        if doc:
            print(f"\n📅 {date}:")
            analysis = doc.get("analysis", {})
            participants = analysis.get("participants", [])
            
            if isinstance(participants, list):
                print(f"   Total participants: {len(participants)}")
                names = [p.get("name") for p in participants if isinstance(p, dict) and "name" in p]
                print(f"   Names: {names}")
                
                # Check if Ale is in names
                ale_found = any("Ale" in name for name in names)
                print(f"   ✅ Ale found!" if ale_found else "   ❌ Ale NOT found")
            else:
                print(f"   ⚠️  Participants is not a list: {type(participants)}")
        else:
            print(f"\n📅 {date}: ❌ Document not found")
    
    print("\n" + "=" * 80)
    print("TEST 2: Test MongoDB query with $elemMatch")
    print("=" * 80)
    
    # Test the actual query we use in GraphQL
    query = {
        'analysis.participants': {
            '$elemMatch': {
                'name': {'$regex': r'\bAle\b', '$options': 'i'}
            }
        }
    }
    
    print(f"\nQuery: {query}")
    
    # Count documents
    count = await recordings_daily_col.count_documents(query)
    print(f"\n✅ Total documents matching: {count}")
    
    # Get matched documents
    cursor = recordings_daily_col.find(query).sort('target_date', -1).limit(20)
    matched_docs = await cursor.to_list(length=20)
    
    if matched_docs:
        print(f"\n📋 Matched dates (first 20):")
        for doc in matched_docs:
            target_date = doc.get('target_date')
            analysis = doc.get('analysis', {})
            participants = analysis.get('participants', [])
            names = [p.get('name') for p in participants if isinstance(p, dict) and 'name' in p]
            ale_names = [n for n in names if 'Ale' in n]
            print(f"   {target_date}: {ale_names}")
        
        # Check date range
        oldest = matched_docs[-1].get('target_date')
        newest = matched_docs[0].get('target_date')
        print(f"\n📊 Date range: {newest} to {oldest}")
    else:
        print("\n❌ No documents matched!")
    
    print("\n" + "=" * 80)
    print("TEST 3: Check all recent documents (last 15)")
    print("=" * 80)
    
    cursor = recordings_daily_col.find({}).sort('target_date', -1).limit(15)
    recent_docs = await cursor.to_list(length=15)
    
    print(f"\n📋 All recent documents:")
    for doc in recent_docs:
        target_date = doc.get('target_date')
        analysis = doc.get('analysis', {})
        participants = analysis.get('participants', [])
        
        names = []
        if isinstance(participants, list):
            names = [p.get('name') for p in participants if isinstance(p, dict) and 'name' in p]
        
        # Check if Ale is in names
        ale_found = any('Ale' in name for name in names)
        status = "✅" if ale_found else "❌"
        ale_names = [n for n in names if 'Ale' in n] if ale_found else []
        
        print(f"   {status} {target_date}: {ale_names if ale_found else '(No Ale)'}")
    
    # Close connection
    client.close()
    print("\n" + "=" * 80)
    print("Test complete!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_recordings_daily())
