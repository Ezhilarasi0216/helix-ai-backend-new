from fastapi import APIRouter, HTTPException, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.database_sql import get_db
from app.models_sql import EmergencyContact as SQLEmergencyContact
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter()

class EmergencyContactBase(BaseModel):
    name: str
    phone: str
    relationship: str
    is_primary: bool = False

@router.post("/add")
async def add_emergency_contact(
    user_id: int = Body(...),
    contact: EmergencyContactBase = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """Add a new emergency contact for the user."""
    new_contact = SQLEmergencyContact(
        user_id=user_id,
        name=contact.name,
        phone=contact.phone,
        relationship=contact.relationship,
        is_primary=contact.is_primary
    )
    db.add(new_contact)
    await db.commit()
    await db.refresh(new_contact)
    
    return {
        "success": True,
        "contact_id": new_contact.id,
        "message": "Emergency contact added successfully"
    }

@router.get("/list/{user_id}")
async def get_emergency_contacts(user_id: int, db: AsyncSession = Depends(get_db)):
    """Get all emergency contacts for a user."""
    result = await db.execute(select(SQLEmergencyContact).where(SQLEmergencyContact.user_id == user_id))
    contacts = result.scalars().all()
    return {"contacts": contacts}

@router.delete("/delete/{contact_id}")
async def delete_emergency_contact(contact_id: int, db: AsyncSession = Depends(get_db)):
    """Delete an emergency contact."""
    result = await db.execute(delete(SQLEmergencyContact).where(SQLEmergencyContact.id == contact_id))
    await db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    return {"success": True, "message": "Emergency contact deleted"}

@router.put("/update/{contact_id}")
async def update_emergency_contact(
    contact_id: int,
    contact: EmergencyContactBase = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """Update an emergency contact."""
    result = await db.execute(
        update(SQLEmergencyContact)
        .where(SQLEmergencyContact.id == contact_id)
        .values(
            name=contact.name,
            phone=contact.phone,
            relationship=contact.relationship,
            is_primary=contact.is_primary
        )
    )
    await db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    return {"success": True, "message": "Emergency contact updated"}
