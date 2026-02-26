"""
Node Connector - WebSocket connections to all 15 nodes
"""
import asyncio
import logging
import json
import websockets
from datetime import datetime
from typing import Dict, Callable, Optional

from .registry import NodeRegistry, NodeState

logger = logging.getLogger(__name__)

class NodeConnector:
    def __init__(self, registry: NodeRegistry):
        self.registry = registry
        self.websockets: Dict[str, Optional[websockets.WebSocketClientProtocol]] = {}
        self.reconnect_tasks = {}
        self.running = False
        self.broadcast_callback: Optional[Callable] = None
        
        # Reconnection parameters
        self.base_reconnect_delay = 5  # seconds
        self.max_reconnect_delay = 60  # seconds
        self.max_failed_attempts = 10
    
    def set_broadcast_callback(self, callback: Callable):
        """Set callback for broadcasting telemetry updates"""
        self.broadcast_callback = callback
    
    async def start(self):
        """Start connecting to all nodes"""
        self.running = True
        logger.info("Node connector starting... connecting to 15 nodes")
        
        # Start connection tasks for all nodes
        tasks = []
        for node in self.registry.get_all_nodes():
            task = asyncio.create_task(self._connect_to_node(node.node_id))
            tasks.append(task)
        
        # Don't await - let connections happen in background
        logger.info(f"Initiated {len(tasks)} node connection tasks")
    
    async def stop(self):
        """Stop all connections"""
        self.running = False
        logger.info("Stopping node connector...")
        
        # Close all WebSocket connections
        for node_id, ws in self.websockets.items():
            if ws and not ws.closed:
                await ws.close()
                logger.info(f"Closed connection to {node_id}")
        
        # Cancel reconnect tasks
        for task in self.reconnect_tasks.values():
            task.cancel()
    
    async def _connect_to_node(self, node_id: str):
        """Connect to a single node and handle reconnection"""
        node = self.registry.get_node(node_id)
        if not node:
            logger.error(f"Node {node_id} not found in registry")
            return
        
        attempt_count = 0
        
        while self.running:
            try:
                # Update state
                if attempt_count == 0:
                    self.registry.update_node_state(node_id, NodeState.CONNECTING)
                else:
                    self.registry.update_node_state(node_id, NodeState.RECONNECTING)
                
                logger.info(f"Connecting to {node_id} at {node.ws_url} (attempt {attempt_count + 1})")
                
                # Connect via WebSocket
                # Convert ws:// to http:// for local container access
                ws_url = node.ws_url.replace("localhost", node.node_id.lower().replace("-", "_"))
                if not ws_url.startswith("ws://node_"):
                    ws_url = f"ws://node_{node.node_id.lower().replace('-', '_')}:{node.ws_port}/ws/telemetry"
                
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as websocket:
                    self.websockets[node_id] = websocket
                    self.registry.update_node_state(node_id, NodeState.CONNECTED)
                    node.reconnect_count = attempt_count
                    attempt_count = 0  # Reset on successful connection
                    
                    logger.info(f"✅ Connected to {node_id}")
                    
                    # Listen for messages
                    async for message in websocket:
                        await self._handle_message(node_id, message)
                
            except Exception as e:
                attempt_count += 1
                logger.warning(f"Connection to {node_id} failed (attempt {attempt_count}): {e}")
                
                # Update state
                if attempt_count >= self.max_failed_attempts:
                    self.registry.update_node_state(node_id, NodeState.OFFLINE)
                    logger.error(f"Node {node_id} marked OFFLINE after {attempt_count} failed attempts")
                    # Alert dashboard
                    if self.broadcast_callback:
                        await self.broadcast_callback({
                            "type": "node_offline",
                            "node_id": node_id,
                            "since": datetime.utcnow().isoformat()
                        })
                else:
                    self.registry.update_node_state(node_id, NodeState.RECONNECTING)
                
                # Exponential backoff
                delay = min(
                    self.base_reconnect_delay * (2 ** min(attempt_count - 1, 3)),
                    self.max_reconnect_delay
                )
                logger.info(f"Retrying {node_id} in {delay}s...")
                await asyncio.sleep(delay)
    
    async def _handle_message(self, node_id: str, message: str):
        """Handle incoming WebSocket message from node"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "telemetry":
                # Update cached telemetry
                telemetry = data.get("data", {})
                self.registry.update_node_telemetry(node_id, telemetry)
                
                # Broadcast to dashboard clients (throttled to 1Hz in broadcaster)
                if self.broadcast_callback:
                    await self.broadcast_callback({
                        "type": "telemetry_update",
                        "node_id": node_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": telemetry
                    })
            
            elif message_type == "alarm":
                alarm = data.get("data", {})
                logger.warning(f"Alarm from {node_id}: {alarm.get('message')}")
                
                # Broadcast alarm
                if self.broadcast_callback:
                    await self.broadcast_callback({
                        "type": "alarm_raised",
                        "node_id": node_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": alarm
                    })
            
            elif message_type == "connection_event":
                # New connection detected on node
                conn_data = data.get("data", {})
                logger.info(f"Connection event on {node_id}: {conn_data}")
                
                # Check if authorized
                if not conn_data.get("is_authorised", False):
                    logger.warning(f"Unknown connection detected: {conn_data}")
                    
                    if self.broadcast_callback:
                        await self.broadcast_callback({
                            "type": "unknown_connection",
                            "node_id": node_id,
                            "timestamp": datetime.utcnow().isoformat(),
                            "data": conn_data
                        })
            
            elif message_type == "heartbeat":
                # Update heartbeat
                node = self.registry.get_node(node_id)
                if node:
                    node.last_heartbeat = datetime.utcnow()
        
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from {node_id}: {message}")
        except Exception as e:
            logger.error(f"Error handling message from {node_id}: {e}")
    
    def get_connection_status(self) -> Dict:
        """Get status of all connections"""
        status = {
            "total_nodes": len(self.registry.nodes),
            "connected": 0,
            "connecting": 0,
            "reconnecting": 0,
            "offline": 0,
            "nodes": []
        }
        
        for node in self.registry.get_all_nodes():
            status["nodes"].append({
                "node_id": node.node_id,
                "state": node.state.value,
                "last_heartbeat": node.last_heartbeat.isoformat() if node.last_heartbeat else None,
                "reconnect_count": node.reconnect_count
            })
            
            if node.state == NodeState.CONNECTED:
                status["connected"] += 1
            elif node.state == NodeState.CONNECTING:
                status["connecting"] += 1
            elif node.state == NodeState.RECONNECTING:
                status["reconnecting"] += 1
            elif node.state == NodeState.OFFLINE:
                status["offline"] += 1
        
        return status
