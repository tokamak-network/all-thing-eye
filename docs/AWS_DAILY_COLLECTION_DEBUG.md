# AWS Daily Collection Debugging Guide

디버깅 가이드: AWS에서 매일 자정(KST) 데이터 수집이 작동하지 않을 때 확인할 항목들

---

## 🔍 1. Data Collector 컨테이너 상태 확인

### 컨테이너가 실행 중인지 확인

```bash
# EC2에 SSH 접속 후
docker-compose -f docker-compose.prod.yml ps

# 또는
docker ps | grep data-collector

# 예상 출력:
# all-thing-eye-data-collector   Up    (healthy)
```

**문제 발견 시:**
- 컨테이너가 `Exited` 상태면 → 재시작 필요
- 컨테이너가 없으면 → `docker-compose up -d data-collector` 실행

---

## 📋 2. 로그 확인 (가장 중요!)

### 실시간 로그 모니터링

```bash
# 전체 로그 확인
docker-compose -f docker-compose.prod.yml logs -f data-collector

# 최근 1시간 로그 확인
docker-compose -f docker-compose.prod.yml logs --since 1h data-collector

# 자정 시간대 로그만 확인 (예: 00:00 ~ 01:00 KST)
docker-compose -f docker-compose.prod.yml logs --since "2025-11-18T00:00:00" --until "2025-11-18T01:00:00" data-collector
```

### 확인할 로그 패턴

#### ✅ 정상 작동 시 예상 로그:

```
[INFO] ====== Starting daily data collection ======
[INFO] Time: 2025-11-18 00:00:15+09:00
🚀 Starting DAILY data collection - 2025-11-18T00:00:15+09:00
📅 Previous day (KST): 2025-11-17
📂 Collecting Slack data...
   ✅ Slack: 42 messages
📂 Collecting Notion data...
   ✅ Notion: 8 pages
📂 Collecting Google Drive data...
   ✅ Google Drive: 15 activities
✅ Daily collection completed
```

#### ❌ 문제 발생 시 확인할 에러:

```
# Slack 에러 예시
❌ Slack collection failed: Authentication failed
❌ Slack collection failed: Rate limit exceeded
❌ Slack collection failed: Connection timeout

# Notion 에러 예시
❌ Notion collection failed: Invalid token
❌ Notion collection failed: API rate limit

# Google Drive 에러 예시
❌ Google Drive collection failed: Token expired
❌ Google Drive collection failed: Permission denied
```

---

## ⏰ 3. 타임존 및 스케줄 확인

### 컨테이너 내부 타임존 확인

```bash
# 컨테이너 내부 시간 확인
docker exec -it all-thing-eye-data-collector date
# 예상 출력: Mon Nov 18 00:15:23 KST 2025

# 타임존 확인
docker exec -it all-thing-eye-data-collector date +%Z
# 예상 출력: KST

# KST 시간 확인
docker exec -it all-thing-eye-data-collector bash -c "TZ=Asia/Seoul date"
# 예상 출력: Mon Nov 18 00:15:23 KST 2025
```

### 스케줄러 상태 확인

로그에서 다음 메시지 확인:

```
[INFO] Current time: 2025-11-17 14:30:00+09:00
[INFO] Next collection in 34200 seconds (9 hours 30 minutes)
```

**문제 발견 시:**
- 시간이 UTC로 표시되면 → 타임존 설정 문제
- "Next collection" 계산이 잘못되면 → 스크립트 로직 문제

---

## 🔑 4. 환경 변수 및 API 토큰 확인

### 환경 변수 확인

```bash
# 컨테이너 내부 환경 변수 확인
docker exec -it all-thing-eye-data-collector env | grep -E "(SLACK|NOTION|DRIVE|GITHUB)"

# 예상 출력:
# SLACK_BOT_TOKEN=xoxb-...
# SLACK_USER_TOKEN=xoxp-...
# NOTION_TOKEN=secret_...
# GOOGLE_ADMIN_EMAIL=admin@...
```

### API 토큰 유효성 확인

