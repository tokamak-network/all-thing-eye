"""
Google Drive Plugin for All-Thing-Eye (MongoDB Version)

Collects Google Drive activity logs using Admin SDK Reports API.
Requires Google Workspace Admin privileges.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import os
import pickle
from pathlib import Path
import pytz
from pymongo.errors import DuplicateKeyError

from src.plugins.base import DataSourcePlugin
from src.utils.logger import get_logger
from src.core.mongo_manager import MongoDBManager
from src.models.mongo_models import DriveActivity, DriveDocument, DriveFolder

# Google API imports (lazy load to avoid import errors if not installed)
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GOOGLE_APIS_AVAILABLE = True
except ImportError:
    GOOGLE_APIS_AVAILABLE = False


class GoogleDrivePluginMongo(DataSourcePlugin):
    """Plugin for collecting Google Drive activity data via Admin SDK (MongoDB version)"""
    
    # API Scopes - Admin privileges required
    SCOPES = [
        'https://www.googleapis.com/auth/admin.reports.audit.readonly',
        'https://www.googleapis.com/auth/admin.reports.usage.readonly'
    ]
    
    # Activity type mapping
    ACTIVITY_MAP = {
        'create': '생성',
        'edit': '편집',
        'upload': '업로드',
        'download': '다운로드',
        'delete': '삭제',
        'trash': '휴지통 이동',
        'untrash': '복원',
        'rename': '이름 변경',
        'move': '이동',
        'copy': '복사',
        'add_to_folder': '폴더에 추가',
        'remove_from_folder': '폴더에서 제거',
        'share': '공유',
        'unshare': '공유 취소',
        'change_user_access': '접근 권한 변경',
        'change_acl_editors': '편집자 변경',
        'change_document_access_scope': '문서 접근 범위 변경',
        'change_document_visibility': '문서 공개 설정 변경',
        'sheets_import_range': '스프레드시트 범위 가져오기',
        'approval_requested': '승인 요청',
        'approval_completed': '승인 완료',
    }
    
    # Events to EXCLUDE from collection (noise reduction)
    EXCLUDE_EVENTS = {
        'download',                      # 다운로드 (조회 행위)
        'view',                          # 조회
        'share',                         # 공유 변경 (빈번함)
        'change_acl_editors',            # 편집자 권한 변경
        'change_document_access_scope',  # 문서 접근 범위 변경
        'sheets_import_range',           # 스프레드시트 자동 동기화 (매우 빈번)
    }
    
    # Edit events will be summarized daily instead of individual records
    
    # Document type mapping
    DOC_TYPE_MAP = {
        'document': '문서',
        'spreadsheet': '스프레드시트',
        'presentation': '프레젠테이션',
        'folder': '폴더',
        'file': '파일',
        'drawing': '그림',
        'form': '설문지',
        'site': '사이트',
        'mp4': '동영상(mp4)',
        'mpeg': '동영상(mpeg)',
        'mov': '동영상(mov)',
        'avi': '동영상(avi)',
        'video': '동영상',
        'png': '이미지(png)',
        'jpeg': '이미지(jpeg)',
        'jpg': '이미지(jpg)',
        'pdf': 'PDF',
        'txt': '텍스트',
        'msword': 'MS Word',
        'msexcel': 'MS Excel',
        'mspowerpoint': 'MS PowerPoint',
        'html': 'HTML'
    }
    
    def __init__(self, config: Dict[str, Any], mongo_manager=None):
        """
        Initialize Google Drive plugin
        
        Args:
            config: Plugin configuration containing:
                - credentials_path: Path to credentials.json
                - token_path: Path to token_admin.pickle
                - target_users: List of user emails to track (optional, defaults to all)
                - days_to_collect: Number of days to collect (default: 7)
            mongo_manager: MongoDB manager instance
        """
        if not GOOGLE_APIS_AVAILABLE:
            raise ImportError(
                "Google API libraries not installed. "
                "Install with: pip install google-auth google-auth-oauthlib "
                "google-auth-httplib2 google-api-python-client"
            )
        
        self.config = config or {}
        self.mongo = mongo_manager
        self.logger = get_logger(__name__)
        
        # Set up paths
        base_path = Path(__file__).parent.parent.parent
        
        credentials_path_str = self.config.get(
            'credentials_path', 
            'config/google_drive/credentials.json'
        )
        token_path_str = self.config.get(
            'token_path',
            'config/google_drive/token_admin.pickle'
        )
        
        if credentials_path_str:
            self.credentials_path = base_path / credentials_path_str
        else:
            self.credentials_path = base_path / 'config/google_drive/credentials.json'
            
        if token_path_str:
            # If absolute path or starts with /tmp, use as-is
            if token_path_str.startswith('/'):
                self.token_path = Path(token_path_str)
            else:
                self.token_path = base_path / token_path_str
        else:
            # Default to /tmp for Docker compatibility (read-only filesystem)
            self.token_path = Path('/tmp/token_admin.pickle')
        
        self.target_users = self.config.get('target_users', [])
        self.days_to_collect = self.config.get('days_to_collect', 7)
        
        self.service = None
        
        # MongoDB collections
        if mongo_manager:
            self.db = mongo_manager.db
            self.collections = {
                "activities": self.db["drive_activities"],
                "files": self.db["drive_files"],
            }
        else:
            self.db = None
            self.collections = {}
    
    def get_source_name(self) -> str:
        """Return the name of this data source"""
        return "google_drive"
    
    def get_required_config_keys(self) -> List[str]:
        """Return list of required configuration keys"""
        return ['credentials_path', 'token_path']
    
    def get_db_schema(self) -> Dict[str, str]:
        """MongoDB does not use SQL schema"""
        return {}
    
    def authenticate(self) -> bool:
        """
        Authenticate with Google Admin SDK
        
        Returns:
            True if authentication successful, False otherwise
        """
        try:
            creds = None
            
            # Load existing token
            if self.token_path.exists():
                self.logger.info(f"Loading existing token from {self.token_path}")
                with open(self.token_path, 'rb') as token:
                    creds = pickle.load(token)
            
            # Refresh or get new credentials
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    self.logger.info("Refreshing expired token...")
                    creds.refresh(Request())
                else:
                    if not self.credentials_path.exists():
                        self.logger.error(
                            f"credentials.json not found at {self.credentials_path}"
                        )
                        return False
                    
                    self.logger.info("Starting OAuth2 flow...")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_path), 
                        self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                self.logger.info(f"Saving token to {self.token_path}")
                with open(self.token_path, 'wb') as token:
                    pickle.dump(creds, token)
            
            # Build the service
            self.service = build('admin', 'reports_v1', credentials=creds)
            self.logger.info("✅ Google Drive authentication successful")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Authentication failed: {str(e)}")
            return False
    
    def collect_data(
        self, 
        start_date: Optional[datetime] = None, 
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Collect Google Drive activity data
        
        Args:
            start_date: Start of collection period
            end_date: End of collection period
        
        Returns:
            List containing a single dict with all collected data
        """
        if not self.service:
            if not self.authenticate():
                return [{'activities': [], 'folders': []}]
        
        # Calculate date range (always use UTC)
        if not start_date:
            start_date = datetime.now(tz=pytz.UTC) - timedelta(days=self.days_to_collect)
        if not end_date:
            end_date = datetime.now(tz=pytz.UTC)
        
        start_time = start_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        
        self.logger.info(
            f"📅 Collecting Drive activities from {start_date.date()} to {end_date.date()}"
        )
        
        activities = []
        edit_activities = []  # Collect edit events separately for daily summary
        
        # Collect for each target user, or all users if none specified
        users_to_query = self.target_users if self.target_users else ['all']
        
        for user_key in users_to_query:
            self.logger.info(f"🔍 Querying activities for: {user_key}")
            
            try:
                page_token = None
                while True:
                    request_params = {
                        'userKey': user_key,
                        'applicationName': 'drive',
                        'startTime': start_time,
                        'maxResults': 1000
                    }
                    
                    if page_token:
                        request_params['pageToken'] = page_token
                    
                    results = self.service.activities().list(**request_params).execute()
                    
                    if 'items' in results:
                        for item in results['items']:
                            actor_email = item.get('actor', {}).get('email', 'Unknown')
                            timestamp_str = item.get('id', {}).get('time', '')
                            timestamp = self._parse_timestamp(timestamp_str)
                            
                            # Process events
                            events = item.get('events', [])
                            for event in events:
                                event_name = event.get('name', '')
                                
                                # Skip excluded events (noise reduction)
                                if event_name in self.EXCLUDE_EVENTS:
                                    continue
                                
                                doc_info = self._extract_doc_info(event)
                                
                                # For edit events, collect separately for daily summary
                                if event_name == 'edit':
                                    edit_activities.append({
                                        'timestamp': timestamp,
                                        'user_email': actor_email,
                                        'action': self.ACTIVITY_MAP.get(event_name, event_name),
                                        'event_name': event_name,
                                        'doc_title': doc_info['title'],
                                        'doc_type': doc_info['type'],
                                        'doc_id': doc_info['id'],
                                        'raw_event': str(event)
                                    })
                                else:
                                    # Non-edit events are stored as-is
                                    activities.append({
                                        'timestamp': timestamp,
                                        'user_email': actor_email,
                                        'action': self.ACTIVITY_MAP.get(event_name, event_name),
                                        'event_name': event_name,
                                        'doc_title': doc_info['title'],
                                        'doc_type': doc_info['type'],
                                        'doc_id': doc_info['id'],
                                        'raw_event': str(event)
                                    })
                    
                    # Progress
                    total_collected = len(activities) + len(edit_activities)
                    if total_collected % 500 == 0 and total_collected > 0:
                        self.logger.info(f"  Collected {len(activities)} activities + {len(edit_activities)} edit events...")
                    
                    # Next page
                    page_token = results.get('nextPageToken')
                    if not page_token:
                        break
                        
            except Exception as e:
                self.logger.error(f"❌ Error collecting for {user_key}: {str(e)}")
                if "forbidden" in str(e).lower():
                    self.logger.error(
                        "⚠️  Permission error: Ensure you're using a Google Workspace "
                        "Admin account and Admin SDK API is enabled"
                    )
        
        # Summarize edit events by day + user + document
        self.logger.info(f"\n📊 Summarizing {len(edit_activities)} edit events into daily summaries...")
        daily_edit_summaries = self._summarize_edit_events(edit_activities)
        self.logger.info(f"   → Reduced to {len(daily_edit_summaries)} daily edit summaries")
        
        # Combine activities with daily edit summaries
        all_activities = activities + daily_edit_summaries
        
        self.logger.info(f"✅ Final count: {len(all_activities)} Drive activities")
        self.logger.info(f"   - Regular activities: {len(activities)}")
        self.logger.info(f"   - Daily edit summaries: {len(daily_edit_summaries)}")
        
        # Extract folder information from activities
        self.logger.info("\n📁 Extracting folder information from activities...")
        folders = self._extract_folders_from_activities(all_activities)
        
        return [{
            'activities': all_activities,
            'folders': folders,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'user_count': len(users_to_query)
        }]
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse RFC3339 timestamp to datetime"""
        try:
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            return datetime.now(tz=pytz.UTC)
    
    def _summarize_edit_events(self, edit_activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Summarize edit events by day + user + document
        
        Instead of storing individual edit events, we group them into daily summaries:
        "user@example.com edited 'Document Title' 10 times on 2025-12-05"
        
        Args:
            edit_activities: List of individual edit events
            
        Returns:
            List of daily edit summaries
        """
        from collections import defaultdict
        
        # Group by: date + user_email + doc_id
        daily_edits = defaultdict(lambda: {
            'count': 0,
            'first_edit': None,
            'last_edit': None,
            'doc_title': '',
            'doc_type': '',
            'doc_id': '',
            'user_email': ''
        })
        
        for activity in edit_activities:
            timestamp = activity['timestamp']
            date_key = timestamp.strftime('%Y-%m-%d')
            user_email = activity['user_email']
            doc_id = activity['doc_id']
            
            summary_key = f"{date_key}_{user_email}_{doc_id}"
            
            summary = daily_edits[summary_key]
            summary['count'] += 1
            summary['doc_title'] = activity['doc_title']
            summary['doc_type'] = activity['doc_type']
            summary['doc_id'] = doc_id
            summary['user_email'] = user_email
            
            if summary['first_edit'] is None or timestamp < summary['first_edit']:
                summary['first_edit'] = timestamp
            if summary['last_edit'] is None or timestamp > summary['last_edit']:
                summary['last_edit'] = timestamp
        
        # Convert to activity format
        summaries = []
        for key, summary in daily_edits.items():
            date_str = key.split('_')[0]
            
            # Create a summarized activity
            summaries.append({
                'timestamp': summary['last_edit'],  # Use last edit time for sorting
                'user_email': summary['user_email'],
                'action': f"편집 ({summary['count']}회)",  # "편집 (10회)"
                'event_name': 'edit_summary',  # Mark as summary
                'doc_title': summary['doc_title'],
                'doc_type': summary['doc_type'],
                'doc_id': summary['doc_id'],
                'raw_event': f"Daily edit summary: {summary['count']} edits from {summary['first_edit']} to {summary['last_edit']}",
                'edit_count': summary['count'],
                'first_edit': summary['first_edit'],
                'last_edit': summary['last_edit'],
                'summary_date': date_str
            })
        
        return summaries
    
    def _extract_doc_info(self, event: Dict[str, Any]) -> Dict[str, str]:
        """Extract document information from event"""
        parameters = event.get('parameters', [])
        
        doc_title = 'Unknown'
        doc_type = 'file'
        doc_id = 'Unknown'
        
        for param in parameters:
            name = param.get('name', '')
            value = param.get('value', '')
            
            if name == 'doc_title':
                doc_title = value
            elif name == 'doc_type':
                doc_type = value
            elif name == 'doc_id':
                doc_id = value
        
        doc_type_kr = self.DOC_TYPE_MAP.get(doc_type, doc_type)
        
        return {
            'title': doc_title,
            'type': doc_type_kr,
            'id': doc_id
        }
    
    def _extract_folders_from_activities(self, activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract unique folder information from activity logs
        """
        folders_dict = {}
        
        for activity in activities:
            if activity.get('doc_type') != '폴더':
                continue
            
            folder_id = activity.get('doc_id')
            folder_name = activity.get('doc_title')
            
            if not folder_id or not folder_name:
                continue
            
            if folder_id not in folders_dict:
                folders_dict[folder_id] = {
                    'folder_id': folder_id,
                    'folder_name': folder_name,
                    'parent_id': None,
                    'project_key': None,
                    'created_by': activity['user_email'],
                    'created_time': activity['timestamp'],
                    'modified_time': activity['timestamp'],
                    'members': set()
                }
            else:
                folder = folders_dict[folder_id]
                if activity['timestamp'] > folder['modified_time']:
                    folder['modified_time'] = activity['timestamp']
            
            # Track members
            user_email = activity['user_email']
            if '@tokamak.network' in user_email:
                folders_dict[folder_id]['members'].add(user_email)
        
        # Convert to list and format members
        folders = []
        for folder in folders_dict.values():
            folder['members'] = [
                {'email': email, 'role': 'user', 'permission_id': None}
                for email in sorted(folder['members'])
            ]
            folders.append(folder)
        
        self.logger.info(f"✅ Extracted {len(folders)} unique folders from activities")
        return folders
    
    async def save_data(self, collected_data: Dict[str, Any]):
        """Save collected Google Drive data to MongoDB"""
        print("\n8️⃣ Saving to MongoDB...")
        
        # Save activities
        activities_to_save = []
        import hashlib
        
        for activity in collected_data.get('activities', []):
            # Generate unique activity_id using hash of raw_event
            # This ensures each unique activity (even with same timestamp/user/doc) gets a unique ID
            raw_event_str = activity.get('raw_event', '')
            activity_hash = hashlib.md5(raw_event_str.encode()).hexdigest()[:16]
            activity_id = f"{activity['timestamp'].isoformat()}_{activity_hash}"
            
            activity_doc = {
                'activity_id': activity_id,
                'timestamp': activity['timestamp'],
                'user_email': activity['user_email'],
                'action': activity['action'],
                'event_name': activity['event_name'],
                'doc_title': activity['doc_title'],
                'doc_type': activity['doc_type'],
                'doc_id': activity['doc_id'],
                'raw_event': raw_event_str,
                'collected_at': datetime.utcnow()
            }
            
            # Add edit summary fields if present
            if activity.get('edit_count'):
                activity_doc['edit_count'] = activity['edit_count']
                activity_doc['first_edit'] = activity.get('first_edit')
                activity_doc['last_edit'] = activity.get('last_edit')
                activity_doc['summary_date'] = activity.get('summary_date')
            
            activities_to_save.append(activity_doc)
        
        if activities_to_save:
            try:
                # Save in batches to avoid timeout with large datasets
                batch_size = 1000
                total = len(activities_to_save)
                saved_count = 0
                
                for i in range(0, total, batch_size):
                    batch = activities_to_save[i:i+batch_size]
                    try:
                        self.collections["activities"].insert_many(batch, ordered=False)
                        saved_count += len(batch)
                        if (i + batch_size) % 10000 == 0:
                            print(f"   📊 Progress: {saved_count}/{total} activities saved...")
                    except DuplicateKeyError:
                        # Some documents already exist, continue
                        pass
                
                print(f"   ✅ Saved {saved_count} activities")
            except Exception as e:
                print(f"   ❌ Error saving activities: {e}")
        
        # Save folders
        folders_to_save = []
        for folder in collected_data.get('folders', []):
            folder_doc = {
                'folder_id': folder['folder_id'],
                'folder_name': folder['folder_name'],
                'parent_id': folder.get('parent_id'),
                'project_key': folder.get('project_key'),
                'created_by': folder['created_by'],
                'created_time': folder['created_time'],
                'modified_time': folder['modified_time'],
                'members': folder.get('members', []),
                'collected_at': datetime.utcnow()
            }
            folders_to_save.append(folder_doc)
        
        if folders_to_save:
            try:
                # Save folders/files in batches
                saved_count = 0
                for folder_doc in folders_to_save:
                    try:
                        self.collections["files"].replace_one(
                            {'file_id': folder_doc['folder_id']},  # Use file_id for consistency
                            {
                                'file_id': folder_doc['folder_id'],
                                'name': folder_doc['folder_name'],
                                'owner': folder_doc['created_by'],
                                'mime_type': 'application/vnd.google-apps.folder',
                                'created_time': folder_doc['created_time'],
                                'modified_time': folder_doc['modified_time'],
                                'parents': [folder_doc.get('parent_id')] if folder_doc.get('parent_id') else [],
                                'permissions': folder_doc.get('members', []),
                                'collected_at': datetime.utcnow()
                            },
                            upsert=True
                        )
                        saved_count += 1
                    except Exception:
                        # Skip if error on individual folder
                        pass
                
                print(f"   ✅ Saved {saved_count} folders/files")
            except Exception as e:
                print(f"   ❌ Error saving folders: {e}")
    
    def get_member_mapping(self) -> Dict[str, str]:
        """
        Map Google email addresses to member names
        """
        member_list = self.config.get('member_list', [])
        mapping = {}
        
        for member in member_list:
            google_email = member.get('googleEmail') or member.get('email')
            name = member.get('name')
            
            if google_email and name and '@tokamak.network' in google_email.lower():
                mapping[google_email.lower()] = name
        
        return mapping
    
    def get_member_details(self) -> Dict[str, Dict[str, str]]:
        """Get detailed member information"""
        member_list = self.config.get('member_list', [])
        details = {}
        
        for member in member_list:
            name = member.get('name')
            email = member.get('email')
            google_email = member.get('googleEmail', email)
            
            if name:
                details[name] = {
                    'email': email,
                    'google_email': google_email
                }
        
        return details
    
    def extract_member_activities(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract member activities from collected data"""
        activities = []
        
        for activity in data.get('activities', []):
            user_email = activity.get('user_email', '').lower()
            
            if '@tokamak.network' not in user_email:
                continue
            
            timestamp = activity['timestamp']
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            
            activities.append({
                'member_identifier': user_email,
                'activity_type': 'drive_activity',
                'timestamp': timestamp,
                'activity_id': f"drive:{activity['event_name']}:{activity['doc_id']}:{timestamp.isoformat()}",
                'metadata': {
                    'action': activity['action'],
                    'event_name': activity['event_name'],
                    'doc_title': activity['doc_title'],
                    'doc_type': activity['doc_type'],
                    'doc_id': activity['doc_id']
                }
            })
        
        return activities

