#!/bin/bash

# Script to clear Google Drive data and recollect with optimized settings
# Run this on AWS after pushing the updated plugin

set -e

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Default database name
DB_NAME=${MONGODB_DATABASE:-ati}

echo "🗑️  Clearing Google Drive data from MongoDB (Database: $DB_NAME)..."

# Connect to MongoDB through backend container (which has access to the correct MongoDB URI)
# This ensures we're using the same MongoDB that the backend uses
docker-compose -f docker-compose.prod.yml exec -T backend python -c "
import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get MongoDB connection info
mongodb_uri = os.getenv('MONGODB_URI')
db_name = os.getenv('MONGODB_DATABASE', 'ati')

if not mongodb_uri:
    print('❌ Error: MONGODB_URI not found in environment')
    exit(1)

try:
    # Connect to MongoDB
    client = MongoClient(mongodb_uri)
    db = client[db_name]
    
    # Clear collections
    result1 = db.drive_activities.delete_many({})
    print(f'✅ Cleared drive_activities collection')
    print(f'   Documents deleted: {result1.deleted_count}')
    
    result2 = db.drive_files.delete_many({})
    print(f'✅ Cleared drive_files collection')
    print(f'   Documents deleted: {result2.deleted_count}')
    
    client.close()
except Exception as e:
    print(f'❌ Error: {e}')
    exit(1)
"

echo ""
echo "🔄 Starting automatic recollection of Drive data..."
echo "   This may take a few minutes depending on the data size."
echo ""

# Trigger recollection using the initial collection script
# This will collect the past 90 days of data
docker-compose -f docker-compose.prod.yml exec -T data-collector python scripts/initial_data_collection_mongo.py --days 90 --sources drive

echo ""
echo "✨ Process finished! Check the dashboard for updated numbers."
