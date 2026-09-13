from fastapi import APIRouter, HTTPException, UploadFile, File, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from app.database_sql import get_db
from app.models_sql import UserProfile as SQLUserProfile, User as SQLUser
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
import os
import uuid

router = APIRouter()

class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    phone_number: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    bio: Optional[str] = None
    preferred_language: Optional[str] = None
    timezone: Optional[str] = None

@router.get("/{user_id}")
async def get_profile(user_id: int, db: AsyncSession = Depends(get_db)):
    """Get user profile by user_id"""
    try:
        result = await db.execute(
            select(SQLUserProfile)
            .options(joinedload(SQLUserProfile.user))
            .where(SQLUserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        
        if not profile:
            # Check if user exists
            user_result = await db.execute(select(SQLUser).where(SQLUser.id == user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Create default profile
            profile = SQLUserProfile(
                user_id=user_id,
                preferred_language="en",
                timezone="Asia/Kolkata"
            )
            db.add(profile)
            await db.commit()
            await db.refresh(profile)
            # Re-fetch with join
            result = await db.execute(
                select(SQLUserProfile)
                .options(joinedload(SQLUserProfile.user))
                .where(SQLUserProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()
        
        # Merge user info for UI convenience
        profile_dict = {
            "id": profile.id,
            "user_id": profile.user_id,
            "full_name": profile.user.full_name if profile.user else "",
            "email": profile.user.email if profile.user else "",
            "date_of_birth": profile.date_of_birth,
            "gender": profile.gender,
            "city": profile.city,
            "country": profile.country,
            "phone_number": profile.phone_number,
            "emergency_contact_name": profile.emergency_contact_name,
            "emergency_contact_phone": profile.emergency_contact_phone,
            "bio": profile.bio,
            "preferred_language": profile.preferred_language,
            "timezone": profile.timezone,
            "avatar_url": profile.avatar_url
        }
        return profile_dict
    
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{user_id}")
async def update_profile(user_id: int, update_data: ProfileUpdateRequest, db: AsyncSession = Depends(get_db)):
    """Update user profile"""
    try:
        result = await db.execute(select(SQLUserProfile).where(SQLUserProfile.user_id == user_id))
        profile = result.scalar_one_or_none()
        
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        if update_data.date_of_birth: profile.date_of_birth = update_data.date_of_birth.isoformat()
        if update_data.gender: profile.gender = update_data.gender
        if update_data.city: profile.city = update_data.city
        if update_data.country: profile.country = update_data.country
        if update_data.phone_number: profile.phone_number = update_data.phone_number
        if update_data.emergency_contact_name: profile.emergency_contact_name = update_data.emergency_contact_name
        if update_data.emergency_contact_phone: profile.emergency_contact_phone = update_data.emergency_contact_phone
        if update_data.bio: profile.bio = update_data.bio
        if update_data.preferred_language: profile.preferred_language = update_data.preferred_language
        if update_data.timezone: profile.timezone = update_data.timezone
        
        if update_data.full_name:
            # Update full_name in User table too
            user_result = await db.execute(select(SQLUser).where(SQLUser.id == user_id))
            user = user_result.scalar_one_or_none()
            if user: user.full_name = update_data.full_name
            
        await db.commit()
        return {"message": "Profile updated successfully"}
    
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/avatar/{user_id}")
async def upload_avatar(user_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Upload profile avatar"""
    try:
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        upload_dir = os.path.join("static", "avatars")
        os.makedirs(upload_dir, exist_ok=True)
        
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{user_id}_{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        avatar_url = f"/static/avatars/{unique_filename}"
        
        result = await db.execute(select(SQLUserProfile).where(SQLUserProfile.user_id == user_id))
        profile = result.scalar_one_or_none()
        if profile:
            profile.avatar_url = avatar_url
            await db.commit()
        
        return {
            "message": "Avatar uploaded successfully",
            "avatar_url": avatar_url
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
