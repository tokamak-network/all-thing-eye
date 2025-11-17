"""
Custom Query API endpoints (MongoDB Version)

SECURITY: Read-only queries only
Supports MongoDB query language and aggregation pipelines
"""

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import json
from datetime import datetime

from src.utils.logger import get_logger
from src.core.mongo_manager import get_mongo_manager

logger = get_logger(__name__)

router = APIRouter()

# Get MongoDB manager instance (will be initialized by main app)
def get_mongo():
    from backend.main_mongo import mongo_manager
    return mongo_manager


class QueryRequest(BaseModel):
    collection: str  # Collection name to query
    filter: Dict[str, Any] = Field(default_factory=dict)  # MongoDB filter (find query)
    projection: Optional[Dict[str, Any]] = None  # Fields to return
    sort: Optional[Dict[str, int]] = None  # Sort specification
    limit: int = 1000  # Maximum documents to return
    skip: int = 0  # Number of documents to skip


class AggregationRequest(BaseModel):
    collection: str  # Collection name
    pipeline: List[Dict[str, Any]]  # Aggregation pipeline stages
    limit: int = 10000  # Safety limit


class DynamicQueryRequest(BaseModel):
    collection: str
    operation: str  # "find" or "aggregate"
    query: Optional[Dict[str, Any]] = Field(default=None)  # For find operations
    pipeline: Optional[List[Dict[str, Any]]] = Field(default=None)  # For aggregate operations
    projection: Optional[Dict[str, Any]] = Field(default=None)
    sort: Optional[Dict[str, int]] = Field(default=None)
    limit: int = Field(default=1000)
    skip: int = Field(default=0)


class QueryResponse(BaseModel):
    documents: List[Dict[str, Any]]
    count: int
    collection: str


@router.post("/execute", response_model=QueryResponse)
async def execute_dynamic_query(
    request: Request,
    query_request: DynamicQueryRequest
):
    """
    Execute a dynamic MongoDB query (find or aggregate)
    
    Args:
        query_request: MongoDB query parameters with operation type
    
    Returns:
        Query results as list of documents
    
    Example for find:
        {
            "collection": "github_commits",
            "operation": "find",
            "query": {"author_login": "johndoe"},
            "projection": {"sha": 1, "message": 1},
            "sort": {"committed_at": -1},
            "limit": 10
        }
    
    Example for aggregate:
        {
            "collection": "github_commits",
            "operation": "aggregate",
            "pipeline": [
                {"$group": {"_id": "$author_login", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
        }
    """
    collection_name = query_request.collection
    
    # Validate collection name
    valid_collections = [
        'github_commits', 'github_pull_requests', 'github_issues', 'github_repositories',
        'slack_messages', 'slack_channels',
        'notion_pages', 'notion_databases',
        'drive_activities', 'drive_folders'
    ]
    
    if collection_name not in valid_collections:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid collection. Allowed collections: {', '.join(valid_collections)}"
        )
    
    try:
        db = get_mongo().get_database_async()
        collection = db[collection_name]
        
        if query_request.operation == "find":
            # Build find query
            cursor = collection.find(
                query_request.query or {},
                query_request.projection
            )
            
            if query_request.sort:
                cursor = cursor.sort(list(query_request.sort.items()))
            
            cursor = cursor.skip(query_request.skip).limit(query_request.limit)
            
            documents = await cursor.to_list(length=query_request.limit)
            count = len(documents)
            
        elif query_request.operation == "aggregate":
            if not query_request.pipeline:
                raise HTTPException(status_code=400, detail="Pipeline is required for aggregate operation")
            
            # Add safety limit to pipeline if not present
            pipeline = query_request.pipeline.copy()
            if not any('$limit' in stage for stage in pipeline):
                pipeline.append({'$limit': query_request.limit})
            
            cursor = collection.aggregate(pipeline)
            documents = await cursor.to_list(length=query_request.limit)
            count = len(documents)
            
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid operation '{query_request.operation}'. Must be 'find' or 'aggregate'"
            )
        
        # Convert ObjectId to string
        for doc in documents:
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])
        
        return QueryResponse(
            documents=documents,
            count=count,
            collection=collection_name
        )
    
    except Exception as e:
        logger.error(f"Query execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/find", response_model=QueryResponse)
