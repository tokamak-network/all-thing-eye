# 🚀 Quick Start Guide

5분 안에 All-Thing-Eye를 시작해보세요!

## 📋 사전 준비

- Python 3.11 이상
- GitHub Personal Access Token (또는 다른 데이터 소스의 API 키)

## 🛠 설치

### 1. 프로젝트 클론

```bash
cd /Users/son-yeongseong/Desktop/dev/all-thing-eye
```

### 2. 가상환경 생성 및 활성화

```bash
python -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate  # Windows
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정

```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집
# 최소한 다음 항목들을 설정하세요:
```

`.env` 파일:
```env
GITHUB_ENABLED=true
GITHUB_TOKEN=ghp_your_github_personal_access_token
GITHUB_ORG=your-organization-name
```

### 5. 초기 설정 실행

```bash
python scripts/setup.py
```

## ✅ 테스트

### Test GitHub Plugin

```bash
python tests/test_github_plugin.py
```

성공하면 다음과 같은 출력을 볼 수 있습니다:

```
======================================================================
🧪 GitHub Plugin Test
======================================================================

1️⃣ Loading configuration...
   Environment: development
   Database: sqlite:///data/databases/main.db

2️⃣ Initializing database...
✅ Main database schema initialized

3️⃣ Initializing member index...

4️⃣ Loading plugins...
🔌 Loading plugins...
📦 Discovered 1 plugins: github_plugin
✅ Loaded plugin: github
✅ Created database for source: github

✅ Successfully loaded 1 plugins

5️⃣ Authenticating with GitHub...
✅ GitHub authentication successful (user: your-username)

6️⃣ Collecting GitHub data...
...
📊 Collection Results:
   Members: 4
   Repositories: 25
   Commits: 142
   Pull Requests: 38
   Issues: 12

✅ Test completed successfully!
```

## 📊 데이터 확인

### SQLite로 데이터 탐색

```bash
# GitHub 데이터베이스 열기
sqlite3 data/databases/github.db

# 커밋 수 확인
SELECT COUNT(*) FROM github_commits;

# 커밋이 많은 멤버 Top 5
SELECT author_login, COUNT(*) as commit_count 
FROM github_commits 
GROUP BY author_login 
ORDER BY commit_count DESC 
LIMIT 5;

# 종료
.quit
```

### 멤버 인덱스 확인

```bash
sqlite3 data/databases/main.db

# 등록된 멤버 목록
SELECT * FROM members;

# 멤버별 활동 수
SELECT m.name, COUNT(*) as activity_count
FROM members m
JOIN member_activities ma ON m.id = ma.member_id
GROUP BY m.name
ORDER BY activity_count DESC;

.quit
```

## 🎯 다음 단계

### 멤버 추가

`config/config.yaml` 파일을 편집하여 팀 멤버를 추가하세요:

```yaml
plugins:
  github:
    member_list:
      - name: "Your Name"
        githubId: "your-github-username"
        email: "you@company.com"
      - name: "Teammate"
        githubId: "teammate-username"
        email: "teammate@company.com"
```

### 수집 기간 변경

`test_github.py` 파일에서 날짜 범위를 수정:

```python
# 최근 30일 데이터 수집
end_date = datetime.now()
start_date = end_date - timedelta(days=30)  # 7 → 30으로 변경
```

### 다른 데이터 소스 추가

1. Slack 플러그인 활성화
2. Notion 플러그인 구현
3. 커스텀 플러그인 개발

자세한 내용은 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) 참조

## 🐛 문제 해결

### Import Error

```
ModuleNotFoundError: No module named 'yaml'
```

**해결**: 의존성 재설치
```bash
pip install -r requirements.txt
```

### Authentication Failed

```
❌ GitHub authentication failed
```

**해결**:
1. GitHub 토큰이 올바른지 확인
2. 토큰 권한 확인 (repo, read:org, read:user 필요)
3. `.env` 파일이 올바른 위치에 있는지 확인

### No Data Collected

```
📊 Collection Results:
   Commits: 0
```

**해결**:
1. 조직 이름(`GITHUB_ORG`) 확인
2. 날짜 범위 내에 활동이 있는지 확인
3. `member_list`의 GitHub 사용자명이 정확한지 확인

## 📚 더 알아보기

- [GitHub 플러그인 상세 가이드](GITHUB_SETUP.md)
- [아키텍처 문서](ARCHITECTURE.md)
- [구현 계획](IMPLEMENTATION_PLAN.md)

## 💬 도움이 필요하신가요?

Issues에 문의해주세요!

