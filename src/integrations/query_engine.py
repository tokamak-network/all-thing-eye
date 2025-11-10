"""
Query Engine for Member Activity Aggregation

This module provides unified querying capabilities across all data sources,
focusing on member-centric activity aggregation.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from sqlalchemy import text
from src.core.database import DatabaseManager
from src.core.member_index import MemberIndex


class QueryEngine:
    """
    Unified query engine for member activity data
    
    Aggregates data from multiple sources and provides
    member-centric views of activities.
    """
    
    def __init__(self, db_manager: DatabaseManager, member_index: MemberIndex):
        """
        Initialize query engine
        
        Args:
            db_manager: Database manager instance
            member_index: Member index instance
        """
        self.db = db_manager
        self.member_index = member_index
    
    def get_member_github_activities(
        self,
        member_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get GitHub activities for a specific member
        
        Args:
            member_name: Name of the member
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)
            
        Returns:
            Dict containing aggregated GitHub activities
        """
        # Get member's GitHub ID
        member = self.member_index.get_member_by_name(member_name)
        if not member:
            return {
                'error': f'Member {member_name} not found',
                'member_name': member_name
            }
        
        github_id = self.member_index.get_member_identifier(member['id'], 'github')
        if not github_id:
            return {
                'error': f'No GitHub ID found for {member_name}',
                'member_name': member_name
            }
        
        # Build date filter
        date_filter = ""
        params = {'github_id': github_id}
        
        if start_date:
            date_filter += " AND committed_at >= :start_date"
            params['start_date'] = start_date.isoformat()
        
        if end_date:
            date_filter += " AND committed_at <= :end_date"
            params['end_date'] = end_date.isoformat()
        
        # Query commits
        commits = self._query_github_commits(github_id, date_filter, params)
        
        # Query pull requests
        pull_requests = self._query_github_prs(github_id, date_filter, params)
        
        # Query issues
        issues = self._query_github_issues(github_id, date_filter, params)
        
        # Get commit file details
        commit_files = self._query_github_commit_files(commits)
        
        # Calculate statistics
        stats = self._calculate_github_stats(commits, pull_requests, issues, commit_files)
        
        return {
            'member_name': member_name,
            'github_id': github_id,
            'period': {
                'start': start_date.isoformat() if start_date else None,
                'end': end_date.isoformat() if end_date else None
            },
            'statistics': stats,
            'commits': commits,
            'pull_requests': pull_requests,
            'issues': issues,
            'top_repositories': self._get_top_repositories(commits, pull_requests),
            'top_files': self._get_top_modified_files(commit_files)
        }
    
    def _query_github_commits(
        self,
        github_id: str,
        date_filter: str,
        params: Dict
    ) -> List[Dict[str, Any]]:
        """Query GitHub commits for a member"""
        query = text(f"""
            SELECT 
                sha,
                message,
                url,
                committed_at,
                repository_name,
                branch,
                additions,
                deletions,
                changed_files
            FROM github_commits
            WHERE author_login = :github_id
            {date_filter}
            ORDER BY committed_at DESC
        """)
        
        with self.db.get_connection('github') as conn:
            result = conn.execute(query, params)
            commits = []
            for row in result:
                commits.append({
                    'sha': row[0],
                    'message': row[1],
                    'url': row[2],
                    'committed_at': row[3],
                    'repository_name': row[4],
                    'branch': row[5],
                    'additions': row[6] or 0,
                    'deletions': row[7] or 0,
                    'changed_files': row[8] or 0
                })
            return commits
    
    def _query_github_prs(
        self,
        github_id: str,
        date_filter: str,
        params: Dict
    ) -> List[Dict[str, Any]]:
        """Query GitHub pull requests for a member"""
        # Adjust date filter for PR field names
        pr_date_filter = date_filter.replace('committed_at', 'created_at')
        
        query = text(f"""
            SELECT 
                number,
                title,
                url,
                state,
                created_at,
                merged_at,
                closed_at,
                repository_name,
                additions,
                deletions
            FROM github_pull_requests
            WHERE author_login = :github_id
            {pr_date_filter}
            ORDER BY created_at DESC
        """)
        
        with self.db.get_connection('github') as conn:
            result = conn.execute(query, params)
            prs = []
            for row in result:
                prs.append({
                    'number': row[0],
                    'title': row[1],
                    'url': row[2],
                    'state': row[3],
                    'created_at': row[4],
                    'merged_at': row[5],
                    'closed_at': row[6],
                    'repository_name': row[7],
                    'additions': row[8] or 0,
                    'deletions': row[9] or 0
                })
            return prs
    
    def _query_github_issues(
        self,
        github_id: str,
        date_filter: str,
        params: Dict
    ) -> List[Dict[str, Any]]:
        """Query GitHub issues for a member"""
        # Adjust date filter for issue field names
        issue_date_filter = date_filter.replace('committed_at', 'created_at')
        
        query = text(f"""
            SELECT 
                number,
                title,
                url,
                state,
                created_at,
                closed_at,
                repository_name
            FROM github_issues
            WHERE author_login = :github_id
            {issue_date_filter}
            ORDER BY created_at DESC
        """)
        
        with self.db.get_connection('github') as conn:
            result = conn.execute(query, params)
            issues = []
            for row in result:
                issues.append({
                    'number': row[0],
                    'title': row[1],
                    'url': row[2],
                    'state': row[3],
                    'created_at': row[4],
                    'closed_at': row[5],
                    'repository_name': row[6]
                })
            return issues
    
    def _query_github_commit_files(
        self,
        commits: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Query file changes for commits"""
        if not commits:
            return []
        
        commit_shas = [c['sha'] for c in commits]
        placeholders = ','.join([f':sha{i}' for i in range(len(commit_shas))])
        params = {f'sha{i}': sha for i, sha in enumerate(commit_shas)}
        
        query = text(f"""
            SELECT 
                commit_sha,
                filename,
                additions,
                deletions,
                changes,
                status
            FROM github_commit_files
            WHERE commit_sha IN ({placeholders})
        """)
        
        with self.db.get_connection('github') as conn:
            result = conn.execute(query, params)
            files = []
            for row in result:
                files.append({
                    'commit_sha': row[0],
                    'filename': row[1],
                    'additions': row[2] or 0,
                    'deletions': row[3] or 0,
                    'changes': row[4] or 0,
                    'status': row[5]
                })
            return files
    
    def _calculate_github_stats(
        self,
        commits: List[Dict],
        pull_requests: List[Dict],
        issues: List[Dict],
        commit_files: List[Dict]
    ) -> Dict[str, Any]:
        """Calculate aggregate statistics"""
        total_additions = sum(c['additions'] for c in commits)
        total_deletions = sum(c['deletions'] for c in commits)
        total_changed_files = sum(c['changed_files'] for c in commits)
        
        pr_additions = sum(pr['additions'] for pr in pull_requests)
        pr_deletions = sum(pr['deletions'] for pr in pull_requests)
        
        merged_prs = len([pr for pr in pull_requests if pr['merged_at']])
        closed_issues = len([issue for issue in issues if issue['closed_at']])
        
        return {
            'commits': {
                'total': len(commits),
                'additions': total_additions,
                'deletions': total_deletions,
                'changed_files': total_changed_files,
                'net_lines': total_additions - total_deletions
            },
            'pull_requests': {
                'total': len(pull_requests),
                'merged': merged_prs,
                'open': len([pr for pr in pull_requests if pr['state'] == 'open']),
                'closed': len([pr for pr in pull_requests if pr['state'] == 'closed']),
                'additions': pr_additions,
                'deletions': pr_deletions
            },
            'issues': {
                'total': len(issues),
                'closed': closed_issues,
                'open': len([issue for issue in issues if issue['state'] == 'open'])
            },
            'files': {
                'total_modified': len(commit_files),
                'unique_files': len(set(f['filename'] for f in commit_files))
            }
        }
    
    def _get_top_repositories(
        self,
        commits: List[Dict],
        pull_requests: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Get top repositories by activity"""
        repo_stats = {}
        
        # Count commits per repo
        for commit in commits:
            repo = commit['repository_name']
            if repo not in repo_stats:
                repo_stats[repo] = {'commits': 0, 'prs': 0}
            repo_stats[repo]['commits'] += 1
        
        # Count PRs per repo
        for pr in pull_requests:
            repo = pr['repository_name']
            if repo not in repo_stats:
                repo_stats[repo] = {'commits': 0, 'prs': 0}
            repo_stats[repo]['prs'] += 1
        
        # Sort by total activity
        sorted_repos = sorted(
            repo_stats.items(),
            key=lambda x: x[1]['commits'] + x[1]['prs'],
            reverse=True
        )
        
        return [
            {
                'repository': repo,
                'commits': stats['commits'],
                'pull_requests': stats['prs'],
                'total_activity': stats['commits'] + stats['prs']
            }
            for repo, stats in sorted_repos[:10]
        ]
    
    def _get_top_modified_files(
        self,
        commit_files: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Get most frequently modified files"""
        file_stats = {}
        
        for file in commit_files:
            filename = file['filename']
            if filename not in file_stats:
                file_stats[filename] = {
                    'modifications': 0,
                    'additions': 0,
                    'deletions': 0
                }
            
            file_stats[filename]['modifications'] += 1
            file_stats[filename]['additions'] += file['additions']
            file_stats[filename]['deletions'] += file['deletions']
        
        # Sort by modification count
        sorted_files = sorted(
            file_stats.items(),
            key=lambda x: x[1]['modifications'],
            reverse=True
        )
        
        return [
            {
                'filename': filename,
                'modifications': stats['modifications'],
                'additions': stats['additions'],
                'deletions': stats['deletions'],
                'net_changes': stats['additions'] - stats['deletions']
            }
            for filename, stats in sorted_files[:20]
        ]
    
    def get_all_members_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get activity summary for all members
        
        Args:
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)
            
        Returns:
            List of member activity summaries
        """
        members = self.member_index.get_all_members()
        summaries = []
        
        for member in members:
            activities = self.get_member_github_activities(
                member['name'],
                start_date,
                end_date
            )
            
            if 'error' not in activities:
                summaries.append({
                    'member_name': member['name'],
                    'github_id': activities.get('github_id'),
                    'statistics': activities.get('statistics', {}),
                    'top_repositories': activities.get('top_repositories', [])[:3]
                })
        
        # Sort by commit count
        summaries.sort(
            key=lambda x: x.get('statistics', {}).get('commits', {}).get('total', 0),
            reverse=True
        )
        
        return summaries

