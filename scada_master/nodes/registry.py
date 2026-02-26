"""
Node Registry - Maintains list of all nodes
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class NodeState(str, Enum):
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"

class NodeInfo:
    def __init__(self, node_id: str, node_type: str, tier: int, rest_port: int, ws_port: int, service_name: str = None):
        self.node_id = node_id
        self.node_type = node_type  # generation, transmission, distribution
        self.tier = tier
        # Use Docker service name if provided, otherwise localhost
        host = service_name if service_name else "localhost"
        self.rest_url = f"http://{host}:{rest_port}"
        # WebSocket runs on same port as REST API (FastAPI handles both)
        self.ws_url = f"ws://{host}:{rest_port}/ws/telemetry"
        self.rest_port = rest_port
        self.ws_port = ws_port
        self.state = NodeState.CONNECTING
        self.last_heartbeat = None
        self.reconnect_count = 0
        self.telemetry = {}
        self.alarms = []
        self.connections = []
        self.position = {"x":0, "y": 0}  # For topology map
    
    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "type": self.node_type,
            "tier": self.tier,
            "state": self.state.value,
            "rest_url": self.rest_url,
            "ui_url": f"{self.rest_url}/ui",
            "rest_port": self.rest_port,
            "ws_port": self.ws_port,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "reconnect_count": self.reconnect_count,
            "telemetry": self.telemetry,
            "position": self.position
        }

class NodeRegistry:
    def __init__(self):
        self.nodes: Dict[str, NodeInfo] = {}
        self._initialize_nodes()
    
    def _initialize_nodes(self):
        """Initialize all 15 nodes with port mappings"""
        # Generation nodes (GEN-001 to GEN-003)
        gen_nodes = [
            ("GEN-001", "generation", 1, 8101, 8102, 200, 100, "node_gen001"),
            ("GEN-002", "generation", 1, 8103, 8104, 400, 100, "node_gen002"),
            ("GEN-003", "generation", 1, 8105, 8106, 600, 100, "node_gen003"),
        ]
        
        # Transmission substations (SUB-001 to SUB-007)
        sub_nodes = [
            ("SUB-001", "transmission", 2, 8111, 8112, 100, 300, "node_sub001"),
            ("SUB-002", "transmission", 2, 8113, 8114, 250, 300, "node_sub002"),
            ("SUB-003", "transmission", 2, 8115, 8116, 400, 300, "node_sub003"),
            ("SUB-004", "transmission", 2, 8117, 8118, 550, 300, "node_sub004"),
            ("SUB-005", "transmission", 2, 8119, 8120, 700, 300, "node_sub005"),
            ("SUB-006", "transmission", 2, 8121, 8122, 200, 450, "node_sub006"),
            ("SUB-007", "transmission", 2, 8123, 8124, 600, 450, "node_sub007"),
        ]
        
        # Distribution nodes (DIST-001 to DIST-005)
        dist_nodes = [
            ("DIST-001", "distribution", 3, 8131, 8132, 150, 600, "node_dist001"),
            ("DIST-002", "distribution", 3, 8133, 8134, 300, 600, "node_dist002"),
            ("DIST-003", "distribution", 3, 8135, 8136, 450, 600, "node_dist003"),
            ("DIST-004", "distribution", 3, 8137, 8138, 600, 600, "node_dist004"),
            ("DIST-005", "distribution", 3, 8139, 8140, 750, 600, "node_dist005"),
        ]
        
        all_nodes = gen_nodes + sub_nodes + dist_nodes
        
        for node_id, node_type, tier, rest_port, ws_port, pos_x, pos_y, service_name in all_nodes:
            node = NodeInfo(node_id, node_type, tier, rest_port, ws_port, service_name)
            node.position = {"x": pos_x, "y": pos_y}
            self.nodes[node_id] = node
            logger.info(f"Registered node {node_id} ({node_type}) - REST:{rest_port} WS:{ws_port} Service:{service_name}")
    
    def get_node(self, node_id: str) -> Optional[NodeInfo]:
        """Get node by ID"""
        return self.nodes.get(node_id)
    
    def get_all_nodes(self) -> List[NodeInfo]:
        """Get all nodes"""
        return list(self.nodes.values())
    
    def get_nodes_by_type(self, node_type: str) -> List[NodeInfo]:
        """Get nodes by type"""
        return [n for n in self.nodes.values() if n.node_type == node_type]
    
    def get_nodes_by_state(self, state: NodeState) -> List[NodeInfo]:
        """Get nodes by state"""
        return [n for n in self.nodes.values() if n.state == state]
    
    def update_node_state(self, node_id: str, state: NodeState):
        """Update node state"""
        if node_id in self.nodes:
            self.nodes[node_id].state = state
            logger.info(f"Node {node_id} state changed to {state.value}")
    
    def update_node_telemetry(self, node_id: str, telemetry: Dict):
        """Update node telemetry"""
        if node_id in self.nodes:
            self.nodes[node_id].telemetry = telemetry
            self.nodes[node_id].last_heartbeat = datetime.utcnow()
    
    def get_topology(self) -> Dict:
        """Get grid topology for visualization"""
        nodes = []
        for node in self.nodes.values():
            nodes.append({
                "id": node.node_id,
                "type": node.node_type,
                "tier": node.tier,
                "state": node.state.value,
                "position": node.position,
                "telemetry": node.telemetry
            })
        
        # Define edges (transmission lines)
        edges = self._generate_edges()
        
        return {"nodes": nodes, "edges": edges}
    
    def _generate_edges(self) -> List[Dict]:
        """Generate topology edges (connections between nodes)"""
        edges = []
        
        # GEN to SUB connections
        gen_sub_map = [
            ("GEN-001", "SUB-001"),
            ("GEN-001", "SUB-002"),
            ("GEN-002", "SUB-003"),
            ("GEN-002", "SUB-004"),
            ("GEN-003", "SUB-005"),
            ("GEN-003", "SUB-007"),
        ]
        
        # SUB to DIST connections
        sub_dist_map = [
            ("SUB-001", "DIST-001"),
            ("SUB-002", "DIST-001"),
            ("SUB-002", "DIST-002"),
            ("SUB-003", "DIST-002"),
            ("SUB-003", "DIST-003"),
            ("SUB-004", "DIST-003"),
            ("SUB-005", "DIST-004"),
            ("SUB-006", "DIST-002"),
            ("SUB-007", "DIST-004"),
            ("SUB-007", "DIST-005"),
        ]
        
        all_connections = gen_sub_map + sub_dist_map
        
        for source, target in all_connections:
            source_node = self.nodes.get(source)
            target_node = self.nodes.get(target)
            
            if source_node and target_node:
                # Calculate power flow from telemetry
                power_mw = source_node.telemetry.get("active_power_mw", 0)
                current_a = source_node.telemetry.get("current_a", 0)
                energized = source_node.state == NodeState.CONNECTED
                
                edges.append({
                    "id": f"{source}-{target}",
                    "source": source,
                    "target": target,
                    "power_mw": round(power_mw, 2),
                    "current_a": round(current_a, 2),
                    "energized": energized
                })
        
        return edges
