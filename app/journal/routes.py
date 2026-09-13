from fastapi import APIRouter, HTTPException, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database_sql import get_db
from app.journal.service import save_journal_entry, get_user_journals
from pydantic import BaseModel

router = APIRouter()

class JournalCreateRequest(BaseModel):
    user_id: int
    content: str

@router.post("/")
async def create_entry(request: JournalCreateRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await save_journal_entry(request.user_id, request.content, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}")
async def get_entries(user_id: int, db: AsyncSession = Depends(get_db)):
    try:
        entries = await get_user_journals(user_id, db)
        return {"entries": entries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
