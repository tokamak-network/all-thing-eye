"""
Google Drive Plugin for All-Thing-Eye

Collects Google Drive activity logs using Admin SDK Reports API.
Requires Google Workspace Admin privileges.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import os
import pickle
from pathlib import Path

from src.plugins.base import DataSourcePlugin
from src.utils.logger import get_logger

# Google API imports (lazy load to avoid import errors if not installed)
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GOOGLE_APIS_AVAILABLE = True
except ImportError:
    GOOGLE_APIS_AVAILABLE = False


class GoogleDrivePlugin(DataSourcePlugin):
    """Plugin for collecting Google Drive activity data via Admin SDK"""
    
    # API Scopes - Admin privileges required
    SCOPES = [
        'https://www.googleapis.com/auth/admin.reports.audit.readonly',
        'https://www.googleapis.com/auth/admin.reports.usage.readonly'
    ]
    
    # Activity type mapping to Korean
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
    
    # Document type mapping to Korean
    DOC_TYPE_MAP = {
        'document': '문서',
        'spreadsheet': '스프레드시트',
        'presentation': '프레젠테이션',
        'folder': '폴더',
        'file': '파일',
        'drawing': '그림',
        'form': '설문지',
        'site': '사이트',
        # Video formats
        'mp4': '동영상(mp4)',
        'mpeg': '동영상(mpeg)',
        'mov': '동영상(mov)',
        'avi': '동영상(avi)',
        'video': '동영상',
        # Image formats
        'png': '이미지(png)',
        'jpeg': '이미지(jpeg)',
        'jpg': '이미지(jpg)',
        # Document formats
        'pdf': 'PDF',
        'txt': '텍스트',
        'msword': 'MS Word',
        'msexcel': 'MS Excel',
        'mspowerpoint': 'MS PowerPoint',
        'html': 'HTML'
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Google Drive plugin
        
        Args:
            config: Plugin configuration containing:
                - credentials_path: Path to credentials.json
                - token_path: Path to token_admin.pickle
                - target_users: List of user emails to track (optional, defaults to all)
                - days_to_collect: Number of days to collect (default: 7)
        """
        if not GOOGLE_APIS_AVAILABLE:
            raise ImportError(
                "Google API libraries not installed. "
                "Install with: pip install google-auth google-auth-oauthlib "
                "google-auth-httplib2 google-api-python-client"
            )
        
        self.config = config or {}
        self.logger = get_logger(__name__)
        
        # Set up paths
        base_path = Path(__file__).parent.parent.parent
        
        # Get paths from config with defaults
        credentials_path_str = self.config.get(
            'credentials_path', 
            'config/google_drive/credentials.json'
        )
        token_path_str = self.config.get(
            'token_path',
            'config/google_drive/token_admin.pickle'
        )
        
        # Convert to Path objects (handle None case)
        if credentials_path_str:
            self.credentials_path = base_path / credentials_path_str
        else:
            self.credentials_path = base_path / 'config/google_drive/credentials.json'
            
        if token_path_str:
            self.token_path = base_path / token_path_str
        else:
            self.token_path = base_path / 'config/google_drive/token_admin.pickle'
        
        self.target_users = self.config.get('target_users', [])
        self.days_to_collect = self.config.get('days_to_collect', 7)
        
        self.service = None  # Admin SDK Reports API
    
    def get_source_name(self) -> str:
        """Return the name of this data source"""
        return "google_drive"
    
    def get_required_config_keys(self) -> List[str]:
        """Return list of required configuration keys"""
        return ['credentials_path', 'token_path']
    
    def get_db_schema(self) -> Dict[str, str]:
        """
        Define database schema for Google Drive data
        
        Returns:
            Dictionary mapping table names to CREATE TABLE statements
        """
        return {
            'drive_activities': '''
                CREATE TABLE IF NOT EXISTS drive_activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    user_email TEXT NOT NULL,
                    action TEXT NOT NULL,
                    event_name TEXT NOT NULL,
                    doc_title TEXT,
                    doc_type TEXT,
                    doc_id TEXT,
                    raw_event TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'drive_documents': '''
                CREATE TABLE IF NOT EXISTS drive_documents (
                    doc_id TEXT PRIMARY KEY,
                    title TEXT,
                    doc_type TEXT,
                    first_seen TIMESTAMP,
                    last_activity TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'drive_folders': '''
                CREATE TABLE IF NOT EXISTS drive_folders (
                    folder_id TEXT PRIMARY KEY,
                    folder_name TEXT NOT NULL,
                    parent_folder_id TEXT,
                    project_key TEXT,
                    is_project_root BOOLEAN DEFAULT 0,
                    created_by TEXT,
                    first_seen TIMESTAMP,
                    last_activity TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (parent_folder_id) REFERENCES drive_folders(folder_id)
                )
            ''',
            'drive_folder_members': '''
                CREATE TABLE IF NOT EXISTS drive_folder_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    folder_id TEXT NOT NULL,
                    user_email TEXT NOT NULL,
                    access_level TEXT,
                    added_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (folder_id) REFERENCES drive_folders(folder_id),
                    UNIQUE(folder_id, user_email)
                )
            '''
        }
    
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
    ) -> Dict[str, Any]:
        """
        Collect Google Drive activity data
        
        Args:
            start_date: Start of collection period (defaults to N days ago)
            end_date: End of collection period (defaults to now)
        
        Returns:
            Dictionary containing collected activities
        """
        if not self.service:
            if not self.authenticate():
                return {'activities': [], 'folders': []}
        
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
                                doc_info = self._extract_doc_info(event)
                                
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
                    if len(activities) % 100 == 0 and len(activities) > 0:
                        self.logger.info(f"  Collected {len(activities)} activities...")
                    
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
        
        self.logger.info(f"✅ Collected {len(activities)} Drive activities")
        
        # Extract folder information from activities
        self.logger.info("\n📁 Extracting folder information from activities...")
        folders = self._extract_folders_from_activities(activities)
        
        return {
            'activities': activities,
            'folders': folders,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'user_count': len(users_to_query)
        }
    
    def get_member_mapping(self) -> Dict[str, str]:
        """
        Map Google email addresses to member names
        
        Only includes @tokamak.network emails (excludes personal Gmail accounts)
        
        Returns:
            Dictionary mapping email to member name
        """
        member_list = self.config.get('member_list', [])
        mapping = {}
        
        for member in member_list:
            # Use googleEmail if available, fallback to email
            google_email = member.get('googleEmail') or member.get('email')
            name = member.get('name')
            
            # Only include @tokamak.network emails
            if google_email and name and '@tokamak.network' in google_email.lower():
                mapping[google_email.lower()] = name
        
        return mapping
    
    def get_member_details(self) -> Dict[str, Dict[str, str]]:
        """
        Get detailed member information
        
        Returns:
            Dictionary mapping member name to details (email, google_email)
        """
        member_list = self.config.get('member_list', [])
        details = {}
        
        for member in member_list:
            name = member.get('name')
            email = member.get('email')
            # Use googleEmail from config (already has fallback to email)
            google_email = member.get('googleEmail', email)
            
            if name:
                details[name] = {
                    'email': email,
                    'google_email': google_email
                }
        
        return details
    
    def extract_member_activities(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract member activities from collected data
        
        Only includes activities from @tokamak.network emails
        
        Args:
            data: Data returned from collect_data()
        
        Returns:
            List of activity records for member_activities table
        """
        activities = []
        
        for activity in data.get('activities', []):
            user_email = activity.get('user_email', '').lower()
            
            # Only include @tokamak.network emails (exclude personal Gmail, etc.)
            if '@tokamak.network' not in user_email:
                continue
            
            activities.append({
                'member_identifier': user_email,
                'activity_type': 'drive_activity',
                'timestamp': activity['timestamp'],
                'activity_id': f"drive:{activity['event_name']}:{activity['doc_id']}:{activity['timestamp'].isoformat()}",
                'metadata': {
                    'action': activity['action'],
                    'event_name': activity['event_name'],
                    'doc_title': activity['doc_title'],
                    'doc_type': activity['doc_type'],
                    'doc_id': activity['doc_id']
                }
            })
        
        return activities
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse RFC3339 timestamp to datetime (always returns timezone-aware UTC)"""
        try:
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            # Fallback to current time in UTC
            return datetime.now(tz=pytz.UTC)
    
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
        
        Args:
            activities: List of activity dictionaries
            
        Returns:
            List of unique folder information
        """
        folders_dict = {}  # Use dict to deduplicate by folder_id
        
        for activity in activities:
            # Only process folder-related activities
            if activity.get('doc_type') != '폴더':
                continue
            
            folder_id = activity.get('doc_id')
            folder_name = activity.get('doc_title')
            
            if not folder_id or not folder_name:
                continue
            
            # First time seeing this folder
            if folder_id not in folders_dict:
                folders_dict[folder_id] = {
                    'folder_id': folder_id,
                    'folder_name': folder_name,
                    'parent_id': None,  # Not available from activity logs
                    'project_key': None,  # Can be set manually or via query later
                    'created_by': activity['user_email'],
                    'created_time': activity['timestamp'].isoformat(),
                    'modified_time': activity['timestamp'].isoformat(),
                    'members': set()  # Use set to avoid duplicates
                }
            else:
                # Update last activity time
                folder = folders_dict[folder_id]
                if activity['timestamp'] > datetime.fromisoformat(folder['modified_time']):
                    folder['modified_time'] = activity['timestamp'].isoformat()
            
            # Track members who accessed this folder
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

