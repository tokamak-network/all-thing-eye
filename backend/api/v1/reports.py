"""
Reports API

Generates biweekly ecosystem reports using data from MongoDB and AI.
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import get_logger
from backend.middleware.jwt_auth import require_admin

logger = get_logger(__name__)

router = APIRouter()

KST = ZoneInfo("Asia/Seoul")


def get_mongo():
    """Get MongoDB manager from main.py"""
    from backend.main import mongo_manager
    return mongo_manager


class ReportRequest(BaseModel):
    """Request model for report generation"""
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    use_ai: bool = True


class ReportResponse(BaseModel):
    """Response model for generated report"""
    content: str
    metadata: Dict[str, Any]


async def get_github_stats(mongo_manager, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """
    Get GitHub commit statistics from MongoDB.
    """
    db = mongo_manager.async_db
    
    # Query commits in date range
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
    
    # Categorize repos
    categories = {
        'Economics': ['ton-staking-v2', 'TON-Ecosystem', 'staking-dashboard', 'ton-staking', 'tokamak-dao'],
        'Zkp': ['Tokamak-zk-EVM', 'tokamak-zk-evm-docs', 'Tokamak-zkp-channel-manager', 'zkp', 'zk-'],
        'Rollup': ['tokamak-titan', 'tokamak-titan-canyon', 'optimism', 'thanos', 'trh-'],
        'etc': []
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
    """Get active projects and their repositories from MongoDB."""
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
    """Generate project-specific summaries from commits."""
    from src.report.ai_client import generate_completion
    
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
        
        if repo in repo_to_project:
            project_key = repo_to_project[repo]
            project_commits[project_key].append(commit)
            continue
        
        matched = False
        for project, keywords in project_keywords.items():
            if any(kw in repo for kw in keywords):
                project_commits[project].append(commit)
                matched = True
                break
    
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
            
            commit_texts = []
            for c in commits[:20]:
                repo = c.get('repository', '')
                msg = c.get('message', '').split('\n')[0]
                commit_texts.append(f"- [{repo}] {msg}")
            
            prompt = f"""Based on these commits, summarize the key development progress:

{chr(10).join(commit_texts)}

Generate a concise summary with 3-5 bullet points highlighting the main achievements."""
            
            try:
                summary = await generate_completion(prompt, system_prompt, max_tokens=500)
                summaries[project] = summary
            except Exception as e:
                logger.error(f"AI generation failed for {project}: {e}")
                summaries[project] = "\n".join([f"- {c.get('message', '').split(chr(10))[0]}" for c in commits[:5]])
    else:
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
    from src.report.ai_client import generate_completion
    
    if not use_ai:
        return "This bi-weekly period saw continued development across all Tokamak Network projects."
    
    system_prompt = """You are a technical writer for Tokamak Network.
