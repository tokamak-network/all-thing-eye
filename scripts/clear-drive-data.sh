#!/bin/bash

# Script to clear Google Drive data and recollect with optimized settings
# Run this on AWS after pushing the updated plugin

set -e

echo "🗑️  Clearing Google Drive data from MongoDB..."

# Connect to MongoDB container and clear drive collections
docker exec all-thing-eye-mongodb mongosh all_things_eye --eval '
db.drive_activities.deleteMany({});
print("✅ Cleared drive_activities collection");
print("   Documents deleted: " + db.drive_activities.countDocuments({}));
'

echo ""
echo "🔄 Ready to recollect Drive data with optimized settings"
echo ""
echo "To trigger recollection, run:"
echo "  docker-compose -f docker-compose.prod.yml exec data-collector python -c 'from src.plugins.google_drive_plugin_mongo import GoogleDrivePluginMongo; ...'"
echo ""
echo "Or wait for the scheduled data collection to run automatically."
echo ""
echo "📊 Expected improvements:"
echo "   - No download/view/share events (noise removed)"
echo "   - No sheets_import_range events (auto-sync noise removed)"
echo "   - Edit events summarized daily (e.g., '편집 (10회)')"
echo "   - Significantly reduced activity count"
