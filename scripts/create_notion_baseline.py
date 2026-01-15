#!/usr/bin/env python3
"""
Create baseline snapshots for all accessible Notion documents.

This script should be run ONCE before starting diff collection.
It creates initial snapshots without generating diff records,
so future collections will only show actual changes.

Usage:
    python scripts/create_notion_baseline.py
    python scripts/create_notion_baseline.py --dry-run  # Preview only
"""

import os
import sys
import time
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, '.env'))

from notion_client import Client
from notion_client.errors import APIResponseError
from src.core.mongo_manager import MongoDBManager


class NotionBaselineCreator:
    """Create baseline snapshots for all Notion documents"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.rate_limit_delay = 0.35  # ~3 requests/second
        
        # Initialize Notion client
        notion_token = os.getenv("NOTION_API_KEY") or os.getenv("NOTION_TOKEN")
        if not notion_token:
            raise ValueError("NOTION_API_KEY or NOTION_TOKEN environment variable required")
        
        self.client = Client(auth=notion_token)
        
        # Initialize MongoDB
        if not dry_run:
            mongo_config = {
                'uri': os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
                'database': os.getenv('MONGODB_DATABASE', 'ati'),
                'max_pool_size': 50,
                'min_pool_size': 5
            }
            
            print(f"📦 Connecting to MongoDB: {mongo_config['database']}")
            self.mongo = MongoDBManager(mongo_config)
            self.mongo.connect_sync()
            self.db = self.mongo.db
            
            self.collections = {
                "block_snapshots": self.db["notion_block_snapshots"],
                "comment_snapshots": self.db["notion_comment_snapshots"],
                "tracked_pages": self.db["notion_tracked_pages"]
            }
            print("✅ MongoDB connected")
        
        # User cache
        self.user_cache: Dict[str, str] = {}
    
    def run(self):
        """Create baseline snapshots for all accessible pages"""
        print("=" * 70)
        print("📸 Notion Baseline Snapshot Creator")
        print("=" * 70)
        
        if self.dry_run:
            print("🔍 DRY RUN MODE - No data will be saved")
        
        print("\n🔍 Searching for all accessible pages...")
        pages = self._get_all_pages()
        
        print(f"\n📄 Found {len(pages)} accessible pages")
        
        if self.dry_run:
            print("\n📋 Pages to snapshot:")
            for i, page in enumerate(pages[:20], 1):
                print(f"   {i}. {page['title'][:50]}...")
            if len(pages) > 20:
                print(f"   ... and {len(pages) - 20} more")
            return
        
        # Check existing snapshots
        existing_pages = set()
        for doc in self.collections["block_snapshots"].distinct("page_id"):
            existing_pages.add(doc)
        
        new_pages = [p for p in pages if p['id'] not in existing_pages]
        
        print(f"\n📊 Status:")
        print(f"   - Already have snapshots: {len(existing_pages)} pages")
        print(f"   - Need baseline: {len(new_pages)} pages")
        
        if not new_pages:
            print("\n✅ All pages already have baseline snapshots!")
            return
        
        print(f"\n🚀 Creating baseline snapshots for {len(new_pages)} pages...")
        print("   (This may take a while due to API rate limits)")
        
        success_count = 0
        error_count = 0
        
        for i, page in enumerate(new_pages, 1):
            page_id = page['id']
            title = page['title'][:40]
            
            print(f"\n[{i}/{len(new_pages)}] 📄 {title}...")
            
            try:
                # Fetch all blocks
                blocks = self._fetch_all_blocks(page_id)
                print(f"   📦 Found {len(blocks)} blocks")
                
                # Save snapshot
                self._save_baseline_snapshot(page_id, blocks)
                
                # Track the page
                self._mark_page_tracked(page)
                
                success_count += 1
                print(f"   ✅ Baseline created")
                
            except Exception as e:
                error_count += 1
                print(f"   ❌ Error: {e}")
            
            # Rate limiting
            time.sleep(self.rate_limit_delay)
        
        print("\n" + "=" * 70)
        print("📊 Summary")
        print("=" * 70)
        print(f"   ✅ Successful: {success_count}")
        print(f"   ❌ Errors: {error_count}")
        print(f"   📄 Total tracked: {len(existing_pages) + success_count}")
        print("\n✨ Baseline creation complete!")
        print("   Future diff collections will only show actual changes.")
    
    def _get_all_pages(self) -> List[Dict]:
        """Get all accessible pages from Notion workspace"""
        pages = []
        
        query = {
            "filter": {"value": "page", "property": "object"},
            "sort": {"direction": "descending", "timestamp": "last_edited_time"}
        }
        
        has_more = True
        next_cursor = None
        
        while has_more:
            try:
                if next_cursor:
                    query['start_cursor'] = next_cursor
                
                response = self.client.search(**query)
                
                for page in response.get('results', []):
                    title = self._extract_title(page.get('properties', {}))
                    editor_id = page.get('last_edited_by', {}).get('id', '')
                    
                    pages.append({
                        'id': page['id'],
                        'title': title,
                        'url': page.get('url', ''),
                        'last_edited_time': page.get('last_edited_time'),
                        'last_edited_by': editor_id,
                        'editor_name': self._get_user_name(editor_id)
                    })
                
                has_more = response.get('has_more', False)
                next_cursor = response.get('next_cursor')
                
                # Progress indicator
                print(f"   Found {len(pages)} pages so far...", end='\r')
                time.sleep(self.rate_limit_delay)
                
            except Exception as e:
                print(f"\n⚠️ Error searching pages: {e}")
                break
        
        print()  # New line after progress
        return pages
    
    def _fetch_all_blocks(self, page_id: str) -> List[Dict]:
        """Recursively fetch all blocks from a page"""
        blocks = []
        
        def fetch_children(block_id: str, parent_id: Optional[str] = None):
            has_more = True
            next_cursor = None
            
            while has_more:
                try:
                    params = {'block_id': block_id, 'page_size': 100}
                    if next_cursor:
                        params['start_cursor'] = next_cursor
                    
                    response = self.client.blocks.children.list(**params)
                    
                    for block in response.get('results', []):
                        block_type = block.get('type', '')
                        plain_text = self._extract_block_text(block)
                        
                        blocks.append({
                            'block_id': block['id'],
                            'block_type': block_type,
                            'plain_text': plain_text,
                            'last_edited_time': block.get('last_edited_time', ''),
                            'parent_id': parent_id
                        })
                        
                        # Recurse into children, but SKIP child_page blocks
                        # Child pages are tracked separately as their own pages
                        if block.get('has_children', False) and block_type != 'child_page':
                            time.sleep(self.rate_limit_delay)
                            fetch_children(block['id'], block['id'])
                    
                    has_more = response.get('has_more', False)
                    next_cursor = response.get('next_cursor')
                    
                except APIResponseError as e:
                    print(f"   ⚠️ Error fetching blocks: {e}")
                    break
        
        fetch_children(page_id)
        return blocks
    
    def _extract_block_text(self, block: Dict) -> str:
        """Extract plain text from a block"""
        block_type = block.get('type', '')
        
        if block_type not in block:
            return ''
        
        content = block[block_type]
        
        # Handle rich_text fields
        if 'rich_text' in content:
            return ''.join(
                t.get('plain_text', '') 
                for t in content['rich_text']
            )
        
        # Handle text fields (for code blocks, etc.)
        if 'text' in content:
            if isinstance(content['text'], list):
                return ''.join(
                    t.get('plain_text', '') 
                    for t in content['text']
                )
            return content['text']
        
        # Handle caption
        if 'caption' in content:
            return ''.join(
                t.get('plain_text', '') 
                for t in content['caption']
            )
        
        return ''
    
    def _extract_title(self, properties: Dict) -> str:
        """Extract title from page properties"""
        for prop_name, prop_value in properties.items():
            if prop_value.get('type') == 'title':
                title_array = prop_value.get('title', [])
                return ''.join(t.get('plain_text', '') for t in title_array)
        return 'Untitled'
    
    def _get_user_name(self, user_id: str) -> str:
        """Get user name from Notion API with caching"""
        if not user_id:
            return 'Unknown'
        
        if user_id in self.user_cache:
            return self.user_cache[user_id]
        
        try:
            user = self.client.users.retrieve(user_id)
            name = user.get('name', user_id[:8])
            self.user_cache[user_id] = name
            return name
        except:
            return user_id[:8]
    
    def _save_baseline_snapshot(self, page_id: str, blocks: List[Dict]):
        """Save initial baseline snapshot (without creating diff)"""
        snapshot_time = datetime.now(timezone.utc)
        
        if not blocks:
            return
        
        documents = []
        for block in blocks:
            documents.append({
                "page_id": page_id,
                "block_id": block['block_id'],
                "block_type": block['block_type'],
                "plain_text": block['plain_text'],
                "last_edited_time": block['last_edited_time'],
                "parent_id": block.get('parent_id'),
                "snapshot_time": snapshot_time,
                "is_current": True,
                "is_baseline": True  # Mark as baseline (initial snapshot)
            })
        
        try:
            self.collections["block_snapshots"].insert_many(documents, ordered=False)
        except Exception as e:
            print(f"   ⚠️ Insert error: {e}")
    
    def _mark_page_tracked(self, page: Dict):
        """Mark page as tracked with baseline timestamp"""
        self.collections["tracked_pages"].update_one(
            {"page_id": page['id']},
            {
                "$set": {
                    "page_id": page['id'],
                    "title": page['title'],
                    "url": page['url'],
                    "baseline_created_at": datetime.now(timezone.utc),
                    "last_checked_at": datetime.now(timezone.utc)
                },
                "$setOnInsert": {
                    "first_tracked_at": datetime.now(timezone.utc)
                }
            },
            upsert=True
        )


def main():
    parser = argparse.ArgumentParser(
        description="Create baseline snapshots for all Notion documents"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview pages without creating snapshots'
    )
    
    args = parser.parse_args()
    
    try:
        creator = NotionBaselineCreator(dry_run=args.dry_run)
        creator.run()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
