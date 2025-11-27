#!/usr/bin/env python3
"""
Migration script to add member_id field to all activity collections.

This script:
1. Loads member mappings from member_identifiers collection
2. Adds member_id field to each activity based on source-specific identifiers
3. Enables unified filtering by member_id across all sources

Usage:
    python scripts/add_member_id_to_activities.py [--dry-run]
"""

import os
import sys
from datetime import datetime
from pymongo import MongoClient, UpdateMany
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE')


def get_member_mappings(db):
    """
    Build reverse lookup mappings from member_identifiers.
    
    Returns:
        Dict with structure: {
            'github': {'SonYoungsung': 'Ale', 'ggs134': 'Kevin', ...},
            'slack': {'U04DNT2QS31': 'Ale', 'kevin': 'Kevin', ...},
            'notion': {'c5f84a10-...': 'Ale', ...},
            'drive': {'ale@tokamak.network': 'Ale', ...}
        }
    """
    mappings = {
        'github': {},
        'slack': {},
        'notion': {},
        'drive': {}
    }
    
    for doc in db['member_identifiers'].find({}):
        source = doc.get('source')
        identifier = doc.get('identifier_value')
        member_name = doc.get('member_name')
        
        if source and identifier and member_name:
            # Case-insensitive key for github (username matching)
            if source == 'github':
                mappings[source][identifier.lower()] = member_name
                mappings[source][identifier] = member_name  # Also keep original case
            else:
                mappings[source][identifier] = member_name
    
    return mappings


def get_slack_user_mappings(db):
    """
    Build additional Slack mappings from actual message data.
    Maps user_id and user_name to member names.
    """
    mappings = {}
    
    # Get unique user combinations from slack_messages
    pipeline = [
        {'$group': {
            '_id': {
                'user_id': '$user_id',
                'user_name': '$user_name'
            }
        }}
    ]
    
    for doc in db['slack_messages'].aggregate(pipeline):
        user_id = doc['_id'].get('user_id')
        user_name = doc['_id'].get('user_name')
        
        if user_name:
            # Capitalize user_name to match member_name format
            member_name = user_name.capitalize()
            if user_id:
                mappings[user_id] = member_name
            mappings[user_name.lower()] = member_name
    
    return mappings


def get_notion_user_mappings(db):
    """
    Build Notion mappings from created_by.name field.
    Maps UUID and name to member names.
    """
    mappings = {}
    
    # Get unique created_by combinations
    pipeline = [
        {'$group': {
            '_id': {
                'id': '$created_by.id',
                'name': '$created_by.name'
            }
        }}
    ]
    
    for doc in db['notion_pages'].aggregate(pipeline):
        uuid = doc['_id'].get('id')
        name = doc['_id'].get('name')
        
        if uuid:
            if name:
                # Use first name as member_name
                first_name = name.split()[0] if ' ' in name else name
                mappings[uuid] = first_name.capitalize()
            else:
                # No name available, mark as unknown
                mappings[uuid] = None
    
    return mappings


def migrate_github_commits(db, mappings, dry_run=False):
    """Add member_id to github_commits collection."""
    collection = db['github_commits']
    total = collection.count_documents({})
    updated = 0
    not_found = []
    
    print(f"\n=== GitHub Commits ({total} documents) ===")
    
    github_mappings = mappings['github']
    
    for doc in collection.find({'member_id': {'$exists': False}}):
        author_name = doc.get('author_name', '')
        
        # Try exact match first, then lowercase
        member_id = github_mappings.get(author_name)
        if not member_id:
            member_id = github_mappings.get(author_name.lower())
        
        if member_id:
            if not dry_run:
                collection.update_one(
                    {'_id': doc['_id']},
                    {'$set': {'member_id': member_id}}
                )
            updated += 1
        else:
            if author_name not in not_found:
                not_found.append(author_name)
    
    print(f"  Updated: {updated}")
    if not_found:
        print(f"  Not found: {not_found[:10]}{'...' if len(not_found) > 10 else ''}")
    
    return updated


def migrate_github_prs(db, mappings, dry_run=False):
    """Add member_id to github_pull_requests collection."""
    collection = db['github_pull_requests']
    total = collection.count_documents({})
    updated = 0
    not_found = []
    
    print(f"\n=== GitHub Pull Requests ({total} documents) ===")
    
    github_mappings = mappings['github']
    
    for doc in collection.find({'member_id': {'$exists': False}}):
        author = doc.get('author', '')
        
        member_id = github_mappings.get(author)
        if not member_id:
            member_id = github_mappings.get(author.lower())
        
        if member_id:
            if not dry_run:
                collection.update_one(
                    {'_id': doc['_id']},
                    {'$set': {'member_id': member_id}}
                )
            updated += 1
        else:
            if author not in not_found:
                not_found.append(author)
    
    print(f"  Updated: {updated}")
    if not_found:
        print(f"  Not found: {not_found[:10]}{'...' if len(not_found) > 10 else ''}")
    
    return updated


