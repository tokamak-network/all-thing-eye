#!/bin/bash
# Check projects repositories via GraphQL API

echo "================================================================================"
echo "CHECKING PROJECTS REPOSITORIES VIA GRAPHQL"
echo "================================================================================"
echo ""

# GraphQL query to get all projects with repositories
QUERY='
query CheckProjects {
  projects {
    id
    key
    name
    slackChannel
    repositories
    isActive
  }
}
'

# Execute GraphQL query
curl -s -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"$(echo $QUERY | tr '\n' ' ')\"}" \
  | python3 -m json.tool

echo ""
echo "================================================================================"




