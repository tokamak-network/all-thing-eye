#!/bin/bash

# Force rebuild frontend with no cache
# This script ensures a clean rebuild of the frontend

set -e

echo "🔄 Forcing clean rebuild of frontend..."

# Stop frontend container
echo "⏹️  Stopping frontend container..."
docker-compose -f docker-compose.prod.yml stop frontend

# Remove frontend container
echo "🗑️  Removing frontend container..."
docker-compose -f docker-compose.prod.yml rm -f frontend

# Remove frontend image
echo "🗑️  Removing old frontend image..."
docker rmi all-thing-eye-frontend || true

# Build with no cache
echo "🔨 Building frontend with no cache..."
docker-compose -f docker-compose.prod.yml build --no-cache frontend

# Start frontend
echo "🚀 Starting frontend..."
docker-compose -f docker-compose.prod.yml up -d frontend

# Show logs
echo "📋 Frontend logs:"
docker-compose -f docker-compose.prod.yml logs --tail=50 frontend

echo "✅ Frontend rebuild complete!"
echo "💡 If you still see the old version, try:"
echo "   1. Hard refresh in browser (Ctrl+Shift+R or Cmd+Shift+R)"
echo "   2. Clear browser cache"
echo "   3. Open in incognito/private window"
