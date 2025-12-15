"""
Exports API endpoints for MongoDB

Provides data export functionality (CSV, JSON)
"""

from fastapi import APIRouter, HTTPException, Query, Request, Depends
from fastapi.responses import StreamingResponse
from typing import Optional, List
from pydantic import BaseModel
import json
import csv
import io
import zipfile
from datetime import datetime, timedelta
from bson import ObjectId

from src.utils.logger import get_logger
from src.utils.toon_encoder import encode_toon
from backend.middleware.jwt_auth import require_admin

logger = get_logger(__name__)

router = APIRouter()


# Pydantic models
class TableSelection(BaseModel):
    source: str
    collection: Optional[str] = None
    table: Optional[str] = None  # For backward compatibility with frontend
    
    def get_collection_name(self) -> str:
        """Get collection name (supports both 'collection' and 'table' field names)"""
        return self.collection or self.table or ""


class BulkExportRequest(BaseModel):
    tables: List[TableSelection]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    format: str = 'csv'  # 'csv', 'json', or 'toon'


def get_mongo():
    """Get MongoDB manager from main.py"""
    from backend.main import mongo_manager
    return mongo_manager


# Collection name mapping (source -> collections)
COLLECTION_MAP = {
    'main': ['members', 'member_identifiers'],
    'github': ['github_members', 'github_repositories', 'github_commits', 
               'github_pull_requests', 'github_issues'],
    'slack': ['slack_channels', 'slack_messages'],
    'notion': ['notion_pages', 'notion_databases', 'notion_comments'],
    'google_drive': ['drive_files', 'drive_activities'],
    'other': ['recordings'],  # Changed from 'shared' to 'other' to match Database page grouping
    'gemini': ['recordings_daily']  # AI-processed daily analyses
}


