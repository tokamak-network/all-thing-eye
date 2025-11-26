"""
Notion Export API endpoints (MongoDB Version)

Provides API for searching and exporting Notion pages with full content
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import json
import io
import csv

from src.utils.logger import get_logger

# Get MongoDB manager instance
def get_mongo():
    from backend.main import mongo_manager
    return mongo_manager

logger = get_logger(__name__)

router = APIRouter()


# Response models
class NotionPageResponse(BaseModel):
    id: str
    title: str
    content: str
    content_length: int
    created_by: dict
    created_time: str
    last_edited_time: str
    url: Optional[str] = None


class NotionSearchResponse(BaseModel):
    total: int
    pages: List[NotionPageResponse]
    filters: dict


@router.get("/notion/search", response_model=NotionSearchResponse)
async def search_notion_pages(
    request: Request,
    title_contains: Optional[str] = Query(None, description="Filter by title (case-insensitive)"),
    author: Optional[str] = Query(None, description="Filter by author name"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    has_content: bool = Query(True, description="Only pages with content"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Search Notion pages with filters
    
    Returns:
        Paginated list of Notion pages with full content
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        # Build query
        query = {}
        
        # Filter by title
        if title_contains:
            query['title'] = {'$regex': title_contains, '$options': 'i'}
        
        # Filter by author
        if author:
            query['$or'] = [
                {'created_by.name': {'$regex': f"^{author}", '$options': 'i'}},
                {'created_by.email': {'$regex': author, '$options': 'i'}}
            ]
        
        # Filter by date
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter['$gte'] = datetime.fromisoformat(start_date)
            if end_date:
                date_filter['$lte'] = datetime.fromisoformat(end_date)
            query['created_time'] = date_filter
        
        # Filter by content existence
        if has_content:
            query['content_length'] = {'$gt': 0}
        
        # Count total
        total = await db['notion_pages'].count_documents(query)
        
        # Get pages
        pages_cursor = db['notion_pages'].find(query).sort('created_time', -1).skip(offset).limit(limit)
        
        pages = []
        async for page in pages_cursor:
            created_time = page.get('created_time')
            if isinstance(created_time, datetime):
                timestamp_str = created_time.isoformat() + 'Z' if created_time.tzinfo is None else created_time.isoformat()
            else:
                timestamp_str = str(created_time) if created_time else ''
            
            last_edited_time = page.get('last_edited_time')
            if isinstance(last_edited_time, datetime):
                last_edited_str = last_edited_time.isoformat() + 'Z' if last_edited_time.tzinfo is None else last_edited_time.isoformat()
            else:
                last_edited_str = str(last_edited_time) if last_edited_time else ''
            
            pages.append(NotionPageResponse(
                id=str(page['_id']),
                title=page.get('title', 'Untitled'),
                content=page.get('content', ''),
                content_length=page.get('content_length', 0),
                created_by=page.get('created_by', {}),
                created_time=timestamp_str,
                last_edited_time=last_edited_str,
                url=page.get('url')
            ))
        
        return NotionSearchResponse(
            total=total,
            pages=pages,
            filters={
                'title_contains': title_contains,
                'author': author,
                'start_date': start_date,
                'end_date': end_date,
                'has_content': has_content,
                'limit': limit,
                'offset': offset
            }
        )
        
    except Exception as e:
        logger.error(f"Error searching Notion pages: {e}")
        raise HTTPException(status_code=500, detail="Failed to search Notion pages")


@router.get("/notion/export")
async def export_notion_pages(
    request: Request,
    format: str = Query("json", regex="^(json|jsonl|csv)$"),
    title_contains: Optional[str] = Query(None),
    author: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    has_content: bool = Query(True),
    limit: int = Query(10000, ge=1, le=100000)
):
    """
    Export Notion pages with full content
    
    Args:
        format: Export format (json, jsonl, csv)
        title_contains: Filter by title
        author: Filter by author
        start_date: Start date filter
        end_date: End date filter
        has_content: Only pages with content
        limit: Maximum number of pages
    
    Returns:
        File download response
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        # Build query (same as search)
        query = {}
        
        if title_contains:
            query['title'] = {'$regex': title_contains, '$options': 'i'}
        
        if author:
            query['$or'] = [
                {'created_by.name': {'$regex': f"^{author}", '$options': 'i'}},
                {'created_by.email': {'$regex': author, '$options': 'i'}}
            ]
        
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter['$gte'] = datetime.fromisoformat(start_date)
            if end_date:
                date_filter['$lte'] = datetime.fromisoformat(end_date)
            query['created_time'] = date_filter
        
        if has_content:
            query['content_length'] = {'$gt': 0}
        
        # Get pages
        pages_cursor = db['notion_pages'].find(query).sort('created_time', -1).limit(limit)
        
        pages = []
        async for page in pages_cursor:
            pages.append({
                'id': str(page['_id']),
                'notion_id': page.get('notion_id', ''),
                'title': page.get('title', 'Untitled'),
                'content': page.get('content', ''),
                'content_length': page.get('content_length', 0),
                'author': page.get('created_by', {}).get('name', 'Unknown'),
                'author_email': page.get('created_by', {}).get('email', ''),
                'created_time': page.get('created_time').isoformat() if page.get('created_time') else '',
                'last_edited_time': page.get('last_edited_time').isoformat() if page.get('last_edited_time') else '',
                'url': page.get('url', '')
            })
        
        # Generate filename
        filename_base = 'notion_export'
        if title_contains:
            filename_base += f"_{title_contains.replace(' ', '_')}"
        
        if format == 'json':
            # JSON export
            output = json.dumps(pages, indent=2, ensure_ascii=False)
            
            return StreamingResponse(
                iter([output]),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename={filename_base}.json"
                }
            )
        
        elif format == 'jsonl':
            # JSONL export (one JSON object per line - ideal for AI training)
            output = '\n'.join([json.dumps(page, ensure_ascii=False) for page in pages])
            
            return StreamingResponse(
                iter([output]),
                media_type="application/x-ndjson",
                headers={
                    "Content-Disposition": f"attachment; filename={filename_base}.jsonl"
                }
            )
        
        else:  # csv
            # CSV export
            output = io.StringIO()
            fieldnames = ['id', 'title', 'author', 'author_email', 'created_time', 
                         'content_length', 'content', 'url']
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            for page in pages:
                writer.writerow({
                    'id': page['id'],
                    'title': page['title'],
                    'author': page['author'],
                    'author_email': page['author_email'],
                    'created_time': page['created_time'],
                    'content_length': page['content_length'],
                    'content': page['content'],
                    'url': page['url']
                })
            
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename={filename_base}.csv"
                }
            )
        
    except Exception as e:
        logger.error(f"Error exporting Notion pages: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to export Notion pages: {str(e)}")


@router.get("/notion/authors")
async def get_notion_authors(request: Request):
    """
    Get list of unique authors from Notion pages
    
    Returns:
        List of author names and emails
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db
        
        # Aggregate unique authors
        pipeline = [
            {'$match': {'created_by.name': {'$ne': ''}}},
            {'$group': {
                '_id': {
                    'name': '$created_by.name',
                    'email': '$created_by.email'
                },
                'page_count': {'$sum': 1}
            }},
            {'$sort': {'page_count': -1}}
        ]
        
        authors = []
        async for result in db['notion_pages'].aggregate(pipeline):
            author_info = result['_id']
            authors.append({
                'name': author_info.get('name', ''),
                'email': author_info.get('email', ''),
                'page_count': result['page_count']
            })
        
        return {
            'authors': authors,
            'total': len(authors)
        }
        
    except Exception as e:
        logger.error(f"Error fetching Notion authors: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch authors")