def migrate_slack_messages(db, mappings, slack_user_mappings, dry_run=False):
    """Add member_id to slack_messages collection."""
    collection = db['slack_messages']
    total = collection.count_documents({})
    updated = 0
    not_found = []
    
    print(f"\n=== Slack Messages ({total} documents) ===")
    
    slack_id_mappings = mappings['slack']
    
    for doc in collection.find({'member_id': {'$exists': False}}):
        user_id = doc.get('user_id', '')
        user_name = doc.get('user_name', '')
        
        # Try multiple lookups
        member_id = None
        
        # 1. Try user_id in member_identifiers
        if user_id:
            member_id = slack_id_mappings.get(user_id)
        
        # 2. Try user_name in slack_user_mappings
        if not member_id and user_name:
            member_id = slack_user_mappings.get(user_name.lower())
        
        # 3. Fallback: capitalize user_name
        if not member_id and user_name:
            member_id = user_name.capitalize()
        
        if member_id:
            if not dry_run:
                collection.update_one(
                    {'_id': doc['_id']},
                    {'$set': {'member_id': member_id}}
                )
            updated += 1
        else:
            key = f"{user_id}:{user_name}"
            if key not in not_found:
                not_found.append(key)
    
    print(f"  Updated: {updated}")
    if not_found:
        print(f"  Not found: {not_found[:10]}{'...' if len(not_found) > 10 else ''}")
    
    return updated


def migrate_notion_pages(db, mappings, notion_user_mappings, dry_run=False):
    """Add member_id to notion_pages collection."""
    collection = db['notion_pages']
    total = collection.count_documents({})
    updated = 0
    not_found = []
    
    print(f"\n=== Notion Pages ({total} documents) ===")
    
    notion_id_mappings = mappings['notion']
    
    for doc in collection.find({'member_id': {'$exists': False}}):
        created_by = doc.get('created_by', {})
        uuid = created_by.get('id', '')
        name = created_by.get('name', '')
        
        member_id = None
        
        # 1. Try UUID in member_identifiers
        if uuid:
            member_id = notion_id_mappings.get(uuid)
        
        # 2. Try UUID in notion_user_mappings
        if not member_id and uuid:
            member_id = notion_user_mappings.get(uuid)
        
        # 3. Try extracting from name
        if not member_id and name:
            first_name = name.split()[0] if ' ' in name else name
            member_id = first_name.capitalize()
        
        if member_id:
            if not dry_run:
                collection.update_one(
                    {'_id': doc['_id']},
                    {'$set': {'member_id': member_id}}
                )
            updated += 1
        else:
            if uuid not in not_found:
                not_found.append(uuid[:8] + '...')
    
    print(f"  Updated: {updated}")
    if not_found:
        print(f"  Not found (UUIDs): {not_found[:10]}{'...' if len(not_found) > 10 else ''}")
    
    return updated


def migrate_drive_activities(db, mappings, dry_run=False):
    """Add member_id to drive_activities collection."""
    collection = db['drive_activities']
    total = collection.count_documents({})
    updated = 0
    not_found = []
    
    print(f"\n=== Drive Activities ({total} documents) ===")
    
    drive_mappings = mappings['drive']
    
    for doc in collection.find({'member_id': {'$exists': False}}):
        user_email = doc.get('user_email', '')
        
        # Try email lookup
        member_id = drive_mappings.get(user_email.lower()) if user_email else None
        
        # Fallback: extract username from email
        if not member_id and user_email and '@' in user_email:
            username = user_email.split('@')[0]
            member_id = username.capitalize()
        
        if member_id:
            if not dry_run:
                collection.update_one(
                    {'_id': doc['_id']},
                    {'$set': {'member_id': member_id}}
                )
            updated += 1
        else:
            if user_email not in not_found:
                not_found.append(user_email)
    
    print(f"  Updated: {updated}")
    if not_found:
        print(f"  Not found: {not_found[:10]}{'...' if len(not_found) > 10 else ''}")
    
    return updated


def main():
    dry_run = '--dry-run' in sys.argv
    
    if dry_run:
        print("=" * 60)
        print("DRY RUN MODE - No changes will be made")
        print("=" * 60)
    
    print(f"\nConnecting to MongoDB...")
    client = MongoClient(MONGODB_URI)
    db = client[MONGODB_DATABASE]
    
    print(f"Database: {MONGODB_DATABASE}")
    print(f"Started at: {datetime.now()}")
    
    # Load mappings
    print("\nLoading member mappings...")
    mappings = get_member_mappings(db)
    print(f"  GitHub: {len(mappings['github'])} identifiers")
    print(f"  Slack: {len(mappings['slack'])} identifiers")
    print(f"  Notion: {len(mappings['notion'])} identifiers")
    print(f"  Drive: {len(mappings['drive'])} identifiers")
    
    # Load additional mappings from actual data
    slack_user_mappings = get_slack_user_mappings(db)
    print(f"  Slack (from messages): {len(slack_user_mappings)} users")
    
    notion_user_mappings = get_notion_user_mappings(db)
    print(f"  Notion (from pages): {len(notion_user_mappings)} users")
    
    # Migrate each collection
    total_updated = 0
    
    total_updated += migrate_github_commits(db, mappings, dry_run)
    total_updated += migrate_github_prs(db, mappings, dry_run)
    total_updated += migrate_slack_messages(db, mappings, slack_user_mappings, dry_run)
    total_updated += migrate_notion_pages(db, mappings, notion_user_mappings, dry_run)
    total_updated += migrate_drive_activities(db, mappings, dry_run)
    
    print("\n" + "=" * 60)
    print(f"TOTAL UPDATED: {total_updated}")
    print(f"Completed at: {datetime.now()}")
    
    if dry_run:
        print("\nThis was a dry run. Run without --dry-run to apply changes.")
    else:
        print("\nMigration complete! All activities now have member_id field.")
    
    client.close()


if __name__ == '__main__':
    main()

