"""
SCADA Simulation Configuration
Production-faithful configuration reflecting real Indian power grid parameters
"""

import os
from typing import Dict, List, Tuple

# ==================== GRID TOPOLOGY ====================

# System base values for per-unit calculations
SYSTEM_BASE_MVA = 100.0  # 100 MVA base power
NOMINAL_FREQUENCY_HZ = 50.0  # Indian grid nominal frequency
NOMINAL_VOLTAGE_KV = {
    "GENERATION": 400.0,      # Generator terminal voltage (kV)
    "TRANSMISSION": 400.0,    # Transmission bus voltage (kV)
    "DISTRIBUTION": 132.0,    # Distribution bus voltage (kV)
}

# Line impedance matrix (R, X, B in per-unit on 100 MVA base)
# Format: (from_bus, to_bus): (R_pu, X_pu, B_pu)
LINE_IMPEDANCES: Dict[Tuple[str, str], Tuple[float, float, float]] = {
    ("GEN-001", "SUB-001"): (0.02, 0.06, 0.03),
    ("GEN-001", "SUB-002"): (0.03, 0.09, 0.02),
    ("GEN-002", "SUB-003"): (0.02, 0.07, 0.025),
    ("GEN-002", "SUB-004"): (0.04, 0.11, 0.02),
    ("GEN-003", "SUB-005"): (0.025, 0.08, 0.03),
    ("GEN-003", "SUB-006"): (0.03, 0.09, 0.025),
    ("GEN-003", "SUB-007"): (0.02, 0.06, 0.02),
    ("SUB-001", "DIST-001"): (0.05, 0.12, 0.01),
    ("SUB-002", "DIST-001"): (0.06, 0.13, 0.01),
    ("SUB-003", "DIST-002"): (0.04, 0.10, 0.015),
    ("SUB-004", "DIST-002"): (0.05, 0.11, 0.01),
    ("SUB-004", "DIST-003"): (0.06, 0.14, 0.01),
    ("SUB-005", "DIST-003"): (0.04, 0.10, 0.015),
    ("SUB-006", "DIST-004"): (0.05, 0.12, 0.01),
    ("SUB-007", "DIST-005"): (0.04, 0.11, 0.01),
}

# Node configuration
NODE_CONFIG = {
    "GENERATION": ["GEN-001", "GEN-002", "GEN-003"],
    "TRANSMISSION": ["SUB-001", "SUB-002", "SUB-003", "SUB-004", "SUB-005", "SUB-006", "SUB-007"],
    "DISTRIBUTION": ["DIST-001", "DIST-002", "DIST-003", "DIST-004", "DIST-005"],
}

ALL_NODES = (
    NODE_CONFIG["GENERATION"] + 
    NODE_CONFIG["TRANSMISSION"] + 
    NODE_CONFIG["DISTRIBUTION"]
)

# ==================== ELECTRICAL PARAMETERS ====================

# Generator parameters
GENERATOR_CONFIG = {
    "GEN-001": {
        "type": "coal",
        "rated_mw": 500.0,
        "min_mw": 150.0,
        "max_mw": 500.0,
        "inertia_constant_h": 6.0,  # seconds (thermal plant)
        "droop_r": 0.05,  # 5% droop
        "governor_time_constant_s": 0.5,
        "ramp_rate_mw_per_min": 10.0,
        "cost_curve": {"a": 0.004, "b": 20, "c": 100},  # Rs/MWh: a*P^2 + b*P + c
        "reactive_capability": {"min_pf_lag": 0.85, "max_pf_lead": 0.95},
    },
    "GEN-002": {
        "type": "hydro",
        "rated_mw": 300.0,
        "min_mw": 30.0,
        "max_mw": 300.0,
        "inertia_constant_h": 3.0,  # seconds (hydro plant)
        "droop_r": 0.05,
        "governor_time_constant_s": 0.3,
        "ramp_rate_mw_per_min": 50.0,  # Hydro can ramp faster
        "cost_curve": {"a": 0.001, "b": 10, "c": 50},
        "reactive_capability": {"min_pf_lag": 0.85, "max_pf_lead": 0.95},
    },
    "GEN-003": {
        "type": "solar",
        "rated_mw": 200.0,
        "min_mw": 0.0,
        "max_mw": 200.0,
        "inertia_constant_h": 0.0,  # Solar has no rotational inertia
        "droop_r": 0.0,  # Solar doesn't participate in frequency regulation
        "governor_time_constant_s": 0.0,
        "ramp_rate_mw_per_min": 100.0,  # Limited by inverter response
        "cost_curve": {"a": 0.0, "b": 0.0, "c": 0.0},  # Zero marginal cost
        "reactive_capability": {"min_pf_lag": 0.90, "max_pf_lead": 0.90},
    },
}

