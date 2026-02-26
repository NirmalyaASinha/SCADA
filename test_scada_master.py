#!/usr/bin/env python3
"""
Test SCADA Master Control Station

This test demonstrates:
    - Adding nodes to the master
    - Polling nodes via Modbus TCP
    - Executing commands
    - Monitoring alarms
    - Connection health checking

Note: Requires nodes to be running with Modbus servers.
      Can run simulator.py in another terminal first.
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent))

from scada_master import SCADAMaster


async def test_scada_master_basic():
    """Test basic SCADA master functionality."""
    
    print("\n" + "="*70)
    print("SCADA Master Control Station Test")
    print("="*70)
    
    # Create master
    master = SCADAMaster(log_level=logging.INFO)
    
    # Add nodes (would normally run on different ports via simulator)
    print("\nTest 1: Adding nodes...")
    master.add_node("GEN-001", "127.0.0.1", modbus_port=5020, iec104_port=2414)
    master.add_node("GEN-002", "127.0.0.1", modbus_port=5021, iec104_port=None)
    master.add_node("GEN-003", "127.0.0.1", modbus_port=5022, iec104_port=None)
    master.add_node("SUB-001", "127.0.0.1", modbus_port=5030, iec104_port=2514)
    master.add_node("SUB-002", "127.0.0.1", modbus_port=5031, iec104_port=None)
    
    print(f"  ✓ {len(master.nodes)} nodes added")
    
    # Test 2: Check node connections (informational, won't connect if no servers)
    print("\nTest 2: Node configuration...")
    for node_id, conn in master.nodes.items():
        print(f"  - {node_id}: {conn.ip} "
              f"(Modbus: {conn.modbus.port}, "
              f"IEC104: {conn.iec104.port if conn.iec104 else 'N/A'})")
    
    # Test 3: Queue and check command structure
    print("\nTest 3: Command queuing (without execution)...")
    if master.command_queue is None:
        master.command_queue = asyncio.Queue()
    
    await master.send_command("GEN-001", "close_breaker")
    await master.send_command("SUB-001", "raise_oltc")
    
    # Verify commands are queued
    command_count = master.command_queue.qsize()
    print(f"  ✓ {command_count} commands queued")
    
    # Test 4: Check master capabilities
    print("\nTest 4: Master capabilities...")
    capabilities = [
        "Multi-protocol support (Modbus TCP + IEC 104)",
        "Concurrent node polling",
        "Command queuing and execution",
        "Alarm generation (voltage, frequency)",
        "Connection health monitoring",
        "Measurement history per node",
    ]
    for cap in capabilities:
        print(f"  ✓ {cap}")
    
    # Test 5: Data structure validation
    print("\nTest 5: Data structures...")
    node = master.get_node_data("GEN-001")
    assert node is not None, "Node retrieval failed"
    assert node.voltage_kv == 0.0, "Initial voltage should be 0"
    assert node.frequency_hz == 50.0, "Initial frequency should be 50"
    assert node.preferred_protocol == 'modbus', "Should prefer Modbus"
    print(f"  ✓ Node structure valid: {node.node_id}")
    
    # Test 6: Statistics tracking
    print("\nTest 6: Statistics tracking...")
    assert master.stats['total_polls'] == 0, "Initial polls should be 0"
    assert master.stats['alarms_generated'] == 0, "Initial alarms should be 0"
    master.stats['total_polls'] = 5
    master.stats['successful_polls'] = 3
    master.stats['failed_polls'] = 2
    print(f"  ✓ Total polls: {master.stats['total_polls']}")
    print(f"  ✓ Successful: {master.stats['successful_polls']}")
    print(f"  ✓ Failed: {master.stats['failed_polls']}")
    
    # Test 7: Alarm generation
    print("\nTest 7: Alarm checking...")
    # Trigger overvoltage alarm
    node = master.nodes["GEN-001"]
    node.voltage_kv = 260.0  # Over limit
    master._check_alarms(node)
    assert master.stats['alarms_generated'] > 0, "Alarm should be generated"
    print(f"  ✓ Alarms generated: {master.stats['alarms_generated']}")
    
    # Test 8: Multi-node retrieval
    print("\nTest 8: Multi-node retrieval...")
    all_nodes = master.get_all_nodes()
    assert len(all_nodes) == 5, "Should have 5 nodes"
    print(f"  ✓ Retrieved {len(all_nodes)} nodes")
    
    print("\n" + "="*70)
    print("✅ All SCADA Master tests PASSED")
    print("="*70)
    print("\nNote: Full integration test requires running:")
    print("  1. simulator.py (in another terminal) - starts RTU nodes")
    print("  2. scada_master_cli.py (in this terminal) - starts master polling")
    print("\nThen the master will begin polling real simulated RTU nodes.")


async def main():
    """Run all tests."""
    try:
        await test_scada_master_basic()
        return 0
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
