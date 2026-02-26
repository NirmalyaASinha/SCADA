"""
Test Suite for Dashboard API Server
Tests REST endpoints, authentication, and WebSocket connections
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from api_server import app
from fastapi.testclient import TestClient

# Test client
client = TestClient(app)

# ============================================================================
# Test 1: Health Check
# ============================================================================

def test_health_check():
    """Test API health endpoint"""
    print("\n=== Test 1: Health Check ===")
    
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    assert data["status"] == "healthy"
    
    print(f"✅ Health check: {data['status']}")
    print(f"   Timestamp: {data.get('timestamp')}")

# ============================================================================
# Test 2: Root Endpoint
# ============================================================================

def test_root_endpoint():
    """Test root endpoint returns API info"""
    print("\n=== Test 2: Root Endpoint ===")
    
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "name" in data
    assert data["name"] == "SCADA Dashboard API"
    assert "version" in data
    
    print(f"✅ API Name: {data['name']}")
    print(f"   Version: {data['version']}")

# ============================================================================
# Test 3: Authentication - Login Success
# ============================================================================

def test_login_success():
    """Test successful login"""
    print("\n=== Test 3: Login Success ===")
    
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "token" in data
    assert "username" in data
    assert data["username"] == "admin"
    assert "role" in data
    
    print(f"✅ Login successful")
    print(f"   Username: {data['username']}")
    print(f"   Role: {data['role']}")
    print(f"   Token: {data['token'][:20]}...")
    
    return data["token"]

# ============================================================================
# Test 4: Authentication - Login Failure
# ============================================================================

def test_login_failure():
    """Test failed login with invalid credentials"""
    print("\n=== Test 4: Login Failure ===")
    
    response = client.post(
        "/api/auth/login",
        json={"username": "invalid", "password": "wrong"}
    )
    
    assert response.status_code == 401
    
    print(f"✅ Invalid credentials rejected (HTTP 401)")

# ============================================================================
# Test 5: System Overview (Authenticated)
# ============================================================================

def test_system_overview():
    """Test system overview endpoint"""
    print("\n=== Test 5: System Overview ===")
    
    # Login first
    token = test_login_success()
    
    # Get system overview
    response = client.get(
        "/api/system/overview",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "total_nodes" in data
    assert "connected_nodes" in data
    assert "total_power_mw" in data
    assert "total_alarms" in data
    
    print(f"✅ System Overview Retrieved")
    print(f"   Total Nodes: {data['total_nodes']}")
    print(f"   Connected: {data['connected_nodes']}")
    print(f"   Total Power: {data['total_power_mw']} MW")
    print(f"   Alarms: {data['total_alarms']}")

# ============================================================================
# Test 6: Unauthorized Access
# ============================================================================

def test_unauthorized_access():
    """Test that endpoints require authentication"""
    print("\n=== Test 6: Unauthorized Access ===")
    
    # Try to access without token
    response = client.get("/api/system/overview")
    
    assert response.status_code == 403  # Forbidden or 401 Unauthorized
    
    print(f"✅ Unauthorized access blocked (HTTP {response.status_code})")

# ============================================================================
# Test 7: Get Nodes List
# ============================================================================

def test_get_nodes():
    """Test getting list of nodes"""
    print("\n=== Test 7: Get Nodes List ===")
    
    # Login first
    token = test_login_success()
    
    # Get nodes
    response = client.get(
        "/api/nodes",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "nodes" in data
    nodes = data["nodes"]
    
    print(f"✅ Retrieved {len(nodes)} nodes")
    
    if nodes:
        for node in nodes[:3]:  # Show first 3
            print(f"   - {node['node_id']}: {node.get('ip_address', 'N/A')}")

# ============================================================================
# Test 8: Get Alarms
# ============================================================================

def test_get_alarms():
    """Test getting alarm list"""
    print("\n=== Test 8: Get Alarms ===")
    
    # Login first
    token = test_login_success()
    
    # Get alarms
    response = client.get(
        "/api/alarms",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "alarms" in data
    assert "count" in data
    
    print(f"✅ Retrieved alarms")
    print(f"   Total: {data['count']}")

# ============================================================================
# Test 9: Logout
# ============================================================================

def test_logout():
    """Test logout functionality"""
    print("\n=== Test 9: Logout ===")
    
    # Login first
    token = test_login_success()
    
    # Logout
    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "logged out"
    
    print(f"✅ Logout successful")

# ============================================================================
# Test 10: Role-Based Access Control
# ============================================================================

def test_rbac():
    """Test role-based access control"""
    print("\n=== Test 10: Role-Based Access Control ===")
    
    # Login as viewer (limited permissions)
    response = client.post(
        "/api/auth/login",
        json={"username": "viewer", "password": "viewer123"}
    )
    
    assert response.status_code == 200
    viewer_token = response.json()["token"]
    
    # Try to access audit log (admin only)
    response = client.get(
        "/api/security/audit",
        headers={"Authorization": f"Bearer {viewer_token}"}
    )
    
    # Should be denied (403) or return error
    assert response.status_code in [403, 500]  # Access denied
    
    print(f"✅ RBAC: Viewer cannot access admin endpoints (HTTP {response.status_code})")

# ============================================================================
# Run All Tests
# ============================================================================

def run_all_tests():
    """Run all API tests"""
    print("\n" + "="*70)
    print("DASHBOARD API SERVER TEST SUITE")
    print("="*70)
    
    tests = [
        ("Health Check", test_health_check),
        ("Root Endpoint", test_root_endpoint),
        ("Login Success", test_login_success),
        ("Login Failure", test_login_failure),
        ("System Overview", test_system_overview),
        ("Unauthorized Access", test_unauthorized_access),
        ("Get Nodes List", test_get_nodes),
        ("Get Alarms", test_get_alarms),
        ("Logout", test_logout),
        ("Role-Based Access Control", test_rbac)
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ FAILED: {name}")
            print(f"   Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ ERROR: {name}")
            print(f"   Exception: {e}")
            failed += 1
    
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"✅ PASSED: {passed}")
    print(f"❌ FAILED: {failed}")
    print(f"Total: {passed + failed}")
    print("="*70)
    
    if failed == 0:
        print("\n🎉 All tests passed!\n")
    else:
        print(f"\n⚠️  {failed} test(s) failed\n")
    
    return failed == 0

if __name__ == "__main__":
    # Note: API server must be running for these tests
    print("\n⚠️  Make sure the API server is running:")
    print("   python3 api_server.py\n")
    
    success = run_all_tests()
    exit(0 if success else 1)
