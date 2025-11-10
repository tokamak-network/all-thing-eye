# 구현 계획서

## 📅 Phase별 구현 일정

### Phase 1: 기반 구조 구축 (1-2일)

#### 1.1 프로젝트 초기화
- [ ] Python 프로젝트 구조 생성
- [ ] 의존성 관리 (`requirements.txt`, `pyproject.toml`)
- [ ] Docker 환경 설정
- [ ] 기본 설정 파일 (`config.yaml`)

#### 1.2 코어 시스템
- [ ] 데이터베이스 매니저 구현
- [ ] 플러그인 로더 구현
- [ ] 멤버 인덱스 시스템 구현

### Phase 2: 첫 번째 데이터 소스 (2-3일)

#### 2.1 Slack 플러그인
- [ ] Slack API 연동
- [ ] Slack DB 스키마 생성
- [ ] 데이터 수집 로직 구현
- [ ] 멤버 매핑 로직 구현
- [ ] 테스트

### Phase 3: 추가 데이터 소스 (5-7일)

#### 3.1 GitHub 플러그인
- [ ] GitHub API 연동
- [ ] GitHub DB 스키마 생성
- [ ] 커밋, PR, 이슈 수집
- [ ] 코드 리뷰 데이터 수집

#### 3.2 Notion 플러그인
- [ ] Notion API 연동
- [ ] Notion DB 스키마 생성
- [ ] 페이지 및 편집 이력 수집

#### 3.3 Google Drive 플러그인
- [ ] Google Drive API 연동
- [ ] Drive DB 스키마 생성
- [ ] 파일 및 공유 활동 수집

### Phase 4: 통합 쿼리 레이어 (2-3일)

#### 4.1 멤버 중심 쿼리 API
- [ ] 통합 쿼리 인터페이스 설계
- [ ] 멤버별 활동 집계 함수
- [ ] 성능 최적화 (인덱싱, 캐싱)

#### 4.2 AI 프롬프트 포맷터
- [ ] 데이터 포맷 정의
- [ ] 포맷 변환 로직 구현
- [ ] 프롬프트 템플릿 작성

### Phase 5: API 서버 및 스케줄러 (2-3일)

#### 5.1 REST API
- [ ] FastAPI 서버 구현
- [ ] 엔드포인트 설계
- [ ] API 문서 생성 (Swagger)

#### 5.2 스케줄러
- [ ] APScheduler 설정
- [ ] 주기적 데이터 수집 작업
- [ ] 에러 핸들링 및 재시도 로직

### Phase 6: 테스트 및 배포 (2-3일)

#### 6.1 테스트
- [ ] 유닛 테스트 작성
- [ ] 통합 테스트
- [ ] 성능 테스트

#### 6.2 배포
- [ ] Docker 이미지 빌드
- [ ] Docker Compose 설정
- [ ] 배포 스크립트 작성
- [ ] 모니터링 설정

---

## 🗂 프로젝트 구조

