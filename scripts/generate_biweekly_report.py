#!/usr/bin/env python3
"""
Biweekly Report Generator

Generates biweekly ecosystem reports using data from MongoDB and AI.

Usage:
    python scripts/generate_biweekly_report.py
    python scripts/generate_biweekly_report.py --start-date 2025-01-01 --end-date 2025-01-14
    python scripts/generate_biweekly_report.py --no-ai  # Skip AI generation, use template only
    python scripts/generate_biweekly_report.py --output report.md
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.core.mongo_manager import get_mongo_manager
from src.report.external_data import (
    get_staking_data,
    get_staking_summary_text,
    get_ton_wton_tx_counts,
    get_transactions_summary_text,
    get_market_cap_data,
    get_market_cap_summary_text,
)
from src.report.templates.biweekly import BIWEEKLY_REPORT_TEMPLATE, COMMUNITY_TEMPLATE
from src.report.ai_client import generate_completion

KST = ZoneInfo("Asia/Seoul")


async def get_github_stats(mongo_manager, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """
    Get GitHub commit statistics from MongoDB.
    
    Returns:
        Dict with commit counts by project/category
    """
    db = mongo_manager.async_db
    
    # Query commits in date range - use 'date' field (not 'committed_at')
    query = {
        "date": {
            "$gte": start_date,
            "$lte": end_date
        }
    }
    
    commits = await db['github_commits'].find(query).to_list(length=None)
    
    # Also get PRs
    pr_query = {
        "created_at": {
            "$gte": start_date,
            "$lte": end_date
        }
    }
    prs = await db['github_pull_requests'].find(pr_query).to_list(length=None)
    
    # Count commits by repository
    repo_counts = {}
    for commit in commits:
        repo = commit.get('repository', 'unknown')
        repo_counts[repo] = repo_counts.get(repo, 0) + 1
    
    # Count PRs by repository
    pr_counts = {}
    for pr in prs:
        repo = pr.get('repository', 'unknown')
        pr_counts[repo] = pr_counts.get(repo, 0) + 1
    
    # Categorize repos (based on project mapping)
    categories = {
        'Economics': ['ton-staking-v2', 'TON-Ecosystem', 'staking-dashboard', 'ton-staking', 'tokamak-dao'],
        'Zkp': ['Tokamak-zk-EVM', 'tokamak-zk-evm-docs', 'Tokamak-zkp-channel-manager', 'zkp', 'zk-'],
        'Rollup': ['tokamak-titan', 'tokamak-titan-canyon', 'optimism', 'thanos', 'trh-'],
        'etc': []  # Everything else
    }
    
    category_stats = {cat: {'repos': set(), 'commits': 0} for cat in categories}
    
    for repo, count in repo_counts.items():
        found = False
        for cat, keywords in categories.items():
            if cat == 'etc':
                continue
            if any(kw.lower() in repo.lower() for kw in keywords):
                category_stats[cat]['repos'].add(repo)
                category_stats[cat]['commits'] += count
                found = True
                break
        if not found:
            category_stats['etc']['repos'].add(repo)
            category_stats['etc']['commits'] += count
    
    # Convert sets to counts
    for cat in category_stats:
        category_stats[cat]['repos'] = len(category_stats[cat]['repos'])
    
    total_commits = sum(repo_counts.values())
    total_repos = len(repo_counts)
    
    return {
        'total_commits': total_commits,
        'total_repos': total_repos,
        'total_prs': len(prs),
        'by_repo': repo_counts,
        'pr_by_repo': pr_counts,
        'by_category': category_stats,
        'commits_list': commits,
        'prs_list': prs
    }


def format_tech_stats_table(category_stats: Dict) -> str:
    """Format category stats as markdown table."""
    lines = [
        "| Pools      | Repos | Commits |",
        "|------------|-------|---------|"
    ]
    
    for cat in ['Economics', 'Zkp', 'Rollup', 'etc']:
        stats = category_stats.get(cat, {'repos': 0, 'commits': 0})
        lines.append(f"| {cat:10} | {stats['repos']:5} | {stats['commits']:7} |")
    
    return "\n".join(lines)


async def get_active_projects(mongo_manager) -> Dict[str, list]:
    """
    Get active projects and their repositories from MongoDB.
    
    Returns:
        Dict mapping project key to list of repositories
    """
    db = mongo_manager.async_db
    projects = await db['projects'].find({'is_active': True}).to_list(length=None)
    
    active_repos = {}
    for p in projects:
        key = p.get('key', '').replace('project-', '')
        repos = p.get('repositories', [])
        active_repos[key] = [r.lower() for r in repos]
    
    return active_repos


async def generate_project_summaries(
    commits_list: list,
    active_projects: Dict[str, list],
    use_ai: bool = True
) -> Dict[str, str]:
    """
    Generate project-specific summaries from commits.
    
    Args:
        commits_list: List of commit documents
        active_projects: Dict of active project keys to their repos
        use_ai: Whether to use AI for summarization
        
    Returns:
        Dict with project summaries
    """
    # Only include active projects (ooo, eco, trh)
    # syb is not active, so excluded
    project_commits = {
        'ooo': [],
        'eco': [],
        'trh': []
    }
    
    # Map repos to projects based on DB config
    repo_to_project = {}
    for project_key, repos in active_projects.items():
        if project_key in project_commits:
            for repo in repos:
                repo_to_project[repo.lower()] = project_key
    
    # Fallback keywords for repos not in DB
    project_keywords = {
        'ooo': ['zk-evm', 'zkevm', 'zkp', 'tokamak-zk', 'channel-manager'],
        'eco': ['staking', 'ton-staking', 'dao', 'ecosystem', 'ton-total'],
        'trh': ['titan', 'thanos', 'drb', 'trh-', 'commit-reveal']
    }
    
    for commit in commits_list:
        repo = commit.get('repository', '').lower()
        
        # First check if repo is in active project repos
        if repo in repo_to_project:
            project_key = repo_to_project[repo]
            project_commits[project_key].append(commit)
            continue
        
        # Fallback to keyword matching for active projects only
        matched = False
        for project, keywords in project_keywords.items():
            if any(kw in repo for kw in keywords):
                project_commits[project].append(commit)
                matched = True
                break
        
        # Non-matched commits go to etc (not included in project summaries)
    
    summaries = {}
    
    if use_ai:
        system_prompt = """You are a technical writer for Tokamak Network. 