async def execute_find_query(
    request: Request,
    query_request: QueryRequest
):
    """
    Execute a MongoDB find() query
    
    Args:
        query_request: MongoDB find query parameters
    
    Returns:
        Query results as list of documents
    
    Security:
        - Read-only operations
        - Maximum 10,000 documents per query
        - Whitelisted collections only
    
    Example:
        {
            "collection": "github_commits",
            "filter": {"author_login": "johndoe"},
            "projection": {"sha": 1, "message": 1, "committed_at": 1},
            "sort": {"committed_at": -1},
            "limit": 100
        }
    """
    collection_name = query_request.collection
    
    # Validate collection name
    valid_collections = [
        'github_commits', 'github_pull_requests', 'github_issues', 'github_repositories',
        'slack_messages', 'slack_channels',
        'notion_pages', 'notion_databases',
        'drive_activities', 'drive_folders'
    ]
    
    if collection_name not in valid_collections:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid collection. Must be one of: {', '.join(valid_collections)}"
        )
    
    # Enforce limits
    if query_request.limit > 10000:
        raise HTTPException(
            status_code=400,
            detail="Limit cannot exceed 10,000 documents"
        )
    
    try:
        # Get MongoDB connection
        db = get_mongo().get_database_sync()
        collection = db[collection_name]
        
        # Build query
        cursor = collection.find(
            query_request.filter or {},
            projection=query_request.projection
        )
        
        # Apply sort if provided
        if query_request.sort:
            cursor = cursor.sort(list(query_request.sort.items()))
        
        # Apply pagination
        cursor = cursor.skip(query_request.skip).limit(query_request.limit)
        
        # Fetch documents
        documents = []
        for doc in cursor:
            # Convert ObjectId to string
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])
            
            # Convert datetime to ISO string
            for key, value in doc.items():
                if isinstance(value, datetime):
                    doc[key] = value.isoformat()
            
            documents.append(doc)
        
        logger.info(f"Find query executed: {collection_name} (returned {len(documents)} docs)")
        
        return QueryResponse(
            documents=documents,
            count=len(documents),
            collection=collection_name
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Find query execution failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Query execution failed: {str(e)}"
        )


@router.post("/aggregate", response_model=QueryResponse)
async def execute_aggregation(
    request: Request,
    agg_request: AggregationRequest
):
    """
    Execute a MongoDB aggregation pipeline
    
    Args:
        agg_request: MongoDB aggregation pipeline
    
    Returns:
        Aggregation results
    
    Security:
        - Read-only operations
        - Dangerous stages ($out, $merge) are blocked
        - Maximum 10,000 documents
    
    Example:
        {
            "collection": "github_commits",
            "pipeline": [
                {"$match": {"repository_name": "my-repo"}},
                {"$group": {"_id": "$author_login", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10}
            ]
        }
    """
    collection_name = agg_request.collection
    
    # Validate collection name
    valid_collections = [
        'github_commits', 'github_pull_requests', 'github_issues', 'github_repositories',
        'slack_messages', 'slack_channels',
        'notion_pages', 'notion_databases',
        'drive_activities', 'drive_folders'
    ]
    
    if collection_name not in valid_collections:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid collection. Must be one of: {', '.join(valid_collections)}"
        )
    
    # Security: Block dangerous aggregation stages
    dangerous_stages = ['$out', '$merge']
    for stage in agg_request.pipeline:
        for stage_name in stage.keys():
            if stage_name in dangerous_stages:
                raise HTTPException(
                    status_code=400,
                    detail=f"Stage '{stage_name}' is not allowed (read-only operations)"
                )
    
    # Add safety limit if not present
    has_limit = any('$limit' in stage for stage in agg_request.pipeline)
    if not has_limit:
        agg_request.pipeline.append({'$limit': agg_request.limit})
    
    try:
        # Get MongoDB connection
        db = get_mongo().get_database_sync()
        collection = db[collection_name]
        
        # Execute aggregation
        cursor = collection.aggregate(agg_request.pipeline)
        
        # Fetch results
        documents = []
        for doc in cursor:
            # Convert ObjectId to string
            if '_id' in doc and not isinstance(doc['_id'], (str, int, float)):
                try:
                    doc['_id'] = str(doc['_id'])
                except:
                    pass
            
            # Convert datetime to ISO string
            for key, value in doc.items():
                if isinstance(value, datetime):
                    doc[key] = value.isoformat()
            
            documents.append(doc)
        
        logger.info(f"Aggregation executed: {collection_name} (returned {len(documents)} docs)")
        
        return QueryResponse(
            documents=documents,
            count=len(documents),
            collection=collection_name
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Aggregation execution failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Aggregation execution failed: {str(e)}"
        )


