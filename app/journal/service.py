import os
from groq import Groq
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models_sql import JournalEntry as SQLJournalEntry
from datetime import datetime
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

async def analyze_journal(content: str) -> str:
    """
    Generates a short, empathetic AI insight based on the journal content.
    """
    try:
        prompt = f"""You are Healix AI, an empathetic mental health assistant.
The following is a user's journal entry. Provide a very short (1 sentence), warm, and insightful feedback comment to the user.
If they seem sad, be supportive. If they seem happy, celebrate with them. If they are stressed, offer calm encouragement.

Journal Entry: "{content}"

Insight:"""

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )
        
        insight = completion.choices[0].message.content.strip()
        # Remove quotes if AI included them
        if insight.startswith('"') and insight.endswith('"'):
            insight = insight[1:-1]
        return insight
    except Exception as e:
        logger.error(f"Error analyzing journal: {e}")
        return "Thank you for sharing your thoughts today. Healix is here for you."

async def save_journal_entry(user_id: int, content: str, db: AsyncSession):
    insight = await analyze_journal(content)
    
    new_entry = SQLJournalEntry(
        user_id=user_id,
        content=content,
        timestamp=datetime.utcnow(),
        ai_insight=insight
    )
    
    db.add(new_entry)
    await db.commit()
    await db.refresh(new_entry)
    
    return {
        "id": new_entry.id,
        "ai_insight": insight,
        "timestamp": new_entry.timestamp
    }

async def get_user_journals(user_id: int, db: AsyncSession):
    result = await db.execute(
        select(SQLJournalEntry).where(SQLJournalEntry.user_id == user_id).order_by(SQLJournalEntry.timestamp.desc())
    )
    return result.scalars().all()
