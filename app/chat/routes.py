from fastapi import APIRouter, Body, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from app.database_sql import get_db
from app.models_sql import ChatSession as SQLChatSession, Message as SQLMessage, MoodHistory as SQLMoodHistory
from app.chat.service import process_chat
from app.safety.risk_classifier import classify_risk
from app.safety.intervention import get_intervention
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from collections import defaultdict
import random

router = APIRouter()

from typing import Optional, Any

class ChatRequest(BaseModel):
    message: str
    user_id: Any
    session_id: Optional[int] = None
    language: Optional[str] = "en"

@router.post("/")
async def chat_endpoint(request: ChatRequest = Body(...), db: AsyncSession = Depends(get_db)):
    # 1. Safety Check
    risk_level = await classify_risk(request.message)
    if risk_level == "HIGH":
        intervention = get_intervention(risk_level)
        return {
            "type": "intervention",
            "risk_level": risk_level,
            "response": intervention
        }
    
    # 2. Process Chat (Persistence + Proxy)
    try:
        result = await process_chat(request.user_id, request.message, request.session_id, request.language, db)
        return {
            "type": "chat",
            "risk_level": risk_level,
            "response": result["response"],
            "session_id": result["session_id"],
            "metadata": {
                "emotion": result["emotion_detected"],
                "wellness_score": result.get("wellness_score", 0)
            }
        }
    except Exception as e:
        import traceback
        tb_str = traceback.format_exc()
        print(f"Error in chat endpoint: {e}\nTraceback:\n{tb_str}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/latest/{user_id}")
async def get_latest_session(user_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(SQLChatSession)
            .where(SQLChatSession.user_id == user_id)
            .order_by(desc(SQLChatSession.start_time))
            .limit(1)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            return {"messages": [], "session_id": None}
        
        # Fetch messages for this session
        msg_result = await db.execute(
            select(SQLMessage)
            .where(SQLMessage.session_id == session.id)
            .order_by(SQLMessage.timestamp)
        )
        messages = msg_result.scalars().all()
        
        return {
            "session_id": session.id,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp,
                    "emotions": m.emotions
                } for m in messages
            ]
        }
    except Exception as e:
        print(f"Error in get_latest_session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/{user_id}")
async def get_mood_analytics(user_id: int, db: AsyncSession = Depends(get_db)):
    # 1. Fetch messages from last 7 days
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    
    result = await db.execute(
        select(SQLMessage, SQLChatSession.start_time)
        .join(SQLChatSession)
        .where(and_(SQLChatSession.user_id == user_id, SQLMessage.timestamp >= seven_days_ago))
        .order_by(SQLMessage.timestamp)
    )
    msg_data = result.all()
    
    # 2. Daily aggregation
    daily_stats = defaultdict(lambda: {
        "Joy": [], "Trust": [], "Fear": [], "Surprise": [],
        "Sadness": [], "Disgust": [], "Anger": [], "Anticipation": [],
        "message_count": 0,
        "night_chat_count": 0
    })
    
    for msg, session_start in msg_data:
        day_str = msg.timestamp.strftime("%Y-%m-%d")
        if msg.role == "user":
            daily_stats[day_str]["message_count"] += 1
            
            # Check for night chat (10 PM - 5 AM)
            if msg.timestamp.hour >= 22 or msg.timestamp.hour <= 5:
                daily_stats[day_str]["night_chat_count"] += 1
            
            if msg.emotions:
                for em, val in msg.emotions.items():
                    if em in daily_stats[day_str]:
                        daily_stats[day_str][em].append(val)
    
    # 3. Calculate averages
    analytics_data = []
    sorted_days = sorted(daily_stats.keys())
    
    for day in sorted_days:
        stats = daily_stats[day]
        averages = {
            "date": day,
            "message_count": stats["message_count"],
            "night_chat_count": stats["night_chat_count"]
        }
        for em in ["Joy", "Trust", "Fear", "Surprise", "Sadness", "Disgust", "Anger", "Anticipation"]:
            values = stats[em]
            averages[em] = round(sum(values) / len(values), 2) if values else 0
        analytics_data.append(averages)
        
    if not analytics_data:
        # Fallback example data
        today = datetime.utcnow()
        for i in range(7):
            d = (today - timedelta(days=(6-i))).strftime("%Y-%m-%d")
            analytics_data.append({
                "date": d,
                "message_count": random.randint(3, 8),
                "night_chat_count": random.randint(0, 2),
                "Joy": random.randint(20, 80),
                "Trust": random.randint(20, 60),
                "Fear": random.randint(10, 30),
                "Surprise": random.randint(10, 40),
                "Sadness": random.randint(10, 50),
                "Disgust": random.randint(0, 20),
                "Anger": random.randint(0, 20),
                "Anticipation": random.randint(40, 70)
            })

    return {
        "user_id": user_id,
        "period": "last_7_days",
        "data": analytics_data
    }

@router.get("/heatmap/{user_id}")
async def get_heatmap_analytics(user_id: int, db: AsyncSession = Depends(get_db)):
    # 1. Fetch mood history from last 90 days
    ninety_days_ago = datetime.utcnow() - timedelta(days=90)
    
    result = await db.execute(
        select(SQLMoodHistory)
        .where(and_(SQLMoodHistory.user_id == user_id, SQLMoodHistory.date >= ninety_days_ago.strftime("%Y-%m-%d")))
        .order_by(SQLMoodHistory.date)
    )
    entries = result.scalars().all()
    
    heatmap_data = []
    for entry in entries:
        emotions = entry.aggregate_emotions
        if not emotions: continue
        
        dominant = max(emotions.items(), key=lambda x: x[1])
        
        heatmap_data.append({
            "date": entry.date,
            "dominant_emotion": dominant[0],
            "intensity": dominant[1],
            "emotions": emotions
        })
        
    if not heatmap_data:
        emotions_list = ["Joy", "Trust", "Fear", "Surprise", "Sadness", "Calm"]
        today = datetime.utcnow()
        for i in range(30):
            d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            dom = random.choice(emotions_list)
            heatmap_data.append({
                "date": d,
                "dominant_emotion": dom,
                "intensity": random.randint(40, 90),
                "emotions": {dom: 80}
            })

    return {
        "user_id": user_id,
        "period": "last_90_days",
        "data": heatmap_data
    }

@router.get("/insights/{user_id}")
async def get_user_insights(user_id: int):
    from app.emotion.mood_analyzer import get_advanced_insights
    try:
        insights = await get_advanced_insights(user_id)
        return insights
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
