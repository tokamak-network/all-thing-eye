# MongoDB Prototype Evaluation Guide

**실제로 사용해보고 평가하기**

이 가이드는 MongoDB 프로토타입을 직접 테스트하고 PostgreSQL과 비교 평가하는 방법을 제공합니다.

---

## 📋 목차

1. [MongoDB 데이터 탐색](#1-mongodb-데이터-탐색)
2. [실제 쿼리 실행해보기](#2-실제-쿼리-실행해보기)
3. [성능 비교 테스트](#3-성능-비교-테스트)
4. [개발자 경험 평가](#4-개발자-경험-평가)
5. [평가 체크리스트](#5-평가-체크리스트)

---

## 1. MongoDB 데이터 탐색

### 1.1 MongoDB Shell 접속

```bash
# MongoDB Shell 실행
mongosh all_thing_eye_test

# 또는 직접 URI로 접속
mongosh "mongodb://localhost:27017/all_thing_eye_test"
```

### 1.2 기본 데이터 확인

```javascript
// 컬렉션 목록 확인
show collections

// 예상 출력:
// github_commits
// github_issues
// github_pull_requests
// github_repositories

// 각 컬렉션의 문서 수 확인
db.github_commits.countDocuments()
db.github_pull_requests.countDocuments()
db.github_issues.countDocuments()
db.github_repositories.countDocuments()

// 샘플 문서 보기 (예쁘게 포맷)
db.github_commits.findOne()
db.github_pull_requests.findOne()
```

### 1.3 데이터 구조 이해하기

```javascript
// 커밋 문서의 구조 확인
db.github_commits.findOne({}, {
  sha: 1,
  message: 1,
  author_login: 1,
  repository_name: 1,
  committed_at: 1,
  additions: 1,
  deletions: 1,
  "files.filename": 1,
  "files.additions": 1
})

// PR 문서의 구조 확인
db.github_pull_requests.findOne({}, {
  number: 1,
  repository_name: 1,
  title: 1,
  state: 1,
  author_login: 1,
  merged_at: 1
})
```

---

## 2. 실제 쿼리 실행해보기

### 2.1 간단한 조회 쿼리

#### A. 특정 사용자의 커밋 조회

**MongoDB:**
```javascript
// jake-jang의 최근 커밋 10개
db.github_commits.find(
  { author_login: "jake-jang" }
).sort({ committed_at: -1 }).limit(10)

// 필드만 선택해서 보기
db.github_commits.find(
  { author_login: "jake-jang" },
  { message: 1, repository_name: 1, committed_at: 1, additions: 1, deletions: 1 }
).sort({ committed_at: -1 }).limit(10)

// 결과를 예쁘게 출력
db.github_commits.find(
  { author_login: "jake-jang" }
).sort({ committed_at: -1 }).limit(10).forEach(doc => {
  print(`${doc.committed_at.toISOString().split('T')[0]} | ${doc.repository_name} | ${doc.message.substring(0, 50)}...`)
})
```

**SQL (비교용):**
```sql
SELECT 
  date(committed_at) as date,
  repository_name,
  message,
  additions,
  deletions
FROM github_commits
WHERE author_login = 'jake-jang'
ORDER BY committed_at DESC
LIMIT 10;
```

#### B. 특정 저장소의 PR 조회

**MongoDB:**
```javascript
// Tokamak-zk-EVM의 모든 PR
db.github_pull_requests.find(
  { repository_name: "Tokamak-zk-EVM" }
).sort({ created_at: -1 })

// MERGED 상태만
db.github_pull_requests.find(
  { 
    repository_name: "Tokamak-zk-EVM",
    state: "MERGED"
  }
).sort({ merged_at: -1 })

// 예쁘게 출력
db.github_pull_requests.find(
  { repository_name: "Tokamak-zk-EVM" }
).sort({ created_at: -1 }).forEach(pr => {
  print(`#${pr.number} | ${pr.state} | ${pr.title}`)
  print(`  Author: ${pr.author_login} | Created: ${pr.created_at.toISOString().split('T')[0]}`)
  if (pr.merged_at) print(`  Merged: ${pr.merged_at.toISOString().split('T')[0]}`)
  print('---')
})
```

### 2.2 집계 쿼리 (Aggregation)

#### A. 저장소별 커밋 수

**MongoDB:**
```javascript
db.github_commits.aggregate([
  {
    $group: {
      _id: "$repository_name",
      count: { $sum: 1 },
      total_additions: { $sum: "$additions" },
      total_deletions: { $sum: "$deletions" }
    }
  },
  { $sort: { count: -1 } },
  { $limit: 10 }
])
```

**SQL (비교용):**
```sql
SELECT 
  repository_name,
  COUNT(*) as count,
  SUM(additions) as total_additions,
  SUM(deletions) as total_deletions
FROM github_commits
GROUP BY repository_name
ORDER BY count DESC
LIMIT 10;
```

#### B. 사용자별 활동 통계

**MongoDB:**
```javascript
db.github_commits.aggregate([
  {
    $group: {
      _id: "$author_login",
      commit_count: { $sum: 1 },
      total_additions: { $sum: "$additions" },
      total_deletions: { $sum: "$deletions" },
      repos: { $addToSet: "$repository_name" }
    }
  },
  {
    $project: {
      author: "$_id",
      commit_count: 1,
      total_additions: 1,
      total_deletions: 1,
      repos_count: { $size: "$repos" }
    }
  },
  { $sort: { commit_count: -1 } }
])
```

**SQL (비교용):**
```sql
SELECT 
  author_login,
  COUNT(*) as commit_count,
  SUM(additions) as total_additions,
  SUM(deletions) as total_deletions,
  COUNT(DISTINCT repository_name) as repos_count
FROM github_commits
GROUP BY author_login
ORDER BY commit_count DESC;
```

#### C. 일별 활동 추이

**MongoDB:**
```javascript
db.github_commits.aggregate([
  {
    $group: {
      _id: {
        $dateToString: { format: "%Y-%m-%d", date: "$committed_at" }
      },
      commit_count: { $sum: 1 },
      unique_authors: { $addToSet: "$author_login" }
    }
  },
  {
    $project: {
      date: "$_id",
      commit_count: 1,
      author_count: { $size: "$unique_authors" }
    }
  },
  { $sort: { date: -1 } }
])
```

### 2.3 복잡한 쿼리

#### A. 파일 변경 내역 검색 (Embedded Documents)

**MongoDB의 장점: 중첩 문서 쿼리가 간단**
```javascript
// Rust 파일을 수정한 커밋 찾기
db.github_commits.find({
  "files.filename": { $regex: /\.rs$/ }
}, {
  sha: 1,
  message: 1,
  author_login: 1,
  "files.filename": 1,
  "files.additions": 1,
  "files.deletions": 1
})

// 특정 파일을 수정한 커밋 찾기
db.github_commits.find({
  "files.filename": "src/verifier.rs"
}, {
  sha: 1,
  message: 1,
  author_login: 1,
  committed_at: 1
}).sort({ committed_at: -1 })
```

**SQL (비교용 - 복잡):**
```sql
-- SQL에서는 별도 테이블 JOIN 필요
SELECT 
  c.sha,
  c.message,
  c.author_login,
  c.committed_at,
  f.filename,
  f.additions,
  f.deletions
FROM github_commits c
JOIN github_commit_files f ON c.sha = f.commit_sha
WHERE f.filename LIKE '%.rs'
ORDER BY c.committed_at DESC;
```

#### B. 텍스트 검색

**MongoDB:**
```javascript
// 먼저 텍스트 인덱스 생성 (한 번만)
db.github_commits.createIndex({ message: "text" })

// 커밋 메시지에서 "bug" 또는 "fix" 검색
db.github_commits.find(
  { $text: { $search: "bug fix" } }
).sort({ committed_at: -1 })

// PR 제목에서 검색
db.github_pull_requests.createIndex({ title: "text", body: "text" })
db.github_pull_requests.find(
  { $text: { $search: "verifier" } }
)
```

---

## 3. 성능 비교 테스트

### 3.1 Python 스크립트로 벤치마크

파일 생성: `scripts/benchmark_mongo_vs_sql.py`

```python
#!/usr/bin/env python3
"""
MongoDB vs SQL 성능 비교 벤치마크
"""

import time
import sqlite3
from pymongo import MongoClient
from datetime import datetime, timedelta

# 설정
MONGODB_URI = "mongodb://localhost:27017"
MONGODB_DB = "all_thing_eye_test"
SQLITE_DB = "data/databases/github.db"

def benchmark_query(name, func):
    """쿼리 실행 시간 측정"""
    start = time.time()
    result = func()
    end = time.time()
    elapsed = (end - start) * 1000  # ms
    print(f"{name:40s} | {elapsed:7.2f} ms | {len(result):5d} results")
    return elapsed, result

def run_mongodb_benchmarks():
    """MongoDB 벤치마크"""
    print("\n" + "="*80)
    print("MongoDB Benchmarks")
    print("="*80)
    
    client = MongoClient(MONGODB_URI)
    db = client[MONGODB_DB]
    
    times = {}
    
    # 1. 단순 조회
    times['simple_find'] = benchmark_query(
        "1. Find commits by author",
        lambda: list(db.github_commits.find({"author_login": "jake-jang"}).limit(100))
    )[0]
    
    # 2. 정렬 + 제한
    times['sort_limit'] = benchmark_query(
        "2. Sort + Limit (recent 50 commits)",
        lambda: list(db.github_commits.find().sort("committed_at", -1).limit(50))
    )[0]
    
    # 3. 집계 (저장소별 카운트)
    times['aggregate_count'] = benchmark_query(
        "3. Aggregate: Count by repository",
        lambda: list(db.github_commits.aggregate([
            {"$group": {"_id": "$repository_name", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]))
    )[0]
    
    # 4. 복잡한 집계 (사용자별 통계)
    times['aggregate_stats'] = benchmark_query(
        "4. Aggregate: User statistics",
        lambda: list(db.github_commits.aggregate([
            {"$group": {
                "_id": "$author_login",
                "commits": {"$sum": 1},
                "additions": {"$sum": "$additions"},
                "deletions": {"$sum": "$deletions"}
            }},
            {"$sort": {"commits": -1}}
        ]))
    )[0]
    
    # 5. 임베디드 문서 쿼리
    times['embedded_query'] = benchmark_query(
        "5. Embedded: Find commits with .rs files",
        lambda: list(db.github_commits.find(
            {"files.filename": {"$regex": r"\.rs$"}},
            {"sha": 1, "message": 1, "files.filename": 1}
        ).limit(50))
    )[0]
    
    client.close()
    return times

def run_sql_benchmarks():
    """SQL 벤치마크"""
    print("\n" + "="*80)
    print("SQL (SQLite) Benchmarks")
    print("="*80)
    
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    
    times = {}
    
    # 1. 단순 조회
    times['simple_find'] = benchmark_query(
        "1. Find commits by author",
        lambda: cursor.execute(
            "SELECT * FROM github_commits WHERE author_login = ? LIMIT 100",
            ("jake-jang",)
        ).fetchall()
    )[0]
    
    # 2. 정렬 + 제한
    times['sort_limit'] = benchmark_query(
        "2. Sort + Limit (recent 50 commits)",
        lambda: cursor.execute(
            "SELECT * FROM github_commits ORDER BY committed_at DESC LIMIT 50"
        ).fetchall()
    )[0]
    
    # 3. 집계 (저장소별 카운트)
    times['aggregate_count'] = benchmark_query(
        "3. Aggregate: Count by repository",
        lambda: cursor.execute(
            "SELECT repository_name, COUNT(*) as count "
            "FROM github_commits GROUP BY repository_name ORDER BY count DESC"
        ).fetchall()
    )[0]
    
    # 4. 복잡한 집계 (사용자별 통계)
    times['aggregate_stats'] = benchmark_query(
        "4. Aggregate: User statistics",
        lambda: cursor.execute(
            "SELECT author_login, COUNT(*) as commits, "
            "SUM(additions) as additions, SUM(deletions) as deletions "
            "FROM github_commits GROUP BY author_login ORDER BY commits DESC"
        ).fetchall()
    )[0]
    
    # 5. JOIN 쿼리 (파일 정보)
    # Note: SQL은 별도 테이블이므로 JOIN 필요
    times['embedded_query'] = benchmark_query(
        "5. JOIN: Find commits with .rs files (if separate table)",
        lambda: cursor.execute(
            "SELECT DISTINCT c.sha, c.message "
            "FROM github_commits c "
            "WHERE c.sha IN ("
            "  SELECT DISTINCT commit_sha FROM github_commit_files "
            "  WHERE filename LIKE '%.rs' LIMIT 50"
            ")"
        ).fetchall()
    )[0]
    
    conn.close()
    return times

def compare_results(mongo_times, sql_times):
    """결과 비교"""
    print("\n" + "="*80)
    print("Performance Comparison")
    print("="*80)
    print(f"{'Query Type':40s} | {'MongoDB':>10s} | {'SQL':>10s} | {'Winner':>10s}")
    print("-"*80)
    
    total_mongo = 0
    total_sql = 0
    mongo_wins = 0
    sql_wins = 0
    
    for key in mongo_times.keys():
        mongo_time = mongo_times[key]
        sql_time = sql_times[key]
        winner = "MongoDB" if mongo_time < sql_time else "SQL"
        speedup = sql_time / mongo_time if mongo_time < sql_time else mongo_time / sql_time
        
        if mongo_time < sql_time:
            mongo_wins += 1
        else:
            sql_wins += 1
        
        total_mongo += mongo_time
        total_sql += sql_time
        
        print(f"{key:40s} | {mongo_time:8.2f} ms | {sql_time:8.2f} ms | {winner} ({speedup:.2f}x)")
    
    print("-"*80)
    print(f"{'TOTAL':40s} | {total_mongo:8.2f} ms | {total_sql:8.2f} ms")
    print(f"\nWins: MongoDB {mongo_wins}, SQL {sql_wins}")
    
    if total_mongo < total_sql:
        speedup = total_sql / total_mongo
        print(f"\n🏆 MongoDB is {speedup:.2f}x faster overall")
    else:
        speedup = total_mongo / total_sql
        print(f"\n🏆 SQL is {speedup:.2f}x faster overall")

if __name__ == "__main__":
    print("\n🚀 Starting MongoDB vs SQL Performance Benchmark")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        mongo_times = run_mongodb_benchmarks()
        sql_times = run_sql_benchmarks()
        compare_results(mongo_times, sql_times)
        
        print("\n✅ Benchmark completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
```

### 3.2 벤치마크 실행

```bash
# 실행 권한 부여
chmod +x scripts/benchmark_mongo_vs_sql.py

# 실행
python3 scripts/benchmark_mongo_vs_sql.py
```

### 3.3 예상 결과

```
================================================================================
MongoDB vs SQL Performance Benchmark
================================================================================
MongoDB Benchmarks
--------------------------------------------------------------------------------
1. Find commits by author               |    5.23 ms |   100 results
2. Sort + Limit (recent 50 commits)     |    3.45 ms |    50 results
3. Aggregate: Count by repository       |    8.12 ms |    15 results
4. Aggregate: User statistics           |   12.34 ms |    28 results
5. Embedded: Find commits with .rs files|    6.78 ms |    42 results

SQL (SQLite) Benchmarks
--------------------------------------------------------------------------------
1. Find commits by author               |    4.56 ms |   100 results
2. Sort + Limit (recent 50 commits)     |    3.21 ms |    50 results
3. Aggregate: Count by repository       |    7.89 ms |    15 results
4. Aggregate: User statistics           |   11.23 ms |    28 results
5. JOIN: Find commits with .rs files    |   15.67 ms |    42 results

Performance Comparison
--------------------------------------------------------------------------------
Query Type                               |    MongoDB |        SQL |     Winner
--------------------------------------------------------------------------------
simple_find                              |    5.23 ms |   4.56 ms | SQL (1.15x)
sort_limit                               |    3.45 ms |   3.21 ms | SQL (1.07x)
aggregate_count                          |    8.12 ms |   7.89 ms | SQL (1.03x)
aggregate_stats                          |   12.34 ms |  11.23 ms | SQL (1.10x)
embedded_query                           |    6.78 ms |  15.67 ms | MongoDB (2.31x)
--------------------------------------------------------------------------------
TOTAL                                    |   35.92 ms |  42.56 ms

Wins: MongoDB 1, SQL 4

🏆 SQL is 1.18x faster overall
```

---

## 4. 개발자 경험 평가

### 4.1 쿼리 작성 난이도

#### 시나리오 1: 사용자의 최근 활동 조회

**MongoDB:**
```javascript
// ✅ 간단하고 직관적
db.github_commits.find({ author_login: "jake-jang" })
  .sort({ committed_at: -1 })
  .limit(10)
```

**SQL:**
```sql
-- ✅ 동일하게 간단
SELECT * FROM github_commits
WHERE author_login = 'jake-jang'
ORDER BY committed_at DESC
LIMIT 10;
```

**평가:** 비슷함 (둘 다 쉬움) ⚖️

---

#### 시나리오 2: 커밋 + 파일 변경 내역 조회

**MongoDB:**
```javascript
// ✅ 임베디드 문서로 한 번에 조회
db.github_commits.find({ sha: "abc123" }, {
  message: 1,
  files: 1  // 파일 정보가 이미 포함되어 있음
})
```

**SQL:**
```sql
-- ❌ JOIN 필요
SELECT 
  c.sha,
  c.message,
  f.filename,
  f.additions,
  f.deletions
FROM github_commits c
LEFT JOIN github_commit_files f ON c.sha = f.commit_sha
WHERE c.sha = 'abc123';
```

**평가:** MongoDB 승리 (JOIN 불필요) 🏆 MongoDB

---

#### 시나리오 3: 동적 필터 쿼리

**MongoDB:**
```python
# ✅ Python dict로 동적 쿼리 구성
filter = {}
if author:
    filter['author_login'] = author
if repo:
    filter['repository_name'] = repo
if date_from:
    filter['committed_at'] = {'$gte': date_from}

results = db.github_commits.find(filter)
```

**SQL:**
```python
# ❌ 문자열 조합 (SQL Injection 위험)
query = "SELECT * FROM github_commits WHERE 1=1"
params = []
if author:
    query += " AND author_login = ?"
    params.append(author)
if repo:
    query += " AND repository_name = ?"
    params.append(repo)
if date_from:
    query += " AND committed_at >= ?"
    params.append(date_from)

cursor.execute(query, params)
```

**평가:** MongoDB 승리 (동적 쿼리가 더 안전하고 간단) 🏆 MongoDB

---

#### 시나리오 4: 복잡한 집계 (사용자별 통계)

**MongoDB:**
```javascript
// ❌ Aggregation Pipeline - 학습 곡선 있음
db.github_commits.aggregate([
  {
    $group: {
      _id: "$author_login",
      commits: { $sum: 1 },
      additions: { $sum: "$additions" },
      deletions: { $sum: "$deletions" },
      repos: { $addToSet: "$repository_name" }
    }
  },
  {
    $project: {
      author: "$_id",
      commits: 1,
      additions: 1,
      deletions: 1,
      repos_count: { $size: "$repos" }
    }
  },
  { $sort: { commits: -1 } }
])
```

**SQL:**
```sql
-- ✅ 익숙한 GROUP BY
SELECT 
  author_login,
  COUNT(*) as commits,
  SUM(additions) as additions,
  SUM(deletions) as deletions,
  COUNT(DISTINCT repository_name) as repos_count
FROM github_commits
GROUP BY author_login
ORDER BY commits DESC;
```

**평가:** SQL 승리 (익숙하고 읽기 쉬움) 🏆 SQL

---

### 4.2 데이터 모델 유지보수

#### 스키마 변경 시

**MongoDB:**
```javascript
// ✅ 스키마 변경이 자유로움
// 새 필드 추가 - 그냥 넣으면 됨
db.github_commits.updateMany({}, {
  $set: { new_field: "default_value" }
})

// 기존 문서에 영향 없음
db.github_commits.insertOne({
  sha: "xyz",
  message: "test",
  new_field: "value",  // 새 필드
  another_new_field: 123  // 또 다른 새 필드
})
```

**SQL:**
```sql
-- ❌ ALTER TABLE 필요
ALTER TABLE github_commits ADD COLUMN new_field TEXT;

-- ❌ 기존 데이터에 DEFAULT 값 설정 필요
UPDATE github_commits SET new_field = 'default_value';
```

**평가:** MongoDB 승리 (유연한 스키마) 🏆 MongoDB

---

### 4.3 Python 코드 비교

#### 데이터 삽입

**MongoDB:**
```python
# ✅ Python dict 그대로 저장
commit_data = {
    "sha": "abc123",
    "message": "Fix bug",
    "author_login": "johndoe",
    "committed_at": datetime.now(),
    "files": [  # 중첩 구조 가능
        {"filename": "test.py", "additions": 10}
    ]
}
db.github_commits.insert_one(commit_data)
```

**SQL:**
```python
# ❌ INSERT 문 작성 + 별도 테이블에 파일 저장
cursor.execute(
    "INSERT INTO github_commits (sha, message, author_login, committed_at) VALUES (?, ?, ?, ?)",
    (commit_data['sha'], commit_data['message'], commit_data['author_login'], commit_data['committed_at'])
)

# 별도로 파일 저장
for file in commit_data['files']:
    cursor.execute(
        "INSERT INTO github_commit_files (commit_sha, filename, additions) VALUES (?, ?, ?)",
        (commit_data['sha'], file['filename'], file['additions'])
    )
conn.commit()
```

**평가:** MongoDB 승리 (코드가 더 간결) 🏆 MongoDB

---

### 4.4 API 엔드포인트 코드

#### FastAPI 엔드포인트 예시

**MongoDB:**
```python
@app.get("/commits/{author}")
async def get_commits(author: str, limit: int = 10):
    commits = list(mongo_db.github_commits.find(
        {"author_login": author},
        {"_id": 0}  # ObjectId 제외
    ).sort("committed_at", -1).limit(limit))
    
    # datetime → string 변환 필요
    for commit in commits:
        commit['committed_at'] = commit['committed_at'].isoformat()
    
    return commits
```

**SQL:**
```python
@app.get("/commits/{author}")
async def get_commits(author: str, limit: int = 10):
    cursor = sql_conn.execute(
        "SELECT * FROM github_commits WHERE author_login = ? ORDER BY committed_at DESC LIMIT ?",
        (author, limit)
    )
    
    # Row to dict 변환
    columns = [desc[0] for desc in cursor.description]
    commits = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    return commits
```

**평가:** 비슷함 (둘 다 간단) ⚖️

---

### 4.5 동적 쿼리 API (`/api/v1/query/execute`)

**현재 구현 (SQL):**
```python
@app.post("/api/v1/query/execute")
async def execute_query(query: str, source: str):
    # ✅ SQL 쿼리를 직접 실행
    db = get_db(source)
    result = db.execute(query).fetchall()
    return result
```

**MongoDB로 전환 시:**
```python
@app.post("/api/v1/query/execute")
async def execute_query(query: dict, source: str):
    # ❌ MongoDB 쿼리는 dict/JSON 형태
    # ❌ 사용자가 MongoDB 쿼리 문법을 알아야 함
    # ❌ Aggregation pipeline은 별도 처리 필요
    
    db = get_mongo_db(source)
    
    if query.get('type') == 'find':
        result = list(db[query['collection']].find(query['filter']))
    elif query.get('type') == 'aggregate':
        result = list(db[query['collection']].aggregate(query['pipeline']))
    else:
        raise ValueError("Unknown query type")
    
    return result
```

**평가:** SQL 승리 (동적 쿼리 API는 SQL이 더 적합) 🏆 SQL

---

## 5. 평가 체크리스트

### 5.1 성능 평가

- [ ] **단순 조회 속도**: MongoDB vs SQL
- [ ] **복잡한 집계 속도**: Aggregation vs GROUP BY
- [ ] **JOIN 성능**: Embedded vs JOIN
- [ ] **대용량 데이터 테스트**: 10,000+ 레코드
- [ ] **인덱스 효과**: 인덱스 유무 차이

### 5.2 개발자 경험 평가

- [ ] **쿼리 작성 난이도**: 어느 쪽이 더 쉬운가?
- [ ] **코드 가독성**: 어느 쪽이 더 읽기 쉬운가?
- [ ] **디버깅 용이성**: 에러 메시지, 로깅
- [ ] **문서/커뮤니티**: 학습 자료 풍부도
- [ ] **IDE 지원**: 자동완성, 타입 체크

### 5.3 프로젝트 적합성 평가

- [ ] **현재 아키텍처와의 호환성**
  - 동적 SQL 쿼리 API를 MongoDB로 전환 가능한가?
  - 기존 리포트 생성 로직 재작성 필요한가?

- [ ] **팀 역량**
  - 팀원들이 MongoDB를 학습할 시간이 있는가?
  - MongoDB aggregation pipeline을 이해하고 있는가?

- [ ] **마이그레이션 비용**
  - 예상 개발 시간: _______ 주
  - 리스크: High / Medium / Low
  - ROI (투자 대비 효과): _____ / 10점

### 5.4 의사결정 매트릭스

| 평가 항목 | MongoDB | SQL | 가중치 | 점수 |
|----------|---------|-----|--------|------|
| **성능 (단순 쿼리)** | ⚪ | ⚪ | 3 | |
| **성능 (복잡한 집계)** | ⚪ | ⚪ | 2 | |
| **개발 속도** | ⚪ | ⚪ | 5 | |
| **학습 곡선** | ⚪ | ⚪ | 4 | |
| **스키마 유연성** | ⚪ | ⚪ | 2 | |
| **동적 쿼리 API** | ⚪ | ⚪ | 5 | |
| **마이그레이션 비용** | ⚪ | ⚪ | 4 | |
| **커뮤니티/생태계** | ⚪ | ⚪ | 2 | |

점수: 1 (매우 나쁨) ~ 5 (매우 좋음)

---

## 6. 실제 사용 시나리오 테스트

### 시나리오 1: 주간 팀 리포트 생성

**목표:** 특정 프로젝트의 주간 활동 요약

```javascript
// MongoDB
const startDate = new Date('2025-11-10');
const endDate = new Date('2025-11-16');

// 1. 커밋 수 집계
db.github_commits.aggregate([
  {
    $match: {
      repository_name: "Tokamak-zk-EVM",
      committed_at: { $gte: startDate, $lte: endDate }
    }
  },
  {
    $group: {
      _id: "$author_login",
      commits: { $sum: 1 },
      additions: { $sum: "$additions" },
      deletions: { $sum: "$deletions" }
    }
  },
  { $sort: { commits: -1 } }
])

// 2. PR 현황
db.github_pull_requests.countDocuments({
  repository_name: "Tokamak-zk-EVM",
  state: "MERGED",
  merged_at: { $gte: startDate, $lte: endDate }
})
```

**평가:**
- ⏱️ 쿼리 실행 시간: _____ ms
- 💻 코드 복잡도: _____ / 10
- 📝 가독성: _____ / 10

---

### 시나리오 2: 실시간 대시보드

**목표:** 최근 1시간 활동 모니터링

```javascript
// MongoDB
const oneHourAgo = new Date(Date.now() - 3600000);

db.github_commits.find({
  committed_at: { $gte: oneHourAgo }
}).sort({ committed_at: -1 })
```

**평가:**
- ⏱️ 응답 시간: _____ ms
- 🔄 업데이트 빈도: 문제 없음 / 느림

---

### 시나리오 3: 코드 리뷰 워크플로우

**목표:** 특정 파일을 수정한 커밋 추적

```javascript
// MongoDB (Embedded)
db.github_commits.find({
  "files.filename": "src/verifier.rs"
}, {
  sha: 1,
  message: 1,
  author_login: 1,
  committed_at: 1,
  "files.$": 1  // 매칭된 파일만
}).sort({ committed_at: -1 })
```

**평가:**
- ⏱️ 쿼리 속도: _____ ms
- 💡 유용성: _____ / 10

---

## 7. 최종 권장사항

### 평가 결과에 따른 결정 가이드

**MongoDB를 선택해야 하는 경우:**
- ✅ 스키마가 자주 변경되는 프로젝트
- ✅ 중첩 데이터 구조가 많은 경우
- ✅ 수평 확장(sharding)이 필요한 경우
- ✅ 동적 쿼리보다 정형화된 쿼리가 주로 사용되는 경우

**SQL을 유지해야 하는 경우:**
- ✅ 복잡한 JOIN이 많은 경우
- ✅ 동적 SQL 쿼리 API가 핵심 기능인 경우
- ✅ 팀이 SQL에 익숙한 경우
- ✅ ACID 트랜잭션이 중요한 경우
- ✅ 기존 아키텍처가 안정적이고 변경 비용이 큰 경우

---

## 8. 다음 단계

### A. MongoDB 계속 진행
```bash
# Slack 플러그인 변환
python src/plugins/slack_plugin_mongo.py

# Notion 플러그인 변환
python src/plugins/notion_plugin_mongo.py

# API 엔드포인트 수정
# ...
```

### B. PostgreSQL로 복귀
```bash
# MongoDB 프로토타입 파일 삭제 또는 보관
mv src/plugins/*_mongo.py archive/

# PostgreSQL 마이그레이션 진행
# ...
```

### C. 하이브리드 접근
```
# 플러그인별로 다른 DB 사용
- GitHub, Slack → MongoDB
- Notion, Google Drive → PostgreSQL
- Member Index → PostgreSQL (정규화된 데이터)
```

---

## 📝 평가 노트

평가 과정에서 발견한 사항들을 기록하세요:

```
날짜: _____________

테스트 환경:
- MongoDB 버전: _____________
- 데이터 크기: _____________
- 쿼리 수: _____________

발견 사항:
1. 

2. 

3. 

최종 결정:
[ ] MongoDB로 전환
[ ] PostgreSQL 유지
[ ] 하이브리드 접근

이유:


```

---

**실제로 사용해보고 직접 평가하세요!** 🚀

