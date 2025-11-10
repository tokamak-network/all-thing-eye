#!/usr/bin/env python3
"""
Test Query Engine and AI Formatter Integration

This script demonstrates how to:
1. Query member activities from the database
2. Format the data for AI analysis
3. Export results in various formats
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from src.core.config import Config
from src.core.database import DatabaseManager
from src.core.member_index import MemberIndex
from src.integrations.query_engine import QueryEngine
from src.integrations.ai_formatter import AIPromptFormatter
from src.utils.date_helpers import get_current_week_range, get_last_week_range
import argparse
import json


def print_section(title: str):
    """Print a section header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def print_statistics(stats: dict):
    """Pretty print statistics"""
    print("📊 Statistics Summary:")
    print(f"   Commits: {stats.get('commits', {}).get('total', 0)}")
    print(f"   - Additions: +{stats.get('commits', {}).get('additions', 0):,} lines")
    print(f"   - Deletions: -{stats.get('commits', {}).get('deletions', 0):,} lines")
    print(f"   - Net: {stats.get('commits', {}).get('net_lines', 0):,} lines")
    print(f"   - Changed files: {stats.get('commits', {}).get('changed_files', 0)}")
    
    print(f"\n   Pull Requests: {stats.get('pull_requests', {}).get('total', 0)}")
    print(f"   - Merged: {stats.get('pull_requests', {}).get('merged', 0)}")
    print(f"   - Open: {stats.get('pull_requests', {}).get('open', 0)}")
    
    print(f"\n   Issues: {stats.get('issues', {}).get('total', 0)}")
    print(f"   - Closed: {stats.get('issues', {}).get('closed', 0)}")
    print(f"   - Open: {stats.get('issues', {}).get('open', 0)}")


def save_to_file(content: str, filename: str, directory: str = "output/reports"):
    """Save content to file"""
    output_dir = Path(__file__).parent.parent / directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    filepath = output_dir / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n💾 Saved to: {filepath}")
    return filepath


def test_single_member(
    member_name: str,
    use_last_week: bool = False,
    export_format: str = 'all'
):
    """
    Test query and formatting for a single member
    
    Args:
        member_name: Name of the member to analyze
        use_last_week: Use last week's data instead of current week
        export_format: Export format ('prompt', 'json', 'markdown', 'all')
    """
    print_section("Single Member Analysis")
    
    # Initialize components
    config = Config()
    
    # Get database URL from config
    main_db_url = config.get('database', {}).get('main_db', 'sqlite:///data/databases/main.db')
    
    db_manager = DatabaseManager(main_db_url)
    
    # Register GitHub source database
    github_db_path = 'sqlite:///data/databases/github.db'
    db_manager.register_existing_source_database('github', github_db_path)
    
    member_index = MemberIndex(db_manager)
    query_engine = QueryEngine(db_manager, member_index)
    ai_formatter = AIPromptFormatter()
    
    # Get date range
    if use_last_week:
        start_date, end_date = get_last_week_range()
        week_label = "Last Week"
    else:
        start_date, end_date = get_current_week_range()
        week_label = "Current Week"
    
    print(f"👤 Member: {member_name}")
    print(f"📅 Period: {week_label}")
    print(f"   {start_date.isoformat()} to {end_date.isoformat()}")
    
    # Query member activities
    print("\n🔍 Querying member activities...")
    member_data = query_engine.get_member_github_activities(
        member_name,
        start_date,
        end_date
    )
    
    # Check for errors
    if 'error' in member_data:
        print(f"\n❌ Error: {member_data['error']}")
        return
    
    # Print statistics
    print_statistics(member_data.get('statistics', {}))
    
    # Top repositories
    print("\n🏆 Top Repositories:")
    for i, repo in enumerate(member_data.get('top_repositories', [])[:5], 1):
        print(f"   {i}. {repo['repository']}: {repo['commits']} commits, {repo['pull_requests']} PRs")
    
    # Top files
    print("\n📝 Top Modified Files:")
    for i, file in enumerate(member_data.get('top_files', [])[:5], 1):
        print(f"   {i}. {file['filename']}: {file['modifications']} changes")
    
    # Generate outputs
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    member_slug = member_name.lower().replace(' ', '_')
    
    if export_format in ['prompt', 'all']:
        print_section("AI Prompt Generation")
        
        # Performance review prompt
        print("📝 Generating performance review prompt...")
        prompt = ai_formatter.format_member_performance(member_data, include_details=True)
        
        filename = f"{member_slug}_{week_label.lower().replace(' ', '_')}_prompt_{timestamp}.txt"
        save_to_file(prompt, filename)
        
        # Also print first 50 lines
        print("\n📄 Preview (first 50 lines):")
        print("-" * 80)
        lines = prompt.split('\n')[:50]
        print('\n'.join(lines))
        if len(prompt.split('\n')) > 50:
            print(f"\n... ({len(prompt.split('\n')) - 50} more lines)")
    
    if export_format in ['json', 'all']:
        print_section("JSON Export")
        
        print("📊 Exporting as JSON...")
        json_content = ai_formatter.export_as_json(member_data)
        
        filename = f"{member_slug}_{week_label.lower().replace(' ', '_')}_{timestamp}.json"
        save_to_file(json_content, filename)
    
    if export_format in ['markdown', 'all']:
        print_section("Markdown Export")
        
        print("📝 Exporting as Markdown...")
        markdown_content = ai_formatter.export_as_markdown(member_data)
        
        filename = f"{member_slug}_{week_label.lower().replace(' ', '_')}_{timestamp}.md"
        save_to_file(markdown_content, filename)
    
    if export_format in ['technical', 'all']:
        print_section("Technical Depth Analysis")
        
        print("🔬 Generating technical depth analysis...")
        technical_prompt = ai_formatter.format_technical_depth_analysis(member_data)
        
        filename = f"{member_slug}_{week_label.lower().replace(' ', '_')}_technical_{timestamp}.txt"
        save_to_file(technical_prompt, filename)


