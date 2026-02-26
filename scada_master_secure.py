"""
Secure SCADA Master - Integrated Security and Audit Logging

Extends SCADA Master with:
- User authentication and authorization
- Comprehensive audit logging
- Command authorization checks
- Security event monitoring
"""

import logging
from datetime import datetime
from typing import Dict, Optional

from scada_master import SCADAMaster
from security import (
    AuditLogger, EventType, Severity,
    AuthManager, Permission,
    SecurityConfig
)

logger = logging.getLogger(__name__)


class SecureSCADAMaster(SCADAMaster):
    """
    SCADA Master with integrated security and audit logging.
    
    Features:
    - All operations require authenticated session
    - Commands checked against user permissions
    - All actions logged to audit trail
    - Security events monitored
    """
    
    def __init__(self, security_config: Optional[SecurityConfig] = None):
        """
        Initialize secure SCADA Master.
        
        Args:
            security_config: Security configuration (uses default if None)
        """
        super().__init__()
        
        # Security configuration
        self.security_config = security_config or SecurityConfig.default()
        
        # Initialize auth manager
        self.auth_manager = AuthManager(
            session_timeout_minutes=self.security_config.session_timeout_minutes,
            max_failed_attempts=self.security_config.max_failed_login_attempts,
            lockout_duration_minutes=self.security_config.lockout_duration_minutes
        )
        
        # Initialize audit logger
        self.audit_logger = AuditLogger(
            log_file=self.security_config.audit_log_file if self.security_config.audit_log_enabled else None,
            log_to_console=self.security_config.log_to_console
        )
        
        # Log system start
        self.audit_logger.log_event(
            event_type=EventType.SYSTEM_START,
            severity=Severity.INFO,
            user="system",
            action="scada_master_start"
        )
    
    async def start(self):
        """Start secure SCADA master"""
        self.audit_logger.log_event(
            event_type=EventType.SYSTEM_START,
            severity=Severity.INFO,
            user="system",
            action="polling_start",
            details={'nodes': len(self.nodes)}
        )
        await super().start()
    
    async def stop(self):
        """Stop secure SCADA master"""
        self.audit_logger.log_event(
            event_type=EventType.SYSTEM_STOP,
            severity=Severity.INFO,
            user="system",
            action="scada_master_stop"
        )
        await super().stop()
        self.audit_logger.close()
    
    def login(self, username: str, password: str, source_ip: str = "127.0.0.1") -> Optional[str]:
        """
        Authenticate user and create session.
        
        Args:
            username: Username
            password: Password
            source_ip: Source IP address
            
        Returns:
            Session ID if successful, None otherwise
        """
        session_id = self.auth_manager.authenticate(username, password, source_ip)
        
        # Log login attempt
        self.audit_logger.log_login(
            user=username,
            source_ip=source_ip,
            success=(session_id is not None),
            details={'timestamp': datetime.utcnow().isoformat()}
        )
        
        return session_id
    
    def logout(self, session_id: str) -> bool:
        """
        Logout user and destroy session.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if successful
        """
        # Get user before logout
        user = self.auth_manager.get_user_by_session(session_id)
        username = user.username if user else "unknown"
        
        # Logout
        success = self.auth_manager.logout(session_id)
        
        # Log logout
        if success:
            self.audit_logger.log_event(
                event_type=EventType.LOGOUT,
                severity=Severity.INFO,
                user=username,
                action="logout"
            )
        
        return success
    
    def add_node_secure(self,
                       session_id: str,
                       node_id: str,
                       ip: str,
                       modbus_port: int = 502,
                       iec104_port: int = 2414) -> bool:
        """
        Add node with authorization check.
        
        Args:
            session_id: Authenticated session
            node_id: Node identifier
            ip: IP address
            modbus_port: Modbus TCP port
            iec104_port: IEC 104 port
            
        Returns:
            True if successful
        """
        # Check authentication
        user = self.auth_manager.validate_session(session_id)
        if not user:
            self.audit_logger.log_access_denied(
                user="unknown",
                action="add_node",
                reason="invalid_session"
            )
            return False
        
        # Check authorization
        if not user.has_permission(Permission.WRITE_CONFIG):
            self.audit_logger.log_access_denied(
                user=user.username,
                action="add_node",
                reason="insufficient_permissions"
            )
            return False
        
        # Add node
        try:
            self.add_node(node_id, ip, modbus_port, iec104_port)
            
            # Log successful addition
            self.audit_logger.log_event(
                event_type=EventType.NODE_ADDED,
                severity=Severity.INFO,
                user=user.username,
                node_id=node_id,
                action="add_node",
                result="success",
                details={'ip': ip, 'modbus_port': modbus_port, 'iec104_port': iec104_port}
            )
            
            return True
            
        except Exception as e:
            self.audit_logger.log_event(
                event_type=EventType.NODE_ADDED,
                severity=Severity.ERROR,
                user=user.username,
                node_id=node_id,
                action="add_node",
                result="failure",
                details={'error': str(e)}
            )
            return False
    
    async def send_command_secure(self,
                                  session_id: str,
                                  node_id: str,
                                  action: str,
                                  value: Optional[int] = None) -> bool:
        """
        Send command with authorization check.
        
        Args:
            session_id: Authenticated session
            node_id: Target node
            action: Command action
            value: Optional value
            
        Returns:
            True if successful
        """
        # Check authentication
        user = self.auth_manager.validate_session(session_id)
        if not user:
            self.audit_logger.log_access_denied(
                user="unknown",
                action=f"command_{action}",
                reason="invalid_session"
            )
            return False
        
        # Check authorization based on command type
        required_permission = None
        if 'breaker' in action.lower():
            required_permission = Permission.CONTROL_BREAKER
        elif 'oltc' in action.lower():
            required_permission = Permission.CONTROL_OLTC
        elif 'generator' in action.lower() or 'gen' in action.lower():
            required_permission = Permission.CONTROL_GENERATOR
        else:
            required_permission = Permission.WRITE_COMMAND
        
        if not user.has_permission(required_permission):
            self.audit_logger.log_access_denied(
                user=user.username,
                action=f"command_{action}",
                reason=f"requires_{required_permission.value}"
            )
            return False
        
        # Log command issuance
        self.audit_logger.log_event(
            event_type=EventType.COMMAND_ISSUED,
            severity=Severity.INFO,
            user=user.username,
            node_id=node_id,
            action=action,
            details={'value': value}
        )
        
        # Execute command
        try:
            await self.send_command(node_id, action, value)
            
            # Log successful execution
            self.audit_logger.log_command(
                user=user.username,
                node_id=node_id,
                command=action,
                success=True,
                details={'value': value}
            )
            
            return True
            
        except Exception as e:
            # Log failed execution
            self.audit_logger.log_command(
                user=user.username,
                node_id=node_id,
                command=action,
                success=False,
                details={'error': str(e)}
            )
            return False
    
    def get_node_status_secure(self, session_id: str, node_id: Optional[str] = None) -> Optional[Dict]:
        """
        Get node status with authorization check.
        
        Args:
            session_id: Authenticated session
            node_id: Node to query (None = all nodes)
            
        Returns:
            Node status dictionary or None if unauthorized
        """
        # Check authentication
        user = self.auth_manager.validate_session(session_id)
        if not user:
            return None
        
        # Check authorization
        if not user.has_permission(Permission.READ_STATUS):
            self.audit_logger.log_access_denied(
                user=user.username,
                action="read_status",
                reason="insufficient_permissions"
            )
            return None
        
        # Get status
        if node_id:
            if node_id not in self.nodes:
                return None
            conn = self.nodes[node_id]
            return {
                'node_id': node_id,
                'voltage_kv': conn.voltage_kv,
                'current_a': conn.current_a,
                'power_mw': conn.power_mw,
                'frequency_hz': conn.frequency_hz,
                'breaker_closed': conn.breaker_closed,
                'is_healthy': conn.is_healthy,
            }
        else:
            # All nodes
            return {
                nid: {
                    'voltage_kv': conn.voltage_kv,
                    'current_a': conn.current_a,
                    'power_mw': conn.power_mw,
                    'frequency_hz': conn.frequency_hz,
                    'breaker_closed': conn.breaker_closed,
                    'is_healthy': conn.is_healthy,
                }
                for nid, conn in self.nodes.items()
            }
    
    def _check_alarms(self, conn):
        """Check alarms and log to audit trail"""
        # Call parent alarm checking
        super()._check_alarms(conn)
        
        # Additional audit logging for alarms
        if conn.voltage_kv and (conn.voltage_kv < 200 or conn.voltage_kv > 250):
            self.audit_logger.log_alarm(
                node_id=conn.node_id,
                alarm_type='voltage',
                value=conn.voltage_kv,
                severity=Severity.WARNING if 190 < conn.voltage_kv < 260 else Severity.CRITICAL
            )
        
        if conn.frequency_hz and (conn.frequency_hz < 49.5 or conn.frequency_hz > 50.5):
            self.audit_logger.log_alarm(
                node_id=conn.node_id,
                alarm_type='frequency',
                value=conn.frequency_hz,
                severity=Severity.WARNING if 49 < conn.frequency_hz < 51 else Severity.CRITICAL
            )
    
    async def get_alarms(self) -> list:
        """
        Get current active alarms.
        
        Returns:
            List of alarm dictionaries with timestamp, node_id, message, severity
        """
        return self.alarms if hasattr(self, 'alarms') else []
    
    def get_audit_events(self,
                        session_id: str,
                        event_type: Optional[EventType] = None,
                        user: Optional[str] = None,
                        limit: int = 100) -> Optional[list]:
        """
        Get audit events (requires admin permission).
        
        Args:
            session_id: Authenticated session
            event_type: Filter by event type
            user: Filter by user
            limit: Maximum events
            
        Returns:
            List of audit events or None if unauthorized
        """
        # Check authentication
        auth_user = self.auth_manager.validate_session(session_id)
        if not auth_user:
            return None
        
        # Check authorization (only admins can view audit logs)
        if not auth_user.has_permission(Permission.ADMIN_SECURITY):
            self.audit_logger.log_access_denied(
                user=auth_user.username,
                action="view_audit_logs",
                reason="requires_admin"
            )
            return None
        
        # Get events
        events = self.audit_logger.get_events(
            event_type=event_type,
            user=user,
            limit=limit
        )
        
        return [e.to_dict() for e in events]
    
    def get_security_statistics(self, session_id: str) -> Optional[Dict]:
        """
        Get security statistics (requires admin permission).
        
        Args:
            session_id: Authenticated session
            
        Returns:
            Statistics dictionary or None if unauthorized
        """
        # Check authentication
        user = self.auth_manager.validate_session(session_id)
        if not user:
            return None
        
        # Check authorization
        if not user.has_permission(Permission.ADMIN_SECURITY):
            return None
        
        return {
            'auth_stats': self.auth_manager.get_statistics(),
            'audit_stats': self.audit_logger.get_statistics(),
        }
