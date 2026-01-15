"""
Notion Diff API endpoints

Provides granular content change data for Notion pages.
Used by frontend to display GitHub-like diff views.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta

from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# Get MongoDB manager
def get_mongo():
    from backend.main import mongo_manager
    return mongo_manager


# ============================================================================
# Response Models
# ============================================================================

class ChangeItem(BaseModel):
    """Single change item (added/deleted/modified content)"""
    block_id: Optional[str] = None
    block_type: Optional[str] = None
    content: Optional[str] = None
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    added_lines: Optional[List[str]] = None
    deleted_lines: Optional[List[str]] = None
    # For comments
    comment_id: Optional[str] = None
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    created_time: Optional[str] = None


class DiffChanges(BaseModel):
    """Changes in a diff record"""
    added: List[ChangeItem] = []
    deleted: List[ChangeItem] = []
    modified: List[ChangeItem] = []


class NotionDiffResponse(BaseModel):
    """Single diff record"""
    id: str
    document_id: str
    document_title: str
    document_url: str
    editor_id: str
    editor_name: str
    timestamp: str
    diff_type: str  # "block" or "comment"
    changes: DiffChanges
    # Computed fields
    added_count: int = 0
    deleted_count: int = 0
    modified_count: int = 0


class NotionDiffListResponse(BaseModel):
    """List of diff records"""
    total: int
    diffs: List[NotionDiffResponse]
    filters: dict


class NotionDiffStatsResponse(BaseModel):
    """Statistics about Notion diff collection"""
    tracked_pages: int
    current_blocks: int
    total_block_snapshots: int
    total_comment_snapshots: int
    total_diffs: int
    block_diffs: int
    comment_diffs: int


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/notion/diffs", response_model=NotionDiffListResponse)
async def get_notion_diffs(
    page_id: Optional[str] = Query(None, description="Filter by page ID"),
    editor_id: Optional[str] = Query(None, description="Filter by editor ID"),
    editor_name: Optional[str] = Query(None, description="Filter by editor name"),
    diff_type: Optional[str] = Query(None, description="Filter by type (block/comment)"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    Get list of Notion content diffs.
    
    Returns diffs showing what content was added, deleted, or modified.
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        # Build query
        query = {}
        
        if page_id:
            query['document_id'] = page_id
        if editor_id:
            query['editor_id'] = editor_id
        if editor_name:
            query['editor_name'] = {'$regex': editor_name, '$options': 'i'}
        if diff_type:
            query['diff_type'] = diff_type
        
        # Date filter
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query['$gte'] = start_date
            if end_date:
                date_query['$lte'] = end_date
            query['timestamp'] = date_query
        
        # Get total count
        total = await db["notion_content_diffs"].count_documents(query)
        
        # Get diffs
        cursor = db["notion_content_diffs"].find(query).sort(
            "timestamp", -1
        ).skip(offset).limit(limit)
        
        diffs = []
        async for doc in cursor:
            changes = doc.get('changes', {})
            
            diff_response = NotionDiffResponse(
                id=str(doc.get('_id', '')),
                document_id=doc.get('document_id', ''),
                document_title=doc.get('document_title', 'Untitled'),
                document_url=doc.get('document_url', ''),
                editor_id=doc.get('editor_id', ''),
                editor_name=doc.get('editor_name', 'Unknown'),
                timestamp=doc.get('timestamp', ''),
                diff_type=doc.get('diff_type', 'block'),
                changes=DiffChanges(
                    added=[ChangeItem(**item) if isinstance(item, dict) else ChangeItem(content=str(item)) 
                           for item in changes.get('added', [])],
                    deleted=[ChangeItem(**item) if isinstance(item, dict) else ChangeItem(content=str(item)) 
                             for item in changes.get('deleted', [])],
                    modified=[ChangeItem(**item) if isinstance(item, dict) else ChangeItem(content=str(item)) 
                              for item in changes.get('modified', [])]
                ),
                added_count=len(changes.get('added', [])),
                deleted_count=len(changes.get('deleted', [])),
                modified_count=len(changes.get('modified', []))
            )
            diffs.append(diff_response)
        
        return NotionDiffListResponse(
            total=total,
            diffs=diffs,
            filters={
                'page_id': page_id,
                'editor_id': editor_id,
                'editor_name': editor_name,
                'diff_type': diff_type,
                'start_date': start_date,
                'end_date': end_date,
                'limit': limit,
                'offset': offset
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching Notion diffs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notion/diffs/page/{page_id}", response_model=NotionDiffListResponse)
async def get_page_diff_history(
    page_id: str,
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get diff history for a specific Notion page.
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        cursor = db["notion_content_diffs"].find(
            {"document_id": page_id}
        ).sort("timestamp", -1).limit(limit)
        
        diffs = []
        async for doc in cursor:
            changes = doc.get('changes', {})
            
            diff_response = NotionDiffResponse(
                id=str(doc.get('_id', '')),
                document_id=doc.get('document_id', ''),
                document_title=doc.get('document_title', 'Untitled'),
                document_url=doc.get('document_url', ''),
                editor_id=doc.get('editor_id', ''),
                editor_name=doc.get('editor_name', 'Unknown'),
                timestamp=doc.get('timestamp', ''),
                diff_type=doc.get('diff_type', 'block'),
                changes=DiffChanges(
                    added=[ChangeItem(**item) if isinstance(item, dict) else ChangeItem(content=str(item)) 
                           for item in changes.get('added', [])],
                    deleted=[ChangeItem(**item) if isinstance(item, dict) else ChangeItem(content=str(item)) 
                             for item in changes.get('deleted', [])],
                    modified=[ChangeItem(**item) if isinstance(item, dict) else ChangeItem(content=str(item)) 
                              for item in changes.get('modified', [])]
                ),
                added_count=len(changes.get('added', [])),
                deleted_count=len(changes.get('deleted', [])),
                modified_count=len(changes.get('modified', []))
            )
            diffs.append(diff_response)
        
        return NotionDiffListResponse(
            total=len(diffs),
            diffs=diffs,
            filters={'page_id': page_id, 'limit': limit}
        )
        
    except Exception as e:
        logger.error(f"Error fetching page diff history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notion/diffs/user/{user_id}", response_model=NotionDiffListResponse)
async def get_user_diff_activity(
    user_id: str,
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get all diffs by a specific user.
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        cursor = db["notion_content_diffs"].find(
            {"editor_id": user_id}
        ).sort("timestamp", -1).limit(limit)
        
        diffs = []
        async for doc in cursor:
            changes = doc.get('changes', {})
            
            diff_response = NotionDiffResponse(
                id=str(doc.get('_id', '')),
                document_id=doc.get('document_id', ''),
                document_title=doc.get('document_title', 'Untitled'),
                document_url=doc.get('document_url', ''),
                editor_id=doc.get('editor_id', ''),
                editor_name=doc.get('editor_name', 'Unknown'),
                timestamp=doc.get('timestamp', ''),
                diff_type=doc.get('diff_type', 'block'),
                changes=DiffChanges(
                    added=[ChangeItem(**item) if isinstance(item, dict) else ChangeItem(content=str(item)) 
                           for item in changes.get('added', [])],
                    deleted=[ChangeItem(**item) if isinstance(item, dict) else ChangeItem(content=str(item)) 
                             for item in changes.get('deleted', [])],
                    modified=[ChangeItem(**item) if isinstance(item, dict) else ChangeItem(content=str(item)) 
                              for item in changes.get('modified', [])]
                ),
                added_count=len(changes.get('added', [])),
                deleted_count=len(changes.get('deleted', [])),
                modified_count=len(changes.get('modified', []))
            )
            diffs.append(diff_response)
        
        return NotionDiffListResponse(
            total=len(diffs),
            diffs=diffs,
            filters={'user_id': user_id, 'limit': limit}
        )
        
    except Exception as e:
        logger.error(f"Error fetching user diff activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notion/diffs/stats", response_model=NotionDiffStatsResponse)
async def get_notion_diff_stats():
    """
    Get statistics about Notion diff collection.
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        stats = NotionDiffStatsResponse(
            tracked_pages=await db["notion_page_tracking"].count_documents({}),
            current_blocks=await db["notion_block_snapshots"].count_documents({"is_current": True}),
            total_block_snapshots=await db["notion_block_snapshots"].count_documents({}),
            total_comment_snapshots=await db["notion_comment_snapshots"].count_documents({}),
            total_diffs=await db["notion_content_diffs"].count_documents({}),
            block_diffs=await db["notion_content_diffs"].count_documents({"diff_type": "block"}),
            comment_diffs=await db["notion_content_diffs"].count_documents({"diff_type": "comment"})
        )
        
        return stats
        
    except Exception as e:
        logger.error(f"Error fetching Notion diff stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notion/tracked-pages")