Generate a concise 2-3 sentence highlight summarizing the most significant achievements.
Focus on the most impactful developments. Be specific and professional."""
    
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
        logger.error(f"AI generation failed for highlight: {e}")
        return f"This bi-weekly period saw {total_commits} commits across {total_repos} repositories in the Tokamak Network ecosystem."


@router.post("/generate", response_model=ReportResponse)
async def generate_report(
    request: Request,
    report_request: ReportRequest,
    _admin: str = Depends(require_admin)
):
    """
    Generate a biweekly ecosystem report.
    
    Args:
        report_request: Contains start_date, end_date, and use_ai flag
        
    Returns:
        Generated report content and metadata
    """
    try:
        from src.report.external_data import (
            get_staking_data,
            get_staking_summary_text,
            get_ton_wton_tx_counts,
            get_transactions_summary_text,
            get_market_cap_data,
            get_market_cap_summary_text,
        )
        from src.report.templates.biweekly import BIWEEKLY_REPORT_TEMPLATE, COMMUNITY_TEMPLATE
        
        # Parse dates
        try:
            start_date = datetime.strptime(report_request.start_date, '%Y-%m-%d').replace(tzinfo=KST)
            end_date = datetime.strptime(report_request.end_date, '%Y-%m-%d').replace(tzinfo=KST)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
        
        # Convert to UTC for MongoDB queries
        start_utc = start_date.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        end_utc = end_date.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        
        mongo = get_mongo()
        
        # 1. Fetch ecosystem data
        staking_data = await get_staking_data(mongo_manager=mongo)
        staking_summary = get_staking_summary_text(staking_data)
        
        market_data = await get_market_cap_data(mongo_manager=mongo)
        market_summary = get_market_cap_summary_text(market_data)
        
        # Transaction data (may be empty)
        try:
            tx_data = await get_ton_wton_tx_counts(start_utc, end_utc, mongo_manager=mongo)
            tx_summary = get_transactions_summary_text(tx_data)
        except Exception as e:
            logger.warning(f"Transactions data not available: {e}")
            tx_summary = "Transaction data is currently being collected."
        
        # 2. Fetch GitHub stats
        github_stats = await get_github_stats(mongo, start_utc, end_utc)
        
        # 3. Get active projects and generate summaries
        active_projects = await get_active_projects(mongo)
        
        project_summaries = await generate_project_summaries(
            github_stats['commits_list'],
            active_projects=active_projects,
            use_ai=report_request.use_ai
        )
        
        # 4. Generate highlight
        highlight = await generate_highlight(
            github_stats, staking_summary, market_summary, use_ai=report_request.use_ai
        )
        
        # 5. Format tech stats table
        tech_table = format_tech_stats_table(github_stats['by_category'])
        
        # 6. Fill template
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
        
        # Prepare metadata
        metadata = {
            "start_date": report_request.start_date,
            "end_date": report_request.end_date,
            "use_ai": report_request.use_ai,
            "generated_at": datetime.now(KST).isoformat(),
            "stats": {
                "total_commits": github_stats['total_commits'],
                "total_repos": github_stats['total_repos'],
                "total_prs": github_stats['total_prs'],
                "staked_ton": staking_data.get('latest_staked', 0),
                "market_cap": market_data.get('market_cap', 0),
            }
        }
        
        return ReportResponse(content=report, metadata=metadata)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.get("/presets")
async def get_report_presets(
    request: Request,
    _admin: str = Depends(require_admin)
):
    """
    Get preset date ranges for report generation.
    """
    import calendar
    
    now = datetime.now(KST)
    today = now.strftime('%Y-%m-%d')
    current_day = now.day
    current_month = now.month
    current_year = now.year
    
    presets = []
    
    # Current month first half (1-15)
    this_month_first_half_start = now.replace(day=1).strftime('%Y-%m-%d')
    this_month_first_half_end = now.replace(day=15).strftime('%Y-%m-%d')
    
    # Current month second half (16-end)
    last_day_of_month = calendar.monthrange(current_year, current_month)[1]
    this_month_second_half_start = now.replace(day=16).strftime('%Y-%m-%d')
    this_month_second_half_end = now.replace(day=last_day_of_month).strftime('%Y-%m-%d')
    
    # This month halves - 1st half always first
    presets.append({
        "name": "This month 1st half (1-15)",
        "start_date": this_month_first_half_start,
        "end_date": this_month_first_half_end if current_day >= 15 else today
    })
    
    if current_day > 15:
        presets.append({
            "name": "This month 2nd half (16-end)",
            "start_date": this_month_second_half_start,
            "end_date": today
        })
    
    # This quarter
    quarter = (current_month - 1) // 3
    quarter_start_month = quarter * 3 + 1
    this_quarter_start = datetime(current_year, quarter_start_month, 1, tzinfo=KST).strftime('%Y-%m-%d')
    
    presets.append({
        "name": "This quarter",
        "start_date": this_quarter_start,
        "end_date": today
    })
    
    # Last quarter
    if quarter == 0:
        last_quarter_year = current_year - 1
        last_quarter_start_month = 10
        last_quarter_end_month = 12
    else:
        last_quarter_year = current_year
        last_quarter_start_month = (quarter - 1) * 3 + 1
        last_quarter_end_month = quarter * 3
    
    last_quarter_start = datetime(last_quarter_year, last_quarter_start_month, 1, tzinfo=KST).strftime('%Y-%m-%d')
    last_quarter_end_day = calendar.monthrange(last_quarter_year, last_quarter_end_month)[1]
    last_quarter_end = datetime(last_quarter_year, last_quarter_end_month, last_quarter_end_day, tzinfo=KST).strftime('%Y-%m-%d')
    
    presets.append({
        "name": "Last quarter",
        "start_date": last_quarter_start,
        "end_date": last_quarter_end
    })
    
    return {"presets": presets}
