"""
Notion Diff Plugin for All-Thing-Eye

Tracks granular content changes in Notion pages:
- Block-level content changes (added, deleted, modified)
- Comment changes (new comments, deleted comments)
- Stores snapshots and diffs in MongoDB

Collections:
- notion_block_snapshots: Current and historical block states
- notion_comment_snapshots: Current and historical comment states  
- notion_content_diffs: Structured diff records for activity feed
"""

import difflib
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
from notion_client import Client
from notion_client.errors import APIResponseError
from pymongo import UpdateOne, DESCENDING
from pymongo.errors import BulkWriteError

from src.plugins.base import DataSourcePlugin
from src.utils.logger import get_logger
from src.core.mongo_manager import MongoDBManager


@dataclass
class ContentDiff:
    """Structured diff record for activity feed"""
    platform: str  # "notion"
    document_id: str  # page_id
    document_title: str
    document_url: str
    editor_id: str
    editor_name: str
    timestamp: str  # ISO8601
    diff_type: str  # "block" or "comment"
    changes: Dict[str, List[Dict[str, Any]]]  # {"added": [...], "deleted": [...], "modified": [...]}
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class NotionDiffPlugin(DataSourcePlugin):
    """
    Plugin for tracking granular Notion content changes.
    Designed to run frequently (every 1-5 minutes) for real-time tracking.
    """
    
    def __init__(self, config: Dict[str, Any], mongo_manager: MongoDBManager):
        self.config = config or {}
        self.mongo = mongo_manager
        self.token = self.config.get('token', '')
        self.days_to_collect = self.config.get('days_to_collect', 1)
        self.rate_limit_delay = 1.0 / self.config.get('rate_limit', 3)  # requests per second
        
        self.client = None
        self.logger = get_logger(__name__)
        self.user_cache = {}  # Cache user info to reduce API calls
        
        # MongoDB collections
        self.db = mongo_manager.db
        self.collections = {
            "block_snapshots": self.db["notion_block_snapshots"],
            "comment_snapshots": self.db["notion_comment_snapshots"],
            "content_diffs": self.db["notion_content_diffs"],
            "page_tracking": self.db["notion_page_tracking"],
            "users": self.db["notion_users"],
        }
        
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create necessary indexes for performance"""
        try:
            # Block snapshots - find current blocks for a page
            self.collections["block_snapshots"].create_index([
                ("page_id", 1), ("block_id", 1), ("is_current", 1)
            ])
            self.collections["block_snapshots"].create_index([
                ("page_id", 1), ("snapshot_time", DESCENDING)
            ])
            
            # Comment snapshots
            self.collections["comment_snapshots"].create_index([
                ("page_id", 1), ("comment_id", 1), ("is_current", 1)
            ])
            
            # Content diffs - for activity feed queries
            self.collections["content_diffs"].create_index([
                ("timestamp", DESCENDING)
            ])
            self.collections["content_diffs"].create_index([
                ("document_id", 1), ("timestamp", DESCENDING)
            ])
            self.collections["content_diffs"].create_index([
                ("editor_id", 1), ("timestamp", DESCENDING)
            ])
            
            # Page tracking
            self.collections["page_tracking"].create_index("page_id", unique=True)
            
            self.logger.info("✅ MongoDB indexes ensured")
        except Exception as e:
            self.logger.warning(f"⚠️ Index creation warning: {e}")
    
    def get_source_name(self) -> str:
        return "notion_diff"
    
    def get_required_config_keys(self) -> List[str]:
        return ['token']
    
    def get_db_schema(self) -> Dict[str, str]:
        return {}  # MongoDB doesn't use SQL schema
    
    def authenticate(self) -> bool:
        """Authenticate with Notion API"""
        try:
            if not self.token:
                self.logger.error("Notion token not provided")
                return False
            
            self.client = Client(auth=self.token)
            response = self.client.users.me()
            self.logger.info(f"✅ Notion Diff Plugin authenticated: {response.get('name', 'Unknown')}")
            return True
            
        except APIResponseError as e:
            self.logger.error(f"❌ Notion authentication failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"❌ Unexpected error: {e}")
            return False
    
    # =========================================================================
    # Data Collection
    # =========================================================================
    
    def collect_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Collect and process all recently edited pages.
        
        Returns:
            List of diff records for pages with changes
        """
        if not self.client and not self.authenticate():
            return []
        
        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=self.days_to_collect)
        
        self.logger.info(f"\n📊 Notion Diff Collection")
        self.logger.info(f"   Period: {start_date.isoformat()} ~ {end_date.isoformat()}")
        
        # Get recently edited pages
        pages = self._get_recently_edited_pages(start_date)
        self.logger.info(f"   Found {len(pages)} recently edited pages")
        
        if not pages:
            return []
        
        # Process each page
        all_diffs = []
        
        for i, page in enumerate(pages, 1):
            page_id = page['id']
            title = page.get('title', 'Untitled')
            
            self.logger.info(f"\n  [{i}/{len(pages)}] {title[:40]}...")
            
            try:
                # Collect block diffs (pass start_date to detect new documents)
                block_diffs = self._process_page_blocks(page, collection_start=start_date)
                if block_diffs:
                    all_diffs.append(block_diffs)
                    added = len(block_diffs['changes'].get('added', []))
                    deleted = len(block_diffs['changes'].get('deleted', []))
                    modified = len(block_diffs['changes'].get('modified', []))
                    self.logger.info(f"      Blocks: +{added} -{deleted} ~{modified}")
                
                # Collect comment diffs
                comment_diffs = self._process_page_comments(page)
                if comment_diffs:
                    all_diffs.append(comment_diffs)
                    added = len(comment_diffs['changes'].get('added', []))
                    deleted = len(comment_diffs['changes'].get('deleted', []))
                    self.logger.info(f"      Comments: +{added} -{deleted}")
                
                # Update tracking
                self._update_page_tracking(page)
                
            except Exception as e:
                self.logger.error(f"      ❌ Error: {e}")
            
            # Rate limiting
            time.sleep(self.rate_limit_delay)
        
        self.logger.info(f"\n✅ Collected {len(all_diffs)} diff records")
        return all_diffs
    
    def _get_recently_edited_pages(self, since: datetime) -> List[Dict]:
        """Search for pages edited since the given time"""
        pages = []
        
        try:
            query = {
                "filter": {"value": "page", "property": "object"},
                "sort": {"direction": "descending", "timestamp": "last_edited_time"}
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
                    
                    if last_edited < since:
                        has_more = False
                        break
                    
                    # Extract page info
                    title = self._extract_title(page.get('properties', {}))
                    editor_id = page.get('last_edited_by', {}).get('id', '')
                    
                    pages.append({
                        'id': page['id'],
                        'title': title,
                        'url': page.get('url', ''),
                        'created_time': page.get('created_time'),  # For detecting new documents
                        'last_edited_time': page.get('last_edited_time'),
                        'last_edited_by': editor_id,
                        'editor_name': self._get_user_name(editor_id)
                    })
                
                has_more = response.get('has_more', False) and has_more
                next_cursor = response.get('next_cursor')
            
            return pages
            
        except Exception as e:
            self.logger.error(f"❌ Error searching pages: {e}")
            return []
    
    # =========================================================================
    # Block Processing
    # =========================================================================
    
    def _process_page_blocks(self, page: Dict, collection_start: datetime = None) -> Optional[Dict]:
        """
        Fetch blocks, compare with previous snapshot, save new snapshot.
        Returns diff record if changes detected.
        
        Logic for first-time tracking:
        - If page was CREATED within collection window → Record as "new document" (added)
        - If page existed before collection window → Just baseline, no diff
        
        This ensures:
        - Genuinely new documents are tracked as "added"
        - Existing documents we see for first time don't flood as "added"
        """
        page_id = page['id']
        
        # Fetch current blocks
        current_blocks = self._fetch_all_blocks(page_id)
        
        # Get previous snapshot
        previous_blocks = self._get_previous_block_snapshot(page_id)
        
        # Check if this is the first snapshot (baseline)
        is_first_snapshot = len(previous_blocks) == 0
        
        if is_first_snapshot:
            # Check if this is a genuinely NEW document (created within collection window)
            is_new_document = False
            
            if collection_start:
                created_time_str = page.get('created_time', '')
                if created_time_str:
                    try:
                        created_time = datetime.fromisoformat(
                            created_time_str.replace('Z', '+00:00')
                        )
                        is_new_document = created_time >= collection_start
                    except:
                        pass
            
            if is_new_document and current_blocks:
                # This is a genuinely NEW document - record all content as "added"
                self.logger.info(f"      🆕 New document created! Recording as added.")
                
                changes = {
                    'added': [
                        {
                            'block_id': b['block_id'],
                            'block_type': b['block_type'],
                            'content': b['plain_text']
                        }
                        for b in current_blocks if b.get('plain_text')
                    ],
                    'deleted': [],
                    'modified': []
                }
                
                # Save snapshot
                self._save_block_snapshot(page_id, current_blocks, is_baseline=True)
                
                if changes['added']:
                    diff_record = ContentDiff(
                        platform="notion",
                        document_id=page_id,
                        document_title=page.get('title', 'Untitled'),
                        document_url=page.get('url', ''),
                        editor_id=page.get('last_edited_by', ''),
                        editor_name=page.get('editor_name', 'Unknown'),
                        timestamp=page.get('last_edited_time', datetime.now(timezone.utc).isoformat()),
                        diff_type="block",
                        changes=changes
                    )
                    
                    self.collections["content_diffs"].insert_one(diff_record.to_dict())
                    return diff_record.to_dict()
                
                return None
            else:
                # Existing document, first time tracking - just baseline
                self._save_block_snapshot(page_id, current_blocks, is_baseline=True)
                self.logger.info(f"      📸 Created baseline snapshot ({len(current_blocks)} blocks)")
                return None
        
        # Compute diff against previous snapshot
        changes = self._compute_block_diff(previous_blocks, current_blocks)
        
        # Save new snapshot
        self._save_block_snapshot(page_id, current_blocks)
        
        # Return diff only if there are actual changes
        if changes['added'] or changes['deleted'] or changes['modified']:
            diff_record = ContentDiff(
                platform="notion",
                document_id=page_id,
                document_title=page.get('title', 'Untitled'),
                document_url=page.get('url', ''),
                editor_id=page.get('last_edited_by', ''),
                editor_name=page.get('editor_name', 'Unknown'),
                timestamp=page.get('last_edited_time', datetime.now(timezone.utc).isoformat()),
                diff_type="block",
                changes=changes
            )
            
            # Save to MongoDB
            self.collections["content_diffs"].insert_one(diff_record.to_dict())
            
            return diff_record.to_dict()
        
        return None
    
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
                        
                        # COMPLETELY SKIP child_page and child_database blocks
                        # These are tracked as their own separate pages
                        # Including them causes duplicate diffs when child pages are edited
                        if block_type in ('child_page', 'child_database'):
                            continue
                        
                        plain_text = self._extract_block_text(block)
                        
                        blocks.append({
                            'block_id': block['id'],
                            'block_type': block_type,
                            'plain_text': plain_text,
                            'last_edited_time': block.get('last_edited_time', ''),
                            'parent_id': parent_id
                        })
                        
                        # Recurse into children for nested content (lists, toggles, etc.)
                        if block.get('has_children', False):
                            time.sleep(self.rate_limit_delay)
                            fetch_children(block['id'], block['id'])
                    
                    has_more = response.get('has_more', False)
                    next_cursor = response.get('next_cursor')
                    
                except APIResponseError as e:
                    self.logger.warning(f"⚠️ Error fetching blocks: {e}")
                    break
        
        fetch_children(page_id)
        return blocks
    
    def _extract_block_text(self, block: Dict) -> str:
        """Extract plain text from a block"""
        block_type = block.get('type', '')
        
        if block_type not in block:
            return ''
        
        block_content = block[block_type]
        
        # Handle different text sources
        if 'rich_text' in block_content:
            return self._extract_rich_text(block_content['rich_text'])
        elif 'text' in block_content:
            return self._extract_rich_text(block_content['text'])
        elif 'caption' in block_content:
            return self._extract_rich_text(block_content['caption'])
        
        return ''
    
    def _extract_rich_text(self, rich_text: List[Dict]) -> str:
        """Extract plain text from rich_text array (ignoring annotations)"""
        return ''.join(item.get('plain_text', '') for item in rich_text)
    
    def _get_previous_block_snapshot(self, page_id: str) -> List[Dict]:
        """Get the previous block snapshot for comparison"""
        cursor = self.collections["block_snapshots"].find(
            {"page_id": page_id, "is_current": True}
        )
        return list(cursor)
    
    def _save_block_snapshot(self, page_id: str, blocks: List[Dict], is_baseline: bool = False):
        """Save new block snapshot, marking previous as historical"""
        snapshot_time = datetime.now(timezone.utc)
        
        # Mark previous blocks as not current
        self.collections["block_snapshots"].update_many(
            {"page_id": page_id, "is_current": True},
            {"$set": {"is_current": False}}
        )
        
        # Insert new blocks
        if blocks:
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
                    "is_baseline": is_baseline  # Mark if this is initial baseline snapshot
                })
            
            try:
                self.collections["block_snapshots"].insert_many(documents, ordered=False)
            except BulkWriteError as e:
                self.logger.warning(f"⚠️ Some blocks already exist: {e.details.get('nInserted', 0)} inserted")
    
    def _compute_block_diff(
        self, 
        old_blocks: List[Dict], 
        new_blocks: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """Compute block-level differences"""
        old_map = {b['block_id']: b for b in old_blocks}
        new_map = {b['block_id']: b for b in new_blocks}
        
        added = []
        deleted = []
        modified = []
        
        # Find added and modified
        for block_id, new_block in new_map.items():
            text = new_block.get('plain_text', '')
            if not text:
                continue
                
            if block_id not in old_map:
                # New block
                added.append({
                    'block_id': block_id,
                    'block_type': new_block.get('block_type', ''),
                    'content': text
                })
            else:
                # Check if modified
                old_block = old_map[block_id]
                old_text = old_block.get('plain_text', '')
                
                if old_text != text:
                    # Content changed
                    text_diff = self._compute_text_diff(old_text, text)
                    modified.append({
                        'block_id': block_id,
                        'block_type': new_block.get('block_type', ''),
                        'old_content': old_text,
                        'new_content': text,
                        'added_lines': text_diff['added'],
                        'deleted_lines': text_diff['deleted']
                    })
        
        # Find deleted
        for block_id, old_block in old_map.items():
            text = old_block.get('plain_text', '')
            if block_id not in new_map and text:
                deleted.append({
                    'block_id': block_id,
                    'block_type': old_block.get('block_type', ''),
                    'content': text
                })
        
        return {'added': added, 'deleted': deleted, 'modified': modified}
    
    def _compute_text_diff(self, old_text: str, new_text: str) -> Dict[str, List[str]]:
        """Compute line-level text diff"""
        old_lines = old_text.splitlines() if old_text else []
        new_lines = new_text.splitlines() if new_text else []
        
        differ = difflib.Differ()
        diff = list(differ.compare(old_lines, new_lines))
        
        added = [line[2:] for line in diff if line.startswith('+ ') and line[2:].strip()]
        deleted = [line[2:] for line in diff if line.startswith('- ') and line[2:].strip()]
        
        return {'added': added, 'deleted': deleted}
    
    # =========================================================================
    # Comment Processing
    # =========================================================================
    
    def _process_page_comments(self, page: Dict) -> Optional[Dict]:
        """
        Fetch comments, compare with previous snapshot, save new snapshot.
        Returns diff record if changes detected.
        """
        page_id = page['id']
        
        # Fetch current comments
        current_comments = self._fetch_comments(page_id)
        
        # Get previous snapshot
        previous_comments = self._get_previous_comment_snapshot(page_id)
        
        # Compute diff
        changes = self._compute_comment_diff(previous_comments, current_comments)
        
        # Save new snapshot
        self._save_comment_snapshot(page_id, current_comments)
        
        # Return diff if there are changes
        if changes['added'] or changes['deleted']:
            diff_record = ContentDiff(
                platform="notion",
                document_id=page_id,
                document_title=page.get('title', 'Untitled'),
                document_url=page.get('url', ''),
                editor_id=page.get('last_edited_by', ''),
                editor_name=page.get('editor_name', 'Unknown'),
                timestamp=page.get('last_edited_time', datetime.now(timezone.utc).isoformat()),
                diff_type="comment",
                changes=changes
            )
            
            # Save to MongoDB
            self.collections["content_diffs"].insert_one(diff_record.to_dict())
            
            return diff_record.to_dict()
        
        return None
    
    def _fetch_comments(self, page_id: str) -> List[Dict]:
        """Fetch all comments for a page"""
        comments = []
        
        try:
            response = self.client.comments.list(block_id=page_id)
            
            for comment in response.get('results', []):
                created_by = comment.get('created_by', {})
                
                comments.append({
                    'comment_id': comment['id'],
                    'content': self._extract_rich_text(comment.get('rich_text', [])),
                    'created_time': comment.get('created_time', ''),
                    'created_by_id': created_by.get('id', ''),
                    'created_by_name': self._get_user_name(created_by.get('id', ''))
                })
                
        except APIResponseError:
            # Page might not support comments
            pass
        
        return comments
    
    def _get_previous_comment_snapshot(self, page_id: str) -> List[Dict]:
        """Get the previous comment snapshot for comparison"""
        cursor = self.collections["comment_snapshots"].find(
            {"page_id": page_id, "is_current": True}
        )
        return list(cursor)
    
    def _save_comment_snapshot(self, page_id: str, comments: List[Dict]):
        """Save new comment snapshot"""
        snapshot_time = datetime.now(timezone.utc)
        
        # Mark previous as not current
        self.collections["comment_snapshots"].update_many(
            {"page_id": page_id, "is_current": True},
            {"$set": {"is_current": False}}
        )
        
        # Insert new comments
        if comments:
            documents = []
            for comment in comments:
                documents.append({
                    "page_id": page_id,
                    "comment_id": comment['comment_id'],
                    "content": comment['content'],
                    "created_time": comment['created_time'],
                    "created_by_id": comment['created_by_id'],
                    "created_by_name": comment['created_by_name'],
                    "snapshot_time": snapshot_time,
                    "is_current": True
                })
            
            try:
                self.collections["comment_snapshots"].insert_many(documents, ordered=False)
            except BulkWriteError:
                pass
    
    def _compute_comment_diff(
        self, 
        old_comments: List[Dict], 
        new_comments: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """Compute comment differences"""
        old_ids = {c['comment_id'] for c in old_comments}
        new_map = {c['comment_id']: c for c in new_comments}
        
        added = []
        deleted = []
        
        # Find added comments
        for comment_id, comment in new_map.items():
            if comment_id not in old_ids:
                added.append({
                    'comment_id': comment_id,
                    'content': comment.get('content', ''),
                    'author_id': comment.get('created_by_id', ''),
                    'author_name': comment.get('created_by_name', 'Unknown'),
                    'created_time': comment.get('created_time', '')
                })
        
        # Find deleted comments
        for old_comment in old_comments:
            if old_comment['comment_id'] not in new_map:
                deleted.append({
                    'comment_id': old_comment['comment_id'],
                    'content': old_comment.get('content', ''),
                    'author_id': old_comment.get('created_by_id', ''),
                    'author_name': old_comment.get('created_by_name', 'Unknown')
                })
        
        return {'added': added, 'deleted': deleted}
    
    # =========================================================================
    # Utilities
    # =========================================================================
    
    def _extract_title(self, properties: Dict) -> str:
        """Extract title from page properties"""
        for prop_value in properties.values():
            if prop_value.get('type') == 'title':
                title_items = prop_value.get('title', [])
                if title_items:
                    return title_items[0].get('plain_text', 'Untitled')
        return 'Untitled'
    
    def _get_user_name(self, user_id: str) -> str:
        """Get user name from cache or API"""
        if not user_id:
            return 'Unknown'
        
        if user_id in self.user_cache:
            return self.user_cache[user_id]
        
        try:
            user = self.client.users.retrieve(user_id)
            name = user.get('name', 'Unknown')
            self.user_cache[user_id] = name
            return name
        except:
            return 'Unknown'
    
    def _update_page_tracking(self, page: Dict):
        """Update page tracking info"""
        self.collections["page_tracking"].update_one(
            {"page_id": page['id']},
            {
                "$set": {
                    "page_id": page['id'],
                    "title": page.get('title', 'Untitled'),
                    "url": page.get('url', ''),
                    "last_edited_time": page.get('last_edited_time'),
                    "last_snapshot_time": datetime.now(timezone.utc)
                }
            },
            upsert=True
        )
    
    # =========================================================================
    # Query Methods (for frontend)
    # =========================================================================
    
    def get_recent_diffs(
        self, 
        limit: int = 50,
        page_id: Optional[str] = None,
        editor_id: Optional[str] = None,
        diff_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Get recent content diffs for activity feed.
        
        Args:
            limit: Maximum number of records
            page_id: Filter by page
            editor_id: Filter by editor
            diff_type: Filter by type ("block" or "comment")
        """
        query = {}
        
        if page_id:
            query['document_id'] = page_id
        if editor_id:
            query['editor_id'] = editor_id
        if diff_type:
            query['diff_type'] = diff_type
        
        cursor = self.collections["content_diffs"].find(query).sort(
            "timestamp", DESCENDING
        ).limit(limit)
        
        return list(cursor)
    
    def get_page_history(self, page_id: str, limit: int = 20) -> List[Dict]:
        """Get diff history for a specific page"""
        cursor = self.collections["content_diffs"].find(
            {"document_id": page_id}
        ).sort("timestamp", DESCENDING).limit(limit)
        
        return list(cursor)
    
    def get_user_activity(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get all diffs by a specific user"""
        cursor = self.collections["content_diffs"].find(
            {"editor_id": user_id}
        ).sort("timestamp", DESCENDING).limit(limit)
        
        return list(cursor)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        return {
            "tracked_pages": self.collections["page_tracking"].count_documents({}),
            "total_block_snapshots": self.collections["block_snapshots"].count_documents({}),
            "current_blocks": self.collections["block_snapshots"].count_documents({"is_current": True}),
            "total_comment_snapshots": self.collections["comment_snapshots"].count_documents({}),
            "total_diffs": self.collections["content_diffs"].count_documents({}),
            "block_diffs": self.collections["content_diffs"].count_documents({"diff_type": "block"}),
            "comment_diffs": self.collections["content_diffs"].count_documents({"diff_type": "comment"})
        }
    
    # =========================================================================
    # Member Activity Extraction (for unified activity feed)
    # =========================================================================
    
    def get_member_mapping(self) -> Dict[str, str]:
        """Return mapping of Notion user IDs to names"""
        return self.user_cache.copy()
    
    def get_member_details(self) -> Dict[str, Dict]:
        """Return detailed member info"""
        return {
            user_id: {"name": name, "source": "notion"}
            for user_id, name in self.user_cache.items()
        }
    
    def extract_member_activities(self, data: List[Dict]) -> List[Dict]:
        """
        Convert diff records to unified member activity format.
        """
        activities = []
        
        for diff in data:
            # Create activity record
            activity = {
                'source_user_id': diff.get('editor_id', ''),
                'activity_type': f"notion_{diff.get('diff_type', 'edit')}",
                'timestamp': diff.get('timestamp'),
                'metadata': {
                    'page_id': diff.get('document_id'),
                    'page_title': diff.get('document_title'),
                    'page_url': diff.get('document_url'),
                    'diff_type': diff.get('diff_type'),
                    'changes': diff.get('changes', {}),
                    'added_count': len(diff.get('changes', {}).get('added', [])),
                    'deleted_count': len(diff.get('changes', {}).get('deleted', [])),
                    'modified_count': len(diff.get('changes', {}).get('modified', []))
                }
            }
            activities.append(activity)
        
        return activities
