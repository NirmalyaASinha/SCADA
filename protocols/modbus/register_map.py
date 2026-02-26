"""
Modbus TCP Register Map
========================

Defines the register layout for each node type.

Real Modbus RTUs have carefully designed register maps that organize data
logically and provide efficient polling. This map mirrors real utility practice.

Register address conventions (industry standard):
    0-999    : Discrete coils (FC01, FC05) - binary outputs/controls
    1000-1999: Discrete inputs (FC02) - binary status
    3000-3999: Input registers (FC04) - read-only analog measurements
    4000-4999: Holding registers (FC03, FC06, FC16) - read/write analog

Data quality registers:
    Each analog value has a corresponding quality register +100 offset
    Quality codes per IEC 61968:
        0x00 = GOOD
        0x01 = SUSPECT
        0x02 = BAD
        0x04 = OVERFLOW
        0x08 = UNDERRANGE

Modbus data type encoding:
    16-bit registers store:
        - Scaled integers for voltages, currents, power
        - IEEE 754 floats in two consecutive registers (32-bit)
        - Status word bit fields

Scaling factors chosen to maximize resolution within 16-bit range:
    Voltage (kV): scale 10 (e.g., 400.5 kV → 4005)
    Current (A):  scale 1
    Power (MW):   scale 10 (e.g., 123.4 MW → 1234)
    Frequency (Hz): scale 1000 (e.g., 50.123 Hz → 50123)

This register map is the interface between electrical simulation and 
protocol communication - it's what a real SCADA master polls.
"""

from typing import Dict, List, Tuple
from enum import IntEnum
import numpy as np

from config import DATA_QUALITY


class RegisterType(IntEnum):
    """Modbus register types."""
    COIL = 0            # Discrete output (read/write)
    DISCRETE_INPUT = 1  # Discrete input (read-only)
    INPUT_REGISTER = 3  # Analog input (read-only)
    HOLDING_REGISTER = 4  # Analog holding (read/write)


