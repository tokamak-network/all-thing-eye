"""
Exports API endpoints

Provides data export functionality (CSV, JSON)
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from typing import Optional
from sqlalchemy import text
import json
import csv
import io
from datetime import datetime

from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/export/members")
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
        db_manager = request.app.state.db_manager
        
        with db_manager.get_connection() as conn:
            result = conn.execute(
                text("""
                    SELECT id, name, email, created_at
                    FROM members
                    ORDER BY name
                """)
            )
            
            members = []
            for row in result:
                members.append({
                    'id': row[0],
                    'name': row[1],
                    'email': row[2],
                    'created_at': row[3]
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
            writer = csv.DictWriter(output, fieldnames=['id', 'name', 'email', 'created_at'])
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
        raise HTTPException(status_code=500, detail="Failed to export members")


@router.get("/export/activities")
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
        db_manager = request.app.state.db_manager
        
        # Build query
        query = """
            SELECT 
                ma.id, m.name as member_name, ma.source_type, 
                ma.activity_type, ma.timestamp, ma.activity_id,
                ma.metadata
            FROM member_activities ma
            JOIN members m ON ma.member_id = m.id
            WHERE 1=1
        """
        
        params = {}
        
        if source_type:
            query += " AND ma.source_type = :source_type"
            params['source_type'] = source_type
        
        if activity_type:
            query += " AND ma.activity_type = :activity_type"
            params['activity_type'] = activity_type
        
        if start_date:
            query += " AND ma.timestamp >= :start_date"
            params['start_date'] = start_date
        
        if end_date:
            query += " AND ma.timestamp <= :end_date"
            params['end_date'] = end_date
        
        query += " ORDER BY ma.timestamp DESC LIMIT :limit"
        params['limit'] = limit
        
        with db_manager.get_connection() as conn:
            result = conn.execute(text(query), params)
            
            activities = []
            for row in result:
                # Parse metadata
                metadata = {}
                if row[6]:
                    try:
                        metadata = json.loads(row[6]) if isinstance(row[6], str) else row[6]
                    except json.JSONDecodeError:
                        pass
                
                activities.append({
                    'id': row[0],
                    'member_name': row[1],
                    'source_type': row[2],
                    'activity_type': row[3],
                    'timestamp': row[4],
                    'activity_id': row[5],
                    'metadata': metadata if format == 'json' else json.dumps(metadata, ensure_ascii=False)
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
        raise HTTPException(status_code=500, detail="Failed to export activities")


@router.get("/export/projects/{project_key}")
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
        
        db_manager = request.app.state.db_manager
        export_data = {}
        
        # Export Slack data
        if data_type in ['all', 'slack'] and slack_channel_id:
            with db_manager.get_connection('slack') as conn:
                result = conn.execute(
                    text("""
                        SELECT 
                            id, user_id, channel_id, ts, posted_at,
                            text, thread_ts, has_links, has_files
                        FROM slack_messages
                        WHERE channel_id = :channel_id
                        ORDER BY posted_at DESC
                    """),
                    {'channel_id': slack_channel_id}
                )
                
                messages = []
                for row in result:
                    messages.append({
                        'id': row[0],
                        'user_id': row[1],
                        'channel_id': row[2],
                        'ts': row[3],
                        'posted_at': row[4],
                        'text': row[5],
                        'thread_ts': row[6],
                        'has_links': row[7],
                        'has_files': row[8]
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
        raise HTTPException(status_code=500, detail="Failed to export project data")