```
all-thing-eye/
├── docs/                           # 문서
│   ├── ARCHITECTURE.md
│   ├── IMPLEMENTATION_PLAN.md
│   └── API_REFERENCE.md
│
├── src/                            # 소스 코드
│   ├── core/                       # 코어 시스템
│   │   ├── __init__.py
│   │   ├── database.py            # DB 매니저
│   │   ├── plugin_loader.py       # 플러그인 로더
│   │   ├── member_index.py        # 멤버 인덱스
│   │   └── config.py              # 설정 관리
│   │
│   ├── plugins/                    # 데이터 소스 플러그인
│   │   ├── __init__.py
│   │   ├── base.py                # 베이스 플러그인 인터페이스
│   │   ├── slack_plugin.py
│   │   ├── github_plugin.py
│   │   ├── notion_plugin.py
│   │   └── google_drive_plugin.py
│   │
│   ├── models/                     # 데이터 모델
│   │   ├── __init__.py
│   │   ├── member.py
│   │   ├── activity.py
│   │   └── schemas.py
│   │
│   ├── integrations/               # 통합 레이어
│   │   ├── __init__.py
│   │   ├── query_engine.py        # 통합 쿼리
│   │   └── ai_formatter.py        # AI 포맷터
│   │
│   ├── api/                        # REST API
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI 앱
│   │   ├── routes/
│   │   │   ├── members.py
│   │   │   ├── activities.py
│   │   │   └── reports.py
│   │   └── dependencies.py
│   │
│   ├── scheduler/                  # 스케줄러
│   │   ├── __init__.py
│   │   └── jobs.py
│   │
│   └── utils/                      # 유틸리티
│       ├── __init__.py
│       ├── logger.py
│       └── helpers.py
│
├── tests/                          # 테스트
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
├── scripts/                        # 유틸리티 스크립트
│   ├── setup.sh
│   ├── migrate.py
│   └── seed_data.py
│
├── config/                         # 설정 파일
│   ├── config.yaml
│   ├── config.dev.yaml
│   └── config.prod.yaml
│
├── data/                           # 데이터 디렉토리 (gitignore)
│   └── databases/
│
├── docker/                         # Docker 관련
│   ├── Dockerfile
│   └── docker-compose.yaml
│
├── .env.example                    # 환경 변수 템플릿
├── .gitignore
├── requirements.txt                # Python 의존성
├── pyproject.toml                  # 프로젝트 메타데이터
└── README.md
```

---

## 🔧 상세 구현 가이드

### 1. 플러그인 베이스 클래스

```python
# src/plugins/base.py
from abc import ABC, abstractmethod
from typing import Dict, List, Any
from datetime import datetime

class DataSourcePlugin(ABC):
    """모든 데이터 소스 플러그인의 기본 인터페이스"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.source_name = self.get_source_name()
    
    @abstractmethod
    def get_source_name(self) -> str:
        """소스 이름 반환 (예: 'slack', 'github')"""
        pass
    
    @abstractmethod
    def get_db_schema(self) -> Dict[str, str]:
        """
        DB 스키마 정의 반환
        반환 형식: {"table_name": "CREATE TABLE SQL"}
        """
        pass
    
    @abstractmethod
    def authenticate(self) -> bool:
        """API 인증"""
        pass
    
    @abstractmethod
    def collect_data(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        데이터 수집
        Args:
            start_date: 수집 시작 날짜
            end_date: 수집 종료 날짜
        Returns:
            수집된 데이터 리스트
        """
        pass
    
    @abstractmethod
    def get_member_mapping(self) -> Dict[str, str]:
        """
        멤버 ID 매핑 정보 반환
        반환 형식: {source_user_id: email_or_name}
        """
        pass
    
    @abstractmethod
    def extract_member_activities(self, data: List[Dict]) -> List[Dict]:
        """
        멤버별 활동 추출
        Args:
            data: 수집된 원본 데이터
        Returns:
            표준화된 활동 데이터
            형식: {
                'member_identifier': str,
                'activity_type': str,
                'timestamp': datetime,
                'metadata': dict
            }
        """
        pass
    
    def validate_config(self) -> bool:
        """설정 검증"""
        required_keys = self.get_required_config_keys()
        return all(key in self.config for key in required_keys)
    
    @abstractmethod
    def get_required_config_keys(self) -> List[str]:
        """필수 설정 키 목록 반환"""
        pass
```

### 2. 멤버 인덱스 시스템

