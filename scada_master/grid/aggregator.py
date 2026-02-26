"""
Grid Aggregator - Real-time grid state calculation
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List
from collections import deque

from nodes.registry import NodeRegistry, NodeState

logger = logging.getLogger(__name__)

class GridAggregator:
    def __init__(self, registry: NodeRegistry):
        self.registry = registry
        self.grid_state = {}
        self.frequency_history = deque(maxlen=600)  # 10 minutes at 1Hz
        self.running = False
        self.update_task = None
    
    async def start(self):
        """Start periodic grid state aggregation"""
        self.running = True
        self.update_task = asyncio.create_task(self._update_loop())
        logger.info("Grid aggregator started")
    
    async def stop(self):
        """Stop aggregation"""
        self.running = False
        if self.update_task:
            self.update_task.cancel()
    
    async def _update_loop(self):
        """Update grid state every 2 seconds"""
        while self.running:
            try:
                self.grid_state = self._calculate_grid_state()
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Error in grid aggregation: {e}")
                await asyncio.sleep(2)
    
    def _calculate_grid_state(self) -> Dict:
        """Calculate current grid state from all nodes"""
        total_generation_mw = 0.0
        total_load_mw = 0.0
        frequency_sum = 0.0
        frequency_count = 0
        voltage_violations = []
        
        nodes_online = 0
        nodes_offline = 0
        nodes_degraded = 0
        
        active_alarms_critical = 0
        active_alarms_high = 0
        active_alarms_medium = 0
        active_alarms_low = 0
        
        for node in self.registry.get_all_nodes():
            # Count node states
            if node.state == NodeState.CONNECTED:
                nodes_online += 1
            elif node.state == NodeState.OFFLINE:
                nodes_offline += 1
            elif node.state in [NodeState.RECONNECTING, NodeState.DEGRADED]:
                nodes_degraded += 1
            
            # Aggregate telemetry
            if node.telemetry:
                # Power
                if node.node_type == "generation":
                    total_generation_mw += node.telemetry.get("active_power_mw", 0)
                elif node.node_type in ["transmission", "distribution"]:
                    total_load_mw += abs(node.telemetry.get("active_power_mw", 0))
                
                # Frequency
                freq = node.telemetry.get("frequency_hz", 0)
                if freq > 0:
                    frequency_sum += freq
                    frequency_count += 1
                
                # Voltage violations
                voltage = node.telemetry.get("voltage_kv", 0)
                if voltage > 0:
                    # Check against nominal voltage
                    nominal = 132.0 if node.node_type == "transmission" else 33.0
                    deviation = abs(voltage - nominal) / nominal * 100
                    if deviation > 5:  # >5% deviation
                        voltage_violations.append({
                            "node_id": node.node_id,
                            "voltage_kv": round(voltage, 2),
                            "nominal_kv": nominal,
                            "deviation_pct": round(deviation, 2)
                        })
                
                # Alarms (placeholder - would come from alarm system)
                # For now, assume no alarms
        
        # Calculate system frequency
        system_frequency_hz = frequency_sum / frequency_count if frequency_count > 0 else 50.0
        
        # Add to history
        self.frequency_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "value": system_frequency_hz
        })
        
        # Calculate grid losses (generation - load)
        grid_losses_mw = total_generation_mw - total_load_mw
        
        return {
            "total_generation_mw": round(total_generation_mw, 2),
            "total_load_mw": round(total_load_mw, 2),
            "system_frequency_hz": round(system_frequency_hz, 4),
            "grid_losses_mw": round(grid_losses_mw, 2),
            "nodes_online": nodes_online,
            "nodes_offline": nodes_offline,
            "nodes_degraded": nodes_degraded,
            "active_alarms_critical": active_alarms_critical,
            "active_alarms_high": active_alarms_high,
            "active_alarms_medium": active_alarms_medium,
            "active_alarms_low": active_alarms_low,
            "voltage_violations": voltage_violations,
            "frequency_trend": list(self.frequency_history),
            "last_updated": datetime.utcnow().isoformat()
        }
    
    def get_grid_state(self) -> Dict:
        """Get current grid state"""
        return self.grid_state if self.grid_state else self._calculate_grid_state()
