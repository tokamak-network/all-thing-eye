# All-Thing-Eye Web Interface - Quick Start 🚀

이 가이드는 웹 인터페이스를 빠르게 시작하는 방법을 설명합니다.

---

## 🔐 Web3 Authentication

**⚠️ 중요: 웹 인터페이스는 지갑 서명 기반 인증을 사용합니다!**

접속하려면:
1. **MetaMask 지갑** 설치 필요
2. **관리자 지갑 주소** 등록 필요
3. 로그인 시 **서명 요청** (가스비 없음)

**자세한 설정 방법**: [`docs/WEB3_AUTH_SETUP.md`](docs/WEB3_AUTH_SETUP.md)

---

## 🎯 두 가지 실행 방법

### **방법 1: 로컬 개발 (추천, 빠름)** ⚡

기존 SQLite 데이터를 사용하여 즉시 실행 가능합니다.

#### 1단계: Backend API 실행

```bash
cd /Users/son-yeongseong/Desktop/dev/all-thing-eye

# API 서버 실행 (기존 SQLite 데이터 사용)
python -m uvicorn backend.main:app --reload --port 8000
```

#### 2단계: 관리자 주소 설정

**Option 1: 환경 변수 (권장)**

```bash
cd /Users/son-yeongseong/Desktop/dev/all-thing-eye/frontend

# .env.local 파일 생성
cat > .env.local << 'EOF'
NEXT_PUBLIC_ADMIN_ADDRESSES=0x742d35cc6634c0532925a3b844bc9e7595f0beb,0x1234567890123456789012345678901234567890
NEXT_PUBLIC_API_URL=http://localhost:8000
EOF
```

**Option 2: 코드에 직접 설정**

`frontend/src/lib/auth.ts` 파일의 `HARDCODED_ADMINS` 배열에 주소 추가

#### 3단계: Frontend 실행 (새 터미널)

```bash
cd /Users/son-yeongseong/Desktop/dev/all-thing-eye/frontend

# Web3 의존성 설치 (최초 1회만)
npm install wagmi viem @tanstack/react-query

# 기타 의존성 설치
npm install

# Frontend 개발 서버 실행
npm run dev
```

#### 4단계: 접속 및 로그인

- **Frontend**: http://localhost:3000 → 자동으로 `/login` 페이지로 이동
- **API Docs**: http://localhost:8000/api/docs

**로그인 과정:**
1. MetaMask 설치 확인
2. "Connect MetaMask" 클릭
3. 지갑 연결 승인
4. "Sign Message to Authenticate" 클릭
5. 서명 승인 (가스비 없음)
6. 대시보드로 자동 이동

---

### **방법 2: Docker 실행 (프로덕션)** 🐳

모든 서비스를 Docker로 실행합니다.

#### 1단계: 환경 변수 설정

```bash
cd /Users/son-yeongseong/Desktop/dev/all-thing-eye

# .env 파일 생성
cat > .env << 'EOF'
# Database
POSTGRES_DB=allthingeye
POSTGRES_USER=allthingeye
POSTGRES_PASSWORD=changeme_to_secure_password

# Application
APP_ENV=production
SECRET_KEY=your_secret_key_at_least_32_characters_long_random

# API
API_WORKERS=4
CORS_ORIGINS=http://localhost:3000,http://localhost

# GitHub (기존 토큰 사용)
GITHUB_ENABLED=true
GITHUB_TOKEN=your_github_token
GITHUB_ORG=your_org

# Slack (기존 토큰 사용)
SLACK_ENABLED=true
SLACK_BOT_TOKEN=your_slack_token
SLACK_WORKSPACE=your_workspace

# Notion (선택)
NOTION_ENABLED=false
NOTION_TOKEN=your_notion_token

# Logging
LOG_LEVEL=INFO
EOF
```

#### 2단계: Docker 서비스 시작

```bash
# 모든 서비스 빌드 및 시작
docker-compose up -d --build

# 로그 확인
docker-compose logs -f
```

#### 3단계: 데이터 수집 (PostgreSQL은 비어있음)

```bash
# Backend 컨테이너에서 데이터 수집
docker-compose exec backend python tests/test_github_plugin.py --last-week
docker-compose exec backend python tests/test_slack_plugin.py --last-week
docker-compose exec backend python tests/test_google_drive_plugin.py --days 30
```

#### 4단계: 접속

- **Frontend**: http://localhost
- **API Docs**: http://localhost/api/docs
- **Health Check**: http://localhost/health

---

## 📊 화면 구성

### 1. Dashboard (/)
- 전체 통계 (멤버, 활동, 프로젝트, 데이터 소스)
- 소스별 활동 요약
- 빠른 액션 링크

### 2. Members (/members)
- 전체 멤버 목록
- 멤버별 상세 정보 조회
- CSV 내보내기

### 3. Activities (/activities)
- 활동 피드 (최근 50개)
- 소스별 필터링 (GitHub, Slack, Notion, Google Drive)
- CSV 내보내기

### 4. Projects (/projects)
- 프로젝트 카드 목록
- 프로젝트별 통계
- 프로젝트별 데이터 내보내기

---

## 🛠️ 문제 해결

### Backend API가 실행 안 됨

```bash
# 의존성 설치 확인
pip install -r requirements.txt

# 데이터베이스 파일 확인
ls -la data/databases/

# 포트 충돌 확인
lsof -i :8000
```

### Frontend가 실행 안 됨

```bash
cd frontend

# node_modules 삭제 후 재설치
rm -rf node_modules package-lock.json
npm install

# API URL 확인
echo $NEXT_PUBLIC_API_URL
```

### Docker가 실행 안 됨

```bash
# 서비스 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs backend
docker-compose logs frontend

# 재시작
docker-compose restart

# 완전 재빌드
docker-compose down
docker-compose up -d --build
```

### API 연결 오류

Frontend에서 "Failed to fetch data" 에러가 발생하면:

1. Backend가 실행 중인지 확인
2. CORS 설정 확인 (.env의 CORS_ORIGINS)
3. API URL 확인 (Frontend에서 올바른 URL 사용)

```bash
# Backend 헬스 체크
curl http://localhost:8000/health

# 멤버 API 테스트
curl http://localhost:8000/api/v1/members
```

---

## 🔧 개발 워크플로우

### 로컬 개발 시

```bash
# Terminal 1: Backend
python -m uvicorn backend.main:app --reload

# Terminal 2: Frontend  
cd frontend && npm run dev
```

**변경 사항이 자동으로 반영됩니다!**

### Docker 개발 시

```bash
# 코드 변경 후 재빌드
docker-compose up -d --build backend frontend

# 특정 서비스만 재시작
docker-compose restart backend
```

---

## 📚 추가 문서

- [API Development Guide](docs/API_DEVELOPMENT.md) - API 상세 가이드
- [Docker Quick Start](README_DOCKER.md) - Docker 사용법
- [Frontend README](frontend/README.md) - Frontend 개발 가이드
- [Architecture](docs/ARCHITECTURE.md) - 시스템 아키텍처

---

## 🎉 완료!

이제 웹 인터페이스를 통해:
- ✅ 멤버 목록 조회
- ✅ 활동 내역 확인
- ✅ 프로젝트별 통계 확인
- ✅ 데이터 CSV/JSON 내보내기

를 할 수 있습니다!

---

**Questions?** Check the logs or API documentation!

