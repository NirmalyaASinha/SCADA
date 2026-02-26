"""
Modbus Protocol Implementation
===============================

Production-faithful Modbus TCP implementation matching real RTU behavior.

This package provides:
    - ModbusTCPServer: Async TCP server with spec-compliant framing
    - ModbusStateMachine: State machine enforcing realistic request processing
    - Register mapping: Address layout for all node types
    - Data quality: IEC 61968 quality flags

Usage:
    from protocols.modbus import ModbusTCPServer
    from protocols.modbus.register_map import GENERATION_REGISTERS
    
    server = ModbusTCPServer(node, unit_id=1, port=502)
    await server.start()
"""

from protocols.modbus.server import ModbusTCPServer
from protocols.modbus.state_machine import ModbusStateMachine, ModbusException
from protocols.modbus.register_map import (
    GENERATION_REGISTERS,
    SUBSTATION_REGISTERS,
    DISTRIBUTION_REGISTERS,
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
from protocols.modbus.data_quality import DataQualityManager, DataQuality

__all__ = [
    # Server
    'ModbusTCPServer',
    'ModbusStateMachine',
    'ModbusException',
    
    # Register maps
    'GENERATION_REGISTERS',
    'SUBSTATION_REGISTERS',
    'DISTRIBUTION_REGISTERS',
    
    # Encoding functions
    'encode_voltage_kv',
    'encode_current_a',
    'encode_power_mw',
    'encode_frequency_hz',
    'encode_temperature_celsius',
    
    # Decoding functions
    'decode_voltage_kv',
    'decode_current_a',
    'decode_power_mw',
    'decode_frequency_hz',
    'decode_temperature_celsius',
    
    # Data quality
    'DataQualityManager',
    'DataQuality',
]
