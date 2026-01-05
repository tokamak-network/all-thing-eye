import json
import hmac
import hashlib
import time
import httpx
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

async def test_slack_mention():
    url = "http://localhost:8000/api/v1/slack/events"
    signing_secret = os.getenv("SLACK_SIGNING_SECRET", "")
    
    if not signing_secret:
        print("❌ SLACK_SIGNING_SECRET이 .env에 없습니다.")
        return

    # 1. 가짜 슬랙 이벤트 데이터 생성
    timestamp = str(int(time.time()))
    body_dict = {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "user": "U12345678",
            "text": "<@U87654321> 우리 팀 이번 주 커밋 현황 알려줘",
            "channel": "C12345678",
            "ts": "1234567890.123456"
        }
    }
    body_json = json.dumps(body_dict)

    # 2. 슬랙 서명 생성 (보안 검증 통과용)
    sig_basestring = f"v0:{timestamp}:{body_json}"
    signature = "v0=" + hmac.new(
        signing_secret.encode("utf-8"),
        sig_basestring.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    # 3. 요청 보내기
    headers = {
        "X-Slack-Request-Timestamp": timestamp,
        "X-Slack-Signature": signature,
        "Content-Type": "application/json"
    }

    print(f"🚀 로컬 서버({url})로 슬랙 멘션 요청을 보냅니다...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, content=body_json, headers=headers)
            print(f"✅ 응답 코드: {resp.status_code}")
            print(f"✅ 응답 내용: {resp.json()}")
            print("\n💡 이제 백엔드 터미널 로그를 확인하세요. AI가 답변을 생성하고 슬랙으로 전송(Chat.update)하려고 시도할 것입니다.")
        except Exception as e:
            print(f"❌ 요청 실패: {e}")

if __name__ == "__main__":
    asyncio.run(test_slack_mention())
