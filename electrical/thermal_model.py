"""
Transformer Thermal Model (IEC 60076-7)
========================================

Implements thermal behavior of power transformers per IEC 60076-7 standard.

Transformers are the most critical and expensive components in substations.
Thermal overload is a primary failure mode. Real SCADA systems monitor
transformer temperatures continuously.

Physical Model:
    Heat generation in transformer is proportional to losses:
        - No-load losses (core): constant
        - Load losses (winding I^2*R): proportional to (load)^2
    
    Two thermal masses:
        1. Oil temperature (bulk oil temperature)
        2. Hot-spot temperature (winding hot-spot)
    
Top-Oil Temperature Dynamics:
    Differential equation governing oil heating:
    
    d(θ_oil)/dt = [(θ_oil_rated - θ_ambient) * (K^n - 1) - (θ_oil - θ_ambient)] / τ_oil
    
    Where:
        θ_oil = current top-oil temperature (°C)
        θ_oil_rated = rated top-oil temperature rise (°C)
        θ_ambient = ambient temperature (°C)
        K = actual load / rated load (per-unit loading)
        n = oil thermal exponent (typically 0.8)
        τ_oil = oil time constant (typically 180 minutes for large transformers)

Hot-Spot Temperature:
    Hot-spot is the winding hot-spot temperature (highest temperature point):
    
    θ_hs = θ_oil + H * Δθ_rated * K^(2m)
    
    Where:
        H = hot-spot factor (typically 1.1-1.3)
        Δθ_rated = rated winding hot-spot rise over oil (typically 23°C)
        m = winding thermal exponent (typically 0.8)

Protection Actions:
    - Alarm at θ_hs > 98°C (pre-trip warning)
    - Trip at θ_hs > 110°C (protection relay ANSI 49 thermal overload)
    
Real transformer thermal models are used to determine emergency loading
limits - can briefly overload during contingencies if thermal margin available.

Degradation Signature (for ML anomaly detection):
    Before failure, transformers show gradual temperature rise above model
    prediction due to insulation degradation, cooling system issues, or
    internal faults. This is a key pre-failure signature.
"""

import numpy as np
from typing import Dict
import logging
from dataclasses import dataclass
import sys
from pathlib import Path

# Add parent directory to path for imports
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from config import TRANSFORMER_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class TransformerThermalState:
    """Thermal state variables for a transformer."""
    node_name: str
    theta_oil_c: float  # Top-oil temperature (°C)
    theta_hs_c: float   # Hot-spot temperature (°C)
    loading_pu: float   # Current loading (per-unit of rated)
    alarm_active: bool = False
    trip_active: bool = False
    # Degradation simulation
    degradation_factor: float = 1.0  # 1.0 = healthy, >1.0 = degraded


