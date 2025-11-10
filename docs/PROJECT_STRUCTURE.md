# 프로젝트 구조

## 📂 디렉토리 구조

```
all-thing-eye/
│
├── 📄 README.md                    # 프로젝트 소개 및 시작 가이드
├── 📄 requirements.txt             # Python 의존성
├── 📄 pyproject.toml              # 프로젝트 메타데이터 및 빌드 설정
├── 📄 .gitignore                  # Git 무시 파일 목록
├── 📄 .env.example                # 환경 변수 템플릿
│
├── 📁 docs/                       # 문서
│   ├── ARCHITECTURE.md           # 시스템 아키텍처 설계
│   ├── IMPLEMENTATION_PLAN.md    # 구현 계획서
│   └── PROJECT_STRUCTURE.md      # 이 파일
│
├── 📁 src/                        # 소스 코드
│   ├── __init__.py
│   │
│   ├── 📁 core/                   # 핵심 시스템
│   │   ├── __init__.py
│   │   ├── database.py           # 데이터베이스 매니저 (TODO)
│   │   ├── plugin_loader.py      # 플러그인 자동 로더 (TODO)
│   │   ├── member_index.py       # 멤버 통합 인덱스 (TODO)
│   │   └── config.py             # 설정 관리 (TODO)
│   │
│   ├── 📁 plugins/                # 데이터 소스 플러그인
│   │   ├── __init__.py
│   │   ├── base.py               # 베이스 플러그인 인터페이스 (TODO)
│   │   ├── slack_plugin.py       # Slack 플러그인 (TODO)
│   │   ├── github_plugin.py      # GitHub 플러그인 (TODO)
│   │   ├── notion_plugin.py      # Notion 플러그인 (TODO)
│   │   └── google_drive_plugin.py # Google Drive 플러그인 (TODO)
│   │
│   ├── 📁 models/                 # 데이터 모델
│   │   ├── __init__.py
│   │   ├── member.py             # 멤버 모델 (TODO)
│   │   ├── activity.py           # 활동 모델 (TODO)
│   │   └── schemas.py            # Pydantic 스키마 (TODO)
│   │
│   ├── 📁 integrations/           # 통합 레이어
│   │   ├── __init__.py
│   │   ├── query_engine.py       # 통합 쿼리 엔진 (TODO)
│   │   └── ai_formatter.py       # AI 프롬프트 포맷터 (TODO)
│   │
│   ├── 📁 api/                    # REST API
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI 앱 (TODO)
│   │   ├── dependencies.py       # 의존성 주입 (TODO)
│   │   └── 📁 routes/
│   │       ├── __init__.py
│   │       ├── members.py        # 멤버 라우트 (TODO)
│   │       ├── activities.py     # 활동 라우트 (TODO)
│   │       └── reports.py        # 리포트 라우트 (TODO)
│   │
│   ├── 📁 scheduler/              # 스케줄러
│   │   ├── __init__.py
│   │   ├── main.py               # 스케줄러 메인 (TODO)
│   │   └── jobs.py               # 작업 정의 (TODO)
│   │
│   └── 📁 utils/                  # 유틸리티
│       ├── __init__.py
│       ├── logger.py             # 로깅 설정 (TODO)
│       └── helpers.py            # 헬퍼 함수 (TODO)
│
├── 📁 tests/                      # 테스트
│   ├── __init__.py
│   ├── 📁 unit/                   # 단위 테스트
│   ├── 📁 integration/            # 통합 테스트
│   └── 📁 fixtures/               # 테스트 픽스처
│
├── 📁 scripts/                    # 유틸리티 스크립트
│   ├── setup.py                  # 초기 설정 스크립트
│   ├── run_dev.sh               # 개발 서버 실행
│   └── collect_data.sh          # 데이터 수집 스크립트
│
├── 📁 config/                     # 설정 파일
│   ├── config.yaml              # 메인 설정 파일
│   ├── config.dev.yaml          # 개발 환경 설정 (TODO)
│   └── config.prod.yaml         # 프로덕션 설정 (TODO)
│
├── 📁 docker/                     # Docker 관련
│   ├── Dockerfile               # Docker 이미지 정의
│   └── docker-compose.yaml      # Docker Compose 설정
│
├── 📁 data/                       # 데이터 (gitignore)
│   ├── 📁 databases/             # SQLite 데이터베이스
│   ├── 📁 raw/                   # 원본 데이터
│   ├── 📁 processed/             # 가공된 데이터
│   ├── 📁 cache/                 # 캐시
│   └── 📁 backups/               # 백업
│
├── 📁 logs/                       # 로그 파일 (gitignore)
│
├── 📁 credentials/                # API 인증 정보 (gitignore)
│
└── 📁 templates/                  # AI 프롬프트 템플릿
    ├── performance_analysis.txt
    └── team_insights.txt
```

## 🎯 핵심 모듈 설명

### Core (핵심 시스템)

#### `database.py`
- 데이터베이스 연결 관리
- 소스별 DB 생성 및 관리
- 쿼리 실행 인터페이스

#### `plugin_loader.py`
- 플러그인 자동 발견 (auto-discovery)
- 플러그인 로드 및 검증
- 플러그인 생명주기 관리

