"""Database management system"""

from typing import Dict, Optional, List, Any
from pathlib import Path
import sqlite3
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from src.utils.logger import get_logger


class DatabaseManager:
    """
    Manage multiple databases for different data sources
    
    Each data source gets its own database to maintain separation,
    while a main database handles member indexing and integration.
    """
    
    def __init__(self, main_db_url: str):
        """
        Initialize database manager
        
        Args:
            main_db_url: SQLAlchemy database URL for main database
        """
        self.logger = get_logger(__name__)
        self.main_db_url = main_db_url
        self.main_engine = self._create_engine(main_db_url)
        self.source_engines: Dict[str, Engine] = {}
        
        # Create data directory if it doesn't exist
        if main_db_url.startswith('sqlite:///'):
            db_path = Path(main_db_url.replace('sqlite:///', ''))
            db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _create_engine(self, db_url: str) -> Engine:
        """Create SQLAlchemy engine"""
        # For SQLite, use StaticPool to allow multi-threading
        if db_url.startswith('sqlite:'):
            return create_engine(
                db_url,
                connect_args={'check_same_thread': False},
                poolclass=StaticPool,
                echo=False
            )
        else:
            return create_engine(db_url, echo=False)
    
    def get_main_engine(self) -> Engine:
        """Get main database engine"""
        return self.main_engine
    
    def create_source_database(self, source_name: str, schema: Dict[str, str]) -> Engine:
        """
        Create or get database for a specific data source
        
        Args:
            source_name: Name of the data source (e.g., 'slack', 'github')
            schema: Dict mapping table names to CREATE TABLE SQL statements
            
        Returns:
            SQLAlchemy Engine for the source database
        """
        if source_name in self.source_engines:
            return self.source_engines[source_name]
        
        # Create source-specific database URL
        if self.main_db_url.startswith('sqlite:///'):
            # SQLite: create separate file for each source
            main_path = Path(self.main_db_url.replace('sqlite:///', ''))
            source_path = main_path.parent / f"{source_name}.db"
            source_db_url = f"sqlite:///{source_path}"
        else:
            # PostgreSQL: use different schema for each source
            base_url = self.main_db_url.rsplit('/', 1)[0]
            source_db_url = f"{base_url}/{source_name}"
        
        # Create engine
        engine = self._create_engine(source_db_url)
        self.source_engines[source_name] = engine
        
        # Create tables
        self._create_tables(engine, schema)
        
        print(f"✅ Created database for source: {source_name}")
        return engine
    
    def register_existing_source_database(self, source_name: str, db_url: str) -> Engine:
        """
        Register an existing source database without creating new tables
        
        Args:
            source_name: Name of the data source
            db_url: Database URL for the source
            
        Returns:
            Database engine for the source
        """
        if source_name in self.source_engines:
            return self.source_engines[source_name]
        
        # Create engine and register it
        engine = self._create_engine(db_url)
        self.source_engines[source_name] = engine
        
        self.logger.debug(f"✅ Registered existing database for source: {source_name}")
        return engine
    
    def _create_tables(self, engine: Engine, schema: Dict[str, str]) -> None:
        """Create tables from schema definition"""
        with engine.begin() as conn:
            for table_name, create_sql in schema.items():
                try:
                    conn.execute(text(create_sql))
                except Exception as e:
                    print(f"⚠️  Error creating table {table_name}: {e}")
    
    def get_source_engine(self, source_name: str) -> Optional[Engine]:
        """Get database engine for a specific source"""
        return self.source_engines.get(source_name)
    
    @contextmanager
    def get_connection(self, source_name: Optional[str] = None):
        """
        Get database connection context manager
        
        Args:
            source_name: Data source name. If None, uses main database
            
        Yields:
            Database connection
        """
        if source_name and source_name in self.source_engines:
            engine = self.source_engines[source_name]
        else:
            engine = self.main_engine
        
        connection = engine.connect()
        try:
            yield connection
        finally:
            connection.close()
    
    def execute_query(
        self, 
        query: str, 
        params: Optional[Dict[str, Any]] = None,
        source_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a query and return results
        
        Args:
            query: SQL query
            params: Query parameters
            source_name: Data source name. If None, uses main database
            
        Returns:
            List of result rows as dictionaries
        """
        with self.get_connection(source_name) as conn:
            result = conn.execute(text(query), params or {})
            
            if result.returns_rows:
                # Convert to list of dicts
                columns = result.keys()
                return [dict(zip(columns, row)) for row in result.fetchall()]
            
            return []
    
    def insert_data(
        self,
        table_name: str,
        data: List[Dict[str, Any]],
        source_name: Optional[str] = None
    ) -> int:
        """
        Insert multiple rows into a table
        
        Args:
            table_name: Name of the table
            data: List of dictionaries with column: value pairs
            source_name: Data source name. If None, uses main database
            
        Returns:
            Number of rows inserted
        """
        if not data:
            return 0
        
        # Get column names from first row
        columns = list(data[0].keys())
        placeholders = ', '.join([f':{col}' for col in columns])
        columns_str = ', '.join(columns)
        
        query = f"INSERT OR IGNORE INTO {table_name} ({columns_str}) VALUES ({placeholders})"
        
        with self.get_connection(source_name) as conn:
            with conn.begin():
                result = conn.execute(text(query), data)
                return result.rowcount
    
    def initialize_main_schema(self) -> None:
        """Initialize schema for main database (member index, etc.)"""
        schema = {
            'members': '''
                CREATE TABLE IF NOT EXISTS members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'member_identifiers': '''
                CREATE TABLE IF NOT EXISTS member_identifiers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    member_id INTEGER NOT NULL,
                    source_type TEXT NOT NULL,
                    source_user_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (member_id) REFERENCES members(id),
                    UNIQUE(source_type, source_user_id)
                )
            ''',
            'member_activities': '''
                CREATE TABLE IF NOT EXISTS member_activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    member_id INTEGER NOT NULL,
                    source_type TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (member_id) REFERENCES members(id)
                )
            ''',
            'data_collections': '''
                CREATE TABLE IF NOT EXISTS data_collections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    start_date TIMESTAMP,
                    end_date TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    records_collected INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            '''
        }
        
        self._create_tables(self.main_engine, schema)
        print("✅ Main database schema initialized")
    
    def close_all(self) -> None:
        """Close all database connections"""
        for source_name, engine in self.source_engines.items():
            engine.dispose()
            print(f"🔒 Closed database connection for {source_name}")
        
        self.main_engine.dispose()
        print("🔒 Closed main database connection")
    
    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.close_all()
        except:
            pass

