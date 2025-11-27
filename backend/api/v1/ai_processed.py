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

def get_gemini_db():
    """Get gemini database connection"""
    from backend.main import mongo_manager
    # Access underlying sync client to get gemini database
    if mongo_manager._sync_client is None:
        mongo_manager.connect_sync()
    return mongo_manager._sync_client["gemini"]


def get_shared_db():
    """Get shared database connection"""
    from backend.main import mongo_manager
    # Use the shared_db property which connects to 'shared' database
    return mongo_manager.shared_db


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
# Translation API (using Gemini)
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
    Translate text using Gemini API
    
    Supports:
    - Auto language detection
    - EN ↔ KO translation
    """
    try:
        import os
        import google.generativeai as genai
        
        # Get Gemini API key from environment
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=501,
                detail="GEMINI_API_KEY not configured"
            )
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        text = translation_request.text
        target = translation_request.target_language
        
        # Language names for prompt
        lang_names = {
            "ko": "Korean",
            "en": "English",
            "ja": "Japanese",
            "zh": "Chinese",
        }
        target_name = lang_names.get(target, target)
        
        # Create translation prompt
        prompt = f"""Translate the following text to {target_name}. 
Only output the translated text, nothing else. Do not add any explanations or notes.

Text to translate:
{text}"""
        
        response = model.generate_content(prompt)
        translated_text = response.text.strip()
        
        # Detect source language (simple heuristic)
        def detect_language(text: str) -> str:
            korean_chars = sum(1 for c in text if '\uac00' <= c <= '\ud7af')
            if korean_chars > len(text) * 0.3:
                return "ko"
            return "en"
        
        source_lang = translation_request.source_language or detect_language(text)
        
        return TranslationResponse(
            original_text=text,
            translated_text=translated_text,
            source_language=source_lang,
            target_language=target
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Translation error: {e}")
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")
