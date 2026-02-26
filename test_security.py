"""
Test Suite for Security Module

Tests authentication, authorization, and audit logging.
"""

import asyncio
import sys
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, '/home/nirmalya/Desktop/SCADA_SIM')

from security import (
    AuditLogger, EventType, Severity,
    AuthManager, User, Role, Permission,
    SecurityConfig
)


def test_audit_logger_init():
    """Test 1: Audit logger initialization"""
    print("Test 1: Audit logger initialization...", end=" ")
    
    logger = AuditLogger(log_to_console=False)
    
    assert logger.events_logged == 0, "Should start with 0 events"
    assert len(logger.events) == 0, "Should have empty event list"
    
    print("✓ PASSED")


def test_audit_log_event():
    """Test 2: Log audit event"""
    print("Test 2: Log audit event...", end=" ")
    
    logger = AuditLogger(log_to_console=False)
    
    event = logger.log_event(
        event_type=EventType.LOGIN_SUCCESS,
        severity=Severity.INFO,
        user="testuser",
        source_ip="192.168.1.100",
        action="login",
        result="success"
    )
    
    assert event is not None, "Should create event"
    assert logger.events_logged == 1, "Should log 1 event"
    assert len(logger.events) == 1, "Should have 1 event in memory"
    assert event.user == "testuser", "Should set user"
    assert event.event_type == EventType.LOGIN_SUCCESS, "Should set event type"
    
    print("✓ PASSED")


def test_audit_log_helpers():
    """Test 3: Audit log helper methods"""
    print("Test 3: Audit log helper methods...", end=" ")
    
    logger = AuditLogger(log_to_console=False)
    
    # Log login
    logger.log_login("user1", "192.168.1.1", success=True)
    logger.log_login("user2", "192.168.1.2", success=False)
    
    # Log command
    logger.log_command("user1", "GEN-001", "close_breaker", success=True)
    
    # Log access denied
    logger.log_access_denied("user2", "write_config", "insufficient_permissions")
    
    assert logger.events_logged == 4, "Should log 4 events"
    
    print("✓ PASSED")


def test_audit_query_events():
    """Test 4: Query audit events"""
    print("Test 4: Query audit events...", end=" ")
    
    logger = AuditLogger(log_to_console=False)
    
    # Log multiple events
    logger.log_login("user1", "192.168.1.1", success=True)
    logger.log_login("user2", "192.168.1.2", success=False)
    logger.log_command("user1", "GEN-001", "close_breaker", success=True)
    logger.log_command("user1", "SUB-001", "raise_oltc", success=True)
    
    # Query all events
    all_events = logger.get_events()
    assert len(all_events) == 4, "Should get all 4 events"
    
    # Query by user
    user1_events = logger.get_events(user="user1")
    assert len(user1_events) == 3, "Should get 3 events for user1"
    
    # Query by event type
    login_events = logger.get_events(event_type=EventType.LOGIN_SUCCESS)
    assert len(login_events) == 1, "Should get 1 login success"
    
    print("✓ PASSED")


def test_audit_statistics():
    """Test 5: Audit statistics"""
    print("Test 5: Audit statistics...", end=" ")
    
    logger = AuditLogger(log_to_console=False)
    
    logger.log_login("user1", "192.168.1.1", success=True)
    logger.log_command("user1", "GEN-001", "close_breaker", success=True)
    logger.log_alarm("GEN-001", "overvoltage", 255.0, Severity.WARNING)
    
    stats = logger.get_statistics()
    
    assert stats['total_events'] == 3, "Should have 3 total events"
    assert stats['events_in_memory'] == 3, "Should have 3 in memory"
    assert EventType.LOGIN_SUCCESS.value in stats['events_by_type'], "Should track login"
    
    print("✓ PASSED")


def test_auth_manager_init():
    """Test 6: Auth manager initialization"""
    print("Test 6: Auth manager initialization...", end=" ")
    
    auth = AuthManager()
    
    assert 'admin' in auth.users, "Should have default admin user"
    assert 'operator' in auth.users, "Should have default operator user"
    assert auth.users['admin'].role == Role.ADMINISTRATOR, "Admin should be administrator"
    
    print("✓ PASSED")


def test_create_user():
    """Test 7: Create user"""
    print("Test 7: Create user...", end=" ")
    
    auth = AuthManager()
    
    user = auth.create_user(
        username="engineer1",
        password="password123",
        role=Role.ENGINEER,
        full_name="Test Engineer"
    )
    
    assert user is not None, "Should create user"
    assert user.username == "engineer1", "Should set username"
    assert user.role == Role.ENGINEER, "Should set role"
    assert user.enabled is True, "Should be enabled by default"
    
    # Try duplicate
    duplicate = auth.create_user(
        username="engineer1",
        password="different",
        role=Role.OPERATOR
    )
    assert duplicate is None, "Should not create duplicate"
    
    print("✓ PASSED")


def test_authenticate_success():
    """Test 8: Successful authentication"""
    print("Test 8: Successful authentication...", end=" ")
    
    auth = AuthManager()
    
    session_id = auth.authenticate("admin", "admin123", "127.0.0.1")
    
    assert session_id is not None, "Should return session ID"
    assert session_id in auth.sessions, "Should create session"
    assert auth.stats['successful_logins'] == 1, "Should count successful login"
    
    print("✓ PASSED")


