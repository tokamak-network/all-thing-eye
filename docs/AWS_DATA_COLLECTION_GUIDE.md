# AWS EC2 데이터 수집 문제 해결 가이드

**작성일**: 2025-11-18  
**대상**: AWS EC2 환경에서 데이터 수집 설정

이 문서는 AWS EC2 환경에서 Notion, Slack, Google Drive 데이터 수집을 설정하고 문제를 해결하는 방법을 정리합니다.

---

## 📋 목차

1. [개요](#개요)
2. [공통 문제 해결](#공통-문제-해결)
3. [Notion 데이터 수집](#notion-데이터-수집)
4. [Slack 데이터 수집](#slack-데이터-수집)
5. [Google Drive 데이터 수집](#google-drive-데이터-수집)
6. [배포 후 데이터 수집 실행](#배포-후-데이터-수집-실행)
7. [트러블슈팅](#트러블슈팅)

---

## 🎯 개요

### 환경

- **서버**: AWS EC2 (Ubuntu 24.04 LTS)
- **배포 방식**: Docker Compose
- **데이터베이스**: MongoDB
- **데이터 소스**: GitHub, Slack, Notion, Google Drive

### 주요 이슈

1. **플러그인 반환 타입 불일치**: `collect_data()`가 리스트를 반환하지만 `save_data()`는 딕셔너리를 기대
2. **Timezone 문제**: Naive datetime vs timezone-aware datetime 비교 오류
3. **OAuth 인증**: 로컬에서 생성한 토큰 파일을 EC2로 전송 필요
4. **파일 권한**: Docker 컨테이너 내부 파일 권한 문제
5. **컨테이너 재시작**: 임시 파일(`/tmp`) 소실

---

## 🔧 공통 문제 해결

### 1. 플러그인 반환 타입 통일

**문제**: 모든 MongoDB 플러그인의 `collect_data()`는 `List[Dict]`를 반환하지만, `save_data()`는 `Dict`를 기대합니다.

**해결**: `scripts/initial_data_collection_mongo.py`에서 리스트의 첫 번째 요소를 추출합니다.

```python
# ❌ 잘못된 방법
data = plugin.collect_data(start_date=start_date, end_date=end_date)
await plugin.save_data(data)  # TypeError: 'list' object has no attribute 'get'

# ✅ 올바른 방법
data_list = plugin.collect_data(start_date=start_date, end_date=end_date)
if data_list:
    await plugin.save_data(data_list[0])  # 리스트에서 딕셔너리 추출
```

**적용 위치**:
- `collect_slack()` 함수
- `collect_notion()` 함수
- `collect_google_drive()` 함수

---

### 2. MongoDB 인덱스 중복 에러 무시

**문제**: 
```
E11000 duplicate key error collection: all_thing_eye.member_identifiers 
index: source_type_1_source_user_id_1 dup key: { source_type: null, source_user_id: null }
```

**원인**: 기존 데이터와 인덱스 충돌 (일반적으로 무해함)

**해결**: 이 에러는 **무시해도 됩니다**. 데이터 수집은 정상적으로 진행됩니다.

필요 시 MongoDB를 초기화:
```bash
# ⚠️ 주의: 모든 데이터가 삭제됩니다
docker-compose -f docker-compose.prod.yml down
docker volume rm all-thing-eye_mongodb-data
docker-compose -f docker-compose.prod.yml up -d
```

---

## 📝 Notion 데이터 수집

### 발생한 문제들

#### 1. 리스트 반환 타입 문제

**에러**:
```
AttributeError: 'list' object has no attribute 'get'
```

**해결**: [공통 문제 해결 #1](#1-플러그인-반환-타입-통일) 참고

---

#### 2. Timezone 비교 오류

**에러**:
```
TypeError: can't compare offset-naive and offset-aware datetimes
```

**원인**: Notion API는 timezone-aware datetime을 반환하지만, 스크립트는 naive datetime을 사용

**해결**: `scripts/initial_data_collection_mongo.py`의 `collect_notion()` 함수 수정

```python
# 수정 전
end_date = datetime.utcnow()
start_date = end_date - timedelta(days=days)
data = plugin.collect_data(start_date=start_date, end_date=end_date)

# 수정 후
from datetime import timezone
end_date = datetime.now(timezone.utc).replace(tzinfo=None)
start_date = end_date - timedelta(days=days)

# Timezone-aware datetime으로 변환
start_date_tz = start_date.replace(tzinfo=timezone.utc)
end_date_tz = end_date.replace(tzinfo=timezone.utc)

data_list = plugin.collect_data(start_date=start_date_tz, end_date=end_date_tz)
if data_list:
    await plugin.save_data(data_list[0])
```

---

#### 3. MongoDB 중복 키 에러 (id: null)

**에러**:
```
E11000 duplicate key error collection: all_thing_eye.notion_pages 
index: id_1 dup key: { id: null }
```

**원인**: MongoDB 스키마에 `id` 필드가 unique index로 설정되어 있으나, 일부 문서에서 `id`가 누락됨

**해결**: `src/plugins/notion_plugin_mongo.py` 수정

**수정 1**: `collect_data()`에서 `id` 필드 명시적으로 추가

```python
# pages 수집 시
page_data = {
    'id': page['id'],  # ✅ 추가
    'notion_id': page['id'],
    'title': self._extract_title(page.get('properties', {})),
    # ... 나머지 필드
}

# databases 수집 시
db_data = {
    'id': db['id'],  # ✅ 추가
    'notion_id': db['id'],
    'title': self._extract_title(db.get('properties', {})),
    # ... 나머지 필드
}
```

**수정 2**: `id`가 없는 항목은 스킵

```python
# pages 수집 시
for page in response.get('results', []):
    # id가 없으면 스킵
    page_id = page.get('id')
    if not page_id:
        self.logger.warning(f"⚠️  Skipping page without id: {page}")
        continue
    # ... 계속

# databases 수집 시
for db in response.get('results', []):
    # id가 없으면 스킵
    db_id = db.get('id')
    if not db_id:
        self.logger.warning(f"⚠️  Skipping database without id: {db}")
        continue
    # ... 계속
```

**수정 3**: `save_data()`에서도 `id` 필드 추가

```python
# pages 저장 시
page_doc = {
    'id': page.get('id') or page['notion_id'],  # ✅ 추가 (fallback 포함)
    'page_id': page['notion_id'],
    'notion_id': page['notion_id'],
    # ... 나머지 필드
}

# databases 저장 시
db_doc = {
    'id': db.get('id') or db['notion_id'],  # ✅ 추가 (fallback 포함)
    'database_id': db['notion_id'],
    'notion_id': db['notion_id'],
    # ... 나머지 필드
}
```

---

### Notion 데이터 수집 명령어

```bash
# EC2에서 실행
docker exec -it all-thing-eye-data-collector bash

# 컨테이너 내부에서 실행
python scripts/initial_data_collection_mongo.py --days 30 --sources notion
```

---

## 💬 Slack 데이터 수집

### 발생한 문제

#### 리스트 반환 타입 문제

**에러**:
```
AttributeError: 'list' object has no attribute 'get'
```

**해결**: [공통 문제 해결 #1](#1-플러그인-반환-타입-통일) 참고

### 수정 내용

`scripts/initial_data_collection_mongo.py`의 `collect_slack()` 함수:

```python
# 수정 전
data = plugin.collect_data(start_date=start_date, end_date=end_date)
await plugin.save_data(data)

# 수정 후
data_list = plugin.collect_data(start_date=start_date, end_date=end_date)
if data_list:
    await plugin.save_data(data_list[0])  # 리스트에서 딕셔너리 추출
```

---

### Slack 데이터 수집 명령어

```bash
# EC2에서 실행
docker exec -it all-thing-eye-data-collector bash

# 컨테이너 내부에서 실행
python scripts/initial_data_collection_mongo.py --days 14 --sources slack
```

---

## 📁 Google Drive 데이터 수집

Google Drive는 OAuth 인증이 필요하여 **가장 복잡한 설정**이 필요합니다.

### 발생한 문제들

#### 1. 브라우저 인증 오류

**에러**:
```
❌ Authentication failed: could not locate runnable browser
```

**원인**: Docker 컨테이너 내부에는 웹 브라우저가 없어서 OAuth 인증 불가

**해결**: 로컬에서 생성한 토큰 파일을 EC2로 전송

---

#### 2. 토큰 파일 생성 (로컬에서)

**전제 조건**: 
- Google Cloud Console에서 OAuth 2.0 클라이언트 생성 완료
- `config/google_drive/credentials.json` 파일 존재

**로컬에서 토큰 생성**:

```bash
# 로컬 머신에서 실행
cd /path/to/all-thing-eye
python -c "
from src.plugins.google_drive_plugin_mongo import GoogleDrivePluginMongo
from src.core.mongodb import get_mongo_manager
import os

config = {
    'uri': os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
    'database': os.getenv('MONGODB_DATABASE', 'all_thing_eye')
}
mongo_manager = get_mongo_manager(config)

plugin = GoogleDrivePluginMongo(mongo_manager)
# 이 시점에서 브라우저가 열리고 Google 로그인 진행
print('Token generated successfully!')
"
```

브라우저가 열리면:
1. Google 계정으로 로그인
2. 권한 승인
3. `config/google_drive/token_admin.pickle` 파일 생성됨

---

#### 3. 토큰 파일 전송 (로컬 → EC2)

**로컬 머신에서 실행**:

```bash
# SCP로 토큰 파일 전송
scp -i ~/Desktop/key/all-thing-eye-key.pem \
  config/google_drive/token_admin.pickle \
  ubuntu@<EC2_IP>:~/all-thing-eye/config/google_drive/
```

---

#### 4. 토큰 파일을 Docker 컨테이너로 복사

**EC2에서 실행**:

```bash
# 토큰 파일을 컨테이너 내부로 복사 (/tmp에 저장)
docker cp ~/all-thing-eye/config/google_drive/token_admin.pickle \
  all-thing-eye-data-collector:/tmp/token_admin.pickle

# 권한 설정 (중요!)
docker exec all-thing-eye-data-collector chown root:root /tmp/token_admin.pickle
docker exec all-thing-eye-data-collector chmod 666 /tmp/token_admin.pickle
```

**⚠️ 주의**: Docker 컨테이너가 재시작되면 `/tmp` 디렉토리의 파일이 삭제됩니다. 컨테이너를 재시작한 경우 이 명령어를 다시 실행해야 합니다.

---

#### 5. 매개변수 오류 수정

**에러**:
```
TypeError: GoogleDrivePluginMongo.collect_data() got an unexpected keyword argument 'days'
```

**원인**: `GoogleDrivePluginMongo.collect_data()`는 `start_date`, `end_date`를 받지만, 스크립트는 `days`를 전달

**해결**: `scripts/initial_data_collection_mongo.py`의 `collect_google_drive()` 함수 수정

```python
# 수정 전
data = plugin.collect_data(days=days)

# 수정 후
from datetime import timezone
end_date = datetime.now(timezone.utc).replace(tzinfo=None)
start_date = end_date - timedelta(days=days)

logger.info(f"   📅 Date range: {start_date.date()} to {end_date.date()}")

data_list = plugin.collect_data(start_date=start_date, end_date=end_date)
if data_list:
    await plugin.save_data(data_list[0])
```

---

#### 6. 리스트 반환 타입 문제

**에러**:
```
AttributeError: 'list' object has no attribute 'get'
```

**해결**: [공통 문제 해결 #1](#1-플러그인-반환-타입-통일) 참고

---

### Google Drive 데이터 수집 명령어

```bash
# EC2에서 실행
docker exec -it all-thing-eye-data-collector bash

# 컨테이너 내부에서 실행
python scripts/initial_data_collection_mongo.py --days 30 --sources drive
```

---

### Google Drive 설정 파일 수정

`config/config.yaml`에서 토큰 경로를 `/tmp`로 변경:

```yaml
google_drive:
  enabled: true
  credentials_path: "config/google_drive/credentials.json"
  token_path: "/tmp/token_admin.pickle"  # ✅ Docker 환경에서는 /tmp 사용
```

---

## 🚀 배포 후 데이터 수집 실행

### 전체 데이터 소스 수집 (권장)

```bash
# EC2 SSH 접속
ssh -i ~/Desktop/key/all-thing-eye-key.pem ubuntu@<EC2_IP>

# 프로젝트 디렉토리로 이동
cd ~/all-thing-eye

# (Google Drive만) 토큰 파일 복사
docker cp ~/all-thing-eye/config/google_drive/token_admin.pickle \
  all-thing-eye-data-collector:/tmp/token_admin.pickle

docker exec all-thing-eye-data-collector chown root:root /tmp/token_admin.pickle
docker exec all-thing-eye-data-collector chmod 666 /tmp/token_admin.pickle

# 데이터 수집 컨테이너 진입
docker exec -it all-thing-eye-data-collector bash

# 최근 2주 데이터 수집 (모든 소스)
python scripts/initial_data_collection_mongo.py --days 14
```

---

### 개별 데이터 소스 수집

```bash
# GitHub만 수집
python scripts/initial_data_collection_mongo.py --days 14 --sources github

# Slack만 수집
python scripts/initial_data_collection_mongo.py --days 14 --sources slack

# Notion만 수집
python scripts/initial_data_collection_mongo.py --days 30 --sources notion

# Google Drive만 수집 (토큰 파일 필수!)
python scripts/initial_data_collection_mongo.py --days 30 --sources drive
```

---

### 데이터 수집 확인

```bash
# 웹 브라우저에서 확인
https://eye.tokamak.network/database

# 또는 MongoDB 직접 조회
docker exec -it all-thing-eye-mongodb mongosh

# MongoDB 쉘에서
use all_thing_eye

# 각 컬렉션의 문서 수 확인
db.github_commits.countDocuments()
db.slack_messages.countDocuments()
db.notion_pages.countDocuments()
db.drive_activities.countDocuments()
```

---

## 🔍 트러블슈팅

### 1. 컨테이너 재시작 후 Google Drive 인증 실패

**증상**:
```
❌ Authentication failed: could not locate runnable browser
```

**원인**: 컨테이너 재시작으로 `/tmp/token_admin.pickle` 파일이 삭제됨

**해결**:
```bash
# 토큰 파일 다시 복사
docker cp ~/all-thing-eye/config/google_drive/token_admin.pickle \
  all-thing-eye-data-collector:/tmp/token_admin.pickle

docker exec all-thing-eye-data-collector chown root:root /tmp/token_admin.pickle
docker exec all-thing-eye-data-collector chmod 666 /tmp/token_admin.pickle
```

---

### 2. 토큰 파일 권한 에러

**증상**:
```
❌ Authentication failed: [Errno 13] Permission denied: '/tmp/token_admin.pickle'
```

**해결**:
```bash
# 소유자를 root로 변경
docker exec all-thing-eye-data-collector chown root:root /tmp/token_admin.pickle

# 읽기/쓰기 권한 부여
docker exec all-thing-eye-data-collector chmod 666 /tmp/token_admin.pickle
```

---

### 3. 코드 변경 후 컨테이너가 업데이트되지 않음

**증상**: `git pull` 후에도 이전 코드가 실행됨

**원인**: Docker 이미지가 캐시되어 있음

**해결**:
```bash
# 코드 변경사항 가져오기
git pull

# 캐시 없이 재빌드
docker-compose -f docker-compose.prod.yml build --no-cache data-collector

# 컨테이너 재시작
docker-compose -f docker-compose.prod.yml up -d data-collector

# ⚠️ Google Drive 사용 시 토큰 파일 다시 복사 필요!
docker cp ~/all-thing-eye/config/google_drive/token_admin.pickle \
  all-thing-eye-data-collector:/tmp/token_admin.pickle
docker exec all-thing-eye-data-collector chown root:root /tmp/token_admin.pickle
docker exec all-thing-eye-data-collector chmod 666 /tmp/token_admin.pickle
```

---

### 4. MongoDB 중복 키 에러

**증상**:
```
E11000 duplicate key error collection: all_thing_eye.member_identifiers 
index: source_type_1_source_user_id_1 dup key: { source_type: null, source_user_id: null }
```

**해결**: 이 에러는 **무시해도 됩니다**. 데이터 수집은 정상적으로 진행됩니다.

필요 시 MongoDB 초기화:
```bash
# ⚠️ 주의: 모든 데이터가 삭제됩니다
docker-compose -f docker-compose.prod.yml down
docker volume rm all-thing-eye_mongodb-data
docker-compose -f docker-compose.prod.yml up -d
```

---

### 5. Notion API 속도 제한

**증상**:
```
RateLimitError: Rate limit exceeded
```

**해결**: 
- Notion API는 속도 제한이 있습니다 (초당 3회)
- 플러그인에 이미 재시도 로직이 구현되어 있으므로 기다리면 자동으로 재시도됩니다
- 장기간 데이터를 수집할 때는 여러 번 나눠서 실행하는 것을 권장합니다

---

### 6. 데이터 수집 로그 확인

```bash
# 컨테이너 로그 확인
docker logs all-thing-eye-data-collector

# 실시간 로그 모니터링
docker logs -f all-thing-eye-data-collector

# 마지막 100줄만 확인
docker logs --tail 100 all-thing-eye-data-collector
```

---

## 📚 참고 자료

- [AWS Deployment Guide](./AWS_DEPLOYMENT_GUIDE.md)
- [Report Guidelines](./REPORT_GUIDELINES.md)
- [Database Schema](./DATABASE_SCHEMA.md)
- [Slack Setup Guide](./SLACK_SETUP.md)

---

## 🆘 추가 지원

문제가 해결되지 않으면:

1. GitHub 이슈 생성: [All-Thing-Eye Issues](https://github.com/tokamak-network/all-thing-eye/issues)
2. 로그 파일 첨부:
   ```bash
   docker logs all-thing-eye-data-collector > data-collector.log
   ```
3. 환경 정보 제공:
   - Ubuntu 버전: `lsb_release -a`
   - Docker 버전: `docker --version`
   - Docker Compose 버전: `docker-compose --version`

---

**마지막 업데이트**: 2025-11-18  
**작성자**: All-Thing-Eye Development Team

