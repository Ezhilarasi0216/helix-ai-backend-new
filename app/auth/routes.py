from fastapi import APIRouter, HTTPException, status, Body, UploadFile, File, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database_sql import get_db
from app.models_sql import User as SQLUser
from app.auth.utils import get_password_hash, verify_password
from pydantic import EmailStr, BaseModel
from typing import Optional
import os
import shutil
from datetime import datetime

router = APIRouter()

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

@router.post("/register", response_description="Register a new user")
async def register(user: UserCreate = Body(...), db: AsyncSession = Depends(get_db)):
    # Check if user already exists
    result = await db.execute(select(SQLUser).where(SQLUser.email == user.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Hash password
    hashed_password = get_password_hash(user.password)

    # Create user object
    new_user = SQLUser(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name
    )
    
    # Insert into DB
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return {
        "id": new_user.id,
        "email": new_user.email,
        "full_name": new_user.full_name,
        "created_at": new_user.created_at
    }

@router.post("/login", response_description="Login user")
async def login(user: UserLogin = Body(...), db: AsyncSession = Depends(get_db)):
    # Find user
    result = await db.execute(select(SQLUser).where(SQLUser.email == user.email))
    existing_user = result.scalar_one_or_none()
    
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Verify password
    if not verify_password(user.password, existing_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Return success
    return {
        "message": "Login successful",
        "user_id": str(existing_user.id),
        "full_name": existing_user.full_name,
        "email": existing_user.email,
        "emergency_contact": existing_user.emergency_contact,
        "profile_photo": existing_user.profile_photo
    }

class UpdateProfile(BaseModel):
    full_name: Optional[str] = None
    emergency_contact: Optional[str] = None
    profile_photo: Optional[str] = None

@router.put("/profile/{user_id}", response_description="Update user profile")
async def update_profile(user_id: int, profile: UpdateProfile = Body(...), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SQLUser).where(SQLUser.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if profile.full_name is not None:
        user.full_name = profile.full_name
    if profile.emergency_contact is not None:
        user.emergency_contact = profile.emergency_contact
    if profile.profile_photo is not None:
        user.profile_photo = profile.profile_photo
        
    await db.commit()
    return {"message": "Profile updated successfully"}

@router.post("/profile/{user_id}/upload-photo", response_description="Upload profile photo")
async def upload_photo(user_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    # Create uploads directory if it doesn't exist
    upload_dir = os.path.join("static", "uploads", "profiles")
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate unique filename
    file_extension = os.path.splitext(file.filename)[1]
    filename = f"{user_id}_{int(datetime.utcnow().timestamp())}{file_extension}"
    file_path = os.path.join(upload_dir, filename)
    
    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Update user in DB
    photo_url = f"/static/uploads/profiles/{filename}"
    
    result = await db.execute(select(SQLUser).where(SQLUser.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.profile_photo = photo_url
    await db.commit()
    
    return {"photo_url": photo_url, "message": "Photo uploaded successfully"}