@router.get("/tables")
async def get_tables(request: Request):
    """
    Get list of all available collections from MongoDB
    
    Returns:
        Dict with sources and their collections
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db  # Main database
        shared_db = mongo.shared_async_db  # Shared database
        
        # Get gemini database
        from backend.api.v1.ai_processed import get_gemini_db
        gemini_db_sync = get_gemini_db()
        gemini_collections = gemini_db_sync.list_collection_names()
        
        # Get collection names from both databases
        main_collections = await db.list_collection_names()
        shared_collections = await shared_db.list_collection_names()
        
        # Organize by source
        collections_by_source = {}
        
        for source, expected_collections in COLLECTION_MAP.items():
            if source == 'other':
                # Check shared database for 'other' collections
                existing = [col for col in expected_collections if col in shared_collections]
            elif source == 'gemini':
                # Check gemini database
                existing = [col for col in expected_collections if col in gemini_collections]
            else:
                # Check main database
                existing = [col for col in expected_collections if col in main_collections]
            
            if existing:
                collections_by_source[source] = existing
        
        return {
            "sources": collections_by_source,
            "total_sources": len(collections_by_source),
            "total_tables": sum(len(cols) for cols in collections_by_source.values())
        }
        
    except Exception as e:
        logger.error(f"Error getting collections: {e}")
        raise HTTPException(status_code=500, detail="Failed to get collections list")


@router.get("/tables/{source}/{collection}/csv")
async def export_collection_csv(
    request: Request,
    source: str,
    collection: str,
    limit: int = Query(None, ge=1, le=100000, description="Maximum documents to export"),
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)")
):
    """
    Export a specific collection as CSV
    
    Args:
        source: Database source (main, github, slack, google_drive, notion, other)
        collection: Collection name
        limit: Maximum number of documents to export (optional)
        start_date: Filter records from this date onwards (optional)
        end_date: Filter records up to this date (optional)
    
    Returns:
        CSV file download
    """
    try:
        mongo = get_mongo()
        
        # Select database based on source
        if source == 'other':
            db = mongo.shared_async_db
        elif source == 'gemini':
            # For gemini database, use sync operations
            from backend.api.v1.ai_processed import get_gemini_db
            gemini_db_sync = get_gemini_db()
            # Validate collection exists in gemini database
            all_collections = gemini_db_sync.list_collection_names()
            if collection not in all_collections:
                raise HTTPException(
                    status_code=404,
                    detail=f"Collection '{collection}' not found in gemini database"
                )
            db = None  # Will handle separately with sync operations
        else:
            db = mongo.async_db
        
        # Validate source
        if source not in COLLECTION_MAP:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid source. Must be one of: {', '.join(COLLECTION_MAP.keys())}"
            )
        
        # Validate collection exists (for non-gemini databases)
        if db:
            all_collections = await db.list_collection_names()
            if collection not in all_collections:
                raise HTTPException(
                    status_code=404,
                    detail=f"Collection '{collection}' not found"
                )
        
        # Build query filter
        query_filter = {}
        
        # Date filtering
        if start_date or end_date:
            # Determine timestamp field based on collection type
            if source == 'gemini' and collection == 'recordings_daily':
                # For recordings_daily, use target_date field
                date_filter = {}
                if start_date:
                    date_filter['$gte'] = start_date
                if end_date:
                    date_filter['$lte'] = end_date
                if date_filter:
                    query_filter['target_date'] = date_filter
            else:
                # For other collections, use common timestamp fields
                timestamp_fields = ['timestamp', 'posted_at', 'created_at', 'updated_at', 'committed_at', 'target_date']
                timestamp_fields = ['timestamp', 'posted_at', 'created_at', 'updated_at', 'committed_at', 'target_date']
                timestamp_field = None
                
                # Check which timestamp field exists in the collection
                if source == 'gemini':
                    sample_doc = gemini_db_sync[collection].find_one({})
                else:
                    sample_doc = await db[collection].find_one({})
            if sample_doc:
                for field in timestamp_fields:
                    if field in sample_doc:
                        timestamp_field = field
                        break
            
            if timestamp_field:
                date_filter = {}
                if start_date:
                    try:
                        date_filter['$gte'] = datetime.fromisoformat(start_date)
                    except ValueError:
                        date_filter['$gte'] = start_date
                if end_date:
                    try:
                        # Add 1 day to include the entire end date
                        end_dt = datetime.fromisoformat(end_date) + timedelta(days=1)
                        date_filter['$lt'] = end_dt
                    except ValueError:
                        date_filter['$lte'] = end_date + "T23:59:59"
                
                if date_filter:
                    query_filter[timestamp_field] = date_filter
        
        # Query MongoDB
        if source == 'gemini':
            # Use sync operations for gemini database
            cursor = gemini_db_sync[collection].find(query_filter)
            if limit:
                cursor = cursor.limit(limit)
            documents = list(cursor)
        else:
            cursor = db[collection].find(query_filter)
            if limit:
                cursor = cursor.limit(limit)
            documents = await cursor.to_list(length=limit or 10000)
        
        if not documents:
            # Empty collection - return empty CSV with basic header
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['_id', 'no_data'])
            csv_content = output.getvalue()
            row_count = 0
        else:
            # Convert documents to CSV-friendly format
            rows = []
            all_keys = set()
            
            for doc in documents:
                # Convert ObjectId to string
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])
                
                # Convert nested objects to JSON strings
                flat_doc = {}
                for key, value in doc.items():
                    if isinstance(value, (dict, list)):
                        flat_doc[key] = json.dumps(value, default=str, ensure_ascii=False)
                    elif isinstance(value, ObjectId):
                        flat_doc[key] = str(value)
                    elif isinstance(value, datetime):
                        flat_doc[key] = value.isoformat()
                    else:
                        flat_doc[key] = value
                    
                    all_keys.add(key)
                
                rows.append(flat_doc)
            
            # Write CSV
            output = io.StringIO()
            fieldnames = sorted(list(all_keys))
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            csv_content = output.getvalue()
            row_count = len(rows)
        
        # Generate filename
        filename = f"{source}_{collection}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        logger.info(f"Exported {row_count} documents from {source}.{collection}")
        
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting collection {source}.{collection}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export collection: {str(e)}"
        )


@router.get("/tables/{source}/{collection}/toon")
async def export_collection_toon(
    request: Request,
    source: str,
    collection: str,
    limit: int = Query(None, ge=1, le=100000, description="Maximum documents to export"),
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    delimiter: str = Query(',', description="Delimiter for array values (comma, tab, pipe)")
):
    """
    Export a specific collection as TOON format
    
    TOON (Token-Oriented Object Notation) is optimized for LLM prompts:
    - 20-40% fewer tokens than JSON
    - Explicit structure with array lengths and field headers
    - Human-readable and self-documenting
    
    Args:
        source: Database source (main, github, slack, google_drive, notion, other)
        collection: Collection name
        limit: Maximum number of documents to export (optional)
        start_date: Filter records from this date onwards (optional)
        end_date: Filter records up to this date (optional)
        delimiter: Delimiter for array values (',' | '\t' | '|')
    
    Returns:
        TOON file download
    """
    try:
        mongo = get_mongo()
        
        # Select database based on source
        if source == 'other':
            db = mongo.shared_async_db
        else:
            db = mongo.async_db
        
        # Validate source
        if source not in COLLECTION_MAP:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid source. Must be one of: {', '.join(COLLECTION_MAP.keys())}"
            )
        
        # Validate collection exists
        all_collections = await db.list_collection_names()
        if collection not in all_collections:
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{collection}' not found"
            )
        
        # Normalize delimiter
        delimiter_map = {'comma': ',', 'tab': '\t', 'pipe': '|', ',': ',', '\t': '\t', '|': '|'}
        actual_delimiter = delimiter_map.get(delimiter.lower(), ',')
        
        # Build query filter (same as CSV export)
        query_filter = {}
        
        # Date filtering
        if start_date or end_date:
            timestamp_fields = ['timestamp', 'posted_at', 'created_at', 'updated_at', 'committed_at']
            timestamp_field = None
            
            sample_doc = await db[collection].find_one({})
            if sample_doc:
                for field in timestamp_fields:
                    if field in sample_doc:
                        timestamp_field = field
                        break
            
            if timestamp_field:
                date_filter = {}
                if start_date:
                    try:
                        date_filter['$gte'] = datetime.fromisoformat(start_date)
                    except ValueError:
                        date_filter['$gte'] = start_date
                if end_date:
                    try:
                        # Add 1 day to include the entire end date
                        end_dt = datetime.fromisoformat(end_date) + timedelta(days=1)
                        date_filter['$lt'] = end_dt
                    except ValueError:
                        date_filter['$lte'] = end_date + "T23:59:59"
                
                if date_filter:
                    query_filter[timestamp_field] = date_filter
        
        # Query MongoDB
        cursor = db[collection].find(query_filter)
        if limit:
            cursor = cursor.limit(limit)
        
        documents = await cursor.to_list(length=limit or 10000)
        
        if not documents:
            # Empty collection
            toon_content = f"{collection}[0]:"
            row_count = 0
        else:
            # Convert documents to TOON-friendly format
            rows = []
            
            for doc in documents:
                # Convert ObjectId to string
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])
                
                # Convert other special types
                clean_doc = {}
                for key, value in doc.items():
                    if isinstance(value, ObjectId):
                        clean_doc[key] = str(value)
                    elif isinstance(value, datetime):
                        clean_doc[key] = value.isoformat()
                    else:
                        clean_doc[key] = value
                
                rows.append(clean_doc)
            
            # Wrap in collection name for TOON
            toon_data = {collection: rows}
            
            # Encode to TOON format
            toon_content = encode_toon(toon_data, indent=2, delimiter=actual_delimiter)
            row_count = len(rows)
        
        # Generate filename
        filename = f"{source}_{collection}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.toon"
        
        logger.info(f"Exported {row_count} documents from {source}.{collection} as TOON")
        
        return StreamingResponse(
            iter([toon_content]),
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting collection {source}.{collection} as TOON: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export collection as TOON: {str(e)}"
        )


@router.get("/members")
async def export_members(
    request: Request,
    format: str = Query("csv", regex="^(csv|json)$")
):
    """
    Export members data
    
    Args:
        format: Export format (csv or json)
    
    Returns:
        File download response
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db  # Use async_db for asynchronous operations
        
        # Query members collection
        cursor = db['members'].find({}).sort('name', 1)
        members_docs = await cursor.to_list(length=10000)
        
        members = []
        for doc in members_docs:
            members.append({
                'id': str(doc['_id']),
                'name': doc.get('name'),
                'email': doc.get('email'),
                'role': doc.get('role'),
                'team': doc.get('team'),
                'created_at': doc.get('created_at').isoformat() if doc.get('created_at') else None
            })
        
        if format == 'json':
            # JSON export
            output = json.dumps(members, indent=2, ensure_ascii=False)
            
            return StreamingResponse(
                iter([output]),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=members_{datetime.now().strftime('%Y%m%d')}.json"
                }
            )
        
        else:
            # CSV export
            output = io.StringIO()
            fieldnames = ['id', 'name', 'email', 'role', 'team', 'created_at']
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(members)
            
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=members_{datetime.now().strftime('%Y%m%d')}.csv"
                }
            )
        
    except Exception as e:
        logger.error(f"Error exporting members: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to export members: {str(e)}")


