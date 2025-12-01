"""
MongoDB Connection Manager

Manages MongoDB connections, provides database and collection access,
and handles connection pooling for the All-Thing-Eye project.
"""

from typing import Optional, Dict, Any
from contextlib import contextmanager
import pymongo
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from motor.motor_asyncio import AsyncIOMotorClient
import os

from src.utils.logger import get_logger

logger = get_logger(__name__)


class MongoDBManager:
    """
    MongoDB Connection Manager
    
    Provides both sync and async MongoDB connections with connection pooling.
    Handles database and collection access for all data sources.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize MongoDB Manager
        
        Args:
            config: MongoDB configuration from config.yaml
        """
        self.config = config
        self.uri = config.get('uri', 'mongodb://localhost:27017')
        self.database_name = config.get('database', 'all_thing_eye')
        
        # Shared database URI (for recordings from Google Drive)
        self.shared_uri = os.getenv('MONGODB_SHARED_URI', self.uri)
        
        # Connection pool settings
        self.max_pool_size = config.get('max_pool_size', 100)
        self.min_pool_size = config.get('min_pool_size', 10)
        
        # Write concern settings
        write_concern = config.get('write_concern', {})
        self.write_concern = pymongo.WriteConcern(
            w=write_concern.get('w', 'majority'),
            j=write_concern.get('j', True),
            wtimeout=write_concern.get('wtimeout', 5000)
        )
        
        # Read preference
        read_pref_str = config.get('read_preference', 'primaryPreferred')
        self.read_preference = self._get_read_preference(read_pref_str)
        
        # Collection names mapping
        self.collections = config.get('collections', {})
        
        # Sync client (for plugins and synchronous operations)
        self._sync_client: Optional[MongoClient] = None
        self._sync_db: Optional[Database] = None
        
        # Async client (for FastAPI endpoints)
        self._async_client: Optional[AsyncIOMotorClient] = None
        self._async_db: Optional[Database] = None
        
        # Shared database clients (for recordings)
        self._shared_sync_client: Optional[MongoClient] = None
        self._shared_sync_db: Optional[Database] = None
        self._shared_async_client: Optional[AsyncIOMotorClient] = None
        self._shared_async_db: Optional[Database] = None
        
        logger.info(f"MongoDB Manager initialized for database: {self.database_name}")
    
    def _get_read_preference(self, pref_str: str):
        """Convert read preference string to pymongo constant"""
        prefs = {
            'primary': pymongo.ReadPreference.PRIMARY,
            'primaryPreferred': pymongo.ReadPreference.PRIMARY_PREFERRED,
            'secondary': pymongo.ReadPreference.SECONDARY,
            'secondaryPreferred': pymongo.ReadPreference.SECONDARY_PREFERRED,
            'nearest': pymongo.ReadPreference.NEAREST
        }
        return prefs.get(pref_str, pymongo.ReadPreference.PRIMARY_PREFERRED)
    
    def connect_sync(self) -> MongoClient:
        """
        Create synchronous MongoDB connection
        
        Returns:
            MongoClient instance
        """
        if self._sync_client is None:
            try:
                self._sync_client = MongoClient(
                    self.uri,
                    maxPoolSize=self.max_pool_size,
                    minPoolSize=self.min_pool_size,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=10000,
                    socketTimeoutMS=30000,
                )
                
                # Test connection
                self._sync_client.admin.command('ping')
                logger.info("✅ Synchronous MongoDB connection established")
                
                self._sync_db = self._sync_client[self.database_name]
                
                # Create indexes if enabled
                if self.config.get('auto_create_indexes', True):
                    self._create_indexes(self._sync_db)
                
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                logger.error(f"❌ Failed to connect to MongoDB: {e}")
                raise
        
        return self._sync_client
    
    def connect_async(self) -> AsyncIOMotorClient:
        """
        Create asynchronous MongoDB connection (for FastAPI)
        
        Returns:
            AsyncIOMotorClient instance
        """
        if self._async_client is None:
            try:
                self._async_client = AsyncIOMotorClient(
                    self.uri,
                    maxPoolSize=self.max_pool_size,
                    minPoolSize=self.min_pool_size,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=10000,
                    socketTimeoutMS=30000,
                )
                
                logger.info("✅ Asynchronous MongoDB connection established")
                self._async_db = self._async_client[self.database_name]
                
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                logger.error(f"❌ Failed to connect to MongoDB (async): {e}")
                raise
        
        return self._async_client
    
    @property
    def db(self) -> Database:
        """Get synchronous database instance"""
        if self._sync_db is None:
            self.connect_sync()
        return self._sync_db
    
    @property
    def async_db(self) -> Database:
        """Get asynchronous database instance"""
        if self._async_db is None:
            self.connect_async()
        return self._async_db
    
    def connect_shared_sync(self) -> MongoClient:
        """
        Create synchronous connection to shared MongoDB database
        
        Returns:
            MongoClient instance for shared database
        """
        if self._shared_sync_client is None:
            try:
                self._shared_sync_client = MongoClient(
                    self.shared_uri,
                    maxPoolSize=self.max_pool_size,
                    minPoolSize=self.min_pool_size,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=10000,
                    socketTimeoutMS=30000,
                )
                
                # Test connection
                self._shared_sync_client.admin.command('ping')
                logger.info("✅ Synchronous shared MongoDB connection established")
                
                self._shared_sync_db = self._shared_sync_client['shared']
                
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                logger.error(f"❌ Failed to connect to shared MongoDB: {e}")
                raise
        
        return self._shared_sync_client
    
    def connect_shared_async(self) -> AsyncIOMotorClient:
        """
        Create asynchronous connection to shared MongoDB database
        
        Returns:
            AsyncIOMotorClient instance for shared database
        """
        if self._shared_async_client is None:
            try:
                self._shared_async_client = AsyncIOMotorClient(
                    self.shared_uri,
                    maxPoolSize=self.max_pool_size,
                    minPoolSize=self.min_pool_size,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=10000,
                    socketTimeoutMS=30000,
                )
                
                logger.info("✅ Asynchronous shared MongoDB connection established")
                self._shared_async_db = self._shared_async_client['shared']
                
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                logger.error(f"❌ Failed to connect to shared MongoDB (async): {e}")
                raise
        
        return self._shared_async_client
    
    @property
    def shared_db(self) -> Database:
        """Get synchronous shared database instance"""
        if self._shared_sync_db is None:
            self.connect_shared_sync()
        return self._shared_sync_db
    
    @property
    def shared_async_db(self) -> Database:
        """Get asynchronous shared database instance"""
        if self._shared_async_db is None:
            self.connect_shared_async()
        return self._shared_async_db
    
    def get_collection(self, collection_name: str) -> Collection:
        """
        Get collection by name (synchronous)
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Collection instance
        """
        actual_name = self.collections.get(collection_name, collection_name)
        return self.db[actual_name]
    
    def get_async_collection(self, collection_name: str):
        """
        Get collection by name (asynchronous)
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            AsyncIOMotorCollection instance
        """
        actual_name = self.collections.get(collection_name, collection_name)
        return self.async_db[actual_name]
    
    @contextmanager
    def session(self):
        """
        Context manager for MongoDB transactions
        
        Usage:
            with mongo_manager.session() as session:
                collection.insert_one({...}, session=session)
                collection.update_one({...}, session=session)
        """
        client = self.connect_sync()
        session = client.start_session()
        try:
            with session.start_transaction(
                write_concern=self.write_concern,
                read_preference=self.read_preference
            ):
                yield session
        finally:
            session.end_session()
    
    def _create_indexes(self, db: Database):
        """Create indexes for all collections"""
        logger.info("📊 Creating MongoDB indexes...")
        
        try:
            # Members collection
            members = db[self.collections.get('members', 'members')]
            members.create_index('name', unique=True)
            members.create_index('email')
            members.create_index('role')
            
            # Member identifiers collection
            identifiers = db[self.collections.get('member_identifiers', 'member_identifiers')]
            identifiers.create_index([('member_id', 1), ('source_type', 1)])
            identifiers.create_index('source_user_id')
            identifiers.create_index([('source_type', 1), ('source_user_id', 1)], unique=True)
            
            # Member activities collection
            activities = db[self.collections.get('member_activities', 'member_activities')]
            activities.create_index('activity_id', unique=True)
            activities.create_index('member_id')
            activities.create_index('source_type')
            activities.create_index('activity_type')
            activities.create_index('timestamp')
            activities.create_index([('member_id', 1), ('timestamp', -1)])
            activities.create_index([('source_type', 1), ('activity_type', 1)])
            
            # Translations collection (for translation caching)
            translations = db.get_collection('translations')
            translations.create_index('cache_key', unique=True)
            translations.create_index([('source_language', 1), ('target_language', 1)])
            translations.create_index('created_at')
            
            # GitHub collections
            github_commits = db[self.collections.get('github_commits', 'github_commits')]
            github_commits.create_index('sha', unique=True)
            github_commits.create_index('author_name')
            github_commits.create_index('repository')
            github_commits.create_index('date')
            
            github_prs = db[self.collections.get('github_pull_requests', 'github_pull_requests')]
            github_prs.create_index([('repository', 1), ('number', 1)], unique=True)
            github_prs.create_index('author')
            github_prs.create_index('state')
            github_prs.create_index('created_at')
            
            github_issues = db[self.collections.get('github_issues', 'github_issues')]
            github_issues.create_index([('repository', 1), ('number', 1)], unique=True)
            github_issues.create_index('author')
            github_issues.create_index('state')
            
            # Slack collections
            slack_messages = db[self.collections.get('slack_messages', 'slack_messages')]
            slack_messages.create_index([('channel_id', 1), ('ts', 1)], unique=True)
            slack_messages.create_index('user_id')
            slack_messages.create_index('posted_at')
            
            slack_reactions = db[self.collections.get('slack_reactions', 'slack_reactions')]
            slack_reactions.create_index([('message_ts', 1), ('user_id', 1), ('reaction', 1)], unique=True)
            
            # Notion collections
            notion_pages = db[self.collections.get('notion_pages', 'notion_pages')]
            notion_pages.create_index('id', unique=True)
            notion_pages.create_index('last_edited_time')
            
            # Drive collections
            drive_activities = db[self.collections.get('drive_activities', 'drive_activities')]
            drive_activities.create_index('activity_id', unique=True)
            drive_activities.create_index('actor_email')
            drive_activities.create_index('time')
            
            logger.info("✅ Indexes created successfully")
            
        except Exception as e:
            logger.warning(f"⚠️  Error creating indexes: {e}")
    
    def close(self):
        """Close all MongoDB connections"""
        if self._sync_client:
            self._sync_client.close()
            logger.info("🔒 Closed synchronous MongoDB connection")
        
        if self._async_client:
            self._async_client.close()
            logger.info("🔒 Closed asynchronous MongoDB connection")
        
        if self._shared_sync_client:
            self._shared_sync_client.close()
            logger.info("🔒 Closed shared synchronous MongoDB connection")
        
        if self._shared_async_client:
            self._shared_async_client.close()
            logger.info("🔒 Closed shared asynchronous MongoDB connection")
    
    def test_connection(self) -> bool:
        """
        Test MongoDB connection
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            client = self.connect_sync()
            client.admin.command('ping')
            
            # Get server info
            server_info = client.server_info()
            version = server_info.get('version', 'unknown')
            
            logger.info(f"✅ MongoDB connection test successful")
            logger.info(f"   Server version: {version}")
            logger.info(f"   Database: {self.database_name}")
            
            # List collections
            collections = self.db.list_collection_names()
            logger.info(f"   Collections: {len(collections)}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ MongoDB connection test failed: {e}")
            return False


# Singleton instance
_mongo_manager: Optional[MongoDBManager] = None


def get_mongo_manager(config: Optional[Dict[str, Any]] = None) -> MongoDBManager:
    """
    Get MongoDB Manager singleton instance
    
    Args:
        config: MongoDB configuration (required on first call)
        
    Returns:
        MongoDBManager instance
    """
    global _mongo_manager
    
    if _mongo_manager is None:
        if config is None:
            raise ValueError("MongoDB configuration required for first initialization")
        _mongo_manager = MongoDBManager(config)
    
    return _mongo_manager


def close_mongo_manager():
    """Close MongoDB Manager and all connections"""
    global _mongo_manager
    if _mongo_manager:
        _mongo_manager.close()
        _mongo_manager = None

