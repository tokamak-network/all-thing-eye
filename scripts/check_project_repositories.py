#!/usr/bin/env python3
"""
Check project repositories in MongoDB
Usage: docker exec -it all-thing-eye-backend python scripts/check_project_repositories.py
"""

import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, '/app')

def check_project_repositories():
    """Check repositories for all projects in MongoDB"""
    print("=" * 60)
    print("Project Repositories Check")
    print("=" * 60)
    
    try:
        from backend.main import mongo_manager
        
        # Connect to MongoDB
        mongo_manager.connect_sync()
        db = mongo_manager.db
        projects_collection = db["projects"]
        
        # Get all projects
        projects = list(projects_collection.find({}).sort("name", 1))
        
        if not projects:
            print("⚠️  No projects found in MongoDB")
            return
        
        print(f"\n📊 Found {len(projects)} projects\n")
        
        for project in projects:
            project_key = project.get("key", "unknown")
            project_name = project.get("name", "Unknown")
            github_team_slug = project.get("github_team_slug") or project_key
            repositories = project.get("repositories", [])
            repositories_synced_at = project.get("repositories_synced_at")
            is_active = project.get("is_active", False)
            
            print(f"🔍 {project_name} ({project_key})")
            print(f"   GitHub Team Slug: {github_team_slug}")
            print(f"   Status: {'Active' if is_active else 'Inactive'}")
            print(f"   Repositories: {len(repositories)}")
            
            if repositories:
                print(f"   Repository List:")
                for repo in repositories[:10]:  # Show first 10
                    print(f"     - {repo}")
                if len(repositories) > 10:
                    print(f"     ... and {len(repositories) - 10} more")
            else:
                print(f"   ⚠️  No repositories found")
            
            if repositories_synced_at:
                if isinstance(repositories_synced_at, datetime):
                    print(f"   Last Synced: {repositories_synced_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                else:
                    print(f"   Last Synced: {repositories_synced_at}")
            else:
                print(f"   ⚠️  Never synced")
            
            print()
        
        print("=" * 60)
        print("Summary")
        print("=" * 60)
        
        active_projects = [p for p in projects if p.get("is_active", False)]
        projects_with_repos = [p for p in active_projects if p.get("repositories")]
        
        print(f"Total Projects: {len(projects)}")
        print(f"Active Projects: {len(active_projects)}")
        print(f"Active Projects with Repositories: {len(projects_with_repos)}")
        print(f"Active Projects without Repositories: {len(active_projects) - len(projects_with_repos)}")
        
        if len(active_projects) - len(projects_with_repos) > 0:
            print("\n⚠️  Projects without repositories:")
            for project in active_projects:
                if not project.get("repositories"):
                    print(f"   - {project.get('name')} ({project.get('key')})")
                    print(f"     GitHub Team: {project.get('github_team_slug') or project.get('key')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    check_project_repositories()