Generate concise bullet-point summaries of development progress based on commit messages.
Focus on key achievements and features, not internal processes.
Use past tense and be specific about what was implemented.
Output 3-5 bullet points in markdown format starting with "- " (hyphen)."""
        
        for project, commits in project_commits.items():
            if not commits:
                summaries[project] = "- No significant updates in this period."
                continue
            
            # Prepare commit data for AI
            commit_texts = []
            for c in commits[:20]:  # Limit to 20 commits
                repo = c.get('repository', '')
                msg = c.get('message', '').split('\n')[0]  # First line only
                commit_texts.append(f"- [{repo}] {msg}")
            
            prompt = f"""Based on these commits, summarize the key development progress:

{chr(10).join(commit_texts)}

Generate a concise summary with 3-5 bullet points highlighting the main achievements."""
            
            try:
                summary = await generate_completion(prompt, system_prompt, max_tokens=500)
                summaries[project] = summary
            except Exception as e:
                print(f"AI generation failed for {project}: {e}")
                # Fallback to simple summary
                summaries[project] = "\n".join([f"- {c.get('message', '').split(chr(10))[0]}" for c in commits[:5]])
    else:
        # Non-AI mode: just list recent commits
        for project, commits in project_commits.items():
            if not commits:
                summaries[project] = "- No significant updates in this period."
            else:
                bullet_points = [f"- {c.get('message', '').split(chr(10))[0]}" for c in commits[:5]]
                summaries[project] = "\n".join(bullet_points)
    
    return summaries


async def generate_highlight(
    github_stats: Dict,
    staking_summary: str,
    market_summary: str,
    use_ai: bool = True
) -> str:
    """Generate the highlight section using AI."""
    if not use_ai:
        return "This bi-weekly period saw continued development across all Tokamak Network projects."
    
    system_prompt = """You are a technical writer for Tokamak Network.
Generate a concise 2-3 sentence highlight summarizing the most significant achievements.
Focus on the most impactful developments. Be specific and professional."""
    
    # Prepare summary data
    total_commits = github_stats.get('total_commits', 0)
    total_repos = github_stats.get('total_repos', 0)
    top_repos = sorted(github_stats.get('by_repo', {}).items(), key=lambda x: x[1], reverse=True)[:5]
    
    prompt = f"""Based on this data, generate a highlight summary:

GitHub Activity:
- Total commits: {total_commits} in {total_repos} repositories
- Top repositories: {', '.join([f'{r[0]} ({r[1]} commits)' for r in top_repos])}

{staking_summary}
{market_summary}

