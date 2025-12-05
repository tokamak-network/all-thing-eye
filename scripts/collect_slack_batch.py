#!/usr/bin/env python3
"""
Slack Batch Data Collection Script

Collects Slack data in smaller batches (default 7 days) with configurable intervals
to avoid rate limits and timeout errors.

Usage:
    # Collect from 2025-01-01 to 2025-08-29 in 7-day batches with 1-hour intervals
    python scripts/collect_slack_batch.py --start-date 2025-01-01 --end-date 2025-08-29
    
    # With custom batch size and interval
    python scripts/collect_slack_batch.py --start-date 2025-01-01 --end-date 2025-08-29 --batch-days 7 --interval-hours 1
"""

import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.core.config import Config
from src.core.mongo_manager import MongoDBManager, get_mongo_manager
from src.plugins.slack_plugin_mongo import SlackPluginMongo
from src.utils.logger import get_logger

logger = get_logger(__name__)

# UTC timezone
UTC = ZoneInfo("UTC")


def parse_date(date_str: str) -> datetime:
    """Parse date string in YYYY-MM-DD format"""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=UTC)
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD")


def split_date_range(start_date: datetime, end_date: datetime, batch_days: int = 7):
    """
    Split date range into batches
    
    Returns:
        List of (batch_start, batch_end) tuples
    """
    batches = []
    current_start = start_date
    
    while current_start < end_date:
        current_end = min(current_start + timedelta(days=batch_days - 1), end_date)
        # Set end time to end of day
        current_end = current_end.replace(hour=23, minute=59, second=59, microsecond=999999)
        batches.append((current_start, current_end))
        current_start = current_end + timedelta(seconds=1)
    
    return batches


async def collect_slack_batch(
    mongo_manager: MongoDBManager,
    start_date: datetime,
    end_date: datetime,
    batch_num: int,
    total_batches: int,
    dry_run: bool = False
):
    """Collect Slack data for a specific date range"""
    try:
        logger.info(f"\n{'='*80}")
        logger.info(f"📦 Batch {batch_num}/{total_batches}")
        logger.info(f"   Period: {start_date.date()} ~ {end_date.date()}")
        logger.info(f"   Duration: {(end_date - start_date).days + 1} days")
        logger.info(f"{'='*80}")
        
        if dry_run:
            logger.info("   🔍 DRY RUN: Would collect Slack data for this period")
            return True
        
        config = Config()
        plugin_config = config.get_plugin_config('slack')
        
        if not plugin_config or not plugin_config.get('enabled', False):
            logger.warning("   ⏭️  Slack plugin disabled, skipping")
            return False
        
        plugin = SlackPluginMongo(plugin_config, mongo_manager)
        
        if not plugin.authenticate():
            logger.error("   ❌ Slack authentication failed")
            return False
        
        # Convert to timezone-naive for plugin (plugin expects UTC-naive datetime)
        start_naive = start_date.replace(tzinfo=None)
        end_naive = end_date.replace(tzinfo=None)
        
        # Collect data
        logger.info(f"   🚀 Starting collection...")
        data_list = plugin.collect_data(start_date=start_naive, end_date=end_naive)
        
        # Slack plugin returns a list with one dict
        data = data_list[0] if data_list else {}
        
        # Save to MongoDB
        if data:
            await plugin.save_data(data)
        
        messages_count = len(data.get('messages', []))
        channels_count = len(data.get('channels', []))
        users_count = len(data.get('users', []))
        
        logger.info(f"   ✅ Batch {batch_num} completed:")
        logger.info(f"      - Messages: {messages_count:,}")
        logger.info(f"      - Channels: {channels_count}")
        logger.info(f"      - Users: {users_count}")
        
        return True
        
    except Exception as e:
        logger.error(f"   ❌ Batch {batch_num} failed: {e}", exc_info=True)
        return False


async def main():
    """Main collection function"""
    parser = argparse.ArgumentParser(
        description='Collect Slack data in batches to avoid rate limits and timeouts'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        required=True,
        help='Start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        required=True,
        help='End date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--batch-days',
        type=int,
        default=7,
        help='Number of days per batch (default: 7, recommended for Slack to avoid timeouts)'
    )
    parser.add_argument(
        '--interval-hours',
        type=int,
        default=1,
        help='Interval between batches in hours (default: 1)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be collected without actually collecting'
    )
    
    args = parser.parse_args()

    # Parse dates
    start_date = parse_date(args.start_date)
    end_date = parse_date(args.end_date)
    
    # Set start to beginning of day, end to end of day
    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    if start_date >= end_date:
        logger.error("❌ Start date must be before end date")
        sys.exit(1)
    
    # Split into batches
    batches = split_date_range(start_date, end_date, args.batch_days)
    total_batches = len(batches)
    
    logger.info("=" * 80)
    logger.info("🚀 Slack Batch Data Collection")
    logger.info("=" * 80)
    logger.info(f"📅 Date Range: {start_date.date()} ~ {end_date.date()}")
    logger.info(f"📦 Batch Size: {args.batch_days} days")
    logger.info(f"⏱️  Interval: {args.interval_hours} hour(s)")
    logger.info(f"📊 Total Batches: {total_batches}")
    logger.info(f"⏰ Estimated Duration: ~{total_batches * args.interval_hours} hours")
    logger.info("=" * 80)
    
    if args.dry_run:
        logger.info("\n📋 Batch Plan (DRY RUN):")
        for i, (batch_start, batch_end) in enumerate(batches, 1):
            days = (batch_end - batch_start).days + 1
            logger.info(f"   Batch {i}: {batch_start.date()} ~ {batch_end.date()} ({days} days)")
        logger.info("\n✅ Dry run complete. Remove --dry-run to start collection.")
        return
    
    # Initialize MongoDB connection
    import os
    mongodb_config = {
        'uri': os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
        'database': os.getenv('MONGODB_DATABASE', 'all_thing_eye')
    }
    mongo_manager = get_mongo_manager(mongodb_config)
    mongo_manager.connect_async()
    
    try:
        success_count = 0
        fail_count = 0
        
        for i, (batch_start, batch_end) in enumerate(batches, 1):
            success = await collect_slack_batch(
                mongo_manager,
                batch_start,
                batch_end,
                i,
                total_batches
            )
            
            if success:
                success_count += 1
            else:
                fail_count += 1
            
            # Wait before next batch (except for the last one)
            if i < total_batches:
                wait_seconds = args.interval_hours * 3600
                logger.info(f"\n⏳ Waiting {args.interval_hours} hour(s) before next batch...")
                logger.info(f"   Next batch will start at: {(datetime.now(UTC) + timedelta(seconds=wait_seconds)).strftime('%Y-%m-%d %H:%M:%S UTC')}")
                await asyncio.sleep(wait_seconds)
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("📊 Collection Summary")
        logger.info("=" * 80)
        logger.info(f"   ✅ Successful batches: {success_count}/{total_batches}")
        logger.info(f"   ❌ Failed batches: {fail_count}/{total_batches}")
        logger.info(f"   📅 Date range: {start_date.date()} ~ {end_date.date()}")
        logger.info("=" * 80)
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Collection interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Collection failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        mongo_manager.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code if exit_code else 0)