```bash
# 컨테이너 내부에서 직접 테스트
docker exec -it all-thing-eye-data-collector bash

# Python으로 토큰 확인
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()

print('SLACK_BOT_TOKEN:', 'SET' if os.getenv('SLACK_BOT_TOKEN') else 'NOT SET')
print('NOTION_TOKEN:', 'SET' if os.getenv('NOTION_TOKEN') else 'NOT SET')
print('GOOGLE_ADMIN_EMAIL:', os.getenv('GOOGLE_ADMIN_EMAIL', 'NOT SET'))
"
```

**문제 발견 시:**
- 토큰이 `NOT SET`이면 → `.env` 파일 확인 필요
- 토큰이 만료되었으면 → 새 토큰 발급 필요

---

## 🗄️ 5. MongoDB 연결 확인

### MongoDB 연결 테스트

```bash
# 컨테이너 내부에서 MongoDB 연결 확인
docker exec -it all-thing-eye-data-collector python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
from src.core.mongo_manager import get_mongo_manager

mongodb_config = {
    'uri': os.getenv('MONGODB_URI'),
    'database': os.getenv('MONGODB_DATABASE', 'all_thing_eye')
}
mongo_manager = get_mongo_manager(mongodb_config)
mongo_manager.connect_async()
print('✅ MongoDB connection successful')
mongo_manager.close()
"
```

**문제 발견 시:**
- 연결 실패 → `MONGODB_URI` 확인
- 타임아웃 → 네트워크/방화벽 확인
- 인증 실패 → MongoDB 사용자 자격증명 확인

---

## ⚙️ 6. 플러그인 활성화 상태 확인

### config.yaml 확인

```bash
# 컨테이너 내부에서 설정 확인
docker exec -it all-thing-eye-data-collector cat config/config.yaml | grep -A 5 -E "(slack|notion|google_drive):"

# 또는 Python으로 확인
docker exec -it all-thing-eye-data-collector python3 -c "
from src.core.config import Config
config = Config()

slack_config = config.get_plugin_config('slack')
notion_config = config.get_plugin_config('notion')
drive_config = config.get_plugin_config('google_drive')

print('Slack enabled:', slack_config.get('enabled', False) if slack_config else False)
print('Notion enabled:', notion_config.get('enabled', False) if notion_config else False)
print('Drive enabled:', drive_config.get('enabled', False) if drive_config else False)
"
```

**문제 발견 시:**
- `enabled: false`이면 → `config/config.yaml`에서 활성화 필요

---

## 🧪 7. 수동 실행 테스트

### 특정 소스만 수동 실행

```bash
# 컨테이너 내부에서
docker exec -it all-thing-eye-data-collector bash

# Slack만 테스트
python scripts/daily_data_collection_mongo.py --sources slack

# Notion만 테스트
python scripts/daily_data_collection_mongo.py --sources notion

# Google Drive만 테스트
python scripts/daily_data_collection_mongo.py --sources drive
```

### 특정 날짜로 테스트

```bash
# 어제 데이터 수집 테스트
python scripts/daily_data_collection_mongo.py --date 2025-11-17

# 오늘 데이터 수집 테스트
python scripts/daily_data_collection_mongo.py --date 2025-11-18
```

**문제 발견 시:**
- 수동 실행은 성공하지만 자동 실행 실패 → 스케줄러 문제
- 수동 실행도 실패 → 플러그인/API 문제

---

## 📊 8. 데이터베이스에서 최근 수집 확인

### MongoDB에서 최근 수집 시간 확인

```bash
# MongoDB에 직접 연결 (MongoDB Atlas 또는 로컬)
mongosh "mongodb+srv://..."

# 또는 컨테이너 내부에서
docker exec -it all-thing-eye-data-collector python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
from src.core.mongo_manager import get_mongo_manager
from datetime import datetime, timedelta
import asyncio

async def check_recent_collections():
    mongodb_config = {
        'uri': os.getenv('MONGODB_URI'),
        'database': os.getenv('MONGODB_DATABASE', 'all_thing_eye')
    }
    mongo_manager = get_mongo_manager(mongodb_config)
    mongo_manager.connect_async()
    
    db = mongo_manager.async_db
    
    # 최근 24시간 내 수집된 데이터 확인
    yesterday = datetime.utcnow() - timedelta(days=1)
    
    slack_count = await db.slack_messages.count_documents({
        'collected_at': {'$gte': yesterday}
    })
    notion_count = await db.notion_pages.count_documents({
        'collected_at': {'$gte': yesterday}
    })
    drive_count = await db.drive_activities.count_documents({
        'collected_at': {'$gte': yesterday}
    })
    
    print(f'Slack messages (last 24h): {slack_count}')
    print(f'Notion pages (last 24h): {notion_count}')
    print(f'Drive activities (last 24h): {drive_count}')
    
    mongo_manager.close()

asyncio.run(check_recent_collections())
"
```

