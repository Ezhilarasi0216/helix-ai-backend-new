from datetime import datetime, timedelta
from app.memory.reminder_service import get_pending_reminders

async def check_for_due_reminders(user_id: str):
    """
    Checks if there are any reminders due right now for the user.
    """
    reminders = await get_pending_reminders(user_id)
    now = datetime.utcnow()
    
    due = []
    for r in reminders:
        # If due within the last 5 minutes and not notified (in a real app we'd track notification status)
        if r["due_date"] <= now and r["due_date"] > now - timedelta(minutes=5):
            due.append(r)
            
    return due
