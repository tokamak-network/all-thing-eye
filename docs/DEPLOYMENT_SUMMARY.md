# AWS 배포 준비 완료 ✅

All-Thing-Eye의 AWS 배포 준비가 완료되었습니다.

---

## 📦 준비된 파일들

### 1. 데이터 수집 스크립트 (MongoDB 버전)

#### `scripts/initial_data_collection_mongo.py`
- **목적**: 최초 배포 시 2주간의 과거 데이터 수집
- **기능**:
  - GitHub, Slack, Notion, Google Drive 데이터 수집
  - 자동으로 MongoDB에 저장
  - 수집 완료 후 통계 출력

**사용법:**
```bash
# 기본 (2주)
python scripts/initial_data_collection_mongo.py

# 커스텀 기간
python scripts/initial_data_collection_mongo.py --days 30

# 특정 소스만
python scripts/initial_data_collection_mongo.py --sources github slack
```

---

#### `scripts/daily_data_collection_mongo.py`
- **목적**: 매일 자정 KST에 전일 데이터 수집
- **기능**:
  - 타임존 인식 (KST 기준)
  - 전날 00:00:00 ~ 23:59:59 데이터 수집
  - 멤버 인덱스 자동 업데이트

**실행 예시:**
- 금요일 00:00:00 KST 실행 → 목요일 데이터 수집
- 자동으로 UTC로 변환하여 API 호출

**사용법:**
```bash
# 자동 (어제 데이터)
python scripts/daily_data_collection_mongo.py

# 특정 날짜
python scripts/daily_data_collection_mongo.py --date 2025-11-17

# 특정 소스만
python scripts/daily_data_collection_mongo.py --sources github slack
```

---

### 2. Docker 설정 파일

#### `Dockerfile.backend` (수정됨)
- MongoDB 버전 백엔드 실행 (`backend.main:app`)
- Python 3.12 slim 이미지 사용
- 헬스체크 포함

#### `docker-compose.prod.yml` (대폭 수정)
- **MongoDB 서비스 추가**: 로컬 개발/테스트용
- **Data Collector 서비스**:
  - 최초 실행 시 2주 데이터 수집
  - 멤버 인덱스 자동 생성
  - 매일 자정 KST에 전일 데이터 수집
  - 타임존: Asia/Seoul
- **백엔드, 프론트엔드, Nginx** 포함
- **자동 헬스체크** 및 재시작 정책

---

### 3. 환경변수 템플릿

#### `env.production.template`
- 프로덕션 배포에 필요한 모든 환경변수 템플릿
- MongoDB 연결 (Atlas, DocumentDB, Local 옵션)
- API 토큰 (GitHub, Slack, Notion, Google Drive)
- Web3 인증 (Admin Addresses)

**사용법:**
```bash
cp env.production.template .env
nano .env  # 실제 값으로 수정
```

---

### 4. 배포 스크립트

#### `scripts/deploy.sh` (MongoDB 버전으로 업데이트)
- **명령어:**
  - `init`: 초기 배포 (Docker 빌드, 컨테이너 시작)
  - `update`: 코드 업데이트 및 재배포
  - `restart`: 서비스 재시작
  - `logs [service]`: 로그 확인
  - `status`: 서비스 상태 확인
  - `stop`: 서비스 중지
  - `backup`: MongoDB 백업

**사용법:**
```bash
# 실행 권한 부여
chmod +x scripts/deploy.sh

# 초기 배포
./scripts/deploy.sh init

# 로그 확인
./scripts/deploy.sh logs data-collector
```

---

### 5. 배포 가이드 문서

#### `docs/AWS_DEPLOYMENT_GUIDE.md`
- **170+ 줄**의 상세한 배포 가이드
- 아키텍처 다이어그램 포함
- Step-by-step 배포 절차
- MongoDB Atlas / DocumentDB 설정 가이드
- EC2 인스턴스 설정
- 도메인 & SSL 설정
- 모니터링 & 트러블슈팅
- 비용 예상

#### `DEPLOYMENT_QUICKSTART.md`
- **5단계로 완료**하는 빠른 배포 가이드
- SSH, Docker 설치, 환경 설정, 배포, 검증
- 일반 관리 명령어 정리
- 트러블슈팅 FAQ
- 선택적 도메인/SSL 설정

