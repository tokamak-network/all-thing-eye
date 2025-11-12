"""Configuration management system"""

import os
from pathlib import Path
from typing import Any, Dict, Optional, List
import yaml
import json
import csv
from dotenv import load_dotenv


class Config:
    """Configuration manager for the application"""

    def __init__(self, config_path: Optional[str] = None, members_path: Optional[str] = None):
        """
        Initialize configuration
        
        Args:
            config_path: Path to config YAML file. If None, uses default config/config.yaml
            members_path: Path to members file. If None, auto-detects from config directory
        """
        # Project root directory
        self.project_root = Path(__file__).parent.parent.parent
        
        # Load environment variables from project root
        env_path = self.project_root / '.env'
        load_dotenv(dotenv_path=env_path)
        
        if env_path.exists():
            print(f"✅ Loaded environment variables from: {env_path}")
        else:
            print(f"⚠️  .env file not found at: {env_path}")
        
        # Load YAML config
        if config_path is None:
            config_path = self.project_root / "config" / "config.yaml"
        
        self.config_path = Path(config_path)
        self._config = self._load_yaml_config()
        
        # Apply environment variable substitutions
        self._substitute_env_vars(self._config)
        
        # Load members list
        self.members_path = members_path
        self._load_members()
    
    def _load_yaml_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def _substitute_env_vars(self, config: Any) -> None:
        """
        Recursively substitute environment variables in config
        Format: ${VAR_NAME:default_value} or ${VAR_NAME}
        """
        if isinstance(config, dict):
            for key, value in config.items():
                if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                    # Extract variable name and default value
                    var_content = value[2:-1]  # Remove ${ and }
                    if ':' in var_content:
                        var_name, default = var_content.split(':', 1)
                    else:
                        var_name, default = var_content, None
                    
                    # Get from environment or use default
                    config[key] = os.getenv(var_name, default)
                elif isinstance(value, (dict, list)):
                    self._substitute_env_vars(value)
        elif isinstance(config, list):
            for item in config:
                self._substitute_env_vars(item)
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated key path
        
        Args:
            key_path: Dot-separated path (e.g., 'database.main_db')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific plugin
        
        Args:
            plugin_name: Name of the plugin (e.g., 'slack', 'github')
            
        Returns:
            Plugin configuration dict
        """
        return self.get(f'plugins.{plugin_name}', {})
    
    @property
    def database_url(self) -> str:
        """Get database URL"""
        return self.get('database.main_db', 'sqlite:///data/databases/main.db')
    
    @property
    def log_level(self) -> str:
        """Get log level"""
        return self.get('logging.level', 'INFO')
    
    @property
    def app_env(self) -> str:
        """Get application environment"""
        return self.get('app.environment', 'development')
    
    def is_plugin_enabled(self, plugin_name: str) -> bool:
        """Check if a plugin is enabled"""
        return self.get(f'plugins.{plugin_name}.enabled', False)
    
    def _load_members(self) -> None:
        """
        Load members list from external file
        
        Supports multiple formats:
        - members.yaml (preferred)
        - members.json
        - members.csv
        
        If file not found, uses member_list from config.yaml
        """
        config_dir = self.config_path.parent
        
        # Try to find members file if not specified
        if self.members_path is None:
            # Check for different file formats
            for ext in ['yaml', 'yml', 'json', 'csv']:
                potential_path = config_dir / f"members.{ext}"
                if potential_path.exists():
                    self.members_path = potential_path
                    break
        
        # If members file found, load it
        if self.members_path and Path(self.members_path).exists():
            members = self._load_members_file(Path(self.members_path))
            
            # Inject members into plugin configs
            if members:
                # For GitHub plugin
                if 'plugins' in self._config and 'github' in self._config['plugins']:
                    github_members = [
                        {
                            'name': m['name'],
                            'githubId': m.get('github_id'),
                            'email': m.get('email')
                        }
                        for m in members if m.get('github_id')
                    ]
                    self._config['plugins']['github']['member_list'] = github_members
                
                # For Slack plugin
                if 'plugins' in self._config and 'slack' in self._config['plugins']:
                    slack_members = [
                        {
                            'name': m['name'],
                            'slackId': m.get('slack_id'),
                            'email': m.get('email')
                        }
                        for m in members if m.get('slack_id') or m.get('email')
                    ]
                    self._config['plugins']['slack']['member_list'] = slack_members
                
                # For Notion plugin
                if 'plugins' in self._config and 'notion' in self._config['plugins']:
                    notion_members = [
                        {
                            'name': m['name'],
                            'notionId': m.get('notion_id'),
                            'email': m.get('email')
                        }
                        for m in members if m.get('notion_id')
                    ]
                    self._config['plugins']['notion']['member_list'] = notion_members
                
                # For Google Drive plugin
                if 'plugins' in self._config and 'google_drive' in self._config['plugins']:
                    google_drive_members = [
                        {
                            'name': m['name'],
                            'googleEmail': m.get('google_email') or m.get('email'),  # Fallback to email
                            'email': m.get('email')
                        }
                        for m in members if m.get('google_email') or m.get('email')
                    ]
                    self._config['plugins']['google_drive']['member_list'] = google_drive_members
                
                print(f"✅ Loaded {len(members)} members from {self.members_path.name}")
    
    def _load_members_file(self, path: Path) -> List[Dict[str, Any]]:
        """
        Load members from file (YAML, JSON, or CSV)
        
        Args:
            path: Path to members file
            
        Returns:
            List of member dictionaries
        """
        suffix = path.suffix.lower()
        
        try:
            if suffix in ['.yaml', '.yml']:
                with open(path, 'r', encoding='utf-8') as f:
                    members = yaml.safe_load(f) or []
                    return members if isinstance(members, list) else []
            
            elif suffix == '.json':
                with open(path, 'r', encoding='utf-8') as f:
                    members = json.load(f)
                    return members if isinstance(members, list) else []
            
            elif suffix == '.csv':
                members = []
                with open(path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Convert empty strings to None
                        member = {k: (v if v else None) for k, v in row.items()}
                        members.append(member)
                return members
            
            else:
                print(f"⚠️  Unsupported members file format: {suffix}")
                return []
        
        except Exception as e:
            print(f"⚠️  Failed to load members from {path}: {e}")
            return []
    
    def get_members(self) -> List[Dict[str, Any]]:
        """
        Get all members from loaded configuration
        
        Returns:
            List of member dictionaries with all identifiers
        """
        if self.members_path and Path(self.members_path).exists():
            return self._load_members_file(Path(self.members_path))
        
        # Fallback: try to get from config
        members = []
        
        # Collect from all plugin configs
        for plugin_name in ['github', 'slack', 'notion']:
            plugin_members = self.get(f'plugins.{plugin_name}.member_list', [])
            if plugin_members:
                members.extend(plugin_members)
        
        return members
    
    def __repr__(self) -> str:
        members_info = f", members={self.members_path.name}" if self.members_path else ""
        return f"Config(config_path={self.config_path}{members_info})"


# Global config instance
_config_instance: Optional[Config] = None


def get_config(config_path: Optional[str] = None) -> Config:
    """
    Get global config instance (singleton)
    
    Args:
        config_path: Path to config file (only used on first call)
        
    Returns:
        Config instance
    """
    global _config_instance
    
    if _config_instance is None:
        _config_instance = Config(config_path)
    
    return _config_instance


def reload_config(config_path: Optional[str] = None) -> Config:
    """
    Reload configuration (useful for testing or config changes)
    
    Args:
        config_path: Path to config file
        
    Returns:
        New Config instance
    """
    global _config_instance
    _config_instance = Config(config_path)
    return _config_instance

