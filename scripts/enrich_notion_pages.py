#!/usr/bin/env python3
"""
Enrich Notion Pages with User Names and Emails

This script updates notion_pages collection by enriching created_by and last_edited_by
fields with full user information (name, email) from notion_users collection.

Usage:
    python scripts/enrich_notion_pages.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def enrich_notion_pages(mongo_uri: str, mongo_db: str):
    """
    Enrich notion_pages with user information from notion_users
    
    Args:
        mongo_uri: MongoDB connection URI
        mongo_db: Database name
    """
    try:
        client = AsyncIOMotorClient(mongo_uri)
        db = client[mongo_db]
        
        logger.info("=" * 70)
        logger.info("🔄 Enriching Notion Pages with User Information")
        logger.info("=" * 70)
        
        # Step 1: Build user map from notion_users
        logger.info("\n1️⃣ Building user map from notion_users...")
        user_map = {}
        user_count = 0
        
        async for user in db["notion_users"].find({}):
            user_id = user.get('user_id')
            if user_id:
                user_map[user_id] = {
                    'id': user_id,
                    'name': user.get('name', ''),
                    'email': user.get('email', ''),
                    'type': user.get('type', 'person')
                }
                user_count += 1
        
        logger.info(f"   ✅ Built map for {user_count} users")
        
        if user_count == 0:
            logger.warning("   ⚠️  No users found in notion_users collection")
            logger.warning("   Please run Notion data collection first")
            return
        
        # Step 2: Update notion_pages
        logger.info("\n2️⃣ Updating notion_pages with user information...")
        updated_count = 0
        skipped_count = 0
        total_pages = await db["notion_pages"].count_documents({})
        
        logger.info(f"   📊 Total pages to process: {total_pages}")
        
        async for page in db["notion_pages"].find({}):
            created_by = page.get('created_by', {})
            created_by_id = created_by.get('id', '')
            
            if created_by_id and created_by_id in user_map:
                # Enrich created_by
                enriched_created_by = user_map[created_by_id]
                
                # Enrich last_edited_by
                last_edited_by = page.get('last_edited_by', {})
                last_edited_by_id = last_edited_by.get('id', '')
                enriched_last_edited_by = (
                    user_map[last_edited_by_id] 
                    if last_edited_by_id in user_map 
                    else last_edited_by
                )
                
                # Update page
                await db["notion_pages"].update_one(
                    {'_id': page['_id']},
                    {'$set': {
                        'created_by': enriched_created_by,
                        'last_edited_by': enriched_last_edited_by
                    }}
                )
                updated_count += 1
                
                # Progress indicator
                if updated_count % 100 == 0:
                    logger.info(f"   📝 Updated {updated_count} pages...")
            else:
                skipped_count += 1
        
        logger.info(f"\n   ✅ Updated {updated_count} pages")
        if skipped_count > 0:
            logger.info(f"   ⏭️  Skipped {skipped_count} pages (no user mapping)")
        
        # Step 3: Verify
        logger.info("\n3️⃣ Verifying results...")
        sample_page = await db["notion_pages"].find_one(
            {},
            sort=[("created_time", -1)]
        )
        
        if sample_page:
            created_by = sample_page.get('created_by', {})
            logger.info(f"   📄 Sample page: {sample_page.get('title', 'Untitled')[:50]}")
            logger.info(f"   👤 created_by.name: '{created_by.get('name', 'N/A')}'")
            logger.info(f"   📧 created_by.email: '{created_by.get('email', 'N/A')}'")
        
        client.close()
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ Notion Pages Enrichment Complete!")
        logger.info("=" * 70)
        logger.info(f"\n   Total pages: {total_pages}")
        logger.info(f"   Updated: {updated_count}")
        logger.info(f"   Skipped: {skipped_count}")
        logger.info(f"   Users in map: {user_count}")
        logger.info("\n" + "=" * 70)
        
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ Error enriching Notion pages: {e}")
        import traceback
        traceback.print_exc()
        return 1


async def main():
    """Main function"""
    # Load environment
    env_path = project_root / '.env'
    load_dotenv(dotenv_path=env_path)
    
    mongo_uri = os.getenv("MONGODB_URI")
    mongo_db = os.getenv("MONGODB_DATABASE")
    
    if not mongo_uri or not mongo_db:
        logger.error("❌ MONGODB_URI or MONGODB_DATABASE not set in environment")
        return 1
    
    logger.info(f"\n📊 MongoDB Configuration:")
    logger.info(f"   URI: {mongo_uri}")
    logger.info(f"   Database: {mongo_db}")
    
    return await enrich_notion_pages(mongo_uri, mongo_db)


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

