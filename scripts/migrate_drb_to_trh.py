#!/usr/bin/env python3
"""
Migration script to merge DRB project data into TRH project

This script:
1. Updates Slack messages from project-drb channel to project_trh
2. Updates Slack channels metadata
3. Updates any project-specific metadata in other collections
"""

import os
import sys
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection
mongodb_uri = os.getenv("MONGODB_URI")
mongodb_db = os.getenv("MONGODB_DATABASE", "ati")

if not mongodb_uri:
    print("Error: MONGODB_URI not set in environment")
    sys.exit(1)

print(f"Connecting to MongoDB: {mongodb_uri[:30]}...")
print(f"Database: {mongodb_db}")

client = MongoClient(mongodb_uri)
db = client[mongodb_db]

# DRB and TRH channel names
DRB_CHANNEL_NAME = "project-drb"
TRH_CHANNEL_NAME = "project_trh"

def migrate_slack_messages():
    """Migrate Slack messages from DRB channel to TRH"""
    print("\n=== Migrating Slack Messages ===")
    
    messages_collection = db["slack_messages"]
    
    # Find all messages in DRB channel
    drb_messages = list(messages_collection.find({"channel_name": DRB_CHANNEL_NAME}))
    print(f"Found {len(drb_messages)} messages in {DRB_CHANNEL_NAME} channel")
    
    if not drb_messages:
        print("No DRB messages to migrate")
        return 0
    
    # Update channel_name to TRH
    result = messages_collection.update_many(
        {"channel_name": DRB_CHANNEL_NAME},
        {
            "$set": {
                "channel_name": TRH_CHANNEL_NAME,
                "migrated_from_drb": True,
                "migrated_at": datetime.utcnow()
            }
        }
    )
    
    print(f"✅ Updated {result.modified_count} messages from {DRB_CHANNEL_NAME} to {TRH_CHANNEL_NAME}")
    return result.modified_count


def migrate_slack_channels():
    """
    Update Slack channels: Make DRB channel identical to TRH
    - channel_id remains unchanged (Slack's actual channel ID)
    - channel_name: project-drb → project_trh (to match TRH)
    - All metadata updated to reflect TRH project
    """
    print("\n=== Migrating Slack Channels ===")
    
    channels_collection = db["slack_channels"]
    
    # Find DRB channel
    drb_channel = channels_collection.find_one({"name": DRB_CHANNEL_NAME})
    
    if not drb_channel:
        print(f"No channel found with name: {DRB_CHANNEL_NAME}")
        return 0
    
    drb_channel_id = drb_channel.get('channel_id')
    print(f"Found DRB channel: {drb_channel_id} ({drb_channel.get('name')})")
    
    # Check if TRH channel exists
    trh_channel = channels_collection.find_one({"name": TRH_CHANNEL_NAME})
    
    if trh_channel:
        trh_channel_id = trh_channel.get('channel_id')
        print(f"TRH channel already exists: {trh_channel_id} ({trh_channel.get('name')})")
        print(f"⚠️  Note: Both channels will be treated as TRH project")
        print(f"   DRB channel_id: {drb_channel_id}")
        print(f"   TRH channel_id: {trh_channel_id}")
    
    # Update DRB channel name to match TRH (make them identical for filtering)
    # channel_id stays the same (it's Slack's actual channel ID)
    result = channels_collection.update_one(
        {"name": DRB_CHANNEL_NAME},
        {
            "$set": {
                "name": TRH_CHANNEL_NAME,  # Change name to match TRH
                "parent_project": "project-trh",
                "is_sub_project": True,
                "migrated_from_drb": True,
                "migrated_at": datetime.utcnow()
            }
        }
    )
    
    print(f"✅ Updated DRB channel to be identical to TRH (name changed, channel_id preserved)")
    return result.modified_count if result else 0


def migrate_member_activities():
    """Update member_activities if they reference DRB project"""
    print("\n=== Migrating Member Activities ===")
    
    activities_collection = db["member_activities"]
    
    # Find activities with DRB project reference
    drb_activities = list(activities_collection.find({
        "$or": [
            {"project": "project-drb"},
            {"project": "DRB"},
            {"metadata.project": "project-drb"},
            {"metadata.project": "DRB"}
        ]
    }))
    
    print(f"Found {len(drb_activities)} activities referencing DRB project")
    
    if not drb_activities:
        print("No DRB activities to migrate")
        return 0
    
    # Update to TRH
    result = activities_collection.update_many(
        {
            "$or": [
                {"project": "project-drb"},
                {"project": "DRB"},
                {"metadata.project": "project-drb"},
                {"metadata.project": "DRB"}
            ]
        },
        {
            "$set": {
                "project": "project-trh",
                "migrated_from_drb": True,
                "migrated_at": datetime.utcnow()
            }
        }
    )
    
    print(f"✅ Updated {result.modified_count} activities from DRB to TRH")
    return result.modified_count


def verify_migration():
    """Verify migration results"""
    print("\n=== Verification ===")
    
    messages_collection = db["slack_messages"]
    channels_collection = db["slack_channels"]
    
    # Check remaining DRB messages
    remaining_drb_messages = messages_collection.count_documents({"channel_name": DRB_CHANNEL_NAME})
    trh_messages = messages_collection.count_documents({"channel_name": TRH_CHANNEL_NAME})
    
    print(f"Remaining DRB messages: {remaining_drb_messages}")
    print(f"Total TRH messages: {trh_messages}")
    
    # Check channels
    drb_channel = channels_collection.find_one({"name": DRB_CHANNEL_NAME})
    trh_channel = channels_collection.find_one({"name": TRH_CHANNEL_NAME})
    
    print(f"DRB channel exists: {drb_channel is not None}")
    print(f"TRH channel exists: {trh_channel is not None}")
    
    if drb_channel:
        print(f"  DRB channel metadata: {drb_channel.get('parent_project', 'N/A')}")
    
    return {
        "remaining_drb_messages": remaining_drb_messages,
        "trh_messages": trh_messages,
        "drb_channel_exists": drb_channel is not None,
        "trh_channel_exists": trh_channel is not None
    }


def main():
    """Main migration function"""
    print("=" * 60)
    print("DRB to TRH Migration Script")
    print("=" * 60)
    print(f"Started at: {datetime.now()}")
    
    # Confirm before proceeding
    print("\n⚠️  This will migrate DRB project data to TRH project.")
    print("   - Slack messages from 'project-drb' → 'project_trh'")
    print("   - Slack channels metadata updates")
    print("   - Member activities project references")
    
    response = input("\nDo you want to proceed? (yes/no): ").strip().lower()
    if response != "yes":
        print("Migration cancelled.")
        return
    
    try:
        # Run migrations
        messages_updated = migrate_slack_messages()
        channels_updated = migrate_slack_channels()
        activities_updated = migrate_member_activities()
        
        # Verify
        verification = verify_migration()
        
        print("\n" + "=" * 60)
        print("Migration Summary")
        print("=" * 60)
        print(f"Slack messages updated: {messages_updated}")
        print(f"Slack channels updated: {channels_updated}")
        print(f"Member activities updated: {activities_updated}")
        print(f"\nCompleted at: {datetime.now()}")
        
        if verification["remaining_drb_messages"] == 0:
            print("\n✅ Migration completed successfully!")
        else:
            print(f"\n⚠️  Warning: {verification['remaining_drb_messages']} DRB messages still remain")
        
    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()

