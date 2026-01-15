"""
Granular Data Collection Test: Snapshot-based Diff Tracking

This module implements the specification from docs/data-collection/upgrade-api.md
- Google Drive: Revision-based text comparison
- Notion: Block-level snapshot comparison

Usage:
    # Test Notion diff collection
    python tests/diff_collection/test_diff_collector.py --source notion --page-id <PAGE_ID>
    
    # Test Google Drive diff collection  
    python tests/diff_collection/test_diff_collector.py --source drive --doc-id <DOC_ID>
    
    # List tracked documents
    python tests/diff_collection/test_diff_collector.py --list-tracked

Database:
    Uses local SQLite at tests/diff_collection/test_diff.db
    Does NOT touch existing production databases.
"""

import sys
import os
import sqlite3
import json
import difflib
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class DiffResult:
    """Structured diff output as per spec"""
    platform: str  # "google_drive" | "notion"
    document_id: str
    editor: str
    timestamp: str  # ISO8601
    changes: Dict[str, List[str]]  # {"added": [...], "deleted": [...]}
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)


@dataclass  
class BlockSnapshot:
    """Notion block snapshot data"""
    block_id: str
    block_type: str
    plain_text: str
    last_edited_time: str
    parent_block_id: Optional[str] = None


# ============================================================================
# Database Manager (Local Test DB)
# ============================================================================