#### `member_index.py`
- 멤버 통합 인덱스 관리
- 멤버 ID 매핑 (소스별 사용자 ID ↔ 통합 멤버 ID)
- 멤버 활동 통합 뷰

#### `config.py`
- YAML 설정 파일 파싱
- 환경 변수 관리
- 설정 검증

### Plugins (플러그인)

#### `base.py`
```python
class DataSourcePlugin(ABC):
    """모든 플러그인의 기본 인터페이스"""
    - get_source_name()
    - get_db_schema()
    - authenticate()
    - collect_data()
    - get_member_mapping()
    - extract_member_activities()
```

#### 각 플러그인 (`*_plugin.py`)
- API 인증 및 연결
- 데이터 수집 로직
- 소스별 DB 스키마 정의
- 멤버 매핑 정보 제공
- 활동 데이터 추출 및 정규화

### Models (데이터 모델)

#### `member.py`
- Member SQLAlchemy 모델
- 멤버 관련 데이터베이스 테이블

#### `activity.py`
- Activity SQLAlchemy 모델
- 활동 관련 데이터베이스 테이블

#### `schemas.py`
- Pydantic 스키마 정의
- API 요청/응답 검증
- 데이터 직렬화/역직렬화

### Integrations (통합 레이어)

#### `query_engine.py`
- 멤버 중심 통합 쿼리 API
- 여러 소스 DB를 조합한 쿼리
- 쿼리 결과 캐싱

#### `ai_formatter.py`
- 멤버 데이터를 AI 프롬프트 형식으로 변환
- 프롬프트 템플릿 렌더링
- 데이터 요약 및 포맷팅

### API (REST API)

#### `main.py`
- FastAPI 애플리케이션 초기화
- 라우터 등록
- 미들웨어 설정
- 헬스체크 엔드포인트

#### Routes
- `members.py`: 멤버 조회, 등록, 수정
- `activities.py`: 활동 데이터 조회
- `reports.py`: 퍼포먼스 리포트 생성

### Scheduler (스케줄러)

#### `main.py`
- APScheduler 초기화
- 작업 스케줄 등록
- 백그라운드 실행

#### `jobs.py`
- 주기적 데이터 수집 작업
- 데이터 정리 작업
- 통합 인덱스 업데이트 작업

## 🔄 데이터 흐름

```
1. Scheduler 트리거
   ↓
2. Plugin Loader가 활성화된 플러그인 로드
   ↓
3. 각 플러그인이 데이터 수집
   ↓
4. 소스별 DB에 데이터 저장
   ↓
5. Member Index 업데이트 (멤버 매핑)
   ↓
6. 통합 활동 테이블 업데이트
   ↓
7. API를 통해 데이터 조회
   ↓
8. AI Formatter가 프롬프트 생성
```

## 🚀 개발 워크플로우

### 1. 새 데이터 소스 추가

1. `src/plugins/`에 새 플러그인 파일 생성
2. `DataSourcePlugin` 클래스 상속
3. 필수 메서드 구현
4. `config/config.yaml`에 설정 추가
5. 플러그인이 자동으로 로드됨

### 2. API 엔드포인트 추가

1. `src/api/routes/`에 새 라우트 파일 생성
2. 라우트 함수 정의
3. `src/api/main.py`에 라우터 등록

### 3. 데이터 모델 추가

1. `src/models/`에 모델 정의
2. Alembic 마이그레이션 생성
3. 마이그레이션 실행

### 4. 스케줄 작업 추가

1. `src/scheduler/jobs.py`에 작업 함수 정의
2. `config/config.yaml`의 scheduler 섹션에 작업 추가

## 📝 다음 단계 구현 순서

1. **Core 시스템**
   - [ ] `database.py`: 데이터베이스 매니저
   - [ ] `config.py`: 설정 관리
   - [ ] `plugin_loader.py`: 플러그인 로더
   - [ ] `member_index.py`: 멤버 인덱스

2. **첫 번째 플러그인 (Slack)**
   - [ ] `plugins/base.py`: 베이스 플러그인
   - [ ] `plugins/slack_plugin.py`: Slack 플러그인

3. **모델 및 스키마**
   - [ ] `models/member.py`
   - [ ] `models/activity.py`
   - [ ] `models/schemas.py`

4. **통합 레이어**
   - [ ] `integrations/query_engine.py`
   - [ ] `integrations/ai_formatter.py`

5. **API 서버**
   - [ ] `api/main.py`
   - [ ] `api/routes/members.py`
   - [ ] `api/routes/activities.py`

6. **추가 플러그인**
   - [ ] GitHub
   - [ ] Notion
   - [ ] Google Drive

7. **스케줄러**
   - [ ] `scheduler/main.py`
   - [ ] `scheduler/jobs.py`

8. **유틸리티**
   - [ ] `utils/logger.py`
   - [ ] `utils/helpers.py`

## 🧪 테스트 전략

- **Unit Tests**: 각 모듈의 개별 함수 테스트
- **Integration Tests**: 플러그인-DB, API-DB 통합 테스트
- **End-to-End Tests**: 전체 데이터 파이프라인 테스트

## 📚 참고

자세한 내용은 다음 문서를 참고하세요:
- [아키텍처 설계](ARCHITECTURE.md)
- [구현 계획](IMPLEMENTATION_PLAN.md)

