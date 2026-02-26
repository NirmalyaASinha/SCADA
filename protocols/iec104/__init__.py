"""
IEC 60870-5-104 Protocol Implementation
========================================

IEC 60870-5-104 is the international standard for SCADA communication over TCP/IP.
Widely used in power utilities across India, Europe, and globally.

This module implements:
    - IEC 104 APCI (Application Protocol Control Information) framing
    - Common protocol data types (R, S, M, ST)
    - Type IDs for measurement and control data
    - Causes of Transmission (COT)
    - Connection state machine
    - Asynchronous message handling

Key differences from Modbus:
    - APCI-based framing with sequence numbers
    - Object-oriented information reporting
    - Richer cause codes for context
    - Better support for time synchronization
    - More efficient for large datasets

Server behavior:
    - Sends unsolicited transmissions when values change
    - Responds to interrogation with complete object database
    - Handles control commands with confirmation
    - Maintains connection health with keep-alive (test frames)
"""

from protocols.iec104.server import IEC104Server
from protocols.iec104.messages import APDU, ASDU, ObjectAddress, CauseOfTransmission

__all__ = [
    'IEC104Server',
    'APDU',
    'ASDU',
    'ObjectAddress',
    'CauseOfTransmission',
]
