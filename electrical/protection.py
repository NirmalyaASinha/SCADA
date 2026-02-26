"""
Protection Relay Logic (ANSI Standard Device Numbers)
======================================================

Implements protection functions per IEC 60255 and IEEE C37 standards.

Protection relays are the "immune system" of the power grid - they detect
abnormal conditions and isolate faults to prevent damage and cascading failures.

Each protection function has an ANSI device number (IEEE C37.2 standard):
    ANSI 27  : Undervoltage
    ANSI 51  : Overcurrent (inverse time)
    ANSI 59  : Overvoltage
    ANSI 81  : Underfrequency (load shedding)
    ANSI 87T : Transformer differential

Real SCADA systems receive protection relay trip signals as discrete inputs.
Every relay operation generates:
    1. SOE (Sequence of Events) record with 1ms timestamp
    2. SCADA alarm with priority based on severity
    3. Event log with fault current/voltage measurements

Protection relay coordination is critical - relays must trip in correct
sequence to isolate only the faulted section (selectivity).

This simulation implements the trip logic used in real protective relays,
producing trip signals that appear in the SCADA system exactly as they
would in a real substation.
"""

import numpy as np
from typing import Dict, List, Optional
import logging
from dataclasses import dataclass
from enum import Enum
import sys
from pathlib import Path

# Add parent directory to path for imports
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from config import PROTECTION_CONFIG, NOMINAL_FREQUENCY_HZ

logger = logging.getLogger(__name__)


class ProtectionTripReason(Enum):
    """Protection trip reason codes."""
    NONE = "No trip"
    OVERCURRENT = "ANSI 51 - Overcurrent"
    OVERVOLTAGE = "ANSI 59 - Overvoltage"
    UNDERVOLTAGE = "ANSI 27 - Undervoltage"
    UNDERFREQUENCY = "ANSI 81 - Underfrequency"
    DIFFERENTIAL = "ANSI 87T - Differential"
    THERMAL = "ANSI 49 - Thermal Overload"


@dataclass
class ProtectionState:
    """State of protection relay pickups."""
    overcurrent_pickup_time: float = 0.0
    overvoltage_pickup_time: float = 0.0
    undervoltage_pickup_time: float = 0.0
    underfreq_stage1_pickup_time: float = 0.0
    underfreq_stage2_pickup_time: float = 0.0
    underfreq_stage3_pickup_time: float = 0.0
    differential_pickup_time: float = 0.0
    
    tripped: bool = False
    trip_reason: ProtectionTripReason = ProtectionTripReason.NONE
    trip_time: float = 0.0


