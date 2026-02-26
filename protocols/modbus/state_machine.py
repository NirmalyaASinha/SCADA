"""
Modbus TCP State Machine
=========================

Implements the state machine for Modbus RTU request processing.

Real Modbus RTUs process requests through distinct states with realistic timing:

    IDLE → PROCESSING → RESPONDING → IDLE

State transitions:
    IDLE: Waiting for request
    PROCESSING: Validating request, fetching data, applying logic
    RESPONDING: Constructing and sending response

Processing delays are critical for realism:
    FC01 (Read Coils):              8-15ms
    FC03 (Read Holding Registers):  12-25ms
    FC05 (Write Single Coil):       15-30ms
    FC06 (Write Single Register):   15-30ms
    FC16 (Write Multiple Registers): 20-40ms

These delays create the "feel" of a real RTU when monitored with Wireshark.
Scripted attacks that don't account for these delays will be detectable.

Exception conditions:
    0x01 - Illegal Function: Function code not supported
    0x02 - Illegal Data Address: Register address out of range
    0x03 - Illegal Data Value: Value out of acceptable range
    0x04 - Slave Device Failure: RTU internal error
    0x06 - Slave Device Busy: Request received while processing previous

The state machine enforces single-threaded request processing - only one
request processed at a time, mirroring real RTU behavior.
"""

import time
import random
from enum import Enum
from typing import Dict, List, Optional, Tuple
import logging
import sys

# Support standalone testing
if __name__ == "__main__":
    sys.path.insert(0, '/home/nirmalya/Desktop/SCADA_SIM')

from config import MODBUS_CONFIG

logger = logging.getLogger(__name__)


class ModbusState(Enum):
    """Modbus RTU processing states."""
    IDLE = "IDLE"
    PROCESSING = "PROCESSING"
    RESPONDING = "RESPONDING"


class ModbusException(Enum):
    """Modbus exception codes."""
    ILLEGAL_FUNCTION = 0x01
    ILLEGAL_DATA_ADDRESS = 0x02
    ILLEGAL_DATA_VALUE = 0x03
    SLAVE_DEVICE_FAILURE = 0x04
    SLAVE_DEVICE_BUSY = 0x06


