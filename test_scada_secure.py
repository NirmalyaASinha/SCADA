"""
Test Suite for Secure SCADA Master

Tests integration of security with SCADA operations.
"""

import asyncio
import sys

# Add parent directory to path
sys.path.insert(0, '/home/nirmalya/Desktop/SCADA_SIM')

from scada_master_secure import SecureSCADAMaster
from security import SecurityConfig, Permission, EventType


async def test_secure_master_init():
    """Test 1: Secure SCADA master initialization"""
    print("Test 1: Secure SCADA master initialization...", end=" ")
    
    master = SecureSCADAMaster()
    
    assert master.auth_manager is not None, "Should have auth manager"
    assert master.audit_logger is not None, "Should have audit logger"
    assert master.security_config is not None, "Should have security config"
    
    await master.stop()
    
    print("✓ PASSED")


async def test_login_logout():
    """Test 2: Login and logout"""
    print("Test 2: Login and logout...", end=" ")
    
    master = SecureSCADAMaster()
    
    # Login with valid credentials
    session_id = master.login("admin", "admin123", "127.0.0.1")
    assert session_id is not None, "Should login successfully"
    
    # Logout
    success = master.logout(session_id)
    assert success is True, "Should logout successfully"
    
    await master.stop()
    
    print("✓ PASSED")


async def test_login_invalid():
    """Test 3: Login with invalid credentials"""
    print("Test 3: Login with invalid credentials...", end=" ")
    
    master = SecureSCADAMaster()
    
    # Wrong password
    session_id = master.login("admin", "wrongpassword", "127.0.0.1")
    assert session_id is None, "Should reject invalid password"
    
    # Non-existent user
    session_id = master.login("nonexistent", "password", "127.0.0.1")
    assert session_id is None, "Should reject non-existent user"
    
    await master.stop()
    
    print("✓ PASSED")


async def test_add_node_authorized():
    """Test 4: Add node with authorization"""
    print("Test 4: Add node with authorization...", end=" ")
    
    master = SecureSCADAMaster()
    
    # Login as admin
    session_id = master.login("admin", "admin123", "127.0.0.1")
    
    # Add node (admin has permission)
    success = master.add_node_secure(session_id, "GEN-001", "127.0.0.1")
    assert success is True, "Admin should be able to add node"
    assert "GEN-001" in master.nodes, "Node should be added"
    
    await master.stop()
    
    print("✓ PASSED")


async def test_add_node_unauthorized():
    """Test 5: Add node without authorization"""
    print("Test 5: Add node without authorization...", end=" ")
    
    master = SecureSCADAMaster()
    
    # Login as viewer (no write permissions)
    session_id = master.login("viewer", "viewer123", "127.0.0.1")
    
    # Try to add node (should be denied)
    success = master.add_node_secure(session_id, "GEN-001", "127.0.0.1")
    assert success is False, "Viewer should not be able to add node"
    assert "GEN-001" not in master.nodes, "Node should not be added"
    
    await master.stop()
    
    print("✓ PASSED")


async def test_send_command_authorized():
    """Test 6: Send command with authorization"""
    print("Test 6: Send command with authorization...", end=" ")
    
    master = SecureSCADAMaster()
    
    # Login as operator (has command permissions)
    session_id = master.login("operator", "operator123", "127.0.0.1")
    
    # Add node first (as admin)
    admin_session = master.login("admin", "admin123", "127.0.0.1")
    master.add_node_secure(admin_session, "GEN-001", "127.0.0.1")
    
    # Start master to enable command queue
    start_task = asyncio.create_task(master.start())
    await asyncio.sleep(0.3)  # Let it initialize
    
    # Send command as operator
    success = await master.send_command_secure(
        session_id,
        "GEN-001",
        "close_breaker"
    )
    # Command should be authorized (queued) even if execution fails
    # Success depends on whether node is actually reachable
    assert success is True, "Operator should be authorized to send command"
    
    await master.stop()
    try:
        await start_task
    except:
        pass
    
    print("✓ PASSED")


async def test_send_command_unauthorized():
    """Test 7: Send command without authorization"""
    print("Test 7: Send command without authorization...", end=" ")
    
    master = SecureSCADAMaster()
    
    # Login as viewer (no command permissions)
    session_id = master.login("viewer", "viewer123", "127.0.0.1")
    
    # Add node as admin
    admin_session = master.login("admin", "admin123", "127.0.0.1")
    master.add_node_secure(admin_session, "GEN-001", "127.0.0.1")
    
    # Try to send command as viewer
    success = await master.send_command_secure(
        session_id,
        "GEN-001",
        "close_breaker"
    )
    assert success is False, "Viewer should not be able to send command"
    
    await master.stop()
    
    print("✓ PASSED")


async def test_get_node_status_authorized():
    """Test 8: Get node status with authorization"""
    print("Test 8: Get node status with authorization...", end=" ")
    
    master = SecureSCADAMaster()
    
    # Login as viewer (has read permissions)
    session_id = master.login("viewer", "viewer123", "127.0.0.1")
    
    # Add node as admin
    admin_session = master.login("admin", "admin123", "127.0.0.1")
    master.add_node_secure(admin_session, "GEN-001", "127.0.0.1")
    
    # Get status as viewer
    status = master.get_node_status_secure(session_id, "GEN-001")
    assert status is not None, "Viewer should be able to read status"
    assert 'voltage_kv' in status, "Status should contain voltage"
    
    await master.stop()
    
    print("✓ PASSED")