class DiffTestDatabase:
    """
    Local SQLite database for diff tracking tests.
    Stored at tests/diff_collection/test_diff.db
    """
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            self.db_path = Path(__file__).parent / "test_diff.db"
        else:
            self.db_path = Path(db_path)
        
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
    
    def _init_schema(self):
        """Create tables for snapshot storage"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Google Drive revision tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS drive_revisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL,
                    revision_id TEXT NOT NULL,
                    plain_text TEXT,
                    editor_email TEXT,
                    modified_time TEXT,
                    snapshot_time TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(document_id, revision_id)
                )
            ''')
            
            # Google Drive last processed revision
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS drive_tracking (
                    document_id TEXT PRIMARY KEY,
                    document_title TEXT,
                    last_processed_revision_id TEXT,
                    last_check_time TEXT
                )
            ''')
            
            # Notion block snapshots
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notion_blocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_id TEXT NOT NULL,
                    block_id TEXT NOT NULL,
                    block_type TEXT,
                    plain_text TEXT,
                    last_edited_time TEXT,
                    parent_block_id TEXT,
                    snapshot_time TEXT DEFAULT CURRENT_TIMESTAMP,
                    is_current INTEGER DEFAULT 1,
                    UNIQUE(page_id, block_id, snapshot_time)
                )
            ''')
            
            # Notion page tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notion_tracking (
                    page_id TEXT PRIMARY KEY,
                    page_title TEXT,
                    last_snapshot_time TEXT,
                    last_edited_time TEXT
                )
            ''')
            
            # Diff history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS diff_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    editor TEXT,
                    timestamp TEXT,
                    diff_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            print(f"✅ Database initialized: {self.db_path}")
    
    def get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)
    
    # Drive methods
    def save_drive_revision(self, doc_id: str, revision_id: str, 
                           plain_text: str, editor: str, modified_time: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO drive_revisions 
                (document_id, revision_id, plain_text, editor_email, modified_time)
                VALUES (?, ?, ?, ?, ?)
            ''', (doc_id, revision_id, plain_text, editor, modified_time))
            conn.commit()
    
    def get_last_drive_revision(self, doc_id: str) -> Optional[Tuple[str, str]]:
        """Get (revision_id, plain_text) for last processed revision"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT revision_id, plain_text FROM drive_revisions
                WHERE document_id = ?
                ORDER BY modified_time DESC
                LIMIT 1
            ''', (doc_id,))
            row = cursor.fetchone()
            return row if row else None
    
    def update_drive_tracking(self, doc_id: str, doc_title: str, revision_id: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO drive_tracking 
                (document_id, document_title, last_processed_revision_id, last_check_time)
                VALUES (?, ?, ?, ?)
            ''', (doc_id, doc_title, revision_id, datetime.now(timezone.utc).isoformat()))
            conn.commit()
    
    # Notion methods
    def save_notion_snapshot(self, page_id: str, blocks: List[BlockSnapshot]):
        """Save current block state, marking previous as not current"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            snapshot_time = datetime.now(timezone.utc).isoformat()
            
            # Mark all previous blocks for this page as not current
            cursor.execute('''
                UPDATE notion_blocks SET is_current = 0 
                WHERE page_id = ? AND is_current = 1
            ''', (page_id,))
            
            # Insert new blocks
            for block in blocks:
                cursor.execute('''
                    INSERT INTO notion_blocks 
                    (page_id, block_id, block_type, plain_text, last_edited_time, 
                     parent_block_id, snapshot_time, is_current)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                ''', (page_id, block.block_id, block.block_type, block.plain_text,
                      block.last_edited_time, block.parent_block_id, snapshot_time))
            
            conn.commit()
    
    def get_previous_notion_snapshot(self, page_id: str) -> List[BlockSnapshot]:
        """Get the previous (non-current) snapshot"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT block_id, block_type, plain_text, last_edited_time, parent_block_id
                FROM notion_blocks
                WHERE page_id = ? AND is_current = 0
                ORDER BY snapshot_time DESC
            ''', (page_id,))
            
            # Get only the most recent non-current snapshot
            rows = cursor.fetchall()
            if not rows:
                return []
            
            return [
                BlockSnapshot(
                    block_id=row[0],
                    block_type=row[1],
                    plain_text=row[2],
                    last_edited_time=row[3],
                    parent_block_id=row[4]
                ) for row in rows
            ]
    
    def update_notion_tracking(self, page_id: str, page_title: str, last_edited: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO notion_tracking 
                (page_id, page_title, last_snapshot_time, last_edited_time)
                VALUES (?, ?, ?, ?)
            ''', (page_id, page_title, datetime.now(timezone.utc).isoformat(), last_edited))
            conn.commit()
    
    def save_diff(self, diff_result: DiffResult):
        """Save diff to history"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO diff_history 
                (platform, document_id, editor, timestamp, diff_json)
                VALUES (?, ?, ?, ?, ?)
            ''', (diff_result.platform, diff_result.document_id, 
                  diff_result.editor, diff_result.timestamp, diff_result.to_json()))
            conn.commit()
    
    def list_tracked_documents(self) -> Dict[str, List[Dict]]:
        """List all tracked documents"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            result = {"google_drive": [], "notion": []}
            
            cursor.execute('SELECT * FROM drive_tracking')
            for row in cursor.fetchall():
                result["google_drive"].append({
                    "document_id": row[0],
                    "title": row[1],
                    "last_revision": row[2],
                    "last_check": row[3]
                })
            
            cursor.execute('SELECT * FROM notion_tracking')
            for row in cursor.fetchall():
                result["notion"].append({
                    "page_id": row[0],
                    "title": row[1],
                    "last_snapshot": row[2],
                    "last_edited": row[3]
                })
            
            return result


# ============================================================================
# Diff Engine
# ============================================================================

