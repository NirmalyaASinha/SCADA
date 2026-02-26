"""
DC Power Flow Solver for 15-Bus Grid
=====================================

Implements simplified DC power flow approximation for real-time simulation.
This mirrors the fast-decoupled power flow used in real Energy Management Systems.

DC Power Flow Assumptions:
1. All bus voltages are approximately 1.0 per-unit
2. Line resistances are small compared to reactances (R << X)
3. Voltage angle differences are small (sin(θ) ≈ θ, cos(θ) ≈ 1)
4. Reactive power decoupled from active power

Under these assumptions:
    P_ij = (θ_i - θ_j) / X_ij

Where:
    P_ij = active power flow from bus i to bus j
    θ_i, θ_j = voltage angles at buses i and j (radians)
    X_ij = line reactance (per-unit)

This forms a linear system: P = B * θ
where B is the DC susceptance matrix.

Solves for bus voltage angles given net power injections.
Then calculates line flows and losses.

Real SCADA systems run full AC power flow every 5-15 minutes.
We use DC approximation every 5 seconds for computational efficiency.
"""

import numpy as np
from typing import Dict, Tuple, List
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    LINE_IMPEDANCES, 
    ALL_NODES, 
    SYSTEM_BASE_MVA,
    NODE_CONFIG,
)

logger = logging.getLogger(__name__)