class ProtectionRelay:
    """
    Multi-function protection relay (like real microprocessor relays).
    
    Implements multiple protection functions:
    - ANSI 51: Inverse-time overcurrent
    - ANSI 59: Overvoltage
    - ANSI 27: Undervoltage
    - ANSI 81: Underfrequency load shedding
    - ANSI 87T: Transformer differential
    
    Each function operates independently but with coordination logic.
    """
    
    def __init__(self, node_name: str, rated_current_a: float, rated_voltage_kv: float):
        self.node_name = node_name
        self.rated_current_a = rated_current_a
        self.rated_voltage_kv = rated_voltage_kv
        
        self.state = ProtectionState()
        
        # Trip log for SOE recording
        self.trip_log: List[Dict] = []
        
        logger.info(
            f"Protection relay initialized for {node_name} "
            f"(I_rated={rated_current_a:.0f}A, V_rated={rated_voltage_kv:.0f}kV)"
        )
    
    def update(
        self,
        current_time: float,
        dt: float,
        line_current_a: float,
        bus_voltage_kv: float,
        frequency_hz: float,
        transformer_i_primary_a: Optional[float] = None,
        transformer_i_secondary_a: Optional[float] = None,
        transformer_turns_ratio: Optional[float] = None,
    ) -> Dict:
        """
        Update protection relay logic for one time step.
        
        Args:
            current_time: Current simulation time (s)
            dt: Time step (s)
            line_current_a: Line current magnitude (A)
            bus_voltage_kv: Bus voltage magnitude (kV)
            frequency_hz: System frequency (Hz)
            transformer_i_primary_a: Transformer primary current (optional)
            transformer_i_secondary_a: Transformer secondary current (optional)
            transformer_turns_ratio: Transformer turns ratio (optional)
        
        Returns:
            results: Dict containing trip status and measurements
        """
        
        if self.state.tripped:
            # Once tripped, relay is latched until reset
            return self._get_tripped_result()
        
        # Check each protection function
        
        # --- ANSI 51: Overcurrent Protection ---
        trip_overcurrent = self._check_overcurrent(
            current_time, dt, line_current_a
        )
        
        # --- ANSI 59: Overvoltage Protection ---
        trip_overvoltage = self._check_overvoltage(
            current_time, dt, bus_voltage_kv
        )
        
        # --- ANSI 27: Undervoltage Protection ---
        trip_undervoltage = self._check_undervoltage(
            current_time, dt, bus_voltage_kv
        )
        
        # --- ANSI 81: Underfrequency Load Shedding ---
        shed_load_percent = self._check_underfrequency(
            current_time, dt, frequency_hz
        )
        
        # --- ANSI 87T: Transformer Differential ---
        trip_differential = False
        if transformer_i_primary_a is not None and transformer_i_secondary_a is not None:
            trip_differential = self._check_differential(
                current_time, dt,
                transformer_i_primary_a,
                transformer_i_secondary_a,
                transformer_turns_ratio or 1.0,
            )
        
        # Priority: Differential > Overcurrent > Overvoltage > Undervoltage
        # (Internal faults are highest priority)
        
        if trip_differential:
            self._trip(current_time, ProtectionTripReason.DIFFERENTIAL)
        elif trip_overcurrent:
            self._trip(current_time, ProtectionTripReason.OVERCURRENT)
        elif trip_overvoltage:
            self._trip(current_time, ProtectionTripReason.OVERVOLTAGE)
        elif trip_undervoltage:
            self._trip(current_time, ProtectionTripReason.UNDERVOLTAGE)
        
        results = {
            "tripped": self.state.tripped,
            "trip_reason": self.state.trip_reason.value,
            "load_shed_percent": shed_load_percent,
            "measurements": {
                "current_a": line_current_a,
                "voltage_kv": bus_voltage_kv,
                "frequency_hz": frequency_hz,
                "current_percent": (line_current_a / self.rated_current_a) * 100.0,
                "voltage_percent": (bus_voltage_kv / self.rated_voltage_kv) * 100.0,
            },
        }
        
        return results
    
    def _check_overcurrent(self, current_time: float, dt: float, current_a: float) -> bool:
        """
        ANSI 51: Inverse-time overcurrent protection.
        
        Uses IEC Standard Inverse characteristic:
            t_trip = TMS * 0.14 / ((I/I_s)^0.02 - 1)
        
        Where:
            TMS = Time Multiplier Setting (from config)
            I = actual current
            I_s = pickup current setting
        
        Returns True if trip condition met.
        """
        config = PROTECTION_CONFIG["ANSI_51"]
        pickup_percent = config["pickup_percent"]
        I_pickup = (pickup_percent / 100.0) * self.rated_current_a
        
        if current_a > I_pickup:
            # Current exceeds pickup - calculate trip time
            TMS = config["time_multiplier"]
            exponent = config["curve_exponent"]
            min_trip_time = config["min_trip_time_s"]
            
            I_ratio = current_a / I_pickup
            
            # IEC Standard Inverse characteristic
            if I_ratio > 1.0:
                t_trip = TMS * 0.14 / ((I_ratio ** exponent) - 1.0)
                t_trip = max(t_trip, min_trip_time)
            else:
                t_trip = float('inf')
            
            # Accumulate pickup time
            if self.state.overcurrent_pickup_time == 0.0:
                self.state.overcurrent_pickup_time = current_time
                logger.warning(
                    f"{self.node_name} ANSI 51 PICKUP: I={current_a:.0f}A "
                    f"({I_ratio*100:.0f}%), trip in {t_trip:.1f}s"
                )
            
            elapsed = current_time - self.state.overcurrent_pickup_time
            
            if elapsed >= t_trip:
                logger.error(
                    f"{self.node_name} ANSI 51 TRIP: Overcurrent {current_a:.0f}A "
                    f"for {elapsed:.1f}s"
                )
                return True
        else:
            # Current below pickup - reset timer
            if self.state.overcurrent_pickup_time > 0.0:
                logger.info(f"{self.node_name} ANSI 51 RESET")
            self.state.overcurrent_pickup_time = 0.0
        
        return False
    
    def _check_overvoltage(self, current_time: float, dt: float, voltage_kv: float) -> bool:
        """ANSI 59: Overvoltage protection (definite time)."""
        config = PROTECTION_CONFIG["ANSI_59"]
        pickup_percent = config["pickup_percent"]
        V_pickup = (pickup_percent / 100.0) * self.rated_voltage_kv
        trip_delay = config["trip_delay_s"]
        
        if voltage_kv > V_pickup:
            if self.state.overvoltage_pickup_time == 0.0:
                self.state.overvoltage_pickup_time = current_time
                logger.warning(
                    f"{self.node_name} ANSI 59 PICKUP: V={voltage_kv:.1f}kV "
                    f"({voltage_kv/self.rated_voltage_kv*100:.0f}%)"
                )
            
            elapsed = current_time - self.state.overvoltage_pickup_time
            
            if elapsed >= trip_delay:
                logger.error(
                    f"{self.node_name} ANSI 59 TRIP: Overvoltage {voltage_kv:.1f}kV "
                    f"for {elapsed:.1f}s"
                )
                return True
        else:
            if self.state.overvoltage_pickup_time > 0.0:
                logger.info(f"{self.node_name} ANSI 59 RESET")
            self.state.overvoltage_pickup_time = 0.0
        
        return False
    
    def _check_undervoltage(self, current_time: float, dt: float, voltage_kv: float) -> bool:
        """ANSI 27: Undervoltage protection (definite time)."""
        config = PROTECTION_CONFIG["ANSI_27"]
        pickup_percent = config["pickup_percent"]
        V_pickup = (pickup_percent / 100.0) * self.rated_voltage_kv
        trip_delay = config["trip_delay_s"]
        
        if voltage_kv < V_pickup:
            if self.state.undervoltage_pickup_time == 0.0:
                self.state.undervoltage_pickup_time = current_time
                logger.warning(
                    f"{self.node_name} ANSI 27 PICKUP: V={voltage_kv:.1f}kV "
                    f"({voltage_kv/self.rated_voltage_kv*100:.0f}%)"
                )
            
            elapsed = current_time - self.state.undervoltage_pickup_time
            
            if elapsed >= trip_delay:
                logger.error(
                    f"{self.node_name} ANSI 27 TRIP: Undervoltage {voltage_kv:.1f}kV "
                    f"for {elapsed:.1f}s"
                )
                return True
        else:
            if self.state.undervoltage_pickup_time > 0.0:
                logger.info(f"{self.node_name} ANSI 27 RESET")
            self.state.undervoltage_pickup_time = 0.0
        
        return False
    
    def _check_underfrequency(self, current_time: float, dt: float, frequency_hz: float) -> float:
        """
        ANSI 81: Underfrequency load shedding.
        
        Returns percentage of load to shed (0-100).
        """
        config = PROTECTION_CONFIG["ANSI_81"]
        stages = config["stages"]
        
        total_shed_percent = 0.0
        
        # Check each stage in order
        for idx, stage in enumerate(stages):
            f_threshold = stage["frequency_hz"]
            delay_s = stage["delay_s"]
            shed_percent = stage["shed_percent"]
            
            if frequency_hz < f_threshold:
                # Determine which pickup timer to use
                if idx == 0:
                    pickup_time_attr = "underfreq_stage1_pickup_time"
                elif idx == 1:
                    pickup_time_attr = "underfreq_stage2_pickup_time"
                else:
                    pickup_time_attr = "underfreq_stage3_pickup_time"
                
                pickup_time = getattr(self.state, pickup_time_attr)
                
                if pickup_time == 0.0:
                    setattr(self.state, pickup_time_attr, current_time)
                    logger.warning(
                        f"{self.node_name} ANSI 81 STAGE {idx+1} PICKUP: "
                        f"f={frequency_hz:.3f}Hz < {f_threshold:.3f}Hz"
                    )
                    pickup_time = current_time
                
                elapsed = current_time - pickup_time
                
                if elapsed >= delay_s:
                    # Shed this stage
                    total_shed_percent += shed_percent
                    logger.error(
                        f"{self.node_name} ANSI 81 STAGE {idx+1} SHED: "
                        f"{shed_percent:.0f}% load shed due to f={frequency_hz:.3f}Hz"
                    )
            else:
                # Frequency above threshold - reset this stage
                if idx == 0:
                    self.state.underfreq_stage1_pickup_time = 0.0
                elif idx == 1:
                    self.state.underfreq_stage2_pickup_time = 0.0
                else:
                    self.state.underfreq_stage3_pickup_time = 0.0
        
        return total_shed_percent
    
    def _check_differential(
        self,
        current_time: float,
        dt: float,
        I_primary_a: float,
        I_secondary_a: float,
        turns_ratio: float,
    ) -> bool:
        """
        ANSI 87T: Transformer differential protection.
        
        Compares primary and secondary currents.
        Trip if: |I_primary - I_secondary * turns_ratio| > pickup
        
        Most sensitive and fastest protection - detects internal faults.
        """
        config = PROTECTION_CONFIG["ANSI_87T"]
        pickup_percent = config["pickup_percent"]
        
        # Normalize secondary current to primary side
        I_secondary_normalized = I_secondary_a * turns_ratio
        
        # Differential current
        I_diff = abs(I_primary_a - I_secondary_normalized)
        
        # Restraint current (average of through current)
        I_restraint = (abs(I_primary_a) + abs(I_secondary_normalized)) / 2.0
        
        # Pickup threshold
        I_pickup = (pickup_percent / 100.0) * self.rated_current_a
        
        if I_diff > I_pickup and I_restraint > 0.1 * self.rated_current_a:
            # Differential trip (instantaneous - no intentional delay)
            logger.error(
                f"{self.node_name} ANSI 87T TRIP: Differential current {I_diff:.0f}A "
                f"(I_pri={I_primary_a:.0f}A, I_sec={I_secondary_a:.0f}A, ratio={turns_ratio:.2f})"
            )
            return True
        
        return False
    
    def _trip(self, trip_time: float, reason: ProtectionTripReason):
        """Execute protection trip."""
        self.state.tripped = True
        self.state.trip_reason = reason
        self.state.trip_time = trip_time
        
        # Log trip event for SOE
        trip_event = {
            "node": self.node_name,
            "time": trip_time,
            "reason": reason.value,
            "function": reason.name,
        }
        self.trip_log.append(trip_event)
        
        logger.critical(
            f"{'='*60}\n"
            f"PROTECTION TRIP: {self.node_name}\n"
            f"Function: {reason.value}\n"
            f"Time: {trip_time:.3f}s\n"
            f"{'='*60}"
        )
    
    def _get_tripped_result(self) -> Dict:
        """Return result when relay is tripped."""
        return {
            "tripped": True,
            "trip_reason": self.state.trip_reason.value,
            "trip_time": self.state.trip_time,
            "load_shed_percent": 0.0,
            "measurements": {},
        }
    
    def reset(self):
        """Reset relay (operator action after fault cleared)."""
        if self.state.tripped:
            logger.info(f"{self.node_name} Protection relay RESET by operator")
        
        self.state = ProtectionState()
    
    def get_trip_log(self) -> List[Dict]:
        """Return trip event log for SOE recording."""
        return self.trip_log.copy()


