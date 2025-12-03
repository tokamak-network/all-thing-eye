"""
Database Viewer API endpoints for MongoDB

Provides schema inspection and data exploration functionality
"""

from fastapi import APIRouter, HTTPException, Request, Query, Depends
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId

from src.utils.logger import get_logger
from backend.middleware.jwt_auth import require_admin

logger = get_logger(__name__)

router = APIRouter()


def get_mongo():
    """Get MongoDB manager from main.py"""
    from backend.main import mongo_manager
    return mongo_manager


@router.get("/last-collected")
async def get_last_collected_times(request: Request, _admin: str = Depends(require_admin)):
    """
    Get the last data collection time for each data source
    
    Returns:
        Dictionary with last collection times per source
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        sources = {
            "github": ["github_commits", "github_pull_requests", "github_issues"],
            "slack": ["slack_messages"],
            "notion": ["notion_pages"],
            "drive": ["drive_activities"]
        }
        
        last_collected = {}
        
        for source, collections in sources.items():
            latest_time = None
            for coll_name in collections:
                try:
                    collection = db[coll_name]
                    # Find the most recent collected_at
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
            
            # Add 'Z' suffix to indicate UTC timezone
            last_collected[source] = latest_time.isoformat() + 'Z' if latest_time else None
        
        return {
            "last_collected": last_collected,
            "checked_at": datetime.utcnow().isoformat() + 'Z'
        }
        
    except Exception as e:
        logger.error(f"Error getting last collected times: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections")
async def get_collections(request: Request, _admin: str = Depends(require_admin)):
    """
    Get list of all MongoDB collections with basic stats (including shared database)
    
    Returns:
        List of collections with document counts from both main and shared databases
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        shared_db = mongo.shared_async_db
        
        # Get gemini database
        from backend.api.v1.ai_processed import get_gemini_db
        gemini_db_sync = get_gemini_db()
        
        collections_info = []
        
        # Get main database collections
        collection_names = await db.list_collection_names()
        for name in collection_names:
            try:
                collection = db[name]
                count = await collection.count_documents({})
                
                # Get collection stats
                stats = await db.command("collStats", name)
                
                collections_info.append({
                    "name": name,
                    "count": count,
                    "size": stats.get("size", 0),
                    "avgObjSize": stats.get("avgObjSize", 0),
                    "storageSize": stats.get("storageSize", 0),
                    "indexes": stats.get("nindexes", 0),
                    "database": "main"
                })
            except Exception as e:
                logger.warning(f"Failed to get stats for collection {name}: {e}")
                collections_info.append({
                    "name": name,
                    "count": 0,
                    "size": 0,
                    "avgObjSize": 0,
                    "storageSize": 0,
                    "indexes": 0,
                    "database": "main"
                })
        
        # Get shared database collections
        try:
            shared_collection_names = await shared_db.list_collection_names()
            for name in shared_collection_names:
                try:
                    collection = shared_db[name]
                    count = await collection.count_documents({})
                    
                    # Get collection stats
                    stats = await shared_db.command("collStats", name)
                    
                    collections_info.append({
                        "name": f"shared.{name}",  # Prefix with database name
                        "count": count,
                        "size": stats.get("size", 0),
                        "avgObjSize": stats.get("avgObjSize", 0),
                        "storageSize": stats.get("storageSize", 0),
                        "indexes": stats.get("nindexes", 0),
                        "database": "shared"
                    })
                except Exception as e:
                    logger.warning(f"Failed to get stats for shared collection {name}: {e}")
                    collections_info.append({
                        "name": f"shared.{name}",
                        "count": 0,
                        "size": 0,
                        "avgObjSize": 0,
                        "storageSize": 0,
                        "indexes": 0,
                        "database": "shared"
                    })
        except Exception as e:
            logger.warning(f"Failed to access shared database: {e}")
        
        # Get gemini database collections
        try:
            gemini_collection_names = gemini_db_sync.list_collection_names()
            for name in gemini_collection_names:
                try:
                    collection = gemini_db_sync[name]
                    count = collection.count_documents({})
                    
                    # Get collection stats
                    stats = gemini_db_sync.command("collStats", name)
                    
                    collections_info.append({
                        "name": f"gemini.{name}",  # Prefix with database name
                        "count": count,
                        "size": stats.get("size", 0),
                        "avgObjSize": stats.get("avgObjSize", 0),
                        "storageSize": stats.get("storageSize", 0),
                        "indexes": stats.get("nindexes", 0),
                        "database": "gemini"
                    })
                except Exception as e:
                    logger.warning(f"Failed to get stats for gemini collection {name}: {e}")
                    collections_info.append({
                        "name": f"gemini.{name}",
                        "count": 0,
                        "size": 0,
                        "avgObjSize": 0,
                        "storageSize": 0,
                        "indexes": 0,
                        "database": "gemini"
                    })
        except Exception as e:
            logger.warning(f"Failed to access gemini database: {e}")
        
        # Sort by document count (descending)
        collections_info.sort(key=lambda x: x["count"], reverse=True)
        
        return {
            "collections": collections_info,
            "total_collections": len(collections_info),
            "total_documents": sum(c["count"] for c in collections_info),
        }
        
    except Exception as e:
        logger.error(f"Error getting collections: {e}")
        raise HTTPException(status_code=500, detail="Failed to get collections list")


