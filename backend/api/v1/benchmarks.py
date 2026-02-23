"""
Benchmarks API - External project comparison endpoints.

Provides endpoints to manage external project registrations
and compare project metrics over time.
"""

import os
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from typing import List

router = APIRouter()


class AddProjectRequest(BaseModel):
    owner: str
    repo: str
    category: str = ""
    display_name: str = ""


class BackfillRequest(BaseModel):
    projects: List[str]
    start_date: str
    end_date: str


# --- Helper ---

def _get_db(request: Request):
    return request.app.state.mongo_manager.db


# --- External Project CRUD ---

@router.get("/projects")
async def list_external_projects(request: Request):
    """List all registered external projects."""
    db = _get_db(request)
    projects = list(db["external_projects"].find(
        {},
        {"_id": 0},
    ).sort("full_name", 1))
    return {"projects": projects, "total": len(projects)}


@router.post("/projects")
async def add_external_project(request: Request, body: AddProjectRequest):
    """Register a new external project for benchmarking."""
    db = _get_db(request)

    full_name = f"{body.owner}/{body.repo}"
    existing = db["external_projects"].find_one({"full_name": full_name})
    if existing:
        raise HTTPException(status_code=409, detail=f"Project {full_name} already registered")

    # Verify repo exists on GitHub
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN not configured")

    from src.plugins.external_github_collector import ExternalGitHubCollector

    collector = ExternalGitHubCollector(github_token)
    info = collector.get_repo_info(body.owner, body.repo)
    if not info:
        raise HTTPException(status_code=404, detail=f"Repository {full_name} not found on GitHub")

    if info.get("is_archived"):
        raise HTTPException(status_code=400, detail=f"Repository {full_name} is archived")

    now = datetime.now(timezone.utc)
    doc = {
        "owner": info["owner"],
        "repo": info["repo"],
        "full_name": info["full_name"],
        "display_name": body.display_name or info["repo"].replace("-", " ").title(),
        "category": body.category,
        "is_active": True,
        "stars": info["stars"],
        "language": info["language"],
        "description": info["description"],
        "created_at": now,
        "updated_at": now,
    }
    db["external_projects"].insert_one(doc)
    doc.pop("_id", None)

    # Backfill 30 days of benchmark data (bulk fetch)
    backfill_days = 30
    today = datetime.now(timezone.utc)
    start_date = today - timedelta(days=backfill_days)

    daily_stats = collector.collect_range_stats(body.owner, body.repo, start_date, today)
    backfill_count = 0
    for stats in daily_stats:
        if stats["commits_count"] > 0 or stats["prs_opened"] > 0 or stats["issues_opened"] > 0:
            db["project_benchmarks"].update_one(
                {"project_ref": full_name, "date": stats["date"]},
                {"$set": stats},
                upsert=True,
            )
            backfill_count += 1

    return {
        "message": f"Project {full_name} registered successfully",
        "project": doc,
        "backfill_days": backfill_count,
    }


@router.delete("/projects/{owner}/{repo}")
async def remove_external_project(request: Request, owner: str, repo: str):
    """Remove an external project and its benchmark data."""
    db = _get_db(request)
    full_name = f"{owner}/{repo}"

    result = db["external_projects"].delete_one({"full_name": full_name})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"Project {full_name} not found")

    # Also remove benchmark data
    deleted_benchmarks = db["project_benchmarks"].delete_many({"project_ref": full_name})

    return {
        "message": f"Project {full_name} removed",
        "benchmarks_deleted": deleted_benchmarks.deleted_count,
    }


# --- Comparison Data ---

