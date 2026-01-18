"""
AI Processed Data API endpoints

Provides endpoints for AI-processed data (Gemini summaries, translations, etc.)
"""

from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId

from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ============================================
# Pydantic Models
# ============================================

class MeetingAnalysis(BaseModel):
    """Individual analysis result for a meeting"""
    model_config = {"protected_namespaces": ()}
    
    id: str
    meeting_id: str
    meeting_title: str
    meeting_date: Optional[str] = None
    participants: List[str] = []
    template_used: str
    status: str
    analysis: str
    participant_stats: Optional[Dict[str, Any]] = None
    model_used: Optional[str] = None
    timestamp: Optional[str] = None
    total_statements: Optional[int] = None


class MeetingSummary(BaseModel):
    """Meeting summary with all analysis types"""
    id: str
    meeting_id: str
    meeting_title: str
    meeting_date: Optional[str] = None
    participants: List[str] = []
    web_view_link: Optional[str] = None
    content_preview: Optional[str] = None
    created_by: Optional[str] = None
    analyses: Dict[str, MeetingAnalysis] = {}  # template_used -> analysis


class MeetingListResponse(BaseModel):
    """List of meetings with pagination"""
    total: int
    meetings: List[MeetingSummary]
    limit: int
    offset: int


class FailedRecording(BaseModel):
    """Failed recording document"""
    id: str
    name: str
    web_view_link: Optional[str] = None
    created_time: Optional[str] = None
    created_by: Optional[str] = None
    content_preview: Optional[str] = None


# ============================================
# Helper functions
# ============================================

# Cache for gemini database connection
_gemini_db_cache = None

def get_gemini_db():
    """Get gemini database connection (cached)"""
    global _gemini_db_cache
    
    if _gemini_db_cache is not None:
        return _gemini_db_cache
    
    import os
    from pymongo import MongoClient
    
    # Get MongoDB URI from environment
    gemini_uri = os.getenv('GEMINI_MONGODB_URI')
    if not gemini_uri:
        # Fall back to main MongoDB URI
        gemini_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
    
    # Create a direct connection to gemini database
    client = MongoClient(gemini_uri)
    _gemini_db_cache = client["gemini"]
    return _gemini_db_cache


# Cache for shared database connection
_shared_db_cache = None

def get_shared_db():
    """Get shared database connection (cached)"""
    global _shared_db_cache
    
    if _shared_db_cache is not None:
        return _shared_db_cache
    
    import os
    from pymongo import MongoClient
    
    # Get MongoDB URI from environment
    shared_uri = os.getenv('SHARED_MONGODB_URI')
    if not shared_uri:
        # Fall back to main MongoDB URI
        shared_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
    
    # Create a direct connection to shared database
    client = MongoClient(shared_uri)
    _shared_db_cache = client["shared"]
    return _shared_db_cache


# ============================================
# Meetings API (gemini.recordings + shared.recordings)
# ============================================