def test_team_summary(use_last_week: bool = False):
    """
    Test team-wide summary
    
    Args:
        use_last_week: Use last week's data instead of current week
    """
    print_section("Team Summary Analysis")
    
    # Initialize components
    config = Config()
    
    # Get database URL from config
    main_db_url = config.get('database', {}).get('main_db', 'sqlite:///data/databases/main.db')
    
    db_manager = DatabaseManager(main_db_url)
    
    # Register GitHub source database
    github_db_path = 'sqlite:///data/databases/github.db'
    db_manager.register_existing_source_database('github', github_db_path)
    
    member_index = MemberIndex(db_manager)
    query_engine = QueryEngine(db_manager, member_index)
    ai_formatter = AIPromptFormatter()
    
    # Get date range
    if use_last_week:
        start_date, end_date = get_last_week_range()
        week_label = "Last Week"
    else:
        start_date, end_date = get_current_week_range()
        week_label = "Current Week"
    
    print(f"📅 Period: {week_label}")
    print(f"   {start_date.isoformat()} to {end_date.isoformat()}")
    
    # Query all members
    print("\n🔍 Querying team activities...")
    team_data = query_engine.get_all_members_summary(start_date, end_date)
    
    print(f"\n👥 Total members: {len(team_data)}")
    
    # Print top contributors
    print("\n🏆 Top Contributors (by commits):")
    for i, member in enumerate(team_data[:10], 1):
        stats = member.get('statistics', {})
        commits = stats.get('commits', {}).get('total', 0)
        prs = stats.get('pull_requests', {}).get('total', 0)
        print(f"   {i}. {member['member_name']}: {commits} commits, {prs} PRs")
    
    # Generate team summary prompt
    print("\n📝 Generating team summary prompt...")
    period_dict = {
        'start': start_date.isoformat(),
        'end': end_date.isoformat()
    }
    team_prompt = ai_formatter.format_team_summary(team_data, period_dict)
    
    # Save to file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"team_summary_{week_label.lower().replace(' ', '_')}_{timestamp}.txt"
    save_to_file(team_prompt, filename)
    
    # Print preview
    print("\n📄 Preview (first 50 lines):")
    print("-" * 80)
    lines = team_prompt.split('\n')[:50]
    print('\n'.join(lines))
    if len(team_prompt.split('\n')) > 50:
        print(f"\n... ({len(team_prompt.split('\n')) - 50} more lines)")


def main():
    """Main test function"""
    parser = argparse.ArgumentParser(
        description='Test Query Engine and AI Formatter',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze single member for current week
  python tests/test_query_and_ai.py --member Kevin
  
  # Analyze single member for last week
  python tests/test_query_and_ai.py --member Kevin --last-week
  
  # Export only AI prompt
  python tests/test_query_and_ai.py --member Kevin --format prompt
  
  # Team summary
  python tests/test_query_and_ai.py --team-summary
  
  # Team summary for last week
  python tests/test_query_and_ai.py --team-summary --last-week
        """
    )
    
    parser.add_argument(
        '--member',
        type=str,
        help='Member name to analyze'
    )
    
    parser.add_argument(
        '--team-summary',
        action='store_true',
        help='Generate team-wide summary instead of single member'
    )
    
    parser.add_argument(
        '--last-week',
        action='store_true',
        help='Use last week data instead of current week'
    )
    
    parser.add_argument(
        '--format',
        type=str,
        choices=['prompt', 'json', 'markdown', 'technical', 'all'],
        default='all',
        help='Export format (default: all)'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.member and not args.team_summary:
        parser.error("Either --member or --team-summary must be specified")
    
    if args.member and args.team_summary:
        parser.error("Cannot specify both --member and --team-summary")
    
    try:
        if args.team_summary:
            test_team_summary(args.last_week)
        else:
            test_single_member(args.member, args.last_week, args.format)
        
        print_section("✅ Test Completed Successfully")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

