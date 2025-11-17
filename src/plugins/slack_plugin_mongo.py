"""
Slack Data Collection Plugin (MongoDB Version)

Collects team communication data from Slack including:
- Messages from channels
- Thread conversations
- Reactions (embedded in messages)
- Shared links (embedded in messages)
- File metadata (embedded in messages)
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import re
import os
import ssl
import certifi
import pytz
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from pymongo.errors import DuplicateKeyError

from src.plugins.base import DataSourcePlugin
from src.core.mongo_manager import MongoDBManager, get_mongo_manager
from src.models.mongo_models import SlackMessage, SlackChannel, SlackReaction, SlackLink, SlackFile


class SlackPluginMongo(DataSourcePlugin):
    """Plugin for collecting data from Slack (MongoDB version)"""
    
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
    
    def __init__(self, config: Dict[str, Any], mongo_manager: MongoDBManager):
        """
        Initialize Slack plugin
        
        Args:
            config: Plugin configuration
            mongo_manager: MongoDB manager instance
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
        self.user_name_map = {}  # Slack user ID -> name mapping
        self.channel_name_map = {}  # Channel ID -> name mapping
        
        # MongoDB manager and collections
        self.mongo = mongo_manager
        self.db = self.mongo.db
        self.collections = {
            "messages": self.db["slack_messages"],
            "channels": self.db["slack_channels"],
        }
        
    def get_source_name(self) -> str:
        """Get data source name"""
        return "slack"
    
    def get_required_config_keys(self) -> List[str]:
        """Get list of required configuration keys"""
        return ['workspace']
    
    def get_db_schema(self) -> Dict[str, str]:
        """MongoDB does not use SQL schema"""
        return {}
    
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
            List containing a single dict with all collected data
        """
        if not self.client:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        
        print(f"\n📊 Collecting Slack data for {self.workspace}")
        if start_date and end_date:
            print(f"   Period: {start_date.isoformat()} ~ {end_date.isoformat()}")
        
        try:
            # Convert datetime to Slack timestamps (Unix epoch seconds)
            oldest = str(start_date.timestamp()) if start_date else "0"
            latest = str(end_date.timestamp()) if end_date else str(datetime.now(tz=pytz.UTC).timestamp())
            
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
            
            for idx, channel in enumerate(channels, 1):
                channel_id = channel['id']
                channel_name = channel['name']
                
                print(f"   📂 [{idx}/{len(channels)}] Collecting from #{channel_name}...", end=" ")
                
                messages = self._fetch_channel_messages(channel_id, oldest, latest)
                
                if messages:
                    all_messages.extend(messages)
                    print(f"✅ {len(messages)} messages")
                else:
                    print("- no messages")
            
            print(f"\n📊 Collection Results:")
            print(f"   Users: {len(users)}")
            print(f"   Channels: {len(channels)}")
            print(f"   Messages: {len(all_messages)}")
            
            # Count embedded data
            total_reactions = sum(len(msg.get('reactions', [])) for msg in all_messages)
            total_links = sum(len(msg.get('links', [])) for msg in all_messages)
            total_files = sum(len(msg.get('files', [])) for msg in all_messages)
            
            print(f"   Reactions: {total_reactions}")
            print(f"   Links: {total_links}")
            print(f"   Files: {total_files}")
            
            return [{
                'users': users,
                'channels': channels,
                'messages': all_messages,
            }]
            
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
                    user_id = member['id']
                    name = member.get('name', '')
                    email = member.get('profile', {}).get('email', '')
                    
                    users.append(member)
                    
                    # Build mappings
                    if email:
                        self.user_email_map[user_id] = email
                    if name:
                        self.user_name_map[user_id] = name
                
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
                    channels.append(channel)
                    self.channel_name_map[channel['id']] = channel['name']
                
                if not response.get('response_metadata', {}).get('next_cursor'):
                    break
                    
                cursor = response['response_metadata']['next_cursor']
                
            except SlackApiError as e:
                print(f"   ⚠️  Error fetching public channels: {e.response['error']}")
                break
        
        # Fetch private channels
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
                    channels.append(channel)
                    self.channel_name_map[channel['id']] = channel['name']
                
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
                    
                    # Convert Slack timestamp to UTC datetime
                    msg_timestamp = datetime.fromtimestamp(float(msg['ts']), tz=pytz.UTC)
                    
                    user_id = msg.get('user', '')
                    
                    # Extract reactions (to be embedded)
                    reactions = []
                    if self.include_reactions and 'reactions' in msg:
                        for reaction in msg['reactions']:
                            reactions.append({
                                'reaction': reaction['name'],
                                'count': reaction['count'],
                                'users': reaction.get('users', [])
                            })
                    
                    # Extract links (to be embedded)
                    links = self._extract_links_from_text(msg.get('text', ''))
                    
                    # Extract files (to be embedded)
                    files = []
                    if self.include_files and 'files' in msg:
                        for file_obj in msg['files']:
                            files.append({
                                'id': file_obj['id'],
                                'name': file_obj.get('name', ''),
                                'url_private': file_obj.get('url_private', ''),
                                'size': file_obj.get('size', 0)
                            })
                    
                    message_data = {
                        'ts': msg['ts'],
                        'channel_id': channel_id,
                        'channel_name': self.channel_name_map.get(channel_id, ''),
                        'user_id': user_id,
                        'user_name': self.user_name_map.get(user_id, ''),
                        'text': msg.get('text', ''),
                        'thread_ts': msg.get('thread_ts'),
                        'reply_count': msg.get('reply_count', 0),
                        'reactions': reactions,
                        'links': links,
                        'files': files,
                        'posted_at': msg_timestamp,
                    }
                    messages.append(message_data)
                    
                    # Fetch thread replies if this is a thread parent
                    if self.include_threads and msg.get('thread_ts') == msg.get('ts'):
                        thread_messages = self._fetch_thread_replies(
                            channel_id,
                            msg['thread_ts'],
                            oldest,
                            latest
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
    
    def _fetch_thread_replies(
        self, 
        channel_id: str, 
        thread_ts: str,
        oldest: str = None,
        latest: str = None
    ) -> List[Dict[str, Any]]:
        """Fetch replies in a thread"""
        replies = []
        
        oldest_ts = float(oldest) if oldest else 0
        latest_ts = float(latest) if latest else float('inf')
        
        try:
            response = self.client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=1000
            )
            
            for msg in response['messages']:
                # Skip the parent message
                if msg['ts'] == thread_ts:
                    continue
                
                if msg.get('subtype') in ['bot_message']:
                    continue
                
                # Filter by date range
                msg_ts = float(msg['ts'])
                if msg_ts < oldest_ts or msg_ts > latest_ts:
                    continue
                
                reply_timestamp = datetime.fromtimestamp(msg_ts, tz=pytz.UTC)
                user_id = msg.get('user', '')
                
                # Extract reactions
                reactions = []
                if self.include_reactions and 'reactions' in msg:
                    for reaction in msg['reactions']:
                        reactions.append({
                            'reaction': reaction['name'],
                            'count': reaction['count'],
                            'users': reaction.get('users', [])
                        })
                
                # Extract links
                links = self._extract_links_from_text(msg.get('text', ''))
                
                # Extract files
                files = []
                if self.include_files and 'files' in msg:
                    for file_obj in msg['files']:
                        files.append({
                            'id': file_obj['id'],
                            'name': file_obj.get('name', ''),
                            'url_private': file_obj.get('url_private', ''),
                            'size': file_obj.get('size', 0)
                        })
                
                reply_data = {
                    'ts': msg['ts'],
                    'channel_id': channel_id,
                    'channel_name': self.channel_name_map.get(channel_id, ''),
                    'user_id': user_id,
                    'user_name': self.user_name_map.get(user_id, ''),
                    'text': msg.get('text', ''),
                    'thread_ts': thread_ts,
                    'reply_count': 0,
                    'reactions': reactions,
                    'links': links,
                    'files': files,
                    'posted_at': reply_timestamp,
                }
                replies.append(reply_data)
        
        except SlackApiError as e:
            print(f"\n   ⚠️  Error fetching thread replies: {e.response['error']}")
        
        return replies
    
    def _extract_links_from_text(self, text: str) -> List[Dict[str, str]]:
        """Extract and classify links from message text"""
        links = []
        
        # Find all URLs in text
        url_pattern = r'https?://[^\s<>]+'
        urls = re.findall(url_pattern, text)
        
        for url in urls:
            url = url.strip('<>')
            
            # Classify link
            link_type = 'external'
            
            for pattern_name, pattern in self.LINK_PATTERNS.items():
                if re.search(pattern, url):
                    link_type = pattern_name
                    break
            
            links.append({
                'url': url,
                'type': link_type
            })
        
        return links
    
    async def save_data(self, collected_data: Dict[str, Any]):
        """Save collected Slack data to MongoDB"""
        print("\n8️⃣ Saving to MongoDB...")
        
        # Save channels
        channels_to_save = []
        for ch in collected_data.get('channels', []):
            channel_doc = {
                'channel_id': ch['id'],
                'name': ch['name'],
                'is_private': ch.get('is_private', False),
                'created': datetime.fromtimestamp(ch['created'], tz=pytz.UTC) if 'created' in ch else datetime.utcnow(),
                'num_members': ch.get('num_members', 0)
            }
            channels_to_save.append(channel_doc)
        
        if channels_to_save:
            try:
                # Use replace_one with upsert for each channel to avoid duplicates
                for ch_doc in channels_to_save:
                    self.collections["channels"].replace_one(
                        {'channel_id': ch_doc['channel_id']},
                        ch_doc,
                        upsert=True
                    )
                print(f"   ✅ Saved {len(channels_to_save)} channels")
            except Exception as e:
                print(f"   ❌ Error saving channels: {e}")
        
        # Save messages
        messages_to_save = []
        for msg in collected_data.get('messages', []):
            # Ensure posted_at is a datetime object
            if isinstance(msg['posted_at'], str):
                msg['posted_at'] = datetime.fromisoformat(msg['posted_at'])
            
            message_doc = {
                'channel_id': msg['channel_id'],
                'channel_name': msg['channel_name'],
                'ts': msg['ts'],
                'user_id': msg['user_id'],
                'user_name': msg['user_name'],
                'text': msg['text'],
                'type': 'message',
                'thread_ts': msg.get('thread_ts'),
                'reply_count': msg.get('reply_count', 0),
                'reactions': msg.get('reactions', []),
                'links': msg.get('links', []),
                'files': msg.get('files', []),
                'posted_at': msg['posted_at'],
                'collected_at': datetime.utcnow()
            }
            messages_to_save.append(message_doc)
        
        if messages_to_save:
            try:
                # Use replace_one with upsert for each message to avoid duplicates
                saved_count = 0
                for msg_doc in messages_to_save:
                    self.collections["messages"].replace_one(
                        {'ts': msg_doc['ts'], 'channel_id': msg_doc['channel_id']},
                        msg_doc,
                        upsert=True
                    )
                    saved_count += 1
                print(f"   ✅ Saved {saved_count} messages")
            except Exception as e:
                print(f"   ❌ Error saving messages: {e}")
    
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
            
            # Check if slack_id is actually an email address
            if slack_id and '@' in slack_id:
                email = slack_id
                slack_id = None
            
            if slack_id and name:
                mapping[slack_id.lower()] = name
                print(f"   ✅ Direct mapping: {name} -> {slack_id}")
            elif email and name:
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
        
        # Build set of deleted user IDs
        deleted_users = set()
        for user in data.get('users', []):
            if user.get('is_deleted', False) or user.get('deleted', False):
                deleted_users.add(user['id'].lower())
        
        if deleted_users:
            print(f"   🗑️  Filtering out {len(deleted_users)} deleted/deactivated users")
        
        for message in data.get('messages', []):
            user_id = message.get('user_id')
            if not user_id or user_id.lower() in deleted_users:
                continue
            
            channel_id = message['channel_id']
            ts = message['ts']
            posted_at = message['posted_at']
            
            # Ensure posted_at is a datetime object
            if isinstance(posted_at, str):
                posted_at = datetime.fromisoformat(posted_at)
            
            activity = {
                'member_identifier': user_id.lower(),
                'activity_type': 'message',
                'timestamp': posted_at,
                'activity_id': f"slack:message:{channel_id}:{ts}",
                'metadata': {
                    'channel_id': channel_id,
                    'message_ts': ts,
                    'text_length': len(message.get('text', '')),
                    'is_thread': bool(message.get('thread_ts')),
                    'has_links': len(message.get('links', [])) > 0,
                    'has_files': len(message.get('files', [])) > 0
                }
            }
            activities.append(activity)
            
            # Add reaction activities
            for reaction_obj in message.get('reactions', []):
                reaction_name = reaction_obj.get('reaction', '')
                for reactor_id in reaction_obj.get('users', []):
                    if reactor_id.lower() in deleted_users:
                        continue
                    
                    reaction_timestamp = posted_at  # Use message timestamp as approximation
                    
                    activity = {
                        'member_identifier': reactor_id.lower(),
                        'activity_type': 'reaction',
                        'timestamp': reaction_timestamp,
                        'activity_id': f"slack:reaction:{ts}:{reaction_name}:{reactor_id}",
                        'metadata': {
                            'message_ts': ts,
                            'emoji': reaction_name
                        }
                    }
                    activities.append(activity)
        
        return activities

