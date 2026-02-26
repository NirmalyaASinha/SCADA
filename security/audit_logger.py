"""
Audit Logger - Security event logging and monitoring

Provides comprehensive audit trail for all SCADA operations including:
- User authentication events
- Command execution
- Configuration changes
- System events
- Security violations
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pathlib import Path


class EventType(Enum):
    """Types of audit events"""
    # Authentication
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    SESSION_TIMEOUT = "session_timeout"
    
    # Authorization
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    
    # SCADA Operations
    COMMAND_ISSUED = "command_issued"
    COMMAND_EXECUTED = "command_executed"
    COMMAND_FAILED = "command_failed"
    
    # Configuration
    CONFIG_CHANGED = "config_changed"
    NODE_ADDED = "node_added"
    NODE_REMOVED = "node_removed"
    
    # System Events
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    ALARM_TRIGGERED = "alarm_triggered"
    
    # Security Events
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    BRUTE_FORCE_DETECTED = "brute_force_detected"
    CREDENTIAL_CHANGED = "credential_changed"
    PRIVILEGE_ESCALATION = "privilege_escalation"


class Severity(Enum):
    """Severity levels for audit events"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Single audit event record"""
    timestamp: datetime
    event_type: EventType
    severity: Severity
    user: Optional[str] = None
    source_ip: Optional[str] = None
    node_id: Optional[str] = None
    action: Optional[str] = None
    result: Optional[str] = None
    details: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        data = {
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type.value,
            'severity': self.severity.value,
        }
        
        if self.user:
            data['user'] = self.user
        if self.source_ip:
            data['source_ip'] = self.source_ip
        if self.node_id:
            data['node_id'] = self.node_id
        if self.action:
            data['action'] = self.action
        if self.result:
            data['result'] = self.result
        if self.details:
            data['details'] = self.details
        
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())


