#!/bin/bash

BASE_URL="http://localhost:8000"

echo "===================================================================="
echo "🧪 MongoDB API Testing"
echo "===================================================================="

# 1. Health Check
echo -e "\n1️⃣ Testing Health Endpoint"
echo "GET /health"
echo "--------------------------------------------------------------------"
curl -s "$BASE_URL/health" | jq '.'

# 2. Members API
echo -e "\n\n2️⃣ Testing Members API"
echo "GET /api/v1/members"
echo "--------------------------------------------------------------------"
curl -s "$BASE_URL/api/v1/members?limit=5" | jq '.data[0:2]'

# 3. Activities API - GitHub Commits
echo -e "\n\n3️⃣ Testing Activities API - GitHub Commits"
echo "GET /api/v1/activities?source_type=github&activity_type=commit"
echo "--------------------------------------------------------------------"
curl -s "$BASE_URL/api/v1/activities?source_type=github&activity_type=commit&limit=3" | jq '.data[0:2]'

# 4. Activities API - GitHub PRs
echo -e "\n\n4️⃣ Testing Activities API - GitHub PRs"
echo "GET /api/v1/activities?source_type=github&activity_type=pull_request"
echo "--------------------------------------------------------------------"
curl -s "$BASE_URL/api/v1/activities?source_type=github&activity_type=pull_request&limit=3" | jq '.data[0:1]'

# 5. Projects API
echo -e "\n\n5️⃣ Testing Projects API"
echo "GET /api/v1/projects"
echo "--------------------------------------------------------------------"
curl -s "$BASE_URL/api/v1/projects" | jq '.'

# 6. Query API - Simple aggregation
echo -e "\n\n6️⃣ Testing Dynamic Query API - Commit count by author"
echo "POST /api/v1/query/execute"
echo "--------------------------------------------------------------------"
curl -s -X POST "$BASE_URL/api/v1/query/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "github_commits",
    "operation": "aggregate",
    "pipeline": [
      {"$group": {"_id": "$author_login", "count": {"$sum": 1}}},
      {"$sort": {"count": -1}},
      {"$limit": 5}
    ]
  }' | jq '.'

# 7. Query API - Recent commits
echo -e "\n\n7️⃣ Testing Dynamic Query API - Recent commits"
echo "POST /api/v1/query/execute"
echo "--------------------------------------------------------------------"
curl -s -X POST "$BASE_URL/api/v1/query/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "github_commits",
    "operation": "find",
    "query": {},
    "sort": {"committed_at": -1},
    "limit": 3,
    "projection": {"sha": 1, "message": 1, "author_login": 1, "committed_at": 1}
  }' | jq '.'

echo -e "\n===================================================================="
echo "✅ API Testing Completed!"
echo "===================================================================="

