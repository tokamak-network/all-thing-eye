#!/usr/bin/env python3
"""
Update Member Projects

Updates member project assignments directly in MongoDB.
This is a one-time migration script - for ongoing management, use the frontend UI.
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Member project assignments
# Format: "Name": ["project-key1", "project-key2"]
# Empty list [] means no project assignment
MEMBER_PROJECTS = {
    "Aamir": ["project-ooo", "project-syb"],
    "Aryan": ["project-syb", "project-trh"],
    "Bernard": ["project-eco"],
    "Eugenie": ["project-eco"],
    "George": ["project-trh"],
    "Harvey": ["project-eco"],
    "Irene": [],  # No project assignment
    "Jamie": ["project-syb"],
    "Jason": ["project-eco"],
    "Jeff": ["project-syb"],
    "Luca": ["project-syb", "project-ooo"],
    "Manish": ["project-trh"],
    "Mehdi": ["project-ooo", "project-trh"],
    "Monica": ["project-ooo", "project-trh"],
    "Muhammed": ["project-ooo"],
    "Nam": ["project-trh"],
    "Nil": ["project-syb", "project-ooo"],
    "Praveen": ["project-trh"],
    "Rangga": [],  # No project assignment
    "Singh": ["project-syb", "project-trh"],
    "Theo": ["project-trh"],
    "Thomas": ["project-eco"],
    "Sahil": ["project-trh"],
}


async def update_member_projects():
    """Update member projects in MongoDB"""
    
    # Load environment
    load_dotenv(dotenv_path=project_root / '.env')
    
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    mongodb_database = os.getenv("MONGODB_DATABASE", "all_thing_eye")
    
    print("=" * 70)
    print("🔄 Updating Member Projects in MongoDB")
    print("=" * 70)
    print(f"\n📍 Database: {mongodb_database}")
    print(f"📍 Members to update: {len(MEMBER_PROJECTS)}")
    print()
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(mongodb_uri)
    db = client[mongodb_database]
    members_col = db["members"]
    
    updated_count = 0
    not_found = []
    
    for name, projects in MEMBER_PROJECTS.items():
        # Find member by name
        member = await members_col.find_one({"name": name})
        
        if not member:
            not_found.append(name)
            print(f"   ⚠️  {name}: NOT FOUND in database")
            continue
        
        # Update projects and team field
        # team field is legacy - set to first project or None
        team_value = projects[0] if projects else None
        
        result = await members_col.update_one(
            {"name": name},
            {
                "$set": {
                    "projects": projects,
                    "team": team_value,  # Also update legacy team field
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        if result.modified_count > 0:
            print(f"   ✅ {name}: {', '.join(projects)}")
            updated_count += 1
        else:
            # Check if already has same projects
            current_projects = member.get("projects", [])
            if set(current_projects) == set(projects):
                print(f"   ℹ️  {name}: Already up to date ({', '.join(projects)})")
            else:
                print(f"   ✅ {name}: {', '.join(projects)} (set)")
                updated_count += 1
    
    print()
    print("=" * 70)
    print("📊 Summary")
    print("=" * 70)
    print(f"   Updated: {updated_count}")
    print(f"   Not found: {len(not_found)}")
    if not_found:
        print(f"   Missing members: {', '.join(not_found)}")
    print()
    
    # Close connection
    client.close()
    
    return 0 if not not_found else 1


async def main():
    return await update_member_projects()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

