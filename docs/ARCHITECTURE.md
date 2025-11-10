# HR 데이터 파이프라인 시스템 아키텍처

## 📌 프로젝트 개요

팀 멤버들의 퍼포먼스 분석을 위한 데이터 파이프라인 시스템
- 다양한 데이터 소스에서 데이터 수집
- 멤버 중심의 통합 데이터베이스 구축
- AI 분석을 위한 데이터 제공

## 🎯 핵심 목표

1. **다중 소스 데이터 수집**: Slack, GitHub, Notion, Google Drive 등
2. **소스별 독립 DB 관리**: 각 데이터 소스마다 전용 DB 생성
3. **멤버 중심 통합**: 멤버 이름을 키로 하는 통합 쿼리 시스템
4. **확장 가능성**: 새 데이터 소스 추가 시 자동 통합
5. **AI 연동**: 프롬프트 AI에 최적화된 데이터 포맷 제공

## 🏗 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                     Data Sources Layer                      │
├──────────────┬──────────────┬──────────────┬────────────────┤
│    Slack     │   GitHub     │   Notion     │ Google Drive   │
│   API/SDK    │   API/SDK    │   API/SDK    │   API/SDK      │
└──────┬───────┴──────┬───────┴──────┬───────┴────────┬───────┘
       │              │              │                │
       └──────────────┼──────────────┼────────────────┘
                      │              │
              ┌───────▼──────────────▼──────┐
              │   Data Collectors Layer     │
              │  (Plugin Architecture)      │
              └───────┬─────────────────────┘
                      │
              ┌───────▼─────────────────────┐
              │   Source-Specific DBs       │
              │  ┌─────────────────────┐    │
              │  │ slack_db            │    │
              │  │ github_db           │    │
              │  │ notion_db           │    │
              │  │ google_drive_db     │    │
              │  └─────────────────────┘    │
              └───────┬─────────────────────┘
                      │
              ┌───────▼─────────────────────┐
              │  Integration Layer          │
              │  (Member-Centric Index)     │
              │  ┌─────────────────────┐    │
              │  │ member_index        │    │
              │  │ unified_query_api   │    │
              │  └─────────────────────┘    │
              └───────┬─────────────────────┘
                      │
              ┌───────▼─────────────────────┐
              │  AI Prompt Formatter        │
              │  (Performance Analysis)     │
              └─────────────────────────────┘
```

## 💾 데이터베이스 설계

### 1. 소스별 데이터베이스

각 데이터 소스는 독립적인 SQLite/PostgreSQL DB를 가집니다.

#### Slack DB
```sql
-- 메시지, 리액션, 채널 활동
messages: id, member_id, channel, timestamp, content, reactions
channels: id, name, members
threads: id, parent_message_id, reply_count
```

#### GitHub DB
```sql
-- 커밋, PR, 이슈, 리뷰
commits: id, member_id, repo, timestamp, message, additions, deletions
pull_requests: id, member_id, repo, status, created_at, merged_at
code_reviews: id, reviewer_id, pr_id, timestamp, comments
issues: id, assignee_id, status, created_at, closed_at
```

#### Notion DB
```sql
-- 페이지, 작성 내용, 수정 이력
pages: id, member_id, title, created_at, updated_at
edits: id, page_id, member_id, timestamp, content_length
```

#### Google Drive DB
```sql
-- 문서, 스프레드시트, 공유 활동
files: id, owner_id, name, type, created_at, modified_at
shares: id, file_id, shared_by, shared_with, timestamp
comments: id, file_id, member_id, timestamp, content
```

### 2. 통합 멤버 인덱스

모든 소스를 관통하는 멤버 중심 인덱스

```sql
-- 멤버 마스터 테이블
members:
  id (primary key)
  name
  email
  slack_user_id
  github_username
  notion_user_id
  google_email

-- 멤버별 활동 통합 뷰
member_activities:
  member_id
  source_type (slack/github/notion/drive)
  source_db
  activity_type
  timestamp
  metadata (JSON)
```

## 🔌 플러그인 아키텍처

새로운 데이터 소스를 쉽게 추가할 수 있도록 플러그인 시스템 구현

### 플러그인 인터페이스

```python
class DataSourcePlugin:
    """모든 데이터 소스 플러그인의 기본 인터페이스"""
    
    def get_source_name(self) -> str:
        """소스 이름 반환 (예: 'slack', 'github')"""
        pass
    
    def get_db_schema(self) -> dict:
        """DB 스키마 정의 반환"""
        pass
    
    def collect_data(self, config: dict) -> list:
        """데이터 수집"""
        pass
    
    def get_member_mapping(self) -> dict:
        """멤버 ID 매핑 정보 반환"""
        pass
    
    def extract_member_activities(self, data: list) -> list:
        """멤버별 활동 추출"""
        pass
