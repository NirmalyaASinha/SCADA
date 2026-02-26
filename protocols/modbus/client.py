"""
Modbus TCP Client Wrapper
=========================

Wrapper around Modbus TCP protocol for SCADA master communication.

Features:
    - Connection management
    - Automatic reconnect on failure
    - Read/write operations (FC03/04, FC05/06)
    - Exception handling
    - Timeout management
"""

import socket
import struct
import logging
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
import time


logger = logging.getLogger(__name__)


class ModbusClient:
    """
    Modbus TCP client for communication with RTU nodes.
    
    Implements Modbus protocol framing:
    - MBAP (Modbus Application Protocol) header
    - Function codes: FC03 (read holding), FC04 (read input), FC05 (write coil), FC06 (write register)
    """
    
    def __init__(self, host: str, port: int = 502, timeout_s: float = 2.0):
        """
        Initialize Modbus client.
        
        Args:
            host: RTU IP address or hostname
            port: Modbus TCP port (default 502)
            timeout_s: Socket timeout in seconds
        """
        self.host = host
        self.port = port
        self.timeout_s = timeout_s
        self.socket: Optional[socket.socket] = None
        self.transaction_id = 0
        self.connected = False
        self.last_error: Optional[str] = None
        self.last_rx_time: datetime = datetime.now()
        
        # Connection statistics
        self.stats = {
            'connections': 0,
            'disconnections': 0,
            'reads': 0,
            'writes': 0,
            'errors': 0,
        }
    
    def connect(self) -> bool:
        """
        Connect to RTU via Modbus TCP.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout_s)
            self.socket.connect((self.host, self.port))
            self.connected = True
            self.stats['connections'] += 1
            logger.info(f"Modbus connected to {self.host}:{self.port}")
            return True
        
        except Exception as e:
            self.last_error = str(e)
            self.connected = False
            logger.error(f"Modbus connection failed to {self.host}: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from RTU."""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.connected = False
        self.stats['disconnections'] += 1
        logger.info(f"Modbus disconnected from {self.host}:{self.port}")
    
    def _get_transaction_id(self) -> int:
        """Get next transaction ID (1-65535)."""
        self.transaction_id = (self.transaction_id % 65535) + 1
        return self.transaction_id
    
    def read_holding_registers(self, address: int, count: int = 1) -> Optional[List[int]]:
        """
        Read holding registers (FC03).
        
        Args:
            address: Starting register address (0-65535)
            count: Number of registers to read (1-125)
        
        Returns:
            List of register values, or None on error
        """
        if not self.connected:
            if not self.connect():
                return None
        
        try:
            # Build request
            txn_id = self._get_transaction_id()
            request = self._build_request(txn_id, fc=3, address=address, count=count)
            
            # Send and receive
            self.socket.sendall(request)
            response = self.socket.recv(256)
            self.last_rx_time = datetime.now()
            self.stats['reads'] += 1
            
            # Parse response
            values = self._parse_read_response(response)
            return values
        
        except Exception as e:
            self.last_error = str(e)
            self.stats['errors'] += 1
            logger.error(f"Read failed for {self.host}: {e}")
            self.connected = False
            return None
    
    def read_input_registers(self, address: int, count: int = 1) -> Optional[List[int]]:
        """
        Read input registers (FC04).
        
        Args:
            address: Starting register address
            count: Number of registers to read
        
        Returns:
            List of register values, or None on error
        """
        if not self.connected:
            if not self.connect():
                return None
        
        try:
            txn_id = self._get_transaction_id()
            request = self._build_request(txn_id, fc=4, address=address, count=count)
            
            self.socket.sendall(request)
            response = self.socket.recv(256)
            self.last_rx_time = datetime.now()
            self.stats['reads'] += 1
            
            values = self._parse_read_response(response)
            return values
        
        except Exception as e:
            self.last_error = str(e)
            self.stats['errors'] += 1
            logger.error(f"Read failed for {self.host}: {e}")
            self.connected = False
            return None
    
    def read_coils(self, address: int, count: int = 1) -> Optional[List[bool]]:
        """
        Read coils (FC01).
        
        Args:
            address: Starting coil address
            count: Number of coils to read
        
        Returns:
            List of coil states, or None on error
        """
        if not self.connected:
            if not self.connect():
                return None
        
        try:
            txn_id = self._get_transaction_id()
            request = self._build_request(txn_id, fc=1, address=address, count=count)
            
            self.socket.sendall(request)
            response = self.socket.recv(256)
            self.last_rx_time = datetime.now()
            self.stats['reads'] += 1
            
            # Parse coil response
            coils = []
            if len(response) >= 9:
                byte_count = response[8]
                for i in range(count):
                    byte_idx = 9 + (i // 8)
                    bit_idx = i % 8
                    if byte_idx < len(response):
                        coils.append(bool((response[byte_idx] >> bit_idx) & 1))
            return coils if coils else None
        
        except Exception as e:
            self.last_error = str(e)
            self.stats['errors'] += 1
            logger.error(f"Read coils failed for {self.host}: {e}")
            self.connected = False
            return None
    
    def write_register(self, address: int, value: int) -> bool:
        """
        Write single register (FC06).
        
        Args:
            address: Register address
            value: Value to write (0-65535)
        
        Returns:
            True if successful, False otherwise
        """
        if not self.connected:
            if not self.connect():
                return False
        
        try:
            txn_id = self._get_transaction_id()
            request = self._build_write_request(txn_id, fc=6, address=address, value=value)
            
            self.socket.sendall(request)
            response = self.socket.recv(256)
            self.last_rx_time = datetime.now()
            self.stats['writes'] += 1
            
            # Check for exception
            if len(response) > 7 and response[7] & 0x80:
                exception_code = response[8]
                raise Exception(f"Modbus exception {exception_code}")
            
            return True
        
        except Exception as e:
            self.last_error = str(e)
            self.stats['errors'] += 1
            logger.error(f"Write failed for {self.host}: {e}")
            self.connected = False
            return False
    
    def write_coil(self, address: int, value: bool) -> bool:
        """
        Write single coil (FC05).
        
        Args:
            address: Coil address
            value: True (ON) or False (OFF)
        
        Returns:
            True if successful, False otherwise
        """
        if not self.connected:
            if not self.connect():
                return False
        
        try:
            txn_id = self._get_transaction_id()
            payload_value = 0xFF00 if value else 0x0000
            request = self._build_write_request(txn_id, fc=5, address=address, 
                                               value=payload_value)
            
            self.socket.sendall(request)
            response = self.socket.recv(256)
            self.last_rx_time = datetime.now()
            self.stats['writes'] += 1
            
            # Check for exception
            if len(response) > 7 and response[7] & 0x80:
                exception_code = response[8]
                raise Exception(f"Modbus exception {exception_code}")
            
            return True
        
        except Exception as e:
            self.last_error = str(e)
            self.stats['errors'] += 1
            logger.error(f"Write coil failed for {self.host}: {e}")
            self.connected = False
            return False
    
    def _build_request(self, txn_id: int, fc: int, address: int, count: int) -> bytes:
        """Build Modbus TCP request."""
        # MBAP header (12 bytes)
        request = bytearray()
        request.extend(struct.pack('>HHH', txn_id, 0, 6))  # Transaction, protocol, length
        request.append(1)  # Unit ID
        request.append(fc)  # Function code
        request.extend(struct.pack('>HH', address, count))  # Address, count
        return bytes(request)
    
    def _build_write_request(self, txn_id: int, fc: int, address: int, 
                           value: int) -> bytes:
        """Build Modbus TCP write request (FC05/06)."""
        request = bytearray()
        request.extend(struct.pack('>HHH', txn_id, 0, 6))  # Transaction, protocol, length
        request.append(1)  # Unit ID
        request.append(fc)  # Function code
        request.extend(struct.pack('>H', address))  # Address
        request.extend(struct.pack('>H', value))  # Value
        return bytes(request)
    
    def _parse_read_response(self, response: bytes) -> Optional[List[int]]:
        """Parse Modbus read response."""
        if len(response) < 9:
            raise ValueError("Response too short")
        
        # Check for exception
        if response[7] & 0x80:
            exception_code = response[8] if len(response) > 8 else 0
            raise Exception(f"Modbus exception {exception_code}")
        
        byte_count = response[8]
        values = []
        
        for i in range(byte_count // 2):
            offset = 9 + (i * 2)
            if offset + 1 < len(response):
                value = struct.unpack('>H', response[offset:offset+2])[0]
                values.append(value)
        
        return values if values else None
    
    def is_healthy(self) -> bool:
        """Check if connection is healthy."""
        if not self.connected:
            return False
        
        # Check for timeout
        if (datetime.now() - self.last_rx_time).total_seconds() > 10:
            return False
        
        return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Modbus TCP client module - import and use ModbusClient class")
