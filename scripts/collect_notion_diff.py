#!/usr/bin/env python3
"""
Notion Diff Collector Script

Collects granular content changes from Notion pages and stores in MongoDB.
Designed to run frequently (every 1-5 minutes) for real-time tracking.

Usage:
    # Single run (collect last hour)
    python scripts/collect_notion_diff.py
    
    # Single run with custom time range
    python scripts/collect_notion_diff.py --hours 24
    
    # Run as scheduler (every N minutes)
    python scripts/collect_notion_diff.py --schedule 1
    
    # Show statistics
    python scripts/collect_notion_diff.py --stats
    
    # Show recent diffs
    python scripts/collect_notion_diff.py --recent 20

Environment:
    NOTION_TOKEN: Notion integration token
    MONGODB_URI: MongoDB connection URI
    MONGODB_DATABASE: Database name
"""

import sys
import os
import time
import signal
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.core.mongo_manager import MongoDBManager
from src.plugins.notion_diff_plugin import NotionDiffPlugin
from src.utils.logger import get_logger

logger = get_logger(__name__)


def create_plugin() -> Optional[NotionDiffPlugin]:
    """Initialize MongoDB and Notion Diff Plugin"""
    
    # MongoDB config
    mongo_config = {
        'uri': os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
        'database': os.getenv('MONGODB_DATABASE', 'ati'),
        'max_pool_size': 50,
        'min_pool_size': 5
    }
    
    print(f"📦 Connecting to MongoDB: {mongo_config['database']}", flush=True)
    
    try:
        mongo_manager = MongoDBManager(mongo_config)
        mongo_manager.connect_sync()  # Use sync connection for script
        print("✅ MongoDB connected", flush=True)
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}", flush=True)
        return None
    
    # Notion config
    notion_config = {
        'token': os.getenv('NOTION_TOKEN'),
        'days_to_collect': 1,
        'rate_limit': 3  # requests per second
    }
    
    if not notion_config['token']:
        print("❌ NOTION_TOKEN not set", flush=True)
        return None
    
    print("🔐 Authenticating with Notion...", flush=True)
    plugin = NotionDiffPlugin(notion_config, mongo_manager)
    
    if not plugin.authenticate():
        print("❌ Notion authentication failed", flush=True)
        return None
    
    return plugin


