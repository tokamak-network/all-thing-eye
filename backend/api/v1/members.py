"""
Members API endpoints

Provides member information and statistics
"""

from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import text

from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# Response models
class MemberResponse(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    created_at: str
    
    class Config:
        from_attributes = True


class MemberDetailResponse(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    identifiers: List[dict] = []
    activity_summary: dict = {}
    created_at: str


class MemberListResponse(BaseModel):
    total: int
    members: List[MemberResponse]


@router.get("/members", response_model=MemberListResponse)
async def get_members(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Get list of all members
    
    Args:
        limit: Maximum number of members to return
        offset: Number of members to skip
    
    Returns:
        List of members with pagination
    """
    try:
        db_manager = request.app.state.db_manager
        
        # Get total count
        with db_manager.get_connection() as conn:
            result = conn.execute(text("SELECT COUNT(*) as count FROM members"))
            total = result.fetchone()[0]
            
            # Get members
            result = conn.execute(
                text("""
                    SELECT id, name, email, created_at
                    FROM members
                    ORDER BY name
                    LIMIT :limit OFFSET :offset
                """),
                {'limit': limit, 'offset': offset}
            )
            
            members = []
            for row in result:
                members.append(MemberResponse(
                    id=row[0],
                    name=row[1],
                    email=row[2],
                    created_at=row[3]
                ))
        
        return MemberListResponse(
            total=total,
            members=members
        )
        
    except Exception as e:
        logger.error(f"Error fetching members: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch members")


@router.get("/members/{member_id}", response_model=MemberDetailResponse)
async def get_member_detail(
    request: Request,
    member_id: int
):
    """
    Get detailed information for a specific member
    
    Args:
        member_id: Member ID
    
    Returns:
        Detailed member information including identifiers and activity summary
    """
    try:
        db_manager = request.app.state.db_manager
        
        with db_manager.get_connection() as conn:
            # Get member basic info
            result = conn.execute(
                text("""
                    SELECT id, name, email, created_at
                    FROM members
                    WHERE id = :member_id
                """),
                {'member_id': member_id}
            )
            
            row = result.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Member not found")
            
            member_data = {
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'created_at': row[3]
            }
            
            # Get member identifiers
            result = conn.execute(
                text("""
                    SELECT source_type, source_user_id
                    FROM member_identifiers
                    WHERE member_id = :member_id
                """),
                {'member_id': member_id}
            )
            
            identifiers = []
            for row in result:
                identifiers.append({
                    'source_type': row[0],
                    'source_user_id': row[1]
                })
            
            # Get activity summary
            result = conn.execute(
                text("""
                    SELECT 
                        source_type,
                        activity_type,
                        COUNT(*) as count,
                        MIN(timestamp) as first_activity,
                        MAX(timestamp) as last_activity
                    FROM member_activities
                    WHERE member_id = :member_id
                    GROUP BY source_type, activity_type
                    ORDER BY source_type, activity_type
                """),
                {'member_id': member_id}
            )
            
            activity_summary = {}
            for row in result:
                source = row[0]
                if source not in activity_summary:
                    activity_summary[source] = {}
                
                activity_summary[source][row[1]] = {
                    'count': row[2],
                    'first_activity': row[3],
                    'last_activity': row[4]
                }
        
        return MemberDetailResponse(
            **member_data,
            identifiers=identifiers,
            activity_summary=activity_summary
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching member detail: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch member detail")


@router.get("/members/{member_id}/activities")
async def get_member_activities(
    request: Request,
    member_id: int,
    source_type: Optional[str] = Query(None),
    activity_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Get activities for a specific member
    
    Args:
        member_id: Member ID
        source_type: Filter by source (github, slack, notion, google_drive)
        activity_type: Filter by activity type
        start_date: Filter by start date (ISO format)
        end_date: Filter by end date (ISO format)
        limit: Maximum number of activities to return
        offset: Number of activities to skip
    
    Returns:
        List of member activities
    """
    try:
        db_manager = request.app.state.db_manager
        
        # Build query
        query = """
            SELECT 
                id, source_type, activity_type, timestamp, metadata, activity_id
            FROM member_activities
            WHERE member_id = :member_id
        """
        
        params = {'member_id': member_id}
        
        if source_type:
            query += " AND source_type = :source_type"
            params['source_type'] = source_type
        
        if activity_type:
            query += " AND activity_type = :activity_type"
            params['activity_type'] = activity_type
        
        if start_date:
            query += " AND timestamp >= :start_date"
            params['start_date'] = start_date
        
        if end_date:
            query += " AND timestamp <= :end_date"
            params['end_date'] = end_date
        
        query += " ORDER BY timestamp DESC LIMIT :limit OFFSET :offset"
        params['limit'] = limit
        params['offset'] = offset
        
        with db_manager.get_connection() as conn:
            result = conn.execute(text(query), params)
            
            activities = []
            for row in result:
                activities.append({
                    'id': row[0],
                    'source_type': row[1],
                    'activity_type': row[2],
                    'timestamp': row[3],
                    'metadata': row[4],
                    'activity_id': row[5]
                })
        
        return {
            'member_id': member_id,
            'total': len(activities),
            'activities': activities
        }
        
    except Exception as e:
        logger.error(f"Error fetching member activities: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch member activities")

