"""
Quick script to check what scopes the current Slack token actually has
"""
import os
from dotenv import load_dotenv
from slack_sdk import WebClient
import ssl
import certifi

# Load environment
load_dotenv()
token = os.getenv('SLACK_BOT_TOKEN')

if not token:
    print("❌ SLACK_BOT_TOKEN not found in .env")
    exit(1)

print(f"🔑 Token: {token[:20]}...")

# Create client with SSL
ssl_context = ssl.create_default_context(cafile=certifi.where())
client = WebClient(token=token, ssl=ssl_context)

try:
    # Test auth and get token info
    response = client.auth_test()
    
    print("\n✅ Authentication Successful")
    print(f"   Workspace: {response['team']}")
    print(f"   Bot User: {response['user']}")
    print(f"   Bot ID: {response['user_id']}")
    
    # The auth.test response doesn't include scopes
    # Let's try to call APIs and see what fails
    print("\n🧪 Testing API Calls:")
    
    # Test users.list
    try:
        users = client.users_list(limit=1)
        print("   ✅ users:read - Working")
    except Exception as e:
        print(f"   ❌ users:read - {str(e)}")
    
    # Test conversations.list (public channels)
    try:
        channels = client.conversations_list(types="public_channel", limit=1)
        print("   ✅ channels:read - Working")
    except Exception as e:
        print(f"   ❌ channels:read - {str(e)}")
    
    # Test conversations.list (private channels)
    try:
        groups = client.conversations_list(types="private_channel", limit=1)
        print("   ✅ groups:read - Working")
    except Exception as e:
        print(f"   ❌ groups:read - {str(e)}")
    
    # Test conversations.history
    try:
        # Get first public channel
        channels_resp = client.conversations_list(types="public_channel", limit=1)
        if channels_resp['channels']:
            channel_id = channels_resp['channels'][0]['id']
            history = client.conversations_history(channel=channel_id, limit=1)
            print("   ✅ channels:history - Working")
    except Exception as e:
        print(f"   ❌ channels:history - {str(e)}")
    
except Exception as e:
    print(f"\n❌ Error: {e}")


