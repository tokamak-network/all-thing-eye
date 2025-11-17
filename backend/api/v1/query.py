"""
Custom Query API endpoints

SECURITY: Read-only queries only (SELECT statements)
"""

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy import text
import json

from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    source: str = "main"  # main, github, slack, notion, google_drive


class QueryResponse(BaseModel):
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    source: str


@router.post("/execute", response_model=QueryResponse)
async def execute_query(
    request: Request,
    query_request: QueryRequest
):
    """
    Execute a read-only SQL query
    
    Args:
        query_request: Query string and source database
    
    Returns:
        Query results with columns and rows
    
    Security:
        - Only SELECT queries are allowed
        - Queries are validated before execution
        - 10,000 row limit enforced
    """
    query = query_request.query.strip()
    source = query_request.source
    
    # Security: Only allow SELECT queries
    if not query.upper().startswith('SELECT'):
        raise HTTPException(
            status_code=400,
            detail="Only SELECT queries are allowed. No INSERT, UPDATE, DELETE, DROP, etc."
        )
    
    # Prevent multiple statements
    if ';' in query[:-1]:  # Allow trailing semicolon
        raise HTTPException(
            status_code=400,
            detail="Multiple statements not allowed. Only single SELECT queries."
        )
    
    # Blacklist dangerous keywords
    dangerous_keywords = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE', 'TRUNCATE', 'PRAGMA']
    query_upper = query.upper()
    for keyword in dangerous_keywords:
        if keyword in query_upper:
            raise HTTPException(
                status_code=400,
                detail=f"Keyword '{keyword}' is not allowed in queries"
            )
    
    # Validate source
    valid_sources = ['main', 'github', 'slack', 'notion', 'google_drive']
    if source not in valid_sources:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source. Must be one of: {', '.join(valid_sources)}"
        )
    
    try:
        db_manager = request.app.state.db_manager
        
        # Add LIMIT if not present (max 10,000 rows)
        if 'LIMIT' not in query_upper:
            query = query.rstrip(';') + ' LIMIT 10000'
        
        # Get connection
        if source == 'main':
            conn_context = db_manager.get_connection()
        else:
            conn_context = db_manager.get_connection(source)
        
        with conn_context as conn:
            result = conn.execute(text(query))
            
            # Get column names
            columns = list(result.keys())
            
            # Fetch all rows
            rows = []
            for row in result:
                rows.append(list(row))
            
            logger.info(f"Query executed successfully: {query[:100]}... (source: {source}, rows: {len(rows)})")
            
            return QueryResponse(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                source=source
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Query execution failed: {str(e)}"
        )


@router.get("/tables")
async def get_table_schemas(
    request: Request,
    source: str = Query("main", description="Database source")
):
    """
    Get table schemas for a specific source
    
    Args:
        source: Database source
    
    Returns:
        Table schemas with column information
    """
    valid_sources = ['main', 'github', 'slack', 'notion', 'google_drive']
    if source not in valid_sources:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source. Must be one of: {', '.join(valid_sources)}"
        )
    
    try:
        db_manager = request.app.state.db_manager
        
        if source == 'main':
            conn_context = db_manager.get_connection()
        else:
            conn_context = db_manager.get_connection(source)
        
        with conn_context as conn:
            # Get all tables
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            )
            tables = [row[0] for row in result if not row[0].startswith('sqlite_')]
            
            # Get schema for each table
            schemas = {}
            for table in tables:
                result = conn.execute(text(f"PRAGMA table_info({table})"))
                columns = []
                for row in result:
                    columns.append({
                        'name': row[1],
                        'type': row[2],
                        'not_null': bool(row[3]),
                        'default': row[4],
                        'primary_key': bool(row[5])
                    })
                schemas[table] = columns
            
            return {
                'source': source,
                'tables': schemas
            }
    
    except Exception as e:
        logger.error(f"Failed to get table schemas: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get table schemas: {str(e)}"
        )


@router.get("/examples")
async def get_query_examples():
    """
    Get example queries for different sources
    
    Returns:
        Dictionary of example queries
    """
    examples = {
        "main": {
            "members": "SELECT * FROM members ORDER BY name",
            "member_activities_count": "SELECT source_type, COUNT(*) as count FROM member_activities GROUP BY source_type",
            "member_identifiers": "SELECT m.name, mi.source_type, mi.source_user_id FROM members m JOIN member_identifiers mi ON m.id = mi.member_id",
            "recent_activities": "SELECT m.name, ma.source_type, ma.activity_type, ma.timestamp FROM member_activities ma JOIN members m ON ma.member_id = m.id ORDER BY ma.timestamp DESC LIMIT 20"
        },
        "github": {
            "commits_by_author": "SELECT author_name, COUNT(*) as commits FROM github_commits GROUP BY author_name ORDER BY commits DESC",
            "recent_commits": "SELECT sha, author_name, message, date FROM github_commits ORDER BY date DESC LIMIT 20",
            "pull_requests": "SELECT number, title, state, author, created_at FROM github_pull_requests ORDER BY created_at DESC",
            "issues": "SELECT number, title, state, created_at FROM github_issues ORDER BY created_at DESC"
        },
        "slack": {
            "messages_by_channel": "SELECT sc.name as channel, COUNT(*) as messages FROM slack_messages sm JOIN slack_channels sc ON sm.channel_id = sc.id GROUP BY sm.channel_id ORDER BY messages DESC",
            "recent_messages": "SELECT user_id, channel_id, text, posted_at FROM slack_messages ORDER BY posted_at DESC LIMIT 20",
            "reactions_summary": "SELECT reaction, COUNT(*) as count FROM slack_reactions GROUP BY reaction ORDER BY count DESC",
            "links_shared": "SELECT url, COUNT(*) as shares FROM slack_links GROUP BY url ORDER BY shares DESC LIMIT 20"
        },
        "notion": {
            "pages": "SELECT id, title, created_time, last_edited_time FROM notion_pages ORDER BY last_edited_time DESC LIMIT 20",
            "comments": "SELECT * FROM notion_comments",
            "databases": "SELECT * FROM notion_databases"
        },
        "google_drive": {
            "activity_types": "SELECT type, COUNT(*) as count FROM drive_activities GROUP BY type ORDER BY count DESC",
            "recent_activities": "SELECT type, actor_email, time FROM drive_activities ORDER BY time DESC LIMIT 20",
            "folders": "SELECT name, drive_id, owner, created_time FROM drive_folders ORDER BY created_time DESC LIMIT 20",
            "activities_by_user": "SELECT actor_email, COUNT(*) as activities FROM drive_activities GROUP BY actor_email ORDER BY activities DESC"
        }
    }
    
    return {
        "examples": examples,
        "usage": "POST /api/v1/query/execute with body: {\"query\": \"SELECT ...\", \"source\": \"main\"}"
    }


