"""
Project-based report generation utilities.

This module provides functions to generate team activity reports
following the guidelines in docs/REPORT_GUIDELINES.md
"""

from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy import text
import pytz
from src.core.database import DatabaseManager
from src.core.config import Config
from src.utils.date_helpers import get_week_info


class ProjectReportGenerator:
    """Generate activity reports for specific projects."""
    
    def __init__(self, db_manager: DatabaseManager, config: Config):
        """
        Initialize report generator.
        
        Args:
            db_manager: Database manager instance
            config: Configuration instance
        """
        self.db = db_manager
        self.config = config
        self.kst = pytz.timezone('Asia/Seoul')
    
    def get_project_config(self, project_key: str) -> Dict[str, Any]:
        """
        Get project configuration.
        
        Args:
            project_key: Project identifier (e.g., 'project-ooo')
            
        Returns:
            Project configuration dictionary
            
        Raises:
            ValueError: If project not found
        """
        projects = self.config.get('projects', {})
        if project_key not in projects:
            raise ValueError(f"Project '{project_key}' not found in configuration")
        
        return projects[project_key]
    
    def get_active_members(
        self,
        project_key: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        Get members active in project's Slack channel during period.
        
        Args:
            project_key: Project identifier
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            List of member dictionaries with name, email, id
        """
        project_config = self.get_project_config(project_key)
        channel_id = project_config.get('slack_channel_id')
        
        if not channel_id or channel_id == 'TBD':
            raise ValueError(
                f"Slack channel ID not configured for {project_key}. "
                f"Please update config/config.yaml"
            )
        
        query = text("""
            SELECT DISTINCT 
                m.id,
                m.name,
                m.email
            FROM members m
            JOIN member_activities ma ON m.id = ma.member_id
            WHERE ma.source_type = 'slack'
              AND (ma.activity_type = 'message' OR ma.activity_type = 'reaction')
              AND json_extract(ma.metadata, '$.channel_id') = :channel_id
              AND date(ma.timestamp) >= :start_date
              AND date(ma.timestamp) <= :end_date
            ORDER BY m.name
        """)
        
        result = self.db.execute_query(query, {
            'channel_id': channel_id,
            'start_date': start_date,
            'end_date': end_date
        })
        
        return [dict(row) for row in result]
    
    def get_github_stats(
        self,
        member_names: List[str],
        repositories: List[str],
        start_date: str,
        end_date: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get GitHub statistics for members, filtered by repositories.
        
        Args:
            member_names: List of member names to include
            repositories: List of repository names to filter
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Dictionary mapping member names to their GitHub stats
        """
        if not member_names:
            return {}
        
        # Build repository filter clause
        repo_placeholders = ', '.join([f':repo{i}' for i in range(len(repositories))])
        repo_filter = f"AND json_extract(ma.metadata, '$.repository') IN ({repo_placeholders})" if repositories else ""
        
        query = text(f"""
            SELECT 
                m.name,
                SUM(CASE WHEN ma.activity_type = 'github_commit' THEN 1 ELSE 0 END) as commits,
                SUM(CASE WHEN ma.activity_type = 'github_pull_request' THEN 1 ELSE 0 END) as prs,
                SUM(CASE WHEN ma.activity_type = 'github_issue' THEN 1 ELSE 0 END) as issues,
                SUM(CASE WHEN ma.activity_type = 'github_commit' 
                    THEN COALESCE(json_extract(ma.metadata, '$.additions'), 0) 
                    ELSE 0 END) as additions,
                SUM(CASE WHEN ma.activity_type = 'github_commit' 
                    THEN COALESCE(json_extract(ma.metadata, '$.deletions'), 0) 
                    ELSE 0 END) as deletions
            FROM members m
            JOIN member_activities ma ON m.id = ma.member_id
            WHERE ma.source_type = 'github'
              AND m.name IN ({','.join([f':name{i}' for i in range(len(member_names))])})
              {repo_filter}
              AND date(ma.timestamp) >= :start_date
              AND date(ma.timestamp) <= :end_date
            GROUP BY m.name
        """)
        
        params = {
            'start_date': start_date,
            'end_date': end_date
        }
        
        # Add member names to params
        for i, name in enumerate(member_names):
            params[f'name{i}'] = name
        
        # Add repositories to params
        for i, repo in enumerate(repositories):
            params[f'repo{i}'] = repo
        
        result = self.db.execute_query(query, params)
        
        return {
            row['name']: {
                'commits': row['commits'] or 0,
                'prs': row['prs'] or 0,
                'issues': row['issues'] or 0,
                'additions': row['additions'] or 0,
                'deletions': row['deletions'] or 0
            }
            for row in result
        }
    
    def get_slack_stats(
        self,
        member_names: List[str],
        channel_id: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get Slack statistics for members in specific channel.
        
        Args:
            member_names: List of member names to include
            channel_id: Slack channel ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Dictionary mapping member names to their Slack stats
        """
        if not member_names:
            return {}
        
        query = text(f"""
            SELECT 
                m.name,
                SUM(CASE WHEN ma.activity_type = 'message' THEN 1 ELSE 0 END) as messages,
                SUM(CASE WHEN ma.activity_type = 'reaction' THEN 1 ELSE 0 END) as reactions
            FROM members m
            JOIN member_activities ma ON m.id = ma.member_id
            WHERE ma.source_type = 'slack'
              AND json_extract(ma.metadata, '$.channel_id') = :channel_id
              AND m.name IN ({','.join([f':name{i}' for i in range(len(member_names))])})
              AND date(ma.timestamp) >= :start_date
              AND date(ma.timestamp) <= :end_date
            GROUP BY m.name
        """)
        
        params = {
            'channel_id': channel_id,
            'start_date': start_date,
            'end_date': end_date
        }
        
        for i, name in enumerate(member_names):
            params[f'name{i}'] = name
        
        result = self.db.execute_query(query, params)
        
        return {
            row['name']: {
                'messages': row['messages'] or 0,
                'reactions': row['reactions'] or 0
            }
            for row in result
        }
    
    def calculate_contribution_score(
        self,
        github_stats: Dict[str, Any],
        slack_stats: Dict[str, Any]
    ) -> float:
        """
        Calculate weighted contribution score based on guidelines.
        
        Weights (from REPORT_GUIDELINES.md):
        - GitHub Commit: 1.0x
        - GitHub PR: 2.0x
        - GitHub Issue: 0.5x
        - Slack Message: 0.3x
        - Slack Reaction: 0.1x
        
        Args:
            github_stats: GitHub activity statistics
            slack_stats: Slack activity statistics
            
        Returns:
            Weighted contribution score
        """
        score = 0.0
        
        # GitHub contributions
        score += github_stats.get('commits', 0) * 1.0
        score += github_stats.get('prs', 0) * 2.0
        score += github_stats.get('issues', 0) * 0.5
        
        # Slack contributions
        score += slack_stats.get('messages', 0) * 0.3
        score += slack_stats.get('reactions', 0) * 0.1
        
        return round(score, 2)
    
    def generate_project_report_data(
        self,
        project_key: str,
        week_offset: int = 0
    ) -> Dict[str, Any]:
        """
        Generate report data for a project.
        
        Args:
            project_key: Project identifier (e.g., 'project-ooo')
            week_offset: Weeks to go back (0 = current week, -1 = last week)
            
        Returns:
            Dictionary with all report data
        """
        # Get project configuration
        project_config = self.get_project_config(project_key)
        
        # Get week information
        week_info = get_week_info(week_offset)
        
        # Convert to date strings for SQL
        start_date = week_info['start_date'].strftime('%Y-%m-%d')
        end_date = week_info['end_date'].strftime('%Y-%m-%d')
        
        # Get active members from Slack
        active_members = self.get_active_members(project_key, start_date, end_date)
        member_names = [m['name'] for m in active_members]
        
        if not member_names:
            return {
                'project': project_config,
                'period': week_info,
                'members': [],
                'error': 'No active members found in Slack channel for this period'
            }
        
        # Get GitHub statistics (filtered by project repositories)
        github_stats = self.get_github_stats(
            member_names,
            project_config.get('repositories', []),
            start_date,
            end_date
        )
        
        # Get Slack statistics
        slack_stats = self.get_slack_stats(
            member_names,
            project_config['slack_channel_id'],
            start_date,
            end_date
        )
        
        # Combine member data
        member_data = []
        for member in active_members:
            name = member['name']
            gh_stats = github_stats.get(name, {})
            sl_stats = slack_stats.get(name, {})
            
            contribution_score = self.calculate_contribution_score(gh_stats, sl_stats)
            
            member_data.append({
                'name': name,
                'email': member.get('email'),
                'github': gh_stats,
                'slack': sl_stats,
                'contribution_score': contribution_score
            })
        
        # Sort by contribution score descending
        member_data.sort(key=lambda x: x['contribution_score'], reverse=True)
        
        return {
            'project': project_config,
            'period': week_info,
            'members': member_data,
            'summary': {
                'total_members': len(member_data),
                'total_commits': sum(m['github'].get('commits', 0) for m in member_data),
                'total_prs': sum(m['github'].get('prs', 0) for m in member_data),
                'total_messages': sum(m['slack'].get('messages', 0) for m in member_data),
                'total_additions': sum(m['github'].get('additions', 0) for m in member_data),
                'total_deletions': sum(m['github'].get('deletions', 0) for m in member_data),
            }
        }
    
    def format_markdown_report(self, report_data: Dict[str, Any]) -> str:
        """
        Format report data as Markdown following guidelines.
        
        Args:
            report_data: Report data from generate_project_report_data()
            
        Returns:
            Formatted Markdown report
        """
        project = report_data['project']
        period = report_data['period']
        members = report_data['members']
        summary = report_data['summary']
        
        # Start with header
        md = f"# {project['name']} - Weekly Activity Report\n\n"
        md += f"**{period['week_title']}**\n\n"
        
        # Period information
        md += "## 📅 Reporting Period\n\n"
        md += f"- **Start**: {period['formatted_range'].split(' ~ ')[0]}\n"
        md += f"- **End**: {period['formatted_range'].split(' ~ ')[1]}\n"
        md += "- **Duration**: 7 days\n"
        md += f"- **Timezone**: KST (UTC+9)\n\n"
        
        # Executive Summary
        md += "## 📊 Executive Summary\n\n"
        md += f"- **Active Members**: {summary['total_members']}\n"
        md += f"- **Total Commits**: {summary['total_commits']}\n"
        md += f"- **Total Pull Requests**: {summary['total_prs']}\n"
        md += f"- **Total Slack Messages**: {summary['total_messages']}\n"
        md += f"- **Code Changes**: +{summary['total_additions']} / -{summary['total_deletions']} lines\n\n"
        
        # Project repositories
        md += "## 🗂️ Project Repositories\n\n"
        for repo in project.get('repositories', []):
            md += f"- [{repo}](https://github.com/tokamak-network/{repo})\n"
        md += "\n"
        
        # Team composition
        md += "## 👥 Team Composition\n\n"
        md += f"**Project Lead**: {project.get('lead', 'TBD')}\n\n"
        md += f"**Active Members ({len(members)})**:\n"
        for i, member in enumerate(members, 1):
            md += f"{i}. {member['name']}"
            if member.get('email'):
                md += f" ({member['email']})"
            md += f" - Contribution Score: {member['contribution_score']}\n"
        md += "\n"
        
        # Detailed member analysis
        md += "## 🔍 Detailed Analysis\n\n"
        
        for member in members:
            md += f"### {member['name']}\n\n"
            
            gh = member['github']
            sl = member['slack']
            
            md += "**GitHub Contributions:**\n"
            md += f"- Commits: {gh.get('commits', 0)} "
            md += f"(+{gh.get('additions', 0)} / -{gh.get('deletions', 0)} lines)\n"
            md += f"- Pull Requests: {gh.get('prs', 0)}\n"
            md += f"- Issues: {gh.get('issues', 0)}\n\n"
            
            md += "**Slack Activity:**\n"
            md += f"- Messages: {sl.get('messages', 0)}\n"
            md += f"- Reactions: {sl.get('reactions', 0)}\n\n"
            
            md += f"**Contribution Score**: {member['contribution_score']}\n\n"
            
            md += "---\n\n"
        
        # Footer
        md += "## 📝 Notes\n\n"
        md += "- This report follows the guidelines in [REPORT_GUIDELINES.md](../docs/REPORT_GUIDELINES.md)\n"
        md += f"- Only activities in project repositories are included: {', '.join(project.get('repositories', []))}\n"
        md += f"- Only members active in #{project['slack_channel']} are included\n"
        md += "- Contribution scores use weighted metrics (see guidelines)\n"
        md += "- All timestamps are in KST (Korea Standard Time)\n\n"
        
        md += f"**Generated on**: {datetime.now(self.kst).strftime('%Y-%m-%d %H:%M:%S KST')}\n"
        
        return md


def generate_report_cli(
    project_key: str,
    week_offset: int = 0,
    output_file: Optional[str] = None
) -> None:
    """
    CLI function to generate a project report.
    
    Args:
        project_key: Project identifier (e.g., 'project-ooo')
        week_offset: Weeks to go back (0 = current week, -1 = last week)
        output_file: Optional output file path (defaults to reports/ directory)
    """
    from pathlib import Path
    
    # Initialize
    config = Config()
    main_db_url = config.get('database', {}).get('main_db', 'sqlite:///data/databases/main.db')
    db_manager = DatabaseManager(main_db_url)
    
    generator = ProjectReportGenerator(db_manager, config)
    
    # Generate report data
    print(f"📊 Generating report for {project_key}...")
    report_data = generator.generate_project_report_data(project_key, week_offset)
    
    if 'error' in report_data:
        print(f"❌ Error: {report_data['error']}")
        return
    
    # Format as markdown
    markdown = generator.format_markdown_report(report_data)
    
    # Determine output file
    if not output_file:
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        week_info = report_data['period']
        filename = f"{project_key}_weekly_report_{week_info['week_title'].replace(', ', '').replace(' ', '_').replace('(', '').replace(')', '')}.md"
        output_file = reports_dir / filename
    
    # Write to file
    Path(output_file).write_text(markdown, encoding='utf-8')
    print(f"✅ Report generated: {output_file}")
    print(f"   Members: {report_data['summary']['total_members']}")
    print(f"   Commits: {report_data['summary']['total_commits']}")
    print(f"   PRs: {report_data['summary']['total_prs']}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate project activity report")
    parser.add_argument(
        'project',
        help='Project key (e.g., project-ooo, project-eco)'
    )
    parser.add_argument(
        '--week-offset',
        type=int,
        default=-1,
        help='Weeks to go back (0=current, -1=last week)'
    )
    parser.add_argument(
        '--output',
        '-o',
        help='Output file path'
    )
    
    args = parser.parse_args()
    
    generate_report_cli(args.project, args.week_offset, args.output)

