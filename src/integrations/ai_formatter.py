"""
AI Prompt Formatter

Formats member activity data into structured prompts for AI analysis.
Supports multiple AI providers and analysis types.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json


class AIPromptFormatter:
    """
    Format member activity data for AI analysis
    
    Converts raw activity data into well-structured prompts
    suitable for performance analysis by AI models.
    """
    
    def __init__(self, template_type: str = 'performance_review'):
        """
        Initialize formatter
        
        Args:
            template_type: Type of analysis template to use
                          ('performance_review', 'team_summary', 'technical_depth')
        """
        self.template_type = template_type
    
    def format_member_performance(
        self,
        member_data: Dict[str, Any],
        include_details: bool = False
    ) -> str:
        """
        Format member performance data for AI analysis
        
        Args:
            member_data: Member activity data from QueryEngine
            include_details: Whether to include detailed commit/PR lists
            
        Returns:
            Formatted prompt string
        """
        if 'error' in member_data:
            return f"Error: {member_data['error']}"
        
        member_name = member_data.get('member_name', 'Unknown')
        github_id = member_data.get('github_id', 'Unknown')
        period = member_data.get('period', {})
        stats = member_data.get('statistics', {})
        
        prompt = f"""# Team Member Performance Analysis

## Basic Information
- **Name**: {member_name}
- **GitHub ID**: {github_id}
- **Analysis Period**: {self._format_period(period)}

## GitHub Activity Summary

### Code Contributions
{self._format_commit_stats(stats.get('commits', {}))}

### Pull Requests
{self._format_pr_stats(stats.get('pull_requests', {}))}

### Issues
{self._format_issue_stats(stats.get('issues', {}))}

### File Activity
{self._format_file_stats(stats.get('files', {}))}

## Repository Contributions
{self._format_top_repositories(member_data.get('top_repositories', []))}

## Most Modified Files
{self._format_top_files(member_data.get('top_files', []))}
"""
        
        if include_details:
            prompt += f"""
## Detailed Activity Log

### Recent Commits (Top 10)
{self._format_commit_details(member_data.get('commits', [])[:10])}

### Recent Pull Requests
{self._format_pr_details(member_data.get('pull_requests', []))}

### Recent Issues
{self._format_issue_details(member_data.get('issues', []))}
"""
        
        prompt += """
## Analysis Request

Based on the above data, please provide:

1. **Overall Activity Assessment**
   - Evaluate the developer's overall activity level and engagement
   - Compare against typical productivity metrics for the role

2. **Strengths Identified**
   - What areas show strong performance?
   - What positive patterns emerge from the data?

3. **Areas for Improvement**
   - Are there any concerning patterns or gaps?
   - What aspects could be enhanced?

4. **Work Style Analysis**
   - Commit frequency and patterns
   - Code review participation
   - Issue resolution approach

5. **Recommendations**
   - Specific actionable suggestions for improvement
   - Team collaboration opportunities
   - Technical growth areas

Please provide a balanced, constructive analysis suitable for performance review discussions.
"""
        
        return prompt.strip()
    
    def format_team_summary(
        self,
        team_data: List[Dict[str, Any]],
        period: Dict[str, Any]
    ) -> str:
        """
        Format team-wide summary for AI analysis
        
        Args:
            team_data: List of member activity summaries
            period: Time period for the summary
            
        Returns:
            Formatted team summary prompt
        """
        prompt = f"""# Team Performance Summary

## Analysis Period
{self._format_period(period)}

## Team Overview
- **Total Members Analyzed**: {len(team_data)}

## Individual Member Statistics

"""
        
        for i, member in enumerate(team_data, 1):
            stats = member.get('statistics', {})
            commits = stats.get('commits', {})
            prs = stats.get('pull_requests', {})
            issues = stats.get('issues', {})
            
            prompt += f"""### {i}. {member.get('member_name', 'Unknown')}
- **GitHub ID**: {member.get('github_id', 'N/A')}
- **Commits**: {commits.get('total', 0)} (+{commits.get('additions', 0)} -{commits.get('deletions', 0)} lines)
- **Pull Requests**: {prs.get('total', 0)} (Merged: {prs.get('merged', 0)})
- **Issues**: {issues.get('total', 0)} (Closed: {issues.get('closed', 0)})
- **Top Repositories**: {', '.join([r['repository'] for r in member.get('top_repositories', [])[:3]])}

