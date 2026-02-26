"""
Security Configuration

Centralized security settings for SCADA system.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class SecurityConfig:
    """Security configuration settings"""
    
    # Authentication
    session_timeout_minutes: int = 30
    max_failed_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    password_min_length: int = 8
    require_password_complexity: bool = True
    
    # Audit Logging
    audit_log_enabled: bool = True
    audit_log_file: str = "logs/audit.log"
    log_to_console: bool = True
    log_successful_logins: bool = True
    log_failed_logins: bool = True
    log_all_commands: bool = True
    
    # Network Security
    allowed_ip_ranges: List[str] = None
    enable_rate_limiting: bool = True
    max_requests_per_minute: int = 60
    
    # Command Security
    require_command_confirmation: bool = True
    critical_commands_require_dual_auth: bool = False
    command_timeout_seconds: int = 300
    
    # System
    enable_security_hardening: bool = True
    enforce_https: bool = False
    session_encryption: bool = True
    
    def __post_init__(self):
        """Initialize defaults"""
        if self.allowed_ip_ranges is None:
            self.allowed_ip_ranges = ["127.0.0.1", "192.168.0.0/16", "10.0.0.0/8"]
    
    @classmethod
    def default(cls) -> 'SecurityConfig':
        """Create default security configuration"""
        return cls()
    
    @classmethod
    def strict(cls) -> 'SecurityConfig':
        """Create strict security configuration"""
        return cls(
            session_timeout_minutes=15,
            max_failed_login_attempts=3,
            lockout_duration_minutes=30,
            password_min_length=12,
            require_password_complexity=True,
            require_command_confirmation=True,
            critical_commands_require_dual_auth=True,
            enable_security_hardening=True,
            enforce_https=True,
            session_encryption=True,
        )
    
    @classmethod
    def development(cls) -> 'SecurityConfig':
        """Create relaxed configuration for development"""
        return cls(
            session_timeout_minutes=120,
            max_failed_login_attempts=10,
            lockout_duration_minutes=5,
            password_min_length=4,
            require_password_complexity=False,
            require_command_confirmation=False,
            critical_commands_require_dual_auth=False,
            enable_security_hardening=False,
            enforce_https=False,
        )
