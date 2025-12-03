#!/bin/bash
# Script to check backend logs in AWS environment

echo "🔍 Checking backend logs in AWS..."
echo ""

# Check recent backend logs
echo "📋 Last 100 lines of backend logs:"
docker-compose -f docker-compose.prod.yml logs --tail=100 backend

echo ""
echo "📋 Last 50 lines with errors:"
docker-compose -f docker-compose.prod.yml logs --tail=200 backend | grep -i "error\|exception\|traceback" | tail -50

echo ""
echo "📋 Recent 502 errors:"
docker-compose -f docker-compose.prod.yml logs --tail=500 backend | grep -i "502\|bad gateway" | tail -20

echo ""
echo "✅ Log check complete!"
echo ""
echo "💡 To follow logs in real-time, run:"
echo "   docker-compose -f docker-compose.prod.yml logs -f backend"

