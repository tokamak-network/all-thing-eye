#!/bin/bash

echo "Testing GraphQL recordings_daily query for Ale Son..."
echo "======================================================"
echo ""

curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query TestAleAnalysis { activities(source: RECORDINGS_DAILY, memberName: \"Ale\", limit: 50) { memberName sourceType activityType timestamp message } }"
  }' | python3 -m json.tool

echo ""
echo "======================================================"
echo "Done!"