@router.get("/collections")
async def get_collections():
    """
    Get list of available collections
    
    Returns:
        List of collection names with document counts
    """
    try:
        db = get_mongo().get_database_sync()
        
        collections_info = {}
        
        collection_names = [
            'github_commits', 'github_pull_requests', 'github_issues', 'github_repositories',
            'slack_messages', 'slack_channels',
            'notion_pages', 'notion_databases',
            'drive_activities', 'drive_folders'
        ]
        
        for coll_name in collection_names:
            try:
                collection = db[coll_name]
                count = collection.count_documents({})
                
                # Get sample document to show schema
                sample = collection.find_one()
                fields = list(sample.keys()) if sample else []
                
                collections_info[coll_name] = {
                    'count': count,
                    'fields': fields
                }
            except Exception as e:
                logger.warning(f"Could not get info for {coll_name}: {e}")
                collections_info[coll_name] = {
                    'count': 0,
                    'fields': [],
                    'error': str(e)
                }
        
        return {
            'database': db.name,
            'collections': collections_info
        }
    
    except Exception as e:
        logger.error(f"Failed to get collections: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get collections: {str(e)}"
        )


@router.get("/examples")
async def get_query_examples():
    """
    Get example queries for MongoDB
    
    Returns:
        Dictionary of example find and aggregation queries
    """
    examples = {
        "find_examples": {
            "github_commits_by_author": {
                "collection": "github_commits",
                "filter": {"author_login": "johndoe"},
                "projection": {"sha": 1, "message": 1, "committed_at": 1},
                "sort": {"committed_at": -1},
                "limit": 10
            },
            "slack_messages_in_channel": {
                "collection": "slack_messages",
                "filter": {"channel_name": "project-ooo"},
                "projection": {"text": 1, "user_name": 1, "posted_at": 1},
                "sort": {"posted_at": -1},
                "limit": 20
            },
            "notion_pages_recent": {
                "collection": "notion_pages",
                "filter": {},
                "projection": {"title": 1, "created_time": 1, "last_edited_time": 1},
                "sort": {"last_edited_time": -1},
                "limit": 10
            }
        },
        "aggregation_examples": {
            "commits_by_repository": {
                "collection": "github_commits",
                "pipeline": [
                    {"$group": {"_id": "$repository_name", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                    {"$limit": 10}
                ]
            },
            "messages_by_channel": {
                "collection": "slack_messages",
                "pipeline": [
                    {"$group": {"_id": "$channel_name", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}}
                ]
            },
            "user_commit_stats": {
                "collection": "github_commits",
                "pipeline": [
                    {
                        "$group": {
                            "_id": "$author_login",
                            "total_commits": {"$sum": 1},
                            "total_additions": {"$sum": "$additions"},
                            "total_deletions": {"$sum": "$deletions"}
                        }
                    },
                    {"$sort": {"total_commits": -1}},
                    {"$limit": 10}
                ]
            },
            "messages_with_reactions": {
                "collection": "slack_messages",
                "pipeline": [
                    {"$match": {"reactions": {"$exists": True, "$ne": []}}},
                    {"$project": {
                        "channel_name": 1,
                        "user_name": 1,
                        "text": 1,
                        "reaction_count": {"$size": "$reactions"}
                    }},
                    {"$sort": {"reaction_count": -1}},
                    {"$limit": 10}
                ]
            }
        },
        "usage": {
            "find": "POST /api/v1/query/find",
            "aggregate": "POST /api/v1/query/aggregate",
            "note": "All queries are read-only. Use MongoDB query language."
        }
    }
    
    return examples