@router.get("/activities")
async def export_activities(
    request: Request,
    format: str = Query("csv", regex="^(csv|json)$"),
    source_type: Optional[str] = Query(None),
    activity_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(10000, ge=1, le=100000)
):
    """
    Export activities data from source collections (not member_activities)
    
    Args:
        format: Export format (csv or json)
        source_type: Filter by source
        activity_type: Filter by activity type
        start_date: Start date filter
        end_date: End date filter
        limit: Maximum number of records
    
    Returns:
        File download response
    """
    try:
        # Import helper functions from activities_mongo
        from backend.api.v1.activities_mongo import (
            load_member_mappings,
            get_identifiers_for_member,
            get_mapped_member_name
        )
        from datetime import timezone
        
        mongo = get_mongo()
        db = mongo.async_db
        
        # Load member mappings
        member_mappings = await load_member_mappings(db)
        
        # Determine which sources to query
        sources_to_query = [source_type] if source_type else ['github', 'slack', 'notion', 'drive', 'recordings', 'recordings_daily']
        
        # Build date filter
        date_filter = {}
        if start_date:
            start_str = start_date.replace('Z', '+00:00') if start_date.endswith('Z') else start_date
            start_dt = datetime.fromisoformat(start_str)
            if start_dt.tzinfo is not None:
                start_dt = start_dt.astimezone(timezone.utc).replace(tzinfo=None)
            date_filter['$gte'] = start_dt
        if end_date:
            end_str = end_date.replace('Z', '+00:00') if end_date.endswith('Z') else end_date
            end_dt = datetime.fromisoformat(end_str)
            if end_dt.tzinfo is not None:
                end_dt = end_dt.astimezone(timezone.utc).replace(tzinfo=None)
            date_filter['$lte'] = end_dt
        
        activities = []
        
        # Query each source collection directly (same logic as activities_mongo.py)
        for source in sources_to_query:
            if source == 'github':
                # GitHub commits
                if not activity_type or activity_type == 'commit':
                    commits = db["github_commits"]
                    query = {}
                    if date_filter:
                        query['date'] = date_filter
                    
                    async for commit in commits.find(query).sort("date", -1).limit(limit):
                        commit_date = commit.get('date')
                        if isinstance(commit_date, datetime):
                            timestamp_str = commit_date.isoformat() + 'Z' if commit_date.tzinfo is None else commit_date.isoformat()
                        else:
                            timestamp_str = str(commit_date) if commit_date else ''
                        
                        github_username = commit.get('author_name', '')
                        member_name = get_mapped_member_name(member_mappings, 'github', github_username)
                        
                        metadata = {
                            'sha': commit.get('sha'),
                            'message': commit.get('message'),
                            'repository': commit.get('repository', ''),
                            'additions': commit.get('additions', 0),
                            'deletions': commit.get('deletions', 0),
                            'url': commit.get('url')
                        }
                        
                        activities.append({
                            'id': str(commit['_id']),
                            'member_name': member_name,
                            'source_type': 'github',
                            'activity_type': 'commit',
                            'timestamp': timestamp_str,
                            'activity_id': f"github:commit:{commit.get('sha')}",
                            'metadata': metadata if format == 'json' else json.dumps(metadata, ensure_ascii=False, default=str)
                        })
                
                # GitHub PRs
                if not activity_type or activity_type == 'pull_request':
                    prs = db["github_pull_requests"]
                    query = {}
                    if date_filter:
                        query['created_at'] = date_filter
                    
                    async for pr in prs.find(query).sort("created_at", -1).limit(limit):
                        created_at = pr.get('created_at')
                        if isinstance(created_at, datetime):
                            timestamp_str = created_at.isoformat() + 'Z' if created_at.tzinfo is None else created_at.isoformat()
                        else:
                            timestamp_str = str(created_at) if created_at else ''
                        
                        github_username = pr.get('author_login', '')
                        member_name = get_mapped_member_name(member_mappings, 'github', github_username)
                        
                        metadata = {
                            'repository': pr.get('repository_name', ''),
                            'title': pr.get('title'),
                            'number': pr.get('number'),
                            'state': pr.get('state'),
                            'url': pr.get('url')
                        }
                        
                        activities.append({
                            'id': str(pr['_id']),
                            'member_name': member_name,
                            'source_type': 'github',
                            'activity_type': 'pull_request',
                            'timestamp': timestamp_str,
                            'activity_id': f"github:pr:{pr.get('repository_name')}:{pr.get('number')}",
                            'metadata': metadata if format == 'json' else json.dumps(metadata, ensure_ascii=False, default=str)
                        })
                
                # GitHub Issues
                if not activity_type or activity_type == 'issue':
                    issues = db["github_issues"]
                    query = {}
                    if date_filter:
                        query['created_at'] = date_filter
                    
                    async for issue in issues.find(query).sort("created_at", -1).limit(limit):
                        created_at = issue.get('created_at')
                        if isinstance(created_at, datetime):
                            timestamp_str = created_at.isoformat() + 'Z' if created_at.tzinfo is None else created_at.isoformat()
                        else:
                            timestamp_str = str(created_at) if created_at else ''
                        
                        github_username = issue.get('author_login', '')
                        member_name = get_mapped_member_name(member_mappings, 'github', github_username)
                        
                        metadata = {
                            'repository': issue.get('repository_name', ''),
                            'title': issue.get('title'),
                            'number': issue.get('number'),
                            'state': issue.get('state'),
                            'url': issue.get('url')
                        }
                        
                        activities.append({
                            'id': str(issue['_id']),
                            'member_name': member_name,
                            'source_type': 'github',
                            'activity_type': 'issue',
                            'timestamp': timestamp_str,
                            'activity_id': f"github:issue:{issue.get('repository_name')}:{issue.get('number')}",
                            'metadata': metadata if format == 'json' else json.dumps(metadata, ensure_ascii=False, default=str)
                        })
            
            elif source == 'slack':
                # Slack messages
                if not activity_type or activity_type == 'message':
                    messages = db["slack_messages"]
                    query = {}
                    if date_filter:
                        query['posted_at'] = date_filter
                    
                    async for msg in messages.find(query).sort("posted_at", -1).limit(limit):
                        posted_at = msg.get('posted_at')
                        if isinstance(posted_at, datetime):
                            timestamp_str = posted_at.isoformat() + 'Z' if posted_at.tzinfo is None else posted_at.isoformat()
                        else:
                            timestamp_str = str(posted_at) if posted_at else ''
                        
                        slack_user_id = msg.get('user_id', '')
                        member_name = get_mapped_member_name(member_mappings, 'slack', slack_user_id)
                        
                        metadata = {
                            'channel_id': msg.get('channel_id'),
                            'channel_name': msg.get('channel_name'),
                            'text': msg.get('text', ''),
                            'thread_ts': msg.get('thread_ts'),
                            'reactions': msg.get('reactions', [])
                        }
                        
                        activities.append({
                            'id': str(msg['_id']),
                            'member_name': member_name,
                            'member_name': member_name,
                            'source_type': 'slack',
                            'activity_type': 'message',
                            'timestamp': timestamp_str,
                            'activity_id': f"slack:message:{msg.get('channel_id')}:{msg.get('ts')}",
                            'metadata': metadata if format == 'json' else json.dumps(metadata, ensure_ascii=False, default=str)
                        })
            elif source == 'notion':
                # Notion pages
                if not activity_type or activity_type == 'page':
                    pages = db["notion_pages"]
                    query = {}
                    if date_filter:
                        query['last_edited_time'] = date_filter
                    
                    async for page in pages.find(query).sort("last_edited_time", -1).limit(limit):
                        last_edited = page.get('last_edited_time')
                        if isinstance(last_edited, datetime):
                            timestamp_str = last_edited.isoformat() + 'Z' if last_edited.tzinfo is None else last_edited.isoformat()
                        else:
                            timestamp_str = str(last_edited) if last_edited else ''
                        
                        notion_user_id = page.get('created_by', {}).get('id', '') if isinstance(page.get('created_by'), dict) else ''
                        member_name = get_mapped_member_name(member_mappings, 'notion', notion_user_id)
                        
                        metadata = {
                            'page_id': page.get('page_id'),
                            'title': page.get('title'),
                            'url': page.get('url'),
                            'database_id': page.get('database_id')
                        }
                        
                        activities.append({
                            'id': str(page['_id']),
                            'member_name': member_name,
                            'source_type': 'notion',
                            'activity_type': 'page',
                            'timestamp': timestamp_str,
                            'activity_id': f"notion:page:{page.get('page_id')}",
                            'metadata': metadata if format == 'json' else json.dumps(metadata, ensure_ascii=False, default=str)
                        })
            
            elif source == 'drive':
                # Drive activities
                if not activity_type or activity_type == 'activity':
                    drive_activities = db["drive_activities"]
                    query = {}
                    if date_filter:
                        query['time'] = date_filter
                    
                    async for activity in drive_activities.find(query).sort("time", -1).limit(limit):
                        time = activity.get('time')
                        if isinstance(time, datetime):
                            timestamp_str = time.isoformat() + 'Z' if time.tzinfo is None else time.isoformat()
                        else:
                            timestamp_str = str(time) if time else ''
                        
                        actor_email = activity.get('actor_email', '')
                        member_name = get_mapped_member_name(member_mappings, 'drive', actor_email)
                        
                        metadata = {
                            'activity_type': activity.get('activity_type'),
                            'file_id': activity.get('file_id'),
                            'file_name': activity.get('file_name'),
                            'target': activity.get('target')
                        }
                        
                        activities.append({
                            'id': str(activity['_id']),
                            'member_name': member_name,
                            'source_type': 'drive',
                            'activity_type': activity.get('activity_type', 'activity'),
                            'timestamp': timestamp_str,
                            'activity_id': activity.get('activity_id', f"drive:{activity.get('file_id')}"),
                            'metadata': metadata if format == 'json' else json.dumps(metadata, ensure_ascii=False, default=str)
                        })
        
            elif source == 'recordings':
                # Recordings from Gemini database
                try:
                    from backend.api.v1.ai_processed import get_gemini_db
                    gemini_db = get_gemini_db()
                    recordings_col = gemini_db["recordings"]
                    
                    query = {}
                    if date_filter:
                        query['meeting_date'] = date_filter
                    
                    # Use sync cursor for gemini database
                    recordings_cursor = recordings_col.find(query).sort("meeting_date", -1).limit(limit)
                    
                    for recording in recordings_cursor:
                        meeting_date = recording.get('meeting_date')
                        if isinstance(meeting_date, datetime):
                            timestamp_str = meeting_date.isoformat() + 'Z' if meeting_date.tzinfo is None else meeting_date.isoformat()
                        else:
                            timestamp_str = str(meeting_date) if meeting_date else ''
                        
                        participants = recording.get('participants', [])
                        # For recordings, use first participant as member_name
                        member_name = participants[0] if participants else 'Unknown'
                        
                        metadata = {
                            'meeting_id': recording.get('meeting_id'),
                            'meeting_title': recording.get('meeting_title'),
                            'participants': participants,
                            'participant_count': len(participants)
                        }
                        
                        activities.append({
                            'id': str(recording['_id']),
                            'member_name': member_name,
                            'source_type': 'recordings',
                            'activity_type': 'meeting',
                            'timestamp': timestamp_str,
                            'activity_id': f"recordings:meeting:{recording.get('meeting_id')}",
                            'metadata': metadata if format == 'json' else json.dumps(metadata, ensure_ascii=False, default=str)
                        })
                except Exception as e:
                    logger.error(f"Error fetching recordings data: {e}")
            
            elif source == 'recordings_daily':
                # Daily analysis from Gemini database
                try:
                    from backend.api.v1.ai_processed import get_gemini_db
                    gemini_db = get_gemini_db()
                    recordings_daily_col = gemini_db["recordings_daily"]
                    
                    query = {}
                    if date_filter:
                        # target_date is string format, need to convert date_filter
                        string_date_filter = {}
                        for op, value in date_filter.items():
                            if isinstance(value, datetime):
                                string_date_filter[op] = value.strftime('%Y-%m-%d')
                            else:
                                string_date_filter[op] = value
                        query['target_date'] = string_date_filter
                    
                    # Use sync cursor for gemini database
                    daily_cursor = recordings_daily_col.find(query).sort("target_date", -1).limit(limit)
                    
                    for daily in daily_cursor:
                        timestamp = daily.get('timestamp')
                        if isinstance(timestamp, datetime):
                            timestamp_str = timestamp.isoformat() + 'Z' if timestamp.tzinfo is None else timestamp.isoformat()
                        else:
                            timestamp_str = daily.get('target_date', '')
                        
                        analysis = daily.get('analysis', {})
                        meeting_count = daily.get('meeting_count', 0)
                        
                        metadata = {
                            'target_date': daily.get('target_date'),
                            'meeting_count': meeting_count,
                            'total_meeting_time': daily.get('total_meeting_time'),
                            'meeting_titles': daily.get('meeting_titles', []),
                            'status': daily.get('status')
                        }
                        
                        activities.append({
                            'id': str(daily['_id']),
                            'member_name': 'System',
                            'source_type': 'recordings_daily',
                            'activity_type': 'daily_analysis',
                            'timestamp': timestamp_str,
                            'activity_id': f"recordings_daily:{daily.get('target_date')}",
                            'metadata': metadata if format == 'json' else json.dumps(metadata, ensure_ascii=False, default=str)
                        })
                except Exception as e:
                    logger.error(f"Error fetching recordings_daily data: {e}")
        
        # Sort all activities by timestamp (newest first)
        activities.sort(key=lambda x: x['timestamp'] or '', reverse=True)
        
        # Apply limit
        activities = activities[:limit]
        
        filename_base = f"activities_{datetime.now().strftime('%Y%m%d')}"
        if source_type:
            filename_base += f"_{source_type}"
        
        if format == 'json':
            # JSON export
            output = json.dumps(activities, indent=2, ensure_ascii=False)
            
            return StreamingResponse(
                iter([output]),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename={filename_base}.json"
                }
            )
        
        else:
            # CSV export
            output = io.StringIO()
            fieldnames = ['id', 'member_name', 'source_type', 'activity_type', 
                         'timestamp', 'activity_id', 'metadata']
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(activities)
            
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename={filename_base}.csv"
                }
            )
        
    except Exception as e:
        logger.error(f"Error exporting activities: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to export activities: {str(e)}")


