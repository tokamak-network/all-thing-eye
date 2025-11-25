"""
Unified Statistics API

Provides consolidated statistics from MongoDB for Dashboard and other pages.
This ensures data consistency across all frontend pages.
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from typing import Dict, Any
from datetime import datetime

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
        
        # Calculate totals
        total_documents = sum(c["count"] for c in collections_info)
        total_collections = len(collections_info)
        
        # 2. Get members count
        members = db["members"]
        total_members = await members.count_documents({})
        
        # 3. Get active projects (from config or database)
        # For now, hardcode based on known projects
        active_projects = 5  # github, slack, notion, drive, recordings
        
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
        
        # Drive
        drive_activities = await db["drive_activities"].count_documents({})
        if drive_activities > 0:
            activity_summary["drive"] = {
                "total_activities": drive_activities,
                "activity_types": {
                    "file_activity": drive_activities
                }
            }
        
        # Recordings
        recordings = await shared_db["recordings"].count_documents({})
        if recordings > 0:
            activity_summary["recordings"] = {
                "total_activities": recordings,
                "activity_types": {
                    "meeting_recording": recordings
                }
            }
        
        # 5. Get last collection times
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
        
        # 6. Compile final response
        return {
            # Main statistics (for Dashboard cards)
            "total_members": total_members,
            "total_activities": total_documents,
            "active_projects": active_projects,
            "data_sources": len(activity_summary),
            
            # Activity breakdown (for Dashboard summary section)
            "activity_summary": activity_summary,
            
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