# Transformer parameters (IEC 60076-7 thermal model)
TRANSFORMER_CONFIG = {
    "rated_mva": 100.0,
    "rated_voltage_hv_kv": 400.0,
    "rated_voltage_lv_kv": 132.0,
    "turns_ratio": 400.0 / 132.0,
    "oil_time_constant_min": 180.0,  # Oil thermal time constant
    "oil_thermal_exponent_n": 0.8,
    "hot_spot_factor_h": 1.3,
    "winding_thermal_exponent_m": 0.8,
    "delta_theta_rated_c": 23.0,  # Rated winding hot-spot rise over oil
    "theta_ambient_c": 35.0,  # Indian ambient temperature (conservative)
    "theta_oil_rated_c": 75.0,  # Rated top-oil temperature
    "theta_hs_alarm_c": 98.0,  # Hot-spot alarm threshold
    "theta_hs_trip_c": 110.0,  # Hot-spot trip threshold
}

# OLTC (On-Load Tap Changer) parameters
OLTC_CONFIG = {
    "tap_positions": 17,
    "tap_nominal": 9,  # Middle position
    "tap_step_percent": 1.25,  # 1.25% per step
    "voltage_deadband_percent": 1.0,  # No action within +-1%
    "tap_delay_s": (30, 45),  # Random delay between 30-45 seconds
    "max_operations_per_10min": 3,  # Mechanical wear protection
    "voltage_target_pu": 1.0,  # Per-unit voltage target
}

# Protection relay parameters (ANSI device numbers)
PROTECTION_CONFIG = {
    "ANSI_51": {  # Overcurrent
        "name": "Overcurrent Protection",
        "pickup_percent": 120.0,  # 120% of rated current
        "time_multiplier": 0.5,
        "curve_exponent": 0.02,  # IEC Standard Inverse
        "min_trip_time_s": 5.0,
    },
    "ANSI_59": {  # Overvoltage
        "name": "Overvoltage Protection",
        "pickup_percent": 110.0,  # 110% of nominal
        "trip_delay_s": 2.0,
    },
    "ANSI_27": {  # Undervoltage
        "name": "Undervoltage Protection",
        "pickup_percent": 85.0,  # 85% of nominal
        "trip_delay_s": 3.0,
    },
    "ANSI_81": {  # Underfrequency Load Shedding
        "name": "Underfrequency Load Shedding",
        "stages": [
            {"frequency_hz": 49.5, "delay_s": 0.5, "shed_percent": 10.0},
            {"frequency_hz": 49.2, "delay_s": 0.5, "shed_percent": 15.0},
            {"frequency_hz": 48.8, "delay_s": 0.5, "shed_percent": 20.0},
        ],
    },
    "ANSI_87T": {  # Transformer Differential
        "name": "Transformer Differential Protection",
        "pickup_percent": 20.0,  # 20% differential current
        "restraint_slope": 0.5,
    },
}

# ==================== FREQUENCY DYNAMICS ====================

# AGC (Automatic Generation Control) parameters
AGC_CONFIG = {
    "frequency_bias_mw_per_hz": 20.0,  # B parameter
    "control_interval_s": 4.0,
    "proportional_gain": 0.1,
    "integral_gain": 0.01,
    "max_rate_mw_per_min": 50.0,
}

# Indian grid frequency operating parameters
FREQUENCY_CONFIG = {
    "nominal_hz": 50.0,
    "normal_band_min_hz": 49.7,
    "normal_band_max_hz": 50.3,
    "emergency_min_hz": 48.8,
    "emergency_max_hz": 51.5,
}

# ==================== INDIAN LOAD PROFILE ====================