class DiffEngine:
    """
    Text comparison engine using Python's difflib
    """
    
    @staticmethod
    def compute_diff(old_text: str, new_text: str) -> Dict[str, List[str]]:
        """
        Compute added and deleted lines between two versions
        
        Args:
            old_text: Previous version text
            new_text: Current version text
            
        Returns:
            {"added": [...], "deleted": [...]}
        """
        if old_text is None:
            old_text = ""
        if new_text is None:
            new_text = ""
            
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        
        differ = difflib.Differ()
        diff = list(differ.compare(old_lines, new_lines))
        
        added = []
        deleted = []
        
        for line in diff:
            if line.startswith('+ '):
                text = line[2:].strip()
                if text:  # Skip empty lines
                    added.append(text)
            elif line.startswith('- '):
                text = line[2:].strip()
                if text:
                    deleted.append(text)
        
        return {"added": added, "deleted": deleted}
    
    @staticmethod
    def compute_block_diff(old_blocks: List[BlockSnapshot], 
                          new_blocks: List[BlockSnapshot]) -> Dict[str, List[str]]:
        """
        Compare Notion blocks using the specification:
        - Added: New block_id
        - Deleted: Missing block_id
        - Updated: Same block_id with different last_edited_time
        """
        old_map = {b.block_id: b for b in old_blocks}
        new_map = {b.block_id: b for b in new_blocks}
        
        added = []
        deleted = []
        
        # Find added blocks (in new but not in old)
        for block_id, block in new_map.items():
            if block_id not in old_map:
                if block.plain_text:
                    added.append(block.plain_text)
        
        # Find deleted blocks (in old but not in new)
        for block_id, block in old_map.items():
            if block_id not in new_map:
                if block.plain_text:
                    deleted.append(block.plain_text)
        
        # Find updated blocks (same id, different edit time)
        for block_id, new_block in new_map.items():
            if block_id in old_map:
                old_block = old_map[block_id]
                if old_block.last_edited_time != new_block.last_edited_time:
                    # Content changed - compute text diff
                    text_diff = DiffEngine.compute_diff(
                        old_block.plain_text or "", 
                        new_block.plain_text or ""
                    )
                    added.extend(text_diff["added"])
                    deleted.extend(text_diff["deleted"])
        
        return {"added": added, "deleted": deleted}


# ============================================================================
# Google Drive Collector
# ============================================================================

