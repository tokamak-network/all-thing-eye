#!/usr/bin/env python3
"""
Fix team slugs in MongoDB projects collection

Changes hyphens to underscores to match GitHub team slugs.
"""

import sys
import asyncio
from pathlib import Path
import os

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.core.config import Config
from src.core.mongo_manager import get_mongo_manager

async def fix_team_slugs():
    """Fix team slugs to match GitHub"""
    print("=" * 80)
    print("🔧 FIXING TEAM SLUGS IN MONGODB")
    print("=" * 80)
    
    config = Config()
    mongodb_config = {
        'uri': os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
        'database': os.getenv('MONGODB_DATABASE', config.get('mongodb.database', 'ati'))
    }
    mongo_manager = get_mongo_manager(mongodb_config)
    db = mongo_manager.async_db
    
    try:
        # Slug mapping: old (hyphen) → new (underscore)
        slug_fixes = {
            'project-ooo': 'project_ooo',
            'project-eco': 'project_eco',
            'project-syb': 'project_syb',
            'project-trh': 'project_trh'
        }
        
        print(f"\n📋 Slug corrections to apply:\n")
        for old_slug, new_slug in slug_fixes.items():
            print(f"   {old_slug} → {new_slug}")
        
        print(f"\n🔄 Updating projects...\n")
        
        updated_count = 0
        for old_slug, new_slug in slug_fixes.items():
            result = await db['projects'].update_one(
                {'github_team_slug': old_slug},
                {'$set': {'github_team_slug': new_slug}}
            )
            
            if result.modified_count > 0:
                print(f"   ✅ Updated: {old_slug} → {new_slug}")
                updated_count += 1
            else:
                print(f"   ⏭️  Skipped: {old_slug} (not found or already correct)")
        
        print(f"\n📊 Summary:")
        print(f"   Total updated: {updated_count}")
        
        # Verify the changes
        print(f"\n🔍 Verifying updated slugs:\n")
        
        projects = db['projects'].find({'is_active': True})
        async for project in projects:
            slug = project.get('github_team_slug')
            print(f"   • {project.get('name')}: {slug}")
        
        print("\n" + "=" * 80)
        print("✅ TEAM SLUGS FIXED")
        print("=" * 80)
        print("\n💡 Next step: Run data collector to sync repositories")
        print("   python scripts/daily_data_collection_mongo.py")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if hasattr(mongo_manager, 'close'):
            mongo_manager.close()


if __name__ == "__main__":
    asyncio.run(fix_team_slugs())

