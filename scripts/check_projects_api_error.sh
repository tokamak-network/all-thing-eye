#!/bin/bash
# Script to check projects API error logs on AWS EC2

echo "=========================================="
echo "Projects API Error Debugging Script"
echo "=========================================="
echo ""

# Check if running in Docker container
if [ -f /.dockerenv ]; then
    echo "Running inside Docker container"
    CONTAINER_NAME="all-thing-eye-backend"
else
    echo "Running on EC2 host"
    CONTAINER_NAME="all-thing-eye-backend"
fi

echo ""
echo "1. Checking recent backend logs for projects API errors..."
echo "------------------------------------------------------------"
docker logs --tail 100 $CONTAINER_NAME 2>&1 | grep -i "projects\|error\|exception" | tail -20

echo ""
echo "2. Testing projects API endpoint directly..."
echo "------------------------------------------------------------"
echo "Testing GET /api/v1/projects-management/projects?active_only=true"
curl -s -X GET "http://localhost:8000/api/v1/projects-management/projects?active_only=true" \
  -H "Content-Type: application/json" \
  -w "\nHTTP Status: %{http_code}\n" \
  | head -50

echo ""
echo "3. Checking MongoDB connection..."
echo "------------------------------------------------------------"
docker exec $CONTAINER_NAME python3 -c "
from backend.main import mongo_manager
try:
    mongo_manager.connect_sync()
    db = mongo_manager.get_database_sync()
    projects_collection = db['projects']
    count = projects_collection.count_documents({})
    print(f'MongoDB connection: OK')
    print(f'Projects collection count: {count}')
    
    # Check sample document structure
    sample = projects_collection.find_one({})
    if sample:
        print(f'Sample document keys: {list(sample.keys())}')
        print(f'created_at type: {type(sample.get(\"created_at\"))}')
        print(f'updated_at type: {type(sample.get(\"updated_at\"))}')
        print(f'repositories_synced_at type: {type(sample.get(\"repositories_synced_at\"))}')
    else:
        print('No documents found in projects collection')
except Exception as e:
    print(f'MongoDB connection error: {e}')
    import traceback
    traceback.print_exc()
"

echo ""
echo "4. Checking Python traceback for detailed error..."
echo "------------------------------------------------------------"
docker exec $CONTAINER_NAME python3 -c "
import sys
sys.path.insert(0, '/app')
from backend.api.v1.projects_management import get_mongo
from datetime import datetime

try:
    mongo = get_mongo()
    db = mongo.get_database_sync()
    projects_collection = db['projects']
    
    query = {'is_active': True}
    cursor = projects_collection.find(query).sort('name', 1)
    
    projects = []
    for doc in cursor:
        # Test the same logic as in the API
        created_at = doc.get('created_at')
        if not isinstance(created_at, datetime):
            created_at = datetime.utcnow()
        
        updated_at = doc.get('updated_at')
        if not isinstance(updated_at, datetime):
            updated_at = datetime.utcnow()
        
        repositories_synced_at = doc.get('repositories_synced_at')
        if repositories_synced_at is not None and not isinstance(repositories_synced_at, datetime):
            repositories_synced_at = None
        
        print(f'Processing project: {doc.get(\"key\")}')
        print(f'  created_at: {created_at} (type: {type(created_at)})')
        print(f'  updated_at: {updated_at} (type: {type(updated_at)})')
        print(f'  repositories_synced_at: {repositories_synced_at} (type: {type(repositories_synced_at)})')
        
        projects.append({
            'key': doc.get('key'),
            'name': doc.get('name'),
            'created_at': created_at,
            'updated_at': updated_at,
            'repositories_synced_at': repositories_synced_at
        })
    
    print(f'Successfully processed {len(projects)} projects')
    
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
"

echo ""
echo "=========================================="
echo "Debugging complete"
echo "=========================================="

