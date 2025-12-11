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
import time
from pymongo.errors import DuplicateKeyError

from src.plugins.base import DataSourcePlugin
from src.utils.logger import get_logger
from src.core.mongo_manager import MongoDBManager
from src.models.mongo_models import NotionPage, NotionDatabase, NotionUser, NotionBlock


class NotionPluginMongo(DataSourcePlugin):
    """Plugin for collecting Notion workspace activity data (MongoDB version)"""
    
    def __init__(self, config: Dict[str, Any], mongo_manager=None):
        """
        Initialize Notion plugin
        
        Args:
            config: Plugin configuration including:
                - token: Notion Integration Token
                - workspace_id: Workspace ID (optional)
                - days_to_collect: Number of days to collect (default: 7)
            mongo_manager: MongoDB manager instance
        """
        self.config = config if config else {}
        self.mongo = mongo_manager
        self.token = self.config.get('token', '')
        self.workspace_id = self.config.get('workspace_id')
        self.days_to_collect = self.config.get('days_to_collect', 7)
        
        self.client = None
        self.logger = get_logger(__name__)
        
        # MongoDB collections
        if mongo_manager:
            self.db = mongo_manager.db
            self.collections = {
                "pages": self.db["notion_pages"],
                "databases": self.db["notion_databases"],
                "comments": self.db["notion_comments"],
                "users": self.db["notion_users"],  # Add users collection
            }
        else:
            self.db = None
            self.collections = {}
    
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
            error_msg = str(e) if hasattr(e, '__str__') else getattr(e, 'message', 'Unknown error')
            self.logger.error(f"❌ Notion authentication failed: {error_msg}")
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
            error_msg = str(e) if hasattr(e, '__str__') else getattr(e, 'message', 'Unknown error')
            self.logger.warning(f"⚠️  Error fetching users: {error_msg}")
            return []
    
    def _search_pages(self, start_date: datetime) -> List[Dict[str, Any]]:
        """Search for pages updated after start_date"""
        pages = []
        
        # Ensure start_date is timezone-aware (UTC)
        if start_date.tzinfo is None:
            import pytz
            start_date = start_date.replace(tzinfo=pytz.UTC)
        
        try:
            # Note: Notion API search doesn't support filtering by last_edited_time directly
            # We'll collect all pages and filter by last_edited_time in the loop
            # This ensures all pages are collected regardless of parent hierarchy
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
            pages_collected = 0
            pages_skipped = 0
            
            while has_more:
                if next_cursor:
                    query['start_cursor'] = next_cursor
                
                response = self.client.search(**query)
                
                for page in response.get('results', []):
                    # Skip pages without id
                    page_id = page.get('id')
                    if not page_id:
                        self.logger.warning(f"⚠️  Skipping page without id: {page}")
                        pages_skipped += 1
                        continue
                    
                    last_edited = datetime.fromisoformat(
                        page['last_edited_time'].replace('Z', '+00:00')
                    )
                    
                    # Safety check: skip if somehow older than start_date
                    # (API filter should handle this, but double-check)
                    if last_edited < start_date:
                        pages_skipped += 1
                        continue  # Skip this page but continue processing others
                    
                    # Fetch page content (full text)
                    page_content = self._fetch_page_content(page_id)
                    
                    # Rate limiting: respect Notion API limit (3 req/s)
                    # Increase delay when collecting many pages to avoid rate limits
                    time.sleep(0.5)  # ~2 requests per second (more conservative)
                    
                    page_data = {
                        'id': page_id,
                        'notion_id': page_id,
                        'title': self._extract_title(page.get('properties', {})),
                        'content': page_content,  # Add full content
                        'content_length': len(page_content),  # Add content length for reference
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
                    pages_collected += 1
                
                has_more = response.get('has_more', False) and has_more
                next_cursor = response.get('next_cursor')
            
            if pages_skipped > 0:
                self.logger.info(f"   ⚠️  Skipped {pages_skipped} pages (older than start_date despite API filter)")
            self.logger.info(f"   ✅ Collected {pages_collected} pages")
            
            return pages
            
        except APIResponseError as e:
            error_msg = str(e) if hasattr(e, '__str__') else getattr(e, 'message', 'Unknown error')
            self.logger.warning(f"⚠️  Error searching pages: {error_msg}")
            return []
    
    def _fetch_databases(self, start_date: datetime) -> List[Dict[str, Any]]:
        """Search for databases updated after start_date"""
        databases = []
        
        # Ensure start_date is timezone-aware (UTC)
        if start_date.tzinfo is None:
            import pytz
            start_date = start_date.replace(tzinfo=pytz.UTC)
        
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
                    # Skip databases without id
                    db_id = db.get('id')
                    if not db_id:
                        self.logger.warning(f"⚠️  Skipping database without id: {db}")
                        continue
                    
                    last_edited = datetime.fromisoformat(
                        db['last_edited_time'].replace('Z', '+00:00')
                    )
                    
                    if last_edited < start_date:
                        has_more = False
                        break
                    
                    db_data = {
                        'id': db_id,
                        'notion_id': db_id,
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
            error_msg = str(e) if hasattr(e, '__str__') else getattr(e, 'message', 'Unknown error')
            self.logger.warning(f"⚠️  Error fetching databases: {error_msg}")
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
                
                page['comments'] = comments  # Fixed: use 'comments' instead of 'blocks'
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
    
    def _fetch_page_content(self, page_id: str, max_retries: int = 5) -> str:
        """
        Fetch full content of a Notion page by retrieving all blocks with retry logic
        
        Args:
            page_id: Notion page ID
            max_retries: Maximum number of retry attempts for server errors
            
        Returns:
            Full page content as plain text string
        """
        # Retry logic for fetching blocks
        last_error = None
        for attempt in range(1, max_retries + 1):
            # Reset last_error at the start of each attempt
            attempt_error = None
            try:
                content_parts = []
                has_more = True
                next_cursor = None
                
                while has_more:
                    # Request with pagination
                    try:
                        if next_cursor:
                            response = self.client.blocks.children.list(
                                block_id=page_id,
                                start_cursor=next_cursor,
                                page_size=100  # Max allowed by Notion API
                            )
                        else:
                            response = self.client.blocks.children.list(
                                block_id=page_id,
                                page_size=100
                            )
                    except APIResponseError as e:
                        # Check if it's a server error or rate limit that we should retry
                        status_code = getattr(e, 'status', None)
                        error_msg = str(e) if hasattr(e, '__str__') else getattr(e, 'message', 'Unknown error')
                        attempt_error = f"HTTP {status_code}: {error_msg}"
                        last_error = attempt_error  # Keep for final error message
                        
                        # Retry on 429 (Rate Limit), 502, 503, 504 errors
                        if status_code in [429, 502, 503, 504] and attempt < max_retries:
                            # Break inner while loop, retry outer loop
                            # The retry log will be printed in the outer loop with error info
                            has_more = False  # Exit while loop
                            break
                        else:
                            # Final failure or non-retryable error
                            self.logger.warning(f"⚠️  Could not fetch content for page {page_id}: {attempt_error}")
                            return ""
                    
                    # Process blocks
                    for block in response.get('results', []):
                        block_type = block.get('type')
                        
                        # Extract text from different block types
                        if block_type == 'paragraph':
                            text = self._extract_rich_text(block['paragraph'].get('rich_text', []))
                            if text:
                                content_parts.append(text)
                        
                        elif block_type in ['heading_1', 'heading_2', 'heading_3']:
                            heading = block[block_type]
                            text = self._extract_rich_text(heading.get('rich_text', []))
                            if text:
                                # Add markdown-style heading
                                prefix = '#' * int(block_type[-1])
                                content_parts.append(f"{prefix} {text}")
                        
                        elif block_type == 'bulleted_list_item':
                            text = self._extract_rich_text(block['bulleted_list_item'].get('rich_text', []))
                            if text:
                                content_parts.append(f"• {text}")
                        
                        elif block_type == 'numbered_list_item':
                            text = self._extract_rich_text(block['numbered_list_item'].get('rich_text', []))
                            if text:
                                content_parts.append(f"- {text}")
                        
                        elif block_type == 'quote':
                            text = self._extract_rich_text(block['quote'].get('rich_text', []))
                            if text:
                                content_parts.append(f"> {text}")
                        
                        elif block_type == 'code':
                            text = self._extract_rich_text(block['code'].get('rich_text', []))
                            language = block['code'].get('language', '')
                            if text:
                                content_parts.append(f"```{language}\n{text}\n```")
                        
                        elif block_type == 'toggle':
                            text = self._extract_rich_text(block['toggle'].get('rich_text', []))
                            if text:
                                content_parts.append(text)
                        
                        elif block_type == 'callout':
                            text = self._extract_rich_text(block['callout'].get('rich_text', []))
                            if text:
                                content_parts.append(f"💡 {text}")
                    
                    # Check for more pages
                    has_more = response.get('has_more', False)
                    next_cursor = response.get('next_cursor')
                
                # Successfully fetched all content
                if content_parts:
                    full_content = '\n\n'.join(content_parts)
                    return full_content
                else:
                    # If we broke out of while loop due to retry, continue outer retry loop
                    # Only retry if we have an error (attempt_error is set)
                    if attempt_error and attempt < max_retries:
                        # Check if it's a rate limit error (429) - wait 1 hour
                        if "HTTP 429" in attempt_error:
                            wait_time = 3600  # Wait 1 hour for rate limit reset
                            self.logger.warning(
                                f"⚠️  Notion API rate limit (429) for page {page_id} "
                                f"(attempt {attempt}/{max_retries}). Error: {attempt_error}. Waiting 1 hour (3600s) for rate limit reset..."
                            )
                        else:
                            wait_time = min(2 ** (attempt - 1) * 2, 30)
                            self.logger.warning(
                                f"⚠️  Retrying page {page_id} (attempt {attempt + 1}/{max_retries}) in {wait_time}s - Error: {attempt_error}..."
                            )
                        time.sleep(wait_time)
                        continue
                    elif attempt_error:
                        # Max retries reached
                        self.logger.warning(f"⚠️  Failed to fetch content for page {page_id} after {max_retries} attempts. Last error: {attempt_error}")
                        return ""
                    else:
                        # No content and no error - this shouldn't happen, but handle gracefully
                        return ""
                
            except APIResponseError as e:
                # Handle APIResponseError that wasn't caught in inner try block
                status_code = getattr(e, 'status', None)
                error_msg = str(e) if hasattr(e, '__str__') else getattr(e, 'message', 'Unknown error')
                attempt_error = f"HTTP {status_code}: {error_msg}"
                last_error = attempt_error  # Keep for final error message
                
                # Retry on 429 (Rate Limit), 502, 503, 504 errors
                if status_code in [429, 502, 503, 504] and attempt < max_retries:
                    # For rate limit (429), wait 1 hour
                    if status_code == 429:
                        wait_time = 3600  # Wait 1 hour for rate limit reset
                        self.logger.warning(
                            f"⚠️  Notion API rate limit (429) for page {page_id} "
                            f"(attempt {attempt}/{max_retries}). Error: {attempt_error}. Waiting 1 hour (3600s) for rate limit reset..."
                        )
                    else:
                        wait_time = min(2 ** (attempt - 1) * 2, 30)
                        self.logger.warning(
                            f"⚠️  Notion API {status_code} error for page {page_id} "
                            f"(attempt {attempt}/{max_retries}). Error: {attempt_error}. Retrying in {wait_time}s..."
                        )
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.warning(f"⚠️  Could not fetch content for page {page_id}: {attempt_error}")
                    return ""
            except Exception as e:
                # For other exceptions, only retry if it's a network/server issue
                if attempt < max_retries:
                    wait_time = min(2 ** (attempt - 1) * 2, 30)
                    self.logger.warning(
                        f"⚠️  Unexpected error fetching content for page {page_id} "
                        f"(attempt {attempt}/{max_retries}): {str(e)}. Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.warning(f"⚠️  Unexpected error fetching content for page {page_id}: {str(e)}")
                    return ""
        
        # If all retries exhausted
        self.logger.warning(f"⚠️  Failed to fetch content for page {page_id} after {max_retries} attempts")
        return ""
    
    async def save_data(self, collected_data: Dict[str, Any]):
        """Save collected Notion data to MongoDB"""
        print("\n8️⃣ Saving to MongoDB...")
        
        # Save users first
        users_to_save = []
        user_map = {}  # UUID -> {name, email} for enriching pages
        
        for user in collected_data.get('users', []):
            # Skip users without valid ID
            if not user.get('id'):
                continue
                
            user_doc = {
                'user_id': user['id'],
                'name': user.get('name', ''),
                'email': user.get('email', ''),
                'type': user.get('type', 'person')
            }
            users_to_save.append(user_doc)
            
            # Build map for enriching pages
            user_map[user['id']] = {
                'id': user['id'],
                'name': user.get('name', ''),
                'email': user.get('email', ''),
                'type': user.get('type', 'person')
            }
        
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
        
        # Save pages (enrich with user info)
        pages_to_save = []
        for page in collected_data.get('pages', []):
            # Skip pages without valid notion_id
            if not page.get('notion_id'):
                continue
            
            # Enrich created_by with name and email from user_map
            created_by = page.get('created_by', {})
            created_by_id = created_by.get('id', '')
            if created_by_id in user_map:
                created_by = user_map[created_by_id]
            
            # Enrich last_edited_by with name and email from user_map
            last_edited_by = page.get('last_edited_by', {})
            last_edited_by_id = last_edited_by.get('id', '')
            if last_edited_by_id in user_map:
                last_edited_by = user_map[last_edited_by_id]
                
            page_doc = {
                'id': page.get('id') or page['notion_id'],  # Required for unique index
                'page_id': page['notion_id'],  # Use page_id to match Pydantic model
                'notion_id': page['notion_id'],  # Keep notion_id for compatibility
                'title': page.get('title', ''),
                'content': page.get('content', ''),  # Add full content
                'content_length': page.get('content_length', 0),  # Add content length
                'url': page.get('url', ''),
                'created_time': page['created_time'],
                'last_edited_time': page['last_edited_time'],
                'created_by': created_by,  # Now includes name and email
                'last_edited_by': last_edited_by,  # Now includes name and email
                'parent_type': page.get('parent', {}).get('type'),
                'parent_id': page.get('parent', {}).get('id') if page.get('parent', {}).get('type') != 'workspace' else None,
                'properties': page.get('properties', {}),
                'comments': page.get('comments', []),
                'comments_count': page.get('comments_count', 0),
                'is_archived': page.get('is_archived', False),
                'collected_at': datetime.utcnow()
            }
            pages_to_save.append(page_doc)
        
        if pages_to_save:
            try:
                saved_count = 0
                for page_doc in pages_to_save:
                    result = self.collections["pages"].replace_one(
                        {'page_id': page_doc['page_id']},
                        page_doc,
                        upsert=True
                    )
                    if result.modified_count > 0 or result.upserted_id:
                        saved_count += 1
                print(f"   ✅ Saved/Updated {saved_count} pages")
            except Exception as e:
                print(f"   ❌ Error saving pages: {e}")
        
        # Save databases (enrich with user info)
        dbs_to_save = []
        for db in collected_data.get('databases', []):
            # Skip databases without valid notion_id
            if not db.get('notion_id'):
                continue
            
            # Enrich created_by with name and email from user_map
            created_by = db.get('created_by', {})
            created_by_id = created_by.get('id', '')
            if created_by_id in user_map:
                created_by = user_map[created_by_id]
            
            # Enrich last_edited_by with name and email from user_map
            last_edited_by = db.get('last_edited_by', {})
            last_edited_by_id = last_edited_by.get('id', '')
            if last_edited_by_id in user_map:
                last_edited_by = user_map[last_edited_by_id]
                
            db_doc = {
                'id': db.get('id') or db['notion_id'],  # Required for unique index
                'database_id': db['notion_id'],  # Use database_id to match Pydantic model
                'notion_id': db['notion_id'],  # Keep notion_id for compatibility
                'title': db.get('title', ''),
                'description': db.get('description', ''),
                'url': db.get('url', ''),
                'created_time': db['created_time'],
                'last_edited_time': db['last_edited_time'],
                'created_by': created_by,  # Now includes name and email
                'last_edited_by': last_edited_by,  # Now includes name and email
                'parent_type': db.get('parent', {}).get('type'),
                'parent_id': db.get('parent', {}).get('id') if db.get('parent', {}).get('type') != 'workspace' else None,
                'properties': db.get('properties', {}),
                'is_archived': db.get('is_archived', False),
                'collected_at': datetime.utcnow()
            }
            dbs_to_save.append(db_doc)
        
        if dbs_to_save:
            try:
                saved_count = 0
                for db_doc in dbs_to_save:
                    result = self.collections["databases"].replace_one(
                        {'database_id': db_doc['database_id']},
                        db_doc,
                        upsert=True
                    )
                    if result.modified_count > 0 or result.upserted_id:
                        saved_count += 1
                print(f"   ✅ Saved/Updated {saved_count} databases")
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