class GoogleDriveDiffCollector:
    """
    Google Drive revision-based diff collector
    
    Mechanism (from spec 2.1):
    1. Get revision list via drive.revisions.list
    2. Export as text/plain to remove formatting noise
    3. Compare with previous snapshot using difflib
    """
    
    def __init__(self, db: DiffTestDatabase):
        self.db = db
        self.service = None
        self._init_service()
    
    def _init_service(self):
        """Initialize Google Drive API service"""
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            import pickle
            
            SCOPES = [
                'https://www.googleapis.com/auth/drive.readonly',
                'https://www.googleapis.com/auth/documents.readonly'
            ]
            
            creds = None
            token_path = project_root / "config" / "google_drive" / "token_diff_test.pickle"
            credentials_path = project_root / "config" / "google_drive" / "credentials.json"
            
            if token_path.exists():
                with open(token_path, 'rb') as token:
                    creds = pickle.load(token)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not credentials_path.exists():
                        print(f"⚠️  credentials.json not found at {credentials_path}")
                        print("   Please place your Google OAuth credentials file there.")
                        return
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(credentials_path), SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                
                with open(token_path, 'wb') as token:
                    pickle.dump(creds, token)
            
            self.service = build('drive', 'v3', credentials=creds)
            print("✅ Google Drive API connected")
            
        except ImportError:
            print("⚠️  Google API libraries not installed")
            print("   Run: pip install google-api-python-client google-auth-oauthlib")
        except Exception as e:
            print(f"❌ Google Drive API error: {e}")
    
    def get_document_revisions(self, doc_id: str) -> List[Dict]:
        """Get all revisions for a document"""
        if not self.service:
            return []
        
        try:
            # Get file metadata
            file = self.service.files().get(
                fileId=doc_id, 
                fields='name,mimeType'
            ).execute()
            
            print(f"📄 Document: {file['name']}")
            print(f"   Type: {file['mimeType']}")
            
            # List revisions
            revisions = self.service.revisions().list(
                fileId=doc_id,
                fields='revisions(id,modifiedTime,lastModifyingUser)'
            ).execute()
            
            return revisions.get('revisions', [])
            
        except Exception as e:
            print(f"❌ Error getting revisions: {e}")
            return []
    
    def get_revision_text(self, doc_id: str, revision_id: str) -> str:
        """
        Get plain text content of a specific revision.
        Uses export to text/plain as per spec 2.1.
        """
        if not self.service:
            return ""
        
        try:
            # Export as plain text
            response = self.service.revisions().get(
                fileId=doc_id,
                revisionId=revision_id,
                fields='exportLinks'
            ).execute()
            
            export_links = response.get('exportLinks', {})
            
            # Prefer text/plain, fallback to other formats
            text_url = export_links.get('text/plain')
            if text_url:
                import requests
                # Need to use authorized session
                from google.auth.transport.requests import AuthorizedSession
                from google.oauth2.credentials import Credentials
                import pickle
                
                token_path = project_root / "config" / "google_drive" / "token_diff_test.pickle"
                with open(token_path, 'rb') as f:
                    creds = pickle.load(f)
                
                session = AuthorizedSession(creds)
                resp = session.get(text_url)
                return resp.text
            
            # Fallback: Get content directly for Google Docs
            content = self.service.files().export(
                fileId=doc_id,
                mimeType='text/plain'
            ).execute()
            
            return content.decode('utf-8') if isinstance(content, bytes) else content
            
        except Exception as e:
            print(f"⚠️  Could not get revision text: {e}")
            return ""
    
    def collect_diff(self, doc_id: str) -> Optional[DiffResult]:
        """
        Collect diff for a Google Drive document
        
        1. Get latest revision
        2. Compare with stored previous version
        3. Store new version and return diff
        """
        if not self.service:
            print("❌ Google Drive service not initialized")
            return None
        
        print(f"\n🔍 Collecting diff for Drive document: {doc_id}")
        
        # Get revisions
        revisions = self.get_document_revisions(doc_id)
        if not revisions:
            print("   No revisions found")
            return None
        
        # Get latest revision
        latest = revisions[-1]
        latest_id = latest['id']
        editor = latest.get('lastModifyingUser', {}).get('emailAddress', 'Unknown')
        modified_time = latest.get('modifiedTime', datetime.now(timezone.utc).isoformat())
        
        print(f"   Latest revision: {latest_id}")
        print(f"   Modified by: {editor}")
        print(f"   Time: {modified_time}")
        
        # Get current text
        new_text = self.get_revision_text(doc_id, latest_id)
        print(f"   Content length: {len(new_text)} chars")
        
        # Get previous version from DB
        previous = self.db.get_last_drive_revision(doc_id)
        old_text = previous[1] if previous else ""
        
        if previous:
            print(f"   Previous revision in DB: {previous[0]}")
        else:
            print("   📝 First snapshot - no previous version")
        
        # Compute diff
        changes = DiffEngine.compute_diff(old_text, new_text)
        
        # Save new version
        self.db.save_drive_revision(doc_id, latest_id, new_text, editor, modified_time)
        
        # Get doc title for tracking
        try:
            file = self.service.files().get(fileId=doc_id, fields='name').execute()
            doc_title = file['name']
        except:
            doc_title = doc_id
        
        self.db.update_drive_tracking(doc_id, doc_title, latest_id)
        
        # Create result
        result = DiffResult(
            platform="google_drive",
            document_id=doc_id,
            editor=editor,
            timestamp=modified_time,
            changes=changes
        )
        
        # Save diff to history
        self.db.save_diff(result)
        
        return result


# ============================================================================
# Notion Collector
# ============================================================================