class ModbusRegisterMap:
    """
    Modbus register map for SCADA nodes.
    
    Provides register address allocation and data encoding/decoding.
    """
    
    # Register base addresses
    COILS_BASE = 0
    DISCRETE_INPUTS_BASE = 1000
    INPUT_REGISTERS_BASE = 3000
    HOLDING_REGISTERS_BASE = 4000
    QUALITY_REGISTERS_OFFSET = 100
    
    # Common registers for all nodes
    COMMON_INPUT_REGISTERS = {
        "bus_voltage_kv": 3000,          # Bus voltage (kV * 10)
        "bus_voltage_quality": 3100,     # Quality code
        "frequency_hz": 3001,            # Frequency (Hz * 1000)
        "frequency_quality": 3101,
        "active_power_mw": 3002,        # Active power (MW * 10)
        "active_power_quality": 3102,
        "reactive_power_mvar": 3003,    # Reactive power (MVAR * 10)
        "reactive_power_quality": 3103,
        "power_factor": 3004,           # Power factor (* 1000)
        "power_factor_quality": 3104,
    }
    
    # Generation node registers
    GENERATION_REGISTERS = {
        **COMMON_INPUT_REGISTERS,
        "generator_mw": 3010,           # Generator output (MW * 10)
        "generator_mw_quality": 3110,
        "generator_mvar": 3011,         # Generator reactive (MVAR * 10)
        "generator_mvar_quality": 3111,
        "governor_setpoint_mw": 4010,   # Governor setpoint (holding register)
        "governor_setpoint_quality": 4110,
        "avr_setpoint_kv": 4011,        # AVR voltage setpoint (holding register)
        "avr_setpoint_quality": 4111,
    }
    
    # Generation discrete inputs
    GENERATION_DISCRETE_INPUTS = {
        "generator_breaker_status": 1000,    # 0=open, 1=closed
        "sync_status": 1001,                 # 0=not synchronized, 1=synchronized
        "governor_mode": 1002,               # 0=manual, 1=auto
        "avr_mode": 1003,                    # 0=manual, 1=auto
        "protection_trip": 1010,             # Any protection trip
        "overcurrent_trip": 1011,            # ANSI 51 trip
        "overvoltage_trip": 1012,            # ANSI 59 trip
        "undervoltage_trip": 1013,           # ANSI 27 trip
    }
    
    # Generation coils (controls)
    GENERATION_COILS = {
        "breaker_close_cmd": 0,          # Command to close breaker
        "breaker_open_cmd": 1,           # Command to open breaker
        "governor_auto_mode": 2,          # Governor auto mode enable
        "avr_auto_mode": 3,               # AVR auto mode enable
        "protection_reset_cmd": 10,      # Reset protection trip
    }
    
    # Substation (transmission) registers
    SUBSTATION_REGISTERS = {
        **COMMON_INPUT_REGISTERS,
        "transformer_load_percent": 3020,    # Transformer loading percent
        "transformer_oil_temp_c": 3021,      # Oil temperature (°C * 10)
        "transformer_oil_temp_quality": 3121,
        "transformer_hotspot_temp_c": 3022,       # Hot-spot temperature (°C * 10)
        "transformer_hotspot_temp_quality": 3122,
        "oltc_tap_position": 3023,           # Tap changer position (offset +100)\n        "oltc_tap_position_quality": 3123,
        "oltc_target_voltage_kv": 4020,      # OLTC target voltage (holding register)
        "line_current_a_ph_a": 3030,         # Line current phase A (A)
        "line_current_a_ph_b": 3031,
        "line_current_a_ph_c": 3032,
        "line_current_quality": 3130,
    }
    
    # Substation discrete inputs
    SUBSTATION_DISCRETE_INPUTS = {
        "transformer_breaker_hv_status": 1000,  # HV side breaker
        "transformer_breaker_lv_status": 1001,  # LV side breaker
        "oltc_auto_mode": 1002,                 # OLTC auto/manual
        "oltc_at_max_position": 1003,           # Tap at max (17)
        "oltc_at_min_position": 1004,           # Tap at min (1)
        "thermal_alarm": 1010,                  # Transformer overtemperature alarm
        "thermal_trip": 1011,                   # Transformer overtemperature trip
        "differential_trip": 1012,              # ANSI 87T trip
        "overcurrent_trip": 1013,               # ANSI 51 trip
    }
    
    # Substation coils
    SUBSTATION_COILS = {
        "breaker_hv_close_cmd": 0,
        "breaker_hv_open_cmd": 1,
        "breaker_lv_close_cmd": 2,
        "breaker_lv_open_cmd": 3,
        "oltc_raise": 4,                # Raise tap position
        "oltc_lower": 5,                # Lower tap position
        "oltc_auto_enable": 6,            # Enable OLTC auto mode
        "protection_reset_cmd": 10,
    }
    
    # Distribution registers
    DISTRIBUTION_REGISTERS = {
        **COMMON_INPUT_REGISTERS,
        "feeder_load_percent": 3040,        # Feeder load percent
        "feeder_load_quality": 3140,
        "total_load_shed_percent": 3041,    # Total load shed percent
        "capacitor_banks_online": 3042,     # Number of capacitor banks online
        "line_current_a": 3043,             # Line current (A)
        "line_current_quality": 3143,
        "voltage_phase_a_kv": 3044,         # Phase voltages
        "voltage_phase_b_kv": 3045,
        "voltage_phase_c_kv": 3046,
        "voltage_quality": 3144,
        "energy_delivered_mwh": 3050,       # Energy meter (MWh * 10)
        "energy_quality": 3150,
    }
    
    # Distribution discrete inputs
    DISTRIBUTION_DISCRETE_INPUTS = {
        "feeder_breaker_status": 1000,
        "capacitor_auto_mode": 1001,
        "ufls_enabled": 1002,
        "ufls_stage1_active": 1003,
        "ufls_stage2_active": 1004,
        "ufls_stage3_active": 1005,
        "recloser_status": 1010,
        "undervoltage_alarm": 1011,
        "overcurrent_alarm": 1012,
    }
    
    # Distribution coils
    DISTRIBUTION_COILS = {
        "breaker_close_cmd": 0,
        "breaker_open_cmd": 1,
        "capacitor_auto_enable": 2,     # Capacitor auto mode enable
        "capacitor_bank1_switch": 3,     # Manual capacitor bank 1 control
        "capacitor_bank2_switch": 4,     # Manual capacitor bank 2 control
        "ufls_enable": 5,                # UFLS enable
    }
    
    @staticmethod
    def get_register_map(node_type: str) -> Dict[str, int]:
        """
        Get register map for node type.
        
        Args:
            node_type: "GENERATION", "TRANSMISSION", or "DISTRIBUTION"
        
        Returns:
            Dict mapping register name to address
        """
        if node_type == "GENERATION":
            return ModbusRegisterMap.GENERATION_REGISTERS
        elif node_type == "TRANSMISSION":
            return ModbusRegisterMap.SUBSTATION_REGISTERS
        elif node_type == "DISTRIBUTION":
            return ModbusRegisterMap.DISTRIBUTION_REGISTERS
        else:
            return ModbusRegisterMap.COMMON_INPUT_REGISTERS
    
    @staticmethod
    def get_discrete_inputs(node_type: str) -> Dict[str, int]:
        """Get discrete input addresses for node type."""
        if node_type == "GENERATION":
            return ModbusRegisterMap.GENERATION_DISCRETE_INPUTS
        elif node_type == "TRANSMISSION":
            return ModbusRegisterMap.SUBSTATION_DISCRETE_INPUTS
        elif node_type == "DISTRIBUTION":
            return ModbusRegisterMap.DISTRIBUTION_DISCRETE_INPUTS
        else:
            return {}
    
    @staticmethod
    def get_coils(node_type: str) -> Dict[str, int]:
        """Get coil addresses for node type."""
        if node_type == "GENERATION":
            return ModbusRegisterMap.GENERATION_COILS
        elif node_type == "TRANSMISSION":
            return ModbusRegisterMap.SUBSTATION_COILS
        elif node_type == "DISTRIBUTION":
            return ModbusRegisterMap.DISTRIBUTION_COILS
        else:
            return {}
    
    @staticmethod
    def encode_voltage_kv(voltage_kv: float) -> int:
        """Encode voltage (kV) to 16-bit register value."""
        return int(round(voltage_kv * 10.0))
    
    @staticmethod
    def decode_voltage_kv(register_value: int) -> float:
        """Decode voltage register value to kV."""
        return float(register_value) / 10.0
    
    @staticmethod
    def encode_current_a(current_a: float) -> int:
        """Encode current (A) to 16-bit register value."""
        return int(round(current_a))
    
    @staticmethod
    def decode_current_a(register_value: int) -> float:
        """Decode current register value to A."""
        return float(register_value)
    
    @staticmethod
    def encode_power_mw(power_mw: float) -> int:
        """Encode power (MW) to 16-bit register value."""
        return int(round(power_mw * 10.0))
    
    @staticmethod
    def decode_power_mw(register_value: int) -> float:
        """Decode power register value to MW."""
        return float(register_value) / 10.0
    
    @staticmethod
    def encode_frequency_hz(frequency_hz: float) -> int:
        """Encode frequency (Hz) to 16-bit register value."""
        if not np.isfinite(frequency_hz):
            frequency_hz = 50.0  # Default to nominal
        return int(round(frequency_hz * 1000.0))
    
    @staticmethod
    def decode_frequency_hz(register_value: int) -> float:
        """Decode frequency register value to Hz."""
        return float(register_value) / 1000.0
    
    @staticmethod
    def encode_temperature_c(temp_c: float) -> int:
        """Encode temperature (°C) to 16-bit register value."""
        return int(round(temp_c * 10.0))
    
    @staticmethod
    def decode_temperature_c(register_value: int) -> float:
        """Decode temperature register value to °C."""
        return float(register_value) / 10.0
    
    @staticmethod
    def encode_power_factor(pf: float) -> int:
        """Encode power factor to 16-bit register value."""
        return int(round(pf * 1000.0))
    
    @staticmethod
    def decode_power_factor(register_value: int) -> float:
        """Decode power factor register value."""
        return float(register_value) / 1000.0


# Module-level convenience functions (delegates to class methods)
encode_voltage_kv = ModbusRegisterMap.encode_voltage_kv
decode_voltage_kv = ModbusRegisterMap.decode_voltage_kv
encode_current_a = ModbusRegisterMap.encode_current_a
decode_current_a = ModbusRegisterMap.decode_current_a
encode_power_mw = ModbusRegisterMap.encode_power_mw
decode_power_mw = ModbusRegisterMap.decode_power_mw
encode_frequency_hz = ModbusRegisterMap.encode_frequency_hz
decode_frequency_hz = ModbusRegisterMap.decode_frequency_hz
encode_temperature_celsius = ModbusRegisterMap.encode_temperature_c
decode_temperature_celsius = ModbusRegisterMap.decode_temperature_c
encode_power_factor = ModbusRegisterMap.encode_power_factor
decode_power_factor = ModbusRegisterMap.decode_power_factor


# Export register map dictionaries
GENERATION_REGISTERS = ModbusRegisterMap.GENERATION_REGISTERS
SUBSTATION_REGISTERS = ModbusRegisterMap.SUBSTATION_REGISTERS
DISTRIBUTION_REGISTERS = ModbusRegisterMap.DISTRIBUTION_REGISTERS
