from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import List, Optional
import os

from api.auth import get_current_user
from api.database import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])

ADMIN_IDS = []
_raw_admins = os.getenv("ADMIN_IDS", "")
if _raw_admins.strip():
    for x in _raw_admins.split(","):
        x = x.strip()
        if x.lstrip("-").isdigit():
            ADMIN_IDS.append(int(x))

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def require_admin(current_user: dict = Depends(get_current_user)):
    if not is_admin(current_user['user_id']):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

class ApprovePaymentRequest(BaseModel):
    payment_id: int
    group_ids: List[int]
    start_date: Optional[str] = None

class RejectPaymentRequest(BaseModel):
    payment_id: int

@router.get("/stats")
async def get_stats(admin: dict = Depends(require_admin)):
    """Get admin statistics"""
    db = await get_db()
    now = int(datetime.utcnow().timestamp())
    
    async with db.acquire() as conn:
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
        
        active_main = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE expires_at > $1 AND group_id > 0", now
        )
        active_groups = await conn.fetchval(
            "SELECT COUNT(DISTINCT user_id) FROM user_groups WHERE expires_at > $1", now
        )
        active_users = max(active_main or 0, active_groups or 0)
        
        expired_users = (total_users or 0) - active_users
        
        pending_payments = await conn.fetchval(
            "SELECT COUNT(*) FROM payments WHERE status='pending'"
        )
        
        approved_payments = await conn.fetchval(
            "SELECT COUNT(*) FROM payments WHERE status='approved'"
        )
    
    return {
        "total_users": total_users or 0,
        "active_users": active_users,
        "expired_users": expired_users,
        "pending_payments": pending_payments or 0,
        "approved_payments": approved_payments or 0
    }

@router.get("/payments/pending")
async def get_pending_payments(admin: dict = Depends(require_admin)):
    """Get all pending payments"""
    db = await get_db()
    async with db.acquire() as conn:
        payments = await conn.fetch("""
            SELECT p.id, p.user_id, p.photo_file, p.created_at,
                   u.username, u.full_name, u.phone, u.course_name, u.agreed_at
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.status='pending'
            ORDER BY p.created_at DESC
        """)
        
        result = []
        for p in payments:
            result.append({
                "id": p['id'],
                "user_id": p['user_id'],
                "username": p['username'],
                "full_name": p['full_name'],
                "phone": p['phone'],
                "course_name": p['course_name'],
                "photo_file": p['photo_file'],
                "created_at": p['created_at'],
                "agreed_at": p['agreed_at']
            })
        
        return {"payments": result}

@router.get("/payments/approved")
async def get_approved_payments(
    limit: int = 10,
    admin: dict = Depends(require_admin)
):
    """Get approved payments"""
    db = await get_db()
    async with db.acquire() as conn:
        payments = await conn.fetch(f"""
            SELECT p.id, p.user_id, p.created_at,
                   u.username, u.full_name, u.phone, u.course_name
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.status='approved'
            ORDER BY p.created_at DESC
            LIMIT {limit}
        """)
        
        result = []
        for p in payments:
            groups = await conn.fetch(
                "SELECT group_id FROM user_groups WHERE user_id=$1", p['user_id']
            )
            group_ids = [g['group_id'] for g in groups]
            
            result.append({
                "id": p['id'],
                "user_id": p['user_id'],
                "username": p['username'],
                "full_name": p['full_name'],
                "phone": p['phone'],
                "course_name": p['course_name'],
                "created_at": p['created_at'],
                "group_ids": group_ids
            })
        
        return {"payments": result}

@router.post("/payment/approve")
async def approve_payment(
    data: ApprovePaymentRequest,
    admin: dict = Depends(require_admin)
):
    """Approve payment and assign to groups"""
    db = await get_db()
    
    SUBSCRIPTION_DAYS = int(os.getenv("SUBSCRIPTION_DAYS", "30"))
    
    if data.start_date:
        start_dt = datetime.fromisoformat(data.start_date)
    else:
        start_dt = datetime.utcnow()
    
    expires_at = int((start_dt + timedelta(days=SUBSCRIPTION_DAYS)).timestamp())
    
    async with db.acquire() as conn:
        payment = await conn.fetchrow(
            "SELECT user_id FROM payments WHERE id=$1", data.payment_id
        )
        
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        
        user_id = payment['user_id']
        
        await conn.execute(
            "UPDATE payments SET status='approved', admin_id=$1 WHERE id=$2",
            admin['user_id'], data.payment_id
        )
        
        if len(data.group_ids) == 1:
            await conn.execute("""
                UPDATE users SET group_id=$1, expires_at=$2 WHERE user_id=$3
            """, data.group_ids[0], expires_at, user_id)
        else:
            for group_id in data.group_ids:
                await conn.execute("""
                    INSERT INTO user_groups(user_id, group_id, expires_at)
                    VALUES($1, $2, $3)
                    ON CONFLICT(user_id, group_id) DO UPDATE SET expires_at=$3
                """, user_id, group_id, expires_at)
    
    return {
        "success": True,
        "message": "Payment approved",
        "user_id": user_id,
        "expires_at": expires_at
    }

@router.post("/payment/reject")
async def reject_payment(
    data: RejectPaymentRequest,
    admin: dict = Depends(require_admin)
):
    """Reject payment"""
    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE payments SET status='rejected', admin_id=$1 WHERE id=$2",
            admin['user_id'], data.payment_id
        )
    
    return {"success": True, "message": "Payment rejected"}

@router.get("/groups")
async def get_groups(admin: dict = Depends(require_admin)):
    """Get all configured groups"""
    GROUP_IDS = []
    _raw_groups = os.getenv("PRIVATE_GROUP_ID", "")
    if _raw_groups.strip():
        for x in _raw_groups.split(","):
            x = x.strip()
            if x.lstrip("-").isdigit():
                GROUP_IDS.append(int(x))
    
    return {"groups": [{"id": gid, "name": f"Group {gid}"} for gid in GROUP_IDS]}
