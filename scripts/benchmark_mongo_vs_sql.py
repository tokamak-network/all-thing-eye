#!/usr/bin/env python3
"""
MongoDB vs SQL Performance Benchmark

MongoDB 프로토타입과 기존 SQL 버전의 성능을 비교합니다.
"""

import time
import sqlite3
import sys
from pathlib import Path
from pymongo import MongoClient
from datetime import datetime
from typing import List, Tuple, Dict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 설정
MONGODB_URI = "mongodb://localhost:27017"
MONGODB_DB = "all_thing_eye_test"
SQLITE_DB = project_root / "data" / "databases" / "github.db"


def benchmark_query(name: str, func, description: str = "") -> Tuple[float, int]:
    """
    쿼리 실행 시간 측정
    
    Returns:
        (elapsed_ms, result_count)
    """
    start = time.perf_counter()
    try:
        result = func()
        end = time.perf_counter()
        elapsed_ms = (end - start) * 1000
        
        # 결과 개수 확인
        if isinstance(result, list):
            count = len(result)
        elif hasattr(result, '__len__'):
            count = len(result)
        else:
            count = 0
        
        status = "✅"
    except Exception as e:
        end = time.perf_counter()
        elapsed_ms = (end - start) * 1000
        count = 0
        status = f"❌ {str(e)[:30]}"
    
    # 결과 출력
    if description:
        print(f"  {status} {description}")
    print(f"     {name:45s} | {elapsed_ms:8.2f} ms | {count:5d} results")
    
    return elapsed_ms, count


