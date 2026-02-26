"""
Substation Node
===============

RTU node for transmission substations.

Extends BaseNode with substation-specific functionality:
    - Transformer thermal monitoring (IEC 60076-7)
    - On-Load Tap Changer (OLTC) control
    - Bus differential protection (ANSI 87B)
    - Multiple transformer monitoring
    - Reactive power compensation

Real substation RTUs monitor complex equipment:
    - Power transformers with thermal models
    - OLTC for voltage regulation
    - Bus protection schemes
    - Capacitor banks for reactive power control

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
from electrical.thermal_model import TransformerThermalModel
from protocols.modbus.register_map import (
    ModbusRegisterMap,
    encode_voltage_kv,
    encode_current_a,
    encode_power_mw,
    encode_frequency_hz,
    encode_temperature_celsius,
)
from config import TRANSFORMER_CONFIG

logger = logging.getLogger(__name__)


class SubstationNode(BaseNode):
    """
    Transmission substation RTU node.
    
    Adds transformer thermal and OLTC control on top of BaseNode.
    """
    
    def __init__(
        self,
        node_id: str,
        transformer_mva: float,
        primary_voltage_kv: float,
        secondary_voltage_kv: float,
    ):
        """
        Initialize substation node.
        
        Args:
            node_id: Node identifier (e.g., "SUB-001")
            transformer_mva: Transformer MVA rating
            primary_voltage_kv: Primary winding voltage in kV
            secondary_voltage_kv: Secondary winding voltage in kV
        """
        # Calculate rated current from transformer MVA
        # I = MVA / (sqrt(3) * kV)
        rated_current_a = (transformer_mva * 1000) / (1.732 * secondary_voltage_kv)
        
        super().__init__(
            node_id=node_id,
            node_type="SUBSTATION",
            rated_voltage_kv=secondary_voltage_kv,
            rated_current_a=rated_current_a,
        )
        
        self.transformer_mva = transformer_mva
        self.primary_voltage_kv = primary_voltage_kv
        self.secondary_voltage_kv = secondary_voltage_kv
        
        # Transformer thermal model
        self.thermal_model = TransformerThermalModel(
            node_name=node_id,
        )
        
        # OLTC state
        self.oltc_tap_position = 0  # -16 to +16 (neutral = 0)
        self.oltc_tap_range = 16
        self.oltc_volts_per_tap = secondary_voltage_kv * 0.00625  # 0.625% per tap
        self.oltc_auto_mode = True
        self.oltc_target_voltage_kv = secondary_voltage_kv
        
        # Transformer loading
        self.transformer_load_mva = 0.0
        self.transformer_load_percent = 0.0
        
        # Bus voltages
        self.primary_bus_voltage_kv = 0.0
        self.secondary_bus_voltage_kv = 0.0
        
        # Initialize protection relay
        self.protection = ProtectionRelay(
            node_name=node_id,
            rated_current_a=rated_current_a,
            rated_voltage_kv=secondary_voltage_kv,
        )
        
        # Initialize Modbus registers
        self._initialize_modbus_registers()
        
        logger.info(
            f"Substation node {node_id} initialized - "
            f"Transformer: {transformer_mva}MVA, {primary_voltage_kv}/{secondary_voltage_kv}kV"
        )
    
    def _initialize_modbus_registers(self):
        """Initialize substation-specific Modbus registers."""
        reg_map = ModbusRegisterMap.get_register_map("TRANSMISSION")
        
        # Initialize input registers (transformer thermal)
        self.input_registers[reg_map["transformer_oil_temp_c"]] = encode_temperature_celsius(35.0)
        self.input_registers[reg_map["transformer_hotspot_temp_c"]] = encode_temperature_celsius(40.0)
        self.input_registers[reg_map["transformer_load_percent"]] = 0
        self.input_registers[reg_map["oltc_tap_position"]] = 0
        
        # Initialize holding registers (setpoints)
        self.holding_registers[reg_map["oltc_target_voltage_kv"]] = encode_voltage_kv(self.secondary_voltage_kv)
        
        # Initialize discrete inputs (status)
        discrete_map = ModbusRegisterMap.get_discrete_inputs("TRANSMISSION")
        self.discrete_inputs[discrete_map["transformer_breaker_hv_status"]] = self.state.breaker_52_closed
        self.discrete_inputs[discrete_map["transformer_breaker_lv_status"]] = self.state.breaker_52_closed
        self.discrete_inputs[discrete_map["oltc_auto_mode"]] = self.oltc_auto_mode
        self.discrete_inputs[discrete_map["thermal_alarm"]] = False
        
        # Initialize coils (controls)
        coil_map = ModbusRegisterMap.get_coils("TRANSMISSION")
        self.coils[coil_map["oltc_auto_enable"]] = True
        self.coils[coil_map["oltc_raise"]] = False
        self.coils[coil_map["oltc_lower"]] = False
    
    def update_electrical_state(
        self,
        voltage_kv: Optional[float] = None,
        voltage_angle_deg: Optional[float] = None,
        current_a: Optional[float] = None,
        p_mw: Optional[float] = None,
        q_mvar: Optional[float] = None,
        frequency_hz: Optional[float] = None,
        primary_voltage_kv: Optional[float] = None,
        dt: float = 0.1,
    ):
        """
        Update electrical state and thermal model.
        
        Args:
            voltage_kv: Secondary bus voltage in kV
            voltage_angle_deg: Voltage angle in degrees
            current_a: Transformer current in amperes
            p_mw: Active power through transformer in MW
            q_mvar: Reactive power in MVAr
            frequency_hz: System frequency in Hz
            primary_voltage_kv: Primary bus voltage in kV
            dt: Time step in seconds
        """
        # Call base class update
        super().update_electrical_state(
            voltage_kv=voltage_kv,
            voltage_angle_deg=voltage_angle_deg,
            current_a=current_a,
            p_mw=p_mw,
            q_mvar=q_mvar,
            frequency_hz=frequency_hz,
        )
        
        # Update bus voltages
        if voltage_kv is not None:
            self.secondary_bus_voltage_kv = voltage_kv
        if primary_voltage_kv is not None:
            self.primary_bus_voltage_kv = primary_voltage_kv
        
        # Calculate transformer loading
        if p_mw is not None and q_mvar is not None:
            self.transformer_load_mva = (p_mw**2 + q_mvar**2)**0.5
            self.transformer_load_percent = (self.transformer_load_mva / self.transformer_mva) * 100.0
        
        # Update thermal model
        self.thermal_model.update(
            dt=dt,
            loading_mva=self.transformer_load_mva,
        )
        
        # Check for thermal alarm
        if self.thermal_model.state.alarm_active:
            if not self.discrete_inputs[ModbusRegisterMap.get_discrete_inputs("TRANSMISSION")["thermal_alarm"]]:
                logger.warning(
                    f"{self.node_id} - THERMAL ALARM: "
                    f"Oil temp {self.thermal_model.state.theta_oil_c:.1f}°C"
                )
                self.record_soe(
                    "THERMAL_ALARM",
                    f"Transformer thermal alarm: {self.thermal_model.state.theta_oil_c:.1f}°C",
                    value=self.thermal_model.state.theta_oil_c,
                )
        
        # Update OLTC if in auto mode
        if self.oltc_auto_mode:
            self._update_oltc_auto()
        
        # Update Modbus registers
        self._update_modbus_registers()
    
    def _update_oltc_auto(self):
        """Automatic OLTC control to maintain target voltage."""
        if not self.state.breaker_52_closed:
            return  # Don't adjust OLTC with breaker open
        
        voltage_error = self.secondary_bus_voltage_kv - self.oltc_target_voltage_kv
        deadband = 0.01 * self.secondary_voltage_kv  # 1% deadband
        
        # Only adjust if outside deadband
        if abs(voltage_error) > deadband:
            if voltage_error < 0:  # Voltage too low
                if self.oltc_tap_position < self.oltc_tap_range:
                    self._raise_tap()
            else:  # Voltage too high
                if self.oltc_tap_position > -self.oltc_tap_range:
                    self._lower_tap()
    
    def _raise_tap(self):
        """Raise OLTC tap position (increase secondary voltage)."""
        if self.oltc_tap_position < self.oltc_tap_range:
            self.oltc_tap_position += 1
            logger.info(f"{self.node_id} - OLTC tap raised to {self.oltc_tap_position:+d}")
            self.record_soe(
                "OLTC_TAP_RAISE",
                f"OLTC tap raised to {self.oltc_tap_position:+d}",
                value=self.oltc_tap_position,
            )
    
    def _lower_tap(self):
        """Lower OLTC tap position (decrease secondary voltage)."""
        if self.oltc_tap_position > -self.oltc_tap_range:
            self.oltc_tap_position -= 1
            logger.info(f"{self.node_id} - OLTC tap lowered to {self.oltc_tap_position:+d}")
            self.record_soe(
                "OLTC_TAP_LOWER",
                f"OLTC tap lowered to {self.oltc_tap_position:+d}",
                value=self.oltc_tap_position,
            )
    
    def _update_modbus_registers(self):
        """Update Modbus registers with current state."""
        reg_map = ModbusRegisterMap.get_register_map("TRANSMISSION")
        
        # Update input registers (measurements)
        self.input_registers[reg_map["bus_voltage_kv"]] = encode_voltage_kv(self.secondary_bus_voltage_kv)
        self.input_registers[reg_map["frequency_hz"]] = encode_frequency_hz(self.state.frequency_hz)
        self.input_registers[reg_map["active_power_mw"]] = encode_power_mw(self.state.p_mw)
        self.input_registers[reg_map["reactive_power_mvar"]] = encode_power_mw(self.state.q_mvar)
        
        # Transformer thermal
        self.input_registers[reg_map["transformer_oil_temp_c"]] = encode_temperature_celsius(
            self.thermal_model.state.theta_oil_c
        )
        self.input_registers[reg_map["transformer_hotspot_temp_c"]] = encode_temperature_celsius(
            self.thermal_model.state.theta_hs_c
        )
        self.input_registers[reg_map["transformer_load_percent"]] = int(self.transformer_load_percent)
        self.input_registers[reg_map["oltc_tap_position"]] = self.oltc_tap_position + 100  # Offset for unsigned
        
        # Update discrete inputs (status)
        discrete_map = ModbusRegisterMap.get_discrete_inputs("TRANSMISSION")
        self.discrete_inputs[discrete_map["transformer_breaker_hv_status"]] = self.state.breaker_52_closed
        self.discrete_inputs[discrete_map["transformer_breaker_lv_status"]] = self.state.breaker_52_closed
        self.discrete_inputs[discrete_map["oltc_auto_mode"]] = self.oltc_auto_mode
        self.discrete_inputs[discrete_map["thermal_alarm"]] = self.thermal_model.state.alarm_active
    
    def write_holding_register(self, address: int, value: int):
        """
        Handle writes to holding registers (setpoints).
        
        Args:
            address: Register address
            value: Register value (16-bit)
        """
        # Call base class
        super().write_holding_register(address, value)
        
        reg_map = ModbusRegisterMap.get_register_map("TRANSMISSION")
        
        # OLTC target voltage
        if address == reg_map["oltc_target_voltage_kv"]:
            from protocols.modbus.register_map import decode_voltage_kv
            new_target = decode_voltage_kv(value)
            
            # Validate range (±10% of rated)
            min_v = self.secondary_voltage_kv * 0.9
            max_v = self.secondary_voltage_kv * 1.1
            
            if min_v <= new_target <= max_v:
                old_target = self.oltc_target_voltage_kv
                self.oltc_target_voltage_kv = new_target
                
                logger.info(
                    f"{self.node_id} - OLTC target voltage changed: "
                    f"{old_target:.1f} → {new_target:.1f} kV"
                )
                
                self.record_soe(
                    "OLTC_TARGET_CHANGE",
                    f"OLTC target: {new_target:.1f} kV",
                    value=new_target,
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
        
        coil_map = ModbusRegisterMap.get_coils("TRANSMISSION")
        
        # OLTC auto mode
        if address == coil_map["oltc_auto_enable"]:
            if value != self.oltc_auto_mode:
                self.oltc_auto_mode = value
                mode = "AUTO" if value else "MANUAL"
                logger.info(f"{self.node_id} - OLTC mode: {mode}")
                self.record_soe("OLTC_MODE_CHANGE", f"OLTC mode: {mode}")
        
        # Manual OLTC raise (pulse)
        elif address == coil_map["oltc_raise"]:
            if value and not self.oltc_auto_mode:
                self._raise_tap()
        
        # Manual OLTC lower (pulse)
        elif address == coil_map["oltc_lower"]:
            if value and not self.oltc_auto_mode:
                self._lower_tap()
    
    def get_stats(self) -> Dict:
        """Get substation node statistics."""
        stats = super().get_stats()
        stats["substation"] = {
            "transformer_mva": self.transformer_mva,
            "transformer_load_mva": self.transformer_load_mva,
            "transformer_load_percent": self.transformer_load_percent,
            "oil_temp_c": self.thermal_model.state.theta_oil_c,
            "hotspot_temp_c": self.thermal_model.state.theta_hs_c,
            "thermal_alarm": self.thermal_model.state.alarm_active,
            "oltc_tap_position": self.oltc_tap_position,
            "oltc_auto_mode": self.oltc_auto_mode,
        }
        return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n===== SUBSTATION NODE TEST =====\n")
    
    # Create substation node
    sub = SubstationNode(
        node_id="SUB-001",
        transformer_mva=100.0,
        primary_voltage_kv=400.0,
        secondary_voltage_kv=132.0,
    )
    
    print(f"Substation created: {sub.node_id}")
    print(f"Transformer: {sub.transformer_mva}MVA, {sub.primary_voltage_kv}/{sub.secondary_voltage_kv}kV")
    print(f"Rated current: {sub.rated_current_a:.1f}A\n")
    
    # Test 1: Update electrical state
    print("Test 1: Update electrical state")
    sub.update_electrical_state(
        voltage_kv=132.0,
        voltage_angle_deg=-5.0,
        current_a=400.0,
        p_mw=80.0,
        q_mvar=20.0,
        frequency_hz=50.0,
        primary_voltage_kv=400.0,
        dt=60.0,  # 1 minute
    )
    
    print(f"  Secondary bus: {sub.secondary_bus_voltage_kv:.1f} kV")
    print(f"  Transformer load: {sub.transformer_load_mva:.1f} MVA ({sub.transformer_load_percent:.1f}%)")
    print(f"  Oil temp: {sub.thermal_model.state.theta_oil_c:.1f}°C")
    print(f"  Hotspot temp: {sub.thermal_model.state.theta_hs_c:.1f}°C")
    
    # Test 2: OLTC target voltage change
    print("\nTest 2: OLTC target voltage change")
    from protocols.modbus.register_map import encode_voltage_kv, ModbusRegisterMap
    
    reg_map = ModbusRegisterMap.get_register_map("TRANSMISSION")
    oltc_addr = reg_map["oltc_target_voltage_kv"]
    
    print(f"  Initial target: {sub.oltc_target_voltage_kv:.1f} kV")
    sub.write_holding_register(oltc_addr, encode_voltage_kv(135.0))
    print(f"  New target: {sub.oltc_target_voltage_kv:.1f} kV")
    
    # Test 3: Manual OLTC control
    print("\nTest 3: Manual OLTC control")
    coil_map = ModbusRegisterMap.get_coils("TRANSMISSION")
    
    # Disable auto mode
    sub.write_coil(coil_map["oltc_auto_enable"], False)
    print(f"  OLTC mode: {'AUTO' if sub.oltc_auto_mode else 'MANUAL'}")
    
    # Raise tap manually
    print(f"  Initial tap: {sub.oltc_tap_position:+d}")
    sub.write_coil(coil_map["oltc_raise"], True)
    sub.write_coil(coil_map["oltc_raise"], True)
    print(f"  After 2 raises: {sub.oltc_tap_position:+d}")
    
    # Lower tap manually
    sub.write_coil(coil_map["oltc_lower"], True)
    print(f"  After 1 lower: {sub.oltc_tap_position:+d}")
    
    # Test 4: Thermal simulation
    print("\nTest 4: Thermal simulation (120% load for 10 minutes)")
    for i in range(10):
        sub.update_electrical_state(
            voltage_kv=132.0,
            current_a=600.0,
            p_mw=120.0,
            q_mvar=30.0,
            frequency_hz=50.0,
            dt=60.0,  # 1 minute steps
        )
    
    print(f"  After 10 min at 120% load:")
    print(f"    Oil temp: {sub.thermal_model.state.theta_oil_c:.1f}°C")
    print(f"    Hotspot temp: {sub.thermal_model.state.theta_hs_c:.1f}°C")
    print(f"    Alarm: {sub.thermal_model.state.alarm_active}")
    
    # Test 5: SOE records
    print("\nTest 5: SOE records")
    soe = sub.get_soe_records(count=5)
    print(f"  Total SOE events: {len(sub.soe_buffer)}")
    for record in soe[:3]:
        print(f"    {record.event_type}: {record.description}")
    
    # Test 6: Statistics
    print("\nTest 6: Statistics")
    stats = sub.get_stats()
    print(f"  Transformer load: {stats['substation']['transformer_load_percent']:.1f}%")
    print(f"  Oil temperature: {stats['substation']['oil_temp_c']:.1f}°C")
    print(f"  OLTC tap: {stats['substation']['oltc_tap_position']:+d}")
    print(f"  OLTC mode: {'AUTO' if stats['substation']['oltc_auto_mode'] else 'MANUAL'}")
    
    print("\n✅ Substation node test complete\n")
