#!/usr/bin/env python
"""
Get all Slack channels that the bot is invited to
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from slack_sdk import WebClient
from dotenv import load_dotenv

# Load environment variables
env_path = project_root / '.env'
load_dotenv(env_path)

def main():
    """Get all channels the bot has access to"""
    
    # Get token
    token = os.getenv('SLACK_BOT_TOKEN')
    if not token:
        print("❌ SLACK_BOT_TOKEN not found in .env")
        return
    
    print("=" * 70)
    print("📋 Slack Channels List")
    print("=" * 70)
    
    try:
        client = WebClient(token=token)
        
        # Get bot user info
        auth_response = client.auth_test()
        bot_user_id = auth_response.get('user_id')
        bot_name = auth_response.get('user')
        
        print(f"\n🤖 Bot: {bot_name} ({bot_user_id})")
        print(f"👥 Team: {auth_response.get('team')}")
        print()
        
        # Get all channels (public)
        print("🔍 Fetching public channels...")
        public_channels = []
        cursor = None
        
        while True:
            response = client.conversations_list(
                types="public_channel",
                limit=200,
                cursor=cursor
            )
            
            channels = response.get('channels', [])
            for channel in channels:
                if channel.get('is_member'):  # Bot is a member
                    public_channels.append(channel)
            
            cursor = response.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break
        
        # Get private channels
        print("🔍 Fetching private channels...")
        private_channels = []
        cursor = None
        
        while True:
            response = client.conversations_list(
                types="private_channel",
                limit=200,
                cursor=cursor
            )
            
            channels = response.get('channels', [])
            for channel in channels:
                if channel.get('is_member'):  # Bot is a member
                    private_channels.append(channel)
            
            cursor = response.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break
        
        # Display results
        all_channels = public_channels + private_channels
        
        print("\n" + "=" * 70)
        print(f"✅ Found {len(all_channels)} channels where bot is invited")
        print("=" * 70)
        
        if all_channels:
            print("\n📌 Public Channels:")
            if public_channels:
                for ch in sorted(public_channels, key=lambda x: x['name']):
                    print(f"   • #{ch['name']:<30} → {ch['id']}")
            else:
                print("   (none)")
            
            print("\n🔒 Private Channels:")
            if private_channels:
                for ch in sorted(private_channels, key=lambda x: x['name']):
                    print(f"   • 🔐 {ch['name']:<30} → {ch['id']}")
            else:
                print("   (none)")
            
            print("\n" + "=" * 70)
            print("💡 Copy these channel IDs to config/config.yaml")
            print("=" * 70)
            
            # Generate config snippet
            print("\n📝 Config snippet for config.yaml:")
            print()
            for ch in sorted(all_channels, key=lambda x: x['name']):
                project_key = ch['name'].replace('-', '_')
                print(f"  # {ch['name']}")
                print(f"  {project_key}:")
                print(f"    slack_channel: \"{ch['name']}\"")
                print(f"    slack_channel_id: \"{ch['id']}\"")
                print()
        else:
            print("\n⚠️  No channels found where bot is a member!")
            print("\n💡 Invite the bot to channels:")
            print("   1. Go to Slack channel")
            print("   2. Type: /invite @allthingeye_bot")
            print("   3. Press Enter")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