# Load profile parameters (percentage of peak load)
LOAD_PROFILE = {
    "00:00": 0.30, "01:00": 0.28, "02:00": 0.30, "03:00": 0.32,
    "04:00": 0.35, "05:00": 0.45, "06:00": 0.60, "07:00": 0.68,
    "08:00": 0.70, "09:00": 0.72, "10:00": 0.70, "11:00": 0.68,
    "12:00": 0.60, "13:00": 0.55, "14:00": 0.55, "15:00": 0.58,
    "16:00": 0.62, "17:00": 0.70, "18:00": 0.85, "19:00": 0.95,
    "20:00": 1.00, "21:00": 0.95, "22:00": 0.75, "23:00": 0.50,
}

# Seasonal load multipliers
SEASONAL_MULTIPLIERS = {
    "summer": 1.20,  # Apr-Jun (air conditioning)
    "monsoon": 1.00,  # Jul-Sep
    "autumn": 1.05,  # Oct-Nov
    "winter": 0.95,  # Dec-Mar
}

# Peak load per distribution node (MW)
DISTRIBUTION_PEAK_LOAD_MW = {
    "DIST-001": 150.0,
    "DIST-002": 120.0,
    "DIST-003": 100.0,
    "DIST-004": 80.0,
    "DIST-005": 90.0,
}

# ==================== EQUIPMENT FAILURE PARAMETERS ====================

# IEEE Std 493 (Gold Book) reliability data
RELIABILITY_CONFIG = {
    "TRANSFORMER": {
        "mtbf_years": 40.0,
        "mttr_hours": 200.0,
        "weibull_beta": 2.5,
        "failure_modes": {
            "winding_failure": 0.40,
            "bushing_failure": 0.20,
            "oltc_failure": 0.15,
            "core_fault": 0.10,
            "cooling_system": 0.15,
        },
    },
    "BREAKER": {
        "mtbf_years": 30.0,
        "mttr_hours": 120.0,
        "weibull_beta": 2.5,
        "failure_modes": {
            "fail_to_open": 0.30,  # Most dangerous
            "fail_to_close": 0.25,
            "spurious_trip": 0.45,
        },
    },
    "RTU": {
        "mtbf_years": 5.0,
        "mttr_hours": 4.0,
        "weibull_beta": 1.5,
        "failure_modes": {
            "communication_loss": 1.0,
        },
    },
}

# ==================== PROTOCOL CONFIGURATION ====================

# Modbus TCP configuration
MODBUS_CONFIG = {
    "port": 502,
    "unit_id_map": {
        "GEN-001": 1, "GEN-002": 2, "GEN-003": 3,
        "SUB-001": 4, "SUB-002": 5, "SUB-003": 6, "SUB-004": 7,
        "SUB-005": 8, "SUB-006": 9, "SUB-007": 10,
        "DIST-001": 11, "DIST-002": 12, "DIST-003": 13,
        "DIST-004": 14, "DIST-005": 15,
    },
    "poll_interval_critical_s": 2.0,
    "poll_interval_normal_s": 10.0,
    "poll_interval_discrete_s": 0.5,
    "max_response_time_ms": 200,
    "response_times_ms": {  # Realistic RTU processing delays
        "FC01": (8, 15),    # Read Coils
        "FC03": (12, 25),   # Read Holding Registers
        "FC05": (15, 30),   # Write Single Coil
        "FC06": (15, 30),   # Write Single Register
        "FC16": (20, 40),   # Write Multiple Registers
    },
}

# IEC 60870-5-104 configuration
IEC104_CONFIG = {
    "port": 2404,
    "common_address_map": MODBUS_CONFIG["unit_id_map"],  # Same mapping
    "t1_timeout_s": 15,  # Response timeout
    "t2_timeout_s": 10,  # Acknowledgment timeout
    "t3_timeout_s": 20,  # Test frame interval
    "k_window": 12,      # Max unacknowledged APDUs
    "w_window": 8,       # Latest acknowledgment after w APDUs
    "deadbands": {
        "bus_voltage_kv_percent": 0.5,
        "line_current_a_percent": 1.0,
        "active_power_mw_percent": 0.5,
        "frequency_hz_absolute": 0.01,
    },
}

# DNP3 configuration
DNP3_CONFIG = {
    "port": 20000,
    "address_map": MODBUS_CONFIG["unit_id_map"],
    "unsolicited_enabled": True,
    "max_event_buffer": 100,
    "class_poll_intervals_s": {
        "class0": 900,  # 15 minutes (integrity poll)
        "class1": 0.5,  # High priority events
        "class2": 2.0,  # Normal priority events
        "class3": 10.0, # Low priority events
    },
}

