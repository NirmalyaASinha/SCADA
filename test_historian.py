"""
Test Suite for TimescaleDB Historian

Tests time-series storage, retrieval, aggregation, and alarm storage.
"""

import asyncio
import sys
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, '/home/nirmalya/Desktop/SCADA_SIM')

from historians import TimescaleDBHistorian, MeasurementPoint


async def test_historian_init():
    """Test 1: Historian initialization"""
    print("Test 1: Historian initialization...", end=" ")
    
    historian = TimescaleDBHistorian(use_mock=True)
    connected = await historian.connect()
    
    assert connected is True, "Should connect successfully"
    assert historian.is_connected is True, "Should be marked connected"
    assert historian.use_mock is True, "Should be in mock mode"
    
    await historian.disconnect()
    
    print("✓ PASSED")


async def test_store_single_measurement():
    """Test 2: Store single measurement"""
    print("Test 2: Store single measurement...", end=" ")
    
    historian = TimescaleDBHistorian(use_mock=True)
    await historian.connect()
    
    measurement = MeasurementPoint(
        time=datetime.utcnow(),
        node_id="GEN-001",
        voltage_kv=230.5,
        current_a=1250.0,
        power_mw=287.6,
        frequency_hz=50.0,
        breaker_closed=True
    )
    
    result = await historian.store_measurement(measurement)
    
    assert result is True, "Should store successfully"
    assert historian.measurements_stored == 1, "Should count 1 measurement"
    assert len(historian.mock_measurements) == 1, "Should have 1 in memory"
    
    await historian.disconnect()
    
    print("✓ PASSED")


async def test_store_batch_measurements():
    """Test 3: Store batch measurements"""
    print("Test 3: Store batch measurements...", end=" ")
    
    historian = TimescaleDBHistorian(use_mock=True)
    await historian.connect()
    
    # Create batch of measurements
    measurements = []
    base_time = datetime.utcnow()
    
    for i in range(10):
        measurements.append(
            MeasurementPoint(
                time=base_time + timedelta(seconds=i),
                node_id="SUB-001",
                voltage_kv=225.0 + i * 0.5,
                current_a=800.0 + i * 10,
                power_mw=180.0 + i * 2.25,
                frequency_hz=50.0,
                breaker_closed=True
            )
        )
    
    count = await historian.store_measurements_batch(measurements)
    
    assert count == 10, "Should store all 10 measurements"
    assert historian.measurements_stored == 10, "Should count 10"
    
    await historian.disconnect()
    
    print("✓ PASSED")


async def test_query_measurements():
    """Test 4: Query measurements by node"""
    print("Test 4: Query measurements by node...", end=" ")
    
    historian = TimescaleDBHistorian(use_mock=True)
    await historian.connect()
    
    # Store measurements for multiple nodes
    base_time = datetime.utcnow()
    
    for node_id in ["GEN-001", "GEN-002", "SUB-001"]:
        for i in range(5):
            await historian.store_measurement(
                MeasurementPoint(
                    time=base_time + timedelta(seconds=i),
                    node_id=node_id,
                    voltage_kv=230.0,
                    current_a=1000.0,
                    power_mw=230.0,
                    frequency_hz=50.0
                )
            )
    
    # Query for specific node
    results = await historian.get_measurements(node_id="GEN-001")
    
    assert len(results) == 5, "Should retrieve 5 measurements for GEN-001"
    assert all(m.node_id == "GEN-001" for m in results), "All should be GEN-001"
    
    # Query all nodes
    all_results = await historian.get_measurements()
    assert len(all_results) == 15, "Should retrieve all 15 measurements"
    
    await historian.disconnect()
    
    print("✓ PASSED")


async def test_query_time_range():
    """Test 5: Query measurements with time range"""
    print("Test 5: Query measurements with time range...", end=" ")
    
    historian = TimescaleDBHistorian(use_mock=True)
    await historian.connect()
    
    # Store measurements across time span (all in the past)
    base_time = datetime.utcnow() - timedelta(hours=2)
    
    for i in range(10):
        await historian.store_measurement(
            MeasurementPoint(
                time=base_time + timedelta(minutes=i * 10),
                node_id="SUB-001",
                voltage_kv=225.0,
                current_a=800.0,
                power_mw=180.0,
                frequency_hz=50.0
            )
        )
    
    # Query with time range that includes some measurements
    # Base time is 2 hours ago, measurements span from 120 min to 30 min ago
    start_time = datetime.utcnow() - timedelta(hours=1, minutes=30)  # 90 min ago
    results = await historian.get_measurements(
        node_id="SUB-001",
        start_time=start_time
    )
    
    # Should get measurements from index 6-9 (60, 70, 80, 90 min offset = 4 measurements)
    assert len(results) >= 3, f"Should get at least 3 measurements, got {len(results)}"
    assert all(m.time >= start_time for m in results), "All in time range"
    
    await historian.disconnect()
    
    print("✓ PASSED")


async def test_latest_measurement():
    """Test 6: Get latest measurement for node"""
    print("Test 6: Get latest measurement for node...", end=" ")
    
    historian = TimescaleDBHistorian(use_mock=True)
    await historian.connect()
    
    # Store measurements
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
    
    # Get latest
    latest = await historian.get_latest_measurement("GEN-001")
    
    assert latest is not None, "Should retrieve latest measurement"
    assert latest.voltage_kv == 234.0, "Should be most recent (last stored)"
    
    await historian.disconnect()
    
    print("✓ PASSED")