---

## 🚀 배포 실행 순서

### Phase 1: MongoDB 설정
1. MongoDB Atlas 계정 생성
2. 클러스터 생성 (M10 이상 권장)
3. 네트워크 접근 허용 (EC2 IP)
4. 데이터베이스 사용자 생성
5. 연결 문자열 복사

---

### Phase 2: EC2 인스턴스 준비
1. EC2 인스턴스 생성 (Ubuntu 22.04, t3.medium+)
2. SSH 접속
3. Docker & Docker Compose 설치
4. 레포지토리 클론

```bash
ssh -i your-key.pem ubuntu@your-ec2-ip
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
git clone https://github.com/your-org/all-thing-eye.git
cd all-thing-eye
```

---

### Phase 3: 환경 설정
1. 환경변수 파일 생성

```bash
cp env.production.template .env
nano .env
```

2. 필수 항목 입력:
   - `MONGODB_URI` (MongoDB Atlas 연결 문자열)
   - `GITHUB_TOKEN`, `SLACK_BOT_TOKEN`, etc.
   - `ADMIN_ADDRESSES`
   - `NEXT_PUBLIC_API_URL`

3. Google credentials 업로드

```bash
# 로컬 머신에서
scp -i your-key.pem config/google_drive/credentials.json ubuntu@your-ec2-ip:~/all-thing-eye/config/google_drive/
```

---

### Phase 4: 배포 실행

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh init
```

**자동으로 실행되는 작업:**
1. ✅ Docker 이미지 빌드
2. ✅ 모든 서비스 시작 (MongoDB, Backend, Frontend, Nginx, Data-Collector)
3. ✅ 2주간 데이터 수집 (자동)
4. ✅ 멤버 인덱스 생성 (자동)
5. ✅ 매일 자정 KST 크론잡 설정 (자동)

---

### Phase 5: 검증

```bash
# 서비스 상태 확인
./scripts/deploy.sh status

# 데이터 수집 모니터링
./scripts/deploy.sh logs data-collector

# 백엔드 로그
./scripts/deploy.sh logs backend

# 웹 인터페이스 접속
curl ifconfig.me  # EC2 퍼블릭 IP 확인
# 브라우저에서: http://YOUR_EC2_IP
```

---

## 📅 데이터 수집 일정

### 초기 수집 (배포 직후)
- **시점**: `data-collector` 서비스 시작 60초 후
- **기간**: 최근 2주
- **소스**: GitHub, Slack, Notion, Google Drive
- **소요시간**: 약 30~60분 (데이터량에 따라)

### 일일 수집 (매일 자동)
- **시간**: 매일 00:00:00 KST (한국 표준시)
- **대상**: 전일 데이터
  - 예: 금요일 00:00 실행 → 목요일 00:00~23:59 데이터 수집
- **자동 실행**: Docker 컨테이너가 실행 중이면 자동
- **로그**: `./scripts/deploy.sh logs data-collector`

---

## 🔧 일상 관리

### 로그 확인
```bash
# 전체 로그
./scripts/deploy.sh logs

# 특정 서비스
./scripts/deploy.sh logs backend
./scripts/deploy.sh logs data-collector
./scripts/deploy.sh logs frontend

# 실시간 팔로우
./scripts/deploy.sh logs -f
```

### 서비스 재시작
```bash
./scripts/deploy.sh restart
```

### 코드 업데이트
```bash
./scripts/deploy.sh update
```

### 백업
```bash
./scripts/deploy.sh backup
```

### 서비스 중지
```bash
./scripts/deploy.sh stop
```

---

## 🐛 트러블슈팅

### 데이터가 수집되지 않는 경우

```bash
# 1. 데이터 콜렉터 로그 확인
./scripts/deploy.sh logs data-collector

# 2. 환경변수 확인
docker exec -it all-thing-eye-data-collector env | grep TOKEN

# 3. MongoDB 연결 확인
docker exec -it all-thing-eye-backend python -c "
from src.core.mongo_manager import get_mongo_manager
m = get_mongo_manager()
m.connect_async()
print('OK')
"
```

### 백엔드 500 에러

```bash
# 백엔드 로그 확인
./scripts/deploy.sh logs backend

