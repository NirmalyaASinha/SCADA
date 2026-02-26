"""
WebSocket Manager - Broadcast to dashboard clients
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Set, Dict
from fastapi import WebSocket, WebSocketDisconnect
from collections import defaultdict

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.user_connections: Dict[str, WebSocket] = {}  # username -> websocket
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.running = False
        self.broadcast_task = None
        
        # Throttling - limit telemetry broadcasts to 1Hz per node
        self.last_broadcast_time = defaultdict(lambda: datetime.min)
        self.telemetry_throttle_seconds = 1.0
    
    async def connect(self, websocket: WebSocket, username: str):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.user_connections[username] = websocket
        logger.info(f"Dashboard WebSocket connected: {username} (total: {len(self.active_connections)})")
        
        # Send welcome message
        await self.send_personal_message({
            "type": "connected",
            "message": "Connected to SCADA Master WebSocket",
            "timestamp": datetime.utcnow().isoformat()
        }, websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        self.active_connections.discard(websocket)
        
        # Remove from user connections
        username_to_remove = None
        for username, ws in self.user_connections.items():
            if ws == websocket:
                username_to_remove = username
                break
        
        if username_to_remove:
            del self.user_connections[username_to_remove]
            logger.info(f"Dashboard WebSocket disconnected: {username_to_remove} (remaining: {len(self.active_connections)})")
    
    async def send_personal_message(self, message: Dict, websocket: WebSocket):
        """Send message to specific client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
    
    async def broadcast(self, message: Dict):
        """Queue message for broadcast to all connected clients"""
        # Throttle telemetry updates
        if message.get("type") == "telemetry_update":
            node_id = message.get("node_id")
            now = datetime.utcnow()
            last_time = self.last_broadcast_time[node_id]
            
            elapsed = (now - last_time).total_seconds()
            if elapsed < self.telemetry_throttle_seconds:
                return  # Skip this update
            
            self.last_broadcast_time[node_id] = now
        
        # Add to queue
        await self.message_queue.put(message)
    
    async def start_broadcasting(self):
        """Start background task for broadcasting queued messages"""
        self.running = True
        self.broadcast_task = asyncio.create_task(self._broadcast_loop())
        logger.info("WebSocket broadcaster started")
    
    async def stop_broadcasting(self):
        """Stop broadcasting"""
        self.running = False
        if self.broadcast_task:
            self.broadcast_task.cancel()
    
    async def _broadcast_loop(self):
        """Background loop to broadcast queued messages"""
        while self.running:
            try:
                # Get message from queue with timeout
                try:
                    message = await asyncio.wait_for(self.message_queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    continue
                
                # Broadcast to all connected clients
                disconnected = set()
                for websocket in self.active_connections:
                    try:
                        await websocket.send_json(message)
                    except Exception as e:
                        logger.error(f"Error broadcasting to client: {e}")
                        disconnected.add(websocket)
                
                # Remove disconnected clients
                for websocket in disconnected:
                    self.disconnect(websocket)
                
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}")
    
    async def send_full_state_snapshot(self, websocket: WebSocket, grid_state: Dict, topology: Dict, nodes: list):
        """Send full current state to newly connected client"""
        snapshot = {
            "type": "full_state_snapshot",
            "timestamp": datetime.utcnow().isoformat(),
            "grid_state": grid_state,
            "topology": topology,
            "nodes": nodes
        }
        await self.send_personal_message(snapshot, websocket)
    
    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)
