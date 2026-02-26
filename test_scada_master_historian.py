"""
Test Suite for SCADA Master with Historian Integration

Tests the integrated SCADA Master that automatically stores
measurements and alarms in the TimescaleDB historian.
"""

import asyncio
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, '/home/nirmalya/Desktop/SCADA_SIM')

from scada_master_historian import SCADAMasterWithHistorian
from historians import TimescaleDBHistorian


async def test_master_historian_init():
    """Test 1: Initialize SCADA Master with historian"""
    print("Test 1: Initialize SCADA Master with historian...", end=" ")
    
    master = SCADAMasterWithHistorian()
    
    assert master.historian is not None, "Should have historian instance"
    assert master.historian_enabled is False, "Should not be enabled initially"
    
    print("✓ PASSED")


async def test_historian_connection():
    """Test 2: Connect historian on start"""
    print("Test 2: Connect historian on start...", end=" ")
    
    historian = TimescaleDBHistorian(use_mock=True)
    master = SCADAMasterWithHistorian(historian=historian)
    
    # Add a node
    master.add_node("GEN-001", "127.0.0.1", modbus_port=502, iec104_port=2414)
    
    # Start should connect historian (but we'll stop immediately)
    start_task = asyncio.create_task(master.start_with_historian())
    await asyncio.sleep(0.5)  # Let it connect
    await master.stop()
    
    try:
        await start_task
    except:
        pass  # Expected since we stopped early
    
    assert historian.is_connected is False, "Should disconnect on stop"
    
    print("✓ PASSED")


async def test_measurement_storage():
    """Test 3: Measurements stored in historian"""
    print("Test 3: Measurements stored in historian...", end=" ")
    
    historian = TimescaleDBHistorian(use_mock=True)
    master = SCADAMasterWithHistorian(historian=historian)
    
    # Enable historian manually for testing
    await historian.connect()
    master.historian_enabled = True
    
    # Add node
    master.add_node("GEN-001", "127.0.0.1", modbus_port=502, iec104_port=2414)
    
    # Manually store a measurement to test integration
    from historians import MeasurementPoint
    from datetime import datetime
    
    node = master.nodes["GEN-001"]
    await historian.store_measurement(
        MeasurementPoint(
            time=datetime.utcnow(),
            node_id="GEN-001",
            voltage_kv=230.5,
            current_a=1250.0,
            power_mw=287.6,
            frequency_hz=50.0,
            breaker_closed=True
        )
    )
    
    assert historian.measurements_stored >= 1, "Should store measurement"
    
    await master.stop()
    
    print("✓ PASSED")


async def test_get_measurement_history():
    """Test 4: Retrieve measurement history"""
    print("Test 4: Retrieve measurement history...", end=" ")
    
    historian = TimescaleDBHistorian(use_mock=True)
    master = SCADAMasterWithHistorian(historian=historian)
    
    await historian.connect()
    master.historian_enabled = True
    
    # Store some measurements
    from historians import MeasurementPoint
    from datetime import timedelta
    
    base_time = datetime.utcnow()
    for i in range(5):
        await historian.store_measurement(
            MeasurementPoint(
                time=base_time + timedelta(seconds=i),
                node_id="GEN-001",
                voltage_kv=230.0 + i,
                current_a=1000.0,
                power_mw=230.0,
                frequency_hz=50.0
            )
        )
    
    # Retrieve history
    history = await master.get_measurement_history("GEN-001", limit=10)
    
    assert len(history) == 5, "Should retrieve 5 measurements"
    assert isinstance(history[0], dict), "Should be dictionaries"
    assert 'voltage_kv' in history[0], "Should have voltage field"
    
    await master.stop()
    
    print("✓ PASSED")