class DCPowerFlow:
    """
    DC Power Flow solver for 15-bus Indian grid model.
    
    Topology:
        3 Generation nodes (GEN-001, GEN-002, GEN-003)
        7 Transmission substations (SUB-001 through SUB-007)
        5 Distribution substations (DIST-001 through DIST-005)
        
    Slack bus: GEN-001 (largest generator, typical EMS configuration)
    """
    
    def __init__(self):
        self.num_buses = len(ALL_NODES)
        self.bus_names = ALL_NODES
        self.bus_index = {name: idx for idx, name in enumerate(self.bus_names)}
        
        # Slack bus is GEN-001 (index 0)
        self.slack_bus_idx = self.bus_index["GEN-001"]
        
        # Build DC susceptance matrix
        self.B_matrix = self._build_susceptance_matrix()
        
        # Reduced B matrix (excluding slack bus for solving)
        self.B_reduced = self._reduce_matrix()
        
        logger.info(f"DC Power Flow initialized with {self.num_buses} buses")
        logger.info(f"Slack bus: {self.bus_names[self.slack_bus_idx]}")
    
    def _build_susceptance_matrix(self) -> np.ndarray:
        """
        Build DC susceptance matrix B where B_ij = -1/X_ij for connected buses.
        
        Diagonal elements: B_ii = sum of susceptances of all lines connected to bus i.
        Off-diagonal: B_ij = -1/X_ij if buses i and j are connected, else 0.
        
        This is the electrical analog of Kirchhoff's Current Law applied to power flow.
        """
        B = np.zeros((self.num_buses, self.num_buses))
        
        for (bus_i_name, bus_j_name), (R, X, B_shunt) in LINE_IMPEDANCES.items():
            i = self.bus_index[bus_i_name]
            j = self.bus_index[bus_j_name]
            
            # Susceptance (inverse of reactance)
            b_ij = 1.0 / X
            
            # Off-diagonal elements (negative)
            B[i, j] = -b_ij
            B[j, i] = -b_ij
            
            # Diagonal elements (positive, sum of connected line susceptances)
            B[i, i] += b_ij
            B[j, j] += b_ij
        
        return B
    
    def _reduce_matrix(self) -> np.ndarray:
        """
        Remove slack bus row and column from B matrix.
        
        In power flow solution, slack bus angle is fixed at 0.0 radians (reference).
        We solve for all other bus angles relative to slack.
        """
        mask = np.ones(self.num_buses, dtype=bool)
        mask[self.slack_bus_idx] = False
        
        B_reduced = self.B_matrix[np.ix_(mask, mask)]
        
        return B_reduced
    
    def solve(
        self, 
        generation_mw: Dict[str, float],
        load_mw: Dict[str, float],
    ) -> Dict[str, Dict]:
        """
        Solve DC power flow for given generation and load.
        
        Args:
            generation_mw: Dict mapping node name to active power generation (MW)
            load_mw: Dict mapping node name to active power load (MW)
        
        Returns:
            results: Dict containing:
                - bus_angles_rad: voltage angles at each bus (radians)
                - bus_voltages_pu: voltage magnitudes (fixed at 1.0 for DC)
                - line_flows_mw: power flow on each line (MW)
                - line_losses_mw: active power losses on each line (MW)
                - total_generation_mw: total system generation
                - total_load_mw: total system load
                - total_losses_mw: total system losses
        
        Process:
            1. Calculate net injection at each bus: P_net = P_gen - P_load
            2. Solve B * θ = P_net for voltage angles θ
            3. Calculate line flows: P_ij = (θ_i - θ_j) / X_ij
            4. Calculate losses: P_loss = I^2 * R ≈ (P_ij^2 * R) / V^2
        """
        
        # Calculate net injection at each bus (per-unit on system base)
        P_net = np.zeros(self.num_buses)
        
        for bus_name, idx in self.bus_index.items():
            gen_mw = generation_mw.get(bus_name, 0.0)
            ld_mw = load_mw.get(bus_name, 0.0)
            P_net[idx] = (gen_mw - ld_mw) / SYSTEM_BASE_MVA  # Convert to per-unit
        
        # Extract P vector excluding slack bus
        mask = np.ones(self.num_buses, dtype=bool)
        mask[self.slack_bus_idx] = False
        P_reduced = P_net[mask]
        
        # Solve for voltage angles: θ = B^-1 * P
        try:
            theta_reduced = np.linalg.solve(self.B_reduced, P_reduced)
        except np.linalg.LinAlgError:
            logger.error("Singular B matrix - power flow not solvable")
            return self._get_failed_result()
        
        # Reconstruct full theta vector (slack bus angle = 0.0)
        theta = np.zeros(self.num_buses)
        theta[mask] = theta_reduced
        theta[self.slack_bus_idx] = 0.0  # Slack bus reference angle
        
        # Build results dictionary with bus angles
        bus_angles_rad = {name: theta[idx] for name, idx in self.bus_index.items()}
        
        # DC power flow assumes |V| = 1.0 p.u. at all buses
        bus_voltages_pu = {name: 1.0 for name in self.bus_names}
        
        # Calculate line flows and losses
        line_flows_mw = {}
        line_losses_mw = {}
        total_losses_mw = 0.0
        
        for (bus_i_name, bus_j_name), (R, X, B_shunt) in LINE_IMPEDANCES.items():
            i = self.bus_index[bus_i_name]
            j = self.bus_index[bus_j_name]
            
            # Power flow from i to j: P_ij = (θ_i - θ_j) / X_ij
            theta_diff = theta[i] - theta[j]
            P_ij_pu = theta_diff / X
            P_ij_mw = P_ij_pu * SYSTEM_BASE_MVA
            
            line_key = f"{bus_i_name}-{bus_j_name}"
            line_flows_mw[line_key] = P_ij_mw
            
            # Losses: P_loss ≈ P_ij^2 * R / V^2
            # In per-unit: P_loss = P_ij^2 * R (since V ≈ 1.0 p.u.)
            P_loss_pu = (P_ij_pu ** 2) * R
            P_loss_mw = P_loss_pu * SYSTEM_BASE_MVA
            
            line_losses_mw[line_key] = P_loss_mw
            total_losses_mw += P_loss_mw
        
        # Calculate totals
        total_generation_mw = sum(generation_mw.values())
        total_load_mw = sum(load_mw.values())
        
        # Power balance check: Generation = Load + Losses (within numerical tolerance)
        power_balance_error = abs(total_generation_mw - total_load_mw - total_losses_mw)
        if power_balance_error > 0.1:  # 0.1 MW tolerance
            logger.warning(
                f"Power balance error: {power_balance_error:.3f} MW "
                f"(Gen: {total_generation_mw:.1f}, Load: {total_load_mw:.1f}, "
                f"Loss: {total_losses_mw:.1f})"
            )
        
        results = {
            "bus_angles_rad": bus_angles_rad,
            "bus_voltages_pu": bus_voltages_pu,  # Fixed at 1.0 for DC
            "line_flows_mw": line_flows_mw,
            "line_losses_mw": line_losses_mw,
            "total_generation_mw": total_generation_mw,
            "total_load_mw": total_load_mw,
            "total_losses_mw": total_losses_mw,
            "converged": True,
        }
        
        logger.debug(
            f"Power flow solved: Gen={total_generation_mw:.1f} MW, "
            f"Load={total_load_mw:.1f} MW, Loss={total_losses_mw:.1f} MW"
        )
        
        return results
    
    def _get_failed_result(self) -> Dict:
        """Return a failure result when power flow doesn't converge."""
        return {
            "bus_angles_rad": {name: 0.0 for name in self.bus_names},
            "bus_voltages_pu": {name: 0.0 for name in self.bus_names},
            "line_flows_mw": {},
            "line_losses_mw": {},
            "total_generation_mw": 0.0,
            "total_load_mw": 0.0,
            "total_losses_mw": 0.0,
            "converged": False,
        }
    
    def get_bus_voltages_kv(
        self, 
        bus_voltages_pu: Dict[str, float],
        node_name: str,
    ) -> float:
        """
        Convert per-unit voltage to kV for a specific node.
        
        Args:
            bus_voltages_pu: Per-unit voltages from power flow solution
            node_name: Node identifier (e.g., "GEN-001", "SUB-003")
        
        Returns:
            Voltage in kV
        """
        from config import NOMINAL_VOLTAGE_KV
        
        v_pu = bus_voltages_pu.get(node_name, 1.0)
        
        # Determine nominal voltage based on node type
        if node_name in NODE_CONFIG["GENERATION"]:
            v_nominal_kv = NOMINAL_VOLTAGE_KV["GENERATION"]
        elif node_name in NODE_CONFIG["TRANSMISSION"]:
            v_nominal_kv = NOMINAL_VOLTAGE_KV["TRANSMISSION"]
        else:  # DISTRIBUTION
            v_nominal_kv = NOMINAL_VOLTAGE_KV["DISTRIBUTION"]
        
        return v_pu * v_nominal_kv
    
    def calculate_line_currents(
        self,
        line_flows_mw: Dict[str, float],
        bus_voltages_pu: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Calculate line currents from power flows.
        
        Current magnitude: I = P / (sqrt(3) * V) for three-phase
        
        Args:
            line_flows_mw: Power flows on each line (MW)
            bus_voltages_pu: Per-unit voltages
        
        Returns:
            line_currents_a: Line currents in Amperes
        """
        from config import NOMINAL_VOLTAGE_KV, SYSTEM_BASE_MVA
        
        line_currents_a: Dict[str, float] = {}
        
        for line_key, P_mw in line_flows_mw.items():
            # Extract from and to buses
            from_bus, to_bus = line_key.split('-')
            
            # Use voltage at from bus for current calculation
            v_pu = bus_voltages_pu.get(from_bus, 1.0)
            
            # Determine nominal voltage
            if from_bus in NODE_CONFIG["GENERATION"]:
                v_nominal_kv = NOMINAL_VOLTAGE_KV["GENERATION"]
            elif from_bus in NODE_CONFIG["TRANSMISSION"]:
                v_nominal_kv = NOMINAL_VOLTAGE_KV["TRANSMISSION"]
            else:
                v_nominal_kv = NOMINAL_VOLTAGE_KV["DISTRIBUTION"]
            
            v_kv = v_pu * v_nominal_kv
            
            # Three-phase current: I = P / (sqrt(3) * V)
            # P in MW, V in kV → I in kA, then convert to A
            if v_kv > 0.1:  # Avoid division by zero
                I_ka = abs(P_mw) / (np.sqrt(3) * v_kv)
                I_a = I_ka * 1000.0
            else:
                I_a = 0.0
            
            line_currents_a[line_key] = I_a
        
        return line_currents_a


if __name__ == "__main__":
    # Test the power flow solver
    logging.basicConfig(level=logging.DEBUG)
    
    pf = DCPowerFlow()
    
    # Test case: Simple generation and load scenario
    generation_mw = {
        "GEN-001": 400.0,  # Coal base load
        "GEN-002": 200.0,  # Hydro
        "GEN-003": 100.0,  # Solar (daytime)
    }
    
    load_mw = {
        "DIST-001": 150.0,
        "DIST-002": 120.0,
        "DIST-003": 100.0,
        "DIST-004": 80.0,
        "DIST-005": 90.0,
    }
    
    results = pf.solve(generation_mw, load_mw)
    
    print("\n===== DC POWER FLOW RESULTS =====")
    print(f"Converged: {results['converged']}")
    print(f"\nTotal Generation: {results['total_generation_mw']:.2f} MW")
    print(f"Total Load: {results['total_load_mw']:.2f} MW")
    print(f"Total Losses: {results['total_losses_mw']:.2f} MW")
    print(f"Loss Percentage: {100.0 * results['total_losses_mw'] / results['total_generation_mw']:.2f}%")
    
    print("\n----- Bus Voltage Angles (degrees) -----")
    for bus, angle_rad in sorted(results['bus_angles_rad'].items()):
        angle_deg = np.degrees(angle_rad)
        print(f"{bus:12s}: {angle_deg:7.3f}°")
    
    print("\n----- Line Flows (MW) -----")
    for line, flow in sorted(results['line_flows_mw'].items()):
        loss = results['line_losses_mw'][line]
        print(f"{line:25s}: {flow:8.2f} MW (loss: {loss:5.2f} MW)")
