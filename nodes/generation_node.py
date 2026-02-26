"""
Generation Node
===============

RTU node for generator stations (coal, hydro, solar).

Extends BaseNode with generation-specific functionality:
    - Governor control (MW setpoint)
    - Automatic Voltage Regulator (AVR) control (kV setpoint)
    - Generator protection (ANSI 32, 40, 46, 87G)
    - Synchronization status
    - Fuel/resource status

Real generator RTUs have specialized control systems for:
    - Active power control (governor droop + setpoint)
    - Reactive power/voltage control (AVR)
    - Synchronization to grid
    - Protection specific to rotating machinery

This implementation mirrors that architecture.
"""

import time
from typing import Dict, Optional
import logging
import sys

# Support standalone testing
if __name__ == "__main__":
    sys.path.insert(0, '/home/nirmalya/Desktop/SCADA_SIM')

from nodes.base_node import BaseNode, ElectricalState
from electrical.protection import ProtectionRelay
from protocols.modbus.register_map import (
    ModbusRegisterMap,
    encode_voltage_kv,
    encode_current_a,
    encode_power_mw,
    encode_frequency_hz,
)
from config import GENERATOR_CONFIG

logger = logging.getLogger(__name__)


class GenerationNode(BaseNode):
    """
    Generator station RTU node.
    
    Adds governor and AVR control on top of BaseNode.
    """
    
    def __init__(
        self,
        node_id: str,
        generator_type: str,  # "COAL", "HYDRO", "SOLAR"
        rated_mw: float,
        rated_voltage_kv: float,
    ):
        """
        Initialize generation node.
        
        Args:
            node_id: Node identifier (e.g., "GEN-001")
            generator_type: Type of generator
            rated_mw: Rated power output in MW
            rated_voltage_kv: Rated terminal voltage in kV
        """
        # Calculate rated current from MVA rating
        # For generators: MVA = sqrt(3) * kV * I / 1000
        # Assume power factor ~0.9, so MVA = MW / 0.9
        rated_mva = rated_mw / 0.9
        rated_current_a = (rated_mva * 1000) / (1.732 * rated_voltage_kv)
        
        super().__init__(
            node_id=node_id,
            node_type="GENERATION",
            rated_voltage_kv=rated_voltage_kv,
            rated_current_a=rated_current_a,
        )
        
        self.generator_type = generator_type
        self.rated_mw = rated_mw
        
        # Generator-specific state
        self.governor_setpoint_mw = 0.0
        self.governor_mode = "AUTO"  # AUTO or MANUAL
        
        self.avr_setpoint_kv = rated_voltage_kv
        self.avr_mode = "AUTO"  # AUTO or MANUAL
        
        self.synchronized = False
        self.sync_check_voltage_diff = 0.0  # kV
        self.sync_check_angle_diff = 0.0    # degrees
        
        # Fuel/resource status
        self.fuel_available = True  # For coal
        self.water_available = True  # For hydro
        self.irradiance_w_m2 = 0.0  # For solar
        
        # Generator electrical output
        self.generator_p_mw = 0.0
        self.generator_q_mvar = 0.0
        
        # Initialize protection relay
        self.protection = ProtectionRelay(
            node_name=node_id,
            rated_current_a=rated_current_a,
            rated_voltage_kv=rated_voltage_kv,
        )
        
        # Initialize Modbus registers
        self._initialize_modbus_registers()
        
        logger.info(
            f"Generation node {node_id} initialized - "
            f"Type: {generator_type}, Rated: {rated_mw}MW, {rated_voltage_kv}kV"
        )
    
    def _initialize_modbus_registers(self):
        """Initialize generation-specific Modbus registers."""
        reg_map = ModbusRegisterMap.get_register_map("GENERATION")
        
        # Initialize holding registers (setpoints)
        self.holding_registers[reg_map["governor_setpoint_mw"]] = encode_power_mw(0.0)
        self.holding_registers[reg_map["avr_setpoint_kv"]] = encode_voltage_kv(self.rated_voltage_kv)
        
        # Initialize discrete inputs (status)
        discrete_map = ModbusRegisterMap.get_discrete_inputs("GENERATION")
        self.discrete_inputs[discrete_map["generator_breaker_status"]] = self.state.breaker_52_closed
        self.discrete_inputs[discrete_map["sync_status"]] = False
        self.discrete_inputs[discrete_map["governor_mode"]] = (self.governor_mode == "AUTO")
        self.discrete_inputs[discrete_map["avr_mode"]] = (self.avr_mode == "AUTO")
        
        # Initialize coils (controls)
        coil_map = ModbusRegisterMap.get_coils("GENERATION")
        self.coils[coil_map["governor_auto_mode"]] = True
        self.coils[coil_map["avr_auto_mode"]] = True
    
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
        Update electrical state and refresh Modbus registers.
        
        For generators, p_mw and q_mvar represent bus injection.
        The generator output is calculated based on governor/AVR control.
        """
        # Call base class update
        super().update_electrical_state(
            voltage_kv=voltage_kv,
            voltage_angle_deg=voltage_angle_deg,
            current_a=current_a,
            p_mw=p_mw,
            q_mvar=q_mvar,
            frequency_hz=frequency_hz,
            dt=dt,
        )
        
        # Update generator output (same as bus injection for generator nodes)
        if p_mw is not None:
            self.generator_p_mw = p_mw
        if q_mvar is not None:
            self.generator_q_mvar = q_mvar
        
        # Update Modbus registers
        self._update_modbus_registers()
    
    def _update_modbus_registers(self):
        """Update Modbus registers with current state."""
        reg_map = ModbusRegisterMap.get_register_map("GENERATION")
        
        # Update input registers (measurements)
        self.input_registers[reg_map["bus_voltage_kv"]] = encode_voltage_kv(self.state.voltage_kv)
        self.input_registers[reg_map["frequency_hz"]] = encode_frequency_hz(self.state.frequency_hz)
        self.input_registers[reg_map["active_power_mw"]] = encode_power_mw(self.state.p_mw)
        self.input_registers[reg_map["reactive_power_mvar"]] = encode_power_mw(self.state.q_mvar)
        self.input_registers[reg_map["generator_mw"]] = encode_power_mw(self.generator_p_mw)
        self.input_registers[reg_map["generator_mvar"]] = encode_power_mw(self.generator_q_mvar)
        
        # Update discrete inputs (status)
        discrete_map = ModbusRegisterMap.get_discrete_inputs("GENERATION")
        self.discrete_inputs[discrete_map["generator_breaker_status"]] = self.state.breaker_52_closed
        self.discrete_inputs[discrete_map["sync_status"]] = self.synchronized
        self.discrete_inputs[discrete_map["governor_mode"]] = (self.governor_mode == "AUTO")
        self.discrete_inputs[discrete_map["avr_mode"]] = (self.avr_mode == "AUTO")
    
    def write_holding_register(self, address: int, value: int):
        """
        Handle writes to holding registers (setpoints).
        
        Args:
            address: Register address
            value: Register value (16-bit)
        """
        # Call base class
        super().write_holding_register(address, value)
        
        reg_map = ModbusRegisterMap.get_register_map("GENERATION")
        
        # Governor setpoint
        if address == reg_map["governor_setpoint_mw"]:
            from protocols.modbus.register_map import decode_power_mw
            new_setpoint = decode_power_mw(value)
            
            # Validate range
            if 0.0 <= new_setpoint <= self.rated_mw:
                old_setpoint = self.governor_setpoint_mw
                self.governor_setpoint_mw = new_setpoint
                
                logger.info(
                    f"{self.node_id} - Governor setpoint changed: "
                    f"{old_setpoint:.1f} → {new_setpoint:.1f} MW"
                )
                
                self.record_soe(
                    "GOVERNOR_SETPOINT_CHANGE",
                    f"Governor setpoint: {new_setpoint:.1f} MW",
                    value=new_setpoint,
                )
            else:
                logger.warning(
                    f"{self.node_id} - Governor setpoint out of range: "
                    f"{new_setpoint:.1f} MW (max: {self.rated_mw:.1f} MW)"
                )
        
        # AVR setpoint
        elif address == reg_map["avr_setpoint_kv"]:
            from protocols.modbus.register_map import decode_voltage_kv
            new_setpoint = decode_voltage_kv(value)
            
            # Validate range (±10% of rated)
            min_v = self.rated_voltage_kv * 0.9
            max_v = self.rated_voltage_kv * 1.1
            
            if min_v <= new_setpoint <= max_v:
                old_setpoint = self.avr_setpoint_kv
                self.avr_setpoint_kv = new_setpoint
                
                logger.info(
                    f"{self.node_id} - AVR setpoint changed: "
                    f"{old_setpoint:.1f} → {new_setpoint:.1f} kV"
                )
                
                self.record_soe(
                    "AVR_SETPOINT_CHANGE",
                    f"AVR setpoint: {new_setpoint:.1f} kV",
                    value=new_setpoint,
                )
            else:
                logger.warning(
                    f"{self.node_id} - AVR setpoint out of range: "
                    f"{new_setpoint:.1f} kV (range: {min_v:.1f}-{max_v:.1f} kV)"
                )
    
    def write_coil(self, address: int, value: bool):
        """
        Handle writes to coils (controls).
        
        Args:
            address: Coil address
            value: Coil value (True/False)
        """
        # Call base class (handles breaker control)
        super().write_coil(address, value)
        
        coil_map = ModbusRegisterMap.get_coils("GENERATION")
        
        # Governor mode control
        if address == coil_map["governor_auto_mode"]:
            new_mode = "AUTO" if value else "MANUAL"
            if new_mode != self.governor_mode:
                self.governor_mode = new_mode
                logger.info(f"{self.node_id} - Governor mode: {new_mode}")
                self.record_soe("GOVERNOR_MODE_CHANGE", f"Governor mode: {new_mode}")
        
        # AVR mode control
        elif address == coil_map["avr_auto_mode"]:
            new_mode = "AUTO" if value else "MANUAL"
            if new_mode != self.avr_mode:
                self.avr_mode = new_mode
                logger.info(f"{self.node_id} - AVR mode: {new_mode}")
                self.record_soe("AVR_MODE_CHANGE", f"AVR mode: {new_mode}")
    
    def check_synchronization(self, grid_voltage_kv: float, grid_angle_deg: float):
        """
        Check if generator can be synchronized to grid.
        
        Args:
            grid_voltage_kv: Grid voltage in kV
            grid_angle_deg: Grid voltage angle in degrees
        
        Returns:
            True if synchronization OK
        """
        # Calculate differences
        self.sync_check_voltage_diff = abs(self.state.voltage_kv - grid_voltage_kv)
        self.sync_check_angle_diff = abs(self.state.voltage_angle_deg - grid_angle_deg)
        
        # Synchronization limits
        max_voltage_diff = 0.05 * self.rated_voltage_kv  # 5%
        max_angle_diff = 10.0  # degrees
        
        sync_ok = (
            self.sync_check_voltage_diff < max_voltage_diff and
            self.sync_check_angle_diff < max_angle_diff
        )
        
        if sync_ok and not self.synchronized:
            self.synchronized = True
            logger.info(f"{self.node_id} - Synchronized to grid")
            self.record_soe("SYNCHRONIZED", "Generator synchronized to grid")
        elif not sync_ok and self.synchronized:
            self.synchronized = False
            logger.warning(f"{self.node_id} - Lost synchronization")
            self.record_soe("SYNC_LOST", "Lost synchronization")
        
        return sync_ok
    
    def get_stats(self) -> Dict:
        """Get generation node statistics."""
        stats = super().get_stats()
        stats["generation"] = {
            "type": self.generator_type,
            "rated_mw": self.rated_mw,
            "governor_setpoint_mw": self.governor_setpoint_mw,
            "governor_mode": self.governor_mode,
            "avr_setpoint_kv": self.avr_setpoint_kv,
            "avr_mode": self.avr_mode,
            "generator_p_mw": self.generator_p_mw,
            "generator_q_mvar": self.generator_q_mvar,
            "synchronized": self.synchronized,
        }
        return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n===== GENERATION NODE TEST =====\n")
    
    # Create coal generator node
    gen = GenerationNode(
        node_id="GEN-001",
        generator_type="COAL",
        rated_mw=500.0,
        rated_voltage_kv=22.0,
    )
    
    print(f"Generator created: {gen.node_id}")
    print(f"Type: {gen.generator_type}, Rated: {gen.rated_mw}MW, {gen.rated_voltage_kv}kV")
    print(f"Rated current: {gen.rated_current_a:.1f}A\n")
    
    # Test 1: Update electrical state
    print("Test 1: Update electrical state")
    gen.update_electrical_state(
        voltage_kv=22.0,
        voltage_angle_deg=5.0,
        current_a=10000.0,
        p_mw=350.0,
        q_mvar=50.0,
        frequency_hz=50.0,
    )
    
    print(f"  Voltage: {gen.state.voltage_kv:.1f} kV")
    print(f"  Generator output: {gen.generator_p_mw:.1f} MW, {gen.generator_q_mvar:.1f} MVAr")
    print(f"  Frequency: {gen.state.frequency_hz:.3f} Hz")
    
    # Test 2: Governor setpoint change
    print("\nTest 2: Governor setpoint change")
    from protocols.modbus.register_map import encode_power_mw, ModbusRegisterMap
    
    reg_map = ModbusRegisterMap.get_register_map("GENERATION")
    gov_addr = reg_map["governor_setpoint_mw"]
    
    print(f"  Initial setpoint: {gen.governor_setpoint_mw:.1f} MW")
    gen.write_holding_register(gov_addr, encode_power_mw(400.0))
    print(f"  New setpoint: {gen.governor_setpoint_mw:.1f} MW")
    
    # Test 3: AVR setpoint change
    print("\nTest 3: AVR setpoint change")
    avr_addr = reg_map["avr_setpoint_kv"]
    
    print(f"  Initial AVR setpoint: {gen.avr_setpoint_kv:.1f} kV")
    gen.write_holding_register(avr_addr, encode_voltage_kv(22.5))
    print(f"  New AVR setpoint: {gen.avr_setpoint_kv:.1f} kV")
    
    # Test 4: Mode changes
    print("\nTest 4: Control mode changes")
    coil_map = ModbusRegisterMap.get_coils("GENERATION")
    
    print(f"  Initial governor mode: {gen.governor_mode}")
    gen.write_coil(coil_map["governor_auto_mode"], False)
    print(f"  After coil write: {gen.governor_mode}")
    
    # Test 5: Synchronization check
    print("\nTest 5: Synchronization check")
    grid_v = 22.0
    grid_angle = 5.2
    
    sync_ok = gen.check_synchronization(grid_v, grid_angle)
    print(f"  Grid: {grid_v:.1f}kV ∠{grid_angle:.1f}°")
    print(f"  Gen:  {gen.state.voltage_kv:.1f}kV ∠{gen.state.voltage_angle_deg:.1f}°")
    print(f"  ΔV = {gen.sync_check_voltage_diff:.3f} kV, Δθ = {gen.sync_check_angle_diff:.1f}°")
    print(f"  Synchronized: {gen.synchronized}")
    
    # Test 6: SOE records
    print("\nTest 6: SOE records")
    soe = gen.get_soe_records(count=5)
    print(f"  Total SOE events: {len(gen.soe_buffer)}")
    for record in soe[:3]:
        print(f"    {record.event_type}: {record.description}")
    
    # Test 7: Statistics
    print("\nTest 7: Statistics")
    stats = gen.get_stats()
    print(f"  Generator type: {stats['generation']['type']}")
    print(f"  Governor setpoint: {stats['generation']['governor_setpoint_mw']:.1f} MW")
    print(f"  AVR setpoint: {stats['generation']['avr_setpoint_kv']:.1f} kV")
    print(f"  Synchronized: {stats['generation']['synchronized']}")
    
    print("\n✅ Generation node test complete\n")
