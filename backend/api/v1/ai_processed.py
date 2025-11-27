"""
AI Processed Data API endpoints

Provides endpoints for AI-processed data (Gemini summaries, translations, etc.)
"""

from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ============================================
# Gemini Recordings (AI Summaries)
# ============================================

class RecordingSummary(BaseModel):
    """Recording summary document"""
    source_id: str  # Original document _id from source collection
    source_collection: str  # e.g., "drive_files", "drive_activities"
    title: str
    summary: str
    summary_kr: Optional[str] = None  # Korean translation
    key_points: Optional[List[str]] = None
    participants: Optional[List[str]] = None
    duration_minutes: Optional[int] = None
    language: Optional[str] = None  # Detected language
    processed_at: Optional[datetime] = None
    model: Optional[str] = "gemini-1.5-flash"  # Model used


class RecordingSummaryResponse(BaseModel):
    id: str
    source_id: str
    source_collection: str
    title: str
    summary: str
    summary_kr: Optional[str] = None
    key_points: Optional[List[str]] = None
    participants: Optional[List[str]] = None
    duration_minutes: Optional[int] = None
    language: Optional[str] = None
    processed_at: Optional[str] = None
    model: Optional[str] = None


@router.get("/ai/recordings", response_model=List[RecordingSummaryResponse])
async def get_recording_summaries(
    request: Request,
    source_id: Optional[str] = Query(None, description="Filter by source document ID"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    Get AI-processed recording summaries
    """
    try:
        from backend.main import mongo_manager
        db = mongo_manager.db
        
        collection = db["gemini_recordings"]
        
        query = {}
        if source_id:
            query["source_id"] = source_id
        
        cursor = collection.find(query).sort("processed_at", -1).skip(offset).limit(limit)
        
        results = []
        for doc in cursor:
            results.append(RecordingSummaryResponse(
                id=str(doc["_id"]),
                source_id=doc.get("source_id", ""),
                source_collection=doc.get("source_collection", ""),
                title=doc.get("title", ""),
                summary=doc.get("summary", ""),
                summary_kr=doc.get("summary_kr"),
                key_points=doc.get("key_points"),
                participants=doc.get("participants"),
                duration_minutes=doc.get("duration_minutes"),
                language=doc.get("language"),
                processed_at=doc.get("processed_at").isoformat() if doc.get("processed_at") else None,
                model=doc.get("model")
            ))
        
        return results
        
    except Exception as e:
        logger.error(f"Error fetching recording summaries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai/recordings/{source_id}", response_model=RecordingSummaryResponse)
async def get_recording_summary_by_source(
    request: Request,
    source_id: str
):
    """
    Get AI-processed recording summary by source document ID
    """
    try:
        from backend.main import mongo_manager
        db = mongo_manager.db
        
        collection = db["gemini_recordings"]
        doc = collection.find_one({"source_id": source_id})
        
        if not doc:
            raise HTTPException(status_code=404, detail="Recording summary not found")
        
        return RecordingSummaryResponse(
            id=str(doc["_id"]),
            source_id=doc.get("source_id", ""),
            source_collection=doc.get("source_collection", ""),
            title=doc.get("title", ""),
            summary=doc.get("summary", ""),
            summary_kr=doc.get("summary_kr"),
            key_points=doc.get("key_points"),
            participants=doc.get("participants"),
            duration_minutes=doc.get("duration_minutes"),
            language=doc.get("language"),
            processed_at=doc.get("processed_at").isoformat() if doc.get("processed_at") else None,
            model=doc.get("model")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching recording summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai/recordings", response_model=RecordingSummaryResponse)
async def create_recording_summary(
    request: Request,
    summary: RecordingSummary
):
    """
    Create or update an AI-processed recording summary
    """
    try:
        from backend.main import mongo_manager
        db = mongo_manager.db
        
        collection = db["gemini_recordings"]
        
        doc = summary.model_dump()
        doc["processed_at"] = datetime.utcnow()
        
        # Upsert by source_id
        result = collection.update_one(
            {"source_id": summary.source_id},
            {"$set": doc},
            upsert=True
        )
        
        # Get the updated/inserted document
        updated_doc = collection.find_one({"source_id": summary.source_id})
        
        return RecordingSummaryResponse(
            id=str(updated_doc["_id"]),
            source_id=updated_doc.get("source_id", ""),
            source_collection=updated_doc.get("source_collection", ""),
            title=updated_doc.get("title", ""),
            summary=updated_doc.get("summary", ""),
            summary_kr=updated_doc.get("summary_kr"),
            key_points=updated_doc.get("key_points"),
            participants=updated_doc.get("participants"),
            duration_minutes=updated_doc.get("duration_minutes"),
            language=updated_doc.get("language"),
            processed_at=updated_doc.get("processed_at").isoformat() if updated_doc.get("processed_at") else None,
            model=updated_doc.get("model")
        )
        
    except Exception as e:
        logger.error(f"Error creating recording summary: {e}")
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
        model = genai.GenerativeModel("gemini-1.5-flash")
        
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

