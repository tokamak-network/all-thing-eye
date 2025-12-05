# 🐳 Docker 서비스 재빌드 스크립트

## 📋 개요

AWS에서 All-Thing-Eye 프로젝트의 Docker 서비스를 쉽게 재빌드하고 재시작할 수 있는 스크립트입니다.

## 🚀 빠른 시작

### 가장 간단한 방법 (권장)

```bash
# 프론트엔드와 백엔드 모두 재빌드
./scripts/quick-rebuild.sh
```

또는 직접 docker-compose 명령어 사용:

```bash
# 프론트엔드와 백엔드 함께 재빌드
docker-compose -f docker-compose.prod.yml up -d --build frontend backend
```

## 📖 상세 사용법

### 1. `rebuild-services.sh` - 고급 옵션 지원

```bash
# 기본 사용 (frontend + backend 재빌드)
./scripts/rebuild-services.sh

# 프론트엔드만 재빌드
./scripts/rebuild-services.sh --frontend

# 백엔드만 재빌드
./scripts/rebuild-services.sh --backend

# 캐시 없이 완전히 새로 빌드
./scripts/rebuild-services.sh --no-cache

# 기존 컨테이너 중지 후 재빌드
./scripts/rebuild-services.sh --down

# 여러 옵션 조합
./scripts/rebuild-services.sh --frontend --backend --no-cache
```

### 2. `quick-rebuild.sh` - 빠른 재빌드

```bash
# 프론트엔드와 백엔드 모두 재빌드 (가장 간단)
./scripts/quick-rebuild.sh
```

## 🎯 옵션 설명

### rebuild-services.sh 옵션

| 옵션 | 단축 | 설명 |
|------|------|------|
| `--frontend` | `-f` | 프론트엔드만 재빌드 |
| `--backend` | `-b` | 백엔드만 재빌드 |
| `--all` | `-a` | 모든 서비스 재빌드 (기본값) |
| `--no-cache` | `-n` | 캐시 없이 빌드 (느리지만 깨끗함) |
| `--down` | `-d` | 기존 컨테이너 중지 후 재빌드 |
| `--help` | `-h` | 도움말 표시 |

## 📝 사용 예시

### 시나리오 1: 프론트엔드 코드 수정 후 배포

```bash
# 코드 커밋
git add .
git commit -m "feat: update dashboard"
git push

# AWS 서버에서 프론트엔드만 재빌드
./scripts/rebuild-services.sh --frontend
```

### 시나리오 2: 백엔드 API 수정 후 배포

```bash
# 코드 커밋
git add .
git commit -m "fix: update API endpoint"
git push

# AWS 서버에서 백엔드만 재빌드
./scripts/rebuild-services.sh --backend
```

### 시나리오 3: 전체 스택 업데이트

```bash
# 코드 커밋
git add .
git commit -m "feat: major update"
git push

# AWS 서버에서 전체 재빌드
./scripts/quick-rebuild.sh
# 또는
./scripts/rebuild-services.sh
```

### 시나리오 4: 문제 발생 시 완전 재빌드

```bash
# 캐시 없이 완전히 새로 빌드
./scripts/rebuild-services.sh --down --no-cache
```

## 🔧 직접 Docker Compose 명령어 사용

스크립트를 사용하지 않고 직접 명령어를 실행하고 싶다면:

```bash
# 프론트엔드와 백엔드 함께 재빌드
docker-compose -f docker-compose.prod.yml up -d --build frontend backend

# 프론트엔드만
docker-compose -f docker-compose.prod.yml up -d --build frontend

# 백엔드만
docker-compose -f docker-compose.prod.yml up -d --build backend

# 모든 서비스
docker-compose -f docker-compose.prod.yml up -d --build

# 캐시 없이 빌드
docker-compose -f docker-compose.prod.yml build --no-cache frontend backend
docker-compose -f docker-compose.prod.yml up -d frontend backend

# 컨테이너 중지 후 재시작
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d --build frontend backend
```

## 📊 로그 확인

재빌드 후 로그를 확인하려면:

```bash
# 모든 서비스 로그
docker-compose -f docker-compose.prod.yml logs -f

# 프론트엔드 로그만
docker-compose -f docker-compose.prod.yml logs -f frontend

# 백엔드 로그만
docker-compose -f docker-compose.prod.yml logs -f backend

# 최근 100줄만 보기
docker-compose -f docker-compose.prod.yml logs --tail=100 frontend backend
```

## 🔍 상태 확인

```bash
# 실행 중인 컨테이너 확인
docker-compose -f docker-compose.prod.yml ps

# 상세 정보
docker-compose -f docker-compose.prod.yml ps -a
```

## ⚠️ 주의사항

1. **캐시 사용**: 기본적으로 Docker 빌드 캐시를 사용하여 빠르게 빌드합니다. 문제가 있다면 `--no-cache` 옵션을 사용하세요.

2. **다운타임**: 재빌드 중에는 서비스가 잠시 중단됩니다. 트래픽이 적은 시간에 수행하는 것이 좋습니다.

3. **디스크 공간**: 오래된 이미지가 쌓일 수 있습니다. 주기적으로 정리하세요:
   ```bash
   docker system prune -a
   ```

4. **권한**: 스크립트 실행 권한이 필요합니다:
   ```bash
   chmod +x scripts/*.sh
   ```

## 🎨 출력 예시

스크립트 실행 시 다음과 같은 색상 출력을 볼 수 있습니다:

```
ℹ️  Starting rebuild process...
ℹ️  Services to rebuild: frontend backend
ℹ️  Building services...
✅ Build completed successfully
ℹ️  Starting services...
✅ Services started successfully
ℹ️  Running containers:
NAME                    STATUS              PORTS
frontend                Up 2 seconds        0.0.0.0:3000->3000/tcp
backend                 Up 2 seconds        0.0.0.0:8000->8000/tcp
✅ Rebuild complete! 🎉
```

## 🆘 문제 해결

### 빌드 실패 시

```bash
# 캐시 없이 재시도
./scripts/rebuild-services.sh --no-cache

# 컨테이너 완전 제거 후 재시도
docker-compose -f docker-compose.prod.yml down -v
./scripts/rebuild-services.sh
```

### 포트 충돌 시

```bash
# 실행 중인 컨테이너 확인
docker ps

# 특정 컨테이너 중지
docker stop <container_id>
```

### 디스크 공간 부족 시

```bash
# 사용하지 않는 이미지/컨테이너 정리
docker system prune -a

# 볼륨까지 정리 (주의: 데이터 손실 가능)
docker system prune -a --volumes
```

## 📚 추가 리소스

- [Docker Compose 문서](https://docs.docker.com/compose/)
- [프로젝트 배포 가이드](../DEPLOYMENT_QUICKSTART.md)
- [Docker 문서](../README_DOCKER.md)

## 💡 팁

1. **Alias 설정**: 자주 사용하는 명령어는 alias로 등록하세요
   ```bash
   # ~/.bashrc 또는 ~/.zshrc에 추가
   alias rebuild-fe='./scripts/rebuild-services.sh --frontend'
   alias rebuild-be='./scripts/rebuild-services.sh --backend'
   alias rebuild-all='./scripts/quick-rebuild.sh'
   ```

2. **Git Hook**: 자동 배포를 위해 Git hook을 설정할 수 있습니다

3. **모니터링**: 재빌드 후 항상 로그를 확인하여 정상 작동하는지 확인하세요

---

**작성일**: 2025-12-05  
**버전**: 1.0.0
