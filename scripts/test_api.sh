#!/bin/bash

# API Testing Script for All-Thing-Eye

API_URL=${API_URL:-"http://localhost/api/v1"}

echo "🧪 Testing All-Thing-Eye API"
echo "API URL: $API_URL"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test function
test_endpoint() {
    local method=$1
    local endpoint=$2
    local description=$3
    
    echo -n "Testing: $description ... "
    
    response=$(curl -s -o /dev/null -w "%{http_code}" -X $method "$API_URL$endpoint")
    
    if [ "$response" -eq 200 ]; then
        echo -e "${GREEN}✓ PASS${NC} (HTTP $response)"
    else
        echo -e "${RED}✗ FAIL${NC} (HTTP $response)"
    fi
}

# Run tests
echo "📋 Running API Tests"
echo "===================="
echo ""

test_endpoint "GET" "/members" "Get all members"
test_endpoint "GET" "/members/1" "Get member detail"
test_endpoint "GET" "/members/1/activities" "Get member activities"
test_endpoint "GET" "/activities" "Get all activities"
test_endpoint "GET" "/activities/summary" "Get activity summary"
test_endpoint "GET" "/activities/types" "Get activity types"
test_endpoint "GET" "/projects" "Get all projects"
test_endpoint "GET" "/export/members?format=json" "Export members (JSON)"
test_endpoint "GET" "/export/activities?format=csv&limit=10" "Export activities (CSV)"

echo ""
echo "✅ Testing complete!"
echo ""
echo "📊 For detailed API exploration, visit:"
echo "   http://localhost/api/docs"