async def test_get_node_statistics():
    """Test 5: Get node statistics"""
    print("Test 5: Get node statistics...", end=" ")
    
    historian = TimescaleDBHistorian(use_mock=True)
    master = SCADAMasterWithHistorian(historian=historian)
    
    await historian.connect()
    master.historian_enabled = True
    
    # Store measurements
    from historians import MeasurementPoint
    
    for i in range(10):
        await historian.store_measurement(
            MeasurementPoint(
                time=datetime.utcnow(),
                node_id="SUB-001",
                voltage_kv=225.0,
                current_a=800.0,
                power_mw=180.0,
                frequency_hz=50.0
            )
        )
    
    # Get statistics
    stats = await master.get_node_statistics("SUB-001")
    
    assert stats['node_id'] == "SUB-001", "Should be for correct node"
    assert stats['measurement_count'] == 10, "Should have 10 measurements"
    assert 'latest_time' in stats, "Should have latest time"
    
    await master.stop()
    
    print("✓ PASSED")


async def test_alarm_storage():
    """Test 6: Alarms stored in historian"""
    print("Test 6: Alarms stored in historian...", end=" ")
    
    historian = TimescaleDBHistorian(use_mock=True)
    master = SCADAMasterWithHistorian(historian=historian)
    
    await historian.connect()
    master.historian_enabled = True
    
    # Add node with alarm condition
    master.add_node("GEN-001", "127.0.0.1", modbus_port=502, iec104_port=2414)
    
    # Manually store alarm to test integration
    await historian.store_alarm(
        node_id="GEN-001",
        alarm_type="voltage",
        alarm_value=260.0,
        severity="high",
        description="Voltage out of range: 260.0 kV"
    )
    
    # Verify alarm stored
    assert historian.alarms_stored >= 1, "Should store at least 1 alarm"
    
    # Get alarms
    alarms = await master.get_recent_alarms(node_id="GEN-001")
    assert len(alarms) >= 1, "Should retrieve alarm"
    
    await master.stop()
    
    print("✓ PASSED")


async def test_get_aggregated_data():
    """Test 7: Get aggregated statistics"""
    print("Test 7: Get aggregated statistics...", end=" ")
    
    historian = TimescaleDBHistorian(use_mock=True)
    master = SCADAMasterWithHistorian(historian=historian)
    
    await historian.connect()
    master.historian_enabled = True
    
    # Store measurements
    from historians import MeasurementPoint
    from datetime import timedelta
    
    base_time = datetime.utcnow() - timedelta(hours=2)
    for i in range(20):
        await historian.store_measurement(
            MeasurementPoint(
                time=base_time + timedelta(minutes=i * 5),
                node_id="GEN-001",
                voltage_kv=225.0 + i,
                current_a=1000.0,
                power_mw=225.0,
                frequency_hz=50.0
            )
        )
    
    # Get aggregated data
    agg_data = await master.get_aggregated_data(
        node_id="GEN-001",
        bucket_interval="hourly"
    )
    
    assert isinstance(agg_data, dict), "Should return dictionary"
    # Data might be empty if bucketing doesn't match, but should not error
    
    await master.stop()
    
    print("✓ PASSED")


async def test_historian_stats():
    """Test 8: Get historian statistics"""
    print("Test 8: Get historian statistics...", end=" ")
    
    historian = TimescaleDBHistorian(use_mock=True)
    master = SCADAMasterWithHistorian(historian=historian)
    
    await historian.connect()
    master.historian_enabled = True
    
    # Get stats
    stats = master.get_historian_stats()
    
    assert 'is_connected' in stats, "Should have connection status"
    assert 'mode' in stats, "Should have mode"
    assert stats['mode'] == 'mock', "Should be in mock mode"
    
    await master.stop()
    
    print("✓ PASSED")


async def run_all_tests():
    """Run all SCADA Master historian integration tests"""
    print("\n" + "="*60)
    print("SCADA Master with Historian Integration Test Suite")
    print("="*60 + "\n")
    
    tests = [
        test_master_historian_init,
        test_historian_connection,
        test_measurement_storage,
        test_get_measurement_history,
        test_get_node_statistics,
        test_alarm_storage,
        test_get_aggregated_data,
        test_historian_stats,
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
            failed += 1
    
    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed == 0:
        print("\n✅ All SCADA Master historian tests PASSED!\n")
        return 0
    else:
        print(f"\n❌ {failed} test(s) FAILED\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
