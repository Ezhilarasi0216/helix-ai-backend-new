from datetime import datetime
from sqlalchemy import select, update, and_
from app.database_sql import async_session
from app.models_sql import MoodHistory as SQLMoodHistory

async def save_daily_mood(user_id: int, emotions: dict):
    """
    Saves or updates the aggregate mood for a user on the current day.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    async with async_session() as db:
        # Check if a record already exists
        result = await db.execute(
            select(SQLMoodHistory).where(and_(SQLMoodHistory.user_id == user_id, SQLMoodHistory.date == today))
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            new_aggregate = existing.aggregate_emotions.copy()
            for k, v in emotions.items():
                if k in new_aggregate:
                    new_aggregate[k] = (new_aggregate[k] + v) / 2
                else:
                    new_aggregate[k] = v
            
            existing.aggregate_emotions = new_aggregate
            await db.commit()
        else:
            new_history = SQLMoodHistory(
                user_id=user_id,
                date=today,
                aggregate_emotions=emotions
            )
            db.add(new_history)
            await db.commit()

async def get_mood_trend(user_id: int, days: int = 7):
    """
    Retrieves the mood trend for the last N days.
    """
    async with async_session() as db:
        result = await db.execute(
            select(SQLMoodHistory)
            .where(SQLMoodHistory.user_id == user_id)
            .order_by(SQLMoodHistory.date.desc())
            .limit(days)
        )
        return result.scalars().all()
