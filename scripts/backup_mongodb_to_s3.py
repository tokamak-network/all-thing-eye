#!/usr/bin/env python3
"""
MongoDB Backup Script (S3)

Creates a backup of MongoDB collections and uploads to AWS S3.
This is the safest option for AWS deployments.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import subprocess
import tempfile
import shutil

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

def get_s3_bucket() -> str:
    """Get S3 bucket name from environment"""
    bucket = os.getenv("S3_BACKUP_BUCKET")
    if not bucket:
        print("⚠️  S3_BACKUP_BUCKET not set, will use local backup only")
    return bucket

def create_backup_to_s3():
    """Create MongoDB backup and upload to S3"""
    print("=" * 60)
    print("MongoDB Backup Script (S3)")
    print("=" * 60)
    print(f"Started at: {datetime.now()}\n")
    
    # Get MongoDB connection info
    uri = get_mongodb_uri()
    database_name = get_mongodb_database()
    s3_bucket = get_s3_bucket()
    
    print(f"Database: {database_name}")
    print(f"URI: {uri.split('@')[-1] if '@' in uri else uri}")
    if s3_bucket:
        print(f"S3 Bucket: {s3_bucket}")
    print()
    
    # Create temporary backup directory
    temp_backup_dir = Path(tempfile.mkdtemp(prefix="mongodb_backup_"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"Temporary backup directory: {temp_backup_dir}\n")
    
    # Collections to backup
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
        print("Starting mongodump...\n")
        
        cmd = [
            "mongodump",
            "--uri", uri,
            "--db", database_name,
            "--out", str(temp_backup_dir)
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
        
        print("✅ mongodump completed successfully!")
        
        # Create compressed archive
        archive_name = f"mongodb_backup_{database_name}_{timestamp}.tar.gz"
        archive_path = temp_backup_dir.parent / archive_name
        
        print(f"\nCreating archive: {archive_name}...")
        subprocess.run(
            ["tar", "-czf", str(archive_path), "-C", str(temp_backup_dir), database_name],
            check=True
        )
        
        archive_size = archive_path.stat().st_size / (1024 * 1024)  # MB
        print(f"✅ Archive created: {archive_size:.2f} MB")
        
        # Upload to S3 if bucket is configured
        if s3_bucket:
            print(f"\nUploading to S3: s3://{s3_bucket}/{archive_name}...")
            
            # Check if AWS CLI is available
            try:
                subprocess.run(
                    ["aws", "s3", "cp", str(archive_path), f"s3://{s3_bucket}/{archive_name}"],
                    check=True,
                    capture_output=True
                )
                print(f"✅ Uploaded to S3: s3://{s3_bucket}/{archive_name}")
                
                # Also save local copy in backups directory
                local_backup_dir = project_root / "backups"
                local_backup_dir.mkdir(exist_ok=True)
                local_backup_path = local_backup_dir / archive_name
                shutil.copy2(archive_path, local_backup_path)
                print(f"✅ Local copy saved: {local_backup_path}")
                
            except FileNotFoundError:
                print("⚠️  AWS CLI not found, skipping S3 upload")
                print("   Install: pip install awscli or brew install awscli")
                # Save to local backups directory
                local_backup_dir = project_root / "backups"
                local_backup_dir.mkdir(exist_ok=True)
                local_backup_path = local_backup_dir / archive_name
                shutil.copy2(archive_path, local_backup_path)
                print(f"✅ Saved to local backups: {local_backup_path}")
            except subprocess.CalledProcessError as e:
                print(f"⚠️  S3 upload failed: {e.stderr}")
                # Still save locally
                local_backup_dir = project_root / "backups"
                local_backup_dir.mkdir(exist_ok=True)
                local_backup_path = local_backup_dir / archive_name
                shutil.copy2(archive_path, local_backup_path)
                print(f"✅ Saved to local backups: {local_backup_path}")
        else:
            # No S3 bucket, save to local backups directory
            local_backup_dir = project_root / "backups"
            local_backup_dir.mkdir(exist_ok=True)
            local_backup_path = local_backup_dir / archive_name
            shutil.copy2(archive_path, local_backup_path)
            print(f"✅ Saved to local backups: {local_backup_path}")
        
        # Cleanup temporary directory
        print(f"\nCleaning up temporary files...")
        shutil.rmtree(temp_backup_dir)
        if archive_path.exists():
            archive_path.unlink()
        
        print("\n" + "=" * 60)
        print("Backup Summary")
        print("=" * 60)
        print(f"Backup ID: {timestamp}")
        print(f"Archive: {archive_name}")
        print(f"Size: {archive_size:.2f} MB")
        if s3_bucket:
            print(f"S3 Location: s3://{s3_bucket}/{archive_name}")
        print(f"\nTo restore:")
        print(f"  tar -xzf {archive_name}")
        print(f"  mongorestore --uri <uri> --db {database_name} {database_name}/")
        
        print(f"\n✅ Backup completed at: {datetime.now()}")
        
        return archive_name
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Backup failed!")
        print(f"Error: {e.stderr}")
        return None
    except FileNotFoundError as e:
        if "mongodump" in str(e):
            print("\n❌ mongodump not found!")
            print("Please install MongoDB Database Tools:")
            print("  macOS: brew install mongodb-database-tools")
            print("  Linux: https://www.mongodb.com/try/download/database-tools")
        else:
            print(f"\n❌ Error: {e}")
        return None
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # Always cleanup temp directory
        if temp_backup_dir.exists():
            try:
                shutil.rmtree(temp_backup_dir)
            except:
                pass

if __name__ == "__main__":
    try:
        archive_name = create_backup_to_s3()
        if archive_name:
            print(f"\n✅ Backup completed: {archive_name}")
            sys.exit(0)
        else:
            print(f"\n⚠️  Backup failed")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Backup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

