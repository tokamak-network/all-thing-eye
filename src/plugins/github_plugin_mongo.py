"""GitHub data source plugin - MongoDB version"""

import time
from typing import Dict, List, Any, Optional
from datetime import datetime
import requests
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from .base import DataSourcePlugin
from src.core.mongo_manager import MongoDBManager
from src.models.mongo_models import (
    GitHubCommit, 
    GitHubPullRequest, 
    GitHubIssue,
    GitHubFileChange,
    GitHubReview
)


class GitHubPluginMongo(DataSourcePlugin):
    """
    GitHub data collection plugin - MongoDB version
    
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
    
    def __init__(self, config: Dict[str, Any], mongo_manager: MongoDBManager):
        super().__init__(config)
        self.token = config.get('token')
        self.org_name = config.get('organization')
        self.include_diff = config.get('collection', {}).get('include_diff', False)
        self.rate_limit = config.get('rate_limit', 5000)
        self.member_list = config.get('member_list', [])
        
        # MongoDB Manager
        self.mongo = mongo_manager
        
        # Collections
        self.commits_col = self.mongo.get_collection('github_commits')
        self.prs_col = self.mongo.get_collection('github_pull_requests')
        self.issues_col = self.mongo.get_collection('github_issues')
        self.repos_col = self.mongo.get_collection('github_repositories')
        
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
        """
        MongoDB doesn't require schema definition.
        Return empty dict to satisfy base class interface.
        """
        return {}
    
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
            
            # Save repositories to MongoDB
            self._save_repositories(collected_data['repositories'])
            
            # 3. Get pull requests
            print("\n3️⃣ Fetching pull requests...")
            collected_data['pull_requests'] = self._get_pull_requests(start_date, end_date)
            print(f"   ✅ Found {len(collected_data['pull_requests'])} pull requests")
            
            # Save PRs to MongoDB
            saved_prs = self._save_pull_requests(collected_data['pull_requests'])
            print(f"   💾 Saved {saved_prs} pull requests to MongoDB")
            
            # 4. Get issues
            print("\n4️⃣ Fetching issues...")
            collected_data['issues'] = self._get_issues(start_date, end_date)
            print(f"   ✅ Found {len(collected_data['issues'])} issues")
            
            # Save issues to MongoDB
            saved_issues = self._save_issues(collected_data['issues'])
            print(f"   💾 Saved {saved_issues} issues to MongoDB")
            
            # 5. Get commits for each member
            print("\n5️⃣ Fetching commits...")
            collected_data['commits'] = self._get_all_member_commits(
                collected_data['members'],
                collected_data['repositories'],
                start_date,
                end_date
            )
            print(f"   ✅ Found {len(collected_data['commits'])} total commits")
            
            # Save commits to MongoDB
            saved_commits = self._save_commits(collected_data['commits'])
            print(f"   💾 Saved {saved_commits} commits to MongoDB")
            
            # 6. Sync project repositories from GitHub Teams
            print("\n6️⃣ Syncing project repositories from GitHub Teams...")
            synced_projects = self._sync_project_repositories()
            print(f"   ✅ Synced repositories for {synced_projects} projects")
            
            return [collected_data]
            
        except Exception as e:
            print(f"❌ Error collecting GitHub data: {e}")
            raise
    
    def _save_repositories(self, repositories: List[Dict[str, Any]]) -> int:
        """Save repositories to MongoDB"""
        if not repositories:
            return 0
        
        saved_count = 0
        for repo in repositories:
            try:
                self.repos_col.update_one(
                    {'name': repo['name']},
                    {
                        '$set': {
                            'github_id': repo.get('id'),
                            'url': repo.get('url'),
                            'description': repo.get('description'),
                            'is_archived': repo.get('isArchived', False),
                            'pushed_at': datetime.fromisoformat(repo['pushedAt'].replace('Z', '+00:00')) if repo.get('pushedAt') else None,
                            'created_at': datetime.fromisoformat(repo['createdAt'].replace('Z', '+00:00')) if repo.get('createdAt') else None,
                            'updated_at': datetime.utcnow()
                        }
                    },
                    upsert=True
                )
                saved_count += 1
            except Exception as e:
                print(f"      ⚠️  Error saving repository {repo.get('name')}: {e}")
        
        return saved_count
    
    def _sync_project_repositories(self) -> int:
        """
        Sync project repositories from GitHub Teams API to MongoDB projects collection
        
        This method:
        1. Fetches all active projects from MongoDB
        2. For each project, calls GitHub Teams API to get repositories
        3. Updates the project's repositories field in MongoDB
        
        Returns:
            Number of projects successfully synced
        """
        try:
            db = self.mongo.db
            projects_collection = db["projects"]
            
            # Get all active projects
            projects = list(projects_collection.find({"is_active": True}))
            
            if not projects:
                print("      ℹ️  No active projects found in MongoDB")
                return 0
            
            synced_count = 0
            github_token = self.token
            github_org = self.org_name
            
            if not github_token:
                print("      ⚠️  GITHUB_TOKEN not set, skipping repository sync")
                return 0
            
            for project in projects:
                project_key = project.get("key")
                github_team_slug = project.get("github_team_slug") or project_key
                
                if not project_key:
                    continue
                
                try:
                    # Fetch repositories from GitHub Teams API
                    repos = self._get_repositories_from_team(github_org, github_team_slug, github_token)
                    
                    if repos is None:
                        # Team doesn't exist or API error, skip
                        continue
                    
                    # Update project in MongoDB
                    now = datetime.utcnow()
                    projects_collection.update_one(
                        {"key": project_key},
                        {
                            "$set": {
                                "repositories": repos,
                                "repositories_synced_at": now,
                                "updated_at": now
                            }
                        }
                    )
                    
                    synced_count += 1
                    print(f"      ✅ {project_key}: {len(repos)} repositories")
                    
                except Exception as e:
                    print(f"      ⚠️  Error syncing {project_key}: {e}")
                    continue
            
            return synced_count
            
        except Exception as e:
            print(f"      ❌ Error syncing project repositories: {e}")
            return 0
    
    def _get_repositories_from_team(self, org: str, team_slug: str, token: str) -> Optional[List[str]]:
        """
        Get repositories for a GitHub team using Teams API
        
        Args:
            org: GitHub organization name
            team_slug: Team slug (e.g., "project-ooo")
            token: GitHub API token
        
        Returns:
            List of repository names (without org prefix), or None if error
        """
        try:
            url = f"https://api.github.com/orgs/{org}/teams/{team_slug}/repos"
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            repos = set()
            page = 1
            per_page = 100
            
            while True:
                params = {"page": page, "per_page": per_page}
                response = requests.get(url, headers=headers, params=params, timeout=10)
                
                if response.status_code == 404:
                    # Team doesn't exist
                    return None
                
                if response.status_code != 200:
                    # API error
                    return None
                
                data = response.json()
                if not data:
                    break
                
                # Extract repository names (remove org prefix)
                for repo in data:
                    full_name = repo.get("full_name", "")
                    if "/" in full_name:
                        repo_name = full_name.split("/", 1)[1]
                        repos.add(repo_name)
                
                # Check if there are more pages
                if len(data) < per_page:
                    break
                page += 1
            
            return sorted(list(repos))
            
        except Exception as e:
            print(f"      ⚠️  Error fetching repositories for team {team_slug}: {e}")
            return None
    
    def _save_commits(self, commits: List[Dict[str, Any]]) -> int:
        """Save commits to MongoDB"""
        if not commits:
            return 0
        
        saved_count = 0
        for commit_data in commits:
            try:
                # Prepare file changes if included
                files = []
                if 'files' in commit_data:
                    for f in commit_data['files']:
                        file_data = {
                            'filename': f.get('filename'),
                            'additions': f.get('additions', 0),
                            'deletions': f.get('deletions', 0),
                            'changes': f.get('changes', 0),
                            'status': f.get('status')
                        }
                        # Parse patch/diff if available
                        if 'patch' in f and f['patch']:
                            parsed = self._parse_patch(f['patch'])
                            file_data['added_lines'] = parsed['added_lines']
                            file_data['deleted_lines'] = parsed['deleted_lines']
                        files.append(file_data)
                
                # Insert or update commit
                self.commits_col.update_one(
                    {'sha': commit_data['sha']},
                    {
                        '$set': {
                            'repository': commit_data.get('repository_name'),  # Changed from repository_name
                            'author_name': commit_data.get('author_login'),  # Changed from author_login
                            'author_email': commit_data.get('author_email', ''),
                            'message': commit_data.get('message'),
                            'date': datetime.fromisoformat(commit_data['committed_at'].replace('Z', '+00:00')),  # Changed from committed_at
                            'additions': commit_data.get('additions', 0),
                            'deletions': commit_data.get('deletions', 0),
                            'total_changes': commit_data.get('additions', 0) + commit_data.get('deletions', 0),
                            'files': files,
                            'url': commit_data.get('url'),
                            'verified': True,
                            'collected_at': datetime.utcnow()
                        }
                    },
                    upsert=True
                )
                saved_count += 1
            except Exception as e:
                print(f"      ⚠️  Error saving commit {commit_data.get('sha', 'unknown')}: {e}")
        
        return saved_count
    
    def _save_pull_requests(self, prs: List[Dict[str, Any]]) -> int:
        """Save pull requests to MongoDB"""
        if not prs:
            return 0
        
        saved_count = 0
        for pr_data in prs:
            try:
                # Parse dates
                created_at = datetime.fromisoformat(pr_data['created_at'].replace('Z', '+00:00'))
                merged_at = datetime.fromisoformat(pr_data['merged_at'].replace('Z', '+00:00')) if pr_data.get('merged_at') else None
                closed_at = datetime.fromisoformat(pr_data['closed_at'].replace('Z', '+00:00')) if pr_data.get('closed_at') else None
                
                # Insert or update PR
                self.prs_col.update_one(
                    {
                        'repository': pr_data['repository_name'],  # Changed from repository_name
                        'number': pr_data['number']
                    },
                    {
                        '$set': {
                            'title': pr_data.get('title'),
                            'state': pr_data.get('state'),
                            'author': pr_data.get('author_login'),  # Changed from author_login
                            'created_at': created_at,
                            'updated_at': datetime.utcnow(),
                            'merged_at': merged_at,
                            'closed_at': closed_at,
                            'additions': pr_data.get('additions', 0),
                            'deletions': pr_data.get('deletions', 0),
                            'changed_files': 0,  # Not available in current data
                            'commits': 0,  # Not available in current data
                            'reviews': [],  # Would need additional API calls
                            'labels': [],  # Not available in current data
                            'assignees': [],  # Not available in current data
                            'url': pr_data.get('url'),
                            'collected_at': datetime.utcnow()
                        }
                    },
                    upsert=True
                )
                saved_count += 1
            except Exception as e:
                print(f"      ⚠️  Error saving PR #{pr_data.get('number')}: {e}")
        
        return saved_count
    
    def _save_issues(self, issues: List[Dict[str, Any]]) -> int:
        """Save issues to MongoDB"""
        if not issues:
            return 0
        
        saved_count = 0
        for issue_data in issues:
            try:
                # Parse dates
                created_at = datetime.fromisoformat(issue_data['created_at'].replace('Z', '+00:00'))
                closed_at = datetime.fromisoformat(issue_data['closed_at'].replace('Z', '+00:00')) if issue_data.get('closed_at') else None
                
                # Insert or update issue
                self.issues_col.update_one(
                    {
                        'repository': issue_data['repository_name'],  # Changed from repository_name
                        'number': issue_data['number']
                    },
                    {
                        '$set': {
                            'title': issue_data.get('title'),
                            'state': issue_data.get('state'),
                            'author': issue_data.get('author_login'),  # Changed from author_login
                            'created_at': created_at,
                            'updated_at': datetime.utcnow(),
                            'closed_at': closed_at,
                            'labels': [],  # Not available in current data
                            'assignees': [],  # Not available in current data
                            'url': issue_data.get('url'),
                            'collected_at': datetime.utcnow()
                        }
                    },
                    upsert=True
                )
                saved_count += 1
            except Exception as e:
                print(f"      ⚠️  Error saving issue #{issue_data.get('number')}: {e}")
        
        return saved_count
    
    def get_member_mapping(self) -> Dict[str, str]:
        """
        Map GitHub usernames to member names
        
        Returns:
            Dict of {github_login: member_name}
            Uses the 'name' field from members.yaml as the primary identifier
        """
        mapping = {}
        
        for member in self.member_list:
            github_id = member.get('githubId') or member.get('github_id')
            name = member.get('name')
            email = member.get('email')
            
            if github_id and name:
                # Use name as primary identifier (e.g., 'Ale', 'Kevin')
                # This matches the 'name' column in members collection
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
    # (Same as original GitHub plugin - no database interaction here)
    
    def _query_graphql(
        self, 
        query: str, 
        variables: Dict[str, Any],
        retries: int = 5
    ) -> Optional[Dict[str, Any]]:
        """Execute GraphQL query with retry logic"""
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
                    
                    if status in [502, 503, 504] and attempt < retries:
                        wait_time = min(2 ** (attempt - 1) * 2, 30)
                        print(f"\n         ⚠️  GitHub API {status} error{repo_info} (attempt {attempt}/{retries}). Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    
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
        # Ensure start_date has timezone info for comparison
        from datetime import timezone
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        
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
            
            time.sleep(0.5)
        
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
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f" ❌ Error")
                print(f"         ⚠️  Failed to fetch commits from {repo_name}: {e}")
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
        query = '''
            query RepoCommits($owner: String!, $name: String!, $sinceDate: GitTimestamp!, $cursor: String) {
                repository(owner: $owner, name: $name) {
                    refs(refPrefix: "refs/heads/", first: 100, after: $cursor, orderBy: {field: TAG_COMMIT_DATE, direction: DESC}) {
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
        max_branches_to_check = 500  # Increased limit to collect more branches
        
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
            
            for branch in refs['nodes']:
                branches_checked += 1
                
                if not branch.get('target'):
                    continue
                
                target = branch['target']
                
                branch_last_commit_date_str = target.get('committedDate')
                if not branch_last_commit_date_str:
                    continue
                
                branch_last_commit_date = datetime.fromisoformat(
                    branch_last_commit_date_str.replace('Z', '+00:00')
                )
                
                # Don't skip branches based on last commit date - check all branches
                # The history query already filters by sinceDate, so we don't need this check
                # This ensures we don't miss branches that had recent activity but older last commit
                # However, we can still use it as an optimization hint
                # Only skip if the branch is clearly inactive (last commit is way before start_date)
                # But allow branches that might have activity in the range
                
                if not target.get('history'):
                    continue
                
                commits = target['history']['nodes']
                
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
                        'patch': f.get('patch')
                    }
                    for f in files
                ]
                
            except Exception as e:
                if attempt == retries:
                    print(f"         ⚠️  Failed to fetch files for commit {commit_sha[:7]}: {e}")
                    return []
                time.sleep(2 ** (attempt - 1))
        
        return []
    
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

