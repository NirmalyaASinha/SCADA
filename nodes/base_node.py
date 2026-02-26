"""
Base Node Class
===============

Foundation class for all SCADA RTU nodes (generation, substation, distribution).

This class integrates:
    - Electrical models (power flow, thermal, protection)
    - Protocol servers (Modbus, IEC 104, DNP3)
    - Data quality management
    - Sequence of Events (SOE) recording

The base node provides the common infrastructure that all node types share:
    - Register/coil storage
    - Data quality tracking
    - Electrical state updates
    - Protocol server interfaces

Node-specific subclasses (GenerationNode, SubstationNode, DistributionNode)
add specialized behavior on top of this foundation.

Real SCADA RTUs have this same architecture - a common platform with
node-type-specific modules loaded on top.
"""

import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import logging
import sys

# Support standalone testing
if __name__ == "__main__":
    sys.path.insert(0, '/home/nirmalya/Desktop/SCADA_SIM')

from protocols.modbus.data_quality import DataQualityManager, DataQuality
from protocols.iec104.server import IEC104Server
from electrical.protection import ProtectionRelay, ProtectionState
from config import NODE_CONFIG, DATA_QUALITY

logger = logging.getLogger(__name__)


@dataclass
class ElectricalState:
    """
    Electrical state of a node.
    
    This mirrors what a real RTU measures and computes.
    """
    # Voltage measurements
    voltage_kv: float = 0.0
    voltage_pu: float = 0.0
    voltage_angle_deg: float = 0.0
    
    # Current measurements
    current_a: float = 0.0
    current_pu: float = 0.0
    
    # Power measurements
    p_mw: float = 0.0
    q_mvar: float = 0.0
    s_mva: float = 0.0
    power_factor: float = 1.0
    
    # Frequency
    frequency_hz: float = 50.0
    
    # Breaker states
    breaker_52_closed: bool = True
    breaker_52_position: str = "CLOSED"  # OPEN/CLOSED/INTERMEDIATE
    
    # Protection status
    protection_enabled: bool = True
    protection_healthy: bool = True
    protection_state: ProtectionState = field(default_factory=ProtectionState)
    
    # Time-stamping
    last_update_time: float = field(default_factory=time.time)


@dataclass
class SOERecord:
    """Sequence of Events record."""
    timestamp: float
    node_id: str
    event_type: str  # BREAKER_TRIP, BREAKER_CLOSE, ALARM, PROTECTION_PICKUP, etc.
    description: str
    value: Optional[float] = None


