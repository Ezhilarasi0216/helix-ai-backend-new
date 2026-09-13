from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database_sql import get_db
from app.memory.reminder_service import create_reminder, get_pending_reminders, mark_reminder_completed
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

router = APIRouter()

class ReminderRequest(BaseModel):
    user_id: int
    text: str
    due_date: datetime

@router.post("/set")
async def set_reminder_endpoint(request: ReminderRequest, db: AsyncSession = Depends(get_db)):
    """
    Sets a new reminder for the user.
    """
    reminder_id = await create_reminder(request.user_id, request.text, request.due_date, db)
    return {"status": "success", "reminder_id": reminder_id}

@router.get("/{user_id}")
async def get_user_reminders(user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Retrieves all pending reminders for a user.
    """
    reminders = await get_pending_reminders(user_id, db)
    return {"reminders": reminders}

@router.post("/complete/{reminder_id}")
async def complete_reminder(reminder_id: int, db: AsyncSession = Depends(get_db)):
    """
    Marks a reminder as completed.
    """
    await mark_reminder_completed(reminder_id, db)
    return {"status": "success"}
