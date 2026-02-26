"""
Authentication and Authorization Manager

Provides:
- User authentication (password-based, token-based)
- Role-based access control (RBAC)
- Session management
- Permission checking
"""

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set


class Permission(Enum):
    """SCADA system permissions"""
    # Read permissions
    READ_STATUS = "read_status"
    READ_MEASUREMENTS = "read_measurements"
    READ_ALARMS = "read_alarms"
    READ_HISTORY = "read_history"
    
    # Write permissions
    WRITE_COMMAND = "write_command"
    WRITE_CONFIG = "write_config"
    
    # Control permissions
    CONTROL_BREAKER = "control_breaker"
    CONTROL_OLTC = "control_oltc"
    CONTROL_GENERATOR = "control_generator"
    
    # Admin permissions
    ADMIN_USER_MANAGEMENT = "admin_user_management"
    ADMIN_SYSTEM_CONFIG = "admin_system_config"
    ADMIN_SECURITY = "admin_security"


class Role(Enum):
    """Predefined user roles"""
    OPERATOR = "operator"
    ENGINEER = "engineer"
    SUPERVISOR = "supervisor"
    ADMINISTRATOR = "administrator"
    VIEWER = "viewer"


# Role to permissions mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.VIEWER: {
        Permission.READ_STATUS,
        Permission.READ_MEASUREMENTS,
        Permission.READ_ALARMS,
        Permission.READ_HISTORY,
    },
    Role.OPERATOR: {
        Permission.READ_STATUS,
        Permission.READ_MEASUREMENTS,
        Permission.READ_ALARMS,
        Permission.READ_HISTORY,
        Permission.WRITE_COMMAND,
        Permission.CONTROL_BREAKER,
    },
    Role.ENGINEER: {
        Permission.READ_STATUS,
        Permission.READ_MEASUREMENTS,
        Permission.READ_ALARMS,
        Permission.READ_HISTORY,
        Permission.WRITE_COMMAND,
        Permission.WRITE_CONFIG,
        Permission.CONTROL_BREAKER,
        Permission.CONTROL_OLTC,
        Permission.CONTROL_GENERATOR,
    },
    Role.SUPERVISOR: {
        Permission.READ_STATUS,
        Permission.READ_MEASUREMENTS,
        Permission.READ_ALARMS,
        Permission.READ_HISTORY,
        Permission.WRITE_COMMAND,
        Permission.WRITE_CONFIG,
        Permission.CONTROL_BREAKER,
        Permission.CONTROL_OLTC,
        Permission.CONTROL_GENERATOR,
        Permission.ADMIN_USER_MANAGEMENT,
    },
    Role.ADMINISTRATOR: set(Permission),  # All permissions
}


@dataclass
class User:
    """SCADA system user"""
    username: str
    password_hash: str
    role: Role
    full_name: str = ""
    email: str = ""
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if user has specific permission"""
        if not self.enabled:
            return False
        return permission in ROLE_PERMISSIONS.get(self.role, set())
    
    def get_permissions(self) -> Set[Permission]:
        """Get all permissions for user's role"""
        if not self.enabled:
            return set()
        return ROLE_PERMISSIONS.get(self.role, set())


@dataclass
class Session:
    """User session"""
    session_id: str
    username: str
    created_at: datetime
    last_activity: datetime
    source_ip: str
    expires_at: datetime
    
    def is_valid(self) -> bool:
        """Check if session is still valid"""
        return datetime.utcnow() < self.expires_at
    
    def refresh(self, timeout_minutes: int = 30):
        """Refresh session activity"""
        self.last_activity = datetime.utcnow()
        self.expires_at = self.last_activity + timedelta(minutes=timeout_minutes)