# MongoDB 연결 테스트
docker exec -it all-thing-eye-mongodb mongosh --eval "db.adminCommand('ping')"
```

### 프론트엔드 접속 안 됨

```bash
# .env 파일 확인
cat .env | grep NEXT_PUBLIC_API_URL

# 프론트엔드 재시작
docker-compose -f docker-compose.prod.yml restart frontend
```

---

## 📊 프로덕션 체크리스트

배포 전 확인 사항:

- [ ] MongoDB Atlas 클러스터 생성 완료
- [ ] 모든 API 토큰 발급 및 .env에 입력
- [ ] Google credentials.json 업로드
- [ ] Admin wallet addresses 설정
- [ ] EC2 보안 그룹 설정 (포트 22, 80, 443만 허용)
- [ ] Docker & Docker Compose 설치
- [ ] `deploy.sh` 스크립트 실행 권한 부여
- [ ] 초기 배포 실행 (`./scripts/deploy.sh init`)
- [ ] 데이터 수집 모니터링 (30~60분)
- [ ] 웹 인터페이스 접속 테스트
- [ ] 멤버 페이지에서 통합 데이터 확인
- [ ] Database 뷰어에서 스키마 확인
- [ ] 다음날 자정 크론잡 실행 확인

선택 사항:
- [ ] 도메인 연결
- [ ] SSL 인증서 설치
- [ ] CloudWatch 모니터링 설정
- [ ] 백업 자동화 설정

---

## 💡 추천 사항

1. **MongoDB Atlas 사용** (프로덕션)
   - 자동 백업
   - 확장성
   - 보안 관리 용이

2. **EC2 인스턴스 사이즈**
   - 최소: t3.medium (2 vCPU, 4GB RAM)
   - 권장: t3.large (2 vCPU, 8GB RAM)

3. **모니터링**
   - 첫 24시간은 로그를 주기적으로 확인
   - 데이터 수집이 제대로 되는지 확인
   - Database 페이지에서 "Last Data Collection" 시간 확인

4. **보안**
   - .env 파일은 절대 커밋하지 않기
   - Admin addresses만 웹 인터페이스 접근 가능
   - EC2 보안 그룹에서 불필요한 포트 차단

5. **백업**
   - MongoDB Atlas의 자동 백업 활성화
   - 또는 `./scripts/deploy.sh backup` 정기적 실행

---

## 📚 참고 문서

- **상세 배포 가이드**: `docs/AWS_DEPLOYMENT_GUIDE.md`
- **빠른 배포 가이드**: `DEPLOYMENT_QUICKSTART.md`
- **프로젝트 구조**: `docs/PROJECT_STRUCTURE.md`
- **MongoDB 스키마**: `docs/MONGODB_COMPLETE_SCHEMA.md`
- **API 문서**: `docs/API_DEVELOPMENT.md`

---

## ⏱️ 예상 소요 시간

- **배포 준비**: 10분 (환경변수 설정, credentials 업로드)
- **Docker 빌드 & 시작**: 5분
- **초기 데이터 수집**: 30~60분 (자동)
- **검증 & 테스트**: 10분

**총 소요 시간**: 약 1~1.5시간

---

## 🎯 배포 후 확인 사항

1. **웹 인터페이스 접속**: `http://YOUR_EC2_IP`
2. **데이터베이스 페이지**에서 컬렉션 확인
3. **Members 페이지**에서 통합 멤버 확인
4. **마지막 수집 시간** 표시 확인
5. **Exports 페이지**에서 CSV/JSON/TOON 다운로드 테스트

---

## 📞 지원

문제 발생 시:
1. `./scripts/deploy.sh logs` 로그 확인
2. `DEPLOYMENT_QUICKSTART.md` 트러블슈팅 섹션 참고
3. `docs/AWS_DEPLOYMENT_GUIDE.md` 상세 가이드 참고

---

**마지막 업데이트:** 2025-11-18  
**버전:** 1.0.0  
**유지보수:** All-Thing-Eye Development Team

---

## ✅ 준비 완료!

모든 파일이 준비되었습니다. 이제 다음 단계는:

1. 커밋 후 푸시
2. EC2 인스턴스 준비
3. `DEPLOYMENT_QUICKSTART.md` 따라 배포 실행

**Good luck! 🚀**

