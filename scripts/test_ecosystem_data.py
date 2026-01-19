#!/usr/bin/env python3
"""
Test script for ecosystem data collection.

Tests:
1. Staking data from The Graph
2. Transaction counts from Etherscan
3. Market cap from CoinGecko

Usage:
    python scripts/test_ecosystem_data.py
    python scripts/test_ecosystem_data.py --collect  # Also collect and save to MongoDB
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()


async def test_staking_api():
    """Test staking data from The Graph API."""
    print("\n" + "=" * 60)
    print("📊 Testing Staking Data (The Graph)")
    print("=" * 60)
    
    try:
        from src.report.external_data.staking import get_staking_data, get_staking_summary_text
        
        data = await get_staking_data()
        
        print(f"✅ Staking data fetched successfully")
        print(f"   Latest staked: {data['latest_staked']:,.0f} TON")
        print(f"   Latest date: {data['latest_date']}")
        print(f"   Data points: {len(data['dates'])}")
        print(f"\n   Summary: {get_staking_summary_text(data)}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def test_transactions_api():
    """Test transaction counts from Etherscan API."""
    print("\n" + "=" * 60)
    print("📊 Testing Transaction Data (Etherscan)")
    print("=" * 60)
    
    try:
        from src.report.external_data.transactions import get_ton_wton_tx_counts, get_transactions_summary_text
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=14)
        
        print(f"   Fetching transactions from {start_date.date()} to {end_date.date()}...")
        print("   (This may take a minute due to Etherscan rate limits)")
        
        data = await get_ton_wton_tx_counts(start_date, end_date)
        
        print(f"✅ Transaction data fetched successfully")
        print(f"   TON transactions: {data['ton_count']}")
        print(f"   WTON transactions: {data['wton_count']}")
        print(f"\n   Summary: {get_transactions_summary_text(data)}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def test_market_cap_api():
    """Test market cap data from CoinGecko API."""
    print("\n" + "=" * 60)
    print("📊 Testing Market Cap Data (CoinGecko)")
    print("=" * 60)
    
    try:
        from src.report.external_data.market_cap import get_market_cap_data, get_market_cap_summary_text, _format_number, _format_supply
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=14)
        
        data = await get_market_cap_data(start_date, end_date)
        
        print(f"✅ Market cap data fetched successfully")
        print(f"   Market Cap: {_format_number(data['market_cap'])}")
        print(f"   Total Supply: {_format_supply(data['total_supply'])} TON")
        print(f"   Current Price: ${data['current_price']:.4f}")
        print(f"   Price High: ${data['price_high']:.4f}")
        print(f"   Price Low: ${data['price_low']:.4f}")
        print(f"   Trading Volume: {_format_number(data['trading_volume'])}")
        print(f"\n   Summary: {get_market_cap_summary_text(data)}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def test_collect_and_save():
    """Test full collection and save to MongoDB."""
    print("\n" + "=" * 60)
    print("📊 Testing Full Collection (MongoDB)")
    print("=" * 60)
    
    import os
    from src.core.mongo_manager import get_mongo_manager
    from src.plugins.ecosystem_plugin_mongo import EcosystemPluginMongo
    
    # Initialize MongoDB
    mongodb_config = {
        'uri': os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
        'database': os.getenv('MONGODB_DATABASE', 'all_thing_eye')
    }
    
    try:
        mongo_manager = get_mongo_manager(mongodb_config)
        mongo_manager.connect_async()
        
        print(f"   Connected to MongoDB: {mongodb_config['database']}")
        
        # Initialize plugin
        plugin_config = {
            'enabled': True,
            'subgraph_api_key': os.getenv('SUBGRAPH_API_KEY', ''),
            'etherscan_api_key': os.getenv('ETHERSCAN_API_KEY', '')
        }
        
        plugin = EcosystemPluginMongo(plugin_config, mongo_manager)
        plugin.authenticate()
        
        # Collect all data
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=14)
        
        print(f"   Collecting data for {start_date.date()} to {end_date.date()}...")
        
        results = await plugin.collect_all(start_date, end_date)
        
        print(f"\n✅ Collection completed:")
        print(f"   Staking: {results['staking']['count']} records saved")
        print(f"   Transactions: {'✓' if results['transactions']['success'] else '✗'}")
        print(f"   Market Cap: {'✓' if results['market_cap']['success'] else '✗'}")
        
        # Verify data in MongoDB
        db = mongo_manager.async_db
        
        staking_count = await db['ecosystem_staking'].count_documents({})
        tx_count = await db['ecosystem_transactions'].count_documents({})
        market_count = await db['ecosystem_market_cap'].count_documents({})
        
        print(f"\n   MongoDB Collections:")
        print(f"   - ecosystem_staking: {staking_count} documents")
        print(f"   - ecosystem_transactions: {tx_count} documents")
        print(f"   - ecosystem_market_cap: {market_count} documents")
        
        mongo_manager.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Test ecosystem data collection')
    parser.add_argument('--collect', action='store_true', help='Also collect and save to MongoDB')
    parser.add_argument('--staking-only', action='store_true', help='Test only staking data')
    parser.add_argument('--transactions-only', action='store_true', help='Test only transaction data')
    parser.add_argument('--market-only', action='store_true', help='Test only market cap data')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🧪 Ecosystem Data Collection Test")
    print("=" * 60)
    
    results = {}
    
    if args.staking_only:
        results['staking'] = await test_staking_api()
    elif args.transactions_only:
        results['transactions'] = await test_transactions_api()
    elif args.market_only:
        results['market'] = await test_market_cap_api()
    elif args.collect:
        results['full_collection'] = await test_collect_and_save()
    else:
        # Run all API tests
        results['staking'] = await test_staking_api()
        results['market'] = await test_market_cap_api()
        # Skip transactions by default (slow due to rate limits)
        print("\n⏭️  Skipping transaction test (use --transactions-only to test)")
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 Test Summary")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