class AuthManager:
    """
    Authentication and authorization manager.
    
    Provides:
    - User authentication with password hashing
    - Session management with timeouts
    - Role-based access control
    - Brute force protection
    """
    
    def __init__(self, 
                 session_timeout_minutes: int = 30,
                 max_failed_attempts: int = 5,
                 lockout_duration_minutes: int = 15):
        """
        Initialize auth manager.
        
        Args:
            session_timeout_minutes: Session inactivity timeout
            max_failed_attempts: Max failed login attempts before lockout
            lockout_duration_minutes: Account lockout duration
        """
        self.session_timeout_minutes = session_timeout_minutes
        self.max_failed_attempts = max_failed_attempts
        self.lockout_duration_minutes = lockout_duration_minutes
        
        # User storage (in production, use database)
        self.users: Dict[str, User] = {}
        
        # Session storage
        self.sessions: Dict[str, Session] = {}
        
        # Lockout tracking
        self.lockouts: Dict[str, datetime] = {}
        
        # Statistics
        self.stats = {
            'total_logins': 0,
            'successful_logins': 0,
            'failed_logins': 0,
            'active_sessions': 0,
            'lockouts': 0,
        }
        
        # Create default admin user
        self._create_default_users()
    
    def _create_default_users(self):
        """Create default system users"""
        self.create_user(
            username="admin",
            password="admin123",  # Should be changed in production!
            role=Role.ADMINISTRATOR,
            full_name="System Administrator"
        )
        
        self.create_user(
            username="operator",
            password="operator123",
            role=Role.OPERATOR,
            full_name="System Operator"
        )
        
        self.create_user(
            username="viewer",
            password="viewer123",
            role=Role.VIEWER,
            full_name="Read-Only Viewer"
        )
    
    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash password with SHA-256"""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    @staticmethod
    def _generate_session_id() -> str:
        """Generate secure random session ID"""
        return secrets.token_urlsafe(32)
    
    def create_user(self,
                   username: str,
                   password: str,
                   role: Role,
                   full_name: str = "",
                   email: str = "") -> Optional[User]:
        """
        Create new user.
        
        Args:
            username: Unique username
            password: Plain text password (will be hashed)
            role: User role
            full_name: Full name
            email: Email address
            
        Returns:
            Created User or None if username exists
        """
        if username in self.users:
            return None
        
        user = User(
            username=username,
            password_hash=self._hash_password(password),
            role=role,
            full_name=full_name,
            email=email
        )
        
        self.users[username] = user
        return user
    
    def authenticate(self,
                    username: str,
                    password: str,
                    source_ip: str = "0.0.0.0") -> Optional[str]:
        """
        Authenticate user and create session.
        
        Args:
            username: Username
            password: Password
            source_ip: Source IP address
            
        Returns:
            Session ID if successful, None otherwise
        """
        self.stats['total_logins'] += 1
        
        # Check if user exists
        if username not in self.users:
            self.stats['failed_logins'] += 1
            return None
        
        user = self.users[username]
        
        # Check if account is locked
        if username in self.lockouts:
            lockout_until = self.lockouts[username]
            if datetime.utcnow() < lockout_until:
                self.stats['failed_logins'] += 1
                return None
            else:
                # Lockout expired
                del self.lockouts[username]
                user.failed_login_attempts = 0
        
        # Check if account is enabled
        if not user.enabled:
            self.stats['failed_logins'] += 1
            return None
        
        # Verify password
        password_hash = self._hash_password(password)
        if password_hash != user.password_hash:
            user.failed_login_attempts += 1
            
            # Check for brute force
            if user.failed_login_attempts >= self.max_failed_attempts:
                self.lockouts[username] = datetime.utcnow() + timedelta(
                    minutes=self.lockout_duration_minutes
                )
                self.stats['lockouts'] += 1
            
            self.stats['failed_logins'] += 1
            return None
        
        # Success! Reset failed attempts
        user.failed_login_attempts = 0
        user.last_login = datetime.utcnow()
        
        # Create session
        session_id = self._generate_session_id()
        session = Session(
            session_id=session_id,
            username=username,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            source_ip=source_ip,
            expires_at=datetime.utcnow() + timedelta(minutes=self.session_timeout_minutes)
        )
        
        self.sessions[session_id] = session
        self.stats['successful_logins'] += 1
        self.stats['active_sessions'] = len(self.sessions)
        
        return session_id
    
    def validate_session(self, session_id: str) -> Optional[User]:
        """
        Validate session and return user.
        
        Args:
            session_id: Session ID to validate
            
        Returns:
            User if session valid, None otherwise
        """
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        
        # Check if expired
        if not session.is_valid():
            del self.sessions[session_id]
            self.stats['active_sessions'] = len(self.sessions)
            return None
        
        # Refresh session
        session.refresh(self.session_timeout_minutes)
        
        # Return user
        return self.users.get(session.username)
    
    def logout(self, session_id: str) -> bool:
        """
        Logout user and destroy session.
        
        Args:
            session_id: Session ID to destroy
            
        Returns:
            True if session existed and was destroyed
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            self.stats['active_sessions'] = len(self.sessions)
            return True
        return False
    
    def check_permission(self,
                        session_id: str,
                        permission: Permission) -> bool:
        """
        Check if session has permission.
        
        Args:
            session_id: Session ID
            permission: Required permission
            
        Returns:
            True if authorized
        """
        user = self.validate_session(session_id)
        if not user:
            return False
        
        return user.has_permission(permission)
    
    def get_user_by_session(self, session_id: str) -> Optional[User]:
        """Get user for session"""
        return self.validate_session(session_id)
    
    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """Get session information"""
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        user = self.users.get(session.username)
        
        if not user:
            return None
        
        return {
            'session_id': session.session_id,
            'username': user.username,
            'role': user.role.value,
            'full_name': user.full_name,
            'created_at': session.created_at.isoformat(),
            'last_activity': session.last_activity.isoformat(),
            'expires_at': session.expires_at.isoformat(),
            'source_ip': session.source_ip,
        }
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions"""
        expired = [
            sid for sid, session in self.sessions.items()
            if not session.is_valid()
        ]
        
        for sid in expired:
            del self.sessions[sid]
        
        self.stats['active_sessions'] = len(self.sessions)
        return len(expired)
    
    def get_statistics(self) -> Dict:
        """Get authentication statistics"""
        return {
            **self.stats,
            'total_users': len(self.users),
            'enabled_users': sum(1 for u in self.users.values() if u.enabled),
            'locked_accounts': len(self.lockouts),
        }