```python
# src/core/member_index.py
from sqlalchemy import create_engine, Table, Column, String, Integer, JSON, MetaData
from typing import Dict, Optional, List

class MemberIndex:
    """멤버 통합 인덱스 관리"""
    
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        self.metadata = MetaData()
        self._create_tables()
    
    def _create_tables(self):
        """멤버 및 활동 테이블 생성"""
        self.members_table = Table(
            'members', self.metadata,
            Column('id', Integer, primary_key=True),
            Column('name', String, nullable=False, unique=True),
            Column('email', String),
            Column('identifiers', JSON)  # {source: source_user_id}
        )
        
        self.activities_table = Table(
            'member_activities', self.metadata,
            Column('id', Integer, primary_key=True),
            Column('member_id', Integer),
            Column('source_type', String),
            Column('activity_type', String),
            Column('timestamp', String),
            Column('metadata', JSON)
        )
        
        self.metadata.create_all(self.engine)
    
    def register_member(self, name: str, email: Optional[str] = None, 
                       identifiers: Optional[Dict] = None) -> int:
        """멤버 등록 또는 업데이트"""
        pass
    
    def resolve_member_id(self, source: str, source_user_id: str) -> Optional[int]:
        """소스별 사용자 ID로 멤버 ID 조회"""
        pass
    
    def add_activity(self, member_id: int, source: str, 
                    activity_type: str, timestamp: str, metadata: Dict):
        """멤버 활동 기록"""
        pass
    
    def get_member_activities(self, member_name: str, 
                            source: Optional[str] = None,
                            start_date: Optional[str] = None,
                            end_date: Optional[str] = None) -> List[Dict]:
        """멤버의 활동 조회"""
        pass
```

### 3. 플러그인 로더

```python
# src/core/plugin_loader.py
import importlib
import pkgutil
from typing import List, Dict
from src.plugins.base import DataSourcePlugin

class PluginLoader:
    """플러그인 자동 발견 및 로드"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.plugins: List[DataSourcePlugin] = []
    
    def discover_plugins(self) -> List[str]:
        """플러그인 디렉토리에서 플러그인 자동 발견"""
        import src.plugins as plugins_package
        
        plugin_names = []
        for _, name, is_pkg in pkgutil.iter_modules(plugins_package.__path__):
            if name.endswith('_plugin') and not name.startswith('base'):
                plugin_names.append(name)
        
        return plugin_names
    
    def load_plugin(self, plugin_name: str) -> DataSourcePlugin:
        """플러그인 로드"""
        module = importlib.import_module(f'src.plugins.{plugin_name}')
        
        # 플러그인 클래스 찾기 (DataSourcePlugin 상속 클래스)
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and 
                issubclass(attr, DataSourcePlugin) and 
                attr is not DataSourcePlugin):
                
                plugin_config = self.config.get(plugin_name.replace('_plugin', ''), {})
                return attr(plugin_config)
        
        raise ValueError(f"No plugin class found in {plugin_name}")
    
    def load_all_plugins(self) -> List[DataSourcePlugin]:
        """모든 플러그인 로드"""
        plugin_names = self.discover_plugins()
        
        for name in plugin_names:
            try:
                plugin = self.load_plugin(name)
                if plugin.validate_config():
                    self.plugins.append(plugin)
                    print(f"✅ Loaded plugin: {plugin.get_source_name()}")
                else:
                    print(f"⚠️  Skipped plugin {name}: invalid config")
            except Exception as e:
                print(f"❌ Failed to load plugin {name}: {e}")
        
        return self.plugins
```

### 4. AI 프롬프트 포맷터