@router.get("/projects/{project_key}")
async def export_project_data(
    request: Request,
    project_key: str,
    format: str = Query("csv", regex="^(csv|json)$"),
    data_type: str = Query("all", regex="^(all|slack|github|google_drive)$")
):
    """
    Export project-specific data
    
    Args:
        project_key: Project identifier
        format: Export format (csv or json)
        data_type: Type of data to export
    
    Returns:
        File download response
    """
    try:
        config = request.app.state.config
        projects_config = config.get('projects', {})
        
        if project_key not in projects_config:
            raise HTTPException(status_code=404, detail="Project not found")
        
        project_data = projects_config[project_key]
        slack_channel_id = project_data.get('slack_channel_id')
        
        mongo = get_mongo()
        db = mongo.db
        export_data = {}
        
        # Export Slack data
        if data_type in ['all', 'slack'] and slack_channel_id:
            cursor = db['slack_messages'].find({
                'channel_id': slack_channel_id,
                'channel_name': {'$ne': 'tokamak-partners'}  # Exclude private channel
            }).sort('timestamp', -1)
            
            messages_docs = await cursor.to_list(length=10000)
            
            messages = []
            for doc in messages_docs:
                messages.append({
                    'id': str(doc['_id']),
                    'user_id': doc.get('user_id'),
                    'channel_id': doc.get('channel_id'),
                    'ts': doc.get('ts'),
                    'timestamp': doc.get('timestamp').isoformat() if doc.get('timestamp') else None,
                    'text': doc.get('text'),
                    'thread_ts': doc.get('thread_ts'),
                    'message_type': doc.get('message_type')
                })
            
            export_data['slack_messages'] = messages
        
        filename = f"{project_key}_data_{datetime.now().strftime('%Y%m%d')}"
        
        if format == 'json':
            output = json.dumps(export_data, indent=2, ensure_ascii=False)
            
            return StreamingResponse(
                iter([output]),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}.json"
                }
            )
        
        else:
            # CSV export (only first data type)
            if 'slack_messages' in export_data:
                output = io.StringIO()
                if export_data['slack_messages']:
                    fieldnames = list(export_data['slack_messages'][0].keys())
                    writer = csv.DictWriter(output, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(export_data['slack_messages'])
                
                return StreamingResponse(
                    iter([output.getvalue()]),
                    media_type="text/csv",
                    headers={
                        "Content-Disposition": f"attachment; filename={filename}_slack.csv"
                    }
                )
        
        raise HTTPException(status_code=404, detail="No data found for export")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting project data: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to export project data: {str(e)}")


@router.post("/bulk")
async def export_bulk_collections(
    request: Request,
    bulk_request: BulkExportRequest
):
    """
    Export multiple collections as a ZIP file
    
    Supports multiple export formats:
    - CSV: Traditional comma-separated values (default)
    - JSON: Structured JSON format
    - TOON: Token-Oriented Object Notation (LLM-optimized, 20-40% fewer tokens)
    
    Args:
        bulk_request: List of collection selections with optional date range and format
        
    Returns:
        ZIP file containing files for each selected collection in the specified format
    """
    if not bulk_request.tables:
        raise HTTPException(status_code=400, detail="No collections selected")
    
    try:
        mongo = get_mongo()
        start_date = bulk_request.start_date
        end_date = bulk_request.end_date
        
        # Create in-memory ZIP file
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for selection in bulk_request.tables:
                source = selection.source
                collection = selection.get_collection_name()
                
                try:
                    # Select database based on source
                    if source == 'other':
                        db = mongo.shared_async_db
                    else:
                        db = mongo.async_db
                    
                    # Build query filter
                    query_filter = {}
                    
                    # Date filtering
                    if start_date or end_date:
                        timestamp_fields = ['timestamp', 'posted_at', 'created_at', 'updated_at', 'committed_at']
                        timestamp_field = None
                        
                        # Check which timestamp field exists
                        sample_doc = await db[collection].find_one({})
                        if sample_doc:
                            for field in timestamp_fields:
                                if field in sample_doc:
                                    timestamp_field = field
                                    break
                        
                        if timestamp_field:
                            date_filter = {}
                            if start_date:
                                try:
                                    date_filter['$gte'] = datetime.fromisoformat(start_date)
                                except ValueError:
                                    date_filter['$gte'] = start_date
                            if end_date:
                                try:
                                    # Add 1 day to include the entire end date
                                    end_dt = datetime.fromisoformat(end_date) + timedelta(days=1)
                                    date_filter['$lt'] = end_dt
                                except ValueError:
                                    date_filter['$lte'] = end_date + "T23:59:59"
                            
                            if date_filter:
                                query_filter[timestamp_field] = date_filter
                    
                    # Query collection
                    cursor = db[collection].find(query_filter).limit(10000)
                    documents = await cursor.to_list(length=10000)
                    
                    if not documents:
                        logger.warning(f"No data in {source}.{collection}")
                        continue
                    
                    # Prepare documents (common processing)
                    rows = []
                    
                    for doc in documents:
                        # Convert ObjectId to string
                        if '_id' in doc:
                            doc['_id'] = str(doc['_id'])
                        
                        # Convert special types
                        clean_doc = {}
                        for key, value in doc.items():
                            if isinstance(value, ObjectId):
                                clean_doc[key] = str(value)
                            elif isinstance(value, datetime):
                                clean_doc[key] = value.isoformat()
                            elif bulk_request.format == 'csv' and isinstance(value, (dict, list)):
                                # Flatten for CSV
                                clean_doc[key] = json.dumps(value, default=str, ensure_ascii=False)
                            else:
                                clean_doc[key] = value
                        
                        rows.append(clean_doc)
                    
                    # Export based on format
                    if bulk_request.format == 'toon':
                        # TOON format
                        toon_data = {collection: rows}
                        content = encode_toon(toon_data, indent=2, delimiter=',')
                        filename = f"{source}_{collection}.toon"
                        zip_file.writestr(filename, content)
                        logger.info(f"Added {filename} to ZIP ({len(rows)} documents, TOON format)")
                    
                    elif bulk_request.format == 'json':
                        # JSON format
                        json_content = json.dumps(rows, indent=2, default=str, ensure_ascii=False)
                        filename = f"{source}_{collection}.json"
                        zip_file.writestr(filename, json_content)
                        logger.info(f"Added {filename} to ZIP ({len(rows)} documents, JSON format)")
                    
                    else:  # Default: CSV
                        # CSV format
                        all_keys = set()
                        for row in rows:
                            all_keys.update(row.keys())
                        
                        csv_buffer = io.StringIO()
                        fieldnames = sorted(list(all_keys))
                        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)
                        
                        csv_content = csv_buffer.getvalue()
                        filename = f"{source}_{collection}.csv"
                        zip_file.writestr(filename, csv_content)
                        logger.info(f"Added {filename} to ZIP ({len(rows)} documents, CSV format)")
                
                except Exception as e:
                    logger.error(f"Error exporting {source}.{collection}: {e}")
                    # Continue with other collections even if one fails
                    continue
        
        # Prepare ZIP for download
        zip_buffer.seek(0)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"all_thing_eye_export_{timestamp}.zip"
        
        logger.info(f"Bulk export completed: {len(bulk_request.tables)} collections")
        
        return StreamingResponse(
            io.BytesIO(zip_buffer.read()),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    
    except Exception as e:
        logger.error(f"Error in bulk export: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to create bulk export: {str(e)}")

