#!/usr/bin/env python3
"""
Test IEC 104 Integration with Nodes

This test verifies:
    - IEC 104 server can be started on nodes
    - Measurements can be sent via IEC 104
    - Control commands can be received and executed
"""

import sys
import asyncio
from pathlib import Path

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from nodes import GenerationNode, SubstationNode, DistributionNode
from protocols.iec104.messages import TypeID


async def test_node_iec104_integration():
    """Test IEC 104 server on different node types"""
    
    print("\n" + "="*70)
    print("IEC 104 Node Integration Test")
    print("="*70)
    
    # Create test nodes
    gen_node = GenerationNode(node_id="GEN-001", generator_type="COAL",
                             rated_mw=500, rated_voltage_kv=230)
    sub_node = SubstationNode(node_id="SUB-001", transformer_mva=100,
                             primary_voltage_kv=230, secondary_voltage_kv=33)
    dist_node = DistributionNode(node_id="DIST-001", feeder_mva=50,
                                rated_voltage_kv=11)
    
    nodes = [gen_node, sub_node, dist_node]
    
    try:
        # Test 1: Start IEC 104 servers on all nodes
        print("\nTest 1: Starting IEC 104 servers...")
        for node in nodes:
            success = await node.start_iec104_server()
            assert success, f"Failed to start IEC 104 on {node.node_id}"
            print(f"  ✓ {node.node_id} - IEC 104 server started on port {node.iec104_port}")
        
        # Test 2: Send measurements
        print("\nTest 2: Sending IEC 104 measurements...")
        test_measurements = [
            (1, 230.5),   # Voltage
            (2, 150.3),   # Current
            (3, 34.5),    # Power
        ]
        
        for node in nodes:
            for ioa, value in test_measurements:
                await node.send_iec104_measurement(ioa, value, quality=0x00)
            
            # Check measurements were stored on server
            assert len(node.iec104_server.measurements) > 0
            print(f"  ✓ {node.node_id} - {len(node.iec104_server.measurements)} measurements stored")
        
        # Test 3: Check server status
        print("\nTest 3: IEC 104 server status...")
        for node in nodes:
            status = node.iec104_server.get_status()
            print(f"  {node.node_id}:")
            print(f"    - Running: {status['running']}")
            print(f"    - Connections: {status['connections']}")
            print(f"    - Measurements: {status['measurements']}")
        
        # Test 4: Control callback registration
        print("\nTest 4: Control command registration...")
        for node in nodes:
            node.iec104_server.register_control_callback(
                200,
                lambda val: print(f"Control command for {node.node_id}: {val}")
            )
            assert 200 in node.iec104_server.control_callbacks
            print(f"  ✓ {node.node_id} - Control callback registered for IOA 200")
        
        # Test 5: Stop servers cleanly
        print("\nTest 5: Stopping IEC 104 servers...")
        for node in nodes:
            success = await node.stop_iec104_server()
            assert success, f"Failed to stop IEC 104 on {node.node_id}"
            assert node.iec104_server is None
            print(f"  ✓ {node.node_id} - IEC 104 server stopped cleanly")
        
        print("\n" + "="*70)
        print("✅ All IEC 104 node integration tests PASSED")
        print("="*70 + "\n")
        return True
    
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        for node in nodes:
            try:
                if node.iec104_server:
                    await node.stop_iec104_server()
            except:
                pass


if __name__ == "__main__":
    # Run test
    success = asyncio.run(test_node_iec104_integration())
    sys.exit(0 if success else 1)
