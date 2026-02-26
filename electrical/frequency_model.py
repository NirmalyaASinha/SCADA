"""
Frequency Dynamics Model
========================

Implements system frequency behavior based on swing equation and governor response.

Physical basis:
    System frequency is a global quantity - all synchronous generators share
    the same frequency. Frequency deviation results from power imbalance:
    
    When Generation > Load: frequency rises
    When Generation < Load: frequency falls
    
Swing Equation (per-unit):
    df/dt = (P_mech - P_elec) / (2 * H * f_nom)
    
Where:
    f = system frequency (Hz)
    P_mech = mechanical power input to generators
    P_elec = electrical power output (load + losses)
    H = system inertia constant (seconds)
    f_nom = nominal frequency (50 Hz for India)

Primary Frequency Response:
    Generators automatically adjust output through governor droop control:
    ΔP = -(1/R) * Δf
    
Where:
    R = droop coefficient (typically 0.05 = 5% droop)
    
A 5% droop means a 5% frequency change (2.5 Hz) causes 100% power change.
In practice: 0.1 Hz drop → 2% power increase.

Governor Dynamics:
    Governors have first-order lag response:
    dP_mech/dt = (P_setpoint - P_mech) / T_g
    
Where T_g = governor time constant (0.3-0.5s for hydro, 0.5-0.8s for thermal)

AGC (Automatic Generation Control):
    Slower secondary control (4-second intervals) to return frequency to 50 Hz:
    ACE = ΔP_tie + B * Δf  (Area Control Error)
    
Where:
    ΔP_tie = net tie-line power deviation (0 for island grid)
    B = frequency bias factor (MW/Hz)
    
AGC sends raise/lower pulses to generators to eliminate ACE.

This model is critical for realistic SCADA behavior - real grid operators
monitor frequency in real-time and it's the primary indicator of grid health.
"""

import numpy as np
from typing import Dict, List
import logging
from dataclasses import dataclass
import sys
from pathlib import Path

# Add parent directory to path for imports
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    GENERATOR_CONFIG,
    FREQUENCY_CONFIG,
    AGC_CONFIG,
    NOMINAL_FREQUENCY_HZ,
)

logger = logging.getLogger(__name__)


@dataclass
class GeneratorState:
    """State variables for a single generator."""
    node_name: str
    P_setpoint_mw: float  # AGC setpoint
    P_mech_mw: float      # Mechanical power (governor output)
    P_elec_mw: float      # Electrical power (actual output)
    governor_time_constant_s: float
    inertia_constant_h: float
    droop_r: float
    participating_in_agc: bool = True