```python
# src/integrations/ai_formatter.py
from typing import Dict, Any
from datetime import datetime

class AIPromptFormatter:
    """멤버 데이터를 AI 프롬프트 형식으로 변환"""
    
    def format_member_performance(self, member_data: Dict[str, Any]) -> str:
        """
        멤버의 퍼포먼스 데이터를 AI 프롬프트로 포맷
        
        Args:
            member_data: {
                'member_name': str,
                'period': {'start': str, 'end': str},
                'slack': {...},
                'github': {...},
                'notion': {...},
                'google_drive': {...}
            }
        
        Returns:
            AI에 입력할 프롬프트 문자열
        """
        prompt = f"""
# 팀 멤버 퍼포먼스 분석 데이터

## 기본 정보
- 이름: {member_data['member_name']}
- 분석 기간: {member_data['period']['start']} ~ {member_data['period']['end']}

## Slack 커뮤니케이션 활동
{self._format_slack_data(member_data.get('slack', {}))}

## GitHub 코드 기여도
{self._format_github_data(member_data.get('github', {}))}

## Notion 문서화 기여도
{self._format_notion_data(member_data.get('notion', {}))}

## Google Drive 협업 활동
{self._format_drive_data(member_data.get('google_drive', {}))}

## 분석 요청
위 데이터를 바탕으로 다음을 분석해주세요:
1. 전반적인 업무 활동 수준 평가
2. 강점과 개선이 필요한 영역
3. 팀 내 협업 및 커뮤니케이션 패턴
4. 구체적인 개선 제안
"""
        return prompt.strip()
    
    def _format_slack_data(self, slack_data: Dict) -> str:
        if not slack_data:
            return "- 데이터 없음"
        
        return f"""
- 메시지 전송: {slack_data.get('message_count', 0)}개
- 참여 채널: {len(slack_data.get('channels', []))}개
- 받은 리액션: {slack_data.get('reactions_received', 0)}개
- 스레드 참여: {slack_data.get('thread_replies', 0)}개
- 활동 시간대: {slack_data.get('active_hours', 'N/A')}
"""
    
    def _format_github_data(self, github_data: Dict) -> str:
        if not github_data:
            return "- 데이터 없음"
        
        return f"""
- 커밋 수: {github_data.get('commit_count', 0)}개
- 코드 추가: +{github_data.get('additions', 0)} lines
- 코드 삭제: -{github_data.get('deletions', 0)} lines
- PR 생성: {github_data.get('prs_created', 0)}개
- PR 리뷰: {github_data.get('prs_reviewed', 0)}개
- 이슈 해결: {github_data.get('issues_closed', 0)}개
- 주요 작업 리포지토리: {', '.join(github_data.get('top_repos', []))}
"""
    
    def _format_notion_data(self, notion_data: Dict) -> str:
        if not notion_data:
            return "- 데이터 없음"
        
        return f"""
- 생성한 페이지: {notion_data.get('pages_created', 0)}개
- 수정한 페이지: {notion_data.get('pages_edited', 0)}개
- 총 작성 분량: 약 {notion_data.get('total_content_length', 0):,} 자
- 최근 활동일: {notion_data.get('last_activity', 'N/A')}
"""
    
    def _format_drive_data(self, drive_data: Dict) -> str:
        if not drive_data:
            return "- 데이터 없음"
        
        return f"""
- 생성한 파일: {drive_data.get('files_created', 0)}개
- 수정한 파일: {drive_data.get('files_modified', 0)}개
- 공유 활동: {drive_data.get('share_count', 0)}건
- 댓글 작성: {drive_data.get('comments', 0)}개
- 파일 유형: {', '.join(drive_data.get('file_types', []))}
"""
```

---

## 🚀 시작하기

### 1단계: 기본 프로젝트 구조 생성

```bash
# 디렉토리 생성
mkdir -p src/{core,plugins,models,integrations,api/routes,scheduler,utils}
mkdir -p tests/{unit,integration,fixtures}
mkdir -p scripts config data/databases docker

# __init__.py 파일 생성
touch src/__init__.py
touch src/core/__init__.py
touch src/plugins/__init__.py
touch src/models/__init__.py
touch src/integrations/__init__.py
touch src/api/__init__.py
touch src/api/routes/__init__.py
touch src/scheduler/__init__.py
touch src/utils/__init__.py
```

### 2단계: 의존성 설치

```bash
pip install -r requirements.txt
```

### 3단계: 설정 파일 구성

```bash
cp .env.example .env
# .env 파일 편집하여 API 키 등 설정
```

### 4단계: 데이터베이스 초기화

```bash
python scripts/setup.py
```

### 5단계: 첫 번째 플러그인 테스트

```bash
python -m src.cli collect --source slack --days 7
```

---

## 📊 성공 지표

1. **데이터 수집**: 모든 소스에서 데이터 수집 성공률 95% 이상
2. **쿼리 성능**: 멤버별 통합 쿼리 응답 시간 1초 이하
3. **확장성**: 새 플러그인 추가 시 30분 이내 통합 가능
4. **안정성**: 일일 데이터 수집 실패율 1% 미만

---

## 📚 참고 자료

- [Slack API Documentation](https://api.slack.com/)
- [GitHub REST API](https://docs.github.com/en/rest)
- [Notion API](https://developers.notion.com/)
- [Google Drive API](https://developers.google.com/drive)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)

