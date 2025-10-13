import os
import hmac
import hashlib
from urllib.parse import parse_qsl
from fastapi import HTTPException, Header
from typing import Dict, Optional

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not found")

def verify_telegram_init_data(init_data: str) -> Dict:
    """
    Verify Telegram Mini App initData signature
    Returns user data if valid, raises HTTPException if invalid
    """
    try:
        parsed_data = dict(parse_qsl(init_data))
        
        if 'hash' not in parsed_data:
            raise HTTPException(status_code=401, detail="Invalid initData: missing hash")
        
        received_hash = parsed_data.pop('hash')
        
        data_check_arr = [f"{k}={v}" for k, v in sorted(parsed_data.items())]
        data_check_string = '\n'.join(data_check_arr)
        
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=BOT_TOKEN.encode(),
            digestmod=hashlib.sha256
        ).digest()
        
        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(calculated_hash, received_hash):
            raise HTTPException(status_code=401, detail="Invalid initData signature")
        
        import json
        user_data = json.loads(parsed_data.get('user', '{}'))
        
        return {
            'user_id': user_data.get('id'),
            'username': user_data.get('username'),
            'first_name': user_data.get('first_name'),
            'last_name': user_data.get('last_name'),
            'language_code': user_data.get('language_code')
        }
    
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

async def get_current_user(authorization: Optional[str] = Header(None)) -> Dict:
    """
    FastAPI dependency to get current user from Telegram initData
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    if not authorization.startswith("tma "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    init_data = authorization[4:]
    return verify_telegram_init_data(init_data)
