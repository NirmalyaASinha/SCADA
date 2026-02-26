"""
Economic Despatch
=================

Implements simplified economic despatch for generator allocation.

Economic despatch solves the optimization problem:
    Minimize: Total generation cost
    Subject to: Sum(P_gen) = P_load + P_losses
                P_gen_min <= P_gen <= P_gen_max for each generator

Real grid operators run economic despatch every 5-15 minutes to determine
optimal generation allocation based on:
    1. Incremental fuel costs
    2. Transmission constraints
    3. Reserve requirements
    4. Renewable curtailment limits

Simplified merit order despatch:
    1. Rank generators by marginal cost (ascending)
    2. Load generators in order until demand met
    3. Last generator on the margin sets system marginal price

Indian grid characteristics:
    - Solar/wind first (zero marginal cost)
    - Hydro second (low cost, but water constrained)
    - Thermal (coal) last (high cost, provides reliability)

Cost curves are quadratic:
    C(P) = a*P^2 + b*P + c  (Rs/hour)

Where a, b, c are generator-specific cost coefficients.

Marginal cost (incremental cost):
    dC/dP = 2*a*P + b  (Rs/MWh)

At optimal despatch, all online generators have equal marginal cost
(Lambda coordination - fundamental principle of economic despatch).

This implementation uses simplified merit order rather than full lambda
iteration - adequate for simulation purposes and mirrors real despatch
practice when transmission constraints are not binding.
"""

import numpy as np
from typing import Dict, List
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from config import GENERATOR_CONFIG

logger = logging.getLogger(__name__)


class EconomicDespatch:
    """
    Economic despatch for generator allocation.
    
    Uses merit order despatch (simplified):
    - Solar @ zero cost
    - Hydro @ low cost
    - Coal @ higher cost
    """
    
    def __init__(self):
        self.generators = list(GENERATOR_CONFIG.keys())
        
        # Build merit order (sorted by marginal cost at rated output)
        self.merit_order = self._build_merit_order()
        
        logger.info(f"Economic despatch initialized with {len(self.generators)} generators")
        logger.info(f"Merit order: {' -> '.join(self.merit_order)}")
    
    def _build_merit_order(self) -> List[str]:
        """
        Build merit order based on marginal costs.
        
        Returns:
            List of generator names in loading order (cheapest first)
        """
        # Calculate marginal cost at mid-point output for each generator
        marginal_costs = []
        
        for gen_name in self.generators:
            config = GENERATOR_CONFIG[gen_name]
            P_mid = (config["min_mw"] + config["max_mw"]) / 2.0
            
            # Marginal cost: dC/dP = 2*a*P + b
            a = config["cost_curve"]["a"]
            b = config["cost_curve"]["b"]
            
            mc = 2.0 * a * P_mid + b
            
            marginal_costs.append((gen_name, mc))
        
        # Sort by marginal cost (ascending)
        marginal_costs.sort(key=lambda x: x[1])
        
        return [gen_name for gen_name, mc in marginal_costs]
    
    def despatch(
        self,
        total_demand_mw: float,
        solar_available_mw: float = None,
    ) -> Dict[str, float]:
        """
        Calculate optimal generation despatch.
        
        Args:
            total_demand_mw: Total system demand (load + losses)
            solar_available_mw: Available solar generation (optional,
                               auto-calculated if not provided)
        
        Returns:
            despatch: Dict mapping generator name to output (MW)
        """
        despatch = {}
        remaining_demand = total_demand_mw
        
        # Load generators in merit order
        for gen_name in self.merit_order:
            config = GENERATOR_CONFIG[gen_name]
            
            # Solar generation based on availability
            if gen_name == "GEN-003" and solar_available_mw is not None:
                # Solar limited by available resource
                P_max = min(config["max_mw"], solar_available_mw)
            else:
                P_max = config["max_mw"]
            
            P_min = config["min_mw"]
            
            if remaining_demand > P_min:
                # Load this generator
                P_gen = min(P_max, remaining_demand)
                P_gen = max(P_min, P_gen)
                
                despatch[gen_name] = P_gen
                remaining_demand -= P_gen
            else:
                # Insufficient demand, keep at minimum or offline
                if remaining_demand > 0:
                    despatch[gen_name] = max(0, min(P_min, remaining_demand))
                    remaining_demand = 0
                else:
                    despatch[gen_name] = 0.0
        
        # Handle under-generation (demand exceeds capacity)
        if remaining_demand > 1.0:  # 1 MW tolerance
            logger.warning(
                f"Under-generation: Demand {total_demand_mw:.1f} MW exceeds "
                f"available capacity by {remaining_demand:.1f} MW"
            )
            
            # Proportionally increase all online generators to max
            total_generation = sum(despatch.values())
            if total_generation > 0:
                scale = total_demand_mw / total_generation
                for gen_name in despatch:
                    config = GENERATOR_CONFIG[gen_name]
                    despatch[gen_name] = min(
                        config["max_mw"],
                        despatch[gen_name] * scale
                    )
        
        return despatch
    
    def calculate_total_cost(self, despatch: Dict[str, float]) -> float:
        """
        Calculate total generation cost.
        
        Args:
            despatch: Generator outputs (MW)
        
        Returns:
            Total cost (Rs/hour)
        """
        total_cost = 0.0
        
        for gen_name, P_mw in despatch.items():
            config = GENERATOR_CONFIG[gen_name]
            
            # Cost curve: C(P) = a*P^2 + b*P + c
            a = config["cost_curve"]["a"]
            b = config["cost_curve"]["b"]
            c = config["cost_curve"]["c"]
            
            cost = a * (P_mw ** 2) + b * P_mw + c
            total_cost += cost
        
        return total_cost
    
    def calculate_marginal_price(self, despatch: Dict[str, float]) -> float:
        """
        Calculate system marginal price (price of next MW).
        
        Marginal price is set by the most expensive generator on the margin.
        
        Args:
            despatch: Generator outputs (MW)
        
        Returns:
            Marginal price (Rs/MWh)
        """
        marginal_price = 0.0
        
        # Find the generator on the margin (last one loaded)
        for gen_name in reversed(self.merit_order):
            config = GENERATOR_CONFIG[gen_name]
            P_gen = despatch.get(gen_name, 0.0)
            
            if P_gen > config["min_mw"] + 1.0:  # Loaded above minimum
                # This generator is on the margin
                # Marginal cost: dC/dP = 2*a*P + b
                a = config["cost_curve"]["a"]
                b = config["cost_curve"]["b"]
                
                marginal_price = 2.0 * a * P_gen + b
                break
        
        return marginal_price