class TransformerThermalModel:
    """
    IEC 60076-7 thermal model for power transformers.
    
    Monitors oil and hot-spot temperatures.
    Issues alarms and trips per protection settings.
    Simulates thermal degradation for ML training data.
    """
    
    def __init__(self, node_name: str):
        self.node_name = node_name
        self.config = TRANSFORMER_CONFIG
        
        # Initialize at ambient temperature (transformer cold)
        self.state = TransformerThermalState(
            node_name=node_name,
            theta_oil_c=self.config["theta_ambient_c"],
            theta_hs_c=self.config["theta_ambient_c"],
            loading_pu=0.0,
        )
        
        # Previous values for rate-of-change calculations
        self.theta_oil_prev = self.state.theta_oil_c
        
        logger.info(f"Thermal model initialized for {node_name}")
    
    def update(
        self,
        dt: float,
        loading_mva: float,
    ) -> Dict:
        """
        Update thermal state for one time step.
        
        Args:
            dt: Time step (seconds)
            loading_mva: Current transformer loading (MVA)
        
        Returns:
            results: Dict containing:
                - theta_oil_c: Top-oil temperature
                - theta_hs_c: Hot-spot temperature
                - loading_pu: Loading in per-unit
                - alarm_active: Temperature alarm status
                - trip_active: Temperature trip status
                - time_to_alarm_s: Estimated time to alarm (if trending up)
                - time_to_trip_s: Estimated time to trip (if trending up)
        
        Process:
            1. Calculate per-unit loading K = MVA_actual / MVA_rated
            2. Solve differential equation for top-oil temperature
            3. Calculate hot-spot temperature algebraically
            4. Check alarm and trip thresholds
        """
        
        rated_mva = self.config["rated_mva"]
        
        # Calculate per-unit loading
        K = loading_mva / rated_mva
        self.state.loading_pu = K
        
        # Apply degradation factor (increases effective thermal load)
        # Degraded transformer runs hotter for same loading
        K_degraded = K * self.state.degradation_factor
        
        # Top-oil temperature differential equation (discretized)
        # d(θ_oil)/dt = [Δθ_oil_rated * (K^n - 1) + (θ_ambient - θ_oil)] / τ_oil
        # where Δθ_oil_rated = θ_oil_rated - θ_ambient
        
        theta_ambient = self.config["theta_ambient_c"]
        theta_oil_rated = self.config["theta_oil_rated_c"]
        delta_theta_oil_rated = theta_oil_rated - theta_ambient
        
        n = self.config["oil_thermal_exponent_n"]
        tau_oil_min = self.config["oil_time_constant_min"]
        tau_oil_s = tau_oil_min * 60.0  # Convert to seconds
        
        # Temperature rise due to loading
        if K_degraded > 0:
            delta_theta_loading = delta_theta_oil_rated * (K_degraded ** n)
        else:
            delta_theta_loading = 0.0
        
        # Target oil temperature at this loading
        theta_oil_target = theta_ambient + delta_theta_loading
        
        # First-order lag towards target
        d_theta_oil_dt = (theta_oil_target - self.state.theta_oil_c) / tau_oil_s
        
        self.state.theta_oil_c += d_theta_oil_dt * dt
        
        # Hot-spot temperature calculation
        # θ_hs = θ_oil + H * Δθ_rated * K^(2m)
        H = self.config["hot_spot_factor_h"]
        m = self.config["winding_thermal_exponent_m"]
        delta_theta_rated = self.config["delta_theta_rated_c"]
        
        if K_degraded > 0:
            delta_theta_hs = H * delta_theta_rated * (K_degraded ** (2 * m))
        else:
            delta_theta_hs = 0.0
        
        self.state.theta_hs_c = self.state.theta_oil_c + delta_theta_hs
        
        # Check alarm and trip thresholds
        theta_hs_alarm = self.config["theta_hs_alarm_c"]
        theta_hs_trip = self.config["theta_hs_trip_c"]
        
        # Alarm logic (with hysteresis to prevent chattering)
        if self.state.theta_hs_c > theta_hs_alarm:
            if not self.state.alarm_active:
                logger.warning(
                    f"{self.node_name} THERMAL ALARM: "
                    f"Hot-spot temperature {self.state.theta_hs_c:.1f}°C "
                    f"exceeds alarm threshold {theta_hs_alarm}°C"
                )
            self.state.alarm_active = True
        elif self.state.theta_hs_c < theta_hs_alarm - 5.0:  # 5°C hysteresis
            if self.state.alarm_active:
                logger.info(f"{self.node_name} THERMAL ALARM CLEARED")
            self.state.alarm_active = False
        
        # Trip logic
        if self.state.theta_hs_c > theta_hs_trip:
            if not self.state.trip_active:
                logger.error(
                    f"{self.node_name} THERMAL TRIP: "
                    f"Hot-spot temperature {self.state.theta_hs_c:.1f}°C "
                    f"exceeds trip threshold {theta_hs_trip}°C"
                )
            self.state.trip_active = True
        elif self.state.theta_hs_c < theta_hs_trip - 10.0:  # 10°C hysteresis
            if self.state.trip_active:
                logger.info(f"{self.node_name} THERMAL TRIP RESET")
            self.state.trip_active = False
        
        # Estimate time to alarm/trip (if temperature trending upward)
        rate_of_rise = (self.state.theta_oil_c - self.theta_oil_prev) / dt if dt > 0 else 0.0
        self.theta_oil_prev = self.state.theta_oil_c
        
        if rate_of_rise > 0.01:  # 0.01 °C/s = 0.6 °C/min
            margin_to_alarm = theta_hs_alarm - self.state.theta_hs_c
            margin_to_trip = theta_hs_trip - self.state.theta_hs_c
            
            time_to_alarm_s = margin_to_alarm / rate_of_rise if margin_to_alarm > 0 else 0.0
            time_to_trip_s = margin_to_trip / rate_of_rise if margin_to_trip > 0 else 0.0
        else:
            time_to_alarm_s = float('inf')
            time_to_trip_s = float('inf')
        
        results = {
            "theta_oil_c": self.state.theta_oil_c,
            "theta_hs_c": self.state.theta_hs_c,
            "loading_pu": self.state.loading_pu,
            "loading_percent": self.state.loading_pu * 100.0,
            "alarm_active": self.state.alarm_active,
            "trip_active": self.state.trip_active,
            "time_to_alarm_s": time_to_alarm_s,
            "time_to_trip_s": time_to_trip_s,
            "rate_of_rise_c_per_min": rate_of_rise * 60.0,
            "degradation_factor": self.state.degradation_factor,
        }
        
        return results
    
    def set_degradation_factor(self, factor: float):
        """
        Set degradation factor to simulate aging transformer.
        
        Args:
            factor: Degradation multiplier (1.0 = healthy, >1.0 = degraded)
                    1.05 = 5% increase in thermal load (early degradation)
                    1.10 = 10% increase (moderate degradation)
                    1.20 = 20% increase (severe degradation, approaching failure)
        
        This simulates insulation degradation, cooling system issues, or
        partial internal faults that increase losses.
        """
        self.state.degradation_factor = max(1.0, factor)
        logger.info(
            f"{self.node_name} degradation factor set to {factor:.3f} "
            f"(thermal load increased by {(factor-1.0)*100:.1f}%)"
        )
    
    def get_thermal_margin(self) -> Dict:
        """
        Calculate thermal margins to alarm and trip.
        
        Returns:
            margins: Dict with margin_to_alarm_c, margin_to_trip_c
        """
        margin_to_alarm = self.config["theta_hs_alarm_c"] - self.state.theta_hs_c
        margin_to_trip = self.config["theta_hs_trip_c"] - self.state.theta_hs_c
        
        return {
            "margin_to_alarm_c": max(0.0, margin_to_alarm),
            "margin_to_trip_c": max(0.0, margin_to_trip),
            "thermal_capacity_remaining_percent": (margin_to_trip / 
                (self.config["theta_hs_trip_c"] - self.config["theta_ambient_c"]) * 100.0),
        }
    
    def calculate_emergency_load_limit(self, duration_minutes: float) -> float:
        """
        Calculate maximum permissible emergency loading for given duration.
        
        Emergency loading allows brief overload if thermal margin available.
        
        Args:
            duration_minutes: Emergency duration (minutes)
        
        Returns:
            max_loading_pu: Maximum safe loading (per-unit)
        
        This calculation is standard practice in grid operations - operators
        can push transformers beyond nameplate during N-1 contingencies if
        thermal model shows headroom.
        """
        # Simplified: assume linear thermal response
        # True emergency loading tables use exponential thermal response
        
        theta_hs_limit = self.config["theta_hs_trip_c"] - 5.0  # 5°C safety margin
        theta_ambient = self.config["theta_ambient_c"]
        
        # Current thermal state
        current_margin = theta_hs_limit - self.state.theta_hs_c
        
        # Estimate loading that would reach limit in given duration
        # This is a simplified calculation - real emergency loading uses
        # IEC 60076-7 full transient thermal model
        
        tau_oil_min = self.config["oil_time_constant_min"]
        
        # Time constant ratio
        time_ratio = duration_minutes / tau_oil_min
        
        # Approximate emergency loading (empirical formula)
        if time_ratio < 0.1:
            # Very short duration - can significantly overload
            emergency_mult = 1.5
        elif time_ratio < 0.5:
            emergency_mult = 1.3
        else:
            emergency_mult = 1.15
        
        max_loading_pu = emergency_mult * (1.0 - self.state.loading_pu) + self.state.loading_pu
        
        # Safety limit: never exceed 150% of rated
        max_loading_pu = min(max_loading_pu, 1.5)
        
        return max_loading_pu


