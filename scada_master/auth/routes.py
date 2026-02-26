"""
Authentication Routes
"""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Dict

from .models import LoginRequest, LoginResponse, UserProfile, SessionInfo
from .jwt_handler import JWTHandler, ACCESS_TOKEN_EXPIRE_MINUTES

logger = logging.getLogger(__name__)
security = HTTPBearer()

router = APIRouter(prefix="/auth", tags=["authentication"])

# In-memory session store (in production, use Redis)
active_sessions = {}
token_blacklist = set()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """Dependency to get current authenticated user"""
    token = credentials.credentials
    
    if token in token_blacklist:
        raise HTTPException(status_code=401, detail="Token has been revoked")
    
    payload = JWTHandler.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    # Update last activity
    session_id = payload.get("session_id")
    if session_id in active_sessions:
        active_sessions[session_id]["last_activity"] = datetime.now(timezone.utc).isoformat()
    
    return payload

async def require_role(required_role: str, credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """Dependency to check if user has required role"""
    user = await get_current_user(credentials)
    
    role_hierarchy = {"viewer": 0, "operator": 1, "engineer": 2, "admin": 3}
    user_level = role_hierarchy.get(user["role"], 0)
    required_level = role_hierarchy.get(required_role, 99)
    
    if user_level < required_level:
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient permissions. Required: {required_role}, Have: {user['role']}"
        )
    
    return user

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, req: Request, audit_callback=None):
    """Authenticate user and return JWT tokens"""
    role = JWTHandler.verify_password(request.username, request.password)
    
    client_ip = req.client.host
    user_agent = req.headers.get("user-agent", "")
    
    if not role:
        # Log failed attempt
        if audit_callback:
            await audit_callback({
                "username": request.username,
                "ip_address": client_ip,
                "success": False,
                "failure_reason": "Invalid credentials",
                "user_agent": user_agent
            })
        
        logger.warning(f"Failed login attempt for user {request.username} from {client_ip}")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    # Generate session
    session_id = JWTHandler.generate_session_id()
    access_token = JWTHandler.create_access_token(request.username, role, session_id)
    refresh_token = JWTHandler.create_refresh_token(request.username, role, session_id)
    
    # Store session
    now = datetime.now(timezone.utc).isoformat()
    active_sessions[session_id] = {
        "session_id": session_id,
        "username": request.username,
        "role": role,
        "ip_address": client_ip,
        "login_time": now,
        "last_activity": now,
        "user_agent": user_agent
    }
    
    # Log successful login
    if audit_callback:
        await audit_callback({
            "username": request.username,
            "ip_address": client_ip,
            "success": True,
            "session_id": session_id,
            "user_agent": user_agent
        })
    
    logger.info(f"User {request.username} ({role}) logged in from {client_ip}")
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        role=role,
        username=request.username,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        last_login=now,
        session_id=session_id
    )

@router.post("/refresh")
async def refresh_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Refresh access token"""
    token = credentials.credentials
    payload = JWTHandler.verify_token(token)
    
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    session_id = payload.get("session_id")
    if session_id not in active_sessions:
        raise HTTPException(status_code=401, detail="Session expired")
    
    # Generate new access token
    new_access_token = JWTHandler.create_access_token(
        payload["sub"],
        payload["role"],
        session_id
    )
    
    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@router.post("/logout")
async def logout(user: Dict = Depends(get_current_user)):
    """Logout and invalidate session"""
    session_id = user.get("session_id")
    
    # Remove session
    if session_id in active_sessions:
        del active_sessions[session_id]
    
    # Note: In production, add token to Redis blacklist with TTL
    logger.info(f"User {user['sub']} logged out")
    
    return {"message": "Logged out successfully"}

@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(user: Dict = Depends(get_current_user)):
    """Get current user profile"""
    session_id = user.get("session_id")
    session = active_sessions.get(session_id, {})
    
    return UserProfile(
        username=user["sub"],
        role=user["role"],
        session_id=session_id,
        login_time=session.get("login_time", ""),
        last_activity=session.get("last_activity", "")
    )

@router.get("/sessions", response_model=List[SessionInfo])
async def get_all_sessions(user: Dict = Depends(get_current_user)):
    """Get all active sessions (admin only)"""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return [SessionInfo(**session) for session in active_sessions.values()]

@router.delete("/sessions/{session_id}")
async def force_logout_session(session_id: str, user: Dict = Depends(get_current_user)):
    """Force logout a session (admin only)"""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if session_id in active_sessions:
        username = active_sessions[session_id]["username"]
        del active_sessions[session_id]
        logger.info(f"Admin {user['sub']} force logged out user {username}")
        return {"message": f"Session {session_id} terminated"}
    
    raise HTTPException(status_code=404, detail="Session not found")

# Export for use in main app
__all__ = ["router", "get_current_user", "require_role", "active_sessions"]
