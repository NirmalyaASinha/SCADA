"""
Indian Grid Load Profile
=========================

Implements realistic Indian power grid daily load curve.

Based on actual load data from GRID-INDIA/POSOCO (Power System Operation
Corporation Limited) which operates the Indian national grid.

Indian load characteristics (distinct from Western grids):
    1. Morning peak (09:00-11:00): ~70% of maximum
       - Industrial load ramp-up
       - Commercial establishments opening
    
    2. Afternoon dip (13:00-16:00): ~55% of maximum
       - Post-lunch reduction (siesta effect)
       - Higher in summer due to air conditioning
    
    3. Evening peak (19:00-22:00): 100% of maximum
       - Lighting load (sunset around 18:00-19:00)
       - Cooking load (dinner preparation)
       - Entertainment (TV peak viewing time)
    
    4. Night trough (02:00-05:00): ~30% of maximum
       - Minimal residential and commercial load
       - Some industrial base load continues
    
Seasonal variations:
    - Summer (Apr-Jun): +20% peak due to air conditioning
    - Monsoon (Jul-Sep): baseline
    - Autumn (Oct-Nov): +5% (festival season - Diwali)
    - Winter (Dec-Mar): -5% (lower AC load, some heating in north)

Weekly variations:
    - Weekend load: -15% (industrial reduction)
    - Monday morning: sharp ramp-up
    - Friday evening: extended peak (social activities)

Festival load patterns:
    - Diwali (Oct/Nov): 25% surge at 20:00 (lighting)
    - Holi (Mar): 15% surge
    - Eid: 10% evening surge

Solar generation impact:
    - Peak solar: 12:00-14:00
    - Duck curve effect: steep evening ramp when solar drops
    - Net load (total load - solar) shows different pattern

This model provides realistic load variation for training anomaly detection
models - abnormal load patterns are key signatures of cyber-physical attacks.
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict
import math
import sys
from pathlib import Path

# Add parent directory to path for imports
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from config import LOAD_PROFILE, SEASONAL_MULTIPLIERS, DISTRIBUTION_PEAK_LOAD_MW


class IndianLoadProfile:
    """
    Indian grid load profile generator.
    
    Generates realistic load variations:
    - Hourly profile based on time of day
    - Seasonal multipliers
    - Weekend/weekday differences
    - Festival load spikes
    - Random variations (±3% normal operation)
    """
    
    def __init__(self, base_time: datetime = None):
        """
        Initialize load profile generator.
        
        Args:
            base_time: Simulation start time (default: current time)
        """
        self.base_time = base_time or datetime.now()
    
    def get_load_factor(self, current_time: datetime) -> float:
        """
        Get load factor (0.0-1.0) for given time.
        
        Args:
            current_time: Current simulation time
        
        Returns:
            Load factor (1.0 = peak load, 0.3 = minimum load)
        """
        # Base hourly profile
        hour_key = f"{current_time.hour:02d}:00"
        base_factor = LOAD_PROFILE.get(hour_key, 0.5)
        
        # Seasonal multiplier
        month = current_time.month
        if 4 <= month <= 6:
            season = "summer"
        elif 7 <= month <= 9:
            season = "monsoon"
        elif 10 <= month <= 11:
            season = "autumn"
        else:
            season = "winter"
        
        seasonal_mult = SEASONAL_MULTIPLIERS[season]
        
        # Weekend reduction
        is_weekend = current_time.weekday() >= 5  # Saturday=5, Sunday=6
        weekend_mult = 0.85 if is_weekend else 1.0
        
        # Festival spike (simplified - check for Diwali-like patterns)
        festival_mult = self._get_festival_multiplier(current_time)
        
        # Combined factor
        load_factor = base_factor * seasonal_mult * weekend_mult * festival_mult
        
        # Add random variation (±3% for realistic fluctuation)
        noise = np.random.normal(0.0, 0.03)
        load_factor = load_factor * (1.0 + noise)
        
        # Clamp to reasonable range
        load_factor = np.clip(load_factor, 0.25, 1.3)
        
        return load_factor
    
    def _get_festival_multiplier(self, current_time: datetime) -> float:
        """
        Get festival load multiplier.
        
        Simplified: Diwali surge on Oct 20-30 around 20:00
        Real implementation would use actual festival calendar.
        """
        if current_time.month == 10 and 20 <= current_time.day <= 30:
            # Diwali period
            if 19 <= current_time.hour <= 22:
                # Peak lighting hours
                return 1.25
        elif current_time.month == 3 and 15 <= current_time.day <= 20:
            # Holi period
            if 18 <= current_time.hour <= 21:
                return 1.15
        
        return 1.0
    
    def get_node_load_mw(
        self,
        node_name: str,
        current_time: datetime,
    ) -> float:
        """
        Get load for a specific distribution node.
        
        Args:
            node_name: Distribution node (DIST-001 through DIST-005)
            current_time: Current simulation time
        
        Returns:
            Load in MW
        """
        if node_name not in DISTRIBUTION_PEAK_LOAD_MW:
            return 0.0
        
        peak_load_mw = DISTRIBUTION_PEAK_LOAD_MW[node_name]
        load_factor = self.get_load_factor(current_time)
        
        return peak_load_mw * load_factor
    
    def get_all_loads_mw(self, current_time: datetime) -> Dict[str, float]:
        """
        Get loads for all distribution nodes.
        
        Args:
            current_time: Current simulation time
        
        Returns:
            Dict mapping node name to load (MW)
        """
        loads = {}
        
        for node_name in DISTRIBUTION_PEAK_LOAD_MW.keys():
            loads[node_name] = self.get_node_load_mw(node_name, current_time)
        
        return loads
    
    def get_total_load_mw(self, current_time: datetime) -> float:
        """Get total system load (sum of all distribution nodes)."""
        loads = self.get_all_loads_mw(current_time)
        return sum(loads.values())


class SolarGenerationProfile:
    """
    Solar generation profile based on irradiance.
    
    Solar output follows:
    - Zero at night (sunset to sunrise)
    - Gaussian profile during day (peak at solar noon)
    - Cloud effects (random reduction)
    - Seasonal variation (sun angle)
    """
    
    def __init__(self, rated_capacity_mw: float):
        """
        Initialize solar profile.
        
        Args:
            rated_capacity_mw: Rated solar capacity (MW)
        """
        self.rated_capacity_mw = rated_capacity_mw
    
    def get_solar_output_mw(self, current_time: datetime) -> float:
        """
        Get solar generation output.
        
        Args:
            current_time: Current simulation time
        
        Returns:
            Solar output (MW)
        """
        hour = current_time.hour + current_time.minute / 60.0
        
        # Solar output only between 06:00 and 18:00
        if hour < 6.0 or hour > 18.0:
            return 0.0
        
        # Gaussian profile centered at solar noon (12:00)
        # Peak at 12:00, sigma = 3 hours
        solar_noon = 12.0
        sigma = 3.0
        
        # Gaussian irradiance profile
        irradiance_factor = math.exp(-((hour - solar_noon) ** 2) / (2 * sigma ** 2))
        
        # Seasonal variation (sun angle)
        month = current_time.month
        if 4 <= month <= 6:  # Summer - higher sun angle
            seasonal_factor = 1.0
        elif 7 <= month <= 9:  # Monsoon - clouds
            seasonal_factor = 0.7
        elif 10 <= month <= 11:  # Autumn
            seasonal_factor = 0.9
        else:  # Winter -lower sun angle
            seasonal_factor = 0.8
        
        # Cloud effects (random reduction, ±20%)
        cloud_factor = np.random.uniform(0.8, 1.0)
        
        output_mw = (
            self.rated_capacity_mw * 
            irradiance_factor * 
            seasonal_factor * 
            cloud_factor
        )
        
        return max(0.0, output_mw)
