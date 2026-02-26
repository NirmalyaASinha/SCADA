"""
Security Module - Authentication, Authorization, and Audit Logging

Provides security controls for SCADA system operations including:
- Audit logging for all operations
- User authentication and session management
- Role-based access control (RBAC)
- Security event monitoring
"""

from .audit_logger import AuditLogger, AuditEvent, EventType, Severity
from .auth import AuthManager, User, Role, Permission
from .security_config import SecurityConfig

__all__ = [
    'AuditLogger',
    'AuditEvent',
    'EventType',
    'Severity',
    'AuthManager',
    'User',
    'Role',
    'Permission',
    'SecurityConfig',
]
