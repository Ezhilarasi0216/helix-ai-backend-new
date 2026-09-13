import os
import json
import httpx
from sqlalchemy import select, desc
from app.database_sql import async_session
from app.models_sql import UserMemory as SQLUserMemory
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

async def call_groq(prompt: str, json_format: bool = True):
    """Utility to call Groq for memory tasks with a timeout"""
    api_key = os.getenv("GROQ_API_KEY")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openai/gpt-oss-120b",
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            if response.status_code != 200:
                logger.error(f"Groq Memory Error: {response.text}")
                return None
                
            data = response.json()
            content = data['choices'][0]['message']['content']
            
            if json_format:
                # Basic JSON extraction
                import re
                match = re.search(r'\{.*\}|\[.*\]', content, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
                return json.loads(content)
            return content
    except Exception as e:
        logger.error(f"Memory API call failed: {e}")
        return None

async def extract_and_save_facts(user_id: int, text: str):
    prompt = f"""Extract important personal facts or preferences from this message: "{text}"
    Example: "User likes coffee", "User has exams".
    Return ONLY a JSON object: {{"facts": ["fact1", "fact2"]}}. If none, return {{"facts": []}}.
    """
    
    data = await call_groq(prompt)
    if data and isinstance(data, dict):
        facts = data.get("facts", [])
        async with async_session() as db:
            for fact in facts:
                new_memory = SQLUserMemory(user_id=user_id, fact=fact, category="general")
                db.add(new_memory)
            await db.commit()

async def get_relevant_memories(user_id: int, query: str):
    try:
        async with async_session() as db:
            result = await db.execute(
                select(SQLUserMemory)
                .where(SQLUserMemory.user_id == user_id)
                .order_by(desc(SQLUserMemory.timestamp))
                .limit(10)
            )
            memories = result.scalars().all()
    except Exception as e:
        logger.error(f"Error fetching memories: {e}")
        return []
        
    if not memories:
        return []
    
    facts_list = [m.fact for m in memories]
    prompt = f"""Message: "{query}"\nMemories: {facts_list}\nIdentify relevant memories. Return JSON: {{"relevant_memories": ["mem1"]}}"""
    
    data = await call_groq(prompt)
    if data and isinstance(data, dict):
        return data.get("relevant_memories", [])
    return facts_list[:2]