**문제 발견 시:**
- 카운트가 0이면 → 수집이 실행되지 않았거나 실패
- 카운트가 있으면 → 수집은 되었지만 최신 데이터가 아닐 수 있음

---

## 🔄 9. 컨테이너 재시작

### 문제 해결을 위한 재시작

```bash
# Data collector만 재시작
docker-compose -f docker-compose.prod.yml restart data-collector

# 로그 확인
docker-compose -f docker-compose.prod.yml logs -f data-collector

# 전체 재시작 (필요시)
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d
```

---

## 🐛 10. 일반적인 문제 및 해결 방법

### 문제 1: 컨테이너가 자정에 실행되지 않음

**원인:**
- 컨테이너가 재시작되면서 스케줄 계산이 리셋됨
- 타임존 설정 오류

**해결:**
```bash
# 컨테이너 로그에서 스케줄 계산 확인
docker-compose -f docker-compose.prod.yml logs data-collector | grep "Next collection"

# 타임존 확인
docker exec -it all-thing-eye-data-collector date
```

### 문제 2: Slack 수집 실패

**원인:**
- 토큰 만료
- Rate limit
- 채널 권한 부족

**해결:**
```bash
# 토큰 확인
docker exec -it all-thing-eye-data-collector env | grep SLACK

# 수동 실행으로 상세 에러 확인
docker exec -it all-thing-eye-data-collector python scripts/daily_data_collection_mongo.py --sources slack
```

### 문제 3: Notion 수집 실패

**원인:**
- 토큰 만료
- Integration 권한 부족

**해결:**
```bash
# Notion 토큰 확인
docker exec -it all-thing-eye-data-collector env | grep NOTION

# 수동 실행
docker exec -it all-thing-eye-data-collector python scripts/daily_data_collection_mongo.py --sources notion
```

### 문제 4: Google Drive 수집 실패

**원인:**
- OAuth 토큰 만료
- Service account 권한 부족
- credentials.json 파일 문제

**해결:**
```bash
# credentials.json 확인
docker exec -it all-thing-eye-data-collector ls -la config/google_drive/

# 토큰 파일 확인
docker exec -it all-thing-eye-data-collector ls -la config/google_drive/token*.json

# 수동 실행
docker exec -it all-thing-eye-data-collector python scripts/daily_data_collection_mongo.py --sources drive
```

---

## 📝 체크리스트

디버깅 시 다음 항목들을 순서대로 확인:

- [ ] Data collector 컨테이너가 실행 중인가?
- [ ] 로그에서 자정 시간대에 실행 시도가 있었는가?
- [ ] 각 플러그인(Slack, Notion, Drive)의 에러 메시지 확인
- [ ] 타임존이 KST로 올바르게 설정되어 있는가?
- [ ] 환경 변수(API 토큰)가 모두 설정되어 있는가?
- [ ] MongoDB 연결이 정상인가?
- [ ] 플러그인이 `config.yaml`에서 활성화되어 있는가?
- [ ] 수동 실행 시 정상 작동하는가?
- [ ] MongoDB에 최근 24시간 내 데이터가 수집되었는가?

---

## 🆘 추가 도움

위 항목들을 모두 확인했는데도 문제가 해결되지 않으면:

1. 전체 로그를 파일로 저장:
   ```bash
   docker-compose -f docker-compose.prod.yml logs data-collector > collector_logs.txt
   ```

2. 환경 변수 확인 (민감 정보 제외):
   ```bash
   docker exec -it all-thing-eye-data-collector env | grep -E "(SLACK|NOTION|DRIVE)" > env_check.txt
   ```

3. 컨테이너 상태 확인:
   ```bash
   docker inspect all-thing-eye-data-collector > container_info.json
   ```

---

**Last Updated:** 2025-11-18  
**Maintained by:** All-Thing-Eye Development Team

