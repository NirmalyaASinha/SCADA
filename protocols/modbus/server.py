"""
Modbus TCP Server
=================

Production-faithful Modbus TCP server implementing spec-compliant behavior.

This server mirrors real RTU behavior observable via Wireshark:
    - Proper MBAP (Modbus Application Protocol) framing
    - Transaction ID management
    - Realistic response timing per function code
    - State machine enforcement (single request at a time)
    - Proper exception code generation

MBAP Header Format (7 bytes):
    Transaction ID:  2 bytes (0x0000-0xFFFF, incrementing)
    Protocol ID:     2 bytes (always 0x0000 for Modbus)
    Length:          2 bytes (byte count of Unit ID + PDU)
    Unit ID:         1 byte  (1-255, matches RTU/node assignment)

PDU Format:
    Function Code:   1 byte
    Data:            Variable (function-specific)

Supported Function Codes:
    FC01: Read Coils (0x references)
    FC03: Read Holding Registers (4x references)
    FC05: Write Single Coil
    FC06: Write Single Register
    FC16: Write Multiple Registers

Integration with Node:
    The server doesn't store data itself - it delegates to a node object
    that maintains the actual register/coil state. This separation matches
    real RTU architecture where protocol handling is separate from I/O.

Anomaly Detection Features:
    - Transaction timing logged for ML models
    - Exception counters for statistical analysis
    - Connection tracking for network behavior profiling
"""

import asyncio
import struct
import logging
from typing import Dict, List, Optional, Tuple
import time

from protocols.modbus.state_machine import ModbusStateMachine, ModbusException
from protocols.modbus.register_map import (
    encode_voltage_kv,
    encode_current_a,
    encode_power_mw,
    encode_frequency_hz,
    encode_temperature_celsius,
    decode_voltage_kv,
    decode_current_a,
    decode_power_mw,
    decode_frequency_hz,
    decode_temperature_celsius,
)
from config import MODBUS_CONFIG

logger = logging.getLogger(__name__)