Generate a 2-3 sentence highlight focusing on the most significant achievements."""
    
    try:
        highlight = await generate_completion(prompt, system_prompt, max_tokens=300)
        return highlight
    except Exception as e:
        print(f"AI generation failed for highlight: {e}")
        return f"This bi-weekly period saw {total_commits} commits across {total_repos} repositories in the Tokamak Network ecosystem."


async def generate_biweekly_report(
    start_date: datetime,
    end_date: datetime,
    use_ai: bool = True,
    output_file: Optional[str] = None
) -> str:
    """
    Generate a complete biweekly report.
    
    Args:
        start_date: Start of reporting period
        end_date: End of reporting period
        use_ai: Whether to use AI for summaries
        output_file: Optional file path to save report
        
    Returns:
        Generated report as markdown string
    """
    print("=" * 60)
    print("📊 Biweekly Report Generator")
    print("=" * 60)
    print(f"Period: {start_date.date()} to {end_date.date()}")
    print(f"AI Mode: {'Enabled' if use_ai else 'Disabled'}")
    print()
    
    # Initialize MongoDB
    mongodb_config = {
        'uri': os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
        'database': os.getenv('MONGODB_DATABASE', 'all_thing_eye')
    }
    mongo_manager = get_mongo_manager(mongodb_config)
    mongo_manager.connect_async()
    
    try:
        # 1. Fetch ecosystem data
        print("📈 Fetching ecosystem data...")
        
        staking_data = await get_staking_data(mongo_manager=mongo_manager)
        staking_summary = get_staking_summary_text(staking_data)
        print(f"   Staking: {staking_data.get('latest_staked', 0):,.0f} TON")
        
        market_data = await get_market_cap_data(mongo_manager=mongo_manager)
        market_summary = get_market_cap_summary_text(market_data)
        print(f"   Market Cap: ${market_data.get('market_cap', 0):,.0f}")
        
        # Transaction data (may be empty)
        try:
            tx_data = await get_ton_wton_tx_counts(start_date, end_date, mongo_manager=mongo_manager)
            tx_summary = get_transactions_summary_text(tx_data)
        except Exception as e:
            print(f"   Transactions: Not available ({e})")
            tx_summary = "Transaction data is currently being collected."
        
        # 2. Fetch GitHub stats
        print("📂 Fetching GitHub data...")
        github_stats = await get_github_stats(mongo_manager, start_date, end_date)
        print(f"   Commits: {github_stats['total_commits']} in {github_stats['total_repos']} repos")
        
        # 3. Get active projects and generate summaries
        print("📝 Generating summaries...")
        active_projects = await get_active_projects(mongo_manager)
        print(f"   Active projects: {list(active_projects.keys())}")
        
        project_summaries = await generate_project_summaries(
            github_stats['commits_list'],
            active_projects=active_projects,
            use_ai=use_ai
        )
        
        # 4. Generate highlight
        highlight = await generate_highlight(
            github_stats, staking_summary, market_summary, use_ai=use_ai
        )
        
        # 5. Format tech stats table
        tech_table = format_tech_stats_table(github_stats['by_category'])
        
        # 6. Fill template (only active projects: ooo, eco, trh)
        report = BIWEEKLY_REPORT_TEMPLATE.format(
            staking_summary=staking_summary,
            transactions_summary=tx_summary,
            market_cap_summary=market_summary,
            tech_stats_table=tech_table,
            total_commits=github_stats['total_commits'],
            total_repos=github_stats['total_repos'],
            ooo_summary=project_summaries.get('ooo', '- No updates'),
            eco_summary=project_summaries.get('eco', '- No updates'),
            trh_summary=project_summaries.get('trh', '- No updates'),
        )
        
        # Replace highlight
        report = report.replace(
            "This week, our primary focus centered on the Tokamak Rollup Hub (TRH) infrastructure upgrade and the ongoing Staking V2 integration. Notable progress includes advanced chain configuration, internal audits for L1 Contract verification, and preparations for UI service deployment.",
            highlight
        )
        
        # Add community section
        report = report + COMMUNITY_TEMPLATE
        
        # Save to file
        if output_file:
            output_path = Path(output_file)
        else:
            output_dir = project_root / "output"
            output_dir.mkdir(exist_ok=True)
            date_str = end_date.strftime("%Y-%m-%d")
            output_path = output_dir / f"biweekly-report-{date_str}.md"
        
        output_path.write_text(report, encoding='utf-8')
        print(f"\n✅ Report saved to: {output_path}")
        
        return report
        
    finally:
        mongo_manager.close()


async def main():
    parser = argparse.ArgumentParser(description='Generate biweekly report')
    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date (YYYY-MM-DD). Default: 2 weeks ago'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='End date (YYYY-MM-DD). Default: today'
    )
    parser.add_argument(
        '--no-ai',
        action='store_true',
        help='Skip AI generation, use basic summaries'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output file path'
    )
    
    args = parser.parse_args()
    
    # Parse dates
    if args.end_date:
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').replace(tzinfo=KST)
    else:
        end_date = datetime.now(KST)
    
    if args.start_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').replace(tzinfo=KST)
    else:
        start_date = end_date - timedelta(days=14)
    
    # Convert to UTC for MongoDB queries
    start_utc = start_date.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    end_utc = end_date.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    
    await generate_biweekly_report(
        start_date=start_utc,
        end_date=end_utc,
        use_ai=not args.no_ai,
        output_file=args.output
    )


if __name__ == '__main__':
    asyncio.run(main())
