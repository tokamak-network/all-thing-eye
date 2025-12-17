#!/bin/bash
# Script to check data-collector logs in AWS environment

echo "🔍 Checking data-collector logs in AWS..."
echo ""

# Check if running on AWS
if [ ! -f "docker-compose.prod.yml" ]; then
    echo "❌ Error: docker-compose.prod.yml not found"
    echo "   This script should be run from project root on AWS server"
    exit 1
fi

echo "📋 Last 100 lines of data-collector logs:"
echo "============================================"
docker-compose -f docker-compose.prod.yml logs --tail=100 data-collector

echo ""
echo "📋 Data collection execution times:"
echo "============================================"
docker-compose -f docker-compose.prod.yml logs data-collector | grep -E "Starting daily data collection|Daily collection completed|Current time" | tail -20

echo ""
echo "📋 Collection results:"
echo "============================================"
docker-compose -f docker-compose.prod.yml logs data-collector | grep -E "Collecting|✅|❌|Error|Failed" | tail -30

echo ""
echo "📋 Next collection schedule:"
echo "============================================"
docker-compose -f docker-compose.prod.yml logs --tail=10 data-collector | grep "Next collection"

echo ""
echo "✅ Log check complete!"
echo ""
echo "💡 To follow logs in real-time, run:"
echo "   docker-compose -f docker-compose.prod.yml logs -f data-collector"
echo ""
echo "💡 To check full logs:"
echo "   docker-compose -f docker-compose.prod.yml logs --since 24h data-collector"