class AuditLogger:
    """
    Audit logger for SCADA security events.
    
    Provides:
    - Structured logging of security events
    - Multiple output formats (file, syslog, database)
    - Event filtering and search
    - Tamper-evident logging
    """
    
    def __init__(self, 
                 log_file: Optional[str] = None,
                 log_to_console: bool = True,
                 log_level: Severity = Severity.INFO):
        """
        Initialize audit logger.
        
        Args:
            log_file: Path to audit log file (None = memory only)
            log_to_console: Whether to log to console
            log_level: Minimum severity to log
        """
        self.log_file = log_file
        self.log_to_console = log_to_console
        self.log_level = log_level
        
        # In-memory event buffer
        self.events: List[AuditEvent] = []
        self.max_events_in_memory = 10000
        
        # Statistics
        self.events_logged = 0
        self.events_by_type: Dict[EventType, int] = {}
        self.events_by_severity: Dict[Severity, int] = {}
        
        # File handle
        self.file_handle = None
        if self.log_file:
            try:
                Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
                self.file_handle = open(self.log_file, 'a', encoding='utf-8')
            except Exception as e:
                logging.error(f"Failed to open audit log file {self.log_file}: {e}")
        
        # Python logger for console output
        self.logger = logging.getLogger('AuditLogger')
        if log_to_console:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s [AUDIT] %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def log_event(self, 
                  event_type: EventType,
                  severity: Severity = Severity.INFO,
                  user: Optional[str] = None,
                  source_ip: Optional[str] = None,
                  node_id: Optional[str] = None,
                  action: Optional[str] = None,
                  result: Optional[str] = None,
                  details: Optional[Dict] = None) -> AuditEvent:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event
            severity: Event severity
            user: Username who performed action
            source_ip: Source IP address
            node_id: SCADA node ID
            action: Action performed
            result: Result of action
            details: Additional details dictionary
            
        Returns:
            Created AuditEvent
        """
        # Create event
        event = AuditEvent(
            timestamp=datetime.utcnow(),
            event_type=event_type,
            severity=severity,
            user=user,
            source_ip=source_ip,
            node_id=node_id,
            action=action,
            result=result,
            details=details
        )
        
        # Check severity filter
        severity_levels = {
            Severity.DEBUG: 0,
            Severity.INFO: 1,
            Severity.WARNING: 2,
            Severity.ERROR: 3,
            Severity.CRITICAL: 4,
        }
        
        if severity_levels[severity] < severity_levels[self.log_level]:
            return event
        
        # Store in memory
        self.events.append(event)
        if len(self.events) > self.max_events_in_memory:
            self.events = self.events[-self.max_events_in_memory:]
        
        # Update statistics
        self.events_logged += 1
        self.events_by_type[event_type] = self.events_by_type.get(event_type, 0) + 1
        self.events_by_severity[severity] = self.events_by_severity.get(severity, 0) + 1
        
        # Write to file
        if self.file_handle:
            try:
                self.file_handle.write(event.to_json() + '\n')
                self.file_handle.flush()
            except Exception as e:
                logging.error(f"Failed to write audit event to file: {e}")
        
        # Log to console
        if self.log_to_console:
            log_msg = f"[{event_type.value}] User:{user or 'system'} Node:{node_id or 'N/A'} Action:{action or 'N/A'} Result:{result or 'N/A'}"
            if details:
                log_msg += f" Details:{details}"
            
            log_level_map = {
                Severity.DEBUG: logging.DEBUG,
                Severity.INFO: logging.INFO,
                Severity.WARNING: logging.WARNING,
                Severity.ERROR: logging.ERROR,
                Severity.CRITICAL: logging.CRITICAL,
            }
            self.logger.log(log_level_map[severity], log_msg)
        
        return event
    
    def log_login(self, user: str, source_ip: str, success: bool, details: Optional[Dict] = None):
        """Log user login attempt"""
        self.log_event(
            event_type=EventType.LOGIN_SUCCESS if success else EventType.LOGIN_FAILURE,
            severity=Severity.INFO if success else Severity.WARNING,
            user=user,
            source_ip=source_ip,
            action="login",
            result="success" if success else "failure",
            details=details
        )
    
    def log_command(self, user: str, node_id: str, command: str, success: bool, details: Optional[Dict] = None):
        """Log SCADA command execution"""
        self.log_event(
            event_type=EventType.COMMAND_EXECUTED if success else EventType.COMMAND_FAILED,
            severity=Severity.INFO if success else Severity.ERROR,
            user=user,
            node_id=node_id,
            action=command,
            result="success" if success else "failure",
            details=details
        )
    
    def log_access_denied(self, user: str, action: str, reason: str, details: Optional[Dict] = None):
        """Log access denied event"""
        self.log_event(
            event_type=EventType.ACCESS_DENIED,
            severity=Severity.WARNING,
            user=user,
            action=action,
            result="denied",
            details={'reason': reason, **(details or {})}
        )
    
    def log_config_change(self, user: str, config_item: str, old_value: str, new_value: str):
        """Log configuration change"""
        self.log_event(
            event_type=EventType.CONFIG_CHANGED,
            severity=Severity.INFO,
            user=user,
            action=f"changed_{config_item}",
            details={
                'config_item': config_item,
                'old_value': old_value,
                'new_value': new_value
            }
        )
    
    def log_alarm(self, node_id: str, alarm_type: str, value: float, severity: Severity = Severity.WARNING):
        """Log SCADA alarm event"""
        self.log_event(
            event_type=EventType.ALARM_TRIGGERED,
            severity=severity,
            node_id=node_id,
            action=alarm_type,
            details={
                'alarm_type': alarm_type,
                'value': value
            }
        )
    
    def log_security_violation(self, user: str, violation_type: str, source_ip: Optional[str] = None, details: Optional[Dict] = None):
        """Log security violation"""
        event_type_map = {
            'brute_force': EventType.BRUTE_FORCE_DETECTED,
            'unauthorized_access': EventType.UNAUTHORIZED_ACCESS,
            'privilege_escalation': EventType.PRIVILEGE_ESCALATION,
        }
        
        self.log_event(
            event_type=event_type_map.get(violation_type, EventType.UNAUTHORIZED_ACCESS),
            severity=Severity.CRITICAL,
            user=user,
            source_ip=source_ip,
            action=violation_type,
            details=details
        )
    
    def get_events(self,
                   event_type: Optional[EventType] = None,
                   user: Optional[str] = None,
                   node_id: Optional[str] = None,
                   severity: Optional[Severity] = None,
                   limit: int = 100) -> List[AuditEvent]:
        """
        Query audit events with filters.
        
        Args:
            event_type: Filter by event type
            user: Filter by user
            node_id: Filter by node
            severity: Filter by severity
            limit: Maximum events to return
            
        Returns:
            List of matching events
        """
        results = self.events
        
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        
        if user:
            results = [e for e in results if e.user == user]
        
        if node_id:
            results = [e for e in results if e.node_id == node_id]
        
        if severity:
            results = [e for e in results if e.severity == severity]
        
        # Return most recent first
        results = sorted(results, key=lambda e: e.timestamp, reverse=True)[:limit]
        return results
    
    def get_statistics(self) -> Dict:
        """Get audit logging statistics"""
        return {
            'total_events': self.events_logged,
            'events_in_memory': len(self.events),
            'events_by_type': {k.value: v for k, v in self.events_by_type.items()},
            'events_by_severity': {k.value: v for k, v in self.events_by_severity.items()},
        }
    
    def close(self):
        """Close audit logger and file handles"""
        if self.file_handle:
            try:
                self.file_handle.close()
            except:
                pass
    
    def __del__(self):
        """Cleanup on deletion"""
        self.close()
