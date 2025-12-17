#!/usr/bin/env python3
"""
Check projects repositories in MongoDB
"""
import asyncio
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

async def check_projects():
    # Load environment
    load_dotenv()
    mongo_uri = os.getenv("MONGODB_URI")
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(mongo_uri)
    db = client["all_thing_eye"]
    projects_col = db["projects"]
    
    print("=" * 80)
    print("CHECKING PROJECTS REPOSITORIES")
    print("=" * 80)
    
    # Get all projects
    cursor = projects_col.find({})
    projects = await cursor.to_list(length=100)
    
    if not projects:
        print("\n❌ No projects found in database!")
        return
    
    print(f"\n📋 Found {len(projects)} projects:\n")
    
    for project in projects:
        key = project.get('key', 'N/A')
        name = project.get('name', 'N/A')
        github_team_slug = project.get('github_team_slug', 'N/A')
        repositories = project.get('repositories', [])
        repos_synced_at = project.get('repositories_synced_at')
        is_active = project.get('is_active', False)
        
        status = "✅" if repositories else "❌"
        active = "🟢" if is_active else "🔴"
        
        print(f"{status} {active} Project: {name} ({key})")
        print(f"   GitHub Team Slug: {github_team_slug}")
        print(f"   Repositories ({len(repositories)}): {repositories if repositories else '(empty)'}")
        print(f"   Last Synced: {repos_synced_at or 'Never'}")
        print()
    
    # Close connection
    mongo.close()
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(check_projects())


