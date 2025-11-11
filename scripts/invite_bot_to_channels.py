#!/usr/bin/env python3
"""
Invite All-Thing-Eye Bot to Slack channels

This script invites the bot to specified channels or all public channels.
"""

import os
import sys
from pathlib import Path
import ssl
import certifi
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
project_root = Path(__file__).parent.parent
load_dotenv(dotenv_path=project_root / '.env')

def get_bot_info(client: WebClient):
    """Get bot user ID"""
    try:
        response = client.auth_test()
        return response['user_id']
    except SlackApiError as e:
        print(f"❌ Failed to get bot info: {e.response['error']}")
        return None

def get_all_channels(client: WebClient):
    """Get all public and private channels"""
    channels = []
    cursor = None
    
    try:
        while True:
            response = client.conversations_list(
                types="public_channel,private_channel",
                exclude_archived=True,
                cursor=cursor,
                limit=200
            )
            
            channels.extend(response['channels'])
            
            cursor = response.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break
        
        return channels
    except SlackApiError as e:
        print(f"❌ Failed to get channels: {e.response['error']}")
        return []

def invite_bot_to_channel(client: WebClient, channel_id: str, channel_name: str, bot_user_id: str):
    """Invite bot to a specific channel"""
    try:
        client.conversations_invite(
            channel=channel_id,
            users=bot_user_id
        )
        print(f"   ✅ Invited to #{channel_name}")
        return True
    except SlackApiError as e:
        error = e.response['error']
        if error == 'already_in_channel':
            print(f"   ℹ️  Already in #{channel_name}")
            return True
        elif error == 'cant_invite_self':
            print(f"   ℹ️  Already in #{channel_name} (can't invite self)")
            return True
        elif error == 'channel_not_found':
            print(f"   ⚠️  Channel #{channel_name} not found")
            return False
        elif error == 'is_archived':
            print(f"   ⚠️  Channel #{channel_name} is archived")
            return False
        elif error == 'not_authed' or error == 'missing_scope':
            print(f"   ❌ Permission denied for #{channel_name} (need channels:join or groups:write scope)")
            return False
        else:
            print(f"   ❌ Failed to invite to #{channel_name}: {error}")
            return False

def main():
    print("=" * 70)
    print("🤖 Slack Bot Channel Invitation Tool")
    print("=" * 70)
    
    # Check for token
    token = os.getenv('SLACK_BOT_TOKEN')
    if not token:
        print("❌ SLACK_BOT_TOKEN not found in .env file")
        return
    
    # Initialize Slack client
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    client = WebClient(token=token, ssl=ssl_context)
    
    # Get bot info
    print("\n1️⃣ Getting bot information...")
    bot_user_id = get_bot_info(client)
    if not bot_user_id:
        return
    print(f"   Bot User ID: {bot_user_id}")
    
    # Get all channels
    print("\n2️⃣ Fetching all channels...")
    channels = get_all_channels(client)
    if not channels:
        print("   ⚠️  No channels found")
        return
    
    print(f"   Found {len(channels)} channels")
    
    # Filter out archived and already joined channels
    print("\n3️⃣ Checking channel membership...")
    channels_to_invite = []
    already_in = []
    
    for channel in channels:
        if channel.get('is_member'):
            already_in.append(channel['name'])
        else:
            channels_to_invite.append(channel)
    
    print(f"   Already in {len(already_in)} channels:")
    for name in already_in[:5]:
        print(f"      • #{name}")
    if len(already_in) > 5:
        print(f"      ... and {len(already_in) - 5} more")
    
    if not channels_to_invite:
        print("\n✅ Bot is already in all available channels!")
        return
    
    print(f"\n   Found {len(channels_to_invite)} channels to join:")
    for channel in channels_to_invite[:10]:
        print(f"      • #{channel['name']}")
    if len(channels_to_invite) > 10:
        print(f"      ... and {len(channels_to_invite) - 10} more")
    
    # Ask for confirmation
    print(f"\n4️⃣ Ready to invite bot to {len(channels_to_invite)} channels")
    response = input("   Continue? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y']:
        print("\n   ❌ Cancelled by user")
        return
    
    # Invite bot to channels
    print("\n5️⃣ Inviting bot to channels...")
    success_count = 0
    fail_count = 0
    
    for channel in channels_to_invite:
        result = invite_bot_to_channel(
            client,
            channel['id'],
            channel['name'],
            bot_user_id
        )
        if result:
            success_count += 1
        else:
            fail_count += 1
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ Invitation process completed!")
    print("=" * 70)
    print(f"   Successfully invited: {success_count}")
    print(f"   Failed: {fail_count}")
    print(f"   Already in: {len(already_in)}")
    print(f"   Total channels: {len(channels)}")
    print()
    print("💡 Note: Some channels may require manual invitation by channel admins.")
    print("   Private channels especially need explicit invitation from members.")
    print()

if __name__ == "__main__":
    main()

