from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import os

from api.auth import get_current_user
from api.database import get_db

router = APIRouter(prefix="/api/user", tags=["user"])

class RegisterRequest(BaseModel):
    agreed_at: int

class SelectCourseRequest(BaseModel):
    course_name: str

class PhoneRequest(BaseModel):
    phone: str

@router.post("/register")
async def register_user(
    data: RegisterRequest,
    current_user: dict = Depends(get_current_user)
):
    """Register user after contract acceptance"""
    user_id = current_user['user_id']
    username = current_user.get('username', '')
    full_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
    if not full_name:
        full_name = f"User{user_id}"
    
    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute("""
            INSERT INTO users(user_id, username, full_name, agreed_at, group_id, expires_at)
            VALUES($1, $2, $3, $4, 0, 0)
            ON CONFLICT(user_id) DO UPDATE SET
                username=EXCLUDED.username,
                full_name=EXCLUDED.full_name,
                agreed_at=EXCLUDED.agreed_at
        """, user_id, username, full_name, data.agreed_at)
    
    return {"success": True, "message": "User registered"}

@router.post("/select-course")
async def select_course(
    data: SelectCourseRequest,
    current_user: dict = Depends(get_current_user)
):
    """Save selected course"""
    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE users SET course_name=$1 WHERE user_id=$2",
            data.course_name, current_user['user_id']
        )
    
    return {"success": True, "message": "Course selected"}

@router.post("/phone")
async def save_phone(
    data: PhoneRequest,
    current_user: dict = Depends(get_current_user)
):
    """Save phone number"""
    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE users SET phone=$1 WHERE user_id=$2",
            data.phone, current_user['user_id']
        )
    
    return {"success": True, "message": "Phone saved"}

@router.post("/payment")
async def submit_payment(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Submit payment photo"""
    
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, f"{current_user['user_id']}_{int(datetime.utcnow().timestamp())}.jpg")
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    db = await get_db()
    async with db.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO payments(user_id, photo_file, status, created_at)
            VALUES($1, $2, 'pending', $3)
            RETURNING id
        """, current_user['user_id'], file_path, int(datetime.utcnow().timestamp()))
    
    return {
        "success": True,
        "message": "Payment submitted",
        "payment_id": row['id']
    }

@router.get("/me")
async def get_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user info"""
    db = await get_db()
    async with db.acquire() as conn:
        user = await conn.fetchrow("""
            SELECT user_id, username, full_name, phone, course_name, agreed_at, expires_at
            FROM users WHERE user_id=$1
        """, current_user['user_id'])
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "user_id": user['user_id'],
            "username": user['username'],
            "full_name": user['full_name'],
            "phone": user['phone'],
            "course_name": user['course_name'],
            "agreed_at": user['agreed_at'],
            "expires_at": user['expires_at']
        }

@router.get("/subscription")
async def get_subscription(current_user: dict = Depends(get_current_user)):
    """Get user subscription status"""
    db = await get_db()
    async with db.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT expires_at FROM users WHERE user_id=$1",
            current_user['user_id']
        )
        
        groups = await conn.fetch("""
            SELECT ug.group_id, ug.expires_at
            FROM user_groups ug
            WHERE ug.user_id=$1
        """, current_user['user_id'])
        
        now = int(datetime.utcnow().timestamp())
        is_active = (user and user['expires_at'] > now) or any(g['expires_at'] > now for g in groups)
        
        return {
            "is_active": is_active,
            "expires_at": user['expires_at'] if user else 0,
            "groups": [{"group_id": g['group_id'], "expires_at": g['expires_at']} for g in groups]
        }
