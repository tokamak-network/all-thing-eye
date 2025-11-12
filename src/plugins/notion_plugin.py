"""
Notion Plugin for All-Thing-Eye

Collects activity data from Notion workspace including:
- Pages (created, edited, viewed)
- Databases and their entries
- Comments and mentions
- User activities
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from notion_client import Client
from notion_client.errors import APIResponseError

from src.plugins.base import DataSourcePlugin
from src.utils.logger import get_logger


class NotionPlugin(DataSourcePlugin):
    """Plugin for collecting Notion workspace activity data"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Notion plugin
        
        Args:
            config: Plugin configuration including:
                - token: Notion Integration Token
                - workspace_id: Workspace ID (optional)
                - days_to_collect: Number of days to collect (default: 7)
        """
        self.config = config if config else {}
        self.token = self.config.get('token', '')
        self.workspace_id = self.config.get('workspace_id')
        self.days_to_collect = self.config.get('days_to_collect', 7)
        
        self.client = None
        self.logger = get_logger(__name__)
    
    def get_source_name(self) -> str:
        """Return the name of this data source"""
        return "notion"
    
    def get_required_config_keys(self) -> List[str]:
        """Return list of required configuration keys"""
        return ['token']
    
    def authenticate(self) -> bool:
        """
        Authenticate with Notion API
        
        Returns:
            True if authentication successful, False otherwise
        """
        try:
            if not self.token:
                self.logger.error("Notion token not provided")
                return False
            
            self.client = Client(auth=self.token)
            
            # Test connection by getting current user
            response = self.client.users.me()
            self.logger.info(f"✅ Notion authentication successful: {response.get('name', 'Unknown')}")
            
            return True
            
        except APIResponseError as e:
            self.logger.error(f"❌ Notion authentication failed: {e.message}")
            return False
        except Exception as e:
            self.logger.error(f"❌ Unexpected error during authentication: {str(e)}")
            return False
    
    def collect_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Collect data from Notion workspace
        
        Args:
            start_date: Start date for collection
            end_date: End date for collection
            
        Returns:
            Dictionary containing collected data
        """
        if not self.client:
            if not self.authenticate():
                return {
                    'users': [],
                    'pages': [],
                    'databases': [],
                    'comments': []
                }
        
        # Calculate date range
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=self.days_to_collect)
        
        self.logger.info(f"\n📊 Collecting Notion data")
        self.logger.info(f"   Period: {start_date.isoformat()} ~ {end_date.isoformat()}")
        
        try:
            # Step 1: Fetch users
            self.logger.info("\n1️⃣ Fetching users...")
            users = self._fetch_users()
            self.logger.info(f"   ✅ Found {len(users)} users")
            
            # Step 2: Search for pages
            self.logger.info("\n2️⃣ Searching pages...")
            pages = self._search_pages(start_date)
            self.logger.info(f"   ✅ Found {len(pages)} pages")
            
            # Step 3: Fetch databases
            self.logger.info("\n3️⃣ Fetching databases...")
            databases = self._fetch_databases(start_date)
            self.logger.info(f"   ✅ Found {len(databases)} databases")
            
            # Step 4: Fetch comments (from pages)
            self.logger.info("\n4️⃣ Fetching comments...")
            comments = self._fetch_comments(pages)
            self.logger.info(f"   ✅ Found {len(comments)} comments")
            
            self.logger.info(f"\n📊 Collection Results:")
            self.logger.info(f"   Users: {len(users)}")
            self.logger.info(f"   Pages: {len(pages)}")
            self.logger.info(f"   Databases: {len(databases)}")
            self.logger.info(f"   Comments: {len(comments)}")
            
            return {
                'users': users,
                'pages': pages,
                'databases': databases,
                'comments': comments,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error collecting Notion data: {e}")
            raise
    
    def _fetch_users(self) -> List[Dict[str, Any]]:
        """Fetch all users in the workspace"""
        users = []
        
        try:
            response = self.client.users.list()
            
            for user in response.get('results', []):
                user_data = {
                    'id': user['id'],
                    'name': user.get('name', ''),
                    'email': user.get('email', ''),  # May be None for guests
                    'type': user.get('type', ''),  # person or bot
                    'avatar_url': user.get('avatar_url', '')
                }
                users.append(user_data)
            
            return users
            
        except APIResponseError as e:
            self.logger.warning(f"⚠️  Error fetching users: {e.message}")
            return []
    
    def _search_pages(self, start_date: datetime) -> List[Dict[str, Any]]:
        """Search for pages updated after start_date"""
        pages = []
        
        try:
            # Search with filter for recently edited pages
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
                    # Check if page was edited after start_date
                    last_edited = datetime.fromisoformat(
                        page['last_edited_time'].replace('Z', '+00:00')
                    )
                    
                    if last_edited < start_date:
                        has_more = False
                        break
                    
                    # Extract page data
                    page_data = {
                        'id': page['id'],
                        'created_time': page.get('created_time'),
                        'last_edited_time': page.get('last_edited_time'),
                        'created_by': page.get('created_by', {}).get('id'),
                        'last_edited_by': page.get('last_edited_by', {}).get('id'),
                        'archived': page.get('archived', False),
                        'url': page.get('url', ''),
                        'parent_type': page.get('parent', {}).get('type'),
                        'parent_id': self._get_parent_id(page.get('parent', {}))
                    }
                    
                    # Extract title from properties
                    title = self._extract_title(page.get('properties', {}))
                    page_data['title'] = title
                    
                    pages.append(page_data)
                
                has_more = response.get('has_more', False) and has_more
                next_cursor = response.get('next_cursor')
            
            return pages
            
        except APIResponseError as e:
            self.logger.warning(f"⚠️  Error searching pages: {e.message}")
            return []
    
    def _fetch_databases(self, start_date: datetime) -> List[Dict[str, Any]]:
        """Search for databases updated after start_date"""
        databases = []
        
        try:
            query = {
                "filter": {
                    "value": "database",
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
                
                for db in response.get('results', []):
                    last_edited = datetime.fromisoformat(
                        db['last_edited_time'].replace('Z', '+00:00')
                    )
                    
                    if last_edited < start_date:
                        has_more = False
                        break
                    
                    db_data = {
                        'id': db['id'],
                        'created_time': db.get('created_time'),
                        'last_edited_time': db.get('last_edited_time'),
                        'created_by': db.get('created_by', {}).get('id'),
                        'last_edited_by': db.get('last_edited_by', {}).get('id'),
                        'archived': db.get('archived', False),
                        'url': db.get('url', '')
                    }
                    
                    # Extract title
                    title = self._extract_title(db.get('properties', {}))
                    db_data['title'] = title
                    
                    databases.append(db_data)
                
                has_more = response.get('has_more', False) and has_more
                next_cursor = response.get('next_cursor')
            
            return databases
            
        except APIResponseError as e:
            self.logger.warning(f"⚠️  Error fetching databases: {e.message}")
            return []
    
    def _fetch_comments(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fetch comments from pages"""
        all_comments = []
        
        # Limit to first 50 pages to avoid rate limiting
        for page in pages[:50]:
            try:
                page_id = page['id']
                
                response = self.client.comments.list(block_id=page_id)
                
                for comment in response.get('results', []):
                    comment_data = {
                        'id': comment['id'],
                        'page_id': page_id,
                        'created_time': comment.get('created_time'),
                        'last_edited_time': comment.get('last_edited_time'),
                        'created_by': comment.get('created_by', {}).get('id'),
                        'rich_text': self._extract_rich_text(comment.get('rich_text', []))
                    }
                    all_comments.append(comment_data)
                    
            except APIResponseError as e:
                # Some pages may not support comments
                continue
        
        return all_comments
    
    def _get_parent_id(self, parent: Dict[str, Any]) -> Optional[str]:
        """Extract parent ID from parent object"""
        parent_type = parent.get('type')
        if parent_type == 'page_id':
            return parent.get('page_id')
        elif parent_type == 'database_id':
            return parent.get('database_id')
        elif parent_type == 'workspace':
            return 'workspace'
        return None
    
    def _extract_title(self, properties: Dict[str, Any]) -> str:
        """Extract title from page/database properties"""
        for prop_name, prop_value in properties.items():
            if prop_value.get('type') == 'title':
                title_array = prop_value.get('title', [])
                if title_array:
                    return ''.join([t.get('plain_text', '') for t in title_array])
        return 'Untitled'
    
    def _extract_rich_text(self, rich_text: List[Dict[str, Any]]) -> str:
        """Extract plain text from rich text array"""
        return ''.join([rt.get('plain_text', '') for rt in rich_text])
    
    def get_member_mapping(self) -> Dict[str, str]:
        """
        Map Notion user IDs to member names
        
        Returns:
            Dictionary mapping Notion user ID to member name
        """
        member_list = self.config.get('member_list', [])
        
        mapping = {}
        for member in member_list:
            notion_id = member.get('notionId') or member.get('email')
            if notion_id:
                mapping[notion_id] = member['name']
        
        return mapping
    
    def get_member_details(self) -> Dict[str, Dict[str, str]]:
        """
        Get detailed member information
        
        Returns:
            Dictionary mapping member name to details (email, notion_id)
        """
        member_list = self.config.get('member_list', [])
        
        details = {}
        for member in member_list:
            details[member['name']] = {
                'email': member.get('email', ''),
                'notion_id': member.get('notionId', '')
            }
        
        return details
    
    def extract_member_activities(
        self,
        notion_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract member activities from collected Notion data
        
        Args:
            notion_data: Dictionary containing collected data
            
        Returns:
            List of activity dictionaries
        """
        activities = []
        member_mapping = self.get_member_mapping()
        
        # Extract page creation/edit activities
        for page in notion_data.get('pages', []):
            # Page creation
            if page.get('created_by'):
                created_by_id = page['created_by']
                if created_by_id in member_mapping:
                    activities.append({
                        'member_identifier': created_by_id,
                        'activity_type': 'page_created',
                        'timestamp': datetime.fromisoformat(
                            page['created_time'].replace('Z', '+00:00')
                        ),
                        'activity_id': f"notion:page_created:{page['id']}",
                        'metadata': {
                            'page_id': page['id'],
                            'title': page.get('title', 'Untitled'),
                            'url': page.get('url', '')
                        }
                    })
            
            # Page edit
            if page.get('last_edited_by'):
                edited_by_id = page['last_edited_by']
                if edited_by_id in member_mapping:
                    activities.append({
                        'member_identifier': edited_by_id,
                        'activity_type': 'page_edited',
                        'timestamp': datetime.fromisoformat(
                            page['last_edited_time'].replace('Z', '+00:00')
                        ),
                        'activity_id': f"notion:page_edited:{page['id']}:{page['last_edited_time']}",
                        'metadata': {
                            'page_id': page['id'],
                            'title': page.get('title', 'Untitled'),
                            'url': page.get('url', '')
                        }
                    })
        
        # Extract database activities
        for db in notion_data.get('databases', []):
            if db.get('created_by'):
                created_by_id = db['created_by']
                if created_by_id in member_mapping:
                    activities.append({
                        'member_identifier': created_by_id,
                        'activity_type': 'database_created',
                        'timestamp': datetime.fromisoformat(
                            db['created_time'].replace('Z', '+00:00')
                        ),
                        'activity_id': f"notion:database_created:{db['id']}",
                        'metadata': {
                            'database_id': db['id'],
                            'title': db.get('title', 'Untitled'),
                            'url': db.get('url', '')
                        }
                    })
        
        # Extract comment activities
        for comment in notion_data.get('comments', []):
            if comment.get('created_by'):
                created_by_id = comment['created_by']
                if created_by_id in member_mapping:
                    activities.append({
                        'member_identifier': created_by_id,
                        'activity_type': 'comment_added',
                        'timestamp': datetime.fromisoformat(
                            comment['created_time'].replace('Z', '+00:00')
                        ),
                        'activity_id': f"notion:comment:{comment['id']}",
                        'metadata': {
                            'comment_id': comment['id'],
                            'page_id': comment.get('page_id'),
                            'text': comment.get('rich_text', '')[:200]  # First 200 chars
                        }
                    })
        
        return activities
    
    def get_db_schema(self) -> Dict[str, str]:
        """
        Get database schema for Notion data
        
        Returns:
            Dictionary mapping table names to CREATE TABLE statements
        """
        return {
            'notion_users': '''
                CREATE TABLE IF NOT EXISTS notion_users (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    email TEXT,
                    type TEXT,
                    avatar_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'notion_pages': '''
                CREATE TABLE IF NOT EXISTS notion_pages (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    created_time TIMESTAMP,
                    last_edited_time TIMESTAMP,
                    created_by TEXT,
                    last_edited_by TEXT,
                    archived BOOLEAN DEFAULT 0,
                    url TEXT,
                    parent_type TEXT,
                    parent_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (created_by) REFERENCES notion_users(id),
                    FOREIGN KEY (last_edited_by) REFERENCES notion_users(id)
                )
            ''',
            'notion_databases': '''
                CREATE TABLE IF NOT EXISTS notion_databases (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    created_time TIMESTAMP,
                    last_edited_time TIMESTAMP,
                    created_by TEXT,
                    last_edited_by TEXT,
                    archived BOOLEAN DEFAULT 0,
                    url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (created_by) REFERENCES notion_users(id),
                    FOREIGN KEY (last_edited_by) REFERENCES notion_users(id)
                )
            ''',
            'notion_comments': '''
                CREATE TABLE IF NOT EXISTS notion_comments (
                    id TEXT PRIMARY KEY,
                    page_id TEXT,
                    created_time TIMESTAMP,
                    last_edited_time TIMESTAMP,
                    created_by TEXT,
                    rich_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (page_id) REFERENCES notion_pages(id),
                    FOREIGN KEY (created_by) REFERENCES notion_users(id)
                )
            '''
        }

