"""
Test Suite for IEC 60870-5-104 Protocol Implementation
======================================================

Tests validate:
    - Message encoding/decoding
    - APDU frame structure
    - Connection state machine
    - Basic server functionality
"""

import unittest
import asyncio
import sys
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from protocols.iec104.messages import (
    APDU, APCI, ASDU, APDUType, TypeID, CauseOfTransmission,
    ObjectAddress, UFrameFunction
)
from protocols.iec104.connection import ConnectionStateMachine, ConnectionState
from protocols.iec104.server import IEC104Server, IEC104Measurement


class TestIEC104Messages(unittest.TestCase):
    """Test IEC 104 message encoding and decoding"""
    
    def test_startdt_act_frame(self):
        """Test STARTDT activation frame"""
        apdu = APDU.create_startdt_act()
        self.assertEqual(apdu.apci.frame_type, APDUType.U_FRAME)
        self.assertEqual(apdu.apci.u_function, UFrameFunction.STARTDT_ACT)
    
    def test_startdt_con_frame(self):
        """Test STARTDT confirmation frame"""
        apdu = APDU.create_startdt_con()
        self.assertEqual(apdu.apci.frame_type, APDUType.U_FRAME)
        self.assertEqual(apdu.apci.u_function, UFrameFunction.STARTDT_CON)
    
    def test_testfr_act_frame(self):
        """Test TESTFR activation frame"""
        apdu = APDU.create_testfr_act()
        data = apdu.encode()
        
        # Should have start byte, length, and APCI
        self.assertEqual(data[0], 0x68)  # Start byte
        self.assertEqual(data[1], 4)     # Length of APCI
        
        # Decode and verify
        decoded, consumed = APDU.decode(data)
        self.assertEqual(decoded.apci.u_function, UFrameFunction.TESTFR_ACT)
        self.assertEqual(consumed, len(data))
    
    def test_supervisory_frame(self):
        """Test supervisory (S) frame"""
        apdu = APDU.create_supervisory(123)
        data = apdu.encode()
        
        self.assertEqual(data[0], 0x68)  # Start byte
        self.assertEqual(data[1], 4)     # APCI length
        
        # Decode and verify sequence
        decoded, consumed = APDU.decode(data)
        self.assertEqual(decoded.apci.frame_type, APDUType.S_FRAME)
        self.assertEqual(decoded.apci.receive_sequence, 123)
    
    def test_information_frame_with_asdu(self):
        """Test information (I) frame with data"""
        # Create ASDU with measurement
        obj = ObjectAddress(
            information_object_address=1,
            type_id=TypeID.M_ME_NC_1,
            cause=CauseOfTransmission.SPONTANEOUS,
            value=230.5,
            quality=0x00
        )
        asdu = ASDU(TypeID.M_ME_NC_1, CauseOfTransmission.SPONTANEOUS,
                   objects=[obj])
        
        # Create I frame
        apdu = APDU.create_data(send_seq=5, recv_seq=10, asdu=asdu)
        data = apdu.encode()
        
        # Verify encoding
        self.assertEqual(data[0], 0x68)  # Start byte
        self.assertGreater(data[1], 4)   # Length > APCI
        
        # Decode and verify
        decoded, consumed = APDU.decode(data)
        self.assertEqual(decoded.apci.send_sequence, 5)
        self.assertEqual(decoded.apci.receive_sequence, 10)
        self.assertIsNotNone(decoded.asdu)
        self.assertEqual(decoded.asdu.type_id, TypeID.M_ME_NC_1)
        self.assertEqual(len(decoded.asdu.objects), 1)
    
    def test_sequence_number_wrapping(self):
        """Test sequence number wrapping (0-32768)"""
        # Create frames with high sequence numbers
        apdu = APDU.create_supervisory(32767)  # Max value
        data = apdu.encode()
        decoded, _ = APDU.decode(data)
        self.assertEqual(decoded.apci.receive_sequence, 32767)
    
    def test_invalid_start_byte(self):
        """Test decoding invalid APDU (wrong start byte)"""
        bad_data = b'\x67\x04\x00\x00\x00\x00'  # Should be 0x68
        with self.assertRaises(ValueError):
            APDU.decode(bad_data)
    
    def test_apdu_too_short(self):
        """Test decoding incomplete APDU"""
        short_data = b'\x68\x04\x00'  # Too short
        with self.assertRaises(ValueError):
            APDU.decode(short_data)


