"""
Unified Statistics API

Provides consolidated statistics from MongoDB for Dashboard and other pages.
This ensures data consistency across all frontend pages.
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from typing import Dict, Any
from datetime import datetime, timedelta
from collections import Counter
import re

from src.utils.logger import get_logger
from backend.middleware.jwt_auth import require_admin

logger = get_logger(__name__)

router = APIRouter()


def get_mongo():
    """Get MongoDB manager from main.py"""
    from backend.main import mongo_manager
    return mongo_manager


@router.get("/summary")
async def get_app_stats(request: Request, _admin: str = Depends(require_admin)):
    """
    Get unified application statistics
    
    This endpoint provides a single source of truth for all app statistics,
    ensuring data consistency across Dashboard, Database Viewer, and other pages.
    
    Returns:
        Comprehensive statistics including:
        - Total documents (accurate count from MongoDB)
        - Total members
        - Total projects
        - Activity breakdown by source
        - Collections information
        - Last data collection times
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        shared_db = mongo.shared_async_db
        
        # 1. Get accurate document counts from MongoDB collections
        collections_info = []
        collection_names = await db.list_collection_names()
        
        for name in collection_names:
            try:
                collection = db[name]
                count = await collection.count_documents({})
                collections_info.append({
                    "name": name,
                    "count": count,
                    "database": "main"
                })
            except Exception as e:
                logger.warning(f"Failed to count {name}: {e}")
        
        # Add shared database collections
        try:
            shared_collection_names = await shared_db.list_collection_names()
            for name in shared_collection_names:
                try:
                    collection = shared_db[name]
                    count = await collection.count_documents({})
                    collections_info.append({
                        "name": f"shared.{name}",
                        "count": count,
                        "database": "shared"
                    })
                except Exception as e:
                    logger.warning(f"Failed to count shared.{name}: {e}")
        except Exception as e:
            logger.warning(f"Failed to access shared database: {e}")
        
        # Add gemini database collections
        try:
            from backend.api.v1.ai_processed import get_gemini_db
            gemini_db_sync = get_gemini_db()
            gemini_collection_names = gemini_db_sync.list_collection_names()
            for name in gemini_collection_names:
                try:
                    collection = gemini_db_sync[name]
                    count = collection.count_documents({})
                    collections_info.append({
                        "name": f"gemini.{name}",
                        "count": count,
                        "database": "gemini"
                    })
                except Exception as e:
                    logger.warning(f"Failed to count gemini.{name}: {e}")
        except Exception as e:
            logger.warning(f"Failed to access gemini database: {e}")
        
        # Calculate totals
        total_documents = sum(c["count"] for c in collections_info)
        total_collections = len(collections_info)
        
        # 2. Get members count
        members = db["members"]
        total_members = await members.count_documents({})
        
        # 3. Get active projects from projects collection
        try:
            projects_collection = db["projects"]
            active_projects = await projects_collection.count_documents({"is_active": True})
        except Exception as e:
            logger.warning(f"Failed to count active projects: {e}")
            active_projects = 0
        
        # 4. Get activity breakdown by source
        activity_summary = {}
        
        # GitHub
        github_commits = await db["github_commits"].count_documents({})
        github_prs = await db["github_pull_requests"].count_documents({})
        github_issues = await db["github_issues"].count_documents({})
        github_total = github_commits + github_prs + github_issues
        
        if github_total > 0:
            activity_summary["github"] = {
                "total_activities": github_total,
                "activity_types": {
                    "commit": github_commits,
                    "pull_request": github_prs,
                    "issue": github_issues
                }
            }
        
        # Slack
        slack_messages = await db["slack_messages"].count_documents({})
        if slack_messages > 0:
            activity_summary["slack"] = {
                "total_activities": slack_messages,
                "activity_types": {
                    "message": slack_messages
                }
            }
        
        # Notion
        notion_pages = await db["notion_pages"].count_documents({})
        if notion_pages > 0:
            activity_summary["notion"] = {
                "total_activities": notion_pages,
                "activity_types": {
                    "page": notion_pages
                }
            }
        
        # Drive (Temporarily disabled)
        # drive_activities = await db["drive_activities"].count_documents({})
        # if drive_activities > 0:
        #     activity_summary["drive"] = {
        #         "total_activities": drive_activities,
        #         "activity_types": {
        #             "file_activity": drive_activities
        #         }
        #     }
        
        # Recordings
        recordings = await shared_db["recordings"].count_documents({})
        if recordings > 0:
            activity_summary["recordings"] = {
                "total_activities": recordings,
                "activity_types": {
                    "meeting_recording": recordings
                }
            }
        
        # 5. Get daily trends
        daily_trends = []
        try:
            # Last 90 days
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=90)
            
            # Helper for aggregation
            async def get_daily_counts(collection_name, date_field):
                try:
                    coll = db[collection_name]
                    pipeline = [
                        {
                            "$match": {
                                date_field: {"$gte": start_date}
                            }
                        },
                        {
                            "$group": {
                                "_id": {
                                    "$dateToString": {
                                        "format": "%Y-%m-%d", 
                                        "date": f"${date_field}"
                                    }
                                },
                                "count": {"$sum": 1}
                            }
                        },
                        {"$sort": {"_id": 1}}
                    ]
                    result = await coll.aggregate(pipeline).to_list(None)
                    return {doc["_id"]: doc["count"] for doc in result if doc["_id"] is not None}
                except Exception as e:
                    logger.warning(f"Trend aggregation failed for {collection_name}: {e}")
                    return {}

            # Execute aggregations
            github_trend = await get_daily_counts("github_commits", "date")
            slack_trend = await get_daily_counts("slack_messages", "posted_at")
            notion_trend = await get_daily_counts("notion_pages", "last_edited_time")
            # drive_trend = await get_daily_counts("drive_activities", "time") # Disabled
            
            # Initialize map with 0s for all dates in range
            trend_map = {}
            current = start_date
            while current <= end_date:
                d = current.strftime("%Y-%m-%d")
                trend_map[d] = {
                    "date": d, 
                    "github": 0, 
                    "slack": 0, 
                    "notion": 0, 
                    "drive": 0
                }
                current += timedelta(days=1)
                
            # Fill data
            for date_str, count in github_trend.items():
                if date_str in trend_map: trend_map[date_str]["github"] = count
            for date_str, count in slack_trend.items():
                if date_str in trend_map: trend_map[date_str]["slack"] = count
            for date_str, count in notion_trend.items():
                if date_str in trend_map: trend_map[date_str]["notion"] = count
            # for date_str, count in drive_trend.items():
            #     if date_str in trend_map: trend_map[date_str]["drive"] = count
                
            daily_trends = sorted(trend_map.values(), key=lambda x: x["date"])
            
        except Exception as e:
            logger.error(f"Failed to generate daily trends: {e}")

        # 6. Get recent critical events (Timeline)
        recent_events = []
        try:
            limit_per_source = 5
            
            # 1. GitHub PRs
            prs = await db["github_pull_requests"].find(
                {}, 
                {"title": 1, "user.login": 1, "created_at": 1, "html_url": 1, "state": 1, "_id": 0}
            ).sort("created_at", -1).limit(limit_per_source).to_list(None)
            
            for pr in prs:
                recent_events.append({
                    "source": "github",
                    "type": "pull_request",
                    "title": pr.get("title", "Untitled PR"),
                    "user": pr.get("user", {}).get("login", "Unknown"),
                    "time": pr.get("created_at"),
                    "url": pr.get("html_url"),
                    "meta": pr.get("state", "open")
                })

            # 2. GitHub Commits
            commits = await db["github_commits"].find(
                {}, 
                {"message": 1, "author.name": 1, "date": 1, "html_url": 1, "_id": 0}
            ).sort("date", -1).limit(limit_per_source).to_list(None)
            
            for commit in commits:
                recent_events.append({
                    "source": "github",
                    "type": "commit",
                    "title": commit.get("message", "No message"),
                    "user": commit.get("author", {}).get("name", "Unknown"),
                    "time": commit.get("date"),
                    "url": commit.get("html_url"),
                    "meta": "commit"
                })

            # 3. Notion Pages (Created)
            pages = await db["notion_pages"].find(
                {}, 
                {"title": 1, "created_by.name": 1, "created_time": 1, "url": 1, "_id": 0}
            ).sort("created_time", -1).limit(limit_per_source).to_list(None)
            
            for page in pages:
                recent_events.append({
                    "source": "notion",
                    "type": "page_create",
                    "title": page.get("title", "Untitled Page"),
                    "user": page.get("created_by", {}).get("name", "Unknown"),
                    "time": page.get("created_time"),
                    "url": page.get("url"),
                    "meta": "created"
                })

            # Sort and Slice
            def get_time_val(e):
                t = e["time"]
                if isinstance(t, str): return t
                if hasattr(t, 'isoformat'): return t.isoformat()
                return ""

            recent_events.sort(key=get_time_val, reverse=True)
            recent_events = recent_events[:7] # Top 7 latest events
            
            # Serialize
            for e in recent_events:
                if hasattr(e["time"], 'isoformat'):
                    e["time"] = e["time"].isoformat()

        except Exception as e:
            logger.warning(f"Failed to fetch recent events: {e}")

        # 7. Get last collection times
        sources = {
            "github": ["github_commits", "github_pull_requests", "github_issues"],
            "slack": ["slack_messages"],
            "notion": ["notion_pages"],
            "drive": ["drive_activities"]
        }
        
        last_collected = {}
        
        for source, source_collections in sources.items():
            latest_time = None
            for coll_name in source_collections:
                try:
                    collection = db[coll_name]
                    result = await collection.find_one(
                        {"collected_at": {"$exists": True}},
                        sort=[("collected_at", -1)]
                    )
                    if result and "collected_at" in result:
                        coll_time = result["collected_at"]
                        if latest_time is None or coll_time > latest_time:
                            latest_time = coll_time
                except Exception as e:
                    logger.warning(f"Error checking {coll_name}: {e}")
                    continue
            
            last_collected[source] = latest_time.isoformat() + 'Z' if latest_time else None
        
        # 8. Compile final response
        return {
            # Main statistics (for Dashboard cards)
            "total_members": total_members,
            "total_activities": total_documents,
            "active_projects": active_projects,
            "data_sources": len(activity_summary),
            
            # Activity breakdown (for Dashboard summary section)
            "activity_summary": activity_summary,
            "daily_trends": daily_trends,
            "recent_events": recent_events,
            
            # Database information (for Database Viewer)
            "database": {
                "total_collections": total_collections,
                "total_documents": total_documents,
                "collections": collections_info
            },
            
            # Last collection times
            "last_collected": last_collected,
            
            # Metadata
            "generated_at": datetime.utcnow().isoformat() + 'Z'
        }
        
    except Exception as e:
        logger.error(f"Error generating app stats: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to generate statistics: {str(e)}")