class FrequencyModel:
    """
    System-wide frequency dynamics model.
    
    Simulates:
    - Swing equation for frequency deviation
    - Governor droop response (primary control)
    - AGC raise/lower pulses (secondary control)
    
    Real Indian grid characteristics:
    - Wider frequency tolerance (49.7-50.3 Hz vs European 49.8-50.2 Hz)
    - Characteristic frequency dips during peak demand hours
    - Under-frequency load shedding at 49.5/49.2/48.8 Hz
    """
    
    def __init__(self, generators: List[str]):
        self.generators = generators
        self.generator_states: Dict[str, GeneratorState] = {}
        
        # System frequency state
        self.frequency_hz = NOMINAL_FREQUENCY_HZ
        self.frequency_target_hz = NOMINAL_FREQUENCY_HZ
        
        # AGC state
        self.agc_integral = 0.0
        self.last_agc_time = 0.0
        
        # Initialize generator states
        self._initialize_generators()
        
        logger.info(f"Frequency model initialized with {len(generators)} generators")
    
    def _initialize_generators(self):
        """Initialize state for each generator."""
        for gen_name in self.generators:
            config = GENERATOR_CONFIG[gen_name]
            
            # Initial setpoint at mid-range
            P_initial = (config["min_mw"] + config["max_mw"]) / 2.0
            
            self.generator_states[gen_name] = GeneratorState(
                node_name=gen_name,
                P_setpoint_mw=P_initial,
                P_mech_mw=P_initial,
                P_elec_mw=P_initial,
                governor_time_constant_s=config["governor_time_constant_s"],
                inertia_constant_h=config["inertia_constant_h"],
                droop_r=config["droop_r"],
                participating_in_agc=(config["type"] != "solar"),  # Solar doesn't do AGC
            )
    
    def update(
        self,
        dt: float,
        total_load_mw: float,
        total_losses_mw: float,
        current_time: float,
    ) -> Dict:
        """
        Update frequency and governor response for one time step.
        
        Args:
            dt: Time step (seconds)
            total_load_mw: Total system load (MW)
            total_losses_mw: Total system losses (MW)
            current_time: Simulation time (seconds since start)
        
        Returns:
            results: Dict containing:
                - frequency_hz: Updated system frequency
                - generator_outputs_mw: Dict of generator electrical outputs
                - frequency_deviation_hz: Deviation from nominal
                - rocof: Rate of change of frequency (Hz/s)
        
        Process:
            1. Calculate total mechanical power from all generators
            2. Calculate total electrical power (load + losses)
            3. Update frequency via swing equation
            4. Update each governor (primary response)
            5. Run AGC if interval elapsed (secondary response)
        """
        
        # Calculate system inertia constant (weighted by generator capacity)
        total_inertia = 0.0
        total_capacity = 0.0
        
        for gen_state in self.generator_states.values():
            config = GENERATOR_CONFIG[gen_state.node_name]
            rated_mw = config["rated_mw"]
            H = gen_state.inertia_constant_h
            
            # Inertia contribution weighted by capacity
            # (Solar has H=0, doesn't contribute to inertia)
            total_inertia += H * rated_mw
            total_capacity += rated_mw
        
        # System inertia constant (seconds)
        if total_capacity > 0:
            H_system = total_inertia / total_capacity
        else:
            H_system = 5.0  # Default fallback
        
        # Calculate total mechanical and electrical power
        P_mechanical_total = sum(
            gen_state.P_mech_mw for gen_state in self.generator_states.values()
        )
        P_electrical_total = total_load_mw + total_losses_mw
        
        # Power imbalance
        power_imbalance_mw = P_mechanical_total - P_electrical_total
        
        # Swing equation: df/dt = (P_mech - P_elec) / (2 * H * f_nom)
        # Convert to per-unit: P_imbalance_pu = power_imbalance_mw / total_capacity
        P_imbalance_pu = power_imbalance_mw / total_capacity if total_capacity > 0 else 0.0
        
        # Rate of change of frequency (Hz/s)
        # df/dt = f_nom * P_imbalance_pu / (2 * H)
        if H_system > 0:
            rocof = NOMINAL_FREQUENCY_HZ * P_imbalance_pu / (2.0 * H_system)
        else:
            rocof = 0.0
        
        # Limit ROCOF to realistic values (real grids: ±1 Hz/s is extreme event)
        rocof = np.clip(rocof, -1.0, 1.0)
        
        # Update frequency
        frequency_old = self.frequency_hz
        self.frequency_hz += rocof * dt
        
        # Limit frequency to physical bounds
        self.frequency_hz = np.clip(
            self.frequency_hz,
            FREQUENCY_CONFIG["emergency_min_hz"],
            FREQUENCY_CONFIG["emergency_max_hz"],
        )
        
        # Frequency deviation from nominal
        freq_deviation_hz = self.frequency_hz - NOMINAL_FREQUENCY_HZ
        
        # Update each generator's governor response (primary control)
        generator_outputs_mw = {}
        
        for gen_name, gen_state in self.generator_states.items():
            config = GENERATOR_CONFIG[gen_name]
            
            # Governor droop response: ΔP = -(1/R) * Δf
            # Negative sign: frequency drops → power increases
            if gen_state.droop_r > 0:
                droop_response_mw = -(1.0 / gen_state.droop_r) * freq_deviation_hz * config["rated_mw"]
            else:
                droop_response_mw = 0.0
            
            # Target mechanical power = setpoint + droop response
            P_target_mw = gen_state.P_setpoint_mw + droop_response_mw
            
            # Enforce generator limits
            P_target_mw = np.clip(P_target_mw, config["min_mw"], config["max_mw"])
            
            # Governor first-order lag: dP/dt = (P_target - P_mech) / T_g
            if gen_state.governor_time_constant_s > 0:
                dP_dt = (P_target_mw - gen_state.P_mech_mw) / gen_state.governor_time_constant_s
                gen_state.P_mech_mw += dP_dt * dt
            else:
                # Instantaneous response (solar inverters)
                gen_state.P_mech_mw = P_target_mw
            
            # Electrical output equals mechanical input (neglecting generator losses)
            gen_state.P_elec_mw = gen_state.P_mech_mw
            
            generator_outputs_mw[gen_name] = gen_state.P_elec_mw
        
        # Run AGC (secondary control) every 4 seconds
        if current_time - self.last_agc_time >= AGC_CONFIG["control_interval_s"]:
            self._run_agc(freq_deviation_hz, dt)
            self.last_agc_time = current_time
        
        results = {
            "frequency_hz": self.frequency_hz,
            "frequency_deviation_hz": freq_deviation_hz,
            "rocof_hz_per_s": rocof,
            "generator_outputs_mw": generator_outputs_mw,
            "power_imbalance_mw": power_imbalance_mw,
            "system_inertia_s": H_system,
        }
        
        # Log significant frequency deviations
        if abs(freq_deviation_hz) > 0.2:
            logger.warning(
                f"Frequency deviation: {freq_deviation_hz:+.3f} Hz "
                f"(f={self.frequency_hz:.3f} Hz, ROCOF={rocof:.4f} Hz/s)"
            )
        
        return results
    
    def _run_agc(self, freq_deviation_hz: float, dt: float):
        """
        Run AGC (Automatic Generation Control) to eliminate frequency error.
        
        AGC uses PI (Proportional-Integral) control:
            ACE = ΔP_tie + B * Δf
            Control signal = K_p * ACE + K_i * ∫ACE dt
        
        For island grid (no tie lines): ACE = B * Δf
        
        Distributes raise/lower commands to AGC-participating generators.
        """
        # Area Control Error (for island grid, just frequency component)
        freq_bias = AGC_CONFIG["frequency_bias_mw_per_hz"]
        ACE = freq_bias * freq_deviation_hz
        
        # PI control
        K_p = AGC_CONFIG["proportional_gain"]
        K_i = AGC_CONFIG["integral_gain"]
        
        # Update integral term
        self.agc_integral += ACE * AGC_CONFIG["control_interval_s"]
        
        # Anti-windup: limit integral term
        self.agc_integral = np.clip(self.agc_integral, -100.0, 100.0)
        
        # Control signal (MW to be distributed)
        control_signal_mw = -(K_p * ACE + K_i * self.agc_integral)
        
        # Limit rate of change
        max_rate = AGC_CONFIG["max_rate_mw_per_min"] * (AGC_CONFIG["control_interval_s"] / 60.0)
        control_signal_mw = np.clip(control_signal_mw, -max_rate, max_rate)
        
        # Distribute control signal among AGC-participating generators
        # (proportional to their remaining headroom)
        agc_generators = [
            (name, state) for name, state in self.generator_states.items()
            if state.participating_in_agc
        ]
        
        if not agc_generators:
            return
        
        # Calculate headroom for each generator
        total_headroom_up = 0.0
        total_headroom_down = 0.0
        
        for gen_name, gen_state in agc_generators:
            config = GENERATOR_CONFIG[gen_name]
            headroom_up = config["max_mw"] - gen_state.P_setpoint_mw
            headroom_down = gen_state.P_setpoint_mw - config["min_mw"]
            total_headroom_up += max(0, headroom_up)
            total_headroom_down += max(0, headroom_down)
        
        # Distribute raise/lower signal
        for gen_name, gen_state in agc_generators:
            config = GENERATOR_CONFIG[gen_name]
            
            if control_signal_mw > 0:  # Raise generation
                if total_headroom_up > 0:
                    headroom = config["max_mw"] - gen_state.P_setpoint_mw
                    fraction = max(0, headroom) / total_headroom_up
                    delta_mw = control_signal_mw * fraction
                    gen_state.P_setpoint_mw += delta_mw
                    gen_state.P_setpoint_mw = min(gen_state.P_setpoint_mw, config["max_mw"])
            
            elif control_signal_mw < 0:  # Lower generation
                if total_headroom_down > 0:
                    headroom = gen_state.P_setpoint_mw - config["min_mw"]
                    fraction = max(0, headroom) / total_headroom_down
                    delta_mw = control_signal_mw * fraction
                    gen_state.P_setpoint_mw += delta_mw
                    gen_state.P_setpoint_mw = max(gen_state.P_setpoint_mw, config["min_mw"])
        
        if abs(control_signal_mw) > 1.0:
            logger.debug(
                f"AGC: ACE={ACE:.2f} MW, Control={control_signal_mw:.2f} MW, "
                f"Δf={freq_deviation_hz:+.3f} Hz"
            )
    
    def set_generator_setpoint(self, gen_name: str, setpoint_mw: float):
        """
        Manually set generator setpoint (operator control).
        
        Args:
            gen_name: Generator node name
            setpoint_mw: Desired power setpoint (MW)
        """
        if gen_name in self.generator_states:
            config = GENERATOR_CONFIG[gen_name]
            setpoint_mw = np.clip(setpoint_mw, config["min_mw"], config["max_mw"])
            self.generator_states[gen_name].P_setpoint_mw = setpoint_mw
            logger.info(f"{gen_name} setpoint changed to {setpoint_mw:.1f} MW")
    
    def get_frequency_status(self) -> Dict:
        """
        Get current frequency status with operational classification.
        
        Returns:
            status: Dict with frequency, deviation, status classification
        """
        freq = self.frequency_hz
        
        # Classify frequency status per Indian grid code
        if FREQUENCY_CONFIG["normal_band_min_hz"] <= freq <= FREQUENCY_CONFIG["normal_band_max_hz"]:
            status = "NORMAL"
        elif FREQUENCY_CONFIG["emergency_min_hz"] <= freq < FREQUENCY_CONFIG["normal_band_min_hz"]:
            status = "LOW"
        elif FREQUENCY_CONFIG["normal_band_max_hz"] < freq <= FREQUENCY_CONFIG["emergency_max_hz"]:
            status = "HIGH"
        else:
            status = "EMERGENCY"
        
        return {
            "frequency_hz": freq,
            "frequency_deviation_hz": freq - NOMINAL_FREQUENCY_HZ,
            "status": status,
            "requires_load_shedding": freq < 49.5,  # First UFLS stage
        }