if __name__ == "__main__":
    # Test t transformer thermal model
    logging.basicConfig(level=logging.DEBUG)
    
    thermal = TransformerThermalModel("SUB-001")
    
    print("\n===== TRANSFORMER THERMAL MODEL TEST =====\n")
    print(f"Rated MVA: {TRANSFORMER_CONFIG['rated_mva']} MVA")
    print(f"Rated oil temp: {TRANSFORMER_CONFIG['theta_oil_rated_c']}°C")
    print(f"Alarm threshold: {TRANSFORMER_CONFIG['theta_hs_alarm_c']}°C")
    print(f"Trip threshold: {TRANSFORMER_CONFIG['theta_hs_trip_c']}°C\n")
    
    print("Simulating 120% overload for 30 minutes...\n")
    
    # Simulate overload scenario
    loading_mva = 120.0  # 120% of 100 MVA rated
    dt = 60.0  # 1-minute time steps
    
    for minute in range(0, 181, 5):  # 3 hours
        if minute == 30:
            loading_mva = 100.0  # Return to rated load
            print(f"\n[Minute {minute}] Load reduced to rated (100 MVA)\n")
        
        results = thermal.update(dt=dt, loading_mva=loading_mva)
        
        if minute % 10 == 0:
            print(
                f"t={minute:3d}min: θ_oil={results['theta_oil_c']:5.1f}°C, "
                f"θ_hs={results['theta_hs_c']:5.1f}°C, "
                f"Load={results['loading_percent']:5.1f}% "
                f"{'[ALARM]' if results['alarm_active'] else ''}"
                f"{'[TRIP]' if results['trip_active'] else ''}"
            )
    
    print("\nThermal margins:")
    margins = thermal.get_thermal_margin()
    print(f"  Margin to alarm: {margins['margin_to_alarm_c']:.1f}°C")
    print(f"  Margin to trip: {margins['margin_to_trip_c']:.1f}°C")
    print(f"  Thermal capacity remaining: {margins['thermal_capacity_remaining_percent']:.1f}%")
    
    print("\nEmergency loading limits:")
    for duration in [5, 15, 30, 60]:
        limit_pu = thermal.calculate_emergency_load_limit(duration)
        print(f"  {duration:3d} minutes: {limit_pu:.2f} p.u. ({limit_pu*100:.0f}%)")