class BaseNode:
    """
    Base RTU node implementation.
    
    Provides common infrastructure for all node types.
    """
    
    def __init__(
        self,
        node_id: str,
        node_type: str,
        rated_voltage_kv: float,
        rated_current_a: float,
    ):
        """
        Initialize base node.
        
        Args:
            node_id: Unique node identifier (e.g., "GEN-001", "SUB-003")
            node_type: Node type ("GENERATION", "SUBSTATION", "DISTRIBUTION")
            rated_voltage_kv: Rated voltage in kV
            rated_current_a: Rated current in amperes
        """
        self.node_id = node_id
        self.node_type = node_type
        self.rated_voltage_kv = rated_voltage_kv
        self.rated_current_a = rated_current_a
        
        # Electrical state
        self.state = ElectricalState()
        
        # Modbus data stores
        # Coils (0x references) - 10000 addresses
        self.coils = [False] * 10000
        
        # Discrete inputs (1x references) - 10000 addresses
        self.discrete_inputs = [False] * 10000
        
        # Input registers (3x references) - 10000 addresses
        self.input_registers = [0] * 10000
        
        # Holding registers (4x references) - 50000 addresses
        self.holding_registers = [0] * 50000
        
        # Data quality management
        self.data_quality = DataQualityManager()
        
        # Initialize all analog registers with GOOD quality
        for addr in range(3000, 5000):  # Analog registers range
            self.data_quality.set_quality(addr, DataQuality.GOOD)
        
        # Protection relay (if applicable)
        self.protection: Optional[ProtectionRelay] = None
        
        # IEC 104 server (optional SCADA protocol alongside Modbus)
        self.iec104_server: Optional[IEC104Server] = None
        self.iec104_port: int = 2404 + self._get_port_offset()
        
        # SOE buffer
        self.soe_buffer: List[SOERecord] = []
        self.max_soe_records = 1000
        
        # Simulation time tracking
        self.simulation_time: float = 0.0
        
        # Statistics
        self.stats = {
            "updates_total": 0,
            "breaker_operations": 0,
            "protection_trips": 0,
            "soe_events": 0,
        }
        
        logger.info(
            f"Node {node_id} initialized - Type: {node_type}, "
            f"V_rated: {rated_voltage_kv}kV, I_rated: {rated_current_a}A"
        )
    
    def update_electrical_state(
        self,
        voltage_kv: Optional[float] = None,
        voltage_angle_deg: Optional[float] = None,
        current_a: Optional[float] = None,
        p_mw: Optional[float] = None,
        q_mvar: Optional[float] = None,
        frequency_hz: Optional[float] = None,
        dt: float = 0.1,
    ):
        """
        Update electrical measurements.
        
        This is called by the grid simulator after each power flow update.
        
        Args:
            voltage_kv: Bus voltage in kV
            voltage_angle_deg: Voltage angle in degrees
            current_a: Line current in amperes
            p_mw: Active power in MW
            q_mvar: Reactive power in MVAr
            frequency_hz: System frequency in Hz
            dt: Time step in seconds (default 0.1s = 100ms)
        """
        # Advance simulation time
        self.simulation_time += dt
        
        # Update state
        if voltage_kv is not None:
            self.state.voltage_kv = voltage_kv
            self.state.voltage_pu = voltage_kv / self.rated_voltage_kv
        
        if voltage_angle_deg is not None:
            self.state.voltage_angle_deg = voltage_angle_deg
        
        if current_a is not None:
            self.state.current_a = current_a
            self.state.current_pu = current_a / self.rated_current_a
        
        if p_mw is not None:
            self.state.p_mw = p_mw
        
        if q_mvar is not None:
            self.state.q_mvar = q_mvar
        
        if p_mw is not None and q_mvar is not None:
            self.state.s_mva = (p_mw**2 + q_mvar**2)**0.5
            if self.state.s_mva > 0:
                self.state.power_factor = abs(p_mw) / self.state.s_mva
        
        if frequency_hz is not None:
            self.state.frequency_hz = frequency_hz
        
        self.state.last_update_time = time.time()
        self.stats["updates_total"] += 1
        
        # Update data quality based on measurements
        self._update_data_quality()
        
        # Update protection relay if enabled
        if self.protection and self.state.protection_enabled:
            self._update_protection(dt)
    
    def _update_data_quality(self):
        """Update data quality flags based on measurement validity."""
        # Check voltage range
        if self.state.voltage_kv > 0:
            v_pu = self.state.voltage_pu
            
            if v_pu > 1.2:  # > 120%
                self.data_quality.set_quality(3000, DataQuality.OVERFLOW)
            elif v_pu < 0.8:  # < 80%
                self.data_quality.set_quality(3000, DataQuality.UNDERRANGE)
            else:
                self.data_quality.set_quality(3000, DataQuality.GOOD)
        
        # Check current range
        if self.state.current_a > 0:
            i_pu = self.state.current_pu
            
            if i_pu > 1.5:  # > 150%
                self.data_quality.set_quality(3001, DataQuality.OVERFLOW)
            else:
                self.data_quality.set_quality(3001, DataQuality.GOOD)
        
        # Check frequency range
        freq = self.state.frequency_hz
        if not (49.0 <= freq <= 51.0):
            self.data_quality.set_quality(3003, DataQuality.BAD)
        else:
            self.data_quality.set_quality(3003, DataQuality.GOOD)
    
    def _update_protection(self, dt: float):
        """Update protection relay and handle trips."""
        if not self.protection:
            return
        
        # Check trip state before update
        was_tripped = self.protection.state.tripped
        
        # Update protection
        self.protection.update(
            current_time=self.simulation_time,
            dt=dt,
            line_current_a=self.state.current_a,
            bus_voltage_kv=self.state.voltage_kv,
            frequency_hz=self.state.frequency_hz,
        )
        
        # Check for new trip
        if self.protection.state.tripped and not was_tripped:
            self._handle_protection_trip()
        
        # Update protection state in node
        self.state.protection_state = self.protection.state
    
    def _handle_protection_trip(self):
        """Handle protection relay trip."""
        logger.warning(f"{self.node_id} - PROTECTION TRIP!")
        
        # Open breaker
        self.open_breaker(reason="PROTECTION_TRIP")
        
        self.stats["protection_trips"] += 1
        
        # Record SOE
        self.record_soe(
            event_type="PROTECTION_TRIP",
            description=f"Protection trip: {self.protection.state.trip_reason.value}",
        )
    
    def open_breaker(self, reason: str = "COMMAND"):
        """
        Open circuit breaker.
        
        Args:
            reason: Reason for opening (COMMAND, PROTECTION_TRIP, etc.)
        """
        if not self.state.breaker_52_closed:
            return  # Already open
        
        logger.info(f"{self.node_id} - Opening breaker (reason: {reason})")
        
        self.state.breaker_52_closed = False
        self.state.breaker_52_position = "OPEN"
        
        # Update Modbus coil
        self.coils[0] = False  # Breaker status coil
        
        self.stats["breaker_operations"] += 1
        
        # Record SOE
        self.record_soe(
            event_type="BREAKER_OPEN",
            description=f"Breaker opened: {reason}",
        )
    
    def close_breaker(self, reason: str = "COMMAND"):
        """
        Close circuit breaker.
        
        Args:
            reason: Reason for closing
        """
        if self.state.breaker_52_closed:
            return  # Already closed
        
        logger.info(f"{self.node_id} - Closing breaker (reason: {reason})")
        
        self.state.breaker_52_closed = True
        self.state.breaker_52_position = "CLOSED"
        
        # Update Modbus coil
        self.coils[0] = True  # Breaker status coil
        
        self.stats["breaker_operations"] += 1
        
        # Record SOE
        self.record_soe(
            event_type="BREAKER_CLOSE",
            description=f"Breaker closed: {reason}",
        )
    
    def record_soe(
        self,
        event_type: str,
        description: str,
        value: Optional[float] = None,
    ):
        """
        Record Sequence of Events.
        
        Args:
            event_type: Event type identifier
            description: Human-readable description
            value: Optional numerical value
        """
        record = SOERecord(
            timestamp=time.time(),
            node_id=self.node_id,
            event_type=event_type,
            description=description,
            value=value,
        )
        
        self.soe_buffer.append(record)
        
        # Trim buffer if needed
        if len(self.soe_buffer) > self.max_soe_records:
            self.soe_buffer = self.soe_buffer[-self.max_soe_records:]
        
        self.stats["soe_events"] += 1
        
        logger.info(f"SOE: {self.node_id} - {event_type}: {description}")
    
    def get_soe_records(self, count: int = 100) -> List[SOERecord]:
        """
        Get recent SOE records.
        
        Args:
            count: Maximum number of records to return
        
        Returns:
            List of SOE records (most recent first)
        """
        return list(reversed(self.soe_buffer[-count:]))
    
    # Modbus interface methods
    
    def read_coils(self, address: int, count: int) -> List[bool]:
        """Read coils (FC01)."""
        return self.coils[address:address+count]
    
    def read_discrete_inputs(self, address: int, count: int) -> List[bool]:
        """Read discrete inputs (FC02)."""
        return self.discrete_inputs[address:address+count]
    
    def read_input_registers(self, address: int, count: int) -> List[int]:
        """Read input registers (FC04)."""
        return self.input_registers[address:address+count]
    
    def read_holding_registers(self, address: int, count: int) -> List[int]:
        """Read holding registers (FC03)."""
        return self.holding_registers[address:address+count]
    
    def write_coil(self, address: int, value: bool):
        """Write single coil (FC05)."""
        self.coils[address] = value
        
        # Handle special coils
        if address == 0:  # Breaker control
            if value:
                self.close_breaker(reason="MODBUS_COMMAND")
            else:
                self.open_breaker(reason="MODBUS_COMMAND")
    
    def write_holding_register(self, address: int, value: int):
        """Write single holding register (FC06)."""
        self.holding_registers[address] = value
        
        # Node-specific handling in subclasses
    
    def write_holding_registers(self, address: int, values: List[int]):
        """Write multiple holding registers (FC16)."""
        for i, value in enumerate(values):
            self.write_holding_register(address + i, value)
    
    def _get_port_offset(self) -> int:
        """
        Calculate unique port offset based on node_id and type
        
        Used to give each node a unique IEC 104 port base (2404 + offset)
        E.g., GEN-001 -> 2404+10, SUB-001 -> 2404+110, DIST-001 -> 2404+210
        """
        try:
            # Get type multiplier
            type_mult = 0
            if "GEN" in self.node_id:
                type_mult = 0
            elif "SUB" in self.node_id:
                type_mult = 100
            elif "DIST" in self.node_id:
                type_mult = 200
            
            # Extract trailing digits from node_id
            num_str = ''.join(c for c in self.node_id if c.isdigit())
            if num_str:
                return type_mult + int(num_str) * 10
        except:
            pass
        return 1  # Default offset if parsing fails
    
    async def start_iec104_server(self, host: str = '0.0.0.0',
                                 port: Optional[int] = None) -> bool:
        """
        Start IEC 104 SCADA protocol server on this node
        
        Args:
            host: Bind address (default all interfaces)
            port: TCP port (default auto-calculated from node_id)
        
        Returns:
            True if server started successfully, False otherwise
        """
        if self.iec104_server is not None:
            logger.warning(f"{self.node_id}: IEC 104 server already running")
            return False
        
        try:
            # Create server instance
            port = port or self.iec104_port
            self.iec104_server = IEC104Server(
                host=host,
                port=port,
                parent_node=self
            )
            
            # Start server
            await self.iec104_server.start()
            logger.info(f"{self.node_id}: IEC 104 server started on port {port}")
            
            # Register callbacks for control commands
            # Coil 0 = breaker control
            self.iec104_server.register_control_callback(
                100,  # IOA 100 = breaker control
                self._handle_iec104_breaker_command
            )
            
            return True
        
        except Exception as e:
            logger.error(f"{self.node_id}: Failed to start IEC 104 server: {e}")
            self.iec104_server = None
            return False
    
    async def stop_iec104_server(self) -> bool:
        """Stop IEC 104 server"""
        if self.iec104_server is None:
            return False
        
        try:
            await self.iec104_server.stop()
            self.iec104_server = None
            logger.info(f"{self.node_id}: IEC 104 server stopped")
            return True
        except Exception as e:
            logger.error(f"{self.node_id}: Error stopping IEC 104 server: {e}")
            return False
    
    async def send_iec104_measurement(self, information_object_address: int,
                                     value: float, quality: int = 0x00):
        """Send measurement via IEC 104"""
        if self.iec104_server is None:
            return
        
        from protocols.iec104.messages import TypeID
        await self.iec104_server.send_measurement(
            information_object_address,
            value,
            type_id=TypeID.M_ME_NC_1,  # 32-bit floating point
            quality=quality
        )
    
    def _handle_iec104_breaker_command(self, value: float):
        """Handle breaker control command received via IEC 104"""
        if value:
            self.close_breaker(reason="IEC104_COMMAND")
        else:
            self.open_breaker(reason="IEC104_COMMAND")
    
    def get_stats(self) -> Dict:
        """Get node statistics."""
        stats = self.stats.copy()
        stats["state"] = {
            "voltage_kv": self.state.voltage_kv,
            "current_a": self.state.current_a,
            "frequency_hz": self.state.frequency_hz,
            "breaker_closed": self.state.breaker_52_closed,
        }
        return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n===== BASE NODE TEST =====\n")
    
    # Create test node
    node = BaseNode(
        node_id="TEST-001",
        node_type="SUBSTATION",
        rated_voltage_kv=400.0,
        rated_current_a=1000.0,
    )
    
    print(f"Node created: {node.node_id}")
    print(f"Rated: {node.rated_voltage_kv}kV, {node.rated_current_a}A\n")
    
    # Test 1: Update electrical state
    print("Test 1: Update electrical state")
    node.update_electrical_state(
        voltage_kv=400.0,
        voltage_angle_deg=0.0,
        current_a=500.0,
        p_mw=346.4,  # sqrt(3) * V * I * pf for 3-phase
        q_mvar=0.0,
        frequency_hz=50.0,
    )
    
    print(f"  Voltage: {node.state.voltage_kv:.1f} kV ({node.state.voltage_pu:.3f} pu)")
    print(f"  Current: {node.state.current_a:.1f} A ({node.state.current_pu:.3f} pu)")
    print(f"  Power: {node.state.p_mw:.1f} MW")
    print(f"  Frequency: {node.state.frequency_hz:.3f} Hz")
    
    # Test 2: Breaker operations
    print("\nTest 2: Breaker operations")
    print(f"  Initial state: {'CLOSED' if node.state.breaker_52_closed else 'OPEN'}")
    
    node.open_breaker(reason="TEST")
    print(f"  After open: {'CLOSED' if node.state.breaker_52_closed else 'OPEN'}")
    
    node.close_breaker(reason="TEST")
    print(f"  After close: {'CLOSED' if node.state.breaker_52_closed else 'OPEN'}")
    
    # Test 3: SOE recording
    print("\nTest 3: SOE recording")
    node.record_soe("TEST_EVENT", "Manual test event", value=123.45)
    
    soe_records = node.get_soe_records(count=5)
    print(f"  Total SOE records: {len(node.soe_buffer)}")
    print(f"  Recent events:")
    for record in soe_records:
        print(f"    {record.event_type}: {record.description}")
    
    # Test 4: Modbus interface
    print("\nTest 4: Modbus interface")
    
    # Write holding register
    node.write_holding_register(4000, 12345)
    
    # Read it back
    values = node.read_holding_registers(4000, 1)
    print(f"  Wrote 12345 to register 4000, read back: {values[0]}")
    
    # Write coil (breaker control)
    node.write_coil(0, False)  # Open breaker
    print(f"  Wrote False to coil 0 (breaker), state: {'CLOSED' if node.state.breaker_52_closed else 'OPEN'}")
    
    # Test 5: Statistics
    print("\nTest 5: Statistics")
    stats = node.get_stats()
    print(f"  Updates: {stats['updates_total']}")
    print(f"  Breaker operations: {stats['breaker_operations']}")
    print(f"  SOE events: {stats['soe_events']}")
    
    print("\n✅ Base node test complete\n")
