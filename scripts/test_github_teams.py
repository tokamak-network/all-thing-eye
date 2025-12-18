#!/usr/bin/env python3
"""
Test GitHub Teams API to check team repositories

This script tests both REST API and GraphQL API to fetch team repositories.
"""

import sys
import os
import asyncio
from pathlib import Path
import requests

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.core.config import Config
from src.core.mongo_manager import get_mongo_manager

# GitHub API configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_ORG = os.getenv('GITHUB_ORG', 'tokamak-network')


def test_rest_api_teams():
    """Test GitHub REST API to list teams"""
    print("=" * 80)
    print("🔍 TESTING GITHUB REST API - LIST TEAMS")
    print("=" * 80)
    
    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN not set in environment")
        return
    
    url = f"https://api.github.com/orgs/{GITHUB_ORG}/teams"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"\n📡 GET {url}")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            teams = response.json()
            print(f"\n✅ Found {len(teams)} teams:\n")
            
            for team in teams:
                print(f"   • {team['name']}")
                print(f"      slug: {team['slug']}")
                print(f"      id: {team['id']}")
                print(f"      members: {team.get('members_count', 'N/A')}")
                print()
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   {response.text}")
    
    except Exception as e:
        print(f"❌ Exception: {e}")


def test_rest_api_team_repos(team_slug: str):
    """Test GitHub REST API to get team repositories"""
    print("=" * 80)
    print(f"🔍 TESTING GITHUB REST API - TEAM REPOSITORIES: {team_slug}")
    print("=" * 80)
    
    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN not set in environment")
        return
    
    url = f"https://api.github.com/orgs/{GITHUB_ORG}/teams/{team_slug}/repos"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"\n📡 GET {url}")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            repos = response.json()
            print(f"\n✅ Found {len(repos)} repositories:\n")
            
            for repo in repos:
                print(f"   • {repo['full_name']}")
                print(f"      private: {repo.get('private', False)}")
                print(f"      archived: {repo.get('archived', False)}")
                print()
            
            return repos
        elif response.status_code == 404:
            print(f"⚠️  Team '{team_slug}' not found")
            print(f"   Make sure the team slug is correct")
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   {response.text}")
    
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    return None


def test_graphql_teams():
    """Test GitHub GraphQL API to list teams and repositories"""
    print("=" * 80)
    print("🔍 TESTING GITHUB GRAPHQL API - TEAMS & REPOSITORIES")
    print("=" * 80)
    
    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN not set in environment")
        return
    
    # GraphQL query to get teams and their repositories
    query = """
    query($org: String!, $cursor: String) {
      organization(login: $org) {
        teams(first: 10, after: $cursor) {
          nodes {
            name
            slug
            description
            members {
              totalCount
            }
            repositories {
              totalCount
              nodes {
                name
                url
                isPrivate
                isArchived
              }
            }
          }
          pageInfo {
            hasNextPage
            endCursor
          }
        }
      }
    }
    """
    
    url = "https://api.github.com/graphql"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        variables = {"org": GITHUB_ORG, "cursor": None}
        response = requests.post(
            url,
            headers=headers,
            json={"query": query, "variables": variables},
            timeout=10
        )
        
        print(f"\n📡 POST {url}")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if "errors" in data:
                print(f"\n❌ GraphQL Errors:")
                for error in data["errors"]:
                    print(f"   • {error.get('message')}")
                return
            
            teams = data.get("data", {}).get("organization", {}).get("teams", {}).get("nodes", [])
            
            print(f"\n✅ Found {len(teams)} teams:\n")
            
            for team in teams:
                print(f"   🏷️  {team['name']}")
                print(f"      slug: {team['slug']}")
                print(f"      members: {team['members']['totalCount']}")
                print(f"      repositories: {team['repositories']['totalCount']}")
                
                if team['repositories']['totalCount'] > 0:
                    print(f"      📦 Repositories:")
                    for repo in team['repositories']['nodes']:
                        print(f"         • {repo['name']}")
                print()
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   {response.text}")
    
    except Exception as e:
        print(f"❌ Exception: {e}")


async def check_mongodb_projects():
    """Check MongoDB projects collection"""
    print("=" * 80)
    print("🔍 CHECKING MONGODB PROJECTS COLLECTION")
    print("=" * 80)
    
    config = Config()
    mongodb_config = {
        'uri': os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
        'database': os.getenv('MONGODB_DATABASE', config.get('mongodb.database', 'ati'))
    }
    mongo_manager = get_mongo_manager(mongodb_config)
    db = mongo_manager.async_db
    
    try:
        projects = db['projects'].find()
        
        print(f"\n📋 Projects in MongoDB:\n")
        
        async for project in projects:
            print(f"   • {project.get('name')} ({project.get('key')})")
            print(f"      active: {project.get('is_active', False)}")
            print(f"      github_team_slug: {project.get('github_team_slug', 'NOT SET')}")
            print(f"      repositories: {project.get('repositories', [])}")
            print(f"      repositories_synced_at: {project.get('repositories_synced_at', 'NEVER')}")
            print()
    
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if hasattr(mongo_manager, 'close'):
            mongo_manager.close()


async def main():
    """Main function to run all tests"""
    
    # 1. Check MongoDB projects
    await check_mongodb_projects()
    
    # 2. List all teams (REST API)
    test_rest_api_teams()
    
    # 3. Test specific team slugs from screenshot
    team_slugs = [
        "Project_ECO",
        "project-eco",
        "Project_Ooo",
        "project-ooo",
        "Project_SYB",
        "project-syb",
        "Project_TRH",
        "project-trh"
    ]
    
    print("\n" + "=" * 80)
    print("🧪 TESTING TEAM REPOSITORY ACCESS")
    print("=" * 80)
    
    for slug in team_slugs:
        test_rest_api_team_repos(slug)
    
    # 4. Test GraphQL API
    test_graphql_teams()
    
    print("\n" + "=" * 80)
    print("✅ TESTS COMPLETE")
    print("=" * 80)
    print("\n💡 Next steps:")
    print("   1. Check if team slugs in MongoDB match actual GitHub team slugs")
    print("   2. Verify GitHub token has 'read:org' permission")
    print("   3. Ensure teams have repositories added in GitHub settings")


if __name__ == "__main__":
    asyncio.run(main())

