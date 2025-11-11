"""
Slack Data Collection Plugin

Collects team communication data from Slack including:
- Messages from channels
- Thread conversations
- Reactions
- Shared links (GitHub, Notion, Google Drive)
- File metadata
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import re
import os
import ssl
import certifi
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from .base import DataSourcePlugin


class SlackPlugin(DataSourcePlugin):
    """Plugin for collecting data from Slack"""
    
    # Link classification patterns
    LINK_PATTERNS = {
        'github_pr': r'https://github\.com/([^/]+/[^/]+)/pull/(\d+)',
        'github_issue': r'https://github\.com/([^/]+/[^/]+)/issues/(\d+)',
        'github_commit': r'https://github\.com/([^/]+/[^/]+)/commit/([a-f0-9]{7,40})',
        'github_repo': r'https://github\.com/([^/]+/[^/]+)(?:/|$)',
        'github_discussion': r'https://github\.com/([^/]+/[^/]+)/discussions/(\d+)',
        'gdrive_doc': r'https://docs\.google\.com/document/d/([^/]+)',
        'gdrive_sheet': r'https://docs\.google\.com/spreadsheets/d/([^/]+)',
        'gdrive_slide': r'https://docs\.google\.com/presentation/d/([^/]+)',
        'gdrive_folder': r'https://drive\.google\.com/drive/folders/([^/]+)',
        'notion_page': r'https://(?:www\.)?notion\.so/(?:[^/]+/)?([a-f0-9]{32})',
        'notion_database': r'https://(?:www\.)?notion\.so/(?:[^/]+/)?([a-f0-9]{32})\?v=',
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Slack plugin
        
        Args:
            config: Plugin configuration
        """
        super().__init__(config)
        self.token = os.getenv('SLACK_BOT_TOKEN')
        self.workspace = config.get('workspace', 'tokamak-network')
        self.target_channels = config.get('target_channels', [])
        self.include_threads = config.get('include_threads', True)
        self.include_reactions = config.get('include_reactions', True)
        self.include_files = config.get('include_files', True)
        self.member_list = config.get('member_list', [])
        
        self.client = None
        self.user_email_map = {}  # Slack user ID -> email mapping
        
    def get_source_name(self) -> str:
        """Get data source name"""
        return "slack"
    
    def get_required_config_keys(self) -> List[str]:
        """Get list of required configuration keys"""
        return ['workspace']  # token is from env, workspace is from config
    
    def get_db_schema(self) -> Dict[str, str]:
        """Define database schema for Slack data"""
        return {
            'slack_channels': '''
                CREATE TABLE IF NOT EXISTS slack_channels (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    is_private BOOLEAN DEFAULT 0,
                    is_archived BOOLEAN DEFAULT 0,
                    member_count INTEGER DEFAULT 0,
                    topic TEXT,
                    purpose TEXT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'slack_users': '''
                CREATE TABLE IF NOT EXISTS slack_users (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    real_name TEXT,
                    email TEXT,
                    is_bot BOOLEAN DEFAULT 0,
                    is_deleted BOOLEAN DEFAULT 0,
                    timezone TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'slack_messages': '''
                CREATE TABLE IF NOT EXISTS slack_messages (
                    ts TEXT PRIMARY KEY,
                    channel_id TEXT NOT NULL,
                    user_id TEXT,
                    text TEXT,
                    thread_ts TEXT,
                    reply_count INTEGER DEFAULT 0,
                    reply_users_count INTEGER DEFAULT 0,
                    is_thread_parent BOOLEAN DEFAULT 0,
                    has_links BOOLEAN DEFAULT 0,
                    has_files BOOLEAN DEFAULT 0,
                    posted_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (channel_id) REFERENCES slack_channels(id),
                    FOREIGN KEY (thread_ts) REFERENCES slack_messages(ts)
                )
            ''',
            'slack_reactions': '''
                CREATE TABLE IF NOT EXISTS slack_reactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_ts TEXT NOT NULL,
                    emoji TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (message_ts) REFERENCES slack_messages(ts),
                    UNIQUE(message_ts, emoji, user_id)
                )
            ''',
            'slack_links': '''
                CREATE TABLE IF NOT EXISTS slack_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_ts TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    link_type TEXT,
                    resource_id TEXT,
                    repository_name TEXT,
                    shared_by_user_id TEXT,
                    shared_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (message_ts) REFERENCES slack_messages(ts),
                    FOREIGN KEY (channel_id) REFERENCES slack_channels(id)
                )
            ''',
            'slack_files': '''
                CREATE TABLE IF NOT EXISTS slack_files (
                    id TEXT PRIMARY KEY,
                    message_ts TEXT,
                    channel_id TEXT NOT NULL,
                    name TEXT,
                    title TEXT,
                    filetype TEXT,
                    size INTEGER,
                    url_private TEXT,
                    uploaded_by_user_id TEXT,
                    uploaded_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (message_ts) REFERENCES slack_messages(ts),
                    FOREIGN KEY (channel_id) REFERENCES slack_channels(id)
                )
            '''
        }
    
    def authenticate(self) -> bool:
        """Authenticate with Slack API"""
        if not self.token:
            print(f"❌ Slack token not provided")
            return False
        
        try:
            # Create SSL context with certifi certificates
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            
            # Initialize Slack client with SSL context
            self.client = WebClient(token=self.token, ssl=ssl_context)
            
            # Test authentication
            response = self.client.auth_test()
            workspace_name = response['team']
            bot_user_id = response['user_id']
            
            print(f"✅ Slack authentication successful")
            print(f"   Workspace: {workspace_name}")
            print(f"   Bot User ID: {bot_user_id}")
            
            self._authenticated = True
            return True
            
        except SlackApiError as e:
            print(f"❌ Slack authentication failed: {e.response['error']}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error during Slack authentication: {e}")
            return False
    
    def collect_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Collect data from Slack
        
        Args:
            start_date: Start date for collection
            end_date: End date for collection
            
        Returns:
            List of collected data records
        """
        if not self.client:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        
        print(f"\n📊 Collecting Slack data for {self.workspace}")
        if start_date and end_date:
            print(f"   Period: {start_date.isoformat()} ~ {end_date.isoformat()}")
        
        try:
            # Convert datetime to Slack timestamps
            oldest = str(start_date.timestamp()) if start_date else "0"
            latest = str(end_date.timestamp()) if end_date else str(datetime.now().timestamp())
            
            # Step 1: Fetch and store users
            print("\n1️⃣ Fetching users...")
            users = self._fetch_users()
            print(f"   ✅ Found {len(users)} users")
            
            # Step 2: Fetch channels
            print("\n2️⃣ Fetching channels...")
            channels = self._fetch_channels()
            print(f"   ✅ Found {len(channels)} channels")
            
            # Filter channels if target_channels specified
            if self.target_channels:
                channels = [c for c in channels if c['name'] in self.target_channels]
                print(f"   🔍 Filtered to {len(channels)} target channels")
            
            # Step 3: Fetch messages from channels
            print("\n3️⃣ Fetching messages...")
            all_messages = []
            all_reactions = []
            all_links = []
            all_files = []
            
            for idx, channel in enumerate(channels, 1):
                channel_id = channel['id']
                channel_name = channel['name']
                
                print(f"   📂 [{idx}/{len(channels)}] Collecting from #{channel_name}...", end=" ")
                
                messages = self._fetch_channel_messages(channel_id, oldest, latest)
                
                if messages:
                    # Extract reactions, links, and files from messages
                    for msg in messages:
                        # Extract reactions
                        if self.include_reactions and 'reactions' in msg:
                            reactions = self._extract_reactions(msg)
                            all_reactions.extend(reactions)
                        
                        # Extract links
                        links = self._extract_links(msg, channel_id)
                        all_links.extend(links)
                        
                        # Extract files
                        if self.include_files and 'files' in msg:
                            files = self._extract_files(msg, channel_id)
                            all_files.extend(files)
                    
                    all_messages.extend(messages)
                    print(f"✅ {len(messages)} messages")
                else:
                    print("- no messages")
            
            print(f"\n📊 Collection Results:")
            print(f"   Users: {len(users)}")
            print(f"   Channels: {len(channels)}")
            print(f"   Messages: {len(all_messages)}")
            print(f"   Reactions: {len(all_reactions)}")
            print(f"   Links: {len(all_links)}")
            print(f"   Files: {len(all_files)}")
            
            return {
                'users': users,
                'channels': channels,
                'messages': all_messages,
                'reactions': all_reactions,
                'links': all_links,
                'files': all_files
            }
            
        except Exception as e:
            print(f"❌ Error collecting Slack data: {e}")
            raise
    
    def _fetch_users(self) -> List[Dict[str, Any]]:
        """Fetch all users in the workspace"""
        users = []
        cursor = None
        
        while True:
            try:
                response = self.client.users_list(cursor=cursor, limit=200)
                
                for member in response['members']:
                    user_data = {
                        'id': member['id'],
                        'name': member.get('name', ''),
                        'real_name': member.get('real_name', ''),
                        'email': member.get('profile', {}).get('email', ''),
                        'is_bot': member.get('is_bot', False),
                        'is_deleted': member.get('deleted', False),
                        'timezone': member.get('tz', '')
                    }
                    users.append(user_data)
                    
                    # Build email mapping
                    if user_data['email']:
                        self.user_email_map[user_data['id']] = user_data['email']
                
                if not response.get('response_metadata', {}).get('next_cursor'):
                    break
                    
                cursor = response['response_metadata']['next_cursor']
                
            except SlackApiError as e:
                print(f"   ⚠️  Error fetching users: {e.response['error']}")
                break
        
        return users
    
    def _fetch_channels(self) -> List[Dict[str, Any]]:
        """Fetch all channels (public and private)"""
        channels = []
        
        # Fetch public channels
        cursor = None
        while True:
            try:
                response = self.client.conversations_list(
                    types="public_channel",
                    exclude_archived=True,
                    cursor=cursor,
                    limit=200
                )
                
                for channel in response['channels']:
                    channel_data = {
                        'id': channel['id'],
                        'name': channel['name'],
                        'is_private': False,
                        'is_archived': channel.get('is_archived', False),
                        'member_count': channel.get('num_members', 0),
                        'topic': channel.get('topic', {}).get('value', ''),
                        'purpose': channel.get('purpose', {}).get('value', ''),
                        'created_at': datetime.fromtimestamp(channel['created']).isoformat() if 'created' in channel else None
                    }
                    channels.append(channel_data)
                
                if not response.get('response_metadata', {}).get('next_cursor'):
                    break
                    
                cursor = response['response_metadata']['next_cursor']
                
            except SlackApiError as e:
                print(f"   ⚠️  Error fetching public channels: {e.response['error']}")
                break
        
        # Fetch private channels (groups)
        cursor = None
        while True:
            try:
                response = self.client.conversations_list(
                    types="private_channel",
                    exclude_archived=True,
                    cursor=cursor,
                    limit=200
                )
                
                for channel in response['channels']:
                    channel_data = {
                        'id': channel['id'],
                        'name': channel['name'],
                        'is_private': True,
                        'is_archived': channel.get('is_archived', False),
                        'member_count': channel.get('num_members', 0),
                        'topic': channel.get('topic', {}).get('value', ''),
                        'purpose': channel.get('purpose', {}).get('value', ''),
                        'created_at': datetime.fromtimestamp(channel['created']).isoformat() if 'created' in channel else None
                    }
                    channels.append(channel_data)
                
                if not response.get('response_metadata', {}).get('next_cursor'):
                    break
                    
                cursor = response['response_metadata']['next_cursor']
                
            except SlackApiError as e:
                print(f"   ⚠️  Error fetching private channels: {e.response['error']}")
                break
        
        return channels
    
    def _fetch_channel_messages(
        self,
        channel_id: str,
        oldest: str,
        latest: str
    ) -> List[Dict[str, Any]]:
        """Fetch messages from a specific channel"""
        messages = []
        cursor = None
        
        while True:
            try:
                response = self.client.conversations_history(
                    channel=channel_id,
                    oldest=oldest,
                    latest=latest,
                    limit=1000,
                    cursor=cursor
                )
                
                for msg in response['messages']:
                    # Skip bot messages and system messages
                    if msg.get('subtype') in ['bot_message', 'channel_join', 'channel_leave']:
                        continue
                    
                    message_data = {
                        'ts': msg['ts'],
                        'channel_id': channel_id,
                        'user_id': msg.get('user', ''),
                        'text': msg.get('text', ''),
                        'thread_ts': msg.get('thread_ts'),
                        'reply_count': msg.get('reply_count', 0),
                        'reply_users_count': msg.get('reply_users_count', 0),
                        'is_thread_parent': 'thread_ts' in msg and msg.get('ts') == msg.get('thread_ts'),
                        'has_links': bool(re.search(r'https?://[^\s]+', msg.get('text', ''))),
                        'has_files': 'files' in msg,
                        'posted_at': datetime.fromtimestamp(float(msg['ts'])).isoformat(),
                        'reactions': msg.get('reactions', []),
                        'files': msg.get('files', [])
                    }
                    messages.append(message_data)
                    
                    # Fetch thread replies if this is a thread parent
                    if self.include_threads and message_data['is_thread_parent']:
                        thread_messages = self._fetch_thread_replies(
                            channel_id,
                            msg['thread_ts']
                        )
                        messages.extend(thread_messages)
                
                if not response.get('has_more'):
                    break
                    
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break
                
            except SlackApiError as e:
                print(f"\n   ⚠️  Error fetching messages: {e.response['error']}")
                break
        
        return messages
    
    def _fetch_thread_replies(self, channel_id: str, thread_ts: str) -> List[Dict[str, Any]]:
        """Fetch replies in a thread"""
        replies = []
        
        try:
            response = self.client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=1000
            )
            
            for msg in response['messages']:
                # Skip the parent message (already collected)
                if msg['ts'] == thread_ts:
                    continue
                
                if msg.get('subtype') in ['bot_message']:
                    continue
                
                reply_data = {
                    'ts': msg['ts'],
                    'channel_id': channel_id,
                    'user_id': msg.get('user', ''),
                    'text': msg.get('text', ''),
                    'thread_ts': thread_ts,
                    'reply_count': 0,
                    'reply_users_count': 0,
                    'is_thread_parent': False,
                    'has_links': bool(re.search(r'https?://[^\s]+', msg.get('text', ''))),
                    'has_files': 'files' in msg,
                    'posted_at': datetime.fromtimestamp(float(msg['ts'])).isoformat(),
                    'reactions': msg.get('reactions', []),
                    'files': msg.get('files', [])
                }
                replies.append(reply_data)
        
        except SlackApiError as e:
            print(f"\n   ⚠️  Error fetching thread replies: {e.response['error']}")
        
        return replies
    
    def _extract_reactions(self, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract reactions from a message"""
        reactions = []
        
        for reaction in message.get('reactions', []):
            emoji = reaction['name']
            users = reaction.get('users', [])
            
            for user_id in users:
                reaction_data = {
                    'message_ts': message['ts'],
                    'emoji': emoji,
                    'user_id': user_id
                }
                reactions.append(reaction_data)
        
        return reactions
    
    def _extract_links(
        self,
        message: Dict[str, Any],
        channel_id: str
    ) -> List[Dict[str, Any]]:
        """Extract and classify links from message text"""
        links = []
        text = message.get('text', '')
        
        # Find all URLs in text
        url_pattern = r'https?://[^\s<>]+'
        urls = re.findall(url_pattern, text)
        
        for url in urls:
            # Remove Slack's <> wrapper if present
            url = url.strip('<>')
            
            # Classify link
            link_type = 'external'
            resource_id = None
            repository_name = None
            
            for pattern_name, pattern in self.LINK_PATTERNS.items():
                match = re.search(pattern, url)
                if match:
                    link_type = pattern_name
                    
                    if 'github' in pattern_name:
                        repository_name = match.group(1) if len(match.groups()) >= 1 else None
                        resource_id = match.group(2) if len(match.groups()) >= 2 else repository_name
                    else:
                        resource_id = match.group(1) if match.groups() else None
                    
                    break
            
            link_data = {
                'message_ts': message['ts'],
                'channel_id': channel_id,
                'url': url,
                'link_type': link_type,
                'resource_id': resource_id,
                'repository_name': repository_name,
                'shared_by_user_id': message.get('user_id'),
                'shared_at': message['posted_at']
            }
            links.append(link_data)
        
        return links
    
    def _extract_files(
        self,
        message: Dict[str, Any],
        channel_id: str
    ) -> List[Dict[str, Any]]:
        """Extract file metadata from message"""
        files = []
        
        for file_obj in message.get('files', []):
            file_data = {
                'id': file_obj['id'],
                'message_ts': message['ts'],
                'channel_id': channel_id,
                'name': file_obj.get('name', ''),
                'title': file_obj.get('title', ''),
                'filetype': file_obj.get('filetype', ''),
                'size': file_obj.get('size', 0),
                'url_private': file_obj.get('url_private', ''),
                'uploaded_by_user_id': message.get('user_id'),
                'uploaded_at': message['posted_at']
            }
            files.append(file_data)
        
        return files
    
    def get_member_mapping(self) -> Dict[str, str]:
        """
        Map Slack user IDs to member names
        
        Returns:
            Dict of {slack_user_id: member_name}
        """
        mapping = {}
        
        print(f"\n🔍 DEBUG: Building member mapping...")
        print(f"   Total members in config: {len(self.member_list)}")
        print(f"   Total Slack users with email: {len(self.user_email_map)}")
        
        for member in self.member_list:
            slack_id = member.get('slackId') or member.get('slack_id')
            email = member.get('email')
            name = member.get('name')
            
            # Check if slack_id is actually an email address (contains @)
            if slack_id and '@' in slack_id:
                # Treat slack_id as email
                email = slack_id
                slack_id = None
            
            if slack_id and name:
                # Direct slack_id mapping (if provided in members.yaml)
                mapping[slack_id.lower()] = name
                print(f"   ✅ Direct mapping: {name} -> {slack_id}")
            elif email and name:
                # Find Slack user ID by email
                found = False
                for user_id, user_email in self.user_email_map.items():
                    if user_email.lower() == email.lower():
                        mapping[user_id.lower()] = name
                        print(f"   ✅ Email mapping: {name} ({email}) -> {user_id}")
                        found = True
                        break
                
                if not found:
                    print(f"   ⚠️  No match for: {name} ({email})")
        
        print(f"\n   📋 Total mappings created: {len(mapping)}")
        return mapping
    
    def get_member_details(self) -> Dict[str, Dict[str, str]]:
        """
        Get detailed member information
        
        Returns:
            Dict of {member_name: {'email': '...', 'slack_id': '...'}}
        """
        details = {}
        
        for member in self.member_list:
            name = member.get('name')
            email = member.get('email')
            slack_id = member.get('slackId') or member.get('slack_id')
            
            if name:
                details[name] = {
                    'email': email,
                    'slack_id': slack_id
                }
        
        return details
    
    def extract_member_activities(
        self,
        data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract member activities from collected data
        
        Args:
            data: Collected Slack data
            
        Returns:
            List of activity records for member_index
        """
        activities = []
        
        for message in data.get('messages', []):
            user_id = message.get('user_id')
            if not user_id:
                continue
            
            channel_id = message['channel_id']
            ts = message['ts']
            activity = {
                'member_identifier': user_id.lower(),
                'activity_type': 'message',
                'timestamp': datetime.fromisoformat(message['posted_at']),
                'activity_id': f"slack:message:{channel_id}:{ts}",
                'metadata': {
                    'channel_id': channel_id,
                    'message_ts': ts,
                    'text_length': len(message.get('text', '')),
                    'is_thread': bool(message.get('thread_ts')),
                    'has_links': message.get('has_links', False),
                    'has_files': message.get('has_files', False)
                }
            }
            activities.append(activity)
        
        # Add reaction activities
        for reaction in data.get('reactions', []):
            user_id = reaction['user_id'].lower()
            message_ts = reaction['message_ts']
            emoji = reaction['emoji']
            activity = {
                'member_identifier': user_id,
                'activity_type': 'reaction',
                'timestamp': datetime.now(),  # Slack doesn't provide reaction timestamp
                'activity_id': f"slack:reaction:{message_ts}:{emoji}:{user_id}",
                'metadata': {
                    'message_ts': message_ts,
                    'emoji': emoji
                }
            }
            activities.append(activity)
        
        return activities

