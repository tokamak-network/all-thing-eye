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
        slack_messages = await db["slack_messages"].count_documents({
            'channel_name': {'$ne': 'tokamak-partners'}  # Exclude private channel
        })
        if slack_messages > 0:
            activity_summary["slack"] = {
                "total_activities": slack_messages,
                "activity_types": {
                    "message": slack_messages
                }
            }
        
        # Notion (using diff tracking data - collected every minute)
        notion_diffs = await db["notion_content_diffs"].count_documents({})
        if notion_diffs > 0:
            activity_summary["notion"] = {
                "total_activities": notion_diffs,
                "activity_types": {
                    "content_diff": notion_diffs
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
        
        # 5. Get code changes statistics (additions + deletions from github_commits)
        code_changes = {
            "total": {"additions": 0, "deletions": 0},
            "daily": [],
            "weekly": []
        }
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=90)

            # Total code changes (last 90 days)
            total_pipeline = [
                {"$match": {"date": {"$gte": start_date}}},
                {"$group": {
                    "_id": None,
                    "additions": {"$sum": {"$ifNull": ["$additions", 0]}},
                    "deletions": {"$sum": {"$ifNull": ["$deletions", 0]}}
                }}
            ]
            total_result = await db["github_commits"].aggregate(total_pipeline).to_list(1)
            if total_result:
                code_changes["total"]["additions"] = total_result[0].get("additions", 0)
                code_changes["total"]["deletions"] = total_result[0].get("deletions", 0)

            # Daily code changes (last 30 days for chart)
            daily_start = end_date - timedelta(days=30)
            daily_pipeline = [
                {"$match": {"date": {"$gte": daily_start}}},
                {"$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date"}},
                    "additions": {"$sum": {"$ifNull": ["$additions", 0]}},
                    "deletions": {"$sum": {"$ifNull": ["$deletions", 0]}}
                }},
                {"$sort": {"_id": 1}}
            ]
            daily_result = await db["github_commits"].aggregate(daily_pipeline).to_list(None)

            # Fill missing days with zeros
            daily_map = {}
            current = daily_start
            while current <= end_date:
                d = current.strftime("%Y-%m-%d")
                daily_map[d] = {"date": d, "additions": 0, "deletions": 0}
                current += timedelta(days=1)

            for doc in daily_result:
                if doc["_id"] in daily_map:
                    daily_map[doc["_id"]]["additions"] = doc["additions"]
                    daily_map[doc["_id"]]["deletions"] = doc["deletions"]

            code_changes["daily"] = sorted(daily_map.values(), key=lambda x: x["date"])

            # Weekly code changes (last 12 weeks)
            weekly_start = end_date - timedelta(weeks=12)
            weekly_pipeline = [
                {"$match": {"date": {"$gte": weekly_start}}},
                {"$group": {
                    "_id": {"$dateToString": {"format": "%Y-%V", "date": "$date"}},
                    "additions": {"$sum": {"$ifNull": ["$additions", 0]}},
                    "deletions": {"$sum": {"$ifNull": ["$deletions", 0]}}
                }},
                {"$sort": {"_id": 1}}
            ]
            weekly_result = await db["github_commits"].aggregate(weekly_pipeline).to_list(None)
            code_changes["weekly"] = [
                {"week": doc["_id"], "additions": doc["additions"], "deletions": doc["deletions"]}
                for doc in weekly_result
            ]

        except Exception as e:
            logger.warning(f"Failed to get code changes stats: {e}")

        # 6. Get daily activity trends
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
            notion_trend = await get_daily_counts("notion_content_diffs", "timestamp")  # Use diff tracking
            drive_trend = await get_daily_counts("drive_activities", "time")
            
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
            for date_str, count in drive_trend.items():
                if date_str in trend_map: trend_map[date_str]["drive"] = count
                
            daily_trends = sorted(trend_map.values(), key=lambda x: x["date"])
            
        except Exception as e:
            logger.error(f"Failed to generate daily trends: {e}")

        # 6. Get context keywords
        top_keywords = []
        try:
            # Recent 7 days for context
            keyword_start_date = datetime.utcnow() - timedelta(days=7)
            
            # Helper to fetch text from collection
            async def get_recent_texts(collection_name, text_field, date_field):
                try:
                    coll = db[collection_name]
                    cursor = coll.find(
                        {date_field: {"$gte": keyword_start_date}},
                        {text_field: 1, "_id": 0}
                    ).sort(date_field, -1).limit(200) # Limit to 200 documents per source
                    
                    texts = []
                    async for doc in cursor:
                        if text_field in doc and doc[text_field]:
                            texts.append(doc[text_field])
                    return texts
                except Exception:
                    return []
            
            # Fetch texts
            github_texts = await get_recent_texts("github_commits", "message", "date")
            slack_texts = await get_recent_texts("slack_messages", "text", "posted_at")
            notion_texts = await get_recent_texts("notion_content_diffs", "page_title", "timestamp")  # Use diff tracking
            # drive_texts = await get_recent_texts("drive_activities", "title", "time") # Re-enable if possible, but title might be missing
            
            all_texts = github_texts + slack_texts + notion_texts
            
            # Simple keyword extraction
            if all_texts:
                # Basic stopwords
                stopwords = set([
                    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", 
                    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at", 
                    "this", "but", "his", "by", "from", "they", "we", "say", "her", 
                    "she", "or", "an", "will", "my", "one", "all", "would", "there", 
                    "their", "what", "so", "up", "out", "if", "about", "who", "get", 
                    "which", "go", "me", "https", "http", "com", "www", "github", 
                    "slack", "drive", "google", "feat", "fix", "chore", "docs", "refactor",
                    "merge", "branch", "pull", "request", "update", "delete", "create",
                    "add", "remove", "test", "main", "master", "dev", "prod", "is", "are", "was"
                ])
                
                words = []
                for text in all_texts:
                    # Remove URLs and special chars
                    clean_text = re.sub(r'http\S+', '', str(text))
                    clean_text = re.sub(r'[^\w\s]', '', clean_text)
                    tokens = clean_text.lower().split()
                    words.extend([w for w in tokens if w not in stopwords and len(w) > 2])
                
                # Get top 30
                common_words = Counter(words).most_common(30)
                top_keywords = [{"text": word, "value": count} for word, count in common_words]
                
        except Exception as e:
            logger.warning(f"Failed to extract keywords: {e}")

        # 7. Get last collection times (based on collector execution, not data timestamps)
        # This shows when the collector last ran, regardless of whether it found data
        last_collected = {}
        
        # Check if collection_status exists (for new tracking system)
        collection_names_list = await db.list_collection_names()
        has_collection_status = 'collection_status' in collection_names_list
        
        # For Notion, always use notion_content_diffs timestamp since it's collected every minute
        # Other sources use collection_status if available
        sources_list = ['github', 'slack', 'drive']  # Notion handled separately
        
        if has_collection_status:
            # New method: Use collection_status tracking for non-Notion sources
            collection_status_coll = db['collection_status']
            
            for source in sources_list:
                try:
                    # Find the most recent collection status for this source
                    status_doc = await collection_status_coll.find_one(
                        {'source': source},
                        sort=[('completed_at', -1)]
                    )
                    
                    if status_doc and 'completed_at' in status_doc:
                        completed_time = status_doc['completed_at']
                        
                        # Ensure it's a datetime object
                        if isinstance(completed_time, datetime):
                            last_collected[source] = completed_time.isoformat() + 'Z'
                        elif isinstance(completed_time, str):
                            # Try to parse if it's a string
                            try:
                                parsed_time = datetime.fromisoformat(completed_time.replace('Z', '+00:00'))
                                last_collected[source] = parsed_time.isoformat() + 'Z'
                            except:
                                logger.warning(f"Could not parse timestamp {completed_time} for {source}")
                                last_collected[source] = None
                        else:
                            last_collected[source] = None
                    else:
                        last_collected[source] = None
                        
                except Exception as e:
                    logger.warning(f"Error checking collection_status for {source}: {e}")
                    last_collected[source] = None
        else:
            # Fallback: Use data timestamps (old method) for non-Notion sources
            logger.info("collection_status not found, using fallback method")
            
            # Map collections with their timestamp field names
            source_collections = {
                'github': [('github_commits', 'collected_at'), ('github_pull_requests', 'collected_at'), ('github_issues', 'collected_at')],
                'slack': [('slack_messages', 'collected_at')],
                'drive': [('drive_files', 'collected_at'), ('drive_activities', 'collected_at')]
            }
            
            for source, collections in source_collections.items():
                latest_time = None
                for coll_name, time_field in collections:
                    try:
                        if coll_name in collection_names_list:
                            # Find most recent document
                            doc = await db[coll_name].find_one(
                                {},
                                sort=[(time_field, -1)]
                            )
                            if doc and time_field in doc:
                                doc_time = doc[time_field]
                                # Handle string timestamps (ISO format)
                                if isinstance(doc_time, str):
                                    try:
                                        doc_time = datetime.fromisoformat(doc_time.replace('Z', '+00:00'))
                                    except:
                                        continue
                                if isinstance(doc_time, datetime):
                                    if not latest_time or doc_time > latest_time:
                                        latest_time = doc_time
                    except Exception as e:
                        logger.warning(f"Error checking {coll_name}: {e}")
                
                if latest_time:
                    last_collected[source] = latest_time.isoformat() + 'Z'
                else:
                    last_collected[source] = None
        
        # Notion: Use collection_status for "notion_diff" source
        # This tracks when the collector last ran successfully, not when data was created
        # This way, even if no changes are detected, we know the collector is running
        try:
            if has_collection_status:
                # Look for notion_diff in collection_status (new diff-based collector)
                status_doc = await collection_status_coll.find_one(
                    {'source': 'notion_diff'},
                    sort=[('completed_at', -1)]
                )
                
                if status_doc and 'completed_at' in status_doc:
                    completed_time = status_doc['completed_at']
                    
                    if isinstance(completed_time, datetime):
                        last_collected['notion'] = completed_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                    elif isinstance(completed_time, str):
                        try:
                            parsed_time = datetime.fromisoformat(completed_time.replace('Z', '+00:00'))
                            last_collected['notion'] = parsed_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                        except:
                            last_collected['notion'] = completed_time
                    else:
                        last_collected['notion'] = None
                else:
                    # Fallback: check old "notion" source
                    old_status_doc = await collection_status_coll.find_one(
                        {'source': 'notion'},
                        sort=[('completed_at', -1)]
                    )
                    if old_status_doc and 'completed_at' in old_status_doc:
                        completed_time = old_status_doc['completed_at']
                        if isinstance(completed_time, datetime):
                            last_collected['notion'] = completed_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                        elif isinstance(completed_time, str):
                            last_collected['notion'] = completed_time
                        else:
                            last_collected['notion'] = None
                    else:
                        last_collected['notion'] = None
                        logger.info("No collection_status found for notion_diff or notion")
            else:
                # No collection_status collection - fallback to data timestamp
                if 'notion_content_diffs' in collection_names_list:
                    notion_doc = await db['notion_content_diffs'].find_one(
                        {},
                        sort=[('timestamp', -1)]
                    )
                    if notion_doc and 'timestamp' in notion_doc:
                        notion_time = notion_doc['timestamp']
                        if isinstance(notion_time, datetime):
                            last_collected['notion'] = notion_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                        elif isinstance(notion_time, str) and 'T' in notion_time:
                            last_collected['notion'] = notion_time
                        else:
                            last_collected['notion'] = None
                    else:
                        last_collected['notion'] = None
                else:
                    last_collected['notion'] = None
        except Exception as e:
            logger.warning(f"Error checking notion collection_status: {e}")
            import traceback
            logger.warning(traceback.format_exc())
            last_collected['notion'] = None
        
        # 9. Compile final response
        return {
            # Main statistics (for Dashboard cards)
            "total_members": total_members,
            "total_activities": total_documents,
            "active_projects": active_projects,
            "data_sources": len(activity_summary),

            # Activity breakdown (for Dashboard summary section)
            "activity_summary": activity_summary,
            "daily_trends": daily_trends,
            "top_keywords": top_keywords,

            # Code changes (additions/deletions from GitHub commits)
            "code_changes": code_changes,
            
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


@router.get("/code-changes")
async def get_code_changes_stats(
    request: Request,
    start_date: str = None,
    end_date: str = None,
    _admin: str = Depends(require_admin)
):
    """
    Get detailed code changes statistics from GitHub commits.

    Args:
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)

    Returns:
        - Total additions/deletions
        - Daily code changes
        - Weekly code changes
        - Top contributors by code changes
        - Top repositories by activity
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db

        # Parse date range or use defaults
        if start_date and end_date:
            try:
                filter_start = datetime.strptime(start_date, "%Y-%m-%d")
                filter_end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)  # Include end date
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        else:
            filter_end = datetime.utcnow()
            filter_start = filter_end - timedelta(days=30)  # Default: last 30 days

        date_filter = {"date": {"$gte": filter_start, "$lt": filter_end}}

        # 1. Total code changes
        total_pipeline = [
            {"$match": date_filter},
            {"$group": {
                "_id": None,
                "additions": {"$sum": {"$ifNull": ["$additions", 0]}},
                "deletions": {"$sum": {"$ifNull": ["$deletions", 0]}}
            }}
        ]
        total_result = await db["github_commits"].aggregate(total_pipeline).to_list(1)
        total = {"additions": 0, "deletions": 0}
        if total_result:
            total["additions"] = total_result[0].get("additions", 0)
            total["deletions"] = total_result[0].get("deletions", 0)

        # 2. Daily code changes
        daily_pipeline = [
            {"$match": date_filter},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date"}},
                "additions": {"$sum": {"$ifNull": ["$additions", 0]}},
                "deletions": {"$sum": {"$ifNull": ["$deletions", 0]}}
            }},
            {"$sort": {"_id": 1}}
        ]
        daily_result = await db["github_commits"].aggregate(daily_pipeline).to_list(None)

        # Fill missing days
        daily_map = {}
        current = filter_start
        while current < filter_end:
            d = current.strftime("%Y-%m-%d")
            daily_map[d] = {"date": d, "additions": 0, "deletions": 0}
            current += timedelta(days=1)

        for doc in daily_result:
            if doc["_id"] and doc["_id"] in daily_map:
                daily_map[doc["_id"]]["additions"] = doc["additions"]
                daily_map[doc["_id"]]["deletions"] = doc["deletions"]

        daily = sorted(daily_map.values(), key=lambda x: x["date"])

        # 3. Weekly code changes
        weekly_pipeline = [
            {"$match": date_filter},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%V", "date": "$date"}},
                "additions": {"$sum": {"$ifNull": ["$additions", 0]}},
                "deletions": {"$sum": {"$ifNull": ["$deletions", 0]}}
            }},
            {"$sort": {"_id": 1}}
        ]
        weekly_result = await db["github_commits"].aggregate(weekly_pipeline).to_list(None)
        weekly = [
            {"week": doc["_id"], "additions": doc["additions"], "deletions": doc["deletions"]}
            for doc in weekly_result if doc["_id"]
        ]

        # 4. Top contributors (by total changes)
        # First, build GitHub username → member name mapping
        github_to_member = {}
        try:
            # Get all GitHub identifiers
            github_identifiers = await db["member_identifiers"].find(
                {"source": "github"}
            ).to_list(None)

            # Build member_id → github_username mapping
            member_ids = set()
            member_id_to_github = {}
            for ident in github_identifiers:
                member_id = ident.get("member_id")
                github_username = ident.get("identifier_value")
                if member_id and github_username:
                    member_ids.add(member_id)
                    # Handle both string and ObjectId member_ids
                    member_id_to_github[str(member_id)] = github_username

            # Get member names
            from bson import ObjectId
            member_obj_ids = []
            for mid in member_ids:
                try:
                    member_obj_ids.append(ObjectId(mid))
                except:
                    pass

            if member_obj_ids:
                members_cursor = db["members"].find(
                    {"_id": {"$in": member_obj_ids}},
                    {"_id": 1, "name": 1}
                )
                async for member in members_cursor:
                    member_id_str = str(member["_id"])
                    member_name = member.get("name")
                    # Find the github username for this member
                    for mid, github_user in member_id_to_github.items():
                        if mid == member_id_str and member_name:
                            github_to_member[github_user.lower()] = member_name
                            github_to_member[github_user] = member_name
        except Exception as e:
            logger.warning(f"Failed to build GitHub to member mapping: {e}")

        member_pipeline = [
            {"$match": date_filter},
            {"$group": {
                "_id": "$author_name",
                "additions": {"$sum": {"$ifNull": ["$additions", 0]}},
                "deletions": {"$sum": {"$ifNull": ["$deletions", 0]}},
                "commits": {"$sum": 1}
            }},
            {"$addFields": {
                "total_changes": {"$add": ["$additions", "$deletions"]}
            }},
            {"$sort": {"total_changes": -1}}
            # No limit - return all members for frontend pagination
        ]
        member_result = await db["github_commits"].aggregate(member_pipeline).to_list(None)

        by_member = []
        for doc in member_result:
            if not doc["_id"]:
                continue
            github_username = doc["_id"]
            # Try to find member name (case-insensitive)
            member_name = github_to_member.get(github_username) or github_to_member.get(github_username.lower()) or github_username
            by_member.append({
                "name": member_name,
                "github_id": github_username,
                "additions": doc["additions"],
                "deletions": doc["deletions"],
                "commits": doc["commits"]
            })

        # 5. Top repositories (by activity)
        repo_pipeline = [
            {"$match": date_filter},
            {"$group": {
                "_id": "$repository",
                "additions": {"$sum": {"$ifNull": ["$additions", 0]}},
                "deletions": {"$sum": {"$ifNull": ["$deletions", 0]}},
                "commits": {"$sum": 1}
            }},
            {"$addFields": {
                "total_changes": {"$add": ["$additions", "$deletions"]}
            }},
            {"$sort": {"total_changes": -1}},
            {"$limit": 20}
        ]
        repo_result = await db["github_commits"].aggregate(repo_pipeline).to_list(None)
        by_repository = [
            {
                "name": doc["_id"] or "Unknown",
                "additions": doc["additions"],
                "deletions": doc["deletions"],
                "commits": doc["commits"]
            }
            for doc in repo_result if doc["_id"]
        ]

        return {
            "total": total,
            "daily": daily,
            "weekly": weekly,
            "by_member": by_member,
            "by_repository": by_repository,
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error(f"Error generating code changes stats: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to generate code statistics: {str(e)}")

