"""
Select-Before-Operate (SBO) Control System
"""
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from enum import Enum
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class SBOAction(str, Enum):
    OPEN = "open"
    CLOSE = "close"

class SBOState(str, Enum):
    SELECTED = "SELECTED"
    OPERATED = "OPERATED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"

class SBOSelectRequest(BaseModel):
    node_id: str
    breaker_id: int
    action: SBOAction
    reason: str
    operator_id: str

class SBOOperateRequest(BaseModel):
    session_id: str

class SBOCancelRequest(BaseModel):
    session_id: str

class SBOSession:
    def __init__(self, session_id: str, node_id: str, breaker_id: int, 
                 action: SBOAction, operator_id: str, reason: str):
        self.session_id = session_id
        self.node_id = node_id
        self.breaker_id = breaker_id
        self.action = action
        self.operator_id = operator_id
        self.reason = reason
        self.selected_at = datetime.utcnow()
        self.expires_at = self.selected_at + timedelta(seconds=10)
        self.state = SBOState.SELECTED
        self.operated_at: Optional[datetime] = None
        self.result: Optional[str] = None
        self.response_time_ms: Optional[int] = None
    
    def is_expired(self) -> bool:
        """Check if SBO session has expired"""
        return datetime.utcnow() > self.expires_at
    
    def time_remaining(self) -> float:
        """Get seconds remaining before expiration"""
        if self.is_expired():
            return 0.0
        return (self.expires_at - datetime.utcnow()).total_seconds()
    
    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "node_id": self.node_id,
            "breaker_id": self.breaker_id,
            "action": self.action.value,
            "operator_id": self.operator_id,
            "reason": self.reason,
            "selected_at": self.selected_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "state": self.state.value,
            "operated_at": self.operated_at.isoformat() if self.operated_at else None,
            "result": self.result,
            "response_time_ms": self.response_time_ms,
            "time_remaining_s": round(self.time_remaining(), 2)
        }

class SBOManager:
    def __init__(self):
        self.sessions: Dict[str, SBOSession] = {}
        self.audit_callback = None
    
    def set_audit_callback(self, callback):
        """Set callback for audit logging"""
        self.audit_callback = callback
    
    def create_session(self, node_id: str, breaker_id: int, action: SBOAction, 
                      operator_id: str, reason: str) -> SBOSession:
        """Create new SBO SELECT session"""
        session_id = str(uuid.uuid4())
        session = SBOSession(session_id, node_id, breaker_id, action, operator_id, reason)
        self.sessions[session_id] = session
        
        logger.info(f"SBO SELECT created: {session_id} - {operator_id} -> {node_id} breaker {breaker_id} {action.value}")
        
        return session
    
    def get_session(self, session_id: str) -> Optional[SBOSession]:
        """Get SBO session"""
        session = self.sessions.get(session_id)
        
        # Auto-expire if needed
        if session and session.is_expired() and session.state == SBOState.SELECTED:
            session.state = SBOState.EXPIRED
            logger.warning(f"SBO session {session_id} expired")
        
        return session
    
    def operate_session(self, session_id: str, result: str, response_time_ms: int) -> Optional[SBOSession]:
        """Execute OPERATE on selected session"""
        session = self.get_session(session_id)
        
        if not session:
            logger.error(f"SBO session {session_id} not found")
            return None
        
        if session.state != SBOState.SELECTED:
            logger.error(f"SBO session {session_id} not in SELECTED state: {session.state}")
            return None
        
        if session.is_expired():
            session.state = SBOState.EXPIRED
            logger.error(f"SBO session {session_id} expired before operate")
            return None
        
        # Execute operate
        session.operated_at = datetime.utcnow()
        session.state = SBOState.OPERATED
        session.result = result
        session.response_time_ms = response_time_ms
        
        logger.info(f"SBO OPERATE executed: {session_id} - result: {result} ({response_time_ms}ms)")
        
        # Audit log
        if self.audit_callback:
            self.audit_callback({
                "action": "breaker_operate",
                "session_id": session_id,
                "node_id": session.node_id,
                "breaker_id": session.breaker_id,
                "command": session.action.value,
                "operator_id": session.operator_id,
                "reason": session.reason,
                "result": result,
                "response_time_ms": response_time_ms
            })
        
        return session
    
    def cancel_session(self, session_id: str) -> bool:
        """Cancel SBO session"""
        session = self.get_session(session_id)
        
        if not session:
            return False
        
        if session.state == SBOState.SELECTED:
            session.state = SBOState.CANCELLED
            logger.info(f"SBO session {session_id} cancelled")
            return True
        
        return False
    
    def cleanup_expired_sessions(self):
        """Remove old sessions from memory"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=5)
        expired_sessions = [
            sid for sid, session in self.sessions.items()
            if session.selected_at < cutoff_time
        ]
        
        for sid in expired_sessions:
            del self.sessions[sid]
        
        if expired_sessions:
            logger.debug(f"Cleaned up {len(expired_sessions)} expired SBO sessions")