class NotionDiffCollector:
    """
    Notion block-based diff collector
    
    Mechanism (from spec 3.1):
    1. Fetch all blocks recursively via blocks.children.list
    2. Store block_id, last_edited_time, plain_text
    3. Compare with previous snapshot:
       - Added: new block_id
       - Deleted: missing block_id
       - Updated: same block_id with changed last_edited_time
    """
    
    def __init__(self, db: DiffTestDatabase):
        self.db = db
        self.client = None
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
    
    def _extract_plain_text(self, rich_text: List[Dict]) -> str:
        """Extract plain text from rich_text array (ignoring annotations per spec 3.2)"""
        return ''.join(
            item.get('plain_text', '') 
            for item in rich_text
        )
    
    def _fetch_blocks_recursive(self, block_id: str, 
                                parent_id: Optional[str] = None) -> List[BlockSnapshot]:
        """
        Recursively fetch all blocks under a page/block
        """
        if not self.client:
            return []
        
        blocks = []
        has_more = True
        next_cursor = None
        
        while has_more:
            try:
                params = {
                    'block_id': block_id,
                    'page_size': 100
                }
                if next_cursor:
                    params['start_cursor'] = next_cursor
                
                response = self.client.blocks.children.list(**params)
                
                for block in response.get('results', []):
                    block_type = block.get('type', '')
                    
                    # Extract text based on block type
                    plain_text = ""
                    if block_type in block:
                        block_content = block[block_type]
                        if 'rich_text' in block_content:
                            plain_text = self._extract_plain_text(block_content['rich_text'])
                        elif 'text' in block_content:
                            plain_text = self._extract_plain_text(block_content['text'])
                    
                    snapshot = BlockSnapshot(
                        block_id=block['id'],
                        block_type=block_type,
                        plain_text=plain_text,
                        last_edited_time=block.get('last_edited_time', ''),
                        parent_block_id=parent_id
                    )
                    blocks.append(snapshot)
                    
                    # Recurse into children if has_children
                    if block.get('has_children', False):
                        child_blocks = self._fetch_blocks_recursive(
                            block['id'], 
                            parent_id=block['id']
                        )
                        blocks.extend(child_blocks)
                
                has_more = response.get('has_more', False)
                next_cursor = response.get('next_cursor')
                
            except Exception as e:
                print(f"⚠️  Error fetching blocks: {e}")
                break
        
        return blocks
    
    def get_page_info(self, page_id: str) -> Dict:
        """Get page metadata"""
        if not self.client:
            return {}
        
        try:
            page = self.client.pages.retrieve(page_id=page_id)
            
            # Extract title
            title = "Untitled"
            properties = page.get('properties', {})
            for prop in properties.values():
                if prop.get('type') == 'title':
                    title_items = prop.get('title', [])
                    if title_items:
                        title = title_items[0].get('plain_text', 'Untitled')
                    break
            
            return {
                'id': page['id'],
                'title': title,
                'last_edited_time': page.get('last_edited_time', ''),
                'last_edited_by': page.get('last_edited_by', {}).get('id', 'Unknown'),
                'url': page.get('url', '')
            }
            
        except Exception as e:
            print(f"❌ Error getting page info: {e}")
            return {}
    
    def collect_diff(self, page_id: str) -> Optional[DiffResult]:
        """
        Collect diff for a Notion page
        
        1. Fetch all blocks
        2. Compare with previous snapshot
        3. Store new snapshot and return diff
        """
        if not self.client:
            print("❌ Notion client not initialized")
            return None
        
        print(f"\n🔍 Collecting diff for Notion page: {page_id}")
        
        # Get page info
        page_info = self.get_page_info(page_id)
        if not page_info:
            print("   Could not get page info")
            return None
        
        print(f"   📄 Page: {page_info['title']}")
        print(f"   Last edited: {page_info['last_edited_time']}")
        
        # Fetch all blocks
        print("   Fetching blocks...")
        new_blocks = self._fetch_blocks_recursive(page_id)
        print(f"   Found {len(new_blocks)} blocks")
        
        # Get previous snapshot
        old_blocks = self.db.get_previous_notion_snapshot(page_id)
        if old_blocks:
            print(f"   Previous snapshot: {len(old_blocks)} blocks")
        else:
            print("   📝 First snapshot - no previous version")
        
        # Compute diff
        changes = DiffEngine.compute_block_diff(old_blocks, new_blocks)
        
        # Save new snapshot
        self.db.save_notion_snapshot(page_id, new_blocks)
        self.db.update_notion_tracking(
            page_id, 
            page_info['title'], 
            page_info['last_edited_time']
        )
        
        # Create result
        result = DiffResult(
            platform="notion",
            document_id=page_id,
            editor=page_info.get('last_edited_by', 'Unknown'),
            timestamp=page_info['last_edited_time'],
            changes=changes
        )
        
        # Save diff to history
        self.db.save_diff(result)
        
        return result


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Test Granular Data Collection with Diff Tracking',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Collect diff from Notion page
  python test_diff_collector.py --source notion --page-id abc123...
  
  # Collect diff from Google Drive document
  python test_diff_collector.py --source drive --doc-id 1xyz...
  
  # List tracked documents
  python test_diff_collector.py --list-tracked
  
  # View diff history
  python test_diff_collector.py --history
        """
    )
    
    parser.add_argument('--source', choices=['notion', 'drive'],
                       help='Data source to test')
    parser.add_argument('--page-id', help='Notion page ID')
    parser.add_argument('--doc-id', help='Google Drive document ID')
    parser.add_argument('--list-tracked', action='store_true',
                       help='List all tracked documents')
    parser.add_argument('--history', action='store_true',
                       help='Show diff history')
    parser.add_argument('--db-path', help='Custom database path')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("🧪 Granular Data Collection Test - Diff Tracking")
    print("=" * 70)
    
    # Initialize database
    db = DiffTestDatabase(args.db_path)
    
    if args.list_tracked:
        print("\n📋 Tracked Documents:")
        tracked = db.list_tracked_documents()
        
        print("\n  Google Drive:")
        if tracked["google_drive"]:
            for doc in tracked["google_drive"]:
                print(f"    - {doc['title']} ({doc['document_id'][:20]}...)")
                print(f"      Last revision: {doc['last_revision']}")
        else:
            print("    (none)")
        
        print("\n  Notion:")
        if tracked["notion"]:
            for page in tracked["notion"]:
                print(f"    - {page['title']} ({page['page_id'][:20]}...)")
                print(f"      Last edited: {page['last_edited']}")
        else:
            print("    (none)")
        return
    
    if args.history:
        print("\n📜 Diff History:")
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT platform, document_id, editor, timestamp, diff_json 
                FROM diff_history 
                ORDER BY created_at DESC 
                LIMIT 10
            ''')
            rows = cursor.fetchall()
            
            if not rows:
                print("  (no history)")
            else:
                for row in rows:
                    print(f"\n  [{row[0]}] {row[1][:30]}...")
                    print(f"    Editor: {row[2]}")
                    print(f"    Time: {row[3]}")
                    diff = json.loads(row[4])
                    added = len(diff.get('changes', {}).get('added', []))
                    deleted = len(diff.get('changes', {}).get('deleted', []))
                    print(f"    Changes: +{added} / -{deleted}")
        return
    
    if args.source == 'notion':
        if not args.page_id:
            print("❌ --page-id required for Notion")
            return
        
        collector = NotionDiffCollector(db)
        result = collector.collect_diff(args.page_id)
        
    elif args.source == 'drive':
        if not args.doc_id:
            print("❌ --doc-id required for Google Drive")
            return
        
        collector = GoogleDriveDiffCollector(db)
        result = collector.collect_diff(args.doc_id)
    
    else:
        parser.print_help()
        return
    
    # Display result
    if result:
        print("\n" + "=" * 70)
        print("📊 Diff Result")
        print("=" * 70)
        print(result.to_json())
        
        # Summary
        added = len(result.changes.get('added', []))
        deleted = len(result.changes.get('deleted', []))
        
        print(f"\n📈 Summary:")
        print(f"   Added: {added} items")
        print(f"   Deleted: {deleted} items")
        
        if added > 0:
            print(f"\n   ➕ Added content (first 3):")
            for item in result.changes['added'][:3]:
                preview = item[:50] + "..." if len(item) > 50 else item
                print(f"      - {preview}")
        
        if deleted > 0:
            print(f"\n   ➖ Deleted content (first 3):")
            for item in result.changes['deleted'][:3]:
                preview = item[:50] + "..." if len(item) > 50 else item
                print(f"      - {preview}")
    
    print("\n✨ Test completed!")
    print(f"   Database: {db.db_path}")


if __name__ == '__main__':
    main()
