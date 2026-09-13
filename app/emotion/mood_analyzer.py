import os
import json
import httpx
from datetime import datetime
from sqlalchemy import select, update
from app.database_sql import async_session
from app.models_sql import MoodHistory as SQLMoodHistory
from app.emotion.emotion_history import get_mood_trend
import logging

logger = logging.getLogger(__name__)

async def call_groq_analytics(prompt: str, json_format: bool = False):
    """Utility to call Groq for analytics tasks with a timeout"""
    api_key = os.getenv("GROQ_API_KEY")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            if response.status_code != 200:
                logger.error(f"Groq Analytics Error: {response.text}")
                return None
                
            data = response.json()
            content = data['choices'][0]['message']['content']
            
            if json_format:
                import re
                match = re.search(r'\{.*\}|\[.*\]', content, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
                return json.loads(content)
            return content
    except Exception as e:
        logger.error(f"Analytics API call failed: {e}")
        return None

async def generate_weekly_mood_summary(user_id: int):
    history = await get_mood_trend(user_id, 7)
    if not history:
        return "It looks like we're just getting started! Once we've chatted more, I'll be able to share deeper insights."
    
    latest = history[0]
    if latest.summary:
        return latest.summary

    history_str = "\n".join([f"{h.date}: {json.dumps(h.aggregate_emotions)}" for h in history])
    prompt = f"Summarize weekly mood history warmly: {history_str}"
    
    summary = await call_groq_analytics(prompt, False)
    if summary:
        async with async_session() as db:
            await db.execute(
                update(SQLMoodHistory)
                .where(SQLMoodHistory.id == latest.id)
                .values(summary=summary)
            )
            await db.commit()
        return summary
    return "I'm here for you, even if the analysis is slow right now."

async def get_advanced_insights(user_id: int):
    history = await get_mood_trend(user_id, 7)
    if not history:
        return {"sentiment_score": 72, "top_triggers": ["Unknown"], "actionable_suggestions": ["Journal today."]}
    
    latest = history[0]
    if latest.sentiment_score is not None:
        return {
            "sentiment_score": latest.sentiment_score,
            "top_triggers": latest.top_triggers or [],
            "actionable_suggestions": latest.actionable_suggestions or []
        }

    history_summary = []
    for h in history:
        if h.aggregate_emotions:
            top_emotion = max(h.aggregate_emotions.items(), key=lambda x: x[1])[0]
            history_summary.append(f"{h.date}: {top_emotion}")

    prompt = f"Analyze 7-day mood history. Return JSON: {{'sentiment_score': 0-100, 'top_triggers': [], 'actionable_suggestions': []}}\nHistory: {history_summary}"
    
    insights = await call_groq_analytics(prompt, True)
    if insights:
        async with async_session() as db:
            await db.execute(
                update(SQLMoodHistory)
                .where(SQLMoodHistory.id == latest.id)
                .values(
                    sentiment_score=insights.get("sentiment_score"),
                    top_triggers=insights.get("top_triggers"),
                    actionable_suggestions=insights.get("actionable_suggestions")
                )
            )
            await db.commit()
        return insights
    return {"sentiment_score": 60, "top_triggers": ["Unknown"], "actionable_suggestions": ["Breathe deep."]}

async def generate_clinician_note(user_id: int):
    history = await get_mood_trend(user_id, 14)
    if not history:
        return "Not enough data for clinical summary."
    
    history_str = "\n".join([f"{h.date}: {json.dumps(h.aggregate_emotions)}" for h in history])
    prompt = f"Act as clinical evaluator. Provide professional Clinician Note for this 14-day data: {history_str}"
    
    note = await call_groq_analytics(prompt, False)
    return note if note else "Clinical summary currently unavailable."

