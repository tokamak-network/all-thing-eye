#!/usr/bin/env python3
"""Check ecosystem data in MongoDB."""
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
    
    print("=" * 60)
    print("MongoDB Ecosystem Data Check")
    print("=" * 60)
    
    # Check collections
    staking_count = await db['ecosystem_staking'].count_documents({})
    tx_count = await db['ecosystem_transactions'].count_documents({})
    market_count = await db['ecosystem_market_cap'].count_documents({})
    
    print(f"ecosystem_staking: {staking_count} documents")
    print(f"ecosystem_transactions: {tx_count} documents")
    print(f"ecosystem_market_cap: {market_count} documents")
    print()
    
    # Show sample staking data
    if staking_count > 0:
        sample = await db['ecosystem_staking'].find_one(sort=[('date', -1)])
        ton_amount = sample.get('total_staked_ton', 0)
        print(f"Latest staking: {sample.get('date')} - {ton_amount:,.0f} TON")
        
        oldest = await db['ecosystem_staking'].find_one(sort=[('date', 1)])
        print(f"Oldest staking: {oldest.get('date')}")
    
    # Show sample market cap
    if market_count > 0:
        sample = await db['ecosystem_market_cap'].find_one(sort=[('date', -1)])
        cap = sample.get('market_cap_usd', 0)
        print(f"Latest market cap: {sample.get('date')} - ${cap:,.0f}")
    
    print("=" * 60)
    mongo.close()

if __name__ == '__main__':
    asyncio.run(check())