if __name__ == "__main__":
    # Test frequency model
    logging.basicConfig(level=logging.DEBUG)
    
    generators = ["GEN-001", "GEN-002", "GEN-003"]
    freq_model = FrequencyModel(generators)
    
    # Simulate sudden load increase (frequency drop scenario)
    print("\n===== FREQUENCY DYNAMICS TEST =====")
    print("Simulating 50 MW sudden load increase...\n")
    
    total_load_mw = 500.0
    total_losses_mw = 10.0
    
    for t in range(0, 60, 1):  # 60 seconds
        if t == 10:
            # Sudden load increase
            total_load_mw += 50.0
            print(f"\n[t={t}s] LOAD STEP: +50 MW\n")
        
        results = freq_model.update(
            dt=1.0,
            total_load_mw=total_load_mw,
            total_losses_mw=total_losses_mw,
            current_time=float(t),
        )
        
        if t % 5 == 0 or t == 10 or t == 11:
            print(
                f"t={t:3d}s: f={results['frequency_hz']:6.3f} Hz "
                f"(Δf={results['frequency_deviation_hz']:+.3f} Hz, "
                f"ROCOF={results['rocof_hz_per_s']:+.4f} Hz/s)"
            )
    
    print("\nGenerator outputs after stabilization:")
    for gen_name, output_mw in results['generator_outputs_mw'].items():
        print(f"  {gen_name}: {output_mw:.2f} MW")
