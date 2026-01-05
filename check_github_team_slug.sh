#!/bin/bash
# Check projects github_team_slug via REST API

echo "================================================================================"
echo "CHECKING GITHUB TEAM SLUG FOR PROJECTS"
echo "================================================================================"
echo ""

# Get projects with full details
curl -s -X GET http://localhost:8000/api/v1/projects/management/projects \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
projects = data.get('projects', [])

print(f'📋 Found {len(projects)} projects:\n')

for p in projects:
    key = p.get('key', 'N/A')
    name = p.get('name', 'N/A')
    team_slug = p.get('github_team_slug', None)
    repos = p.get('repositories', [])
    repos_synced = p.get('repositories_synced_at', None)
    
    status = '✅' if repos else '❌'
    slug_status = '✅' if team_slug else '❌'
    
    print(f'{status} Project: {name} ({key})')
    print(f'   GitHub Team Slug: {slug_status} {team_slug if team_slug else \"(NOT SET)\"}')
    print(f'   Repositories ({len(repos)}): {repos if repos else \"(empty)\"}')
    print(f'   Last Synced: {repos_synced if repos_synced else \"Never\"}')
    print()
"

echo "================================================================================"




