import os
from urllib import response
import httpx
import json
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models_sql import ChatSession as SQLChatSession, Message as SQLMessage, UserProfile as SQLUserProfile
from app.emotion.text_emotion import analyze_text_emotion
from dotenv import load_dotenv
from app.memory.memory_service import extract_and_save_facts, get_relevant_memories
from app.emotion.emotion_history import save_daily_mood
from app.safety.crisis_detector import detect_crisis
from app.safety.ethical_filter import ethical_filter_response
from app.safety.helpline_service import get_helpline_info
from groq import Groq
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Healix, a friendly mental wellness companion. Talk like a caring friend, not a doctor.

RULES:
1. Be warm, calm, and supportive.
2. Keep responses short and natural.
3. DO NOT give medical diagnosis.
4. Encourage positive habits gently.
5. If the user sounds sad, respond with deep empathy.
6. Discuss ONLY mental health, emotional well-being, or psychiatric support. Redirect off-topic queries politely.

LANGUAGE RULES:
- If user writes in Tamil → reply in Tamil.
- If user writes in English → reply in English.
- If mixed → reply in same mixed style.
- Use soft, friendly Tamil words (avoid formal/robotic Tamil).

TECHNICAL REQUIREMENT:
You MUST respond in JSON format with the following keys:
- "response": Your empathetic text reply.
- "emotions": An object with Plutchnik's 8 emotions (Joy, Trust, Fear, Surprise, Sadness, Disgust, Anger, Anticipation), each a value from 0 to 1 based on the user's current message.
- "safety_risk": A string "HIGH", "MEDIUM", or "LOW" based on whether the user's message indicates self-harm or crisis.
"""

from typing import Any

async def process_chat(user_id: Any, message_text: str, session_id: int = None, language: str = "en", db: AsyncSession = None):
    # Determine if this is a guest user
    try:
        user_id = int(str(user_id))
        is_guest = False
    except (ValueError, TypeError):
        is_guest = True
        user_id = 1 # Fallback to user 1 for DB operations if needed, or skip them
    # Increment Wellness Score
    if not is_guest:
        try:
            prof_result = await db.execute(select(SQLUserProfile).where(SQLUserProfile.user_id == user_id))
            profile = prof_result.scalar_one_or_none()
            if profile:
                profile.wellness_score += 1
                await db.commit()
        except Exception as e:
            logger.error(f"Error updating wellness score: {e}")

    # 1. Crisis Check
    safety_risk = await detect_crisis(message_text)
    if safety_risk in ["CRITICAL", "HIGH"]:
        helpline = get_helpline_info()
        crisis_msg = f"I'm very concerned about you. Please reach out to someone who can help right now: {helpline['india']['name']} at {helpline['india']['number']}. {helpline['emergency_message']}"
        return {
            "response": crisis_msg,
            "emotion_detected": {"Sadness": 1.0, "Fear": 0.5},
            "safety_risk": safety_risk,
            "session_id": session_id or 0
        }

    # 2. Find or Create Session
    session = None
    if not is_guest:
        if session_id:
            result = await db.execute(select(SQLChatSession).where(SQLChatSession.id == session_id))
            session = result.scalar_one_or_none()
        
        if not session:
            result = await db.execute(
                select(SQLChatSession)
                .where(SQLChatSession.user_id == user_id)
                .order_by(desc(SQLChatSession.start_time))
                .limit(1)
            )
            session = result.scalar_one_or_none()

        if not session:
            session = SQLChatSession(user_id=user_id)
            db.add(session)
            await db.commit()
            await db.refresh(session)
        
        session_id = session.id
    else:
        session_id = session_id or 0

    # 3. Memory Retrieval
    memories = []
    history = []
    if not is_guest:
        memories = await get_relevant_memories(user_id, message_text)
        
        # Get recent history for context
        msg_result = await db.execute(
            select(SQLMessage)
            .where(SQLMessage.session_id == session_id)
            .order_by(desc(SQLMessage.timestamp))
            .limit(10)
        )
        history = msg_result.scalars().all()
        history = sorted(history, key=lambda x: x.timestamp)

    memory_context = f"\nRelevant past memories: {memories}" if memories else ""

    full_system_prompt = SYSTEM_PROMPT + memory_context
    if language == 'ta':
        full_system_prompt += "\nThe user has preference for TAMIL. You MUST respond in TAMIL code-mixed with English for a natural feel, or pure Tamil if formal."
    
    groq_history = [{"role": "user", "content": f"SYSTEM INSTRUCTIONS: {full_system_prompt}"}]
    
    for m in history:
        groq_history.append({"role": m.role, "content": m.content})
    
    groq_history.append({"role": "user", "content": message_text})

    try:
        # 4. AI Response Generation
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment")
            
        content = None
        models = ["openai/gpt-oss-120b"]
        
        for model_name in models:
            if content: break
            
            try:
                async with httpx.AsyncClient(timeout=30.0) as client_http:
                    response = await client_http.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": model_name,
                            "messages": groq_history,
                            "response_format": {"type": "json_object"}
                        }
                    )
                    response = await client_http.post(
    "https://api.groq.com/openai/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    },
    json={
        "model": model_name,
        "messages": groq_history,
        "response_format": {"type": "json_object"}
    }
)
                    print("GROQ STATUS:", response.status_code)
                    print("GROQ RESPONSE:", response.text)

                    if response.status_code == 200:
                        content = response.json()['choices'][0]['message']['content']
                        break
            except Exception as e:
                logger.error(f"Failed with {model_name}: {e}")

        if not content:
            raise ValueError("Empty response from AI")

        result_data = json.loads(content)
        assistant_text = result_data.get("response", "I'm right here with you.")
        emotion_result = result_data.get("emotions", {
            "Joy": 0, "Trust": 0, "Fear": 0, "Surprise": 0, 
            "Sadness": 0, "Disgust": 0, "Anger": 0, "Anticipation": 0
        })

        # 5. Ethical Filter
        if not ethical_filter_response(assistant_text):
            assistant_text = "I want to make sure I'm providing the best support possible. Let's talk about how you're feeling right now."
            
        # 6. Memory & Mood Updates (Background)
        # Note: These need to be updated to SQL too
        asyncio.create_task(extract_and_save_facts(user_id, message_text))
        asyncio.create_task(save_daily_mood(user_id, emotion_result))

    except Exception as e:
        logger.error(f"Chat processing error: {e}")
        assistant_text = "I'm sorry, I'm having trouble connecting right now. But I'm still here for you."
        emotion_result = {"Joy": 0, "Trust": 0, "Fear": 0, "Surprise": 0, "Sadness": 0, "Disgust": 0, "Anger": 0, "Anticipation": 0}
        safety_risk = "LOW"

    # 7. Persistence
    if not is_guest:
        user_msg = SQLMessage(session_id=session_id, role="user", content=message_text, emotions=emotion_result)
        assistant_msg = SQLMessage(session_id=session_id, role="assistant", content=assistant_text)
        
        db.add(user_msg)
        db.add(assistant_msg)
        await db.commit()

    # Get updated score
    final_score = 0
    if not is_guest:
        prof_result = await db.execute(select(SQLUserProfile).where(SQLUserProfile.user_id == user_id))
        profile = prof_result.scalar_one_or_none()
        if profile:
            final_score = profile.wellness_score

    return {
        "response": assistant_text,
        "emotion_detected": emotion_result,
        "safety_risk": safety_risk,
        "session_id": session_id,
        "wellness_score": final_score,
        "crisis_detected": safety_risk in ["CRITICAL", "HIGH", "MEDIUM"],
        "crisis_data": {"severity": safety_risk.lower()} if safety_risk != "LOW" else None
    }