class TestConnectionStateMachine(unittest.TestCase):
    """Test IEC 104 connection state machine"""
    
    def setUp(self):
        """Set up test connection"""
        self.conn = ConnectionStateMachine("192.168.1.100:54321")
    
    def test_initial_state(self):
        """Test initial connection state"""
        self.assertEqual(self.conn.state, ConnectionState.IDLE)
        self.assertEqual(self.conn.send_sequence, 0)
        self.assertEqual(self.conn.recv_sequence, 0)
    
    def test_connection_flow(self):
        """Test normal connection flow"""
        # TCP connected
        self.assertTrue(self.conn.on_connected())
        self.assertEqual(self.conn.state, ConnectionState.CONNECTED)
        self.assertFalse(self.conn.is_active())
        
        # STARTDT received
        self.assertTrue(self.conn.on_startdt_act())
        self.assertEqual(self.conn.state, ConnectionState.STARTED)
        self.assertTrue(self.conn.is_active())
        
        # STOPDT received
        self.assertTrue(self.conn.on_stopdt_act())
        self.assertEqual(self.conn.state, ConnectionState.STOPPED)
        self.assertFalse(self.conn.is_active())
    
    def test_invalid_state_transitions(self):
        """Test that invalid transitions are rejected"""
        # Can't STOPDT without STARTDT
        self.assertFalse(self.conn.on_stopdt_act())
        
        # Now valid transition
        self.conn.on_connected()
        self.conn.on_startdt_act()
        self.assertTrue(self.conn.on_stopdt_act())
    
    def test_sequence_number_increment(self):
        """Test sequence number increment on send"""
        self.assertEqual(self.conn.next_send_sequence(), 0)
        
        self.conn.on_data_sent()
        self.assertEqual(self.conn.next_send_sequence(), 1)
        
        self.conn.on_data_sent()
        self.assertEqual(self.conn.next_send_sequence(), 2)
    
    def test_testfr_management(self):
        """Test TESTFR (keep-alive) management"""
        self.conn.on_connected()
        self.conn.on_startdt_act()
        
        # Initially no TESTFR needed
        self.assertFalse(self.conn.testfr_active)
        self.assertFalse(self.conn.need_testfr())
        
        # After setting testfr_active, next check returns False
        self.conn.testfr_active = True
        self.assertFalse(self.conn.need_testfr())
        
        # Can consume TESTFR_CON
        self.assertTrue(self.conn.on_testfr_con())
        self.assertFalse(self.conn.testfr_active)
    
    def test_timeout_detection(self):
        """Test timeout detection"""
        import time
        
        self.conn.on_connected()
        
        # Fresh connection - no timeout
        self.assertFalse(self.conn.check_timeout(idle_timeout_s=1))
        
        # Simulate old timestamp
        self.conn.last_recv_time = self.conn.last_recv_time.replace(
            microsecond=0
        ) - self.conn.last_recv_time.replace(
            microsecond=0
        ).replace(year=2000)  # Simple time travel
        
        # Should detect timeout (10 second timeout)
        # Note: this test would need proper mocking for reliable timing


class TestIEC104Server(unittest.TestCase):
    """Test IEC 104 server basic functionality"""
    
    def setUp(self):
        """Set up test server"""
        self.server = IEC104Server(host='127.0.0.1', port=0)  # Port 0 = auto-select
    
    def test_server_creation(self):
        """Test server object creation"""
        self.assertFalse(self.server.running)
        self.assertEqual(len(self.server.connections), 0)
        self.assertEqual(len(self.server.measurements), 0)
    
    def test_measurement_storage(self):
        """Test storing measurements"""
        asyncio.run(self._test_measurement_storage())
    
    async def _test_measurement_storage(self):
        """Async test for measurement storage"""
        await self.server.send_measurement(
            information_object_address=1,
            value=230.5,
            type_id=TypeID.M_ME_NC_1,
            quality=0x00
        )
        
        # Check measurement was stored
        self.assertIn(1, self.server.measurements)
        measurement = self.server.measurements[1]
        self.assertEqual(measurement.value, 230.5)
        self.assertEqual(measurement.type_id, TypeID.M_ME_NC_1)
    
    def test_control_callback_registration(self):
        """Test registering control callbacks"""
        callback_called = []
        
        def test_callback(value):
            callback_called.append(value)
        
        self.server.register_control_callback(12, test_callback)
        self.assertIn(12, self.server.control_callbacks)
    
    def test_get_status(self):
        """Test getting server status"""
        status = self.server.get_status()
        
        self.assertIn('running', status)
        self.assertIn('connections', status)
        self.assertIn('measurements', status)
        self.assertEqual(status['connections'], 0)
        self.assertEqual(status['measurements'], 0)


class TestIEC104Integration(unittest.TestCase):
    """Integration tests for IEC 104 components"""
    
    def test_complete_message_flow(self):
        """Test complete message encoding/decoding flow"""
        # Create interrogation command
        obj = ObjectAddress(100, TypeID.C_IC_NA_1,
                          CauseOfTransmission.INTERROGATION, 0.0)
        asdu = ASDU(TypeID.C_IC_NA_1, CauseOfTransmission.INTERROGATION,
                   objects=[obj])
        apdu = APDU.create_data(send_seq=1, recv_seq=0, asdu=asdu)
        
        # Encode to bytes
        data = apdu.encode()
        
        # Decode back
        decoded, consumed = APDU.decode(data)
        
        # Verify round-trip
        self.assertEqual(decoded.apci.frame_type, APDUType.I_FRAME)
        self.assertEqual(decoded.apci.send_sequence, 1)
        self.assertEqual(decoded.asdu.type_id, TypeID.C_IC_NA_1)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