"""
        
        # Calculate team totals
        total_commits = sum(m.get('statistics', {}).get('commits', {}).get('total', 0) for m in team_data)
        total_additions = sum(m.get('statistics', {}).get('commits', {}).get('additions', 0) for m in team_data)
        total_deletions = sum(m.get('statistics', {}).get('commits', {}).get('deletions', 0) for m in team_data)
        total_prs = sum(m.get('statistics', {}).get('pull_requests', {}).get('total', 0) for m in team_data)
        
        prompt += f"""## Team Totals
- **Total Commits**: {total_commits}
- **Total Code Changes**: +{total_additions} -{total_deletions} lines
- **Total Pull Requests**: {total_prs}

## Analysis Request

Please provide:

1. **Team Health Assessment**
   - Overall team productivity and engagement level
   - Distribution of work across team members

2. **Collaboration Patterns**
   - How well is the team collaborating?
   - Are there any isolated contributors?

3. **Workload Balance**
   - Is work distributed fairly?
   - Are there any bottlenecks or concerns?

4. **Team Recommendations**
   - Suggestions for improving team dynamics
   - Areas where the team excels
   - Opportunities for knowledge sharing
"""
        
        return prompt.strip()
    
    def format_technical_depth_analysis(
        self,
        member_data: Dict[str, Any]
    ) -> str:
        """
        Format data for technical depth analysis
        
        Args:
            member_data: Member activity data from QueryEngine
            
        Returns:
            Formatted prompt focused on technical contributions
        """
        if 'error' in member_data:
            return f"Error: {member_data['error']}"
        
        member_name = member_data.get('member_name', 'Unknown')
        stats = member_data.get('statistics', {})
        top_files = member_data.get('top_files', [])
        top_repos = member_data.get('top_repositories', [])
        
        prompt = f"""# Technical Depth Analysis: {member_name}

## Code Contribution Patterns

### Volume Metrics
- **Total Commits**: {stats.get('commits', {}).get('total', 0)}
- **Lines Added**: +{stats.get('commits', {}).get('additions', 0)}
- **Lines Deleted**: -{stats.get('commits', {}).get('deletions', 0)}
- **Net Code Growth**: {stats.get('commits', {}).get('net_lines', 0)} lines
- **Files Modified**: {stats.get('files', {}).get('unique_files', 0)} unique files

### Repository Focus
{self._format_top_repositories(top_repos)}

### File Modification Patterns
{self._format_top_files(top_files)}

## Analysis Focus

Based on the file modification patterns and repository contributions:

1. **Technical Breadth**
   - How diverse are the technical contributions?
   - Is the developer working across multiple codebases or focused on specific areas?

2. **Code Quality Indicators**
   - Ratio of additions to deletions (code cleanup vs. feature addition)
   - Frequency of modifications to same files (refactoring patterns)

3. **Technical Leadership**
   - Evidence of architectural work (many files changed per commit)
   - Code review and mentoring activities

4. **Specialization vs. Generalization**
   - Is this developer a specialist or generalist?
   - What technical areas do they focus on?

Please provide insights on the technical depth and impact of this developer's contributions.
"""
        
        return prompt.strip()
    
    def _format_period(self, period: Dict[str, Any]) -> str:
        """Format time period"""
        start = period.get('start', 'N/A')
        end = period.get('end', 'N/A')
        
        if start and start != 'N/A':
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            start = start_dt.strftime('%Y-%m-%d %H:%M KST')
        
        if end and end != 'N/A':
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            end = end_dt.strftime('%Y-%m-%d %H:%M KST')
        
        return f"{start} to {end}"
    
    def _format_commit_stats(self, commits: Dict[str, Any]) -> str:
        """Format commit statistics"""
        if not commits:
            return "- No commit data available"
        
        return f"""- **Total Commits**: {commits.get('total', 0)}
- **Lines Added**: +{commits.get('additions', 0):,}
- **Lines Deleted**: -{commits.get('deletions', 0):,}
- **Net Lines**: {commits.get('net_lines', 0):,}
- **Files Changed**: {commits.get('changed_files', 0)}"""
    
    def _format_pr_stats(self, prs: Dict[str, Any]) -> str:
        """Format pull request statistics"""
        if not prs:
            return "- No pull request data available"
        
        merge_rate = 0
        if prs.get('total', 0) > 0:
            merge_rate = (prs.get('merged', 0) / prs.get('total', 1)) * 100
        
        return f"""- **Total PRs**: {prs.get('total', 0)}
