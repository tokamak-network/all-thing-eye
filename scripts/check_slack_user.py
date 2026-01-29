#!/usr/bin/env python
"""
Check specific Slack user information
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
env_path = project_root / ".env"
load_dotenv(env_path)


def check_user(user_id: str):
    """Check user information"""

    # Get token
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        print("❌ SLACK_BOT_TOKEN not found in .env")
        return

    print("=" * 70)
    print(f"🔍 Slack User Information: {user_id}")
    print("=" * 70)

    try:
        client = WebClient(token=token)

        # Get user info
        response = client.users_info(user=user_id)

        if not response["ok"]:
            print(f"\n❌ Error: {response.get('error', 'Unknown error')}")
            return

        user = response["user"]

        print(f"\n📋 User Details:")
        print(f"   ID: {user['id']}")
        print(f"   Username: @{user.get('name', 'N/A')}")
        print(f"   Real Name: {user.get('real_name', 'N/A')}")
        print(f"   Display Name: {user.get('profile', {}).get('display_name', 'N/A')}")
        print(f"   Email: {user.get('profile', {}).get('email', 'N/A')}")
        print(f"   Title: {user.get('profile', {}).get('title', 'N/A')}")

        print(f"\n📊 Status:")
        print(f"   Is Bot: {user.get('is_bot', False)}")
        print(f"   Is Admin: {user.get('is_admin', False)}")
        print(f"   Is Owner: {user.get('is_owner', False)}")
        print(f"   Is Deleted: {user.get('deleted', False)}")
        print(f"   Is Restricted: {user.get('is_restricted', False)}")
        print(f"   Is Ultra Restricted: {user.get('is_ultra_restricted', False)}")

        # Check if deleted/deactivated
        if user.get("deleted", False):
            print(f"\n⚠️  This user account has been DELETED/DEACTIVATED")
            print(f"   This is likely a former employee (퇴사자)")

        print("\n" + "=" * 70)
        print("💡 Next Steps:")
        print("=" * 70)

        if user.get("deleted", False):
            print("\n이 사용자는 퇴사자입니다.")
            print("옵션:")
            print("  1. 무시하기 (권장) - 퇴사자 데이터는 수집하지 않음")
            print("  2. Admin UI에서 멤버 추가 - 과거 데이터 분석용")
        else:
            email = user.get("profile", {}).get("email", "N/A")
            real_name = user.get("real_name", "Unknown")
            username = user.get("name", "unknown")

            print(f"\n현재 활동 중인 사용자입니다!")
            print(f"\nAdmin UI (Members 페이지)에서 추가하세요:")
            print(f"""
  Name: {real_name}
  Email: {email}
  Slack ID: {user_id}
""")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    else:
        # Default user ID from the error message
        user_id = "u03dchbjhsr"

    check_user(user_id)