```

### 자동 통합 프로세스

1. **플러그인 등록**: 새 소스 플러그인을 `plugins/` 디렉토리에 추가
2. **자동 발견**: 시스템이 플러그인을 자동으로 스캔하고 로드
3. **DB 생성**: 플러그인의 스키마를 기반으로 소스별 DB 자동 생성
4. **멤버 매핑**: 새 소스의 멤버 정보를 통합 인덱스에 자동 연결
5. **데이터 수집**: 스케줄러가 주기적으로 데이터 수집 실행

## 🔄 데이터 파이프라인 흐름

### 1단계: 데이터 수집 (Collection)

```python
for plugin in registered_plugins:
    data = plugin.collect_data(config)
    source_db = get_db(plugin.get_source_name())
    source_db.insert(data)
```

### 2단계: 멤버 매핑 (Mapping)

```python
for plugin in registered_plugins:
    member_mapping = plugin.get_member_mapping()
    update_member_index(member_mapping)
```

### 3단계: 통합 인덱싱 (Integration)

```python
for plugin in registered_plugins:
    activities = plugin.extract_member_activities()
    for activity in activities:
        member_id = resolve_member_id(activity)
        member_activities.insert({
            'member_id': member_id,
            'source': plugin.get_source_name(),
            'activity': activity
        })
```

### 4단계: AI 포맷팅 (Formatting)

```python
def get_member_performance_data(member_name: str):
    member = get_member_by_name(member_name)
    
    # 모든 소스에서 활동 데이터 수집
    slack_data = query_slack_db(member.slack_user_id)
    github_data = query_github_db(member.github_username)
    notion_data = query_notion_db(member.notion_user_id)
    drive_data = query_drive_db(member.google_email)
    
    # AI 프롬프트 포맷으로 변환
    return format_for_ai({
        'member': member_name,
        'slack_activity': slack_data,
        'github_contribution': github_data,
        'notion_documentation': notion_data,
        'drive_collaboration': drive_data
    })
```

## 📊 멤버 중심 쿼리 예시

```python
# 특정 멤버의 모든 활동 조회
get_member_all_activities("홍길동", date_range="2025-01-01~2025-01-31")

# 멤버별 코드 기여도
get_member_github_stats("홍길동")

# 멤버별 커뮤니케이션 활동
get_member_slack_stats("홍길동")

# 멤버별 문서화 기여도
get_member_notion_stats("홍길동")

# 통합 퍼포먼스 리포트
generate_performance_report("홍길동")
```

## 🛠 기술 스택

### Backend
- **언어**: Python 3.11+
- **웹 프레임워크**: FastAPI
- **데이터베이스**: 
  - SQLite (개발/소규모)
  - PostgreSQL (프로덕션)
- **ORM**: SQLAlchemy
- **작업 스케줄러**: APScheduler
- **API 클라이언트**: 
  - slack-sdk
  - PyGithub
  - notion-client
  - google-api-python-client

### 데이터 처리
- **Pandas**: 데이터 변환 및 분석
- **Pydantic**: 데이터 검증

### 인프라
- **컨테이너**: Docker
- **오케스트레이션**: Docker Compose
- **모니터링**: Prometheus + Grafana (선택사항)

## 🔐 보안 및 개인정보 보호

1. **API 키 관리**: 환경 변수 또는 비밀 관리 시스템
2. **데이터 암호화**: 민감 정보는 암호화 저장
3. **접근 제어**: RBAC 기반 권한 관리
4. **개인정보 처리**: 
   - 개인 식별 정보 최소화
   - 데이터 익명화 옵션
   - GDPR/개인정보보호법 준수
5. **감사 로그**: 모든 데이터 접근 기록

## 📈 확장성 고려사항

1. **수평 확장**: 데이터 수집기를 독립적으로 스케일 가능
2. **캐싱**: Redis를 활용한 쿼리 결과 캐싱
3. **비동기 처리**: 대량 데이터 수집 시 백그라운드 작업
4. **파티셔닝**: 시계열 데이터는 날짜별 파티션

## 🚀 배포 전략

### 개발 환경
```bash
docker-compose up -d
python manage.py migrate
python manage.py collect --source all
```

### 프로덕션 환경
- CI/CD 파이프라인 (GitHub Actions)
- 자동 백업 시스템
- 모니터링 및 알림 설정

## 📝 다음 단계

1. ✅ 프로젝트 구조 생성
2. ✅ 기본 플러그인 인터페이스 구현
3. ✅ Slack 플러그인 구현 (첫 번째 소스)
4. ✅ 멤버 인덱스 시스템 구현
5. ✅ GitHub 플러그인 추가
6. ✅ Notion, Google Drive 플러그인 추가
7. ✅ AI 포맷터 구현
8. ✅ API 서버 구축
9. ✅ 스케줄러 설정
10. ✅ 테스트 및 문서화

