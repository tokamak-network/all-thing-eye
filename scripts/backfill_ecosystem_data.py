#!/usr/bin/env python3
"""
Backfill Ecosystem Data Script

Collects historical ecosystem data (staking, transactions, market cap) 
and saves to MongoDB.

Usage:
    # Backfill from Jan 1, 2025 to today
    python scripts/backfill_ecosystem_data.py
    
    # Custom date range
    python scripts/backfill_ecosystem_data.py --start-date 2025-01-01 --end-date 2025-01-31
    
    # Staking only (faster, no rate limits)
    python scripts/backfill_ecosystem_data.py --staking-only
    
    # Market cap only
    python scripts/backfill_ecosystem_data.py --market-only
"""

import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.core.mongo_manager import get_mongo_manager
from src.plugins.ecosystem_plugin_mongo import EcosystemPluginMongo
from src.utils.logger import get_logger

logger = get_logger(__name__)

KST = ZoneInfo("Asia/Seoul")


async def backfill_staking(mongo_manager, plugin: EcosystemPluginMongo):
    """
    Backfill staking data.
    Staking data comes from The Graph with historical daily snapshots.
    """
    logger.info("📊 Backfilling staking data...")
    
    try:
        # Fetch all available staking data (up to 365 days)
        staking_data = await plugin.collect_staking_data()
        count = await plugin.save_staking_data(staking_data)
        
        logger.info(f"✅ Staking: {count} records saved")
        
        # Show date range
        if staking_data.get("records"):
            first_date = staking_data["records"][0]["date"]
            last_date = staking_data["records"][-1]["date"]
            logger.info(f"   Date range: {first_date} to {last_date}")
        
        return count
    except Exception as e:
        logger.error(f"❌ Staking backfill failed: {e}")
        return 0


async def backfill_market_cap(
    mongo_manager,
    plugin: EcosystemPluginMongo,
    start_date: datetime,
    end_date: datetime,
    interval_days: int = 14
):
    """
    Backfill market cap data.
    
    Note: CoinGecko free API doesn't support historical date range queries.
    This will only fetch current market data and save it once.
    For historical data, you need CoinGecko Pro API.
    """
    logger.info(f"📊 Fetching current market cap data...")
    logger.warning("   ⚠️ CoinGecko free API only supports current data, not historical ranges")
    
    total_saved = 0
    
    try:
        # Only fetch current market data (CoinGecko free tier limitation)
        # The current endpoint works, but /market_chart/range requires Pro
        market_data = await plugin.collect_market_cap_data(
            start_date=datetime.now() - timedelta(days=14),  # Last 2 weeks for high/low
            end_date=datetime.now()
        )
        
        if market_data:
            success = await plugin.save_market_cap_data(market_data)
            if success:
                total_saved += 1
                logger.info(f"   ✅ Saved current market cap: ${market_data.get('market_cap_usd', 0):,.0f}")
        
    except Exception as e:
        logger.warning(f"   ⚠️ Market cap fetch failed: {e}")
    
    logger.info(f"✅ Market cap: {total_saved} record(s) saved")
    logger.info("   💡 For historical data, run daily collection going forward")
    return total_saved