def test_authenticate_failure():
    """Test 9: Failed authentication"""
    print("Test 9: Failed authentication...", end=" ")
    
    auth = AuthManager()
    
    # Wrong password
    session_id = auth.authenticate("admin", "wrongpassword", "127.0.0.1")
    
    assert session_id is None, "Should not create session"
    assert auth.stats['failed_logins'] == 1, "Should count failed login"
    assert auth.users['admin'].failed_login_attempts == 1, "Should increment attempts"
    
    print("✓ PASSED")


def test_brute_force_protection():
    """Test 10: Brute force protection"""
    print("Test 10: Brute force protection...", end=" ")
    
    auth = AuthManager(max_failed_attempts=3)
    
    # Try 3 failed logins
    for i in range(3):
        auth.authenticate("admin", "wrong", "127.0.0.1")
    
    # Account should be locked
    assert 'admin' in auth.lockouts, "Should lock account"
    assert auth.stats['lockouts'] == 1, "Should count lockout"
    
    # Try with correct password (should still fail due to lockout)
    session_id = auth.authenticate("admin", "admin123", "127.0.0.1")
    assert session_id is None, "Should deny login due to lockout"
    
    print("✓ PASSED")


def test_session_validation():
    """Test 11: Session validation"""
    print("Test 11: Session validation...", end=" ")
    
    auth = AuthManager()
    
    # Create session
    session_id = auth.authenticate("admin", "admin123", "127.0.0.1")
    
    # Validate session
    user = auth.validate_session(session_id)
    assert user is not None, "Should validate session"
    assert user.username == "admin", "Should return correct user"
    
    # Invalid session
    invalid_user = auth.validate_session("invalid_session_id")
    assert invalid_user is None, "Should reject invalid session"
    
    print("✓ PASSED")


def test_logout():
    """Test 12: Logout"""
    print("Test 12: Logout...", end=" ")
    
    auth = AuthManager()
    
    # Login
    session_id = auth.authenticate("admin", "admin123", "127.0.0.1")
    assert session_id in auth.sessions, "Should create session"
    
    # Logout
    success = auth.logout(session_id)
    assert success is True, "Should logout successfully"
    assert session_id not in auth.sessions, "Should destroy session"
    
    print("✓ PASSED")


def test_permission_checking():
    """Test 13: Permission checking"""
    print("Test 13: Permission checking...", end=" ")
    
    auth = AuthManager()
    
    # Viewer has read permissions only
    viewer_session = auth.authenticate("viewer", "viewer123", "127.0.0.1")
    assert auth.check_permission(viewer_session, Permission.READ_STATUS) is True, "Viewer can read"
    assert auth.check_permission(viewer_session, Permission.WRITE_COMMAND) is False, "Viewer cannot write"
    
    # Admin has all permissions
    admin_session = auth.authenticate("admin", "admin123", "127.0.0.1")
    assert auth.check_permission(admin_session, Permission.READ_STATUS) is True, "Admin can read"
    assert auth.check_permission(admin_session, Permission.WRITE_COMMAND) is True, "Admin can write"
    assert auth.check_permission(admin_session, Permission.ADMIN_SECURITY) is True, "Admin has security"
    
    print("✓ PASSED")


def test_role_permissions():
    """Test 14: Role-based permissions"""
    print("Test 14: Role-based permissions...", end=" ")
    
    auth = AuthManager()
    
    # Create engineer
    auth.create_user("engineer", "password", Role.ENGINEER)
    engineer_session = auth.authenticate("engineer", "password", "127.0.0.1")
    
    # Engineer can control
    assert auth.check_permission(engineer_session, Permission.CONTROL_BREAKER) is True
    assert auth.check_permission(engineer_session, Permission.CONTROL_OLTC) is True
    
    # But not admin functions
    assert auth.check_permission(engineer_session, Permission.ADMIN_USER_MANAGEMENT) is False
    
    print("✓ PASSED")


def test_security_config():
    """Test 15: Security configuration"""
    print("Test 15: Security configuration...", end=" ")
    
    # Default config
    default_config = SecurityConfig.default()
    assert default_config.session_timeout_minutes == 30
    assert default_config.audit_log_enabled is True
    
    # Strict config
    strict_config = SecurityConfig.strict()
    assert strict_config.session_timeout_minutes == 15
    assert strict_config.max_failed_login_attempts == 3
    assert strict_config.critical_commands_require_dual_auth is True
    
    # Development config
    dev_config = SecurityConfig.development()
    assert dev_config.session_timeout_minutes == 120
    assert dev_config.require_command_confirmation is False
    
    print("✓ PASSED")


def run_all_tests():
    """Run all security tests"""
    print("\n" + "="*60)
    print("Security Module Test Suite")
    print("="*60 + "\n")
    
    tests = [
        test_audit_logger_init,
        test_audit_log_event,
        test_audit_log_helpers,
        test_audit_query_events,
        test_audit_statistics,
        test_auth_manager_init,
        test_create_user,
        test_authenticate_success,
        test_authenticate_failure,
        test_brute_force_protection,
        test_session_validation,
        test_logout,
        test_permission_checking,
        test_role_permissions,
        test_security_config,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed == 0:
        print("\n✅ All security tests PASSED!\n")
        return 0
    else:
        print(f"\n❌ {failed} test(s) FAILED\n")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
