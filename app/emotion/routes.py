from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.emotion.mood_analyzer import generate_weekly_mood_summary
from app.emotion.emotion_history import get_mood_trend
from app.emotion.text_emotion import analyze_text_emotion
from sqlalchemy.ext.asyncio import AsyncSession
from app.database_sql import get_db

router = APIRouter()

class TextRequest(BaseModel):
    text: str

@router.post("/analyze/text")
async def analyze_text(request: TextRequest):
    """
    Analyzes the emotion of the provided text.
    """
    result = analyze_text_emotion(request.text)
    return result

@router.get("/summary/{user_id}")
async def get_mood_summary(user_id: int):
    """
    Retrieves the weekly mood summary for the user.
    """
    summary = await generate_weekly_mood_summary(user_id)
    return {"summary": summary}

@router.get("/trend/{user_id}")
async def get_user_mood_trend(user_id: int):
    """
    Retrieves the recent mood trend for the user.
    """
    trend = await get_mood_trend(user_id, 7)
    return {"trend": trend}

@router.get("/clinician-note/{user_id}")
async def get_user_clinician_note(user_id: int):
    """
    Retrieves a formal clinician's note for the user.
    """
    from app.emotion.mood_analyzer import generate_clinician_note
    note = await generate_clinician_note(user_id)
    return {"note": note}
