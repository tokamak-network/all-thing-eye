#!/usr/bin/env python3
"""
Sync project repositories from GitHub Teams (without collecting member data)

This script only syncs the repositories field for each project.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.core.config import Config
from src.core.mongo_manager import MongoDBManager, get_mongo_manager
from src.plugins.github_plugin_mongo import GitHubPluginMongo

def sync_repositories():
    """Sync repositories for all projects"""
    print("=" * 80)
    print("🔄 SYNCING PROJECT REPOSITORIES FROM GITHUB TEAMS")
    print("=" * 80)
    
    # Load config
    config = Config()
    
    # Initialize MongoDB
    mongodb_config = config.get('mongodb', {})
    mongo_manager = get_mongo_manager(mongodb_config)
    
    # Initialize GitHub plugin
    plugin_config = config.get_plugin_config('github')
    if not plugin_config or not plugin_config.get('enabled', False):
        print("❌ GitHub plugin is not enabled in config.yaml")
        return
    
    plugin = GitHubPluginMongo(plugin_config, mongo_manager)
    
    if not plugin.authenticate():
        print("❌ GitHub authentication failed")
        return
    
    print(f"\n✅ GitHub authenticated")
    print(f"   Organization: {plugin.org_name}\n")
    
    # Sync repositories
    try:
        synced_count = plugin._sync_project_repositories()
        
        print(f"\n{'=' * 80}")
        print(f"✅ SYNC COMPLETE")
        print(f"{'=' * 80}")
        print(f"\n   Projects synced: {synced_count}")
        
        # Verify in MongoDB
        print(f"\n🔍 Verifying projects in MongoDB:\n")
        
        db = mongo_manager.db
        projects = list(db['projects'].find({'is_active': True}))
        
        for project in projects:
            repos = project.get('repositories', [])
            synced_at = project.get('repositories_synced_at', 'Never')
            print(f"   • {project.get('name')} ({project.get('key')})")
            print(f"      Repositories: {len(repos)}")
            if repos:
                print(f"      Examples: {', '.join(repos[:3])}")
                if len(repos) > 3:
                    print(f"      ... and {len(repos) - 3} more")
            print(f"      Last synced: {synced_at}")
            print()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    sync_repositories()

