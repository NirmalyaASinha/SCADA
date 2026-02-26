"""
JWT Token Handler
"""
import os
import jwt
import uuid
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict

JWT_SECRET = os.getenv("JWT_SECRET", "scada-jwt-secret-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_HOURS = 24

# Hardcoded users with bcrypt hashed passwords
USERS_DB = {
    "admin": {
        "password_hash": bcrypt.hashpw(b"scada@2024", bcrypt.gensalt()).decode(),
        "role": "admin"
    },
    "operator1": {
        "password_hash": bcrypt.hashpw(b"ops@2024", bcrypt.gensalt()).decode(),
        "role": "operator"
    },
    "engineer1": {
        "password_hash": bcrypt.hashpw(b"eng@2024", bcrypt.gensalt()).decode(),
        "role": "engineer"
    },
    "viewer1": {
        "password_hash": bcrypt.hashpw(b"view@2024", bcrypt.gensalt()).decode(),
        "role": "viewer"
    }
}

class JWTHandler:
    @staticmethod
    def verify_password(username: str, password: str) -> Optional[str]:
        """Verify username and password, return role if valid"""
        if username not in USERS_DB:
            return None
        
        user = USERS_DB[username]
        if bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
            return user["role"]
        return None
    
    @staticmethod
    def create_access_token(username: str, role: str, session_id: str) -> str:
        """Create JWT access token"""
        payload = {
            "sub": username,
            "role": role,
            "session_id": session_id,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            "iat": datetime.now(timezone.utc),
            "type": "access"
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    @staticmethod
    def create_refresh_token(username: str, role: str, session_id: str) -> str:
        """Create JWT refresh token"""
        payload = {
            "sub": username,
            "role": role,
            "session_id": session_id,
            "exp": datetime.now(timezone.utc) + timedelta(hours=REFRESH_TOKEN_EXPIRE_HOURS),
            "iat": datetime.now(timezone.utc),
            "type": "refresh"
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    @staticmethod
    def verify_token(token: str) -> Optional[Dict]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    @staticmethod
    def generate_session_id() -> str:
        """Generate unique session ID"""
        return str(uuid.uuid4())