if __name__ == "__main__":
    # Test protection relay
    logging.basicConfig(level=logging.DEBUG)
    
    relay = ProtectionRelay("SUB-001", rated_current_a=1000.0, rated_voltage_kv=400.0)
    
    print("\n===== PROTECTION RELAY TEST =====\n")
    
    # Test overcurrent trip
    print("Test 1: Overcurrent protection (150% rated current)\n")
    
    for t in range(0, 10):
        results = relay.update(
            current_time=float(t),
            dt=1.0,
            line_current_a=1500.0,  # 150% rated
            bus_voltage_kv=400.0,
            frequency_hz=50.0,
        )
        
        if results["tripped"]:
            print(f"t={t}s: TRIPPED - {results['trip_reason']}")
            break
        elif t % 2 == 0:
            print(f"t={t}s: Operating normally, I={results['measurements']['current_percent']:.0f}%")
    
    relay.reset()
    
    # Test underfrequency load shedding
    print("\n\nTest 2: Underfrequency load shedding\n")
    
    for freq in [50.0, 49.6, 49.4, 49.1, 48.7]:
        results = relay.update(
            current_time=10.0,
            dt=1.0,
            line_current_a=800.0,
            bus_voltage_kv=400.0,
            frequency_hz=freq,
        )
        
        print(
            f"f={freq:.1f}Hz: Load shed = {results['load_shed_percent']:.0f}% "
            f"{'[TRIPPED]' if results['tripped'] else ''}"
        )
