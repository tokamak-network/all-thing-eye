#!/usr/bin/env python3
"""
MongoDB Backup Script

Creates a backup of MongoDB collections before major migrations or changes.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import subprocess

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

def create_backup():
    """Create MongoDB backup using mongodump"""
    print("=" * 60)
    print("MongoDB Backup Script")
    print("=" * 60)
    print(f"Started at: {datetime.now()}\n")
    
    # Get MongoDB connection info
    uri = get_mongodb_uri()
    database_name = get_mongodb_database()
    
    # Parse URI to extract host, port, username, password
    # Format: mongodb://[username:password@]host[:port][/database][?options]
    print(f"Database: {database_name}")
    print(f"URI: {uri.split('@')[-1] if '@' in uri else uri}\n")  # Hide credentials
    
    # Create backup directory
    backup_dir = project_root / "backups"
    backup_dir.mkdir(exist_ok=True)
    
    # Create timestamped backup directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"mongodb_backup_{timestamp}"
    backup_path.mkdir(exist_ok=True)
    
    print(f"Backup directory: {backup_path}\n")
    
    # Collections to backup (important ones)
    important_collections = [
        "projects",  # New collection we're creating
        "slack_messages",
        "slack_channels",
        "github_commits",
        "github_pull_requests",
        "notion_pages",
        "drive_activities",
        "members",
        "member_identifiers",
        "member_activities"
    ]
    
    try:
        # Use mongodump to backup specific collections
        print("Starting backup...\n")
        
        # Build mongodump command
        cmd = [
            "mongodump",
            "--uri", uri,
            "--db", database_name,
            "--out", str(backup_path)
        ]
        
        # Add collection filters
        for collection in important_collections:
            cmd.extend(["--collection", collection])
        
        # Execute mongodump
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        print("✅ Backup completed successfully!")
        print(f"\nBackup location: {backup_path}")
        print(f"\nTo restore this backup, use:")
        print(f"  mongorestore --uri {uri} --db {database_name} {backup_path}/{database_name}")
        
        # Create a restore script for convenience
        restore_script = backup_dir / f"restore_{timestamp}.sh"
        with open(restore_script, "w") as f:
            f.write("#!/bin/bash\n")
            f.write(f"# Restore script for backup: {timestamp}\n")
            f.write(f"mongorestore --uri '{uri}' --db {database_name} {backup_path}/{database_name}\n")
        
        restore_script.chmod(0o755)
        print(f"\nRestore script created: {restore_script}")
        
        return backup_path
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Backup failed!")
        print(f"Error: {e.stderr}")
        return None
    except FileNotFoundError:
        print("\n❌ mongodump not found!")
        print("Please install MongoDB Database Tools:")
        print("  macOS: brew install mongodb-database-tools")
        print("  Linux: https://www.mongodb.com/try/download/database-tools")
        return None
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    try:
        backup_path = create_backup()
        if backup_path:
            print(f"\n✅ Backup completed at: {datetime.now()}")
            sys.exit(0)
        else:
            print(f"\n⚠️  Backup failed at: {datetime.now()}")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Backup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

