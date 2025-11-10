"""Base plugin interface for all data source plugins"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime


class DataSourcePlugin(ABC):
    """
    Base class for all data source plugins
    
    All plugins must inherit from this class and implement the abstract methods.
    This ensures consistent interface across different data sources.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize plugin with configuration
        
        Args:
            config: Plugin-specific configuration dict
        """
        self.config = config
        self.source_name = self.get_source_name()
        self._authenticated = False
    
    @abstractmethod
    def get_source_name(self) -> str:
        """
        Get the name of this data source
        
        Returns:
            Source name (e.g., 'slack', 'github', 'notion')
        """
        pass
    
    @abstractmethod
    def get_db_schema(self) -> Dict[str, str]:
        """
        Get database schema definition for this source
        
        Returns:
            Dict mapping table names to CREATE TABLE SQL statements
            Example:
            {
                'github_commits': 'CREATE TABLE github_commits (...)',
                'github_prs': 'CREATE TABLE github_prs (...)'
            }
        """
        pass
    
    @abstractmethod
    def authenticate(self) -> bool:
        """
        Authenticate with the data source API
        
        Returns:
            True if authentication successful, False otherwise
        """
        pass
    
    @abstractmethod
    def collect_data(
        self, 
        start_date: datetime, 
        end_date: datetime,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Collect data from the source within the specified date range
        
        Args:
            start_date: Start of collection period
            end_date: End of collection period
            **kwargs: Additional source-specific parameters
            
        Returns:
            List of collected data records
        """
        pass
    
    @abstractmethod
    def get_member_mapping(self) -> Dict[str, str]:
        """
        Get mapping between source user IDs and member identifiers
        
        Returns:
            Dict mapping source user ID to member email/name
            Example:
            {
                'github_user123': 'john@company.com',
                'slack_U123ABC': 'john@company.com'
            }
        """
        pass
    
    @abstractmethod
    def extract_member_activities(
        self, 
        data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract and normalize member activities from collected data
        
        Args:
            data: Raw data collected from the source
            
        Returns:
            List of normalized activity records with format:
            {
                'member_identifier': str,  # email or username
                'activity_type': str,      # e.g., 'commit', 'message', 'pr'
                'timestamp': datetime,
                'metadata': dict           # source-specific data
            }
        """
        pass
    
    @abstractmethod
    def get_required_config_keys(self) -> List[str]:
        """
        Get list of required configuration keys for this plugin
        
        Returns:
            List of required config key names
            Example: ['token', 'org_name', 'workspace_id']
        """
        pass
    
    def validate_config(self) -> bool:
        """
        Validate that all required configuration is present
        
        Returns:
            True if configuration is valid, False otherwise
        """
        required_keys = self.get_required_config_keys()
        
        for key in required_keys:
            if key not in self.config or not self.config[key]:
                print(f"❌ Missing required config key for {self.source_name}: {key}")
                return False
        
        return True
    
    def is_authenticated(self) -> bool:
        """Check if plugin is authenticated"""
        return self._authenticated
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(source={self.source_name})"