async def backfill_transactions(
    mongo_manager,
    plugin: EcosystemPluginMongo,
    start_date: datetime,
    end_date: datetime,
    interval_days: int = 14
):
    """
    Backfill transaction data in chunks.
    
    WARNING: This is slow due to Etherscan rate limits.
    Each period requires multiple API calls.
    """
    logger.info(f"📊 Backfilling transaction data from {start_date.date()} to {end_date.date()}...")
    logger.warning("   ⚠️ This will be slow due to Etherscan rate limits")
    
    total_saved = 0
    current_start = start_date
    
    while current_start < end_date:
        current_end = min(current_start + timedelta(days=interval_days), end_date)
        
        try:
            logger.info(f"   Fetching {current_start.date()} to {current_end.date()}...")
            
            tx_data = await plugin.collect_transaction_data(current_start, current_end)
            
            if tx_data:
                success = await plugin.save_transaction_data(tx_data)
                if success:
                    total_saved += 1
                    logger.info(f"      TON: {tx_data['ton_count']}, WTON: {tx_data['wton_count']}")
            
            # Longer delay for Etherscan (5 calls/sec free tier)
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.warning(f"   ⚠️ Failed for {current_start.date()}: {e}")
            await asyncio.sleep(10)  # Wait longer on error
        
        current_start = current_end
    
    logger.info(f"✅ Transactions: {total_saved} records saved")
    return total_saved


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Backfill ecosystem data')
    parser.add_argument(
        '--start-date',
        type=str,
        default='2025-01-01',
        help='Start date (YYYY-MM-DD). Default: 2025-01-01'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        default=None,
        help='End date (YYYY-MM-DD). Default: today'
    )
    parser.add_argument(
        '--staking-only',
        action='store_true',
        help='Only backfill staking data'
    )
    parser.add_argument(
        '--market-only',
        action='store_true',
        help='Only backfill market cap data'
    )
    parser.add_argument(
        '--transactions-only',
        action='store_true',
        help='Only backfill transaction data (slow)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=14,
        help='Days per chunk for market/tx data. Default: 14'
    )
    
    args = parser.parse_args()
    
    # Parse dates
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
    if args.end_date:
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    else:
        end_date = datetime.now()
    
    logger.info("=" * 70)
    logger.info("🔄 Ecosystem Data Backfill")
    logger.info("=" * 70)
    logger.info(f"📅 Date range: {start_date.date()} to {end_date.date()}")
    
    # Initialize MongoDB
    mongodb_config = {
        'uri': os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
        'database': os.getenv('MONGODB_DATABASE', 'all_thing_eye')
    }
    
    mongo_manager = get_mongo_manager(mongodb_config)
    mongo_manager.connect_async()
    
    logger.info(f"📦 Connected to MongoDB: {mongodb_config['database']}")
    
    # Initialize plugin
    plugin_config = {
        'enabled': True,
        'subgraph_api_key': os.getenv('SUBGRAPH_API_KEY', ''),
        'etherscan_api_key': os.getenv('ETHERSCAN_API_KEY', '')
    }
    
    plugin = EcosystemPluginMongo(plugin_config, mongo_manager)
    plugin.authenticate()
    
    try:
        results = {}
        
        # Determine what to backfill
        if args.staking_only:
            results['staking'] = await backfill_staking(mongo_manager, plugin)
        elif args.market_only:
            results['market_cap'] = await backfill_market_cap(
                mongo_manager, plugin, start_date, end_date, args.interval
            )
        elif args.transactions_only:
            results['transactions'] = await backfill_transactions(
                mongo_manager, plugin, start_date, end_date, args.interval
            )
        else:
            # Default: staking and market cap (skip transactions due to slowness)
            logger.info("\n📌 Running default backfill (staking + market cap)")
            logger.info("   Use --transactions-only to also backfill transaction data\n")
            
            results['staking'] = await backfill_staking(mongo_manager, plugin)
            results['market_cap'] = await backfill_market_cap(
                mongo_manager, plugin, start_date, end_date, args.interval
            )
        
        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("📋 Backfill Summary")
        logger.info("=" * 70)
        
        for data_type, count in results.items():
            logger.info(f"   {data_type}: {count} records")
        
        # Show collection stats
        db = mongo_manager.async_db
        
        logger.info("\n📊 MongoDB Collection Stats:")
        for coll_name in ['ecosystem_staking', 'ecosystem_transactions', 'ecosystem_market_cap']:
            count = await db[coll_name].count_documents({})
            logger.info(f"   {coll_name}: {count} documents")
        
        logger.info("=" * 70)
        logger.info("✅ Backfill completed!")
        
    finally:
        mongo_manager.close()


if __name__ == '__main__':
    asyncio.run(main())