async def test_store_alarms():
    """Test 7: Store and query alarms"""
    print("Test 7: Store and query alarms...", end=" ")
    
    historian = TimescaleDBHistorian(use_mock=True)
    await historian.connect()
    
    # Store alarms
    result1 = await historian.store_alarm(
        node_id="GEN-001",
        alarm_type="overvoltage",
        alarm_value=255.0,
        severity="high",
        description="Voltage exceeded 250 kV"
    )
    
    result2 = await historian.store_alarm(
        node_id="SUB-001",
        alarm_type="frequency",
        alarm_value=49.2,
        severity="medium",
        description="Frequency below 49.5 Hz"
    )
    
    assert result1 is True, "Should store first alarm"
    assert result2 is True, "Should store second alarm"
    assert historian.alarms_stored == 2, "Should count 2 alarms"
    
    # Query alarms
    alarms = await historian.get_alarms()
    assert len(alarms) == 2, "Should retrieve 2 alarms"
    
    # Query by node
    gen_alarms = await historian.get_alarms(node_id="GEN-001")
    assert len(gen_alarms) == 1, "Should retrieve 1 alarm for GEN-001"
    assert gen_alarms[0]['alarm_type'] == "overvoltage", "Should be overvoltage alarm"
    
    await historian.disconnect()
    
    print("✓ PASSED")


async def test_aggregated_stats():
    """Test 8: Aggregated statistics"""
    print("Test 8: Aggregated statistics...", end=" ")
    
    historian = TimescaleDBHistorian(use_mock=True)
    await historian.connect()
    
    # Store measurements across time
    base_time = datetime.utcnow() - timedelta(hours=3)
    
    for i in range(20):
        await historian.store_measurement(
            MeasurementPoint(
                time=base_time + timedelta(minutes=i * 10),
                node_id="GEN-001",
                voltage_kv=225.0 + (i % 5),  # Varies from 225-229
                current_a=1000.0 + i * 10,   # Increases
                power_mw=225.0,
                frequency_hz=50.0
            )
        )
    
    # Get hourly aggregations
    stats = await historian.get_aggregated_stats(
        node_id="GEN-001",
        bucket_interval="1 hour"
    )
    
    assert 'voltage_kv' in stats, "Should have voltage stats"
    assert len(stats['voltage_kv']) >= 1, "Should have at least 1 bucket"
    
    # Verify statistics structure
    bucket = stats['voltage_kv'][0]
    assert 'avg' in bucket, "Should have average"
    assert 'min' in bucket, "Should have min"
    assert 'max' in bucket, "Should have max"
    assert 'count' in bucket, "Should have count"
    
    await historian.disconnect()
    
    print("✓ PASSED")


async def test_node_stats():
    """Test 9: Node statistics summary"""
    print("Test 9: Node statistics summary...", end=" ")
    
    historian = TimescaleDBHistorian(use_mock=True)
    await historian.connect()
    
    # Store measurements
    base_time = datetime.utcnow()
    
    for i in range(15):
        await historian.store_measurement(
            MeasurementPoint(
                time=base_time + timedelta(seconds=i * 5),
                node_id="SUB-001",
                voltage_kv=225.0,
                current_a=800.0,
                power_mw=180.0,
                frequency_hz=50.0
            )
        )
    
    # Get statistics
    stats = await historian.get_node_stats("SUB-001")
    
    assert stats['node_id'] == "SUB-001", "Should be for correct node"
    assert stats['measurement_count'] == 15, "Should have 15 measurements"
    assert stats['latest_time'] is not None, "Should have latest time"
    assert stats['earliest_time'] is not None, "Should have earliest time"
    
    await historian.disconnect()
    
    print("✓ PASSED")


async def test_historian_stats():
    """Test 10: Historian statistics"""
    print("Test 10: Historian statistics...", end=" ")
    
    historian = TimescaleDBHistorian(use_mock=True)
    await historian.connect()
    
    # Perform operations
    await historian.store_measurement(
        MeasurementPoint(
            time=datetime.utcnow(),
            node_id="GEN-001",
            voltage_kv=230.0,
            current_a=1000.0,
            power_mw=230.0,
            frequency_hz=50.0
        )
    )
    
    await historian.store_alarm(
        node_id="GEN-001",
        alarm_type="test",
        alarm_value=100.0,
        severity="low"
    )
    
    await historian.get_measurements()
    
    # Get stats
    stats = historian.get_stats()
    
    assert stats['is_connected'] is True, "Should be connected"
    assert stats['mode'] == 'mock', "Should be mock mode"
    assert stats['measurements_stored'] == 1, "Should have 1 measurement"
    assert stats['alarms_stored'] == 1, "Should have 1 alarm"
    assert stats['queries_executed'] == 1, "Should have 1 query"
    
    await historian.disconnect()
    
    print("✓ PASSED")


async def run_all_tests():
    """Run all historian tests"""
    print("\n" + "="*60)
    print("SCADA TimescaleDB Historian Test Suite")
    print("="*60 + "\n")
    
    tests = [
        test_historian_init,
        test_store_single_measurement,
        test_store_batch_measurements,
        test_query_measurements,
        test_query_time_range,
        test_latest_measurement,
        test_store_alarms,
        test_aggregated_stats,
        test_node_stats,
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
        print("\n✅ All historian tests PASSED!\n")
        return 0
    else:
        print(f"\n❌ {failed} test(s) FAILED\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