@router.get("/compare")
async def compare_projects(
    request: Request,
    projects: str = Query(..., description="Comma-separated project refs"),
    metric: str = Query("commits", description="Metric: commits, additions, deletions, prs, issues"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    granularity: str = Query("daily", description="Granularity: daily, weekly, monthly"),
):
    """Get comparison data for multiple projects over a date range."""
    db = _get_db(request)

    project_list = [p.strip() for p in projects.split(",") if p.strip()]
    if not project_list:
        raise HTTPException(status_code=400, detail="No projects specified")

    # Validate dates
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    # Fetch benchmark data
    query = {
        "project_ref": {"$in": project_list},
        "date": {"$gte": start_date, "$lte": end_date},
    }
    benchmarks = list(db["project_benchmarks"].find(query, {"_id": 0}).sort("date", 1))

    # Group by project
    project_data = {}
    for b in benchmarks:
        ref = b["project_ref"]
        if ref not in project_data:
            project_data[ref] = []
        project_data[ref].append(b)

    # Aggregate by granularity if needed
    if granularity in ("weekly", "monthly"):
        for ref in project_data:
            project_data[ref] = _aggregate_by_granularity(project_data[ref], granularity)

    # Build summary per project
    summaries = {}
    for ref, data_points in project_data.items():
        summaries[ref] = {
            "total_commits": sum(d.get("commits_count", 0) for d in data_points),
            "total_additions": sum(d.get("additions", 0) for d in data_points),
            "total_deletions": sum(d.get("deletions", 0) for d in data_points),
            "total_prs_opened": sum(d.get("prs_opened", 0) for d in data_points),
            "total_prs_merged": sum(d.get("prs_merged", 0) for d in data_points),
            "total_issues_opened": sum(d.get("issues_opened", 0) for d in data_points),
            "total_issues_closed": sum(d.get("issues_closed", 0) for d in data_points),
            "avg_contributors": round(
                sum(d.get("unique_contributors", 0) for d in data_points) / max(len(data_points), 1), 1
            ),
            "data_points": len(data_points),
        }

    # Build chart series
    chart_data = _build_chart_data(project_data, project_list, metric)

    # Build coverage info: which projects have no/partial data and are external (backfillable)
    coverage = {}
    for ref in project_list:
        data_points = project_data.get(ref, [])
        is_external = not ref.startswith("internal:")
        dates = sorted([d["date"] for d in data_points]) if data_points else []
        coverage[ref] = {
            "has_data": len(data_points) > 0,
            "data_points": len(data_points),
            "earliest": dates[0] if dates else None,
            "latest": dates[-1] if dates else None,
            "is_external": is_external,
            "needs_backfill": is_external and len(data_points) == 0,
        }

    return {
        "projects": project_list,
        "metric": metric,
        "start_date": start_date,
        "end_date": end_date,
        "granularity": granularity,
        "summaries": summaries,
        "chart_data": chart_data,
        "coverage": coverage,
    }


@router.post("/compare/backfill")
async def backfill_comparison_data(request: Request, body: BackfillRequest):
    """On-demand backfill: fetch missing benchmark data for external projects."""
    db = _get_db(request)

    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN not configured")

    try:
        start_dt = datetime.strptime(body.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(body.end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    from src.plugins.external_github_collector import ExternalGitHubCollector
    collector = ExternalGitHubCollector(github_token)

    results = {}
    for ref in body.projects:
        # Only backfill external projects (not internal:xxx)
        if ref.startswith("internal:"):
            continue

        # Verify project is registered
        project = db["external_projects"].find_one({"full_name": ref})
        if not project:
            results[ref] = {"status": "not_registered", "backfilled": 0}
            continue

        owner, repo = ref.split("/", 1)
        daily_stats = collector.collect_range_stats(owner, repo, start_dt, end_dt)
        count = 0
        for stats in daily_stats:
            if stats["commits_count"] > 0 or stats["prs_opened"] > 0 or stats["issues_opened"] > 0:
                db["project_benchmarks"].update_one(
                    {"project_ref": ref, "date": stats["date"]},
                    {"$set": stats},
                    upsert=True,
                )
                count += 1
        results[ref] = {"status": "ok", "backfilled": count}

    return {"results": results}


@router.get("/internal-repos")
async def search_internal_repos(
    request: Request,
    q: str = Query("", description="Search query for repo name"),
    limit: int = Query(20, description="Max results"),
):
    """Search internal GitHub repositories for benchmarking."""
    db = _get_db(request)

    query = {"is_archived": {"$ne": True}}
    if q.strip():
        query["name"] = {"$regex": q.strip(), "$options": "i"}

    repos = list(db["github_repositories"].find(
        query,
        {"_id": 0, "name": 1, "description": 1, "url": 1, "pushed_at": 1},
    ).sort("pushed_at", -1).limit(limit))

    return {"repos": repos, "total": len(repos)}


# --- Helpers ---

def _aggregate_by_granularity(data_points: list, granularity: str) -> list:
    """Aggregate daily data points into weekly or monthly buckets."""
    buckets = {}
    for dp in data_points:
        date = datetime.strptime(dp["date"], "%Y-%m-%d")
        if granularity == "weekly":
            # Use ISO week start (Monday)
            week_start = date - timedelta(days=date.weekday())
            key = week_start.strftime("%Y-%m-%d")
        else:  # monthly
            key = date.strftime("%Y-%m")

        if key not in buckets:
            buckets[key] = {
                "date": key,
                "project_ref": dp["project_ref"],
                "project_type": dp.get("project_type", ""),
                "commits_count": 0,
                "additions": 0,
                "deletions": 0,
                "prs_opened": 0,
                "prs_merged": 0,
                "issues_opened": 0,
                "issues_closed": 0,
                "unique_contributors": 0,
                "_contributor_sum": 0,
                "_day_count": 0,
            }
        b = buckets[key]
        b["commits_count"] += dp.get("commits_count", 0)
        b["additions"] += dp.get("additions", 0)
        b["deletions"] += dp.get("deletions", 0)
        b["prs_opened"] += dp.get("prs_opened", 0)
        b["prs_merged"] += dp.get("prs_merged", 0)
        b["issues_opened"] += dp.get("issues_opened", 0)
        b["issues_closed"] += dp.get("issues_closed", 0)
        b["_contributor_sum"] += dp.get("unique_contributors", 0)
        b["_day_count"] += 1

    result = []
    for b in buckets.values():
        b["unique_contributors"] = round(b["_contributor_sum"] / max(b["_day_count"], 1), 1)
        del b["_contributor_sum"]
        del b["_day_count"]
        result.append(b)
    return sorted(result, key=lambda x: x["date"])


METRIC_FIELDS = {
    "commits": "commits_count",
    "additions": "additions",
    "deletions": "deletions",
    "prs": "prs_opened",
    "prs_merged": "prs_merged",
    "issues": "issues_opened",
    "issues_closed": "issues_closed",
    "contributors": "unique_contributors",
}


def _build_chart_data(project_data: dict, project_list: list, metric: str) -> list:
    """Build chart-friendly data series."""
    field = METRIC_FIELDS.get(metric, "commits_count")

    # Collect all dates
    all_dates = set()
    for data_points in project_data.values():
        for dp in data_points:
            all_dates.add(dp["date"])

    all_dates = sorted(all_dates)

    # Build lookup
    lookup = {}
    for ref, data_points in project_data.items():
        lookup[ref] = {dp["date"]: dp.get(field, 0) for dp in data_points}

    chart_data = []
    for date in all_dates:
        entry = {"date": date}
        for ref in project_list:
            entry[ref] = lookup.get(ref, {}).get(date, 0)
        chart_data.append(entry)

    return chart_data
