#!/bin/bash
# Check Recordings and Daily Analysis Participants on AWS EC2
# This script should be run on the EC2 instance

echo "=================================================================================="
echo "🔍 Checking Recordings and Daily Analysis Participants Data Structure"
echo "=================================================================================="
echo ""

# Check if we're in the project directory
if [ ! -f "scripts/check_recordings_participants.py" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    echo "   cd ~/all-thing-eye"
    exit 1
fi

# Run the Python script inside Docker container (recommended)
echo "📊 Running data structure check in Docker container..."
echo ""
docker exec -it all-thing-eye-backend python scripts/check_recordings_participants.py

# Alternative: If you want to run locally, uncomment below and install pymongo first
# pip3 install pymongo
# python3 scripts/check_recordings_participants.py

