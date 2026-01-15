#!/usr/bin/env python3
"""
Create baseline snapshots for all accessible Google Drive documents.

This script should be run ONCE before starting diff collection.
It creates initial snapshots without generating diff records,
so future collections will only show actual changes.

Usage:
    python scripts/create_drive_baseline.py
    python scripts/create_drive_baseline.py --dry-run  # Preview only
    python scripts/create_drive_baseline.py --folder-id <FOLDER_ID>  # Specific folder
"""

import os
import sys
import time
import argparse
import pickle
import io
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, '.env'))

from src.core.mongo_manager import MongoDBManager

# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    GOOGLE_APIS_AVAILABLE = True
except ImportError:
    GOOGLE_APIS_AVAILABLE = False


class GoogleDriveBaselineCreator:
    """Create baseline snapshots for all Google Drive documents"""
    
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.metadata.readonly'
    ]
    
    EXPORTABLE_TYPES = {
        'application/vnd.google-apps.document': 'text/plain',
        'application/vnd.google-apps.spreadsheet': 'text/csv',
        'application/vnd.google-apps.presentation': 'text/plain',
    }
    
    def __init__(self, dry_run: bool = False, folder_id: str = None):
        self.dry_run = dry_run
        self.folder_id = folder_id
        self.rate_limit_delay = 0.1  # ~10 requests/second
        
        if not GOOGLE_APIS_AVAILABLE:
            raise ImportError("Google API libraries not installed")
        
        # Paths
        self.credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'config/google_drive/credentials.json')
        self.token_path = os.getenv('GOOGLE_TOKEN_PATH', 'config/google_drive/token_diff.pickle')
        
        # Authenticate
        self.drive_service = self._authenticate()
        
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
                "revision_snapshots": self.db["drive_revision_snapshots"],
                "tracked_documents": self.db["drive_tracked_documents"]
            }
            print("✅ MongoDB connected")
    
    def _authenticate(self):
        """Authenticate with Google Drive API"""
        creds = None
        
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(f"Credentials file not found: {self.credentials_path}")
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        return build('drive', 'v3', credentials=creds)
    
    def run(self):
        """Create baseline snapshots for all accessible documents"""
        print("=" * 70)
        print("📁 Google Drive Baseline Snapshot Creator")
        print("=" * 70)
        
        if self.dry_run:
            print("🔍 DRY RUN MODE - No data will be saved")
        
        print("\n🔍 Searching for exportable documents...")
        documents = self._get_all_documents()
        
        print(f"\n📄 Found {len(documents)} exportable documents")
        
        if self.dry_run:
            print("\n📋 Documents to snapshot:")
            for i, doc in enumerate(documents[:20], 1):
                print(f"   {i}. {doc['name'][:50]}...")
            if len(documents) > 20:
                print(f"   ... and {len(documents) - 20} more")
            return
        
        # Check existing snapshots
        existing_docs = set()
        for doc_id in self.collections["revision_snapshots"].distinct("document_id"):
            existing_docs.add(doc_id)
        
        new_docs = [d for d in documents if d['id'] not in existing_docs]
        
        print(f"\n📊 Status:")
        print(f"   - Already have snapshots: {len(existing_docs)} documents")
        print(f"   - Need baseline: {len(new_docs)} documents")
        
        if not new_docs:
            print("\n✅ All documents already have baseline snapshots!")
            return
        
        print(f"\n🚀 Creating baseline snapshots for {len(new_docs)} documents...")
        print("   (This may take a while due to API rate limits)")
        
        success_count = 0
        error_count = 0
        skipped_count = 0
        
        for i, doc in enumerate(new_docs, 1):
            doc_id = doc['id']
            title = doc['name'][:40]
            
            print(f"\n[{i}/{len(new_docs)}] 📄 {title}...")
            
            try:
                # Export content
                content = self._export_document_content(doc_id, doc['mimeType'])
                
                if content is None:
                    skipped_count += 1
                    print(f"   ⏭️ Could not export")
                    continue
                
                # Get latest revision
                revisions = self._get_revisions(doc_id)
                if not revisions:
                    skipped_count += 1
                    print(f"   ⏭️ No revisions available")
                    continue
                
                revision_id = revisions[0].get('id', '')
                
                # Save snapshot
                self._save_baseline_snapshot(doc_id, revision_id, content)
                
                # Track the document
                self._mark_document_tracked(doc)
                
                success_count += 1
                print(f"   ✅ Baseline created ({len(content)} chars)")
                
            except Exception as e:
                error_count += 1
                print(f"   ❌ Error: {e}")
            
            time.sleep(self.rate_limit_delay)
        
        print("\n" + "=" * 70)
        print("📊 Summary")
        print("=" * 70)
        print(f"   ✅ Successful: {success_count}")
        print(f"   ⏭️ Skipped: {skipped_count}")
        print(f"   ❌ Errors: {error_count}")
        print(f"   📄 Total tracked: {len(existing_docs) + success_count}")
        print("\n✨ Baseline creation complete!")
        print("   Future diff collections will only show actual changes.")
    
    def _get_all_documents(self) -> List[Dict]:
        """Get all accessible exportable documents"""
        documents = []
        
        # Build query
        mime_conditions = " or ".join([
            f"mimeType = '{mt}'" for mt in self.EXPORTABLE_TYPES.keys()
        ])
        query_parts = [f"({mime_conditions})", "trashed = false"]
        
        if self.folder_id:
            query_parts.append(f"'{self.folder_id}' in parents")
        
        query = " and ".join(query_parts)
        
        page_token = None
        while True:
            try:
                response = self.drive_service.files().list(
                    q=query,
                    spaces='drive',
                    fields='nextPageToken, files(id, name, mimeType, modifiedTime, createdTime, webViewLink)',
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
                        'webViewLink': file.get('webViewLink', '')
                    })
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
                
                print(f"   Found {len(documents)} documents so far...", end='\r')
                time.sleep(self.rate_limit_delay)
                
            except Exception as e:
                print(f"\n⚠️ Error searching documents: {e}")
                break
        
        print()
        return documents
    
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
            
            return fh.getvalue().decode('utf-8')
            
        except Exception as e:
            return None
    
    def _get_revisions(self, doc_id: str) -> List[Dict]:
        """Get revision list for a document"""
        try:
            response = self.drive_service.revisions().list(
                fileId=doc_id,
                fields='revisions(id, modifiedTime)',
                pageSize=1
            ).execute()
            
            return response.get('revisions', [])
        except:
            return []
    
    def _save_baseline_snapshot(self, doc_id: str, revision_id: str, content: str):
        """Save initial baseline snapshot"""
        snapshot_time = datetime.now(timezone.utc)
        
        self.collections["revision_snapshots"].insert_one({
            "document_id": doc_id,
            "revision_id": revision_id,
            "content": content,
            "snapshot_time": snapshot_time,
            "is_current": True,
            "is_baseline": True
        })
    
    def _mark_document_tracked(self, doc: Dict):
        """Mark document as tracked with baseline timestamp"""
        self.collections["tracked_documents"].update_one(
            {"document_id": doc['id']},
            {
                "$set": {
                    "document_id": doc['id'],
                    "title": doc['name'],
                    "mime_type": doc['mimeType'],
                    "url": doc.get('webViewLink', ''),
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
        description="Create baseline snapshots for all Google Drive documents"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview documents without creating snapshots'
    )
    parser.add_argument(
        '--folder-id',
        type=str,
        help='Limit to specific folder ID'
    )
    
    args = parser.parse_args()
    
    try:
        creator = GoogleDriveBaselineCreator(
            dry_run=args.dry_run,
            folder_id=args.folder_id
        )
        creator.run()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
