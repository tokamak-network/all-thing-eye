#!/usr/bin/env python3
"""Quick script to check MongoDB collections."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from src.core.mongo_manager import get_mongo_manager

async def check():
    mongodb_config = {
        'uri': os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
        'database': os.getenv('MONGODB_DATABASE', 'all_thing_eye')
    }
    mongo = get_mongo_manager(mongodb_config)
    mongo.connect_async()
    db = mongo.async_db
    
    # List all collections
    collections = await db.list_collection_names()
    print('=== Collections ===')
    for col in sorted(collections):
        count = await db[col].count_documents({})
        print(f'  {col}: {count} docs')
    
    print('\n=== GitHub Collections Detail ===')
    for col in collections:
        if 'github' in col.lower() or 'commit' in col.lower():
            count = await db[col].count_documents({})
            print(f'\n{col}: {count} docs')
            if count > 0:
                sample = await db[col].find_one()
                print(f'  Keys: {list(sample.keys())}')
                # Show a few important fields
                for key in ['committed_at', 'timestamp', 'created_at', 'date', 'repository', 'repo', 'message']:
                    if key in sample:
                        print(f'  {key}: {sample[key]}')
    
    mongo.close()

if __name__ == '__main__':
    asyncio.run(check())