def run_collection(plugin: NotionDiffPlugin, hours: float = 1.0):
    """Run a single collection cycle"""
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(hours=hours)
    
    print(f"\n{'=' * 70}", flush=True)
    print(f"🔄 Collection at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"   Looking back {hours} hours", flush=True)
    print(f"{'=' * 70}", flush=True)
    
    diffs = plugin.collect_data(start_date=start_date, end_date=end_date)
    
    # Summary
    block_diffs = [d for d in diffs if d.get('diff_type') == 'block']
    comment_diffs = [d for d in diffs if d.get('diff_type') == 'comment']
    
    print(f"\n📊 Collection Summary:", flush=True)
    print(f"   Total diffs: {len(diffs)}", flush=True)
    print(f"   Block changes: {len(block_diffs)}", flush=True)
    print(f"   Comment changes: {len(comment_diffs)}", flush=True)
    
    # Show details
    if diffs:
        print(f"\n📝 Changes detected:", flush=True)
        for diff in diffs[:10]:  # Show first 10
            title = diff.get('document_title', 'Untitled')[:30]
            diff_type = diff.get('diff_type', 'unknown')
            changes = diff.get('changes', {})
            added = len(changes.get('added', []))
            deleted = len(changes.get('deleted', []))
            modified = len(changes.get('modified', []))
            
            print(f"   - [{diff_type}] {title}... (+{added} -{deleted} ~{modified})", flush=True)
    
    return diffs


def run_scheduler(plugin: NotionDiffPlugin, interval_minutes: int):
    """Run the collector on a schedule"""
    
    print(f"\n⏰ Starting scheduler - every {interval_minutes} minute(s)", flush=True)
    print("   Press Ctrl+C to stop", flush=True)
    
    running = True
    
    def signal_handler(sig, frame):
        nonlocal running
        print("\n\n🛑 Stopping scheduler...", flush=True)
        running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    
    run_count = 0
    
    while running:
        run_count += 1
        
        # Look back 2x the interval to catch any missed changes
        hours = max(1, (interval_minutes * 2) / 60)
        
        try:
            run_collection(plugin, hours=hours)
        except Exception as e:
            print(f"❌ Collection error: {e}", flush=True)
        
        if running:
            print(f"\n💤 Next run in {interval_minutes} minute(s)...", flush=True)
            
            # Sleep in small increments to allow interrupt
            for _ in range(interval_minutes * 60):
                if not running:
                    break
                time.sleep(1)
    
    print("\n✅ Scheduler stopped", flush=True)


def show_stats(plugin: NotionDiffPlugin):
    """Show collection statistics"""
    
    stats = plugin.get_stats()
    
    print("\n" + "=" * 70)
    print("📊 Notion Diff Collection Statistics")
    print("=" * 70)
    print(f"\n📄 Tracked Pages: {stats['tracked_pages']}")
    print(f"🧱 Current Blocks: {stats['current_blocks']}")
    print(f"📦 Total Block Snapshots: {stats['total_block_snapshots']}")
    print(f"💬 Total Comment Snapshots: {stats['total_comment_snapshots']}")
    print(f"\n📜 Total Diffs: {stats['total_diffs']}")
    print(f"   Block Diffs: {stats['block_diffs']}")
    print(f"   Comment Diffs: {stats['comment_diffs']}")


def show_recent(plugin: NotionDiffPlugin, limit: int = 20):
    """Show recent diffs"""
    
    diffs = plugin.get_recent_diffs(limit=limit)
    
    print("\n" + "=" * 70)
    print(f"📜 Recent {len(diffs)} Diffs")
    print("=" * 70)
    
    for diff in diffs:
        timestamp = diff.get('timestamp', '')[:19]
        title = diff.get('document_title', 'Untitled')[:35]
        diff_type = diff.get('diff_type', 'unknown')
        editor = diff.get('editor_name', 'Unknown')[:15]
        changes = diff.get('changes', {})
        
        added = len(changes.get('added', []))
        deleted = len(changes.get('deleted', []))
        modified = len(changes.get('modified', []))
        
        print(f"\n[{timestamp}] {title}...")
        print(f"   Type: {diff_type} | Editor: {editor}")
        print(f"   Changes: +{added} -{deleted} ~{modified}")
        
        # Show sample content
        if changes.get('added'):
            sample = changes['added'][0]
            if isinstance(sample, dict):
                content = sample.get('content', '')[:60]
            else:
                content = str(sample)[:60]
            print(f"   Added: \"{content}...\"")


def main():
    parser = argparse.ArgumentParser(
        description='Notion Diff Collector',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--hours', type=float, default=1.0,
                       help='Hours to look back (default: 1)')
    parser.add_argument('--schedule', type=int, metavar='MINUTES',
                       help='Run on schedule every N minutes')
    parser.add_argument('--stats', action='store_true',
                       help='Show statistics')
    parser.add_argument('--recent', type=int, metavar='N',
                       help='Show N recent diffs')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("📸 Notion Diff Collector (MongoDB)")
    print("=" * 70)
    
    # Initialize plugin
    plugin = create_plugin()
    if not plugin:
        sys.exit(1)
    
    # Execute command
    if args.stats:
        show_stats(plugin)
    elif args.recent:
        show_recent(plugin, args.recent)
    elif args.schedule:
        run_scheduler(plugin, args.schedule)
    else:
        run_collection(plugin, hours=args.hours)
        show_stats(plugin)
    
    print("\n✨ Done!")


if __name__ == '__main__':
    main()