@router.get("/collections/{collection_name}/schema")
async def get_collection_schema(request: Request, collection_name: str, _admin: str = Depends(require_admin)):
    """
    Analyze collection schema by sampling documents
    
    Args:
        collection_name: Name of the collection (use "shared.collection_name" for shared DB)
        
    Returns:
        Schema information with field types and examples
    """
    try:
        mongo = get_mongo()
        
        # Check if it's a shared or gemini collection
        is_shared = collection_name.startswith("shared.")
        is_gemini = collection_name.startswith("gemini.")
        
        if is_shared:
            db = mongo.shared_async_db
            actual_name = collection_name.replace("shared.", "", 1)
            # Verify collection exists
            collection_names = await db.list_collection_names()
            if actual_name not in collection_names:
                raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
            collection = db[actual_name]
            # Sample documents to infer schema (take 100 documents)
            sample_docs = await collection.find({}).limit(100).to_list(length=100)
        elif is_gemini:
            from backend.api.v1.ai_processed import get_gemini_db
            gemini_db_sync = get_gemini_db()
            actual_name = collection_name.replace("gemini.", "", 1)
            # Verify collection exists
            collection_names = gemini_db_sync.list_collection_names()
            if actual_name not in collection_names:
                raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
            collection = gemini_db_sync[actual_name]
            # Sample documents to infer schema (take 100 documents) - sync version
            sample_docs = list(collection.find({}).limit(100))
        else:
            db = mongo.async_db
            actual_name = collection_name
            # Verify collection exists
            collection_names = await db.list_collection_names()
            if actual_name not in collection_names:
                raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
            collection = db[actual_name]
            # Sample documents to infer schema (take 100 documents)
            sample_docs = await collection.find({}).limit(100).to_list(length=100)
        
        if not sample_docs:
            return {
                "collection": collection_name,
                "schema": {},
                "sample_count": 0,
                "message": "Collection is empty"
            }
        
        # Analyze fields
        field_info = {}
        
        for doc in sample_docs:
            for field, value in doc.items():
                if field not in field_info:
                    field_info[field] = {
                        "types": set(),
                        "null_count": 0,
                        "total_count": 0,
                        "example_values": []
                    }
                
                field_info[field]["total_count"] += 1
                
                if value is None:
                    field_info[field]["null_count"] += 1
                    field_info[field]["types"].add("null")
                else:
                    # Get type
                    value_type = type(value).__name__
                    
                    # Special handling for ObjectId
                    if isinstance(value, ObjectId):
                        value_type = "ObjectId"
                    elif isinstance(value, datetime):
                        value_type = "datetime"
                    elif isinstance(value, dict):
                        value_type = "object"
                    elif isinstance(value, list):
                        value_type = "array"
                    
                    field_info[field]["types"].add(value_type)
                    
                    # Store example values (max 3)
                    if len(field_info[field]["example_values"]) < 3:
                        # Convert special types to string for JSON serialization
                        if isinstance(value, ObjectId):
                            example = str(value)
                        elif isinstance(value, datetime):
                            example = value.isoformat()
                        elif isinstance(value, (dict, list)):
                            example = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                        else:
                            example = value
                        
                        field_info[field]["example_values"].append(example)
        
        # Convert sets to lists for JSON serialization
        schema = {}
        for field, info in field_info.items():
            schema[field] = {
                "types": list(info["types"]),
                "nullable": info["null_count"] > 0,
                "null_percentage": round(info["null_count"] / info["total_count"] * 100, 2),
                "occurrence": info["total_count"],
                "occurrence_percentage": round(info["total_count"] / len(sample_docs) * 100, 2),
                "examples": info["example_values"]
            }
        
        return {
            "collection": collection_name,
            "schema": schema,
            "sample_count": len(sample_docs),
            "total_fields": len(schema)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting schema for {collection_name}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get collection schema: {str(e)}")


@router.get("/collections/{collection_name}/documents")
async def get_collection_documents(
    request: Request,
    collection_name: str,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(30, ge=1, le=100, description="Documents per page"),
    search: Optional[str] = Query(None, description="Search query (JSON format)"),
    _admin: str = Depends(require_admin)
):
    """
    Get paginated documents from a collection with optional search
    
    Args:
        collection_name: Name of the collection (use "shared.collection_name" for shared DB)
        page: Page number (1-indexed)
        limit: Documents per page (max 100)
        search: Optional search query in JSON format
        
    Returns:
        Paginated documents from the collection
    """
    try:
        mongo = get_mongo()
        
        # Check if it's a shared or gemini collection
        is_shared = collection_name.startswith("shared.")
        is_gemini = collection_name.startswith("gemini.")
        
        # Parse search query
        query = {}
        if search:
            try:
                import json
                query = json.loads(search)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON search query")
        
        if is_shared:
            db = mongo.shared_async_db
            actual_name = collection_name.replace("shared.", "", 1)
            # Verify collection exists
            collection_names = await db.list_collection_names()
            if actual_name not in collection_names:
                raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
            collection = db[actual_name]
            # Get total count
            total_count = await collection.count_documents(query)
            # Calculate pagination
            skip = (page - 1) * limit
            total_pages = (total_count + limit - 1) // limit  # Ceiling division
            # Get documents
            documents = await collection.find(query).skip(skip).limit(limit).to_list(length=limit)
        elif is_gemini:
            from backend.api.v1.ai_processed import get_gemini_db
            gemini_db_sync = get_gemini_db()
            actual_name = collection_name.replace("gemini.", "", 1)
            # Verify collection exists
            collection_names = gemini_db_sync.list_collection_names()
            if actual_name not in collection_names:
                raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
            collection = gemini_db_sync[actual_name]
            # Get total count
            total_count = collection.count_documents(query)
            # Calculate pagination
            skip = (page - 1) * limit
            total_pages = (total_count + limit - 1) // limit  # Ceiling division
            # Get documents - sync version
            documents = list(collection.find(query).skip(skip).limit(limit))
        else:
            db = mongo.async_db
            actual_name = collection_name
            # Verify collection exists
            collection_names = await db.list_collection_names()
            if actual_name not in collection_names:
                raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
            collection = db[actual_name]
            # Get total count
            total_count = await collection.count_documents(query)
            # Calculate pagination
            skip = (page - 1) * limit
            total_pages = (total_count + limit - 1) // limit  # Ceiling division
            # Get documents
            documents = await collection.find(query).skip(skip).limit(limit).to_list(length=limit)
        
        # Convert ObjectId and datetime to string for JSON serialization
        def serialize_value(value):
            if isinstance(value, ObjectId):
                return str(value)
            elif isinstance(value, datetime):
                return value.isoformat()
            elif isinstance(value, dict):
                return {k: serialize_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [serialize_value(item) for item in value]
            return value
        
        for doc in documents:
            for key, value in list(doc.items()):
                doc[key] = serialize_value(value)
        
        return {
            "collection": collection_name,
            "documents": documents,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "total_pages": total_pages,
                "has_prev": page > 1,
                "has_next": page < total_pages
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting documents from {collection_name}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get documents: {str(e)}")


@router.get("/collections/{collection_name}/sample")
async def get_collection_sample(
    request: Request,
    collection_name: str,
    limit: int = Query(10, ge=1, le=100, description="Number of documents to return"),
    _admin: str = Depends(require_admin)
):
    """
    Get sample documents from a collection (legacy endpoint)
    
    Args:
        collection_name: Name of the collection
        limit: Number of documents to return (max 100)
        
    Returns:
        Sample documents from the collection
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        # Verify collection exists
        collection_names = await db.list_collection_names()
        if collection_name not in collection_names:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
        
        collection = db[collection_name]
        
        # Get sample documents
        documents = await collection.find({}).limit(limit).to_list(length=limit)
        
        # Convert ObjectId and datetime to string for JSON serialization
        def serialize_value(value):
            if isinstance(value, ObjectId):
                return str(value)
            elif isinstance(value, datetime):
                return value.isoformat()
            elif isinstance(value, dict):
                return {k: serialize_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [serialize_value(item) for item in value]
            return value
        
        for doc in documents:
            for key, value in list(doc.items()):
                doc[key] = serialize_value(value)
        
        return {
            "collection": collection_name,
            "documents": documents,
            "count": len(documents),
            "limit": limit
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sample from {collection_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get sample documents: {str(e)}")


@router.get("/collections/{collection_name}/stats")
async def get_collection_stats(request: Request, collection_name: str, _admin: str = Depends(require_admin)):
    """
    Get detailed statistics for a collection
    
    Args:
        collection_name: Name of the collection
        
    Returns:
        Detailed collection statistics
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        # Verify collection exists
        collection_names = await db.list_collection_names()
        if collection_name not in collection_names:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
        
        collection = db[collection_name]
        
        # Get collection stats
        stats = await db.command("collStats", collection_name)
        
        # Get indexes
        indexes = await collection.index_information()
        
        return {
            "collection": collection_name,
            "stats": {
                "count": stats.get("count", 0),
                "size": stats.get("size", 0),
                "avgObjSize": stats.get("avgObjSize", 0),
                "storageSize": stats.get("storageSize", 0),
                "nindexes": stats.get("nindexes", 0),
                "totalIndexSize": stats.get("totalIndexSize", 0),
            },
            "indexes": indexes
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stats for {collection_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get collection stats: {str(e)}")


@router.get("/recordings")
async def get_recordings(
    request: Request,
    limit: int = Query(20, ge=1, le=100, description="Number of recordings"),
    skip: int = Query(0, ge=0, description="Number of recordings to skip"),
    _admin: str = Depends(require_admin)
):
    """
    Get meeting recordings from shared database
    
    Args:
        limit: Number of recordings to return (max 100)
        skip: Number of recordings to skip (for pagination)
        
    Returns:
        List of recordings with metadata (without full content)
    """
    try:
        mongo = get_mongo()
        shared_db = mongo.shared_async_db
        
        # Get recordings (exclude large content field)
        recordings = await shared_db.recordings.find(
            {},
            {"content": 0}  # Exclude content for list view
        ).sort("modifiedTime", -1).skip(skip).limit(limit).to_list(length=limit)
        
        # Convert ObjectId to string
        def serialize_value(value):
            if isinstance(value, ObjectId):
                return str(value)
            elif isinstance(value, datetime):
                return value.isoformat()
            elif isinstance(value, dict):
                return {k: serialize_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [serialize_value(item) for item in value]
            return value
        
        for rec in recordings:
            for key, value in list(rec.items()):
                rec[key] = serialize_value(value)
        
        # Get total count
        total = await shared_db.recordings.count_documents({})
        
        return {
            "recordings": recordings,
            "total": total,
            "limit": limit,
            "skip": skip,
            "has_more": (skip + limit) < total
        }
        
    except Exception as e:
        logger.error(f"Error getting recordings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recordings: {str(e)}")


@router.get("/recordings/{recording_id}")
async def get_recording_detail(
    request: Request,
    recording_id: str,
    _admin: str = Depends(require_admin)
):
    """
    Get full recording details including transcript
    
    Args:
        recording_id: Google Drive file ID of the recording
        
    Returns:
        Full recording document with transcript
    """
    try:
        mongo = get_mongo()
        shared_db = mongo.shared_async_db
        
        # Find recording by Google Drive ID
        recording = await shared_db.recordings.find_one({"id": recording_id})
        
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")
        
        # Convert ObjectId to string
        def serialize_value(value):
            if isinstance(value, ObjectId):
                return str(value)
            elif isinstance(value, datetime):
                return value.isoformat()
            elif isinstance(value, dict):
                return {k: serialize_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [serialize_value(item) for item in value]
            return value
        
        for key, value in list(recording.items()):
            recording[key] = serialize_value(value)
        
        return recording
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recording detail: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recording: {str(e)}")

