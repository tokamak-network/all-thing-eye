#!/usr/bin/env python3
"""Check projects configuration in MongoDB."""
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
        'uri': os.getenv('MONGODB_URI'),
        'database': os.getenv('MONGODB_DATABASE', 'all_thing_eye')
    }
    mongo = get_mongo_manager(mongodb_config)
    mongo.connect_async()
    db = mongo.async_db
    
    # Check projects collection
    projects = await db['projects'].find({}).to_list(length=None)
    print('=== Projects in DB ===')
    for p in projects:
        key = p.get('key', p.get('name', 'unknown'))
        active = p.get('is_active', p.get('active', '?'))
        repos = p.get('repositories', p.get('repos', []))
        print(f"  {key}: active={active}")
        if repos:
            print(f"    repos: {repos[:5]}...")  # First 5 repos
    
    mongo.close()

if __name__ == '__main__':
    asyncio.run(check())
