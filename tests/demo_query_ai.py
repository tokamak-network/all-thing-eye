#!/usr/bin/env python3
"""
Simple demo of Query Engine and AI Formatter

This demonstrates the core functionality without complex CLI parsing.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import Config
from src.core.database import DatabaseManager
from src.core.member_index import MemberIndex
from src.integrations.query_engine import QueryEngine
from src.integrations.ai_formatter import AIPromptFormatter
from src.utils.date_helpers import get_current_week_range


def main():
    print("=" * 80)
    print("  Query Engine and AI Formatter Demo")
    print("=" * 80)
    
    # Initialize components
    print("\n📦 Initializing components...")
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
    print("✅ Initialization complete")
    
    # Get date range
    start_date, end_date = get_current_week_range()
    print(f"\n📅 Date Range: {start_date.date()} to {end_date.date()}")
    
    # Query member data
    member_name = "Kevin"
    print(f"\n🔍 Querying activities for: {member_name}")
    
    member_data = query_engine.get_member_github_activities(
        member_name,
        start_date,
        end_date
    )
    
    if 'error' in member_data:
        print(f"❌ Error: {member_data['error']}")
        return
    
    # Display statistics
    stats = member_data.get('statistics', {})
    print("\n" + "=" * 80)
    print("  📊 STATISTICS SUMMARY")
    print("=" * 80)
    
    commits = stats.get('commits', {})
    print(f"\n🔧 Commits:")
    print(f"   Total: {commits.get('total', 0)}")
    print(f"   Additions: +{commits.get('additions', 0):,} lines")
    print(f"   Deletions: -{commits.get('deletions', 0):,} lines")
    print(f"   Net: {commits.get('net_lines', 0):,} lines")
    
    prs = stats.get('pull_requests', {})
    print(f"\n🔀 Pull Requests:")
    print(f"   Total: {prs.get('total', 0)}")
    print(f"   Merged: {prs.get('merged', 0)}")
    print(f"   Open: {prs.get('open', 0)}")
    
    issues = stats.get('issues', {})
    print(f"\n📋 Issues:")
    print(f"   Total: {issues.get('total', 0)}")
    print(f"   Closed: {issues.get('closed', 0)}")
    print(f"   Open: {issues.get('open', 0)}")
    
    # Top repositories
    print("\n" + "=" * 80)
    print("  🏆 TOP REPOSITORIES")
    print("=" * 80)
    
    for i, repo in enumerate(member_data.get('top_repositories', [])[:5], 1):
        print(f"{i}. {repo['repository']}")
        print(f"   Commits: {repo['commits']}, PRs: {repo['pull_requests']}")
    
    # Generate AI prompt
    print("\n" + "=" * 80)
    print("  🤖 AI PROMPT GENERATION")
    print("=" * 80)
    
    prompt = ai_formatter.format_member_performance(member_data, include_details=False)
    
    print("\n📝 Generated Prompt Preview (first 1500 characters):")
    print("-" * 80)
    print(prompt[:1500])
    print("\n... (truncated)")
    print("-" * 80)
    
    print(f"\n📏 Full prompt length: {len(prompt)} characters")
    print(f"   Lines: {len(prompt.split(chr(10)))}")
    
    # Show other formats
    print("\n" + "=" * 80)
    print("  📤 EXPORT FORMATS AVAILABLE")
    print("=" * 80)
    
    print("\n1. AI Prompt (Text) - For OpenAI, Claude, etc.")
    print(f"   ✅ Generated ({len(prompt)} chars)")
    
    print("\n2. JSON Export - For API responses")
    json_export = ai_formatter.export_as_json(member_data)
    print(f"   ✅ Available ({len(json_export)} chars)")
    
    print("\n3. Markdown Report - For documentation")
    md_export = ai_formatter.export_as_markdown(member_data)
    print(f"   ✅ Available ({len(md_export)} chars)")
    
    print("\n4. Technical Depth Analysis - For engineering reviews")
    tech_prompt = ai_formatter.format_technical_depth_analysis(member_data)
    print(f"   ✅ Generated ({len(tech_prompt)} chars)")
    
    # Save example output
    output_dir = Path(__file__).parent.parent / "output" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    prompt_file = output_dir / f"{member_name.lower()}_demo_prompt.txt"
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write(prompt)
    
    print("\n" + "=" * 80)
    print("  ✅ DEMO COMPLETE")
    print("=" * 80)
    print(f"\n💾 Sample prompt saved to: {prompt_file}")
    print("\n💡 Usage examples:")
    print("   python tests/test_query_and_ai.py --member Kevin")
    print("   python tests/test_query_and_ai.py --team-summary")
    print("   python tests/test_query_and_ai.py --member Kevin --format json")
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

