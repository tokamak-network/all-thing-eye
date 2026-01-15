"""
Scheduled Notion Snapshot Collector

Collects snapshots from all recently edited Notion pages periodically.
Can be run manually or via cron/scheduler.

Usage:
    # Run once (collect all pages edited in last hour)
    python tests/diff_collection/scheduled_collector.py
    
    # Run with custom time range
    python tests/diff_collection/scheduled_collector.py --hours 24
    
    # Start scheduler (runs every N minutes)
    python tests/diff_collection/scheduled_collector.py --schedule 10
    
    # View database stats
    python tests/diff_collection/scheduled_collector.py --stats

Database:
    Uses local SQLite at tests/diff_collection/test_diff.db
"""

import sys
import os
import time
import signal
import sqlite3
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

# Import from test_diff_collector
from tests.diff_collection.test_diff_collector import (
    DiffTestDatabase,
    DiffResult,
    BlockSnapshot,
    DiffEngine,
    NotionDiffCollector
)


class ScheduledNotionCollector:
    """
    Scheduled collector that fetches all recently edited Notion pages
    and creates snapshots for diff tracking.
    """
    
    def __init__(self, db: DiffTestDatabase):
        self.db = db
        self.client = None
        self.diff_collector = NotionDiffCollector(db)
        self._init_client()
    
    def _init_client(self):
        """Initialize Notion client"""
        try:
            from notion_client import Client
            
            token = os.getenv('NOTION_TOKEN')
            if not token:
                print("⚠️  NOTION_TOKEN not set in environment")
                return
            
            self.client = Client(auth=token)
            
            # Test connection
            user = self.client.users.me()
            print(f"✅ Notion API connected: {user.get('name', 'Unknown')}")
            
        except ImportError:
            print("⚠️  notion-client not installed")
            print("   Run: pip install notion-client")
        except Exception as e:
            print(f"❌ Notion API error: {e}")
    
    def _extract_title(self, properties: Dict) -> str:
        """Extract title from page properties"""
        for prop_name, prop_value in properties.items():
            if prop_value.get('type') == 'title':
                title_items = prop_value.get('title', [])
                if title_items:
                    return title_items[0].get('plain_text', 'Untitled')
        return 'Untitled'
    
    def get_recently_edited_pages(self, hours: int = 1) -> List[Dict]:
        """
        Get all pages edited within the last N hours
        """
        if not self.client:
            return []
        
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        pages = []
        
        print(f"\n🔍 Searching for pages edited since {since.isoformat()}")
        
        try:
            query = {
                "filter": {
                    "value": "page",
                    "property": "object"
                },
                "sort": {
                    "direction": "descending",
                    "timestamp": "last_edited_time"
                }
            }
            
            has_more = True
            next_cursor = None
            
            while has_more:
                if next_cursor:
                    query['start_cursor'] = next_cursor
                
                response = self.client.search(**query)
                
                for page in response.get('results', []):
                    last_edited = datetime.fromisoformat(
                        page['last_edited_time'].replace('Z', '+00:00')
                    )
                    
                    # Stop if page is older than our time range
                    if last_edited < since:
                        has_more = False
                        break
                    
                    title = self._extract_title(page.get('properties', {}))
                    
                    pages.append({
                        'id': page['id'],
                        'title': title,
                        'last_edited_time': page.get('last_edited_time'),
                        'last_edited_by': page.get('last_edited_by', {}).get('id', 'Unknown'),
                        'url': page.get('url', '')
                    })
                
                has_more = response.get('has_more', False) and has_more
                next_cursor = response.get('next_cursor')
            
            print(f"   Found {len(pages)} recently edited pages")
            return pages
            
        except Exception as e:
            print(f"❌ Error searching pages: {e}")
            return []
    
    def collect_all_snapshots(self, hours: int = 1) -> Dict[str, Any]:
        """
        Collect snapshots from all recently edited pages
        """
        if not self.client:
            return {'pages_processed': 0, 'diffs': []}
        
        pages = self.get_recently_edited_pages(hours)
        
        if not pages:
            print("📭 No recently edited pages found")
            return {'pages_processed': 0, 'diffs': []}
        
        diffs = []
        errors = []
        
        print(f"\n📸 Collecting snapshots from {len(pages)} pages...")
        
        for i, page in enumerate(pages, 1):
            page_id = page['id']
            title = page['title']
            
            print(f"\n  [{i}/{len(pages)}] {title[:40]}...")
            
            try:
                # Use the diff collector to process this page
                result = self.diff_collector.collect_diff(page_id)
                
                if result:
                    # Count changes
                    added = len(result.changes.get('added', []))
                    deleted = len(result.changes.get('deleted', []))
                    
                    if added > 0 or deleted > 0:
                        print(f"      ✅ Changes detected: +{added} / -{deleted}")
                        diffs.append(result)
                    else:
                        print(f"      📋 No changes (or first snapshot)")
                        
            except Exception as e:
                print(f"      ❌ Error: {e}")
                errors.append({'page_id': page_id, 'title': title, 'error': str(e)})
            
            # Rate limiting - Notion allows ~3 requests/second
            time.sleep(0.5)
        
        return {
            'pages_processed': len(pages),
            'diffs': diffs,
            'errors': errors,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def show_database_stats(self):
        """Show statistics about the collected data"""
        print("\n" + "=" * 70)
        print("📊 Database Statistics")
        print("=" * 70)
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Notion tracking stats
            cursor.execute('SELECT COUNT(*) FROM notion_tracking')
            tracked_pages = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM notion_blocks WHERE is_current = 1')
            current_blocks = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM notion_blocks')
            total_blocks = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM diff_history WHERE platform = 'notion'")
            diff_count = cursor.fetchone()[0]
            
            print(f"\n📄 Tracked Pages: {tracked_pages}")
            print(f"🧱 Current Blocks: {current_blocks}")
            print(f"📦 Total Block Snapshots: {total_blocks}")
            print(f"📜 Diff Records: {diff_count}")
            
            # Recent pages
            print(f"\n📋 Recently Tracked Pages:")
            cursor.execute('''
                SELECT page_id, page_title, last_snapshot_time, last_edited_time 
                FROM notion_tracking 
                ORDER BY last_snapshot_time DESC 
                LIMIT 10
            ''')
            
            for row in cursor.fetchall():
                print(f"   - {row[1][:40]}")
                print(f"     ID: {row[0][:20]}...")
                print(f"     Last snapshot: {row[2]}")
            
            # Recent diffs with changes
            print(f"\n🔄 Recent Diffs with Changes:")
            cursor.execute('''
                SELECT document_id, editor, timestamp, diff_json 
                FROM diff_history 
                WHERE platform = 'notion'
                ORDER BY created_at DESC 
                LIMIT 5
            ''')
            
            for row in cursor.fetchall():
                diff_data = json.loads(row[3])
                changes = diff_data.get('changes', {})
                added = len(changes.get('added', []))
                deleted = len(changes.get('deleted', []))
                
                if added > 0 or deleted > 0:
                    print(f"   - {row[0][:20]}... at {row[2]}")
                    print(f"     Changes: +{added} / -{deleted}")
                    
                    # Show sample changes
                    if changes.get('added'):
                        sample = changes['added'][0][:50]
                        print(f"     Added: \"{sample}...\"")
    
    def show_sample_data(self):
        """Show sample data from the database for inspection"""
        print("\n" + "=" * 70)
        print("🔬 Sample Data Inspection")
        print("=" * 70)
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Sample blocks
            print(f"\n🧱 Sample Blocks (latest 5):")
            cursor.execute('''
                SELECT page_id, block_id, block_type, plain_text, last_edited_time, is_current
                FROM notion_blocks
                ORDER BY snapshot_time DESC
                LIMIT 5
            ''')
            
            for row in cursor.fetchall():
                print(f"\n   Block: {row[1][:30]}...")
                print(f"   Type: {row[2]}")
                print(f"   Current: {'Yes' if row[5] else 'No (historical)'}")
                text = row[3][:100] if row[3] else "(empty)"
                print(f"   Text: {text}")
            
            # Full diff JSON example
            print(f"\n📜 Sample Diff JSON:")
            cursor.execute('''
                SELECT diff_json FROM diff_history 
                WHERE platform = 'notion'
                ORDER BY created_at DESC 
                LIMIT 1
            ''')
            row = cursor.fetchone()
            if row:
                diff_data = json.loads(row[0])
                print(json.dumps(diff_data, indent=2, ensure_ascii=False)[:500])
            else:
                print("   (no diffs recorded yet)")


def run_scheduler(collector: ScheduledNotionCollector, interval_minutes: int):
    """
    Run the collector on a schedule
    """
    print(f"\n⏰ Starting scheduler - running every {interval_minutes} minutes")
    print("   Press Ctrl+C to stop")
    
    running = True
    
    def signal_handler(sig, frame):
        nonlocal running
        print("\n\n🛑 Stopping scheduler...")
        running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    
    run_count = 0
    
    while running:
        run_count += 1
        print(f"\n{'=' * 70}")
        print(f"🔄 Run #{run_count} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        # Collect snapshots (look back 2x the interval to catch any missed)
        hours = max(1, (interval_minutes * 2) / 60)
        result = collector.collect_all_snapshots(hours=hours)
        
        print(f"\n📊 Summary:")
        print(f"   Pages processed: {result['pages_processed']}")
        print(f"   Diffs detected: {len(result['diffs'])}")
        if result.get('errors'):
            print(f"   Errors: {len(result['errors'])}")
        
        if running:
            print(f"\n💤 Sleeping for {interval_minutes} minutes...")
            
            # Sleep in small increments to allow interrupt
            for _ in range(interval_minutes * 60):
                if not running:
                    break
                time.sleep(1)
    
    print("\n✅ Scheduler stopped")


def main():
    parser = argparse.ArgumentParser(
        description='Scheduled Notion Snapshot Collector',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--hours', type=float, default=1,
                       help='Hours to look back for edited pages (default: 1)')
    parser.add_argument('--schedule', type=int, metavar='MINUTES',
                       help='Run on schedule every N minutes')
    parser.add_argument('--stats', action='store_true',
                       help='Show database statistics')
    parser.add_argument('--sample', action='store_true',
                       help='Show sample data from database')
    parser.add_argument('--db-path', help='Custom database path')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("📸 Scheduled Notion Snapshot Collector")
    print("=" * 70)
    
    # Initialize database
    db = DiffTestDatabase(args.db_path)
    collector = ScheduledNotionCollector(db)
    
    if args.stats:
        collector.show_database_stats()
        return
    
    if args.sample:
        collector.show_sample_data()
        return
    
    if args.schedule:
        run_scheduler(collector, args.schedule)
    else:
        # Single run
        print(f"\n📋 Single collection run (looking back {args.hours} hours)")
        result = collector.collect_all_snapshots(hours=args.hours)
        
        print("\n" + "=" * 70)
        print("📊 Collection Summary")
        print("=" * 70)
        print(f"   Pages processed: {result['pages_processed']}")
        print(f"   Diffs with changes: {len(result['diffs'])}")
        
        if result['diffs']:
            print(f"\n📜 Changed Pages:")
            for diff in result['diffs']:
                added = len(diff.changes.get('added', []))
                deleted = len(diff.changes.get('deleted', []))
                print(f"   - {diff.document_id[:30]}... (+{added}/-{deleted})")
        
        # Show stats after collection
        collector.show_database_stats()
    
    print(f"\n💾 Database: {db.db_path}")
    print("✨ Done!")


if __name__ == '__main__':
    main()
