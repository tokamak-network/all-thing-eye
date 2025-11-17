"""
Notion Plugin for All-Thing-Eye (MongoDB Version)

Collects activity data from Notion workspace including:
- Pages (created, edited, viewed)
- Databases and their entries
- Comments (embedded in pages)
- User activities
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from notion_client import Client
from notion_client.errors import APIResponseError
import pytz
from pymongo.errors import DuplicateKeyError

from src.plugins.base import DataSourcePlugin
from src.utils.logger import get_logger
from src.core.mongo_manager import mongo_manager
from src.models.mongo_models import NotionPage, NotionDatabase, NotionUser, NotionBlock


class NotionPluginMongo(DataSourcePlugin):
    """Plugin for collecting Notion workspace activity data (MongoDB version)"""
    
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
        
        # MongoDB collections
        self.db = mongo_manager.get_database_sync()
        self.collections = {
            "pages": self.db[mongo_manager._collections_config["notion_pages"]],
            "databases": self.db[mongo_manager._collections_config["notion_databases"]],
            "users": self.db[mongo_manager._collections_config.get("notion_users", "notion_users")],
        }
    
    def get_source_name(self) -> str:
        """Return the name of this data source"""
        return "notion"
    
    def get_required_config_keys(self) -> List[str]:
        """Return list of required configuration keys"""
        return ['token']
    
    def get_db_schema(self) -> Dict[str, str]:
        """MongoDB does not use SQL schema"""
        return {}
    
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
    ) -> List[Dict[str, Any]]:
        """
        Collect data from Notion workspace
        
        Args:
            start_date: Start date for collection
            end_date: End date for collection
            
        Returns:
            List containing a single dict with all collected data
        """
        if not self.client:
            if not self.authenticate():
                return [{
                    'users': [],
                    'pages': [],
                    'databases': [],
                }]
        
        # Calculate date range
        if not end_date:
            end_date = datetime.now(tz=pytz.UTC)
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
            
            # Step 4: Fetch comments (embedded in pages)
            self.logger.info("\n4️⃣ Fetching comments...")
            pages_with_comments = self._fetch_comments_for_pages(pages)
            self.logger.info(f"   ✅ Enriched pages with comments")
            
            total_comments = sum(pg.get('comments_count', 0) for pg in pages_with_comments)
            
            self.logger.info(f"\n📊 Collection Results:")
            self.logger.info(f"   Users: {len(users)}")
            self.logger.info(f"   Pages: {len(pages_with_comments)}")
            self.logger.info(f"   Databases: {len(databases)}")
            self.logger.info(f"   Comments: {total_comments}")
            
            return [{
                'users': users,
                'pages': pages_with_comments,
                'databases': databases,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }]
            
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
                    'email': user.get('email', ''),
                    'type': user.get('type', ''),
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
                    
                    if last_edited < start_date:
                        has_more = False
                        break
                    
                    page_data = {
                        'notion_id': page['id'],
                        'title': self._extract_title(page.get('properties', {})),
                        'created_time': datetime.fromisoformat(page.get('created_time', '').replace('Z', '+00:00')),
                        'last_edited_time': last_edited,
                        'created_by': self._extract_user_info(page.get('created_by', {})),
                        'last_edited_by': self._extract_user_info(page.get('last_edited_by', {})),
                        'parent': page.get('parent', {}),
                        'properties': page.get('properties', {}),
                        'blocks': [],  # Will be populated with comments
                        'comments_count': 0
                    }
                    
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
                        'notion_id': db['id'],
                        'title': self._extract_title(db.get('properties', {})),
                        'created_time': datetime.fromisoformat(db.get('created_time', '').replace('Z', '+00:00')),
                        'last_edited_time': last_edited,
                        'created_by': self._extract_user_info(db.get('created_by', {})),
                        'last_edited_by': self._extract_user_info(db.get('last_edited_by', {})),
                        'properties': db.get('properties', {})
                    }
                    
                    databases.append(db_data)
                
                has_more = response.get('has_more', False) and has_more
                next_cursor = response.get('next_cursor')
            
            return databases
            
        except APIResponseError as e:
            self.logger.warning(f"⚠️  Error fetching databases: {e.message}")
            return []
    
    def _fetch_comments_for_pages(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fetch comments and embed them in pages"""
        # Limit to first 50 pages to avoid rate limiting
        for page in pages[:50]:
            try:
                page_id = page['notion_id']
                
                response = self.client.comments.list(block_id=page_id)
                
                comments = []
                for comment in response.get('results', []):
                    comment_block = {
                        'type': 'comment',
                        'content': self._extract_rich_text(comment.get('rich_text', [])),
                        'created_time': comment.get('created_time'),
                        'created_by': self._extract_user_info(comment.get('created_by', {}))
                    }
                    comments.append(comment_block)
                
                page['blocks'] = comments
                page['comments_count'] = len(comments)
                    
            except APIResponseError:
                # Some pages may not support comments
                continue
        
        return pages
    
    def _extract_user_info(self, user_obj: Dict[str, Any]) -> Dict[str, str]:
        """Extract user information from Notion user object"""
        return {
            'id': user_obj.get('id', ''),
            'name': user_obj.get('name', ''),
            'email': user_obj.get('email', '')
        }
    
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
    
    async def save_data(self, collected_data: Dict[str, Any]):
        """Save collected Notion data to MongoDB"""
        print("\n8️⃣ Saving to MongoDB...")
        
        # Save users
        users_to_save = []
        for user in collected_data.get('users', []):
            user_doc = {
                'user_id': user['id'],
                'name': user['name'],
                'email': user.get('email', ''),
                'type': user['type']
            }
            users_to_save.append(user_doc)
        
        if users_to_save:
            try:
                for user_doc in users_to_save:
                    self.collections["users"].replace_one(
                        {'user_id': user_doc['user_id']},
                        user_doc,
                        upsert=True
                    )
                print(f"   ✅ Saved {len(users_to_save)} users")
            except Exception as e:
                print(f"   ❌ Error saving users: {e}")
        
        # Save pages
        pages_to_save = []
        for page in collected_data.get('pages', []):
            page_doc = {
                'notion_id': page['notion_id'],
                'title': page['title'],
                'created_time': page['created_time'],
                'last_edited_time': page['last_edited_time'],
                'created_by': page['created_by'],
                'last_edited_by': page['last_edited_by'],
                'parent': page['parent'],
                'properties': page['properties'],
                'blocks': page.get('blocks', []),
                'comments_count': page.get('comments_count', 0),
                'collected_at': datetime.utcnow()
            }
            pages_to_save.append(page_doc)
        
        if pages_to_save:
            try:
                for page_doc in pages_to_save:
                    self.collections["pages"].replace_one(
                        {'notion_id': page_doc['notion_id']},
                        page_doc,
                        upsert=True
                    )
                print(f"   ✅ Saved {len(pages_to_save)} pages")
            except Exception as e:
                print(f"   ❌ Error saving pages: {e}")
        
        # Save databases
        dbs_to_save = []
        for db in collected_data.get('databases', []):
            db_doc = {
                'notion_id': db['notion_id'],
                'title': db['title'],
                'created_time': db['created_time'],
                'last_edited_time': db['last_edited_time'],
                'created_by': db['created_by'],
                'last_edited_by': db['last_edited_by'],
                'properties': db['properties'],
                'collected_at': datetime.utcnow()
            }
            dbs_to_save.append(db_doc)
        
        if dbs_to_save:
            try:
                for db_doc in dbs_to_save:
                    self.collections["databases"].replace_one(
                        {'notion_id': db_doc['notion_id']},
                        db_doc,
                        upsert=True
                    )
                print(f"   ✅ Saved {len(dbs_to_save)} databases")
            except Exception as e:
                print(f"   ❌ Error saving databases: {e}")
    
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
            created_by_info = page.get('created_by', {})
            created_by_id = created_by_info.get('id', '')
            if created_by_id in member_mapping:
                activities.append({
                    'member_identifier': created_by_id,
                    'activity_type': 'page_created',
                    'timestamp': page['created_time'],
                    'activity_id': f"notion:page_created:{page['notion_id']}",
                    'metadata': {
                        'page_id': page['notion_id'],
                        'title': page.get('title', 'Untitled'),
                    }
                })
            
            # Page edit
            edited_by_info = page.get('last_edited_by', {})
            edited_by_id = edited_by_info.get('id', '')
            if edited_by_id in member_mapping:
                activities.append({
                    'member_identifier': edited_by_id,
                    'activity_type': 'page_edited',
                    'timestamp': page['last_edited_time'],
                    'activity_id': f"notion:page_edited:{page['notion_id']}:{page['last_edited_time'].isoformat()}",
                    'metadata': {
                        'page_id': page['notion_id'],
                        'title': page.get('title', 'Untitled'),
                    }
                })
            
            # Comments
            for comment_block in page.get('blocks', []):
                if comment_block.get('type') == 'comment':
                    comment_by_info = comment_block.get('created_by', {})
                    comment_by_id = comment_by_info.get('id', '')
                    if comment_by_id in member_mapping:
                        comment_time = datetime.fromisoformat(
                            comment_block['created_time'].replace('Z', '+00:00')
                        )
                        activities.append({
                            'member_identifier': comment_by_id,
                            'activity_type': 'comment_added',
                            'timestamp': comment_time,
                            'activity_id': f"notion:comment:{page['notion_id']}:{comment_block['created_time']}",
                            'metadata': {
                                'page_id': page['notion_id'],
                                'text': comment_block.get('content', '')[:200]
                            }
                        })
        
        # Extract database activities
        for db in notion_data.get('databases', []):
            created_by_info = db.get('created_by', {})
            created_by_id = created_by_info.get('id', '')
            if created_by_id in member_mapping:
                activities.append({
                    'member_identifier': created_by_id,
                    'activity_type': 'database_created',
                    'timestamp': db['created_time'],
                    'activity_id': f"notion:database_created:{db['notion_id']}",
                    'metadata': {
                        'database_id': db['notion_id'],
                        'title': db.get('title', 'Untitled'),
                    }
                })
        
        return activities

