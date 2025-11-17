"""
Exports API endpoints for MongoDB

Provides data export functionality (CSV, JSON)
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from typing import Optional, List
from pydantic import BaseModel
import json
import csv
import io
import zipfile
from datetime import datetime
from bson import ObjectId

from src.utils.logger import get_logger

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


def get_mongo():
    """Get MongoDB manager from main_mongo.py"""
    from backend.main_mongo import mongo_manager
    return mongo_manager


# Collection name mapping (source -> collections)
COLLECTION_MAP = {
    'main': ['members', 'member_identifiers', 'member_activities'],
    'github': ['github_members', 'github_repositories', 'github_commits', 
               'github_pull_requests', 'github_issues'],
    'slack': ['slack_channels', 'slack_messages'],
    'notion': ['notion_pages', 'notion_databases', 'notion_comments'],
    'google_drive': ['drive_files', 'drive_activities']
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
        db = mongo.async_db  # Use async_db for asynchronous operations
        
        # Get all collection names from MongoDB
        all_collections = await db.list_collection_names()
        
        # Organize by source
        collections_by_source = {}
        
        for source, expected_collections in COLLECTION_MAP.items():
            existing = [col for col in expected_collections if col in all_collections]
            if existing:
                collections_by_source[source] = existing
        
        return {
            "sources": collections_by_source,
            "total_sources": len(collections_by_source),
            "total_collections": sum(len(cols) for cols in collections_by_source.values())
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
        source: Database source (main, github, slack, google_drive, notion)
        collection: Collection name
        limit: Maximum number of documents to export (optional)
        start_date: Filter records from this date onwards (optional)
        end_date: Filter records up to this date (optional)
    
    Returns:
        CSV file download
    """
    try:
        mongo = get_mongo()
        db = mongo.async_db  # Use async_db for asynchronous operations
        
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
        
        # Build query filter
        query_filter = {}
        
        # Date filtering
        if start_date or end_date:
            # Determine timestamp field
            timestamp_fields = ['timestamp', 'posted_at', 'created_at', 'updated_at', 'committed_at']
            timestamp_field = None
            
            # Check which timestamp field exists in the collection
            sample_doc = await db[collection].find_one({})
            if sample_doc:
                for field in timestamp_fields:
                    if field in sample_doc:
                        timestamp_field = field
                        break
            
            if timestamp_field:
                date_filter = {}
                if start_date:
                    date_filter['$gte'] = datetime.fromisoformat(start_date)
                if end_date:
                    # Include the entire end day
                    end_datetime = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)
                    date_filter['$lte'] = end_datetime
                
                if date_filter:
                    query_filter[timestamp_field] = date_filter
        
        # Query MongoDB
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
    Export activities data
    
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
        mongo = get_mongo()
        db = mongo.async_db  # Use async_db for asynchronous operations
        
        # Build aggregation pipeline to join with members
        pipeline = []
        
        # Match stage for filtering
        match_filter = {}
        
        if source_type:
            match_filter['source'] = source_type
        
        if activity_type:
            match_filter['activity_type'] = activity_type
        
        if start_date:
            if 'timestamp' not in match_filter:
                match_filter['timestamp'] = {}
            match_filter['timestamp']['$gte'] = datetime.fromisoformat(start_date)
        
        if end_date:
            if 'timestamp' not in match_filter:
                match_filter['timestamp'] = {}
            end_datetime = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)
            match_filter['timestamp']['$lte'] = end_datetime
        
        if match_filter:
            pipeline.append({'$match': match_filter})
        
        # Sort by timestamp descending
        pipeline.append({'$sort': {'timestamp': -1}})
        
        # Limit
        pipeline.append({'$limit': limit})
        
        # Lookup member name
        pipeline.append({
            '$lookup': {
                'from': 'members',
                'localField': 'member_id',
                'foreignField': '_id',
                'as': 'member_info'
            }
        })
        
        # Unwind member info
        pipeline.append({
            '$unwind': {
                'path': '$member_info',
                'preserveNullAndEmptyArrays': True
            }
        })
        
        # Execute aggregation
        cursor = db['member_activities'].aggregate(pipeline)
        activities_docs = await cursor.to_list(length=limit)
        
        activities = []
        for doc in activities_docs:
            member_name = doc.get('member_info', {}).get('name', 'Unknown')
            
            activities.append({
                'id': str(doc['_id']),
                'member_name': member_name,
                'source_type': doc.get('source'),
                'activity_type': doc.get('activity_type'),
                'timestamp': doc.get('timestamp').isoformat() if doc.get('timestamp') else None,
                'activity_id': doc.get('activity_id'),
                'metadata': doc.get('metadata') if format == 'json' else json.dumps(doc.get('metadata', {}), ensure_ascii=False, default=str)
            })
        
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
            cursor = db['slack_messages'].find(
                {'channel_id': slack_channel_id}
            ).sort('timestamp', -1)
            
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
    Export multiple collections as a ZIP file containing CSV files
    
    Args:
        bulk_request: List of collection selections (source + collection name) with optional date range
        
    Returns:
        ZIP file containing CSV files for each selected collection
    """
    if not bulk_request.tables:
        raise HTTPException(status_code=400, detail="No collections selected")
    
    try:
        mongo = get_mongo()
        db = mongo.async_db  # Use async_db for asynchronous operations
        start_date = bulk_request.start_date
        end_date = bulk_request.end_date
        
        # Create in-memory ZIP file
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for selection in bulk_request.tables:
                source = selection.source
                collection = selection.get_collection_name()
                
                try:
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
                                date_filter['$gte'] = datetime.fromisoformat(start_date)
                            if end_date:
                                end_datetime = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)
                                date_filter['$lte'] = end_datetime
                            
                            if date_filter:
                                query_filter[timestamp_field] = date_filter
                    
                    # Query collection
                    cursor = db[collection].find(query_filter).limit(10000)
                    documents = await cursor.to_list(length=10000)
                    
                    if not documents:
                        logger.warning(f"No data in {source}.{collection}")
                        continue
                    
                    # Convert to CSV
                    rows = []
                    all_keys = set()
                    
                    for doc in documents:
                        # Convert ObjectId to string
                        if '_id' in doc:
                            doc['_id'] = str(doc['_id'])
                        
                        # Flatten document
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
                    csv_buffer = io.StringIO()
                    fieldnames = sorted(list(all_keys))
                    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                    
                    # Add to ZIP
                    csv_content = csv_buffer.getvalue()
                    filename = f"{source}_{collection}.csv"
                    zip_file.writestr(filename, csv_content)
                    
                    logger.info(f"Added {filename} to ZIP ({len(rows)} documents)")
                
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

