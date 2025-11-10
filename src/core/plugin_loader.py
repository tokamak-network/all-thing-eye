"""Plugin loader system for automatic plugin discovery and management"""

import importlib
import pkgutil
from typing import List, Dict, Type
from pathlib import Path

from ..plugins.base import DataSourcePlugin
from .config import Config
from .database import DatabaseManager


class PluginLoader:
    """
    Automatically discover and load data source plugins
    
    Plugins are Python modules in the src/plugins/ directory
    that inherit from DataSourcePlugin.
    """
    
    def __init__(self, config: Config, db_manager: DatabaseManager):
        """
        Initialize plugin loader
        
        Args:
            config: Application configuration
            db_manager: Database manager instance
        """
        self.config = config
        self.db_manager = db_manager
        self.plugins: List[DataSourcePlugin] = []
        self.plugin_classes: Dict[str, Type[DataSourcePlugin]] = {}
    
    def discover_plugins(self) -> List[str]:
        """
        Discover available plugins in the plugins directory
        
        Returns:
            List of plugin module names
        """
        # Import plugins package
        import src.plugins as plugins_package
        
        plugin_names = []
        
        # Iterate through modules in plugins package
        for _, name, is_pkg in pkgutil.iter_modules(plugins_package.__path__):
            # Skip base module and non-plugin modules
            if name == 'base' or name.startswith('_'):
                continue
            
            # Plugin modules should end with _plugin
            if name.endswith('_plugin'):
                plugin_names.append(name)
        
        return plugin_names
    
    def load_plugin(self, plugin_module_name: str) -> DataSourcePlugin:
        """
        Load a specific plugin by module name
        
        Args:
            plugin_module_name: Name of the plugin module (e.g., 'github_plugin')
            
        Returns:
            Instantiated plugin
            
        Raises:
            ValueError: If plugin class not found or invalid
        """
        # Import the plugin module
        module = importlib.import_module(f'src.plugins.{plugin_module_name}')
        
        # Find DataSourcePlugin subclass in the module
        plugin_class = None
        
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            
            # Check if it's a class and subclass of DataSourcePlugin
            if (
                isinstance(attr, type) and
                issubclass(attr, DataSourcePlugin) and
                attr is not DataSourcePlugin
            ):
                plugin_class = attr
                break
        
        if not plugin_class:
            raise ValueError(f"No DataSourcePlugin subclass found in {plugin_module_name}")
        
        # Get plugin config
        # Extract plugin name from module name (remove _plugin suffix)
        plugin_name = plugin_module_name.replace('_plugin', '')
        plugin_config = self.config.get_plugin_config(plugin_name)
        
        # Check if plugin is enabled
        if not plugin_config.get('enabled', False):
            print(f"⏭️  Plugin '{plugin_name}' is disabled in config")
            raise ValueError(f"Plugin '{plugin_name}' is disabled")
        
        # Instantiate plugin
        plugin = plugin_class(plugin_config)
        
        # Validate configuration
        if not plugin.validate_config():
            raise ValueError(f"Plugin '{plugin_name}' has invalid configuration")
        
        # Store plugin class for future reference
        self.plugin_classes[plugin_name] = plugin_class
        
        print(f"✅ Loaded plugin: {plugin.get_source_name()}")
        return plugin
    
    def load_all_plugins(self) -> List[DataSourcePlugin]:
        """
        Discover and load all available plugins
        
        Returns:
            List of successfully loaded plugins
        """
        print("\n🔌 Loading plugins...")
        
        plugin_names = self.discover_plugins()
        print(f"📦 Discovered {len(plugin_names)} plugins: {', '.join(plugin_names)}")
        
        loaded_plugins = []
        
        for plugin_name in plugin_names:
            try:
                plugin = self.load_plugin(plugin_name)
                
                # Create database schema for plugin
                source_name = plugin.get_source_name()
                schema = plugin.get_db_schema()
                self.db_manager.create_source_database(source_name, schema)
                
                loaded_plugins.append(plugin)
                self.plugins.append(plugin)
                
            except ValueError as e:
                # Expected errors (disabled, invalid config)
                continue
            except Exception as e:
                print(f"❌ Failed to load plugin '{plugin_name}': {e}")
                continue
        
        print(f"\n✅ Successfully loaded {len(loaded_plugins)} plugins\n")
        return loaded_plugins
    
    def get_plugin(self, source_name: str) -> DataSourcePlugin:
        """
        Get a loaded plugin by source name
        
        Args:
            source_name: Name of the data source
            
        Returns:
            Plugin instance
            
        Raises:
            KeyError: If plugin not found
        """
        for plugin in self.plugins:
            if plugin.get_source_name() == source_name:
                return plugin
        
        raise KeyError(f"Plugin '{source_name}' not found or not loaded")
    
    def get_enabled_plugins(self) -> List[str]:
        """Get list of enabled plugin names from config"""
        enabled = []
        
        plugins_config = self.config.get('plugins', {})
        for plugin_name, plugin_config in plugins_config.items():
            if isinstance(plugin_config, dict) and plugin_config.get('enabled', False):
                enabled.append(plugin_name)
        
        return enabled
    
    def reload_plugin(self, plugin_name: str) -> DataSourcePlugin:
        """
        Reload a specific plugin
        
        Args:
            plugin_name: Name of the plugin (without _plugin suffix)
            
        Returns:
            Reloaded plugin instance
        """
        # Remove old plugin
        self.plugins = [p for p in self.plugins if p.get_source_name() != plugin_name]
        
        # Reload module
        module_name = f"{plugin_name}_plugin"
        plugin = self.load_plugin(module_name)
        self.plugins.append(plugin)
        
        print(f"🔄 Reloaded plugin: {plugin_name}")
        return plugin
    
    def __repr__(self) -> str:
        plugin_names = [p.get_source_name() for p in self.plugins]
        return f"PluginLoader(loaded={plugin_names})"