# ==================== NETWORK TOPOLOGY ====================

NETWORK_CONFIG = {
    "OCC": "10.0.0.1",
    "GENERATION_SUBNET": "10.1.1.0/24",
    "TRANSMISSION_SUBNET": "10.2.1.0/24",
    "DISTRIBUTION_SUBNET": "10.3.1.0/24",
    "IP_MAP": {
        "GEN-001": "10.1.1.1", "GEN-002": "10.1.1.2", "GEN-003": "10.1.1.3",
        "SUB-001": "10.2.1.1", "SUB-002": "10.2.1.2", "SUB-003": "10.2.1.3",
        "SUB-004": "10.2.1.4", "SUB-005": "10.2.1.5", "SUB-006": "10.2.1.6",
        "SUB-007": "10.2.1.7",
        "DIST-001": "10.3.1.1", "DIST-002": "10.3.1.2", "DIST-003": "10.3.1.3",
        "DIST-004": "10.3.1.4", "DIST-005": "10.3.1.5",
    },
    "BACKUP_LATENCY_MS": (200, 500),  # GPRS backup latency
    "BACKUP_PACKET_LOSS_PERCENT": 2.0,
    "FAILOVER_TIME_S": 30.0,
}

# ==================== HISTORIAN CONFIGURATION ====================

HISTORIAN_CONFIG = {
    "api_port": 8001,
    "raw_retention_days": 7,
    "compressed_retention_days": 365,
    "archive_retention_days": 1825,  # 5 years
    "chunk_interval_hours": 24,
    "compression_after_days": 7,
    "aggregate_intervals": ["1m", "1h"],
}

# ==================== DATABASE CONFIGURATION ====================

DATABASE_CONFIG = {
    "host": os.getenv("DB_HOST", "timescaledb"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "database": os.getenv("DB_NAME", "scada_historian"),
    "user": os.getenv("DB_USER", "scada_user"),
    "password": os.getenv("DB_PASSWORD", "scada_password"),
    "pool_size": 20,
    "max_overflow": 10,
}

# ==================== ALARM MANAGEMENT (IEC 62682) ====================

ALARM_CONFIG = {
    "priorities": {
        1: {
            "name": "CRITICAL",
            "description": "Requires immediate operator action",
            "response_time_s": 0,
            "examples": ["Protection trip", "Bus fault", "Generation loss > 100MW"],
        },
        2: {
            "name": "HIGH",
            "description": "Requires prompt action within 10 minutes",
            "response_time_s": 600,
            "examples": ["Overtemperature", "Voltage out of limits", "Communication failure"],
        },
        3: {
            "name": "MEDIUM",
            "description": "Requires action within 1 hour",
            "response_time_s": 3600,
            "examples": ["Tap changer at limit", "High load"],
        },
        4: {
            "name": "LOW",
            "description": "Informational",
            "response_time_s": None,
            "examples": ["Scheduled switching", "Tap change operation"],
        },
    },
    "flood_threshold_per_minute": 10,
}

# ==================== SIMULATION PARAMETERS ====================

SIMULATION_CONFIG = {
    "time_step_s": 1.0,  # 1-second resolution for electrical simulation
    "power_flow_interval_s": 5.0,  # Run power flow solver every 5 seconds
    "enable_failures": True,
    "enable_degradation": True,
    "start_time": None,  # Will be set to current time on startup
    "time_acceleration": 1.0,  # Real-time (set > 1.0 for faster simulation)
}

# ==================== LOGGING CONFIGURATION ====================

LOGGING_CONFIG = {
    "level": os.getenv("LOG_LEVEL", "INFO"),
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "handlers": ["console", "file"],
    "file_path": "/var/log/scada_sim/simulator.log",
}

# ==================== DATA QUALITY FLAGS (IEC 61968) ====================

DATA_QUALITY = {
    "GOOD": 0x00,        # Value is valid and current
    "SUSPECT": 0x01,     # Value may be stale or uncertain
    "BAD": 0x02,         # Communication or sensor failure
    "OVERFLOW": 0x04,    # Value exceeds sensor range
    "UNDERRANGE": 0x08,  # Value below sensor minimum
}
