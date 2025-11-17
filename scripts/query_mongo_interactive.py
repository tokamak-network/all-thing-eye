#!/usr/bin/env python3
"""
MongoDB Interactive Query Tool

MongoDB 데이터를 직접 조회하고 탐색할 수 있는 대화형 도구
"""

import sys
from pathlib import Path
from pymongo import MongoClient
from datetime import datetime
import json
from bson import ObjectId

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 설정
MONGODB_URI = "mongodb://localhost:27017"
MONGODB_DB = "all_thing_eye_test"


class MongoQueryTool:
    def __init__(self):
        self.client = None
        self.db = None
        
    def connect(self):
        """MongoDB 연결"""
        try:
            self.client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            self.db = self.client[MONGODB_DB]
            self.db.command("ping")
            print(f"✅ Connected to MongoDB: {MONGODB_URI}/{MONGODB_DB}\n")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def disconnect(self):
        """연결 종료"""
        if self.client:
            self.client.close()
            print("\n👋 Disconnected from MongoDB")
    
    def show_menu(self):
        """메뉴 표시"""
        print("\n" + "="*80)
        print("📋 MongoDB Query Menu")
        print("="*80)
        print("1️⃣  Show all collections (컬렉션 목록)")
        print("2️⃣  Show collection stats (컬렉션 통계)")
        print("3️⃣  Find commits by author (사용자별 커밋 조회)")
        print("4️⃣  Find recent commits (최근 커밋 조회)")
        print("5️⃣  Find commits by repository (저장소별 커밋 조회)")
        print("6️⃣  Count commits per repository (저장소별 커밋 수)")
        print("7️⃣  User activity statistics (사용자 활동 통계)")
        print("8️⃣  Find commits with specific files (파일별 커밋 조회)")
        print("9️⃣  Show pull requests (PR 조회)")
        print("🔟  Show issues (이슈 조회)")
        print("0️⃣  Exit (종료)")
        print("="*80)
    
    def show_collections(self):
        """컬렉션 목록 표시"""
        collections = self.db.list_collection_names()
        print(f"\n📚 Collections ({len(collections)}):")
        for i, coll in enumerate(collections, 1):
            count = self.db[coll].count_documents({})
            print(f"   {i}. {coll:30s} ({count:5d} documents)")
    
    def show_collection_stats(self):
        """컬렉션 통계"""
        print("\n📊 Collection Statistics:")
        print("-"*80)
        
        collections = ['github_commits', 'github_pull_requests', 'github_issues', 'github_repositories']
        
        for coll_name in collections:
            if coll_name in self.db.list_collection_names():
                coll = self.db[coll_name]
                count = coll.count_documents({})
                
                # 샘플 문서 크기
                sample = coll.find_one()
                if sample:
                    size_kb = len(str(sample)) / 1024
                    print(f"\n{coll_name}:")
                    print(f"  Documents: {count}")
                    print(f"  Avg doc size: ~{size_kb:.2f} KB")
                    
                    # 컬렉션별 추가 통계
                    if coll_name == 'github_commits':
                        total_additions = sum(doc.get('additions', 0) for doc in coll.find({}, {'additions': 1}).limit(1000))
                        print(f"  Total additions (sample): {total_additions:,}")
                    elif coll_name == 'github_pull_requests':
                        merged = coll.count_documents({'state': 'MERGED'})
                        open_prs = coll.count_documents({'state': 'OPEN'})
                        print(f"  Merged: {merged}, Open: {open_prs}")
    
    def find_commits_by_author(self):
        """사용자별 커밋 조회"""
        author = input("\n👤 Enter author login (e.g., jake-jang): ").strip()
        limit = int(input("📝 Limit (default 10): ").strip() or "10")
        
        print(f"\n🔍 Searching commits by {author}...")
        
        commits = list(self.db.github_commits.find(
            {"author_login": author},
            {"sha": 1, "message": 1, "repository_name": 1, "committed_at": 1, "additions": 1, "deletions": 1}
        ).sort("committed_at", -1).limit(limit))
        
        if not commits:
            print(f"❌ No commits found for {author}")
            return
        
        print(f"\n✅ Found {len(commits)} commits:")
        print("-"*80)
        
        for i, commit in enumerate(commits, 1):
            date = commit['committed_at'].strftime('%Y-%m-%d %H:%M')
            msg = commit['message'][:60] + '...' if len(commit['message']) > 60 else commit['message']
            print(f"{i:2d}. [{date}] {commit['repository_name']}")
            print(f"    {msg}")
            print(f"    SHA: {commit['sha'][:10]}... (+{commit.get('additions', 0)} -{commit.get('deletions', 0)})")
            print()
    
    def find_recent_commits(self):
        """최근 커밋 조회"""
        limit = int(input("\n📝 How many commits? (default 20): ").strip() or "20")
        
        print(f"\n🔍 Fetching {limit} recent commits...")
        
        commits = list(self.db.github_commits.find(
            {},
            {"sha": 1, "message": 1, "repository_name": 1, "author_login": 1, "committed_at": 1}
        ).sort("committed_at", -1).limit(limit))
        
        print(f"\n✅ Recent {len(commits)} commits:")
        print("-"*80)
        
        for i, commit in enumerate(commits, 1):
            date = commit['committed_at'].strftime('%Y-%m-%d %H:%M')
            msg = commit['message'][:50] + '...' if len(commit['message']) > 50 else commit['message']
            print(f"{i:2d}. [{date}] {commit['author_login']} @ {commit['repository_name']}")
            print(f"    {msg}")
            print()
    
    def find_commits_by_repo(self):
        """저장소별 커밋 조회"""
        repo = input("\n📦 Enter repository name (e.g., Tokamak-zk-EVM): ").strip()
        limit = int(input("📝 Limit (default 20): ").strip() or "20")
        
        print(f"\n🔍 Searching commits in {repo}...")
        
        commits = list(self.db.github_commits.find(
            {"repository_name": repo},
            {"sha": 1, "message": 1, "author_login": 1, "committed_at": 1, "additions": 1, "deletions": 1}
        ).sort("committed_at", -1).limit(limit))
        
        if not commits:
            print(f"❌ No commits found in {repo}")
            return
        
        print(f"\n✅ Found {len(commits)} commits in {repo}:")
        print("-"*80)
        
        for i, commit in enumerate(commits, 1):
            date = commit['committed_at'].strftime('%Y-%m-%d %H:%M')
            msg = commit['message'][:60] + '...' if len(commit['message']) > 60 else commit['message']
            print(f"{i:2d}. [{date}] {commit['author_login']}")
            print(f"    {msg}")
            print(f"    (+{commit.get('additions', 0)} -{commit.get('deletions', 0)})")
            print()
    
    def count_commits_per_repo(self):
        """저장소별 커밋 수 집계"""
        print("\n🔍 Counting commits per repository...")
        
        result = list(self.db.github_commits.aggregate([
            {
                "$group": {
                    "_id": "$repository_name",
                    "count": {"$sum": 1},
                    "total_additions": {"$sum": "$additions"},
                    "total_deletions": {"$sum": "$deletions"}
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 20}
        ]))
        
        print(f"\n✅ Top 20 repositories by commit count:")
        print("-"*80)
        print(f"{'Repository':40s} | {'Commits':>8s} | {'Additions':>10s} | {'Deletions':>10s}")
        print("-"*80)
        
        for repo_data in result:
            repo = repo_data['_id']
            count = repo_data['count']
            adds = repo_data['total_additions']
            dels = repo_data['total_deletions']
            print(f"{repo:40s} | {count:8d} | {adds:10,d} | {dels:10,d}")
    
    def user_activity_stats(self):
        """사용자 활동 통계"""
        print("\n🔍 Calculating user activity statistics...")
        
        result = list(self.db.github_commits.aggregate([
            {
                "$group": {
                    "_id": "$author_login",
                    "commits": {"$sum": 1},
                    "additions": {"$sum": "$additions"},
                    "deletions": {"$sum": "$deletions"},
                    "repos": {"$addToSet": "$repository_name"}
                }
            },
            {
                "$project": {
                    "author": "$_id",
                    "commits": 1,
                    "additions": 1,
                    "deletions": 1,
                    "repos_count": {"$size": "$repos"}
                }
            },
            {"$sort": {"commits": -1}},
            {"$limit": 15}
        ]))
        
        print(f"\n✅ Top 15 contributors:")
        print("-"*80)
        print(f"{'Author':20s} | {'Commits':>8s} | {'Repos':>6s} | {'Additions':>10s} | {'Deletions':>10s}")
        print("-"*80)
        
        for user_data in result:
            author = user_data['author']
            commits = user_data['commits']
            repos = user_data['repos_count']
            adds = user_data['additions']
            dels = user_data['deletions']
            print(f"{author:20s} | {commits:8d} | {repos:6d} | {adds:10,d} | {dels:10,d}")
    
    def find_commits_by_files(self):
        """파일별 커밋 조회"""
        file_pattern = input("\n📄 Enter file pattern (e.g., .rs, verifier, src/): ").strip()
        limit = int(input("📝 Limit (default 10): ").strip() or "10")
        
        print(f"\n🔍 Searching commits with files matching '{file_pattern}'...")
        
        commits = list(self.db.github_commits.find(
            {"files.filename": {"$regex": file_pattern, "$options": "i"}},
            {"sha": 1, "message": 1, "repository_name": 1, "author_login": 1, "committed_at": 1, "files": 1}
        ).sort("committed_at", -1).limit(limit))
        
        if not commits:
            print(f"❌ No commits found with files matching '{file_pattern}'")
            return
        
        print(f"\n✅ Found {len(commits)} commits:")
        print("-"*80)
        
        for i, commit in enumerate(commits, 1):
            date = commit['committed_at'].strftime('%Y-%m-%d %H:%M')
            msg = commit['message'][:50] + '...' if len(commit['message']) > 50 else commit['message']
            
            # 매칭된 파일만 표시
            matched_files = [f for f in commit.get('files', []) if file_pattern.lower() in f['filename'].lower()]
            
            print(f"{i:2d}. [{date}] {commit['author_login']} @ {commit['repository_name']}")
            print(f"    {msg}")
            print(f"    Files ({len(matched_files)}):")
            for f in matched_files[:3]:  # 최대 3개만
                print(f"      - {f['filename']} (+{f.get('additions', 0)} -{f.get('deletions', 0)})")
            if len(matched_files) > 3:
                print(f"      ... and {len(matched_files) - 3} more")
            print()
    
    def show_pull_requests(self):
        """PR 조회"""
        repo = input("\n📦 Enter repository name (or press Enter for all): ").strip()
        state = input("🏷️  State (OPEN/MERGED/CLOSED, or press Enter for all): ").strip().upper()
        limit = int(input("📝 Limit (default 10): ").strip() or "10")
        
        query = {}
        if repo:
            query['repository_name'] = repo
        if state:
            query['state'] = state
        
        print(f"\n🔍 Fetching pull requests...")
        
        prs = list(self.db.github_pull_requests.find(
            query,
            {"number": 1, "title": 1, "repository_name": 1, "author_login": 1, "state": 1, "created_at": 1, "merged_at": 1}
        ).sort("created_at", -1).limit(limit))
        
        if not prs:
            print("❌ No pull requests found")
            return
        
        print(f"\n✅ Found {len(prs)} pull requests:")
        print("-"*80)
        
        for i, pr in enumerate(prs, 1):
            created = pr['created_at'].strftime('%Y-%m-%d')
            merged = pr.get('merged_at')
            merged_str = f" (merged {merged.strftime('%Y-%m-%d')})" if merged else ""
            
            print(f"{i:2d}. #{pr['number']} [{pr['state']}] {pr['repository_name']}")
            print(f"    {pr['title']}")
            print(f"    By {pr['author_login']} on {created}{merged_str}")
            print()
    
    def show_issues(self):
        """이슈 조회"""
        repo = input("\n📦 Enter repository name (or press Enter for all): ").strip()
        state = input("🏷️  State (OPEN/CLOSED, or press Enter for all): ").strip().upper()
        limit = int(input("📝 Limit (default 10): ").strip() or "10")
        
        query = {}
        if repo:
            query['repository_name'] = repo
        if state:
            query['state'] = state
        
        print(f"\n🔍 Fetching issues...")
        
        issues = list(self.db.github_issues.find(
            query,
            {"number": 1, "title": 1, "repository_name": 1, "author_login": 1, "state": 1, "created_at": 1}
        ).sort("created_at", -1).limit(limit))
        
        if not issues:
            print("❌ No issues found")
            return
        
        print(f"\n✅ Found {len(issues)} issues:")
        print("-"*80)
        
        for i, issue in enumerate(issues, 1):
            created = issue['created_at'].strftime('%Y-%m-%d')
            
            print(f"{i:2d}. #{issue['number']} [{issue['state']}] {issue['repository_name']}")
            print(f"    {issue['title']}")
            print(f"    By {issue['author_login']} on {created}")
            print()
    
    def run(self):
        """메인 루프"""
        if not self.connect():
            return
        
        try:
            while True:
                self.show_menu()
                choice = input("\n➡️  Select an option: ").strip()
                
                if choice == '1':
                    self.show_collections()
                elif choice == '2':
                    self.show_collection_stats()
                elif choice == '3':
                    self.find_commits_by_author()
                elif choice == '4':
                    self.find_recent_commits()
                elif choice == '5':
                    self.find_commits_by_repo()
                elif choice == '6':
                    self.count_commits_per_repo()
                elif choice == '7':
                    self.user_activity_stats()
                elif choice == '8':
                    self.find_commits_by_files()
                elif choice == '9':
                    self.show_pull_requests()
                elif choice == '10' or choice == '0':
                    self.show_issues()
                elif choice == '0':
                    break
                else:
                    print("❌ Invalid option. Please try again.")
                
                input("\n⏸️  Press Enter to continue...")
        
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
        
        finally:
            self.disconnect()


def main():
    """메인 함수"""
    print("\n" + "="*80)
    print("🍃 MongoDB Interactive Query Tool")
    print("="*80)
    print(f"MongoDB URI: {MONGODB_URI}")
    print(f"Database: {MONGODB_DB}")
    
    tool = MongoQueryTool()
    tool.run()
    
    print("\n👋 Goodbye!")


if __name__ == "__main__":
    main()

