"""
Google Drive Diff Plugin for All-Thing-Eye

Tracks actual content changes in Google Docs/Sheets/Slides by comparing
document revisions. Uses Drive API v3 and Docs export functionality.

Key features:
- Revision-based comparison for Google Docs
- Plain text export for noise-free diffing
- Baseline snapshot support (no false positives on first track)
- New document detection (created within collection window)
"""

import os
import difflib
import pickle
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path

from pymongo.errors import BulkWriteError

from src.plugins.base import DataSourcePlugin
from src.utils.logger import get_logger
from src.core.mongo_manager import MongoDBManager

# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    import io
    GOOGLE_APIS_AVAILABLE = True
except ImportError:
    GOOGLE_APIS_AVAILABLE = False


@dataclass
class ContentDiff:
    """Represents a content diff record"""
    platform: str
    document_id: str
    document_title: str
    document_url: str
    editor_id: str
    editor_name: str
    timestamp: str
    diff_type: str  # 'revision' for Drive
    changes: Dict[str, List[Any]] = field(default_factory=dict)
    revision_id: str = ""
    previous_revision_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GoogleDriveDiffPlugin(DataSourcePlugin):
    """
    Plugin for tracking content changes in Google Drive documents.
    
    Uses revision comparison to detect actual text changes,
    not just activity events.
    """
    
    # Scopes needed for reading document content and revisions
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.metadata.readonly'
    ]
    
    # Supported MIME types for text export
    EXPORTABLE_TYPES = {
        'application/vnd.google-apps.document': 'text/plain',  # Google Docs
        'application/vnd.google-apps.spreadsheet': 'text/csv',  # Google Sheets
        'application/vnd.google-apps.presentation': 'text/plain',  # Google Slides
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Google Drive Diff Plugin.
        
        Config options:
            credentials_path: Path to credentials.json
            token_path: Path to token pickle file
            days_to_collect: Number of days to look back (default: 1)
            rate_limit: Max requests per second (default: 10)
            folder_ids: List of folder IDs to track (optional, tracks all if not specified)
        """
        self.config = config
        self.logger = get_logger(__name__)
        
        if not GOOGLE_APIS_AVAILABLE:
            raise ImportError("Google API libraries not installed. Run: pip install google-api-python-client google-auth-oauthlib")
        
        # Paths
        self.credentials_path = config.get('credentials_path', 'config/google_drive/credentials.json')
        self.token_path = config.get('token_path', 'config/google_drive/token_diff.pickle')
        
        # Collection settings
        self.days_to_collect = config.get('days_to_collect', 1)
        self.rate_limit_delay = 1.0 / config.get('rate_limit', 10)  # Convert to delay
        self.folder_ids = config.get('folder_ids', [])  # Empty = track all accessible
        
        # API clients
        self.drive_service = None
        self.credentials = None
        
        # MongoDB collections
        self.mongo_manager = config.get('mongo_manager')
        if self.mongo_manager:
            db = self.mongo_manager.db
            self.collections = {
                "content_diffs": db["drive_content_diffs"],
                "revision_snapshots": db["drive_revision_snapshots"],
                "tracked_documents": db["drive_tracked_documents"]
            }
            
            # Create indexes
            self._create_indexes()
        
        # User cache
        self.user_cache: Dict[str, str] = {}
    
    def _create_indexes(self):
        """Create MongoDB indexes for efficient querying"""
        try:
            self.collections["content_diffs"].create_index([("document_id", 1), ("timestamp", -1)])
            self.collections["content_diffs"].create_index([("editor_id", 1)])
            self.collections["content_diffs"].create_index([("timestamp", -1)])
            
            self.collections["revision_snapshots"].create_index(
                [("document_id", 1), ("revision_id", 1)],
                unique=True
            )
            self.collections["revision_snapshots"].create_index([("document_id", 1), ("is_current", 1)])
            
            self.collections["tracked_documents"].create_index([("document_id", 1)], unique=True)
        except Exception as e:
            self.logger.warning(f"Index creation warning: {e}")
    
    # =========================================================================
    # Authentication
    # =========================================================================
    
    def authenticate(self) -> bool:
        """Authenticate with Google Drive API"""
        try:
            creds = None
            
            # Load existing token
            if os.path.exists(self.token_path):
                with open(self.token_path, 'rb') as token:
                    creds = pickle.load(token)
            
            # Refresh or get new credentials
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(self.credentials_path):
                        self.logger.error(f"Credentials file not found: {self.credentials_path}")
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                
                # Save token
                os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
                with open(self.token_path, 'wb') as token:
                    pickle.dump(creds, token)
            
            self.credentials = creds
            self.drive_service = build('drive', 'v3', credentials=creds)
            
            self.logger.info("✅ Google Drive authentication successful")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Google Drive authentication failed: {e}")
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
        Collect content diffs from recently modified documents.
        
        Returns:
            List of diff records for documents with changes
        """
        if not self.drive_service and not self.authenticate():
            return []
        
        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=self.days_to_collect)
        
        self.logger.info(f"\n📊 Google Drive Diff Collection")
        self.logger.info(f"   Period: {start_date.isoformat()} ~ {end_date.isoformat()}")
        
        # Get recently modified documents
        documents = self._get_recently_modified_docs(start_date)
        self.logger.info(f"   Found {len(documents)} recently modified documents")
        
        if not documents:
            return []
        
        # Process each document
        all_diffs = []
        
        for i, doc in enumerate(documents, 1):
            doc_id = doc['id']
            title = doc.get('name', 'Untitled')
            
            self.logger.info(f"\n  [{i}/{len(documents)}] {title[:40]}...")
            
            try:
                # Check if document type is exportable
                mime_type = doc.get('mimeType', '')
                if mime_type not in self.EXPORTABLE_TYPES:
                    self.logger.info(f"      ⏭️ Skipping (not exportable: {mime_type})")
                    continue
                
                # Process document revisions
                diff_record = self._process_document_revisions(doc, collection_start=start_date)
                if diff_record:
                    all_diffs.append(diff_record)
                    added = len(diff_record['changes'].get('added', []))
                    deleted = len(diff_record['changes'].get('deleted', []))
                    self.logger.info(f"      Changes: +{added} -{deleted}")
                
                # Update tracking
                self._update_document_tracking(doc)
                
            except Exception as e:
                self.logger.error(f"      ❌ Error: {e}")
            
            # Rate limiting
            import time
            time.sleep(self.rate_limit_delay)
        
        self.logger.info(f"\n✅ Collected {len(all_diffs)} diff records")
        return all_diffs
    
    def _get_recently_modified_docs(self, since: datetime) -> List[Dict]:
        """Get documents modified since the given time"""
        documents = []
        
        try:
            # Format date for Drive API query
            since_str = since.strftime('%Y-%m-%dT%H:%M:%S')
            
            # Build query
            query_parts = [
                f"modifiedTime > '{since_str}'",
                "trashed = false"
            ]
            
            # Add MIME type filter for exportable documents
            mime_conditions = " or ".join([
                f"mimeType = '{mt}'" for mt in self.EXPORTABLE_TYPES.keys()
            ])
            query_parts.append(f"({mime_conditions})")
            
            # Add folder filter if specified
            if self.folder_ids:
                folder_conditions = " or ".join([
                    f"'{fid}' in parents" for fid in self.folder_ids
                ])
                query_parts.append(f"({folder_conditions})")
            
            query = " and ".join(query_parts)
            
            page_token = None
            while True:
                response = self.drive_service.files().list(
                    q=query,
                    spaces='drive',
                    fields='nextPageToken, files(id, name, mimeType, modifiedTime, createdTime, lastModifyingUser, webViewLink)',
                    orderBy='modifiedTime desc',
                    pageSize=100,
                    pageToken=page_token
                ).execute()
                
                for file in response.get('files', []):
                    documents.append({
                        'id': file['id'],
                        'name': file.get('name', 'Untitled'),
                        'mimeType': file.get('mimeType', ''),
                        'modifiedTime': file.get('modifiedTime', ''),
                        'createdTime': file.get('createdTime', ''),
                        'lastModifyingUser': file.get('lastModifyingUser', {}),
                        'webViewLink': file.get('webViewLink', '')
                    })
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
            
            return documents
            
        except Exception as e:
            self.logger.error(f"❌ Error fetching documents: {e}")
            return []
    
    # =========================================================================
    # Revision Processing
    # =========================================================================
    
    def _process_document_revisions(
        self, 
        doc: Dict, 
        collection_start: datetime = None
    ) -> Optional[Dict]:
        """
        Get latest revision, compare with previous snapshot, save new snapshot.
        Returns diff record if changes detected.
        """
        doc_id = doc['id']
        
        # Get revisions list
        revisions = self._get_revisions(doc_id)
        if not revisions:
            self.logger.info(f"      📭 No revisions available")
            return None
        
        # Get the latest revision
        latest_revision = revisions[0]  # Most recent first
        revision_id = latest_revision.get('id', '')
        
        # Get previous snapshot
        previous_snapshot = self._get_previous_snapshot(doc_id)
        
        # Check if we've already processed this revision
        if previous_snapshot and previous_snapshot.get('revision_id') == revision_id:
            self.logger.info(f"      ✓ No new revisions")
            return None
        
        # Export current content as plain text
        current_content = self._export_document_content(doc_id, doc.get('mimeType', ''))
        if current_content is None:
            self.logger.warning(f"      ⚠️ Could not export content")
            return None
        
        # Check if this is the first snapshot (baseline)
        is_first_snapshot = previous_snapshot is None
        
        if is_first_snapshot:
            # Check if this is a genuinely NEW document
            is_new_document = False
            
            if collection_start:
                created_time_str = doc.get('createdTime', '')
                if created_time_str:
                    try:
                        created_time = datetime.fromisoformat(
                            created_time_str.replace('Z', '+00:00')
                        )
                        is_new_document = created_time >= collection_start
                    except:
                        pass
            
            if is_new_document and current_content.strip():
                # This is a genuinely NEW document - record content as "added"
                self.logger.info(f"      🆕 New document created! Recording as added.")
                
                lines = [line for line in current_content.splitlines() if line.strip()]
                changes = {
                    'added': lines[:100],  # Limit to first 100 lines
                    'deleted': [],
                    'modified': []
                }
                
                # Save snapshot
                self._save_revision_snapshot(doc_id, revision_id, current_content, is_baseline=True)
                
                if changes['added']:
                    # Get editor info
                    last_user = doc.get('lastModifyingUser', {})
                    editor_email = last_user.get('emailAddress', '')
                    editor_name = last_user.get('displayName', editor_email.split('@')[0] if editor_email else 'Unknown')
                    
                    diff_record = ContentDiff(
                        platform="google_drive",
                        document_id=doc_id,
                        document_title=doc.get('name', 'Untitled'),
                        document_url=doc.get('webViewLink', ''),
                        editor_id=editor_email,
                        editor_name=editor_name,
                        timestamp=doc.get('modifiedTime', datetime.now(timezone.utc).isoformat()),
                        diff_type="revision",
                        changes=changes,
                        revision_id=revision_id,
                        previous_revision_id=""
                    )
                    
                    self.collections["content_diffs"].insert_one(diff_record.to_dict())
                    return diff_record.to_dict()
                
                return None
            else:
                # Existing document, first time tracking - just baseline
                self._save_revision_snapshot(doc_id, revision_id, current_content, is_baseline=True)
                self.logger.info(f"      📸 Created baseline snapshot")
                return None
        
        # Compare with previous content
        previous_content = previous_snapshot.get('content', '')
        changes = self._compute_text_diff(previous_content, current_content)
        
        # Save new snapshot
        self._save_revision_snapshot(doc_id, revision_id, current_content)
        
        # Return diff only if there are actual changes
        if changes['added'] or changes['deleted']:
            # Get editor info
            last_user = doc.get('lastModifyingUser', {})
            editor_email = last_user.get('emailAddress', '')
            editor_name = last_user.get('displayName', editor_email.split('@')[0] if editor_email else 'Unknown')
            
            diff_record = ContentDiff(
                platform="google_drive",
                document_id=doc_id,
                document_title=doc.get('name', 'Untitled'),
                document_url=doc.get('webViewLink', ''),
                editor_id=editor_email,
                editor_name=editor_name,
                timestamp=doc.get('modifiedTime', datetime.now(timezone.utc).isoformat()),
                diff_type="revision",
                changes=changes,
                revision_id=revision_id,
                previous_revision_id=previous_snapshot.get('revision_id', '')
            )
            
            self.collections["content_diffs"].insert_one(diff_record.to_dict())
            return diff_record.to_dict()
        
        return None
    
    def _get_revisions(self, doc_id: str) -> List[Dict]:
        """Get revision list for a document"""
        try:
            response = self.drive_service.revisions().list(
                fileId=doc_id,
                fields='revisions(id, modifiedTime, lastModifyingUser)',
                pageSize=10  # Get recent revisions only
            ).execute()
            
            revisions = response.get('revisions', [])
            # Sort by modifiedTime descending
            revisions.sort(key=lambda r: r.get('modifiedTime', ''), reverse=True)
            return revisions
            
        except Exception as e:
            self.logger.warning(f"⚠️ Error fetching revisions: {e}")
            return []
    
    def _export_document_content(self, doc_id: str, mime_type: str) -> Optional[str]:
        """Export document content as plain text"""
        try:
            export_mime = self.EXPORTABLE_TYPES.get(mime_type, 'text/plain')
            
            request = self.drive_service.files().export_media(
                fileId=doc_id,
                mimeType=export_mime
            )
            
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while not done:
                _, done = downloader.next_chunk()
            
            content = fh.getvalue().decode('utf-8')
            return content
            
        except Exception as e:
            self.logger.warning(f"⚠️ Error exporting document: {e}")
            return None
    
    def _get_previous_snapshot(self, doc_id: str) -> Optional[Dict]:
        """Get the previous revision snapshot for comparison"""
        snapshot = self.collections["revision_snapshots"].find_one(
            {"document_id": doc_id, "is_current": True}
        )
        return snapshot
    
    def _save_revision_snapshot(
        self, 
        doc_id: str, 
        revision_id: str, 
        content: str,
        is_baseline: bool = False
    ):
        """Save new revision snapshot, marking previous as historical"""
        snapshot_time = datetime.now(timezone.utc)
        
        # Mark previous snapshot as not current
        self.collections["revision_snapshots"].update_many(
            {"document_id": doc_id, "is_current": True},
            {"$set": {"is_current": False}}
        )
        
        # Insert new snapshot
        self.collections["revision_snapshots"].insert_one({
            "document_id": doc_id,
            "revision_id": revision_id,
            "content": content,
            "snapshot_time": snapshot_time,
            "is_current": True,
            "is_baseline": is_baseline
        })
    
    def _compute_text_diff(self, old_text: str, new_text: str) -> Dict[str, List[str]]:
        """Compute line-level text diff"""
        old_lines = [l for l in old_text.splitlines() if l.strip()]
        new_lines = [l for l in new_text.splitlines() if l.strip()]
        
        differ = difflib.Differ()
        diff = list(differ.compare(old_lines, new_lines))
        
        added = [line[2:] for line in diff if line.startswith('+ ') and line[2:].strip()]
        deleted = [line[2:] for line in diff if line.startswith('- ') and line[2:].strip()]
        
        # Limit results to prevent huge diffs
        return {
            'added': added[:100],
            'deleted': deleted[:100],
            'modified': []
        }
    
    def _update_document_tracking(self, doc: Dict):
        """Update document tracking information"""
        self.collections["tracked_documents"].update_one(
            {"document_id": doc['id']},
            {
                "$set": {
                    "document_id": doc['id'],
                    "title": doc.get('name', 'Untitled'),
                    "mime_type": doc.get('mimeType', ''),
                    "url": doc.get('webViewLink', ''),
                    "last_checked_at": datetime.now(timezone.utc)
                },
                "$setOnInsert": {
                    "first_tracked_at": datetime.now(timezone.utc)
                }
            },
            upsert=True
        )
    
    # =========================================================================
    # Plugin Interface Methods
    # =========================================================================
    
    def get_source_name(self) -> str:
        return "google_drive_diff"
    
    def validate_config(self) -> bool:
        if not os.path.exists(self.credentials_path):
            self.logger.warning(f"Credentials file not found: {self.credentials_path}")
            return False
        return True
    
    def get_db_schema(self) -> Dict[str, str]:
        return {
            "drive_content_diffs": "Content diff records",
            "drive_revision_snapshots": "Document revision snapshots",
            "drive_tracked_documents": "Tracked document metadata"
        }
