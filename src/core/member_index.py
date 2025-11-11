"""Member index system for unified member management"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import json
from sqlalchemy import text
from .database import DatabaseManager


class MemberIndex:
    """
    Unified member index that maps identifiers across different data sources
    
    This allows querying member activities from all sources using a single member ID.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize member index
        
        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager
    
    def register_member(
        self, 
        name: str, 
        email: Optional[str] = None,
        source_identifiers: Optional[Dict[str, str]] = None
    ) -> int:
        """
        Register a new member or update existing one
        
        Args:
            name: Member name (primary identifier)
            email: Member email
            source_identifiers: Dict of {source_type: source_user_id}
                               e.g., {'github': 'johndoe', 'slack': 'U123ABC'}
            
        Returns:
            Member ID
        """
        # Check if member already exists
        query = "SELECT id FROM members WHERE name = :name"
        result = self.db.execute_query(query, {'name': name})
        
        if result:
            member_id = result[0]['id']
            print(f"ℹ️  Member '{name}' already exists (ID: {member_id})")
        else:
            # Insert new member
            insert_query = text("INSERT INTO members (name, email) VALUES (:name, :email)")
            with self.db.get_connection() as conn:
                with conn.begin():
                    result = conn.execute(
                        insert_query, 
                        {'name': name, 'email': email}
                    )
                    member_id = result.lastrowid
            
            print(f"✅ Registered member '{name}' (ID: {member_id})")
        
        # Add source identifiers
        if source_identifiers:
            self._add_source_identifiers(member_id, source_identifiers)
        
        return member_id
    
    def _add_source_identifiers(
        self, 
        member_id: int, 
        identifiers: Dict[str, str]
    ) -> None:
        """Add source-specific user IDs for a member"""
        insert_query = text('''
            INSERT OR IGNORE INTO member_identifiers 
            (member_id, source_type, source_user_id) 
            VALUES (:member_id, :source_type, :source_user_id)
        ''')
        
        data = [
            {
                'member_id': member_id,
                'source_type': source_type,
                'source_user_id': user_id
            }
            for source_type, user_id in identifiers.items()
        ]
        
        with self.db.get_connection() as conn:
            with conn.begin():
                for item in data:
                    conn.execute(insert_query, item)
    
    def resolve_member_id(
        self, 
        source_type: str, 
        source_user_id: str
    ) -> Optional[int]:
        """
        Get member ID from source-specific user ID
        
        Args:
            source_type: Type of data source (e.g., 'github', 'slack')
            source_user_id: User ID in that source
            
        Returns:
            Member ID or None if not found
        """
        query = '''
            SELECT member_id 
            FROM member_identifiers 
            WHERE source_type = :source_type 
            AND source_user_id = :source_user_id
        '''
        
        result = self.db.execute_query(
            query, 
            {'source_type': source_type, 'source_user_id': source_user_id}
        )
        
        if result:
            return result[0]['member_id']
        
        return None
    
    def get_member_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get member information by name or email"""
        # Try exact name match first
        query = '''
            SELECT id, name, email, created_at 
            FROM members 
            WHERE name = :name OR email = :name
        '''
        
        result = self.db.execute_query(query, {'name': name})
        if result:
            return result[0]
        
        # Try case-insensitive match
        query_insensitive = '''
            SELECT id, name, email, created_at 
            FROM members 
            WHERE LOWER(name) = LOWER(:name) OR LOWER(email) = LOWER(:name)
        '''
        
        result = self.db.execute_query(query_insensitive, {'name': name})
        return result[0] if result else None
    
    def get_member_identifier(self, member_id: int, source_type: str) -> Optional[str]:
        """
        Get a specific source identifier for a member
        
        Args:
            member_id: Member ID
            source_type: Type of data source (e.g., 'github', 'slack')
            
        Returns:
            Source user ID or None if not found
        """
        query = '''
            SELECT source_user_id 
            FROM member_identifiers 
            WHERE member_id = :member_id AND source_type = :source_type
        '''
        
        result = self.db.execute_query(
            query,
            {'member_id': member_id, 'source_type': source_type}
        )
        
        return result[0]['source_user_id'] if result else None
    
    def get_member_identifiers(self, member_id: int) -> Dict[str, str]:
        """
        Get all source identifiers for a member
        
        Args:
            member_id: Member ID
            
        Returns:
            Dict of {source_type: source_user_id}
        """
        query = '''
            SELECT source_type, source_user_id 
            FROM member_identifiers 
            WHERE member_id = :member_id
        '''
        
        result = self.db.execute_query(query, {'member_id': member_id})
        
        return {row['source_type']: row['source_user_id'] for row in result}
    
    def add_activity(
        self,
        member_id: int,
        source_type: str,
        activity_type: str,
        timestamp: datetime,
        metadata: Dict[str, Any],
        activity_id: Optional[str] = None
    ) -> None:
        """
        Record a member activity
        
        Args:
            member_id: Member ID
            source_type: Type of data source
            activity_type: Type of activity
            timestamp: Activity timestamp
            metadata: Additional activity data
            activity_id: Unique activity identifier (for deduplication)
        """
        insert_query = text('''
            INSERT OR IGNORE INTO member_activities 
            (member_id, source_type, activity_type, timestamp, metadata, activity_id)
            VALUES (:member_id, :source_type, :activity_type, :timestamp, :metadata, :activity_id)
        ''')
        
        with self.db.get_connection() as conn:
            with conn.begin():
                conn.execute(
                    insert_query,
                    {
                        'member_id': member_id,
                        'source_type': source_type,
                        'activity_type': activity_type,
                        'timestamp': timestamp.isoformat(),
                        'metadata': json.dumps(metadata, ensure_ascii=False),
                        'activity_id': activity_id
                    }
                )
    
    def get_member_activities(
        self,
        member_name: str,
        source_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get activities for a member
        
        Args:
            member_name: Member name
            source_type: Filter by source type (optional)
            start_date: Filter by start date (optional)
            end_date: Filter by end date (optional)
            limit: Maximum number of records to return
            
        Returns:
            List of activity records
        """
        # Get member ID
        member = self.get_member_by_name(member_name)
        if not member:
            return []
        
        member_id = member['id']
        
        # Build query
        query = '''
            SELECT 
                ma.source_type,
                ma.activity_type,
                ma.timestamp,
                ma.metadata,
                ma.created_at
            FROM member_activities ma
            WHERE ma.member_id = :member_id
        '''
        
        params = {'member_id': member_id}
        
        if source_type:
            query += ' AND ma.source_type = :source_type'
            params['source_type'] = source_type
        
        if start_date:
            query += ' AND ma.timestamp >= :start_date'
            params['start_date'] = start_date.isoformat()
        
        if end_date:
            query += ' AND ma.timestamp <= :end_date'
            params['end_date'] = end_date.isoformat()
        
        query += ' ORDER BY ma.timestamp DESC'
        
        if limit:
            query += f' LIMIT {limit}'
        
        result = self.db.execute_query(query, params)
        
        # Parse JSON metadata
        for row in result:
            if row.get('metadata'):
                try:
                    row['metadata'] = json.loads(row['metadata'])
                except:
                    pass
        
        return result
    
    def get_all_members(self) -> List[Dict[str, Any]]:
        """Get all registered members"""
        query = '''
            SELECT id, name, email, created_at 
            FROM members 
            ORDER BY name
        '''
        
        return self.db.execute_query(query)
    
    def sync_from_plugin(
        self,
        source_type: str,
        member_mapping: Dict[str, str],
        activities: List[Dict[str, Any]],
        member_details: Optional[Dict[str, Dict[str, str]]] = None
    ) -> Dict[str, int]:
        """
        Sync members and activities from a plugin
        
        Args:
            source_type: Type of data source
            member_mapping: Dict of {source_user_id: member_name}
            activities: List of activity records from plugin
            member_details: Optional dict of {member_name: {'email': '...', 'name': '...'}}
            
        Returns:
            Stats dict with sync results
        """
        stats = {
            'members_registered': 0,
            'activities_added': 0,
            'errors': 0
        }
        
        # First, ensure all members are registered
        member_id_map = {}  # source_user_id -> member_id
        
        for source_user_id, member_name in member_mapping.items():
            try:
                # Try to find existing member
                member = self.get_member_by_name(member_name)
                
                if member:
                    member_id = member['id']
                else:
                    # Get additional member details if available
                    email = None
                    original_source_id = source_user_id  # Default to lowercase key
                    
                    if member_details and member_name in member_details:
                        details = member_details[member_name]
                        email = details.get('email')
                        # Get original case-sensitive source ID
                        if source_type == 'github':
                            original_source_id = details.get('github_id', source_user_id)
                        elif source_type == 'slack':
                            original_source_id = details.get('slack_id', source_user_id)
                    
                    # Register new member with name as primary identifier
                    # IMPORTANT: Use original_source_id with correct case for member_identifiers
                    member_id = self.register_member(
                        name=member_name,
                        email=email,
                        source_identifiers={source_type: original_source_id}
                    )
                    stats['members_registered'] += 1
                
                member_id_map[source_user_id.lower()] = member_id
                
            except Exception as e:
                print(f"⚠️  Error registering member {member_name}: {e}")
                stats['errors'] += 1
        
        # Add activities
        for activity in activities:
            try:
                member_identifier = activity.get('member_identifier', '').lower()
                
                # Resolve member ID
                member_id = None
                if member_identifier in member_id_map:
                    member_id = member_id_map[member_identifier]
                else:
                    # Try to resolve by source user ID
                    member_id = self.resolve_member_id(source_type, member_identifier)
                
                if not member_id:
                    # Last resort: try as member name
                    member = self.get_member_by_name(member_identifier)
                    if member:
                        member_id = member['id']
                
                if not member_id:
                    print(f"⚠️  Could not resolve member: {member_identifier}")
                    stats['errors'] += 1
                    continue
                
                # Add activity
                self.add_activity(
                    member_id=member_id,
                    source_type=source_type,
                    activity_type=activity['activity_type'],
                    timestamp=activity['timestamp'],
                    metadata=activity.get('metadata', {}),
                    activity_id=activity.get('activity_id')
                )
                
                stats['activities_added'] += 1
                
            except Exception as e:
                print(f"⚠️  Error adding activity: {e}")
                stats['errors'] += 1
        
        return stats

