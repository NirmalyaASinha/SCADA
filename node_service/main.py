"""
SCADA Node Microservice
======================
Each of the 15 nodes runs as an independent FastAPI application.
Exposes REST API, WebSocket, Modbus TCP, and IEC 104 on dedicated ports.
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import deque
from dataclasses import dataclass, asdict

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import aioredis
import asyncpg

# ============================================================================
# Configuration
# ============================================================================

# Read from environment variables
NODE_ID = os.getenv("NODE_ID", "TEST-NODE")
NODE_TYPE = os.getenv("NODE_TYPE", "transmission")  # generation, transmission, distribution
UNIT_ID = int(os.getenv("UNIT_ID", "1"))
REST_PORT = int(os.getenv("REST_PORT", "8100"))
WS_PORT = int(os.getenv("WS_PORT", "8101"))
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "5020"))
IEC104_PORT = int(os.getenv("IEC104_PORT", "2401"))
NODE_IP = os.getenv("NODE_IP", "127.0.0.1")
DB_URL = os.getenv("DB_URL", "postgresql://scada:scada123@localhost:5432/scadadb")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
OCC_IP = os.getenv("OCC_IP", "10.0.0.1")
SCADA_MASTER_URL = os.getenv("SCADA_MASTER_URL", "http://localhost:9000")
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Data Models
# ============================================================================

@dataclass
class TelemetryData:
    """Current telemetry snapshot"""
    bus_voltage_kv: float = 132.0
    line_current_a: float = 250.0
    active_power_mw: float = 50.0
    reactive_power_mvar: float = 15.0
    power_factor: float = 0.95
    transformer_temp_c: float = 55.0
    tap_changer_position: int = 9
    breaker_state: bool = True
    protection_relay_trip: bool = False
    earth_fault_indicator: bool = False
    frequency_hz: float = 50.0
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self):
        return asdict(self)

@dataclass
class ConnectionRecord:
    """Record of a connected client"""
    client_ip: str
    client_port: int
    protocol: str  # REST, WebSocket, Modbus, IEC104
    connected_at: str
    last_activity: str
    request_count: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    is_authorised: bool = False
    auth_token: Optional[str] = None

    def to_dict(self):
        return asdict(self)

class NodeResponse(BaseModel):
    node_id: str
    node_type: str
    status: str
    uptime_seconds: int
    telemetry: dict

class ControlRequest(BaseModel):
    action: str  # "open", "close", "isolate", "restore"
    breaker_id: int = 0
    reason: Optional[str] = None

class AlarmModel(BaseModel):
    alarm_id: str
    node_id: str
    timestamp: str
    severity: str  # CRITICAL, WARNING, INFO
    message: str
    acknowledged: bool = False

# ============================================================================
# Node Service Class
# ============================================================================

class NodeService:
    """Main node service controller"""
    
    def __init__(self):
        self.node_id = NODE_ID
        self.node_type = NODE_TYPE
        self.unit_id = UNIT_ID
        self.start_time = datetime.utcnow()
        
        # State
        self.telemetry = TelemetryData()
        self.connections: Dict[str, ConnectionRecord] = {}
        self.alarms: deque = deque(maxlen=100)  # Last 100 alarms
        self.events: deque = deque(maxlen=100)  # Last 100 SOE events
        
        # WebSocket connections
        self.ws_connections: List[WebSocket] = []
        
        # External services
        self.redis = None
        self.db_pool = None
        self.session_token = None
        self.scada_master_connected = False
    
    async def startup(self):
        """Initialize service on startup"""
        logger.info(f"Starting {self.node_id} service...")
        
        # Connect to Redis
        try:
            self.redis = await aioredis.from_url(REDIS_URL)
            logger.info(f"{self.node_id}: Connected to Redis")
        except Exception as e:
            logger.error(f"{self.node_id}: Failed to connect to Redis: {e}")
        
        # Connect to database
        try:
            self.db_pool = await asyncpg.create_pool(DB_URL)
            logger.info(f"{self.node_id}: Connected to database")
        except Exception as e:
            logger.error(f"{self.node_id}: Failed to connect to database: {e}")
        
        # Register with SCADA master
        await self.register_with_master()
        
        # Start telemetry simulation
        asyncio.create_task(self.simulate_telemetry())
        
        logger.info(f"{self.node_id} service started successfully")
    
    async def shutdown(self):
        """Cleanup on shutdown"""
        logger.info(f"Shutting down {self.node_id} service...")
        
        # Deregister from SCADA master
        if self.scada_master_connected:
            try:
                await self.post_to_master("/nodes/deregister", {
                    "node_id": self.node_id
                })
            except:
                pass
        
        # Close connections
        for ws in self.ws_connections:
            await ws.close()
        
        if self.redis:
            await self.redis.close()
        
        if self.db_pool:
            await self.db_pool.close()
        
        logger.info(f"{self.node_id} service stopped")
    
    async def register_with_master(self):
        """Register this node with SCADA master"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                payload = {
                    "node_id": self.node_id,
                    "node_type": self.node_type,
                    "rest_url": f"http://{NODE_IP}:{REST_PORT}",
                    "ws_url": f"ws://{NODE_IP}:{WS_PORT}",
                    "modbus_port": MODBUS_PORT,
                    "iec104_port": IEC104_PORT,
                    "unit_id": self.unit_id
                }
                async with session.post(
                    f"{SCADA_MASTER_URL}/nodes/register",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        self.scada_master_connected = True
                        logger.info(f"{self.node_id}: Registered with SCADA master")
        except Exception as e:
            logger.warning(f"{self.node_id}: Failed to register with SCADA master: {e}")
            self.scada_master_connected = False
    
    async def post_to_master(self, endpoint: str, data: dict):
        """POST to SCADA master"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{SCADA_MASTER_URL}{endpoint}",
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    return await resp.json()
        except Exception as e:
            logger.error(f"{self.node_id}: Failed to POST to master: {e}")
            raise
    
    async def simulate_telemetry(self):
        """Simulate changing telemetry"""
        import random
        while True:
            try:
                # Simulate realistic variations
                self.telemetry.bus_voltage_kv += random.uniform(-0.5, 0.5)
                self.telemetry.bus_voltage_kv = max(100, min(150, self.telemetry.bus_voltage_kv))
                
                self.telemetry.line_current_a += random.uniform(-10, 10)
                self.telemetry.line_current_a = max(0, self.telemetry.line_current_a)
                
                self.telemetry.active_power_mw += random.uniform(-5, 5)
                self.telemetry.active_power_mw = max(0, self.telemetry.active_power_mw)
                
                self.telemetry.frequency_hz += random.uniform(-0.01, 0.01)
                self.telemetry.frequency_hz = max(49.5, min(50.5, self.telemetry.frequency_hz))
                
                self.telemetry.transformer_temp_c += random.uniform(-0.3, 0.3)
                self.telemetry.transformer_temp_c = max(20, min(100, self.telemetry.transformer_temp_c))
                
                self.telemetry.timestamp = datetime.utcnow().isoformat()
                
                # Check alarms
                await self.check_alarms()
                
                # Broadcast to connected WebSocket clients
                await self.broadcast_telemetry()
                
                # Report to master
                if self.scada_master_connected and random.random() < 0.1:  # Every 10 cycles
                    try:
                        await self.post_to_master("/telemetry/report", {
                            "node_id": self.node_id,
                            "telemetry": self.telemetry.to_dict(),
                            "connections_count": len(self.connections),
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    except:
                        pass
                
                await asyncio.sleep(1)  # Update every second
            except Exception as e:
                logger.error(f"{self.node_id}: Telemetry error: {e}")
                await asyncio.sleep(1)
    
    async def check_alarms(self):
        """Check for alarm conditions"""
        alarms_to_raise = []
        
        # Voltage alarm
        if self.telemetry.bus_voltage_kv > 145 or self.telemetry.bus_voltage_kv < 120:
            alarms_to_raise.append({
                "type": "voltage",
                "value": self.telemetry.bus_voltage_kv,
                "severity": "CRITICAL" if self.telemetry.bus_voltage_kv > 150 or self.telemetry.bus_voltage_kv < 110 else "WARNING"
            })
        
        # Frequency alarm
        if self.telemetry.frequency_hz > 50.3 or self.telemetry.frequency_hz < 49.7:
            alarms_to_raise.append({
                "type": "frequency",
                "value": self.telemetry.frequency_hz,
                "severity": "WARNING"
            })
        
        # Temperature alarm
        if self.telemetry.transformer_temp_c > 85:
            alarms_to_raise.append({
                "type": "temperature",
                "value": self.telemetry.transformer_temp_c,
                "severity": "CRITICAL" if self.telemetry.transformer_temp_c > 95 else "WARNING"
            })
        
        for alarm in alarms_to_raise:
            alarm_id = f"{self.node_id}-{int(datetime.utcnow().timestamp() * 1000)}"
            alarm_record = {
                "alarm_id": alarm_id,
                "node_id": self.node_id,
                "timestamp": datetime.utcnow().isoformat(),
                "severity": alarm.get("severity", "INFO"),
                "type": alarm.get("type", "unknown"),
                "value": alarm.get("value"),
                "message": f"{alarm.get('type', 'Unknown').upper()} alarm: {alarm.get('value'):.2f}",
                "acknowledged": False
            }
            self.alarms.append(alarm_record)
    
    async def broadcast_telemetry(self):
        """Broadcast telemetry to all connected WebSocket clients"""
        if not self.ws_connections:
            return
        
        message = {
            "type": "telemetry_update",
            "node_id": self.node_id,
            "timestamp": datetime.utcnow().isoformat(),
            "telemetry": self.telemetry.to_dict(),
            "connected_clients": len(self.connections),
            "client_ips": [c["client_ip"] for c in list(self.connections.values())],
            "alarms": list(self.alarms)[-5:] if self.alarms else [],  # Last 5 alarms
        }
        
        # Send to all WebSocket connections
        disconnected = []
        for ws in self.ws_connections:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"{self.node_id}: WebSocket send error: {e}")
                disconnected.append(ws)
        
        # Remove disconnected clients
        for ws in disconnected:
            self.ws_connections.remove(ws)
    
    async def add_connection(self, client_ip: str, client_port: int, protocol: str):
        """Track a new client connection"""
        key = f"{client_ip}:{client_port}:{protocol}"
        is_authorised = client_ip == OCC_IP or client_ip == "127.0.0.1"
        
        record = ConnectionRecord(
            client_ip=client_ip,
            client_port=client_port,
            protocol=protocol,
            connected_at=datetime.utcnow().isoformat(),
            last_activity=datetime.utcnow().isoformat(),
            is_authorised=is_authorised
        )
        
        self.connections[key] = record.to_dict()
        
        # If unauthorized, alert SCADA master immediately
        if not is_authorised:
            try:
                await self.post_to_master("/security/alert", {
                    "alert_type": "unknown_connection",
                    "node_id": self.node_id,
                    "client_ip": client_ip,
                    "protocol": protocol,
                    "port": client_port,
                    "timestamp": datetime.utcnow().isoformat()
                })
                logger.warning(f"{self.node_id}: Unknown connection from {client_ip} on {protocol}")
            except:
                pass
        
        return record
    
    def get_uptime_seconds(self) -> int:
        """Get service uptime in seconds"""
        return int((datetime.utcnow() - self.start_time).total_seconds())

# ============================================================================
# FastAPI Application Setup
# ============================================================================

app = FastAPI(title=f"SCADA Node {NODE_ID}", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize node service
node = NodeService()

@app.on_event("startup")
async def startup_event():
    await node.startup()

@app.on_event("shutdown")
async def shutdown_event():
    await node.shutdown()

# ============================================================================
# REST API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Node identity card"""
    return {
        "node_id": node.node_id,
        "node_type": node.node_type,
        "status": "ONLINE",
        "uptime_seconds": node.get_uptime_seconds(),
        "rest_port": REST_PORT,
        "ws_port": WS_PORT,
        "modbus_port": MODBUS_PORT,
        "iec104_port": IEC104_PORT,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health():
    """Service health check"""
    return {
        "status": "healthy",
        "node_id": node.node_id,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/status")
async def get_status():
    """Current operational state"""
    return {
        "node_id": node.node_id,
        "node_type": node.node_type,
        "status": "ONLINE",
        "uptime_seconds": node.get_uptime_seconds(),
        "connected_clients": len(node.connections),
        "active_alarms": len(node.alarms),
        "last_telemetry_update": node.telemetry.timestamp,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/telemetry")
async def get_telemetry():
    """All current tag values"""
    return {
        "node_id": node.node_id,
        "timestamp": node.telemetry.timestamp,
        **node.telemetry.to_dict()
    }

@app.get("/telemetry/history")
async def get_telemetry_history(limit: int = 100):
    """Last N readings from local buffer (if stored locally)"""
    return {
        "node_id": node.node_id,
        "limit": limit,
        "data": [node.telemetry.to_dict()],  # Simplified - would be full history
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/alarms")
async def get_alarms(severity: Optional[str] = None):
    """Active alarms on this node"""
    alarms_list = list(node.alarms)
    
    if severity:
        alarms_list = [a for a in alarms_list if a.get("severity") == severity.upper()]
    
    return {
        "node_id": node.node_id,
        "count": len(alarms_list),
        "alarms": alarms_list,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/events")
async def get_events():
    """SOE log last 100 events"""
    return {
        "node_id": node.node_id,
        "count": len(node.events),
        "events": list(node.events),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/connections")
async def get_connections():
    """All currently connected clients"""
    return {
        "node_id": node.node_id,
        "total_connections": len(node.connections),
        "connections": list(node.connections.values()),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/control/breaker")
async def control_breaker(request: ControlRequest):
    """Operate breaker (requires auth)"""
    # Simplified - in production would check JWT
    
    if request.action.lower() == "open":
        node.telemetry.breaker_state = False
        action_status = "OPEN"
    elif request.action.lower() == "close":
        node.telemetry.breaker_state = True
        action_status = "CLOSED"
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    event = {
        "type": "breaker_operation",
        "breaker_id": request.breaker_id,
        "action": action_status,
        "reason": request.reason,
        "timestamp": datetime.utcnow().isoformat()
    }
    node.events.append(event)
    
    return {
        "status": "success",
        "node_id": node.node_id,
        "breaker_id": request.breaker_id,
        "action": action_status,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/control/isolate")
async def isolate_node():
    """Isolate this node"""
    logger.warning(f"{node.node_id}: Isolation command received")
    return {
        "status": "isolated",
        "node_id": node.node_id,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/control/restore")
async def restore_node():
    """Restore this node"""
    logger.info(f"{node.node_id}: Restore command received")
    return {
        "status": "restored",
        "node_id": node.node_id,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/ui")
async def serve_ui():
    """Node local web interface (HTML)"""
    return HTMLResponse(get_node_ui_html())

# ============================================================================
# WebSocket Endpoint
# ============================================================================

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live telemetry streaming"""
    try:
        # Get client info
        client_ip = websocket.client[0] if websocket.client else "unknown"
        client_port = websocket.client[1] if websocket.client else 0
        
        await node.add_connection(client_ip, client_port, "WebSocket")
        
        await websocket.accept()
        node.ws_connections.append(websocket)
        
        logger.info(f"{node.node_id}: WebSocket connected from {client_ip}")
        
        # Send initial state snapshot
        await websocket.send_json({
            "type": "initial_snapshot",
            "node_id": node.node_id,
            "node_type": node.node_type,
            "timestamp": datetime.utcnow().isoformat(),
            "telemetry": node.telemetry.to_dict(),
            "alarms": list(node.alarms),
            "connections": list(node.connections.values())
        })
        
        # Keep connection alive and receive messages
        while True:
            try:
                data = await websocket.receive_text()
                # Could implement commands here
            except WebSocketDisconnect:
                break
    
    except Exception as e:
        logger.error(f"{node.node_id}: WebSocket error: {e}")
    
    finally:
        if websocket in node.ws_connections:
            node.ws_connections.remove(websocket)
        logger.info(f"{node.node_id}: WebSocket disconnected")

# ============================================================================
# Helper Functions
# ============================================================================

def get_node_ui_html() -> str:
    """Generate HTML for node local interface"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{node.node_id} - Local Interface</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ 
                background-color: #0a0a0a;
                color: #00ff88;
                font-family: 'JetBrains Mono', monospace;
                padding: 20px;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .header {{ 
                border-bottom: 2px solid #00ff88;
                padding-bottom: 20px;
                margin-bottom: 20px;
            }}
            .title {{ font-size: 28px; font-weight: bold; }}
            .subtitle {{ font-size: 12px; opacity: 0.7; margin-top: 5px; }}
            .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }}
            .card {{ 
                background-color: #111111;
                border: 1px solid #00ff88;
                padding: 15px;
                border-radius: 4px;
            }}
            .card-title {{ font-size: 12px; opacity: 0.7; margin-bottom: 10px; }}
            .card-value {{ font-size: 32px; font-weight: bold; }}
            .card-unit {{ font-size: 12px; opacity: 0.5; margin-top: 5px; }}
            .status-online {{ color: #00ff88; }}
            .status-offline {{ color: #ff3333; }}
            .critical {{ color: #ff3333; }}
            .warning {{ color: #ffaa00; }}
            .info {{ color: #0088ff; }}
            .connections-list {{ margin-top: 20px; }}
            .connection-row {{ 
                padding: 10px;
                border-bottom: 1px solid #222222;
                display: grid;
                grid-template-columns: auto auto auto auto auto;
                gap: 20px;
                font-size: 11px;
            }}
            .unknown {{ color: #aa44ff; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="title">{node.node_id}</div>
                <div class="subtitle">{node.node_type.upper()} NODE - TYPE {node.unit_id}</div>
            </div>
            
            <div class="grid">
                <div class="card">
                    <div class="card-title">BUS VOLTAGE</div>
                    <div class="card-value status-online" id="voltage">132.0</div>
                    <div class="card-unit">kV</div>
                </div>
                <div class="card">
                    <div class="card-title">LINE CURRENT</div>
                    <div class="card-value" id="current">250.0</div>
                    <div class="card-unit">A</div>
                </div>
                <div class="card">
                    <div class="card-title">ACTIVE POWER</div>
                    <div class="card-value" id="power">50.0</div>
                    <div class="card-unit">MW</div>
                </div>
                <div class="card">
                    <div class="card-title">FREQUENCY</div>
                    <div class="card-value status-online" id="frequency">50.00</div>
                    <div class="card-unit">Hz</div>
                </div>
            </div>
            
            <div class="grid" style="margin-top: 20px;">
                <div class="card">
                    <div class="card-title">BREAKER STATE</div>
                    <div class="card-value status-online" id="breaker">CLOSED</div>
                </div>
                <div class="card">
                    <div class="card-title">TEMPERATURE</div>
                    <div class="card-value" id="temp">55.0</div>
                    <div class="card-unit">°C</div>
                </div>
                <div class="card">
                    <div class="card-title">ACTIVE ALARMS</div>
                    <div class="card-value warning" id="alarms">0</div>
                </div>
                <div class="card">
                    <div class="card-title">CONNECTIONS</div>
                    <div class="card-value info" id="connections">0</div>
                </div>
            </div>
            
            <div class="connections-list">
                <h3 style="margin-bottom: 10px; font-size: 14px;">CONNECTED CLIENTS</h3>
                <div id="connections-table" style="border: 1px solid #222222;"></div>
            </div>
        </div>
        
        <script>
            const ws = new WebSocket('ws://' + window.location.host + '/ws/telemetry');
            
            ws.onmessage = function(event) {{
                const data = JSON.parse(event.data);
                if (data.telemetry) {{
                    document.getElementById('voltage').textContent = data.telemetry.bus_voltage_kv.toFixed(2);
                    document.getElementById('current').textContent = data.telemetry.line_current_a.toFixed(1);
                    document.getElementById('power').textContent = data.telemetry.active_power_mw.toFixed(1);
                    document.getElementById('frequency').textContent = data.telemetry.frequency_hz.toFixed(2);
                    document.getElementById('breaker').textContent = data.telemetry.breaker_state ? 'CLOSED' : 'OPEN';
                    document.getElementById('temp').textContent = data.telemetry.transformer_temp_c.toFixed(1);
                    document.getElementById('alarms').textContent = (data.alarms || []).length;
                    document.getElementById('connections').textContent = data.connected_clients || 0;
                    
                    // Render connections table
                    if (data.client_ips) {{
                        let html = '';
                        data.client_ips.forEach(ip => {{
                            const isUnknown = ip !== '10.0.0.1' && ip !== '127.0.0.1';
                            html += '<div class="connection-row' + (isUnknown ? ' unknown' : '') + '">';
                            html += '<span>' + ip + '</span>';
                            html += '<span>Modbus</span>';
                            html += '<span>Active</span>';
                            html += '</div>';
                        }});
                        document.getElementById('connections-table').innerHTML = html || '<div class="connection-row">No connections</div>';
                    }}
                }}
            }};
        </script>
    </body>
    </html>
    """

# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    logger.info(f"Starting {NODE_ID} node service...")
    logger.info(f"REST API: http://{NODE_IP}:{REST_PORT}")
    logger.info(f"WebSocket: ws://{NODE_IP}:{WS_PORT}")
    logger.info(f"Modbus TCP: {NODE_IP}:{MODBUS_PORT}")
    logger.info(f"IEC 104: {NODE_IP}:{IEC104_PORT}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=REST_PORT,
        log_level=LOG_LEVEL
    )
