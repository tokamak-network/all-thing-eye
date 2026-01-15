#!/usr/bin/env python3
"""
Google Drive Diff Collection Script

Collects actual content changes from Google Drive documents by comparing
document revisions. Supports both one-time collection and scheduled runs.

Usage:
    # One-time collection (last 24 hours)
    python scripts/collect_drive_diff.py --hours 24

    # Scheduled collection (every N minutes)
    python scripts/collect_drive_diff.py --schedule 10

    # Show statistics
    python scripts/collect_drive_diff.py --stats

    # Show recent diffs
    python scripts/collect_drive_diff.py --recent
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

# Load environment variables
from dotenv import load_dotenv
load_dotenv(project_root / '.env')

from src.core.mongo_manager import MongoDBManager
from src.plugins.drive_diff_plugin import GoogleDriveDiffPlugin
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested
    print("\n⚠️ Shutdown requested. Finishing current operation...", flush=True)
    shutdown_requested = True


def create_plugin() -> Optional[GoogleDriveDiffPlugin]:
    """Initialize MongoDB and Google Drive Diff Plugin"""
    
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
        mongo_manager.connect_sync()
        print("✅ MongoDB connected", flush=True)
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}", flush=True)
        return None
    
    # Google Drive config
    drive_config = {
        'credentials_path': os.getenv('GOOGLE_CREDENTIALS_PATH', 'config/google_drive/credentials.json'),
        'token_path': os.getenv('GOOGLE_TOKEN_PATH', 'config/google_drive/token_diff.pickle'),
        'days_to_collect': 1,
        'rate_limit': 10,  # requests per second
        'mongo_manager': mongo_manager
    }
    
    # Check for folder filter
    folder_ids = os.getenv('GOOGLE_DRIVE_FOLDER_IDS', '')
    if folder_ids:
        drive_config['folder_ids'] = [f.strip() for f in folder_ids.split(',') if f.strip()]
    
    print("🔐 Authenticating with Google Drive...", flush=True)
    
    try:
        plugin = GoogleDriveDiffPlugin(drive_config)
        if not plugin.authenticate():
            print("❌ Google Drive authentication failed", flush=True)
            return None
        return plugin
    except Exception as e:
        print(f"❌ Plugin initialization failed: {e}", flush=True)
        return None


def run_collection(plugin: GoogleDriveDiffPlugin, hours: float):
    """Run a single collection cycle"""
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(hours=hours)
    
    print("=" * 70, flush=True)
    print(f"🔄 Collection at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"   Looking back {hours} hours", flush=True)
    print("=" * 70, flush=True)
    
    diffs = plugin.collect_data(start_date=start_date, end_date=end_date)
    
    print(f"\n📊 Collected {len(diffs)} diff records", flush=True)
    
    return diffs


def run_scheduled(plugin: GoogleDriveDiffPlugin, interval_minutes: int):
    """Run collection on a schedule"""
    print(f"\n⏰ Starting scheduled collection every {interval_minutes} minutes", flush=True)
    print("   Press Ctrl+C to stop\n", flush=True)
    
    while not shutdown_requested:
        try:
            # Collect changes from the last interval + buffer
            hours = (interval_minutes * 2) / 60  # Look back 2x interval
            run_collection(plugin, hours)
            
            if shutdown_requested:
                break
            
            # Wait for next cycle
            print(f"\n💤 Sleeping for {interval_minutes} minutes...", flush=True)
            for _ in range(interval_minutes * 60):
                if shutdown_requested:
                    break
                time.sleep(1)
                
        except Exception as e:
            print(f"❌ Error during collection: {e}", flush=True)
            if not shutdown_requested:
                print("   Retrying in 60 seconds...", flush=True)
                time.sleep(60)
    
    print("\n✨ Scheduler stopped gracefully", flush=True)


def show_stats(mongo_manager: MongoDBManager):
    """Show collection statistics"""
    db = mongo_manager.db
    
    print("\n" + "=" * 70, flush=True)
    print("📊 Google Drive Diff Collection Statistics", flush=True)
    print("=" * 70, flush=True)
    
    # Count documents
    tracked_docs = db["drive_tracked_documents"].count_documents({})
    snapshots = db["drive_revision_snapshots"].count_documents({})
    current_snapshots = db["drive_revision_snapshots"].count_documents({"is_current": True})
    total_diffs = db["drive_content_diffs"].count_documents({})
    
    print(f"\n📄 Tracked Documents: {tracked_docs}", flush=True)
    print(f"📸 Total Snapshots: {snapshots}", flush=True)
    print(f"📸 Current Snapshots: {current_snapshots}", flush=True)
    print(f"📜 Total Diffs: {total_diffs}", flush=True)
    
    # Recent diffs breakdown
    if total_diffs > 0:
        # By editor
        pipeline = [
            {"$group": {"_id": "$editor_name", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        top_editors = list(db["drive_content_diffs"].aggregate(pipeline))
        
        print(f"\n👤 Top Editors:", flush=True)
        for editor in top_editors:
            print(f"   - {editor['_id']}: {editor['count']} changes", flush=True)


def show_recent_diffs(mongo_manager: MongoDBManager, limit: int = 20):
    """Show recent diff records"""
    db = mongo_manager.db
    
    diffs = list(db["drive_content_diffs"].find().sort("timestamp", -1).limit(limit))
    
    print("\n" + "=" * 70, flush=True)
    print(f"📜 Recent {len(diffs)} Diffs", flush=True)
    print("=" * 70, flush=True)
    
    for diff in diffs:
        timestamp = diff.get('timestamp', '')[:19]
        title = diff.get('document_title', 'Untitled')[:30]
        editor = diff.get('editor_name', 'Unknown')
        changes = diff.get('changes', {})
        added = len(changes.get('added', []))
        deleted = len(changes.get('deleted', []))
        
        print(f"\n[{timestamp}] {title}...", flush=True)
        print(f"   Editor: {editor}", flush=True)
        print(f"   Changes: +{added} -{deleted}", flush=True)
        
        # Show preview of changes
        if added > 0:
            preview = changes['added'][0][:50]
            print(f"   Added: \"{preview}...\"", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Google Drive Diff Collection Script"
    )
    parser.add_argument(
        '--hours',
        type=float,
        default=24,
        help='Hours to look back for changes (default: 24)'
    )
    parser.add_argument(
        '--schedule',
        type=int,
        metavar='MINUTES',
        help='Run on schedule every N minutes'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show collection statistics'
    )
    parser.add_argument(
        '--recent',
        action='store_true',
        help='Show recent diffs'
    )
    
    args = parser.parse_args()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 70, flush=True)
    print("📁 Google Drive Diff Collector (MongoDB)", flush=True)
    print("=" * 70, flush=True)
    
    # For stats/recent, just need MongoDB
    if args.stats or args.recent:
        mongo_config = {
            'uri': os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
            'database': os.getenv('MONGODB_DATABASE', 'ati'),
            'max_pool_size': 50,
            'min_pool_size': 5
        }
        
        mongo_manager = MongoDBManager(mongo_config)
        mongo_manager.connect_sync()
        
        if args.stats:
            show_stats(mongo_manager)
        if args.recent:
            show_recent_diffs(mongo_manager)
        
        print("\n✨ Done!", flush=True)
        return
    
    # Create plugin
    plugin = create_plugin()
    if not plugin:
        sys.exit(1)
    
    # Run collection
    if args.schedule:
        run_scheduled(plugin, args.schedule)
    else:
        run_collection(plugin, args.hours)
    
    print("\n✨ Done!", flush=True)


if __name__ == "__main__":
    main()