class ModbusTCPServer:
    """
    Production-faithful Modbus TCP server.
    
    Implements exact protocol specification behavior that's indistinguishable
    from real RTUs when monitored with Wireshark.
    """
    
    def __init__(self, node, unit_id: int, port: int = 502):
        """
        Initialize Modbus TCP server.
        
        Args:
            node: Node object providing register/coil data
            unit_id: Modbus unit ID (1-255)
            port: TCP port (default 502)
        """
        self.node = node
        self.unit_id = unit_id
        self.port = port
        
        # State machine for request processing
        self.state_machine = ModbusStateMachine(unit_id)
        
        # Server state
        self.server: Optional[asyncio.Server] = None
        self.connections: List[asyncio.StreamWriter] = []
        
        # Statistics for anomaly detection
        self.stats = {
            "connections_total": 0,
            "connections_active": 0,
            "requests_fc01": 0,
            "requests_fc03": 0,
            "requests_fc05": 0,
            "requests_fc06": 0,
            "requests_fc16": 0,
            "exceptions_total": 0,
            "bytes_received": 0,
            "bytes_sent": 0,
        }
        
        logger.info(f"Modbus TCP server initialized - Unit {unit_id}, Port {port}")
    
    async def start(self):
        """Start the Modbus TCP server."""
        self.server = await asyncio.start_server(
            self._handle_connection,
            '0.0.0.0',
            self.port
        )
        
        addr = self.server.sockets[0].getsockname()
        logger.info(f"Modbus TCP server listening on {addr}")
    
    async def stop(self):
        """Stop the Modbus TCP server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Modbus TCP server stopped")
    
    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ):
        """
        Handle incoming TCP connection.
        
        Args:
            reader: Stream reader
            writer: Stream writer
        """
        addr = writer.get_extra_info('peername')
        logger.info(f"Connection from {addr}")
        
        self.connections.append(writer)
        self.stats["connections_total"] += 1
        self.stats["connections_active"] += 1
        
        try:
            while True:
                # Read MBAP header (7 bytes)
                header = await reader.readexactly(7)
                if not header:
                    break
                
                self.stats["bytes_received"] += 7
                
                # Parse MBAP header
                transaction_id, protocol_id, length, unit_id = struct.unpack('>HHHB', header)
                
                # Validate header
                if protocol_id != 0:
                    logger.error(f"Invalid protocol ID: {protocol_id:#x}")
                    break
                
                if unit_id != self.unit_id:
                    logger.warning(f"Unit ID mismatch: expected {self.unit_id}, got {unit_id}")
                    continue
                
                # Read PDU (length - 1 for unit ID already read)
                pdu_length = length - 1
                pdu = await reader.readexactly(pdu_length)
                self.stats["bytes_received"] += pdu_length
                
                # Process request
                response_pdu = await self._process_request(pdu)
                
                # Build response MBAP + PDU
                response_length = len(response_pdu) + 1  # +1 for unit ID
                response_header = struct.pack('>HHHB',
                    transaction_id,
                    0,  # Protocol ID
                    response_length,
                    unit_id
                )
                
                response = response_header + response_pdu
                
                # Send response
                writer.write(response)
                await writer.drain()
                
                self.stats["bytes_sent"] += len(response)
        
        except asyncio.IncompleteReadError:
            logger.info(f"Connection closed by {addr}")
        except Exception as e:
            logger.error(f"Error handling connection from {addr}: {e}", exc_info=True)
        finally:
            self.connections.remove(writer)
            self.stats["connections_active"] -= 1
            writer.close()
            await writer.wait_closed()
    
    async def _process_request(self, pdu: bytes) -> bytes:
        """
        Process Modbus request PDU.
        
        Args:
            pdu: Request PDU bytes
        
        Returns:
            Response PDU bytes
        """
        function_code = pdu[0]
        
        # Update request statistics
        fc_key = f"requests_fc{function_code:02d}"
        if fc_key in self.stats:
            self.stats[fc_key] += 1
        
        # Try to accept request
        accepted, exception_code = self.state_machine.accept_request(
            function_code,
            {"raw_pdu": pdu}
        )
        
        if not accepted:
            # Return exception response
            self.stats["exceptions_total"] += 1
            return self._build_exception_response(function_code, exception_code)
        
        # Wait for processing delay
        while not self.state_machine.is_processing_complete():
            await asyncio.sleep(0.001)
        
        self.state_machine.transition_to_responding()
        
        # Dispatch to function-specific handler
        try:
            if function_code == 1:
                response = self._handle_fc01(pdu[1:])
            elif function_code == 3:
                response = self._handle_fc03(pdu[1:])
            elif function_code == 5:
                response = self._handle_fc05(pdu[1:])
            elif function_code == 6:
                response = self._handle_fc06(pdu[1:])
            elif function_code == 16:
                response = self._handle_fc16(pdu[1:])
            else:
                # Should never reach here (state machine validates)
                response = self._build_exception_response(
                    function_code,
                    ModbusException.ILLEGAL_FUNCTION.value
                )
                self.stats["exceptions_total"] += 1
        except Exception as e:
            logger.error(f"Error processing FC{function_code:02d}: {e}", exc_info=True)
            response = self._build_exception_response(
                function_code,
                ModbusException.SLAVE_DEVICE_FAILURE.value
            )
            self.stats["exceptions_total"] += 1
            self.state_machine.force_idle()
            return response
        
        self.state_machine.complete_response()
        return response
    
    def _handle_fc01(self, data: bytes) -> bytes:
        """
        Handle FC01: Read Coils.
        
        Args:
            data: Request data (address + count)
        
        Returns:
            Response PDU
        """
        address, count = struct.unpack('>HH', data)
        
        # Validate address range
        valid, exception_code = self.state_machine.validate_address_range(
            address, count, 9999
        )
        if not valid:
            return self._build_exception_response(1, exception_code)
        
        # Read coils from node
        coils = self.node.read_coils(address, count)
        
        # Pack coils into bytes (8 coils per byte, LSB first)
        byte_count = (count + 7) // 8
        coil_bytes = bytearray(byte_count)
        
        for i, coil in enumerate(coils):
            if coil:
                byte_idx = i // 8
                bit_idx = i % 8
                coil_bytes[byte_idx] |= (1 << bit_idx)
        
        # Build response: FC + byte count + coil bytes
        response = struct.pack('BB', 1, byte_count) + bytes(coil_bytes)
        return response
    
    def _handle_fc03(self, data: bytes) -> bytes:
        """
        Handle FC03: Read Holding Registers.
        
        Args:
            data: Request data (address + count)
        
        Returns:
            Response PDU
        """
        address, count = struct.unpack('>HH', data)
        
        # Validate address range
        valid, exception_code = self.state_machine.validate_address_range(
            address, count, 49999
        )
        if not valid:
            return self._build_exception_response(3, exception_code)
        
        # Read registers from node
        registers = self.node.read_holding_registers(address, count)
        
        # Build response: FC + byte count + register values
        byte_count = count * 2
        response = struct.pack('BB', 3, byte_count)
        
        for reg in registers:
            response += struct.pack('>H', reg)
        
        return response
    
    def _handle_fc05(self, data: bytes) -> bytes:
        """
        Handle FC05: Write Single Coil.
        
        Args:
            data: Request data (address + value)
        
        Returns:
            Response PDU
        """
        address, value = struct.unpack('>HH', data)
        
        # Validate coil value (0x0000 or 0xFF00)
        if value not in [0x0000, 0xFF00]:
            return self._build_exception_response(
                5, ModbusException.ILLEGAL_DATA_VALUE.value
            )
        
        # Write coil to node
        coil_state = (value == 0xFF00)
        self.node.write_coil(address, coil_state)
        
        # Echo response
        response = struct.pack('>BHH', 5, address, value)
        return response
    
    def _handle_fc06(self, data: bytes) -> bytes:
        """
        Handle FC06: Write Single Register.
        
        Args:
            data: Request data (address + value)
        
        Returns:
            Response PDU
        """
        address, value = struct.unpack('>HH', data)
        
        # Validate value range (0-65535 for uint16)
        valid, exception_code = self.state_machine.validate_write_value(
            value, 0, 65535
        )
        if not valid:
            return self._build_exception_response(6, exception_code)
        
        # Write register to node
        self.node.write_holding_register(address, value)
        
        # Echo response
        response = struct.pack('>BHH', 6, address, value)
        return response
    
    def _handle_fc16(self, data: bytes) -> bytes:
        """
        Handle FC16: Write Multiple Registers.
        
        Args:
            data: Request data (address + count + byte count + values)
        
        Returns:
            Response PDU
        """
        address, count, byte_count = struct.unpack('>HHB', data[:5])
        
        # Validate byte count
        if byte_count != count * 2:
            return self._build_exception_response(
                16, ModbusException.ILLEGAL_DATA_VALUE.value
            )
        
        # Extract register values
        values = []
        for i in range(count):
            offset = 5 + (i * 2)
            value, = struct.unpack('>H', data[offset:offset+2])
            values.append(value)
        
        # Write registers to node
        self.node.write_holding_registers(address, values)
        
        # Response: FC + address + count
        response = struct.pack('>BHH', 16, address, count)
        return response
    
    def _build_exception_response(self, function_code: int, exception_code: int) -> bytes:
        """
        Build Modbus exception response.
        
        Args:
            function_code: Original function code
            exception_code: Exception code (0x01-0x06)
        
        Returns:
            Exception response PDU
        """
        # Exception response: (FC | 0x80) + Exception Code
        error_fc = function_code | 0x80
        return struct.pack('BB', error_fc, exception_code)
    
    def get_stats(self) -> Dict:
        """Get server statistics."""
        stats = self.stats.copy()
        stats["state_machine"] = self.state_machine.get_stats()
        return stats


# Example node interface (actual implementation in nodes/base_node.py)
class MockNode:
    """Mock node for testing - demonstrates the interface."""
    
    def __init__(self):
        self.coils = [False] * 10000
        self.holding_registers = [0] * 50000
    
    def read_coils(self, address: int, count: int) -> List[bool]:
        return self.coils[address:address+count]
    
    def read_holding_registers(self, address: int, count: int) -> List[int]:
        return self.holding_registers[address:address+count]
    
    def write_coil(self, address: int, value: bool):
        self.coils[address] = value
    
    def write_holding_register(self, address: int, value: int):
        self.holding_registers[address] = value
    
    def write_holding_registers(self, address: int, values: List[int]):
        for i, value in enumerate(values):
            self.holding_registers[address + i] = value


async def test_server():
    """Test Modbus TCP server."""
    import sys
    sys.path.insert(0, '/home/nirmalya/Desktop/SCADA_SIM')
    
    logging.basicConfig(level=logging.DEBUG)
    
    print("\n===== MODBUS TCP SERVER TEST =====\n")
    
    # Create mock node
    node = MockNode()
    
    # Populate some test data
    node.holding_registers[3000] = encode_voltage_kv(11.0)  # 11kV bus
    node.holding_registers[3001] = encode_current_a(150)    # 150A line current
    node.holding_registers[3002] = encode_power_mw(2.5)     # 2.5MW
    node.holding_registers[3003] = encode_frequency_hz(50.0)  # 50.0Hz
    
    node.coils[0] = True  # Breaker closed
    node.coils[1] = False # Breaker open
    
    # Start server on test port
    server = ModbusTCPServer(node, unit_id=1, port=5502)
    await server.start()
    
    print(f"Server started - Unit ID {server.unit_id}, Port {server.port}")
    print("Press Ctrl+C to stop\n")
    
    try:
        # Keep server running
        while True:
            await asyncio.sleep(5)
            
            # Print statistics
            stats = server.get_stats()
            print(f"\n--- Statistics ---")
            print(f"Connections: {stats['connections_active']} active, {stats['connections_total']} total")
            print(f"Requests: FC01={stats['requests_fc01']}, FC03={stats['requests_fc03']}, "
                  f"FC05={stats['requests_fc05']}, FC06={stats['requests_fc06']}, FC16={stats['requests_fc16']}")
            print(f"Exceptions: {stats['exceptions_total']}")
            print(f"Bytes: {stats['bytes_received']} RX, {stats['bytes_sent']} TX")
    
    except KeyboardInterrupt:
        print("\nStopping server...")
        await server.stop()


if __name__ == "__main__":
    asyncio.run(test_server())
