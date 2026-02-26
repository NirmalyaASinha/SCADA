"""
Distribution Node
=================

RTU node for distribution feeders.

Extends BaseNode with distribution-specific functionality:
    - Capacitor bank control (reactive power compensation)
    - Underfrequency Load Shedding (UFLS) implementation
    - Feeder current monitoring
    - Voltage regulation
    - Load tap changers (LTC) on distribution transformers

Real distribution RTUs manage:
    - Switched capacitor banks for power factor correction
    - Load shedding relays for grid stability
    - Voltage regulators
    - Recloser controls

This implementation mirrors that architecture.
"""

import time
from typing import Dict, List, Optional
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
from config import PROTECTION_CONFIG

logger = logging.getLogger(__name__)


class DistributionNode(BaseNode):
    """
    Distribution feeder RTU node.
    
    Adds capacitor bank and UFLS control on top of BaseNode.
    """
    
    def __init__(
        self,
        node_id: str,
        feeder_mva: float,
        rated_voltage_kv: float,
        num_capacitor_banks: int = 2,
        capacitor_mvar_per_bank: float = 5.0,
    ):
        """
        Initialize distribution node.
        
        Args:
            node_id: Node identifier (e.g., "DIST-001")
            feeder_mva: Feeder MVA rating
            rated_voltage_kv: Rated distribution voltage in kV
            num_capacitor_banks: Number of switchable capacitor banks
            capacitor_mvar_per_bank: Reactive power per bank in MVAr
        """
        # Calculate rated current
        rated_current_a = (feeder_mva * 1000) / (1.732 * rated_voltage_kv)
        
        super().__init__(
            node_id=node_id,
            node_type="DISTRIBUTION",
            rated_voltage_kv=rated_voltage_kv,
            rated_current_a=rated_current_a,
        )
        
        self.feeder_mva = feeder_mva
        self.num_capacitor_banks = num_capacitor_banks
        self.capacitor_mvar_per_bank = capacitor_mvar_per_bank
        
        # Capacitor bank states
        self.capacitor_bank_states = [False] * num_capacitor_banks
        self.capacitor_auto_mode = True
        self.target_power_factor = 0.95
        
        # UFLS state
        self.ufls_enabled = True
        self.ufls_stages_active = [False, False, False]  # 3 stages
        self.ufls_total_load_shed_percent = 0.0
        
        # UFLS thresholds from config (ANSI 81 protection)
        ufls_cfg = PROTECTION_CONFIG["ANSI_81"]["stages"]
        self.ufls_stage1_freq = ufls_cfg[0]["frequency_hz"]
        self.ufls_stage2_freq = ufls_cfg[1]["frequency_hz"]
        self.ufls_stage3_freq = ufls_cfg[2]["frequency_hz"]
        self.ufls_stage1_load = ufls_cfg[0]["shed_percent"]
        self.ufls_stage2_load = ufls_cfg[1]["shed_percent"]
        self.ufls_stage3_load = ufls_cfg[2]["shed_percent"]
        
        # Feeder loading
        self.feeder_load_mva = 0.0
        self.feeder_load_percent = 0.0
        
        # Initialize protection relay
        self.protection = ProtectionRelay(
            node_name=node_id,
            rated_current_a=rated_current_a,
            rated_voltage_kv=rated_voltage_kv,
        )
        
        # Initialize Modbus registers
        self._initialize_modbus_registers()
        
        logger.info(
            f"Distribution node {node_id} initialized - "
            f"Feeder: {feeder_mva}MVA, {rated_voltage_kv}kV, "
            f"{num_capacitor_banks} capacitor banks"
        )
    
    def _initialize_modbus_registers(self):
        """Initialize distribution-specific Modbus registers."""
        reg_map = ModbusRegisterMap.get_register_map("DISTRIBUTION")
        
        # Initialize input registers (measurements)
        self.input_registers[reg_map["feeder_load_percent"]] = 0
        self.input_registers[reg_map["total_load_shed_percent"]] = 0
        self.input_registers[reg_map["capacitor_banks_online"]] = 0
        
        # Initialize discrete inputs (status)
        discrete_map = ModbusRegisterMap.get_discrete_inputs("DISTRIBUTION")
        self.discrete_inputs[discrete_map["feeder_breaker_status"]] = self.state.breaker_52_closed
        self.discrete_inputs[discrete_map["capacitor_auto_mode"]] = self.capacitor_auto_mode
        self.discrete_inputs[discrete_map["ufls_enabled"]] = self.ufls_enabled
        self.discrete_inputs[discrete_map["ufls_stage1_active"]] = False
        self.discrete_inputs[discrete_map["ufls_stage2_active"]] = False
        self.discrete_inputs[discrete_map["ufls_stage3_active"]] = False
        
        # Initialize coils (controls)
        coil_map = ModbusRegisterMap.get_coils("DISTRIBUTION")
        self.coils[coil_map["capacitor_auto_enable"]] = True
        self.coils[coil_map["capacitor_bank1_switch"]] = False
        self.coils[coil_map["capacitor_bank2_switch"]] = False
        self.coils[coil_map["ufls_enable"]] = True
    
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
        Update electrical state and control logic.
        
        Args:
            voltage_kv: Feeder voltage in kV
            voltage_angle_deg: Voltage angle in degrees
            current_a: Feeder current in amperes
            p_mw: Active power in MW
            q_mvar: Reactive power in MVAr
            frequency_hz: System frequency in Hz
            dt: Timestep in seconds
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
        
        # Calculate feeder loading
        if p_mw is not None and q_mvar is not None:
            self.feeder_load_mva = (p_mw**2 + q_mvar**2)**0.5
            self.feeder_load_percent = (self.feeder_load_mva / self.feeder_mva) * 100.0
        
        # Update capacitor bank control if in auto mode
        if self.capacitor_auto_mode:
            self._update_capacitor_auto()
        
        # Update UFLS logic
        if self.ufls_enabled and frequency_hz is not None:
            self._update_ufls(frequency_hz)
        
        # Update Modbus registers
        self._update_modbus_registers()
    
    def _update_capacitor_auto(self):
        """Automatic capacitor bank switching for power factor control."""
        if not self.state.breaker_52_closed:
            return  # Don't switch capacitors with breaker open
        
        pf = self.state.power_factor
        
        # Calculate how much reactive power we need to add/remove
        if pf < self.target_power_factor - 0.02:  # PF too low (lagging)
            # Need to add capacitance
            for i in range(self.num_capacitor_banks):
                if not self.capacitor_bank_states[i]:
                    self._switch_capacitor_bank(i, True)
                    break  # Switch one at a time
        
        elif pf > self.target_power_factor + 0.02:  # PF too high (leading)
            # Need to remove capacitance
            for i in range(self.num_capacitor_banks - 1, -1, -1):
                if self.capacitor_bank_states[i]:
                    self._switch_capacitor_bank(i, False)
                    break  # Switch one at a time
    
    def _switch_capacitor_bank(self, bank_index: int, state: bool):
        """
        Switch capacitor bank on/off.
        
        Args:
            bank_index: Bank index (0 to num_capacitor_banks-1)
            state: True = close, False = open
        """
        if 0 <= bank_index < self.num_capacitor_banks:
            if self.capacitor_bank_states[bank_index] != state:
                self.capacitor_bank_states[bank_index] = state
                action = "CLOSED" if state else "OPENED"
                
                logger.info(
                    f"{self.node_id} - Capacitor bank {bank_index+1} {action} "
                    f"({self.capacitor_mvar_per_bank:.1f} MVAr)"
                )
                
                self.record_soe(
                    f"CAPACITOR_BANK_{bank_index+1}_{action}",
                    f"Capacitor bank {bank_index+1} {action.lower()}",
                    value=self.capacitor_mvar_per_bank if state else 0.0,
                )
    
    def _update_ufls(self, frequency_hz: float):
        """
        Update Underfrequency Load Shedding logic.
        
        Args:
            frequency_hz: System frequency in Hz
        """
        # Stage 1
        if frequency_hz < self.ufls_stage1_freq and not self.ufls_stages_active[0]:
            self._activate_ufls_stage(1, self.ufls_stage1_load)
        
        # Stage 2
        elif frequency_hz < self.ufls_stage2_freq and not self.ufls_stages_active[1]:
            if self.ufls_stages_active[0]:  # Only if stage 1 already active
                self._activate_ufls_stage(2, self.ufls_stage2_load)
        
        # Stage 3
        elif frequency_hz < self.ufls_stage3_freq and not self.ufls_stages_active[2]:
            if self.ufls_stages_active[1]:  # Only if stage 2 already active
                self._activate_ufls_stage(3, self.ufls_stage3_load)
        
        # Reset if frequency recovers
        elif frequency_hz > 49.7 and any(self.ufls_stages_active):
            self._reset_ufls()
    
    def _activate_ufls_stage(self, stage: int, load_percent: float):
        """
        Activate UFLS stage.
        
        Args:
            stage: Stage number (1, 2, or 3)
            load_percent: Percentage of load to shed
        """
        stage_idx = stage - 1
        
        if 0 <= stage_idx < 3:
            self.ufls_stages_active[stage_idx] = True
            self.ufls_total_load_shed_percent += load_percent
            
            logger.warning(
                f"{self.node_id} - UFLS STAGE {stage} ACTIVATED: "
                f"Shedding {load_percent:.1f}% load (total: {self.ufls_total_load_shed_percent:.1f}%)"
            )
            
            self.record_soe(
                f"UFLS_STAGE{stage}_ACTIVATED",
                f"UFLS stage {stage} activated: {load_percent:.1f}% load shed",
                value=load_percent,
            )
    
    def _reset_ufls(self):
        """Reset all UFLS stages."""
        if any(self.ufls_stages_active):
            logger.info(f"{self.node_id} - UFLS RESET: Frequency recovered")
            
            self.ufls_stages_active = [False, False, False]
            self.ufls_total_load_shed_percent = 0.0
            
            self.record_soe("UFLS_RESET", "UFLS reset - frequency recovered")
    
    def _update_modbus_registers(self):
        """Update Modbus registers with current state."""
        reg_map = ModbusRegisterMap.get_register_map("DISTRIBUTION")
        
        # Update input registers (measurements)
        self.input_registers[reg_map["bus_voltage_kv"]] = encode_voltage_kv(self.state.voltage_kv)
        self.input_registers[reg_map["frequency_hz"]] = encode_frequency_hz(self.state.frequency_hz)
        self.input_registers[reg_map["active_power_mw"]] = encode_power_mw(self.state.p_mw)
        self.input_registers[reg_map["reactive_power_mvar"]] = encode_power_mw(self.state.q_mvar)
        
        # Distribution-specific
        self.input_registers[reg_map["feeder_load_percent"]] = int(self.feeder_load_percent)
        self.input_registers[reg_map["total_load_shed_percent"]] = int(self.ufls_total_load_shed_percent)
        self.input_registers[reg_map["capacitor_banks_online"]] = sum(self.capacitor_bank_states)
        
        # Update discrete inputs (status)
        discrete_map = ModbusRegisterMap.get_discrete_inputs("DISTRIBUTION")
        self.discrete_inputs[discrete_map["feeder_breaker_status"]] = self.state.breaker_52_closed
        self.discrete_inputs[discrete_map["capacitor_auto_mode"]] = self.capacitor_auto_mode
        self.discrete_inputs[discrete_map["ufls_enabled"]] = self.ufls_enabled
        self.discrete_inputs[discrete_map["ufls_stage1_active"]] = self.ufls_stages_active[0]
        self.discrete_inputs[discrete_map["ufls_stage2_active"]] = self.ufls_stages_active[1]
        self.discrete_inputs[discrete_map["ufls_stage3_active"]] = self.ufls_stages_active[2]
    
    def write_coil(self, address: int, value: bool):
        """
        Handle writes to coils (controls).
        
        Args:
            address: Coil address
            value: Coil value (True/False)
        """
        # Call base class (handles breaker control)
        super().write_coil(address, value)
        
        coil_map = ModbusRegisterMap.get_coils("DISTRIBUTION")
        
        # Capacitor auto mode
        if address == coil_map["capacitor_auto_enable"]:
            if value != self.capacitor_auto_mode:
                self.capacitor_auto_mode = value
                mode = "AUTO" if value else "MANUAL"
                logger.info(f"{self.node_id} - Capacitor control mode: {mode}")
                self.record_soe("CAPACITOR_MODE_CHANGE", f"Capacitor mode: {mode}")
        
        # Manual capacitor bank 1 control
        elif address == coil_map["capacitor_bank1_switch"]:
            if not self.capacitor_auto_mode:
                self._switch_capacitor_bank(0, value)
        
        # Manual capacitor bank 2 control
        elif address == coil_map["capacitor_bank2_switch"]:
            if not self.capacitor_auto_mode and self.num_capacitor_banks >= 2:
                self._switch_capacitor_bank(1, value)
        
        # UFLS enable/disable
        elif address == coil_map["ufls_enable"]:
            if value != self.ufls_enabled:
                self.ufls_enabled = value
                state = "ENABLED" if value else "DISABLED"
                logger.info(f"{self.node_id} - UFLS {state}")
                self.record_soe("UFLS_ENABLE_CHANGE", f"UFLS {state.lower()}")
    
    def get_stats(self) -> Dict:
        """Get distribution node statistics."""
        stats = super().get_stats()
        stats["distribution"] = {
            "feeder_mva": self.feeder_mva,
            "feeder_load_mva": self.feeder_load_mva,
            "feeder_load_percent": self.feeder_load_percent,
            "capacitor_banks_online": sum(self.capacitor_bank_states),
            "capacitor_auto_mode": self.capacitor_auto_mode,
            "ufls_enabled": self.ufls_enabled,
            "ufls_stages_active": self.ufls_stages_active.copy(),
            "ufls_total_load_shed_percent": self.ufls_total_load_shed_percent,
        }
        return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n===== DISTRIBUTION NODE TEST =====\n")
    
    # Create distribution node
    dist = DistributionNode(
        node_id="DIST-001",
        feeder_mva=20.0,
        rated_voltage_kv=11.0,
        num_capacitor_banks=2,
        capacitor_mvar_per_bank=5.0,
    )
    
    print(f"Distribution node created: {dist.node_id}")
    print(f"Feeder: {dist.feeder_mva}MVA, {dist.rated_voltage_kv}kV")
    print(f"Capacitor banks: {dist.num_capacitor_banks} × {dist.capacitor_mvar_per_bank}MVAr\n")
    
    # Test 1: Update electrical state with poor power factor
    print("Test 1: Update with poor power factor (0.7 lagging)")
    dist.update_electrical_state(
        voltage_kv=11.0,
        current_a=800.0,
        p_mw=10.0,
        q_mvar=10.2,  # PF ≈ 0.7
        frequency_hz=50.0,
    )
    
    print(f"  Voltage: {dist.state.voltage_kv:.1f} kV")
    print(f"  Power: {dist.state.p_mw:.1f} MW, {dist.state.q_mvar:.1f} MVAr")
    print(f"  Power factor: {dist.state.power_factor:.3f}")
    print(f"  Capacitor banks online: {sum(dist.capacitor_bank_states)}/{dist.num_capacitor_banks}")
    
    # Test 2: Manual capacitor control
    print("\nTest 2: Manual capacitor control")
    from protocols.modbus.register_map import ModbusRegisterMap
    
    coil_map = ModbusRegisterMap.get_coils("DISTRIBUTION")
    
    # Switch to manual mode
    dist.write_coil(coil_map["capacitor_auto_enable"], False)
    print(f"  Mode: {'AUTO' if dist.capacitor_auto_mode else 'MANUAL'}")
    
    # Close bank 1
    dist.write_coil(coil_map["capacitor_bank1_switch"], True)
    print(f"  Bank 1: {'CLOSED' if dist.capacitor_bank_states[0] else 'OPEN'}")
    
    # Close bank 2
    dist.write_coil(coil_map["capacitor_bank2_switch"], True)
    print(f"  Bank 2: {'CLOSED' if dist.capacitor_bank_states[1] else 'OPEN'}")
    
    # Test 3: UFLS activation
    print("\nTest 3: UFLS activation (frequency drop)")
    
    # Stage 1 frequency
    print(f"  Frequency drop to {dist.ufls_stage1_freq - 0.1:.2f} Hz")
    dist.update_electrical_state(
        voltage_kv=11.0,
        p_mw=10.0,
        q_mvar=5.0,
        frequency_hz=dist.ufls_stage1_freq - 0.1,
    )
    print(f"    Stage 1 active: {dist.ufls_stages_active[0]}")
    print(f"    Total load shed: {dist.ufls_total_load_shed_percent:.1f}%")
    
    # Stage 2 frequency
    print(f"  Frequency drop to {dist.ufls_stage2_freq - 0.1:.2f} Hz")
    dist.update_electrical_state(
        frequency_hz=dist.ufls_stage2_freq - 0.1,
    )
    print(f"    Stage 2 active: {dist.ufls_stages_active[1]}")
    print(f"    Total load shed: {dist.ufls_total_load_shed_percent:.1f}%")
    
    # Frequency recovery
    print(f"  Frequency recovers to 49.9 Hz")
    dist.update_electrical_state(frequency_hz=49.9)
    print(f"    UFLS reset: {not any(dist.ufls_stages_active)}")
    print(f"    Total load shed: {dist.ufls_total_load_shed_percent:.1f}%")
    
    # Test 4: SOE records
    print("\nTest 4: SOE records")
    soe = dist.get_soe_records(count=10)
    print(f"  Total SOE events: {len(dist.soe_buffer)}")
    for record in soe[:5]:
        print(f"    {record.event_type}: {record.description}")
    
    # Test 5: Statistics
    print("\nTest 5: Statistics")
    stats = dist.get_stats()
    print(f"  Feeder load: {stats['distribution']['feeder_load_percent']:.1f}%")
    print(f"  Capacitor banks online: {stats['distribution']['capacitor_banks_online']}")
    print(f"  UFLS enabled: {stats['distribution']['ufls_enabled']}")
    print(f"  Load shed: {stats['distribution']['ufls_total_load_shed_percent']:.1f}%")
    
    print("\n✅ Distribution node test complete\n")