async def test_get_node_status_unauthenticated():
    """Test 9: Get node status without authentication"""
    print("Test 9: Get node status without authentication...", end=" ")
    
    master = SecureSCADAMaster()
    
    # Try to get status without session
    status = master.get_node_status_secure("invalid_session")
    assert status is None, "Should deny unauthenticated access"
    
    await master.stop()
    
    print("✓ PASSED")


async def test_audit_logging():
    """Test 10: Audit logging integration"""
    print("Test 10: Audit logging integration...", end=" ")
    
    master = SecureSCADAMaster()
    
    # Login (should be logged)
    session_id = master.login("admin", "admin123", "127.0.0.1")
    
    # Add node (should be logged)
    master.add_node_secure(session_id, "GEN-001", "127.0.0.1")
    
    # Send command (should be logged)
    await master.send_command_secure(session_id, "GEN-001", "close_breaker")
    
    # Check audit logs
    stats = master.audit_logger.get_statistics()
    assert stats['total_events'] >= 3, "Should have logged multiple events"
    
    # Get specific events (as admin)
    events = master.get_audit_events(session_id, limit=100)
    assert events is not None, "Admin should access audit logs"
    assert len(events) >= 3, "Should have login + node add + command events"
    
    await master.stop()
    
    print("✓ PASSED")


async def test_security_statistics():
    """Test 11: Security statistics"""
    print("Test 11: Security statistics...", end=" ")
    
    master = SecureSCADAMaster()
    
    # Login as admin
    session_id = master.login("admin", "admin123", "127.0.0.1")
    
    # Get security statistics
    stats = master.get_security_statistics(session_id)
    assert stats is not None, "Admin should access security stats"
    assert 'auth_stats' in stats, "Should have auth stats"
    assert 'audit_stats' in stats, "Should have audit stats"
    
    await master.stop()
    
    print("✓ PASSED")


async def test_security_statistics_unauthorized():
    """Test 12: Security statistics without authorization"""
    print("Test 12: Security statistics without authorization...", end=" ")
    
    master = SecureSCADAMaster()
    
    # Login as viewer (no admin permissions)
    session_id = master.login("viewer", "viewer123", "127.0.0.1")
    
    # Try to get statistics
    stats = master.get_security_statistics(session_id)
    assert stats is None, "Viewer should not access security stats"
    
    await master.stop()
    
    print("✓ PASSED")


async def test_session_timeout():
    """Test 13: Session timeout handling"""
    print("Test 13: Session timeout handling...", end=" ")
    
    # Create master with 1-minute timeout
    config = SecurityConfig(session_timeout_minutes=1)
    master = SecureSCADAMaster(security_config=config)
    
    # Login
    session_id = master.login("admin", "admin123", "127.0.0.1")
    
    # Validate immediately (should work)
    user = master.auth_manager.validate_session(session_id)
    assert user is not None, "Session should be valid initially"
    
    # Session should refresh on activity
    user = master.auth_manager.validate_session(session_id)
    assert user is not None, "Session should refresh"
    
    await master.stop()
    
    print("✓ PASSED")


async def test_strict_security_config():
    """Test 14: Strict security configuration"""
    print("Test 14: Strict security configuration...", end=" ")
    
    config = SecurityConfig.strict()
    master = SecureSCADAMaster(security_config=config)
    
    assert master.security_config.session_timeout_minutes == 15, "Should have shorter timeout"
    assert master.security_config.max_failed_login_attempts == 3, "Should have stricter limit"
    assert master.security_config.critical_commands_require_dual_auth is True, "Should require dual auth"
    
    await master.stop()
    
    print("✓ PASSED")


async def test_audit_event_filtering():
    """Test 15: Audit event filtering"""
    print("Test 15: Audit event filtering...", end=" ")
    
    master = SecureSCADAMaster()
    
    # Login as admin
    admin_session = master.login("admin", "admin123", "127.0.0.1")
    
    # Login as operator
    operator_session = master.login("operator", "operator123", "127.0.0.1")
    
    # Perform actions
    master.add_node_secure(admin_session, "GEN-001", "127.0.0.1")
    
    # Get events filtered by user
    admin_events = master.get_audit_events(admin_session, user="admin", limit=100)
    operator_events = master.get_audit_events(admin_session, user="operator", limit=100)
    
    assert admin_events is not None, "Should get admin events"
    assert operator_events is not None, "Should get operator events"
    assert len(admin_events) >= 2, "Admin should have login + node add"
    assert len(operator_events) >= 1, "Operator should have login"
    
    await master.stop()
    
    print("✓ PASSED")


async def run_all_tests():
    """Run all secure SCADA master tests"""
    print("\n" + "="*60)
    print("Secure SCADA Master Test Suite")
    print("="*60 + "\n")
    
    tests = [
        test_secure_master_init,
        test_login_logout,
        test_login_invalid,
        test_add_node_authorized,
        test_add_node_unauthorized,
        test_send_command_authorized,
        test_send_command_unauthorized,
        test_get_node_status_authorized,
        test_get_node_status_unauthenticated,
        test_audit_logging,
        test_security_statistics,
        test_security_statistics_unauthorized,
        test_session_timeout,
        test_strict_security_config,
        test_audit_event_filtering,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            await test()
            passed += 1
        except AssertionError as e:
            print(f"✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed == 0:
        print("\n✅ All secure SCADA master tests PASSED!\n")
        return 0
    else:
        print(f"\n❌ {failed} test(s) FAILED\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
