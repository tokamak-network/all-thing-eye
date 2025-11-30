#!/usr/bin/env python3
"""
Migrate projects from config.yaml to MongoDB

This script reads project configurations from config.yaml and stores them
in MongoDB projects collection for dynamic management.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import yaml
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

def get_mongodb_uri() -> str:
    """Get MongoDB URI from environment"""
    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise ValueError("MONGODB_URI environment variable not set")
    return uri

def get_mongodb_database() -> str:
    """Get MongoDB database name from environment"""
    return os.getenv("MONGODB_DATABASE", "ati")

def load_config() -> Dict[str, Any]:
    """Load config.yaml"""
    config_path = project_root / "config" / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}

def migrate_projects():
    """Migrate projects from config.yaml to MongoDB"""
    print("=" * 60)
    print("Projects Migration Script")
    print("=" * 60)
    print(f"Started at: {datetime.now()}\n")
    
    # Load config
    print("Loading config.yaml...")
    config = load_config()
    projects_config = config.get('projects', {})
    
    if not projects_config:
        print("⚠️  No projects found in config.yaml")
        return
    
    print(f"Found {len(projects_config)} projects in config.yaml\n")
    
    # Connect to MongoDB
    print("Connecting to MongoDB...")
    uri = get_mongodb_uri()
    database_name = get_mongodb_database()
    
    client = MongoClient(uri)
    db = client[database_name]
    projects_collection = db["projects"]
    
    # Create unique index on key
    try:
        projects_collection.create_index("key", unique=True)
        print("✅ Created unique index on 'key' field\n")
    except Exception as e:
        print(f"⚠️  Index creation: {e}\n")
    
    # Migrate each project
    migrated = 0
    updated = 0
    errors = 0
    
    for project_key, project_data in projects_config.items():
        try:
            # Skip DRB as it's merged into TRH
            if project_key == "project-drb":
                print(f"⏭️  Skipping {project_key} (merged into TRH)")
                continue
            
            # Prepare project document
            # Only migrate basic fields from config.yaml (name, slack_channel, lead)
            # Other fields will be populated later via MongoDB API
            project_doc = {
                "key": project_key,
                "name": project_data.get("name", project_key),
                "description": None,  # To be updated via API
                "slack_channel": project_data.get("slack_channel"),
                "slack_channel_id": None,  # To be updated via API
                "lead": project_data.get("lead"),
                "repositories": [],  # Will be auto-synced from GitHub Teams
                "repositories_synced_at": None,
                "github_team_slug": project_key,  # Default to project key (for GitHub Teams sync)
                "drive_folders": [],  # To be updated via API
                "notion_page_ids": [],  # Will be populated from Notion structure
                "notion_parent_page_id": None,  # Will be set from Notion "dev Internal" page
                "sub_projects": [],  # To be updated via API (e.g., ["drb"] for TRH)
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # Try to insert or update
            result = projects_collection.update_one(
                {"key": project_key},
                {"$set": project_doc},
                upsert=True
            )
            
            if result.upserted_id:
                migrated += 1
                print(f"✅ Created: {project_key} ({project_data.get('name', project_key)})")
            else:
                updated += 1
                print(f"🔄 Updated: {project_key} ({project_data.get('name', project_key)})")
                
        except Exception as e:
            errors += 1
            print(f"❌ Error migrating {project_key}: {e}")
    
    print("\n" + "=" * 60)
    print("Migration Summary")
    print("=" * 60)
    print(f"Created: {migrated}")
    print(f"Updated: {updated}")
    print(f"Errors: {errors}")
    print(f"\nCompleted at: {datetime.now()}")
    
    if errors == 0:
        print("\n✅ Migration completed successfully!")
    else:
        print(f"\n⚠️  Migration completed with {errors} error(s)")

if __name__ == "__main__":
    try:
        migrate_projects()
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

