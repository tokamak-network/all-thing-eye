"""GitHub data source plugin"""

import time
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import requests
from .base import DataSourcePlugin


class GitHubPlugin(DataSourcePlugin):
    """
    GitHub data collection plugin
    
    Collects data from GitHub including:
    - Organization members
    - Repositories
    - Commits (with optional diff/patch)
    - Pull Requests
    - Issues
    """
    
    # GitHub API endpoints
    GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
    REST_API_BASE = "https://api.github.com"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.token = config.get('token')
        self.org_name = config.get('organization')
        self.include_diff = config.get('collection', {}).get('include_diff', False)
        self.rate_limit = config.get('rate_limit', 5000)
        self.member_list = config.get('member_list', [])
        
        # Session for REST API
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        })
        
        # Track problematic repositories to skip them for other members
        self.problematic_repos = set()
    
    def get_source_name(self) -> str:
        return "github"
    
    def get_db_schema(self) -> Dict[str, str]:
        """Define database schema for GitHub data"""
        return {
            'github_members': '''
                CREATE TABLE IF NOT EXISTS github_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    login TEXT NOT NULL UNIQUE,
                    github_id TEXT,
                    name TEXT,
                    email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'github_repositories': '''
                CREATE TABLE IF NOT EXISTS github_repositories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    github_id TEXT UNIQUE,
                    url TEXT,
                    description TEXT,
                    is_archived BOOLEAN DEFAULT 0,
                    pushed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'github_commits': '''
                CREATE TABLE IF NOT EXISTS github_commits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sha TEXT NOT NULL UNIQUE,
                    message TEXT,
                    url TEXT,
                    committed_at TIMESTAMP,
                    author_login TEXT,
                    repository_name TEXT,
                    additions INTEGER DEFAULT 0,
                    deletions INTEGER DEFAULT 0,
                    changed_files INTEGER DEFAULT 0,
                    branch TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (author_login) REFERENCES github_members(login)
                )
            ''',
            'github_commit_files': '''
                CREATE TABLE IF NOT EXISTS github_commit_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    commit_sha TEXT NOT NULL,
                    filename TEXT,
                    additions INTEGER DEFAULT 0,
                    deletions INTEGER DEFAULT 0,
                    changes INTEGER DEFAULT 0,
                    status TEXT,
                    patch TEXT,
                    added_lines TEXT,
                    deleted_lines TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (commit_sha) REFERENCES github_commits(sha),
                    UNIQUE(commit_sha, filename)
                )
            ''',
            'github_pull_requests': '''
                CREATE TABLE IF NOT EXISTS github_pull_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    number INTEGER NOT NULL,
                    title TEXT,
                    url TEXT,
                    state TEXT,
                    created_at TIMESTAMP,
                    merged_at TIMESTAMP,
                    closed_at TIMESTAMP,
                    author_login TEXT,
                    repository_name TEXT,
                    additions INTEGER DEFAULT 0,
                    deletions INTEGER DEFAULT 0,
                    FOREIGN KEY (author_login) REFERENCES github_members(login),
                    UNIQUE(repository_name, number)
                )
            ''',
            'github_issues': '''
                CREATE TABLE IF NOT EXISTS github_issues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    number INTEGER NOT NULL,
                    title TEXT,
                    url TEXT,
                    state TEXT,
                    created_at TIMESTAMP,
                    closed_at TIMESTAMP,
                    author_login TEXT,
                    repository_name TEXT,
                    FOREIGN KEY (author_login) REFERENCES github_members(login),
                    UNIQUE(repository_name, number)
                )
            '''
        }
    
    def authenticate(self) -> bool:
        """Authenticate with GitHub API"""
        if not self.token:
            print(f"❌ GitHub token not provided")
            return False
        
        try:
            # Test authentication with a simple query
            query = '''
                query {
                    viewer {
                        login
                    }
                }
            '''
            result = self._query_graphql(query, {})
            
            if result and 'viewer' in result:
                self._authenticated = True
                print(f"✅ GitHub authentication successful (user: {result['viewer']['login']})")
                return True
            
            return False
        except Exception as e:
            print(f"❌ GitHub authentication failed: {e}")
            return False
    
    def collect_data(
        self, 
        start_date: datetime, 
        end_date: datetime,
        **kwargs
    ) -> Dict[str, Any]:
        """Collect GitHub data for the specified period"""
        print(f"\n📊 Collecting GitHub data for {self.org_name}")
        print(f"   Period: {start_date.isoformat()} ~ {end_date.isoformat()}")
        
        if not self._authenticated:
            if not self.authenticate():
                raise RuntimeError("GitHub authentication required")
        
        collected_data = {
            'members': [],
            'repositories': [],
            'commits': [],
            'pull_requests': [],
            'issues': []
        }
        
        try:
            # 1. Get members from predefined list or org
            print("\n1️⃣ Fetching members...")
            collected_data['members'] = self._get_members()
            print(f"   ✅ Found {len(collected_data['members'])} members")
            
            # 2. Get repositories
            print("\n2️⃣ Fetching repositories...")
            collected_data['repositories'] = self._get_repositories()
            print(f"   ✅ Found {len(collected_data['repositories'])} repositories")
            
            # 3. Get pull requests
            print("\n3️⃣ Fetching pull requests...")
            collected_data['pull_requests'] = self._get_pull_requests(start_date, end_date)
            print(f"   ✅ Found {len(collected_data['pull_requests'])} pull requests")
            
            # 4. Get issues
            print("\n4️⃣ Fetching issues...")
            collected_data['issues'] = self._get_issues(start_date, end_date)
            print(f"   ✅ Found {len(collected_data['issues'])} issues")
            
            # 5. Get commits for each member
            print("\n5️⃣ Fetching commits...")
            collected_data['commits'] = self._get_all_member_commits(
                collected_data['members'],
                collected_data['repositories'],
                start_date,
                end_date
            )
            print(f"   ✅ Found {len(collected_data['commits'])} total commits")
            
            return [collected_data]
            
        except Exception as e:
            print(f"❌ Error collecting GitHub data: {e}")
            raise
    
    def get_member_mapping(self) -> Dict[str, str]:
        """
        Map GitHub usernames to member names
        
        Returns:
            Dict of {github_login: member_name}
            Uses the 'name' field from members.csv as the primary identifier
        """
        mapping = {}
        
        for member in self.member_list:
            github_id = member.get('githubId') or member.get('github_id')
            name = member.get('name')
            email = member.get('email')
            
            if github_id and name:
                # Use name as primary identifier (e.g., 'Ale', 'Kevin')
                # This matches the 'name' column in members.csv
                mapping[github_id.lower()] = name
            elif github_id:
                # Fallback to email if name is not available
                mapping[github_id.lower()] = email or github_id
        
        return mapping
    
    def get_member_details(self) -> Dict[str, Dict[str, str]]:
        """
        Get detailed member information
        
        Returns:
            Dict of {member_name: {'email': '...', 'github_id': '...'}}
        """
        details = {}
        
        for member in self.member_list:
            name = member.get('name')
            email = member.get('email')
            github_id = member.get('githubId') or member.get('github_id')
            
            if name:
                details[name] = {
                    'email': email,
                    'github_id': github_id
                }
        
        return details
    
    def extract_member_activities(
        self, 
        data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract normalized member activities from GitHub data"""
        activities = []
        
        if not data:
            return activities
        
        github_data = data[0]  # Collected data is wrapped in a list
        
        # Extract commit activities
        for commit in github_data.get('commits', []):
            sha = commit.get('sha')
            activities.append({
                'member_identifier': commit.get('author_login'),
                'activity_type': 'github_commit',
                'timestamp': datetime.fromisoformat(commit.get('committed_at').replace('Z', '+00:00')),
                'activity_id': f"github:commit:{sha}",
                'metadata': {
                    'repository': commit.get('repository_name'),
                    'message': commit.get('message'),
                    'sha': sha,
                    'additions': commit.get('additions', 0),
                    'deletions': commit.get('deletions', 0),
                    'url': commit.get('url')
                }
            })
        
        # Extract PR activities
        for pr in github_data.get('pull_requests', []):
            repo = pr.get('repository_name')
            number = pr.get('number')
            activities.append({
                'member_identifier': pr.get('author_login'),
                'activity_type': 'github_pull_request',
                'timestamp': datetime.fromisoformat(pr.get('created_at').replace('Z', '+00:00')),
                'activity_id': f"github:pr:{repo}:{number}",
                'metadata': {
                    'repository': repo,
                    'title': pr.get('title'),
                    'number': number,
                    'state': pr.get('state'),
                    'url': pr.get('url')
                }
            })
        
        # Extract issue activities
        for issue in github_data.get('issues', []):
            repo = issue.get('repository_name')
            number = issue.get('number')
            activities.append({
                'member_identifier': issue.get('author_login'),
                'activity_type': 'github_issue',
                'timestamp': datetime.fromisoformat(issue.get('created_at').replace('Z', '+00:00')),
                'activity_id': f"github:issue:{repo}:{number}",
                'metadata': {
                    'repository': repo,
                    'title': issue.get('title'),
                    'number': number,
                    'state': issue.get('state'),
                    'url': issue.get('url')
                }
            })
        
        return activities
    
    def get_required_config_keys(self) -> List[str]:
        return ['token', 'organization']
    
    # ==================== Private Helper Methods ====================
    
    @staticmethod
    def _parse_patch(patch: Optional[str]) -> Dict[str, List[str]]:
        """
        Parse patch string and extract added/deleted lines
        
        Args:
            patch: Unified diff patch string
            
        Returns:
            Dict with 'added_lines' and 'deleted_lines' lists
        """
        if not patch:
            return {'added_lines': [], 'deleted_lines': []}
        
        lines = patch.split('\n')
        added_lines = []
        deleted_lines = []
        
        for line in lines:
            # Skip file headers and line number info
            if line.startswith('---') or line.startswith('+++') or line.startswith('@@'):
                continue
            
            # Deleted line (starts with -)
            if line.startswith('-'):
                deleted_lines.append(line[1:])  # Remove the '-' prefix
            # Added line (starts with +)
            elif line.startswith('+'):
                added_lines.append(line[1:])  # Remove the '+' prefix
        
        return {
            'added_lines': added_lines,
            'deleted_lines': deleted_lines
        }
    
    def _query_graphql(
        self, 
        query: str, 
        variables: Dict[str, Any],
        retries: int = 5
    ) -> Optional[Dict[str, Any]]:
        """Execute GraphQL query with retry logic"""
        # Extract repo name from variables for better logging
        repo_info = ""
        if 'name' in variables:
            repo_info = f" (repo: {variables['name']})"
        
        for attempt in range(1, retries + 1):
            try:
                response = requests.post(
                    self.GRAPHQL_ENDPOINT,
                    json={'query': query, 'variables': variables},
                    headers={
                        'Authorization': f'Bearer {self.token}',
                        'Content-Type': 'application/json'
                    },
                    timeout=30
                )
                
                if not response.ok:
                    status = response.status_code
                    
                    # Retry on server errors
                    if status in [502, 503, 504] and attempt < retries:
                        wait_time = min(2 ** (attempt - 1) * 2, 30)
                        print(f"\n         ⚠️  GitHub API {status} error{repo_info} (attempt {attempt}/{retries}). Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    
                    # Final failure - include repo info
                    error_msg = f"GitHub API HTTP Error ({status}){repo_info}: {response.text[:200]}"
                    raise Exception(error_msg)
                
                result = response.json()
                
                if 'errors' in result:
                    print(f"\n         ⚠️  GraphQL errors{repo_info}: {result['errors']}")
                
                return result.get('data')
                
            except requests.exceptions.RequestException as e:
                if attempt < retries:
                    wait_time = min(2 ** (attempt - 1) * 2, 30)
                    print(f"\n         ⚠️  Network error{repo_info} (attempt {attempt}/{retries}). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                raise
        
        raise Exception(f"GraphQL query{repo_info}: Maximum retries exceeded")
    
    def _get_members(self) -> List[Dict[str, Any]]:
        """Get organization members from config or API"""
        if self.member_list:
            # Use predefined member list
            members = []
            for member in self.member_list:
                members.append({
                    'login': member.get('githubId') or member.get('github_id'),
                    'github_id': member.get('githubId') or member.get('github_id'),
                    'name': member.get('name'),
                    'email': member.get('email')
                })
            return members
        
        # Otherwise fetch from GitHub API
        query = '''
            query getOrgMembers($orgName: String!, $cursor: String) {
                organization(login: $orgName) {
                    membersWithRole(first: 100, after: $cursor) {
                        nodes {
                            login
                            id
                            name
                            email
                        }
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                    }
                }
            }
        '''
        
        all_members = []
        has_next_page = True
        cursor = None
        
        while has_next_page:
            result = self._query_graphql(query, {'orgName': self.org_name, 'cursor': cursor})
            
            if not result or 'organization' not in result:
                break
            
            members_data = result['organization']['membersWithRole']
            all_members.extend(members_data['nodes'])
            
            has_next_page = members_data['pageInfo']['hasNextPage']
            cursor = members_data['pageInfo']['endCursor']
        
        return all_members
    
    def _get_repositories(self) -> List[Dict[str, Any]]:
        """Get organization repositories"""
        query = '''
            query getOrgRepos($orgName: String!, $cursor: String) {
                organization(login: $orgName) {
                    repositories(first: 100, after: $cursor, orderBy: {field: PUSHED_AT, direction: DESC}) {
                        nodes {
                            name
                            id
                            url
                            description
                            isArchived
                            pushedAt
                            createdAt
                        }
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                    }
                }
            }
        '''
        
        all_repos = []
        has_next_page = True
        cursor = None
        
        while has_next_page:
            result = self._query_graphql(query, {'orgName': self.org_name, 'cursor': cursor})
            
            if not result or 'organization' not in result:
                break
            
            repos_data = result['organization']['repositories']
            all_repos.extend(repos_data['nodes'])
            
            has_next_page = repos_data['pageInfo']['hasNextPage']
            cursor = repos_data['pageInfo']['endCursor']
        
        return all_repos
    
    def _get_pull_requests(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get pull requests within date range"""
        start_iso = start_date.strftime('%Y-%m-%d')
        end_iso = end_date.strftime('%Y-%m-%d')
        search_query = f"org:{self.org_name} is:pr created:{start_iso}..{end_iso}"
        
        query = '''
            query getOrgPRs($searchQuery: String!, $cursor: String) {
                search(query: $searchQuery, type: ISSUE, first: 100, after: $cursor) {
                    nodes {
                        ... on PullRequest {
                            number
                            title
                            url
                            state
                            createdAt
                            mergedAt
                            closedAt
                            additions
                            deletions
                            author {
                                login
                            }
                            repository {
                                name
                            }
                        }
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
            }
        '''
        
        all_prs = []
        has_next_page = True
        cursor = None
        
        while has_next_page:
            result = self._query_graphql(query, {'searchQuery': search_query, 'cursor': cursor})
            
            if not result or 'search' not in result:
                break
            
            prs = [
                {
                    'number': node['number'],
                    'title': node['title'],
                    'url': node['url'],
                    'state': node['state'],
                    'created_at': node['createdAt'],
                    'merged_at': node.get('mergedAt'),
                    'closed_at': node.get('closedAt'),
                    'author_login': node['author']['login'] if node.get('author') else 'unknown',
                    'repository_name': node['repository']['name'],
                    'additions': node.get('additions', 0),
                    'deletions': node.get('deletions', 0)
                }
                for node in result['search']['nodes']
            ]
            
            all_prs.extend(prs)
            
            has_next_page = result['search']['pageInfo']['hasNextPage']
            cursor = result['search']['pageInfo']['endCursor']
        
        return all_prs
    
    def _get_issues(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get issues within date range"""
        start_iso = start_date.strftime('%Y-%m-%d')
        end_iso = end_date.strftime('%Y-%m-%d')
        search_query = f"org:{self.org_name} is:issue created:{start_iso}..{end_iso}"
        
        query = '''
            query getOrgIssues($searchQuery: String!, $cursor: String) {
                search(query: $searchQuery, type: ISSUE, first: 100, after: $cursor) {
                    nodes {
                        ... on Issue {
                            number
                            title
                            url
                            state
                            createdAt
                            closedAt
                            author {
                                login
                            }
                            repository {
                                name
                            }
                        }
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
            }
        '''
        
        all_issues = []
        has_next_page = True
        cursor = None
        
        while has_next_page:
            result = self._query_graphql(query, {'searchQuery': search_query, 'cursor': cursor})
            
            if not result or 'search' not in result:
                break
            
            issues = [
                {
                    'number': node['number'],
                    'title': node['title'],
                    'url': node['url'],
                    'state': node['state'],
                    'created_at': node['createdAt'],
                    'closed_at': node.get('closedAt'),
                    'author_login': node['author']['login'] if node.get('author') else 'unknown',
                    'repository_name': node['repository']['name']
                }
                for node in result['search']['nodes']
            ]
            
            all_issues.extend(issues)
            
            has_next_page = result['search']['pageInfo']['hasNextPage']
            cursor = result['search']['pageInfo']['endCursor']
        
        return all_issues
    
    def _get_all_member_commits(
        self,
        members: List[Dict[str, Any]],
        repositories: List[Dict[str, Any]],
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get commits for all members"""
        # Filter to active repositories (pushed within collection date range)
        active_repos = [
            repo for repo in repositories
            if not repo.get('isArchived') and
            datetime.fromisoformat(repo['pushedAt'].replace('Z', '+00:00')) >= start_date
        ]
        
        print(f"   📊 Checking {len(active_repos)} active repositories (pushed during collection period)")
        
        all_commits = []
        
        for member in members:
            member_login = member.get('login')
            if not member_login:
                continue
            
            print(f"\n   👤 Collecting commits for {member_login}...")
            member_commits = self._get_member_commits(
                member_login,
                active_repos,
                start_date,
                end_date
            )
            
            if member_commits:
                all_commits.extend(member_commits)
                print(f"      ✅ Found {len(member_commits)} commits")
            
            # Rate limiting
            time.sleep(0.5)
        
        # Summary of problematic repos
        if self.problematic_repos:
            print(f"\n   ⚠️  Skipped {len(self.problematic_repos)} problematic repositories:")
            for repo in sorted(self.problematic_repos):
                print(f"      • {repo}")
        
        return all_commits
    
    def _get_member_commits(
        self,
        member_login: str,
        repositories: List[Dict[str, Any]],
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get commits for a specific member across all repositories"""
        all_commits = []
        
        for idx, repo in enumerate(repositories, 1):
            repo_name = repo['name']
            
            # Skip repos that already failed for other members
            if repo_name in self.problematic_repos:
                print(f"      ⏭️  Skipping {repo_name} (known issue)")
                continue
            
            try:
                print(f"      📂 [{idx}/{len(repositories)}] Checking {repo_name}...", end='', flush=True)
                
                repo_commits = self._get_repo_commits(
                    repo_name,
                    member_login,
                    start_date,
                    end_date
                )
                
                if repo_commits:
                    all_commits.extend(repo_commits)
                    print(f" ✅ {len(repo_commits)} commits")
                else:
                    print(f" - no commits")
                
                time.sleep(0.1)  # Rate limiting
                
            except Exception as e:
                print(f" ❌ Error")
                print(f"         ⚠️  Failed to fetch commits from {repo_name}: {e}")
                # Mark this repo as problematic to skip for other members
                self.problematic_repos.add(repo_name)
                continue
        
        return all_commits
    
    def _get_repo_commits(
        self,
        repo_name: str,
        member_login: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get commits from a repository for a specific member"""
        # Query branches with their latest commit date to filter by activity
        query = '''
            query RepoCommits($owner: String!, $name: String!, $sinceDate: GitTimestamp!, $cursor: String) {
                repository(owner: $owner, name: $name) {
                    refs(refPrefix: "refs/heads/", first: 50, after: $cursor) {
                        nodes {
                            name
                            target {
                                ... on Commit {
                                    committedDate
                                    history(first: 100, since: $sinceDate) {
                                        nodes {
                                            oid
                                            committedDate
                                            message
                                            url
                                            additions
                                            deletions
                                            changedFiles
                                            author {
                                                name
                                                email
                                                user {
                                                    login
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                    }
                }
            }
        '''
        
        all_commits = []
        has_next_page = True
        cursor = None
        branches_checked = 0
        branches_with_activity = 0
        max_branches_to_check = 50  # Limit to prevent timeout
        
        while has_next_page and branches_checked < max_branches_to_check:
            result = self._query_graphql(query, {
                'owner': self.org_name,
                'name': repo_name,
                'sinceDate': start_date.isoformat(),
                'cursor': cursor
            })
            
            if not result or 'repository' not in result or not result['repository']:
                break
            
            refs = result['repository'].get('refs')
            if not refs or not refs.get('nodes'):
                break
            
            # Filter branches by activity in date range
            for branch in refs['nodes']:
                branches_checked += 1
                
                if not branch.get('target'):
                    continue
                
                target = branch['target']
                
                # Check if branch has activity in our date range
                branch_last_commit_date_str = target.get('committedDate')
                if not branch_last_commit_date_str:
                    continue
                
                branch_last_commit_date = datetime.fromisoformat(
                    branch_last_commit_date_str.replace('Z', '+00:00')
                )
                
                # Skip branches with no activity since start_date
                if branch_last_commit_date < start_date:
                    continue
                
                branches_with_activity += 1
                
                # Process commits from this active branch
                if not target.get('history'):
                    continue
                
                commits = target['history']['nodes']
                
                # Filter by member and date range
                for commit in commits:
                    author_user = commit.get('author', {}).get('user')
                    if not author_user:
                        continue
                    
                    commit_login = author_user.get('login', '').lower()
                    commit_date = datetime.fromisoformat(commit['committedDate'].replace('Z', '+00:00'))
                    
                    if commit_login == member_login.lower() and start_date <= commit_date <= end_date:
                        commit_data = {
                            'sha': commit['oid'],
                            'message': commit['message'],
                            'url': commit['url'],
                            'committed_at': commit['committedDate'],
                            'author_login': member_login,
                            'repository_name': repo_name,
                            'additions': commit.get('additions', 0),
                            'deletions': commit.get('deletions', 0),
                            'changed_files': commit.get('changedFiles', 0),
                            'branch': branch['name']
                        }
                        
                        # Fetch detailed file changes if requested
                        if self.include_diff:
                            commit_data['files'] = self._get_commit_files(repo_name, commit['oid'])
                        
                        all_commits.append(commit_data)
            
            has_next_page = refs['pageInfo']['hasNextPage']
            cursor = refs['pageInfo']['endCursor']
        
        return all_commits
    
    def _get_commit_files(self, repo_name: str, commit_sha: str, retries: int = 5) -> List[Dict[str, Any]]:
        """Fetch detailed commit file changes via REST API"""
        url = f"{self.REST_API_BASE}/repos/{self.org_name}/{repo_name}/commits/{commit_sha}"
        
        for attempt in range(1, retries + 1):
            try:
                response = self.session.get(url, timeout=30)
                
                if not response.ok:
                    if response.status_code in [502, 503, 504] and attempt < retries:
                        wait_time = min(2 ** (attempt - 1), 15)
                        time.sleep(wait_time)
                        continue
                    return []
                
                data = response.json()
                files = data.get('files', [])
                
                return [
                    {
                        'filename': f['filename'],
                        'additions': f.get('additions', 0),
                        'deletions': f.get('deletions', 0),
                        'changes': f.get('changes', 0),
                        'status': f.get('status'),
                        'patch': f.get('patch')  # The actual diff
                    }
                    for f in files
                ]
                
            except Exception as e:
                if attempt == retries:
                    print(f"         ⚠️  Failed to fetch files for commit {commit_sha[:7]}: {e}")
                    return []
                time.sleep(2 ** (attempt - 1))
        
        return []