- **Merged**: {prs.get('merged', 0)} ({merge_rate:.1f}%)
- **Open**: {prs.get('open', 0)}
- **Closed**: {prs.get('closed', 0)}
- **Code Changes**: +{prs.get('additions', 0):,} -{prs.get('deletions', 0):,} lines"""
    
    def _format_issue_stats(self, issues: Dict[str, Any]) -> str:
        """Format issue statistics"""
        if not issues:
            return "- No issue data available"
        
        close_rate = 0
        if issues.get('total', 0) > 0:
            close_rate = (issues.get('closed', 0) / issues.get('total', 1)) * 100
        
        return f"""- **Total Issues**: {issues.get('total', 0)}
- **Closed**: {issues.get('closed', 0)} ({close_rate:.1f}%)
- **Open**: {issues.get('open', 0)}"""
    
    def _format_file_stats(self, files: Dict[str, Any]) -> str:
        """Format file modification statistics"""
        if not files:
            return "- No file data available"
        
        return f"""- **Total File Changes**: {files.get('total_modified', 0)}
- **Unique Files Modified**: {files.get('unique_files', 0)}"""
    
    def _format_top_repositories(self, repos: List[Dict[str, Any]]) -> str:
        """Format top repositories"""
        if not repos:
            return "- No repository data"
        
        lines = []
        for i, repo in enumerate(repos[:5], 1):
            lines.append(
                f"{i}. **{repo['repository']}**: "
                f"{repo['commits']} commits, {repo['pull_requests']} PRs"
            )
        
        return '\n'.join(lines)
    
    def _format_top_files(self, files: List[Dict[str, Any]]) -> str:
        """Format top modified files"""
        if not files:
            return "- No file modification data"
        
        lines = []
        for i, file in enumerate(files[:10], 1):
            lines.append(
                f"{i}. `{file['filename']}`: "
                f"{file['modifications']} changes "
                f"(+{file['additions']} -{file['deletions']})"
            )
        
        return '\n'.join(lines)
    
    def _format_commit_details(self, commits: List[Dict[str, Any]]) -> str:
        """Format detailed commit information"""
        if not commits:
            return "- No commits in period"
        
        lines = []
        for i, commit in enumerate(commits, 1):
            message = commit.get('message', '').split('\n')[0][:80]
            lines.append(
                f"{i}. [{commit['sha'][:7]}]({commit.get('url', '#')}) "
                f"{message}\n"
                f"   - Repository: {commit['repository_name']}\n"
                f"   - Changes: +{commit['additions']} -{commit['deletions']}\n"
                f"   - Date: {commit['committed_at']}"
            )
        
        return '\n\n'.join(lines)
    
    def _format_pr_details(self, prs: List[Dict[str, Any]]) -> str:
        """Format detailed pull request information"""
        if not prs:
            return "- No pull requests in period"
        
        lines = []
        for i, pr in enumerate(prs, 1):
            status = "✅ Merged" if pr.get('merged_at') else f"📌 {pr['state'].title()}"
            lines.append(
                f"{i}. [{pr['repository_name']}#{pr['number']}]({pr.get('url', '#')}) "
                f"{pr['title']}\n"
                f"   - Status: {status}\n"
                f"   - Changes: +{pr['additions']} -{pr['deletions']}\n"
                f"   - Created: {pr['created_at']}"
            )
        
        return '\n\n'.join(lines)
    
    def _format_issue_details(self, issues: List[Dict[str, Any]]) -> str:
        """Format detailed issue information"""
        if not issues:
            return "- No issues in period"
        
        lines = []
        for i, issue in enumerate(issues, 1):
            status = "✅ Closed" if issue.get('closed_at') else "📌 Open"
            lines.append(
                f"{i}. [{issue['repository_name']}#{issue['number']}]({issue.get('url', '#')}) "
                f"{issue['title']}\n"
                f"   - Status: {status}\n"
                f"   - Created: {issue['created_at']}"
            )
        
        return '\n\n'.join(lines)
    
    def export_as_json(self, member_data: Dict[str, Any]) -> str:
        """
        Export member data as JSON for programmatic use
        
        Args:
            member_data: Member activity data from QueryEngine
            
        Returns:
            JSON string
        """
        return json.dumps(member_data, indent=2, ensure_ascii=False)
    
    def export_as_markdown(self, member_data: Dict[str, Any]) -> str:
        """
        Export member data as Markdown report
        
        Args:
            member_data: Member activity data from QueryEngine
            
        Returns:
            Markdown formatted string
        """
        return self.format_member_performance(member_data, include_details=True)