def run_mongodb_benchmarks() -> Dict[str, float]:
    """MongoDB 벤치마크 실행"""
    print("\n" + "="*80)
    print("🍃 MongoDB Benchmarks")
    print("="*80)
    
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        db = client[MONGODB_DB]
        
        # 연결 테스트
        db.command("ping")
        print(f"✅ Connected to MongoDB: {MONGODB_URI}/{MONGODB_DB}\n")
        
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        return {}
    
    times = {}
    
    # 1. 단순 조회
    print("1️⃣ Simple Find Query")
    times['simple_find'], _ = benchmark_query(
        "Find commits by author",
        lambda: list(db.github_commits.find({"author_login": "jake-jang"}).limit(100)),
        "특정 사용자의 커밋 조회 (limit 100)"
    )
    
    # 2. 정렬 + 제한
    print("\n2️⃣ Sort + Limit Query")
    times['sort_limit'], _ = benchmark_query(
        "Recent commits with sort",
        lambda: list(db.github_commits.find().sort("committed_at", -1).limit(50)),
        "최근 커밋 50개 조회 (정렬)"
    )
    
    # 3. 필터 + 정렬
    print("\n3️⃣ Filter + Sort Query")
    times['filter_sort'], _ = benchmark_query(
        "Filter by repository and sort",
        lambda: list(db.github_commits.find(
            {"repository_name": "Tokamak-zk-EVM"}
        ).sort("committed_at", -1)),
        "특정 저장소의 커밋 조회 + 정렬"
    )
    
    # 4. 집계 - 저장소별 카운트
    print("\n4️⃣ Aggregation: Count by Repository")
    times['aggregate_count'], _ = benchmark_query(
        "Count commits per repository",
        lambda: list(db.github_commits.aggregate([
            {"$group": {"_id": "$repository_name", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ])),
        "저장소별 커밋 수 집계"
    )
    
    # 5. 복잡한 집계 - 사용자별 통계
    print("\n5️⃣ Aggregation: User Statistics")
    times['aggregate_stats'], _ = benchmark_query(
        "User commit statistics",
        lambda: list(db.github_commits.aggregate([
            {"$group": {
                "_id": "$author_login",
                "commits": {"$sum": 1},
                "additions": {"$sum": "$additions"},
                "deletions": {"$sum": "$deletions"}
            }},
            {"$sort": {"commits": -1}}
        ])),
        "사용자별 커밋 통계 (커밋 수, 추가/삭제 라인)"
    )
    
    # 6. 임베디드 문서 쿼리
    print("\n6️⃣ Embedded Document Query")
    times['embedded_query'], _ = benchmark_query(
        "Find commits with Rust files",
        lambda: list(db.github_commits.find(
            {"files.filename": {"$regex": r"\.rs$"}},
            {"sha": 1, "message": 1, "files.filename": 1}
        ).limit(50)),
        ".rs 파일을 수정한 커밋 조회 (임베디드 문서)"
    )
    
    # 7. 전체 문서 수 카운트
    print("\n7️⃣ Count All Documents")
    times['count_all'], _ = benchmark_query(
        "Count all commits",
        lambda: [db.github_commits.count_documents({})],
        "전체 커밋 수 조회"
    )
    
    client.close()
    return times


def run_sql_benchmarks() -> Dict[str, float]:
    """SQL (SQLite) 벤치마크 실행"""
    print("\n" + "="*80)
    print("🗄️  SQL (SQLite) Benchmarks")
    print("="*80)
    
    if not SQLITE_DB.exists():
        print(f"❌ SQLite database not found: {SQLITE_DB}")
        return {}
    
    try:
        conn = sqlite3.connect(str(SQLITE_DB))
        cursor = conn.cursor()
        print(f"✅ Connected to SQLite: {SQLITE_DB}\n")
        
    except Exception as e:
        print(f"❌ SQLite connection failed: {e}")
        return {}
    
    times = {}
    
    # 1. 단순 조회
    print("1️⃣ Simple SELECT Query")
    times['simple_find'], _ = benchmark_query(
        "Find commits by author",
        lambda: cursor.execute(
            "SELECT * FROM github_commits WHERE author_login = ? LIMIT 100",
            ("jake-jang",)
        ).fetchall(),
        "특정 사용자의 커밋 조회 (limit 100)"
    )
    
    # 2. 정렬 + 제한
    print("\n2️⃣ Sort + Limit Query")
    times['sort_limit'], _ = benchmark_query(
        "Recent commits with sort",
        lambda: cursor.execute(
            "SELECT * FROM github_commits ORDER BY committed_at DESC LIMIT 50"
        ).fetchall(),
        "최근 커밋 50개 조회 (정렬)"
    )
    
    # 3. 필터 + 정렬
    print("\n3️⃣ Filter + Sort Query")
    times['filter_sort'], _ = benchmark_query(
        "Filter by repository and sort",
        lambda: cursor.execute(
            "SELECT * FROM github_commits WHERE repository_name = ? ORDER BY committed_at DESC",
            ("Tokamak-zk-EVM",)
        ).fetchall(),
        "특정 저장소의 커밋 조회 + 정렬"
    )
    
    # 4. 집계 - 저장소별 카운트
    print("\n4️⃣ Aggregation: Count by Repository")
    times['aggregate_count'], _ = benchmark_query(
        "Count commits per repository",
        lambda: cursor.execute(
            "SELECT repository_name, COUNT(*) as count "
            "FROM github_commits GROUP BY repository_name ORDER BY count DESC"
        ).fetchall(),
        "저장소별 커밋 수 집계"
    )
    
    # 5. 복잡한 집계 - 사용자별 통계
    print("\n5️⃣ Aggregation: User Statistics")
    times['aggregate_stats'], _ = benchmark_query(
        "User commit statistics",
        lambda: cursor.execute(
            "SELECT author_login, COUNT(*) as commits, "
            "SUM(additions) as additions, SUM(deletions) as deletions "
            "FROM github_commits GROUP BY author_login ORDER BY commits DESC"
        ).fetchall(),
        "사용자별 커밋 통계 (커밋 수, 추가/삭제 라인)"
    )
    
    # 6. LIKE 쿼리 (파일명 검색 시뮬레이션)
    # Note: SQL에서는 별도 테이블 JOIN이 필요하지만, 여기서는 단순화
    print("\n6️⃣ LIKE Query (Simulated)")
    times['embedded_query'], _ = benchmark_query(
        "Find commits (simulated file search)",
        lambda: cursor.execute(
            "SELECT sha, message FROM github_commits WHERE message LIKE '%rust%' LIMIT 50"
        ).fetchall(),
        "메시지에 'rust' 포함된 커밋 조회 (파일 검색 시뮬레이션)"
    )
    
    # 7. 전체 레코드 수 카운트
    print("\n7️⃣ Count All Records")
    times['count_all'], _ = benchmark_query(
        "Count all commits",
        lambda: cursor.execute("SELECT COUNT(*) FROM github_commits").fetchall(),
        "전체 커밋 수 조회"
    )
    
    conn.close()
    return times


def compare_results(mongo_times: Dict[str, float], sql_times: Dict[str, float]):
    """결과 비교 및 요약"""
    print("\n" + "="*80)
    print("📊 Performance Comparison Summary")
    print("="*80)
    
    if not mongo_times or not sql_times:
        print("⚠️  Cannot compare - one or both benchmarks failed")
        return
    
    print(f"{'Query Type':40s} | {'MongoDB':>10s} | {'SQL':>10s} | {'Winner':>15s}")
    print("-"*80)
    
    total_mongo = 0
    total_sql = 0
    mongo_wins = 0
    sql_wins = 0
    ties = 0
    
    for key in mongo_times.keys():
        if key not in sql_times:
            continue
        
        mongo_time = mongo_times[key]
        sql_time = sql_times[key]
        
        # 승자 결정 (10% 이내 차이는 동점 처리)
        diff_percent = abs(mongo_time - sql_time) / min(mongo_time, sql_time) * 100
        
        if diff_percent < 10:
            winner = "Tie"
            speedup_str = f"±{diff_percent:.1f}%"
            ties += 1
        elif mongo_time < sql_time:
            winner = "MongoDB"
            speedup = sql_time / mongo_time
            speedup_str = f"{speedup:.2f}x faster"
            mongo_wins += 1
        else:
            winner = "SQL"
            speedup = mongo_time / sql_time
            speedup_str = f"{speedup:.2f}x faster"
            sql_wins += 1
        
        total_mongo += mongo_time
        total_sql += sql_time
        
        print(f"{key:40s} | {mongo_time:8.2f} ms | {sql_time:8.2f} ms | {winner:>8s} {speedup_str:>6s}")
    
    print("-"*80)
    print(f"{'TOTAL':40s} | {total_mongo:8.2f} ms | {total_sql:8.2f} ms")
    
    print(f"\n📈 Results:")
    print(f"   MongoDB wins: {mongo_wins}")
    print(f"   SQL wins: {sql_wins}")
    print(f"   Ties: {ties}")
    
    # 전체 승자
    if total_mongo < total_sql:
        speedup = total_sql / total_mongo
        print(f"\n🏆 Overall Winner: MongoDB ({speedup:.2f}x faster)")
    elif total_sql < total_mongo:
        speedup = total_mongo / total_sql
        print(f"\n🏆 Overall Winner: SQL ({speedup:.2f}x faster)")
    else:
        print(f"\n🤝 Overall: Tie")
    
    # 평균 시간
    avg_mongo = total_mongo / len(mongo_times)
    avg_sql = total_sql / len(sql_times)
    print(f"\n⏱️  Average Query Time:")
    print(f"   MongoDB: {avg_mongo:.2f} ms")
    print(f"   SQL: {avg_sql:.2f} ms")


def main():
    """메인 함수"""
    print("\n" + "="*80)
    print("🚀 MongoDB vs SQL Performance Benchmark")
    print("="*80)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"MongoDB URI: {MONGODB_URI}")
    print(f"SQLite DB: {SQLITE_DB}")
    
    try:
        # MongoDB 벤치마크
        mongo_times = run_mongodb_benchmarks()
        
        # SQL 벤치마크
        sql_times = run_sql_benchmarks()
        
        # 결과 비교
        compare_results(mongo_times, sql_times)
        
        print("\n" + "="*80)
        print("✅ Benchmark completed successfully!")
        print("="*80)
        
        # 권장사항
        print("\n💡 Recommendations:")
        print("   1. MongoDB는 임베디드 문서 쿼리에서 강점")
        print("   2. SQL은 단순 조회와 집계에서 안정적")
        print("   3. 실제 워크로드에 맞는 DB를 선택하세요")
        
    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