@router.get("/ai/meetings", response_model=MeetingListResponse)
async def get_meetings(
    request: Request,
    search: Optional[str] = Query(None, description="Search in title or participants"),
    participant: Optional[str] = Query(None, description="Filter by participant"),
    template: Optional[str] = Query(None, description="Filter by template type"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    Get list of meetings with AI analyses from gemini.recordings
    """
    try:
        gemini_db = get_gemini_db()
        shared_db = get_shared_db()
        
        # Build aggregation pipeline to get unique meetings
        match_stage: Dict[str, Any] = {}
        if search:
            match_stage["$or"] = [
                {"meeting_title": {"$regex": search, "$options": "i"}},
                {"participants": {"$regex": search, "$options": "i"}}
            ]
        if participant:
            match_stage["participants"] = {"$regex": participant, "$options": "i"}
        if template:
            match_stage["analysis.template_used"] = template
        
        # Get unique meeting_ids with their analyses
        pipeline = [
            {"$match": match_stage} if match_stage else {"$match": {}},
            {"$sort": {"meeting_date": -1}},
            {"$group": {
                "_id": "$meeting_id",
                "meeting_title": {"$first": "$meeting_title"},
                "meeting_date": {"$first": "$meeting_date"},
                "participants": {"$first": "$participants"},
                "analyses": {"$push": {
                    "id": {"$toString": "$_id"},
                    "template_used": "$analysis.template_used",
                    "status": "$analysis.status",
                    "analysis": "$analysis.analysis",
                    "participant_stats": "$analysis.participant_stats",
                    "model_used": "$analysis.model_used",
                    "timestamp": "$analysis.timestamp",
                    "total_statements": "$analysis.total_statements"
                }}
            }},
            {"$sort": {"meeting_date": -1}},
            {"$skip": offset},
            {"$limit": limit}
        ]
        
        # Get total count
        count_pipeline = [
            {"$match": match_stage} if match_stage else {"$match": {}},
            {"$group": {"_id": "$meeting_id"}},
            {"$count": "total"}
        ]
        count_result = list(gemini_db["recordings"].aggregate(count_pipeline))
        total = count_result[0]["total"] if count_result else 0
        
        # Execute main pipeline
        results = list(gemini_db["recordings"].aggregate(pipeline))
        
        # Build response with shared.recordings data
        meetings = []
        for r in results:
            meeting_id = r["_id"]
            
            # Get original recording from shared.recordings
            shared_recording = None
            if meeting_id:
                try:
                    shared_recording = shared_db["recordings"].find_one({"_id": ObjectId(meeting_id)})
                except:
                    pass
            
            # Build analyses dict by template
            analyses_dict = {}
            for a in r.get("analyses", []):
                template_name = a.get("template_used", "default")
                analyses_dict[template_name] = MeetingAnalysis(
                    id=a.get("id", ""),
                    meeting_id=str(meeting_id) if meeting_id else "",
                    meeting_title=r.get("meeting_title", ""),
                    meeting_date=r.get("meeting_date").isoformat() if r.get("meeting_date") else None,
                    participants=r.get("participants", []),
                    template_used=template_name,
                    status=a.get("status", ""),
                    analysis=a.get("analysis", "")[:500] + "..." if len(a.get("analysis", "")) > 500 else a.get("analysis", ""),
                    participant_stats=a.get("participant_stats"),
                    model_used=a.get("model_used"),
                    timestamp=a.get("timestamp"),
                    total_statements=a.get("total_statements")
                )
            
            meetings.append(MeetingSummary(
                id=str(meeting_id) if meeting_id else "",
                meeting_id=str(meeting_id) if meeting_id else "",
                meeting_title=r.get("meeting_title", ""),
                meeting_date=r.get("meeting_date").isoformat() if r.get("meeting_date") else None,
                participants=r.get("participants", []),
                web_view_link=shared_recording.get("webViewLink") if shared_recording else None,
                content_preview=shared_recording.get("content", "")[:200] if shared_recording else None,
                created_by=shared_recording.get("created_by") if shared_recording else None,
                analyses=analyses_dict
            ))
        
        return MeetingListResponse(
            total=total,
            meetings=meetings,
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Error fetching meetings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai/meetings/{meeting_id}")
async def get_meeting_detail(
    request: Request,
    meeting_id: str
):
    """
    Get detailed meeting info with all AI analyses
    
    meeting_id can be:
    - MongoDB ObjectId (from shared.recordings._id)
    - Google Drive document ID (from shared.recordings.id)
    """
    try:
        gemini_db = get_gemini_db()
        shared_db = get_shared_db()
        
        # First, try to find the shared recording by different IDs
        shared_recording = None
        actual_meeting_id = None
        
        # Try as MongoDB ObjectId first
        try:
            shared_recording = shared_db["recordings"].find_one({"_id": ObjectId(meeting_id)})
            if shared_recording:
                actual_meeting_id = shared_recording["_id"]
        except:
            pass
        
        # If not found, try as Google Drive ID
        if not shared_recording:
            shared_recording = shared_db["recordings"].find_one({"id": meeting_id})
            if shared_recording:
                actual_meeting_id = shared_recording["_id"]
        
        # Get all analyses for this meeting
        # Note: gemini.recordings stores meeting_id as string, not ObjectId
        analyses = []
        if actual_meeting_id:
            # Try both string and ObjectId formats
            analyses = list(gemini_db["recordings"].find({"meeting_id": str(actual_meeting_id)}))
            if not analyses:
                analyses = list(gemini_db["recordings"].find({"meeting_id": actual_meeting_id}))
        
        # If still no analyses, try with the original meeting_id as string
        if not analyses:
            analyses = list(gemini_db["recordings"].find({"meeting_id": meeting_id}))
        
        if not analyses and not shared_recording:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Build response
        analyses_dict = {}
        meeting_title = ""
        meeting_date = None
        participants = []
        
        if analyses:
            first = analyses[0]
            meeting_title = first.get("meeting_title", "")
            meeting_date = first.get("meeting_date")
            participants = first.get("participants", [])
            
            for a in analyses:
                template_name = a.get("analysis", {}).get("template_used", "default")
                analysis_data = a.get("analysis", {})
                analyses_dict[template_name] = {
                    "id": str(a["_id"]),
                    "template_used": template_name,
                    "status": analysis_data.get("status", ""),
                    "analysis": analysis_data.get("analysis", ""),
                    "participant_stats": analysis_data.get("participant_stats"),
                    "model_used": analysis_data.get("model_used"),
                    "timestamp": analysis_data.get("timestamp"),
                    "total_statements": analysis_data.get("total_statements")
                }
        elif shared_recording:
            # No AI analyses but we have the original recording
            meeting_title = shared_recording.get("name", "")
            meeting_date = shared_recording.get("createdTime")
        
        return {
            "id": meeting_id,
            "meeting_title": meeting_title,
            "meeting_date": meeting_date.isoformat() if hasattr(meeting_date, 'isoformat') else meeting_date,
            "participants": participants,
            "web_view_link": shared_recording.get("webViewLink") if shared_recording else None,
            "content": shared_recording.get("content") if shared_recording else None,
            "created_by": shared_recording.get("created_by") if shared_recording else None,
            "analyses": analyses_dict
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching meeting detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai/meetings/{meeting_id}/analysis/{template}")
async def get_meeting_analysis(
    request: Request,
    meeting_id: str,
    template: str
):
    """
    Get specific analysis for a meeting by template type
    
    Templates: default, team_collaboration, action_items, knowledge_base, 
               decision_log, quick_recap, meeting_context
    """
    try:
        gemini_db = get_gemini_db()
        
        # Find the specific analysis
        try:
            query = {
                "meeting_id": ObjectId(meeting_id),
                "analysis.template_used": template
            }
        except:
            query = {
                "meeting_id": meeting_id,
                "analysis.template_used": template
            }
        
        doc = gemini_db["recordings"].find_one(query)
        
        if not doc:
            raise HTTPException(status_code=404, detail=f"Analysis not found for template: {template}")
        
        analysis = doc.get("analysis", {})
        
        return {
            "id": str(doc["_id"]),
            "meeting_id": meeting_id,
            "meeting_title": doc.get("meeting_title", ""),
            "meeting_date": doc.get("meeting_date").isoformat() if doc.get("meeting_date") else None,
            "participants": doc.get("participants", []),
            "template_used": template,
            "status": analysis.get("status", ""),
            "analysis": analysis.get("analysis", ""),
            "participant_stats": analysis.get("participant_stats"),
            "model_used": analysis.get("model_used"),
            "timestamp": analysis.get("timestamp"),
            "total_statements": analysis.get("total_statements")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching meeting analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Failed Recordings API
# ============================================

@router.get("/ai/failed-recordings", response_model=List[FailedRecording])
async def get_failed_recordings(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """
    Get list of failed recordings from shared.failed_recordings
    """
    try:
        shared_db = get_shared_db()
        
        cursor = shared_db["failed_recordings"].find().skip(offset).limit(limit)
        
        results = []
        for doc in cursor:
            results.append(FailedRecording(
                id=str(doc["_id"]),
                name=doc.get("name", ""),
                web_view_link=doc.get("webViewLink"),
                created_time=doc.get("createdTime"),
                created_by=doc.get("created_by"),
                content_preview=doc.get("content", "")[:200] if doc.get("content") else None
            ))
        
        return results
        
    except Exception as e:
        logger.error(f"Error fetching failed recordings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Stats API
# ============================================

@router.get("/ai/stats")
async def get_ai_stats(request: Request):
    """
    Get AI processing statistics
    """
    try:
        gemini_db = get_gemini_db()
        shared_db = get_shared_db()
        
        # Count unique meetings
        unique_meetings = len(gemini_db["recordings"].distinct("meeting_id"))
        
        # Count by template
        template_stats = list(gemini_db["recordings"].aggregate([
            {"$group": {"_id": "$analysis.template_used", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]))
        
        # Failed recordings count
        failed_count = shared_db["failed_recordings"].count_documents({})
        
        # Original recordings count
        original_count = shared_db["recordings"].count_documents({})
        
        return {
            "total_meetings": unique_meetings,
            "total_analyses": gemini_db["recordings"].count_documents({}),
            "original_recordings": original_count,
            "failed_recordings": failed_count,
            "templates": {t["_id"]: t["count"] for t in template_stats if t["_id"]},
            "success_rate": round((unique_meetings / (unique_meetings + failed_count)) * 100, 1) if (unique_meetings + failed_count) > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error fetching AI stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Recordings Daily Analysis API
# ============================================

class RecordingsDailyResponse(BaseModel):
    """Daily recordings analysis response"""
    id: str
    status: str
    target_date: str
    meeting_count: int
    meeting_titles: List[str]
    date_range: Dict[str, Any]  # start and end can be datetime or string
    total_meeting_time: str
    total_meeting_time_seconds: int
    template_used: str
    template_version: Optional[str] = None
    model_used: str
    timestamp: str
    target_meetings: List[Dict[str, Any]]
    analysis: Dict[str, Any]  # Contains summary, participants, full_analysis_text


class RecordingsDailyListResponse(BaseModel):
    """List of daily recordings analyses"""
    total: int
    analyses: List[RecordingsDailyResponse]
    limit: int
    offset: int


@router.get("/ai/recordings-daily", response_model=RecordingsDailyListResponse)
async def get_recordings_daily(
    request: Request,
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """
    Get list of daily recordings analyses from gemini.recordings_daily
    """
    try:
        gemini_db = get_gemini_db()
        
        # Build query
        query: Dict[str, Any] = {}
        if start_date or end_date:
            date_query: Dict[str, Any] = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            query["target_date"] = date_query
        
        # Get total count
        total = gemini_db["recordings_daily"].count_documents(query)
        
        # Get documents
        cursor = gemini_db["recordings_daily"].find(query).sort("target_date", -1).skip(offset).limit(limit)
        
        def convert_value(v):
            """Convert MongoDB types to JSON-serializable types"""
            if isinstance(v, ObjectId):
                return str(v)
            elif isinstance(v, datetime):
                return v.isoformat()
            elif isinstance(v, dict):
                return {k: convert_value(val) for k, val in v.items()}
            elif isinstance(v, list):
                return [convert_value(item) for item in v]
            return v
        
        analyses = []
        for doc in cursor:
            # Convert ObjectId to string
            doc_id = str(doc["_id"])
            
            # Convert all datetime fields to ISO strings
            converted_doc = convert_value(doc)
            
            # Ensure date_range is properly converted
            date_range = converted_doc.get("date_range", {})
            
            analyses.append(RecordingsDailyResponse(
                id=doc_id,
                status=converted_doc.get("status", ""),
                target_date=converted_doc.get("target_date", ""),
                meeting_count=converted_doc.get("meeting_count", 0),
                meeting_titles=converted_doc.get("meeting_titles", []),
                date_range=date_range,
                total_meeting_time=converted_doc.get("total_meeting_time", ""),
                total_meeting_time_seconds=converted_doc.get("total_meeting_time_seconds", 0),
                template_used=converted_doc.get("template_used", ""),
                template_version=converted_doc.get("template_version"),
                model_used=converted_doc.get("model_used", ""),
                timestamp=converted_doc.get("timestamp", ""),
                target_meetings=converted_doc.get("target_meetings", []),
                analysis=converted_doc.get("analysis", {})
            ))
        
        return RecordingsDailyListResponse(
            total=total,
            analyses=analyses,
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Error fetching recordings daily: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai/recordings-daily/{date}", response_model=RecordingsDailyResponse)
async def get_recordings_daily_by_date(
    request: Request,
    date: str  # YYYY-MM-DD format
):
    """
    Get daily recordings analysis for a specific date
    """
    try:
        gemini_db = get_gemini_db()
        
        doc = gemini_db["recordings_daily"].find_one({"target_date": date})
        
        if not doc:
            raise HTTPException(status_code=404, detail=f"No analysis found for date: {date}")
        
        def convert_value(v):
            """Convert MongoDB types to JSON-serializable types"""
            if isinstance(v, ObjectId):
                return str(v)
            elif isinstance(v, datetime):
                return v.isoformat()
            elif isinstance(v, dict):
                return {k: convert_value(val) for k, val in v.items()}
            elif isinstance(v, list):
                return [convert_value(item) for item in v]
            return v
        
        # Convert all MongoDB types to JSON-serializable
        converted_doc = convert_value(doc)
        doc_id = str(doc["_id"])
        
        return RecordingsDailyResponse(
            id=doc_id,
            status=converted_doc.get("status", ""),
            target_date=converted_doc.get("target_date", ""),
            meeting_count=converted_doc.get("meeting_count", 0),
            meeting_titles=converted_doc.get("meeting_titles", []),
            date_range=converted_doc.get("date_range", {}),
            total_meeting_time=converted_doc.get("total_meeting_time", ""),
            total_meeting_time_seconds=converted_doc.get("total_meeting_time_seconds", 0),
            template_used=converted_doc.get("template_used", ""),
            template_version=converted_doc.get("template_version"),
            model_used=converted_doc.get("model_used", ""),
            timestamp=converted_doc.get("timestamp", ""),
            target_meetings=converted_doc.get("target_meetings", []),
            analysis=converted_doc.get("analysis", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching recordings daily by date: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Translation API (using Tokamak AI - qwen3-80b-next)
# ============================================

class TranslationRequest(BaseModel):
    text: str
    target_language: str = "ko"  # Default to Korean
    source_language: Optional[str] = None  # Auto-detect if not provided


class TranslationResponse(BaseModel):
    original_text: str
    translated_text: str
    source_language: str
    target_language: str


@router.post("/ai/translate", response_model=TranslationResponse)
async def translate_text(
    request: Request,
    translation_request: TranslationRequest
):
    """
    Translate text using Tokamak AI API (qwen3-80b-next) with caching
    
    Supports:
    - Auto language detection
    - EN ↔ KO translation
    - Fast translation for large texts
    - Translation caching in MongoDB to avoid redundant API calls
    """
    try:
        import os
        import httpx
        import hashlib
        from dotenv import load_dotenv
        from pathlib import Path
        
        # Ensure .env file is loaded (in case it wasn't loaded at startup)
        project_root = Path(__file__).parent.parent.parent.parent
        env_path = project_root / '.env'
        load_dotenv(dotenv_path=env_path, override=False)
        
        # Get Tokamak AI API key for translation (qwen3-80b-next)
        api_key = os.getenv("TRANSLATION_API_KEY")
        if not api_key:
            logger.error(f"TRANSLATION_API_KEY not found. .env path: {env_path}")
            raise HTTPException(
                status_code=501,
                detail="TRANSLATION_API_KEY not configured"
            )
        
        text = translation_request.text
        target = translation_request.target_language
        
        # Language name mapping for prompt
        lang_name_map = {
            "ko": "Korean",
            "en": "English",
            "ja": "Japanese",
            "zh": "Chinese",
        }
        target_lang = target.lower()
        target_lang_name = lang_name_map.get(target_lang, target_lang.capitalize())
        
        # Detect source language (simple heuristic if not provided)
        def detect_language(text: str) -> str:
            korean_chars = sum(1 for c in text if '\uac00' <= c <= '\ud7af')
            japanese_chars = sum(1 for c in text if '\u3040' <= c <= '\u30ff')
            chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
            
            if korean_chars > len(text) * 0.2:
                return "ko"
            if japanese_chars > len(text) * 0.1:
                return "ja"
            if chinese_chars > len(text) * 0.2:
                return "zh"
            return "en"
        
        source_lang = translation_request.source_language
        if source_lang:
            source_lang = source_lang.lower()
        else:
            source_lang = detect_language(text)
        
        source_lang_name = lang_name_map.get(source_lang, source_lang.capitalize())
        
        # Generate cache key: hash of (original_text + source_lang + target_lang)
        cache_key_str = f"{text}|{source_lang}|{target_lang}"
        cache_key = hashlib.sha256(cache_key_str.encode('utf-8')).hexdigest()
        
        # Try to get cached translation from MongoDB
        try:
            from backend.main import mongo_manager
            if mongo_manager._sync_client is None:
                mongo_manager.connect_sync()
            db = mongo_manager._sync_client[mongo_manager.database_name]
            translations_collection = db["translations"]
            
            # Check cache
            cached = translations_collection.find_one({"cache_key": cache_key})
            if cached:
                logger.info(f"Translation cache hit for key: {cache_key[:16]}...")
                return TranslationResponse(
                    original_text=cached["original_text"],
                    translated_text=cached["translated_text"],
                    source_language=cached["source_language"],
                    target_language=cached["target_language"]
                )
        except Exception as cache_error:
            logger.warning(f"Failed to check translation cache: {cache_error}")
            # Continue with API call if cache check fails
        
        # Cache miss - call Tokamak AI API
        logger.info(f"Translation cache miss, calling Tokamak AI API for key: {cache_key[:16]}...")
        
        api_url = "https://api.ai.tokamak.network/v1/chat/completions"
        
        # Prepare translation prompt
        system_prompt = f"""You are a professional translator. Translate the given text from {source_lang_name} to {target_lang_name}.
Rules:
- Output ONLY the translated text, nothing else
- Preserve the original formatting and structure
- Keep proper nouns, technical terms, and code unchanged
- Maintain the tone and style of the original text"""
        
        # Prepare request data for OpenAI-compatible API
        request_data = {
            "model": "qwen3-80b-next",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "max_tokens": 4096,
            "temperature": 0.3  # Lower temperature for more consistent translations
        }
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Call Tokamak AI API
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(api_url, json=request_data, headers=headers)
            response.raise_for_status()
            result = response.json()
        
        # Extract translated text from OpenAI-compatible response
        if "choices" in result and len(result["choices"]) > 0:
            translated_text = result["choices"][0]["message"]["content"].strip()
        else:
            raise ValueError("No translation in Tokamak AI API response")
        
        # Save to cache
        try:
            translation_doc = {
                "cache_key": cache_key,
                "original_text": text,
                "source_language": source_lang,
                "translated_text": translated_text,
                "target_language": target_lang,
                "translation_provider": "tokamak-ai",
                "model": "qwen3-80b-next",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            translations_collection.update_one(
                {"cache_key": cache_key},
                {"$set": translation_doc},
                upsert=True
            )
            logger.info(f"Translation cached with key: {cache_key[:16]}...")
        except Exception as save_error:
            logger.warning(f"Failed to save translation to cache: {save_error}")
            # Continue even if cache save fails
        
        return TranslationResponse(
            original_text=text,
            translated_text=translated_text,
            source_language=source_lang,
            target_language=target_lang
        )
        
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        logger.error(f"Tokamak AI API HTTP error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Tokamak AI API error: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Translation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")