class ModbusStateMachine:
    """
    State machine for Modbus request processing.
    
    Enforces realistic RTU behavior:
    - Single request at a time
    - Realistic processing delays
    - Proper exception handling
    - Transaction ID management
    """
    
    def __init__(self, unit_id: int):
        """
        Initialize state machine.
        
        Args:
            unit_id: Modbus unit ID (1-255)
        """
        self.unit_id = unit_id
        self.state = ModbusState.IDLE
        
        # Processing timing
        self.processing_start_time = 0.0
        self.required_processing_time = 0.0
        
        # Current request being processed
        self.current_request: Optional[Dict] = None
        
        # Transaction ID counter
        self.transaction_id = 0
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "successful_responses": 0,
            "exceptions": 0,
            "busy_rejections": 0,
        }
        
        logger.info(f"Modbus state machine initialized for unit {unit_id}")
    
    def accept_request(self, function_code: int, request_data: Dict) -> Tuple[bool, Optional[int]]:
        """
        Attempt to accept a new request.
        
        Args:
            function_code: Modbus function code (1-127)
            request_data: Dict with request parameters
        
        Returns:
            (accepted, exception_code) - True if accepted, else False with exception code
        """
        self.stats["total_requests"] += 1
        
        # Check if busy
        if self.state != ModbusState.IDLE:
            logger.warning(f"Unit {self.unit_id} BUSY - rejecting request FC{function_code:02d}")
            self.stats["busy_rejections"] += 1
            return False, ModbusException.SLAVE_DEVICE_BUSY.value
        
        # Validate function code
        if function_code not in [1, 3, 5, 6, 16]:
            logger.error(f"Unit {self.unit_id} - Illegal function code: {function_code}")
            self.stats["exceptions"] += 1
            return False, ModbusException.ILLEGAL_FUNCTION.value
        
        # Accept request - transition to PROCESSING
        self.state = ModbusState.PROCESSING
        self.processing_start_time = time.time()
        
        # Determine processing time based on function code
        fc_key = f"FC{function_code:02d}"
        if fc_key in MODBUS_CONFIG["response_times_ms"]:
            min_ms, max_ms = MODBUS_CONFIG["response_times_ms"][fc_key]
            self.required_processing_time = random.uniform(min_ms, max_ms) / 1000.0
        else:
            # Default fallback
            self.required_processing_time = random.uniform(10, 20) / 1000.0
        
        # Store request
        self.current_request = {
            "function_code": function_code,
            "data": request_data,
            "transaction_id": self.transaction_id,
            "timestamp": time.time(),
        }
        
        self.transaction_id = (self.transaction_id + 1) % 65536  # 16-bit wraparound
        
        logger.debug(
            f"Unit {self.unit_id} - Accepted FC{function_code:02d}, "
            f"processing time {self.required_processing_time*1000:.1f}ms"
        )
        
        return True, None
    
    def is_processing_complete(self) -> bool:
        """
        Check if processing delay has elapsed.
        
        Returns:
            True if processing complete and ready for response
        """
        if self.state != ModbusState.PROCESSING:
            return False
        
        elapsed = time.time() - self.processing_start_time
        return elapsed >= self.required_processing_time
    
    def transition_to_responding(self):
        """Transition from PROCESSING to RESPONDING state."""
        if self.state == ModbusState.PROCESSING:
            self.state = ModbusState.RESPONDING
            logger.debug(f"Unit {self.unit_id} - Transitioning to RESPONDING")
    
    def complete_response(self):
        """Complete response and return to IDLE state."""
        if self.state == ModbusState.RESPONDING:
            self.state = ModbusState.IDLE
            self.stats["successful_responses"] += 1
            self.current_request = None
            logger.debug(f"Unit {self.unit_id} - Response complete, returning to IDLE")
    
    def force_idle(self):
        """Force return to IDLE state (error condition)."""
        self.state = ModbusState.IDLE
        self.current_request = None
        logger.warning(f"Unit {self.unit_id} - Forced to IDLE state")
    
    def get_state(self) -> str:
        """Get current state as string."""
        return self.state.value
    
    def get_stats(self) -> Dict:
        """Get statistics."""
        return self.stats.copy()
    
    def validate_address_range(
        self,
        start_address: int,
        count: int,
        max_address: int,
    ) -> Tuple[bool, Optional[int]]:
        """
        Validate that address range is within bounds.
        
        Args:
            start_address: Starting register/coil address
            count: Number of registers/coils
            max_address: Maximum valid address
        
        Returns:
            (valid, exception_code) - True if valid, else False with exception code
        """
        if start_address < 0:
            return False, ModbusException.ILLEGAL_DATA_ADDRESS.value
        
        if count <= 0:
            return False, ModbusException.ILLEGAL_DATA_VALUE.value
        
        end_address = start_address + count - 1
        
        if end_address > max_address:
            logger.error(
                f"Unit {self.unit_id} - Address out of range: "
                f"{start_address}+{count} > {max_address}"
            )
            return False, ModbusException.ILLEGAL_DATA_ADDRESS.value
        
        return True, None
    
    def validate_write_value(
        self,
        value: int,
        min_value: int,
        max_value: int,
    ) -> Tuple[bool, Optional[int]]:
        """
        Validate write value is within acceptable range.
        
        Args:
            value: Value to write
            min_value: Minimum acceptable value
            max_value: Maximum acceptable value
        
        Returns:
            (valid, exception_code) - True if valid, else False with exception code
        """
        if not (min_value <= value <= max_value):
            logger.error(
                f"Unit {self.unit_id} - Value out of range: "
                f"{value} not in [{min_value}, {max_value}]"
            )
            return False, ModbusException.ILLEGAL_DATA_VALUE.value
        
        return True, None


if __name__ == "__main__":
    # Test state machine
    logging.basicConfig(level=logging.DEBUG)
    
    sm = ModbusStateMachine(unit_id=1)
    
    print("\n===== MODBUS STATE MACHINE TEST =====\n")
    
    # Test 1: Accept request
    print("Test 1: Accept FC03 request")
    accepted, exc = sm.accept_request(3, {"address": 3000, "count": 10})
    print(f"  Accepted: {accepted}, Exception: {exc}")
    print(f"  State: {sm.get_state()}")
    
    # Test 2: Try to accept while busy
    print("\nTest 2: Try to accept while PROCESSING (should reject)")
    accepted, exc = sm.accept_request(3, {"address": 3001, "count": 5})
    print(f"  Accepted: {accepted}, Exception: {exc:#x}")
    print(f"  State: {sm.get_state()}")
    
    # Test 3: Wait for processing to complete
    print("\nTest 3: Wait for processing delay...")
    while not sm.is_processing_complete():
        time.sleep(0.001)
    print(f"  Processing complete!")
    
    # Test 4: Transition to responding
    print("\nTest 4: Transition to RESPONDING")
    sm.transition_to_responding()
    print(f"  State: {sm.get_state()}")
    
    # Test 5: Complete response
    print("\nTest 5: Complete response")
    sm.complete_response()
    print(f"  State: {sm.get_state()}")
    
    # Test 6: Invalid function code
    print("\nTest 6: Invalid function code")
    accepted, exc = sm.accept_request(99, {})
    print(f"  Accepted: {accepted}, Exception: {exc:#x}")
    
    # Test 7: Address validation
    print("\nTest 7: Address validation")
    valid, exc = sm.validate_address_range(3000, 125, 5000)
    print(f"  Range 3000+125 in [0, 5000]: Valid={valid}")
    
    valid, exc = sm.validate_address_range(4900, 125, 5000)
    print(f"  Range 4900+125 in [0, 5000]: Valid={valid}, Exception={exc:#x}")
    
    # Statistics
    print("\nStatistics:")
    stats = sm.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
