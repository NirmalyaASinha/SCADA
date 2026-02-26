"""
Node Package
============

SCADA RTU node implementations.

This package provides the integration layer between electrical models
and protocol servers. Each node represents a complete RTU with:
    - Electrical state management
    - Protocol communication (Modbus, IEC 104, DNP3)
    - Data quality tracking
    - Sequence of Events recording
    - Protection relay integration

Node types:
    - BaseNode: Common infrastructure for all nodes
    - GenerationNode: Generator RTU (governor, AVR control)
    - SubstationNode: Transmission substation RTU (transformer thermal, OLTC)
    - DistributionNode: Distribution feeder RTU (capacitor banks, UFLS)
"""

from nodes.base_node import BaseNode, ElectricalState, SOERecord
from nodes.generation_node import GenerationNode
from nodes.substation_node import SubstationNode
from nodes.distribution_node import DistributionNode

__all__ = [
    'BaseNode',
    'ElectricalState',
    'SOERecord',
    'GenerationNode',
    'SubstationNode',
    'DistributionNode',
]