async def get_tracked_pages(
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get list of tracked Notion pages.
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        cursor = db["notion_page_tracking"].find({}).sort(
            "last_snapshot_time", -1
        ).limit(limit)
        
        pages = []
        async for doc in cursor:
            pages.append({
                'page_id': doc.get('page_id', ''),
                'title': doc.get('title', 'Untitled'),
                'url': doc.get('url', ''),
                'last_edited_time': doc.get('last_edited_time', ''),
                'last_snapshot_time': str(doc.get('last_snapshot_time', ''))
            })
        
        return {
            'total': len(pages),
            'pages': pages
        }
        
    except Exception as e:
        logger.error(f"Error fetching tracked pages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Activity Feed Integration
# ============================================================================

@router.get("/notion/activities")
async def get_notion_activities(
    member_name: Optional[str] = Query(None, description="Filter by member name"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    Get Notion activities in unified activity format.
    
    This endpoint returns Notion diffs formatted like other activity sources
    (GitHub, Slack) for the unified activity feed.
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        # Build query
        query = {}
        
        if member_name:
            query['editor_name'] = {'$regex': member_name, '$options': 'i'}
        
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query['$gte'] = start_date
            if end_date:
                date_query['$lte'] = end_date
            query['timestamp'] = date_query
        
        # Get total
        total = await db["notion_content_diffs"].count_documents(query)
        
        # Get diffs and convert to activity format
        cursor = db["notion_content_diffs"].find(query).sort(
            "timestamp", -1
        ).skip(offset).limit(limit)
        
        activities = []
        async for doc in cursor:
            changes = doc.get('changes', {})
            diff_type = doc.get('diff_type', 'block')
            
            # Calculate additions/deletions like GitHub
            added_count = len(changes.get('added', []))
            deleted_count = len(changes.get('deleted', []))
            modified_count = len(changes.get('modified', []))
            
            # Sum up line changes from modified blocks
            added_lines = 0
            deleted_lines = 0
            for mod in changes.get('modified', []):
                if isinstance(mod, dict):
                    added_lines += len(mod.get('added_lines', []))
                    deleted_lines += len(mod.get('deleted_lines', []))
            
            activity = {
                'id': str(doc.get('_id', '')),
                'member_name': doc.get('editor_name', 'Unknown'),
                'source_type': 'notion',
                'activity_type': f'notion_{diff_type}',
                'timestamp': doc.get('timestamp', ''),
                'metadata': {
                    'page_id': doc.get('document_id', ''),
                    'page_title': doc.get('document_title', 'Untitled'),
                    'page_url': doc.get('document_url', ''),
                    'diff_type': diff_type,
                    # GitHub-like stats
                    'additions': added_count + added_lines,
                    'deletions': deleted_count + deleted_lines,
                    'blocks_added': added_count,
                    'blocks_deleted': deleted_count,
                    'blocks_modified': modified_count,
                    # Detailed changes for expanded view
                    'changes': changes
                }
            }
            activities.append(activity)
        
        return {
            'total': total,
            'activities': activities,
            'filters': {
                'member_name': member_name,
                'start_date': start_date,
                'end_date': end_date,
                'limit': limit,
                'offset': offset
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching Notion activities: {e}")
        raise HTTPException(status_code=500, detail=str(e))
