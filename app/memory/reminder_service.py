from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models_sql import Reminder as SQLReminder

async def create_reminder(user_id: int, text: str, due_date: datetime, db: AsyncSession):
    """
    Creates a new reminder for the user.
    """
    new_reminder = SQLReminder(
        user_id=user_id,
        text=text,
        due_date=due_date
    )
    db.add(new_reminder)
    await db.commit()
    await db.refresh(new_reminder)
    return new_reminder.id

async def get_pending_reminders(user_id: int, db: AsyncSession):
    """
    Retrieves all non-completed reminders for a user.
    """
    result = await db.execute(
        select(SQLReminder).where(SQLReminder.user_id == user_id, SQLReminder.is_completed == False)
    )
    return result.scalars().all()

async def mark_reminder_completed(reminder_id: int, db: AsyncSession):
    """
    Marks a reminder as completed.
    """
    await db.execute(
        update(SQLReminder).where(SQLReminder.id == reminder_id).values(is_completed=True)
    )
    await db.commit()
