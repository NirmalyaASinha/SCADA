"""
Authentication Models
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    username: str
    expires_in: int
    last_login: str
    session_id: str

class RefreshRequest(BaseModel):
    refresh_token: str

class UserProfile(BaseModel):
    username: str
    role: str
    session_id: str
    login_time: str
    last_activity: str

class SessionInfo(BaseModel):
    session_id: str
    username: str
    role: str
    ip_address: str
    login_time: str
    last_activity: str
    user_agent: Optional[str] = None
