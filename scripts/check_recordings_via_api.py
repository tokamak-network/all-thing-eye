#!/usr/bin/env python3
"""
Check Recordings and Daily Analysis Participants via API

This script uses the backend API to check the actual data structure
of recordings and daily analysis to see if participant filtering is possible.
"""

import sys
import requests
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

import os

# Get API URL from environment or use default
API_URL = os.getenv('NEXT_PUBLIC_API_URL', 'http://localhost:8000')
API_BASE = f"{API_URL}/api/v1"

# You'll need to get an admin token - check your .env or login
# For now, we'll try without auth first (if your API allows it)
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', '')

headers = {}
if ADMIN_TOKEN:
    headers['Authorization'] = f'Bearer {ADMIN_TOKEN}'

print("=" * 80)
print("🔍 Checking Recordings and Daily Analysis Participants via API")
print("=" * 80)
print(f"\n📊 API URL: {API_BASE}")
print()

try:
    # 1. Check recordings endpoint
    print("=" * 80)
    print("1️⃣ Checking /database/recordings endpoint")
    print("=" * 80)
    
    try:
        response = requests.get(
            f"{API_BASE}/database/recordings",
            params={"limit": 1},
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            recordings = data.get('recordings', [])
            
            if recordings:
                sample = recordings[0]
                print(f"✅ Found {data.get('total', 0)} recordings")
                print(f"\n📄 Sample recording fields:")
                for key in sample.keys():
                    value = sample[key]
                    if isinstance(value, (list, dict)):
                        print(f"   - {key}: {type(value).__name__} (length: {len(value) if isinstance(value, list) else 'N/A'})")
                        if key == 'participants' and isinstance(value, list):
                            print(f"     → Participants: {value}")
                    else:
                        print(f"   - {key}: {type(value).__name__} = {str(value)[:100]}")
                
                if 'participants' in sample:
                    print(f"\n✅ Found 'participants' field: {sample['participants']}")
                else:
                    print("\n⚠️  No 'participants' field in recording")
            else:
                print("⚠️  No recordings found")
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Error checking recordings: {e}")
    
    # 2. Check daily analysis endpoint
    print("\n" + "=" * 80)
    print("2️⃣ Checking /ai/recordings-daily endpoint")
    print("=" * 80)
    
    try:
        response = requests.get(
            f"{API_BASE}/ai/recordings-daily",
            params={"limit": 1},
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            analyses = data.get('analyses', [])
            
            if analyses:
                sample = analyses[0]
                print(f"✅ Found {data.get('total', 0)} daily analyses")
                print(f"\n📄 Sample daily analysis structure:")
                
                # Check analysis.participants
                analysis = sample.get('analysis', {})
                participants = analysis.get('participants', [])
                
                if participants:
                    print(f"\n✅ Found 'analysis.participants' field")
                    print(f"   📊 Number of participants: {len(participants)}")
                    
                    if len(participants) > 0:
                        print(f"\n   📝 First participant structure:")
                        first_participant = participants[0]
                        for key, value in first_participant.items():
                            print(f"      - {key}: {type(value).__name__} = {str(value)[:100]}")
                        
                        # Show all participant names
                        print(f"\n   👥 All participant names:")
                        for i, p in enumerate(participants[:10], 1):  # Show first 10
                            name = p.get('name', 'N/A')
                            print(f"      {i}. {name}")
                        if len(participants) > 10:
                            print(f"      ... and {len(participants) - 10} more")
                else:
                    print("\n⚠️  No 'participants' field in analysis")
            else:
                print("⚠️  No daily analyses found")
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Error checking daily analyses: {e}")
    
    # 3. Check meetings endpoint (for participants in recordings)
    print("\n" + "=" * 80)
    print("3️⃣ Checking /ai/meetings endpoint (for recordings participants)")
    print("=" * 80)
    
    try:
        response = requests.get(
            f"{API_BASE}/ai/meetings",
            params={"limit": 1},
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            meetings = data.get('meetings', [])
            
            if meetings:
                sample = meetings[0]
                print(f"✅ Found {data.get('total', 0)} meetings")
                print(f"\n📄 Sample meeting fields:")
                for key in sample.keys():
                    value = sample[key]
                    if isinstance(value, (list, dict)):
                        print(f"   - {key}: {type(value).__name__} (length: {len(value) if isinstance(value, list) else 'N/A'})")
                        if key == 'participants' and isinstance(value, list):
                            print(f"     → Participants: {value}")
                    else:
                        print(f"   - {key}: {type(value).__name__} = {str(value)[:100]}")
                
                if 'participants' in sample:
                    print(f"\n✅ Found 'participants' field: {sample['participants']}")
                else:
                    print("\n⚠️  No 'participants' field in meeting")
            else:
                print("⚠️  No meetings found")
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Error checking meetings: {e}")
    
    # Summary
    print("\n" + "=" * 80)
    print("📋 SUMMARY")
    print("=" * 80)
    print("\n✅ Checked via API endpoints:")
    print("   - /database/recordings")
    print("   - /ai/recordings-daily")
    print("   - /ai/meetings")
    print("\n💡 Next steps:")
    print("   1. Review the field structures above")
    print("   2. If participants exist, we can implement filtering")
    print("   3. If not, we may need to extract participants from other fields")
    print("=" * 80)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

