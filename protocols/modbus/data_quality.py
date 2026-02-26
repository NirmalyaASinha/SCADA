"""
Modbus TCP Data Quality Implementation
=======================================

Implements IEC 61968/CIM data quality flags for Modbus registers.

In real SCADA systems, every measurement has an associated quality flag.
This is critical for operators - bad data can lead to incorrect decisions.

Quality flags indicate:
    - Communication status (timeout, CRC error)
    - Sensor health (out of range, drift)
    - Age of data (stale data after communication loss)
    - Manual override (operator forced value)

Quality codes (per IEC 61968):
    0x00  GOOD       : Value is valid, current, and within range
    0x01  SUSPECT    : Value may be stale or uncertain
    0x02  BAD        : Communication failure or sensor fault
    0x04  OVERFLOW   : Value exceeds sensor maximum range
    0x08  UNDERRANGE : Value below sensor minimum range

Real implementation mirrors GE D20, SEL relays, ABB RTUs which all
implement similar quality mechanisms.

Quality degrades during:
    - Communication timeouts (GOOD → SUSPECT after 3 polls → BAD after 10 polls)
    - Failover to backup path (GOOD → SUSPECT during transition)
    - Value out of expected range (GOOD → OVERFLOW/UNDERRANGE)
    - RTU device failure (all → BAD)
"""

from typing import Dict
from enum import IntFlag
import time

from config import DATA_QUALITY


class DataQuality(IntFlag):
    """Data quality flags (IEC 61968)."""
    GOOD = DATA_QUALITY["GOOD"]
    SUSPECT = DATA_QUALITY["SUSPECT"]
    BAD = DATA_QUALITY["BAD"]
    OVERFLOW = DATA_QUALITY["OVERFLOW"]
    UNDERRANGE = DATA_QUALITY["UNDERRANGE"]


class DataQualityManager:
    """
    Manages data quality for all registers.
    
    Tracks quality for each register and degradation rules.
    """
    
    def __init__(self):
        # Quality state for each register address
        self.register_quality: Dict[int, DataQuality] = {}
        
        # Last update time for each register (for staleness detection)
        self.register_last_update: Dict[int, float] = {}
        
        # Missed poll counter for each register
        self.register_missed_polls: Dict[int, int] = {}
    
    def set_quality(self, register_address: int, quality: DataQuality):
        """
        Set quality for a register.
        
        Args:
            register_address: Modbus register address
            quality: Quality code
        """
        self.register_quality[register_address] = quality
        self.register_last_update[register_address] = time.time()
        
        # Reset missed poll counter on successful update
        if quality == DataQuality.GOOD:
            self.register_missed_polls[register_address] = 0
    
    def get_quality(self, register_address: int) -> DataQuality:
        """
        Get quality for a register.
        
        Args:
            register_address: Modbus register address
        
        Returns:
            Quality code (defaults to BAD if never set)
        """
        return self.register_quality.get(register_address, DataQuality.BAD)
    
    def mark_communication_timeout(self, register_address: int):
        """
        Mark register as having communication timeout.
        
        Quality degrades: GOOD → SUSPECT (after 3 misses) → BAD (after 10 misses)
        
        Args:
            register_address: Modbus register address
        """
        missed = self.register_missed_polls.get(register_address, 0) + 1
        self.register_missed_polls[register_address] = missed
        
        if missed >= 10:
            self.set_quality(register_address, DataQuality.BAD)
        elif missed >= 3:
            self.set_quality(register_address, DataQuality.SUSPECT)
    
    def check_value_range(
        self,
        register_address: int,
        value: float,
        min_value: float,
        max_value: float,
    ) -> DataQuality:
        """
        Check if value is within expected range.
        
        Args:
            register_address: Modbus register address
            value: Measured value
            min_value: Sensor minimum range
            max_value: Sensor maximum range
        
        Returns:
            Quality code based on range check
        """
        if value > max_value:
            quality = DataQuality.OVERFLOW
        elif value < min_value:
            quality = DataQuality.UNDERRANGE
        else:
            quality = DataQuality.GOOD
        
        self.set_quality(register_address, quality)
        return quality
    
    def mark_all_bad(self):
        """Mark all registers as BAD (device failure)."""
        for addr in list(self.register_quality.keys()):
            self.register_quality[addr] = DataQuality.BAD
    
    def mark_all_good(self):
        """Mark all registers as GOOD (recovery from failure)."""
        for addr in list(self.register_quality.keys()):
            self.register_quality[addr] = DataQuality.GOOD
            self.register_missed_polls[addr] = 0
    
    def get_quality_summary(self) -> Dict[str, int]:
        """
        Get summary of quality across all registers.
        
        Returns:
            Dict with count of registers at each quality level
        """
        summary = {
            "GOOD": 0,
            "SUSPECT": 0,
            "BAD": 0,
            "OVERFLOW": 0,
            "UNDERRANGE": 0,
        }
        
        for quality in self.register_quality.values():
            if quality == DataQuality.GOOD:
                summary["GOOD"] += 1
            elif quality == DataQuality.SUSPECT:
                summary["SUSPECT"] += 1
            elif quality == DataQuality.BAD:
                summary["BAD"] += 1
            elif quality == DataQuality.OVERFLOW:
                summary["OVERFLOW"] += 1
            elif quality == DataQuality.UNDERRANGE:
                summary["UNDERRANGE"] += 1
        
        return summary
