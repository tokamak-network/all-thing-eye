"""
Activities API endpoints

Provides activity data across all sources
"""

from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import text
import json

from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# Response models
class ActivityResponse(BaseModel):
    id: int
    member_id: int
    member_name: str
    source_type: str
    activity_type: str
    timestamp: str
    metadata: dict = {}
    activity_id: Optional[str] = None


class ActivityListResponse(BaseModel):
    total: int
    activities: List[ActivityResponse]
    filters: dict


@router.get("/activities", response_model=ActivityListResponse)
async def get_activities(
    request: Request,
    source_type: Optional[str] = Query(None, description="Filter by source (github, slack, notion, google_drive)"),
    activity_type: Optional[str] = Query(None, description="Filter by activity type"),
    member_id: Optional[int] = Query(None, description="Filter by member ID"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Get list of activities with filters
    
    Returns:
        Paginated list of activities
    """
    try:
        db_manager = request.app.state.db_manager
        
        # Build query
        query = """
            SELECT 
                ma.id, ma.member_id, m.name as member_name,
                ma.source_type, ma.activity_type, ma.timestamp,
                ma.metadata, ma.activity_id
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
        
        if member_id:
            query += " AND ma.member_id = :member_id"
            params['member_id'] = member_id
        
        if start_date:
            query += " AND ma.timestamp >= :start_date"
            params['start_date'] = start_date
        
        if end_date:
            query += " AND ma.timestamp <= :end_date"
            params['end_date'] = end_date
        
        # Get total count
        count_query = f"SELECT COUNT(*) as count FROM ({query}) as subquery"
        
        with db_manager.get_connection() as conn:
            result = conn.execute(text(count_query), params)
            total = result.fetchone()[0]
            
            # Get activities with pagination
            query += " ORDER BY ma.timestamp DESC LIMIT :limit OFFSET :offset"
            params['limit'] = limit
            params['offset'] = offset
            
            result = conn.execute(text(query), params)
            
            activities = []
            for row in result:
                # Parse metadata JSON
                metadata = {}
                if row[6]:
                    try:
                        metadata = json.loads(row[6]) if isinstance(row[6], str) else row[6]
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse metadata for activity {row[0]}")
                
                activities.append(ActivityResponse(
                    id=row[0],
                    member_id=row[1],
                    member_name=row[2],
                    source_type=row[3],
                    activity_type=row[4],
                    timestamp=row[5],
                    metadata=metadata,
                    activity_id=row[7]
                ))
        
        return ActivityListResponse(
            total=total,
            activities=activities,
            filters={
                'source_type': source_type,
                'activity_type': activity_type,
                'member_id': member_id,
                'start_date': start_date,
                'end_date': end_date,
                'limit': limit,
                'offset': offset
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching activities: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch activities")


@router.get("/activities/summary")
async def get_activities_summary(
    request: Request,
    source_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """
    Get activity summary statistics
    
    Returns:
        Summary statistics grouped by source and activity type
    """
    try:
        db_manager = request.app.state.db_manager
        
        query = """
            SELECT 
                source_type,
                activity_type,
                COUNT(*) as count,
                COUNT(DISTINCT member_id) as unique_members,
                MIN(timestamp) as first_activity,
                MAX(timestamp) as last_activity
            FROM member_activities
            WHERE 1=1
        """
        
        params = {}
        
        if source_type:
            query += " AND source_type = :source_type"
            params['source_type'] = source_type
        
        if start_date:
            query += " AND timestamp >= :start_date"
            params['start_date'] = start_date
        
        if end_date:
            query += " AND timestamp <= :end_date"
            params['end_date'] = end_date
        
        query += " GROUP BY source_type, activity_type ORDER BY source_type, count DESC"
        
        with db_manager.get_connection() as conn:
            result = conn.execute(text(query), params)
            
            summary = {}
            for row in result:
                source = row[0]
                if source not in summary:
                    summary[source] = {
                        'total_activities': 0,
                        'activity_types': {}
                    }
                
                summary[source]['total_activities'] += row[2]
                summary[source]['activity_types'][row[1]] = {
                    'count': row[2],
                    'unique_members': row[3],
                    'first_activity': row[4],
                    'last_activity': row[5]
                }
        
        return {
            'summary': summary,
            'filters': {
                'source_type': source_type,
                'start_date': start_date,
                'end_date': end_date
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching activity summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch activity summary")


@router.get("/activities/types")
async def get_activity_types(
    request: Request,
    source_type: Optional[str] = Query(None)
):
    """
    Get list of available activity types
    
    Returns:
        List of activity types grouped by source
    """
    try:
        db_manager = request.app.state.db_manager
        
        query = """
            SELECT DISTINCT source_type, activity_type
            FROM member_activities
        """
        
        params = {}
        
        if source_type:
            query += " WHERE source_type = :source_type"
            params['source_type'] = source_type
        
        query += " ORDER BY source_type, activity_type"
        
        with db_manager.get_connection() as conn:
            result = conn.execute(text(query), params)
            
            types = {}
            for row in result:
                source = row[0]
                if source not in types:
                    types[source] = []
                types[source].append(row[1])
        
        return {
            'activity_types': types
        }
        
    except Exception as e:
        logger.error(f"Error fetching activity types: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch activity types")

