"""
FastAPI REST API Server for SCADA Dashboard
Provides real-time data access, control endpoints, and authentication
"""

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import json
import logging

from scada_master_secure import SecureSCADAMaster
from historians.timescaledb import TimescaleDBHistorian
from security.auth import AuthManager, Permission

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="SCADA Dashboard API",
    description="REST API for SCADA System Monitoring and Control",
    version="1.0.0"
)

# CORS configuration for web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Global instances
scada_master: Optional[SecureSCADAMaster] = None
historian: Optional[TimescaleDBHistorian] = None
auth_manager: Optional[AuthManager] = None
active_sessions: Dict[str, str] = {}  # token -> session_id mapping
websocket_clients: List[WebSocket] = []

# ============================================================================
# Data Models
# ============================================================================

class LoginRequest(BaseModel):
    username: str
    password: str
    
class LoginResponse(BaseModel):
    token: str
    username: str
    role: str
    expires_at: str

class CommandRequest(BaseModel):
    node_id: str
    action: str
    value: Optional[Any] = None

class NodeStatusResponse(BaseModel):
    node_id: str
    voltage_kv: float
    current_a: float
    power_mw: float
    frequency_hz: float
    breaker_closed: bool
    timestamp: str
    alarms: List[Dict] = []

class AlarmResponse(BaseModel):
    id: int
    node_id: str
    alarm_type: str
    severity: str
    timestamp: str
    value: float
    description: str
    acknowledged: bool = False

class HistoricalDataRequest(BaseModel):
    node_id: str
    start_time: datetime
    end_time: datetime
    bucket_interval: str = "5 minutes"

# ============================================================================
# Authentication Helper
# ============================================================================

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token and return session_id"""
    token = credentials.credentials
    
    if token not in active_sessions:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    session_id = active_sessions[token]
    
    # Validate session is still active
    if not scada_master.auth_manager.validate_session(session_id):
        del active_sessions[token]
        raise HTTPException(status_code=401, detail="Session expired")
    
    return session_id

# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize SCADA components on startup"""
    global scada_master, historian, auth_manager
    
    logger.info("Starting SCADA API Server...")
    
    # Initialize SCADA Master
    scada_master = SecureSCADAMaster()
    auth_manager = scada_master.auth_manager
    
    # Initialize historian
    historian = TimescaleDBHistorian(use_mock=True)
    await historian.connect()
    
    logger.info("SCADA API Server started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global scada_master, historian
    
    logger.info("Shutting down SCADA API Server...")
    
    if scada_master:
        await scada_master.stop()
    
    if historian:
        await historian.disconnect()
    
    logger.info("SCADA API Server stopped")

# ============================================================================
# Authentication Endpoints
# ============================================================================

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Authenticate user and create session"""
    try:
        session_id = scada_master.login(
            username=request.username,
            password=request.password,
            source_ip="dashboard"
        )
        
        if not session_id:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Generate token (in production, use JWT)
        token = f"token_{session_id}"
        active_sessions[token] = session_id
        
        # Get user info
        user = auth_manager.users.get(request.username)
        session = auth_manager.sessions.get(session_id)
        
        return LoginResponse(
            token=token,
            username=request.username,
            role=user.role.value,
            expires_at=session.expires_at.isoformat()
        )
    
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@app.post("/api/auth/logout")
async def logout(session_id: str = Depends(verify_token)):
    """Logout and destroy session"""
    scada_master.logout(session_id)
    
    # Remove token from active sessions
    for token, sid in list(active_sessions.items()):
        if sid == session_id:
            del active_sessions[token]
    
    return {"status": "logged out"}

# ============================================================================
# System Status Endpoints
# ============================================================================

@app.get("/api/system/overview")
async def get_system_overview(session_id: str = Depends(verify_token)):
    """Get overall system status"""
    try:
        nodes = scada_master.nodes
        total_nodes = len(nodes)
        connected_nodes = sum(1 for n in nodes.values() if n.get("connected", False))
        
        # Get alarms
        alarms = await scada_master.get_alarms()
        critical_alarms = len([a for a in alarms if a.get("severity") == "CRITICAL"])
        warning_alarms = len([a for a in alarms if a.get("severity") == "WARNING"])
        
        # Calculate total power
        total_power = 0.0
        for node_id in nodes:
            try:
                status = await scada_master.get_node_status_secure(session_id, node_id)
                if status and "power_mw" in status:
                    total_power += status["power_mw"]
            except:
                pass
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_nodes": total_nodes,
            "connected_nodes": connected_nodes,
            "disconnected_nodes": total_nodes - connected_nodes,
            "total_power_mw": round(total_power, 2),
            "critical_alarms": critical_alarms,
            "warning_alarms": warning_alarms,
            "total_alarms": len(alarms)
        }
    
    except Exception as e:
        logger.error(f"Error getting system overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/nodes")
async def get_all_nodes(session_id: str = Depends(verify_token)):
    """Get list of all nodes"""
    try:
        nodes = scada_master.nodes
        node_list = []
        
        for node_id, node_info in nodes.items():
            node_list.append({
                "node_id": node_id,
                "ip_address": node_info.get("ip", "unknown"),
                "protocols": list(node_info.get("ports", {}).keys()),
                "connected": node_info.get("connected", False)
            })
        
        return {"nodes": node_list}
    
    except Exception as e:
        logger.error(f"Error getting nodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/nodes/{node_id}/status", response_model=NodeStatusResponse)
async def get_node_status(node_id: str, session_id: str = Depends(verify_token)):
    """Get detailed status of a specific node"""
    try:
        status = await scada_master.get_node_status_secure(session_id, node_id)
        
        if not status:
            raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
        
        # Get node-specific alarms
        all_alarms = await scada_master.get_alarms()
        node_alarms = [a for a in all_alarms if a.get("node_id") == node_id]
        
        return NodeStatusResponse(
            node_id=node_id,
            voltage_kv=status.get("voltage_kv", 0.0),
            current_a=status.get("current_a", 0.0),
            power_mw=status.get("power_mw", 0.0),
            frequency_hz=status.get("frequency_hz", 60.0),
            breaker_closed=status.get("breaker_closed", False),
            timestamp=datetime.now().isoformat(),
            alarms=node_alarms
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting node status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Control Endpoints
# ============================================================================

@app.post("/api/nodes/{node_id}/command")
async def send_command(
    node_id: str,
    command: CommandRequest,
    session_id: str = Depends(verify_token)
):
    """Send control command to a node"""
    try:
        success = await scada_master.send_command_secure(
            session_id=session_id,
            node_id=node_id,
            action=command.action,
            value=command.value
        )
        
        if success:
            return {
                "status": "success",
                "node_id": node_id,
                "action": command.action,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=403, detail="Command not authorized or failed")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending command: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Alarm Endpoints
# ============================================================================

@app.get("/api/alarms")
async def get_alarms(
    severity: Optional[str] = None,
    node_id: Optional[str] = None,
    session_id: str = Depends(verify_token)
):
    """Get all active alarms with optional filtering"""
    try:
        alarms = await scada_master.get_alarms()
        
        # Filter by severity
        if severity:
            alarms = [a for a in alarms if a.get("severity") == severity.upper()]
        
        # Filter by node_id
        if node_id:
            alarms = [a for a in alarms if a.get("node_id") == node_id]
        
        return {"alarms": alarms, "count": len(alarms)}
    
    except Exception as e:
        logger.error(f"Error getting alarms: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Historical Data Endpoints
# ============================================================================

@app.post("/api/historian/query")
async def query_historical_data(
    request: HistoricalDataRequest,
    session_id: str = Depends(verify_token)
):
    """Query historical time-series data"""
    try:
        # Get measurements
        measurements = await historian.get_measurements(
            node_id=request.node_id,
            start_time=request.start_time,
            end_time=request.end_time,
            limit=10000
        )
        
        # Get aggregated stats
        stats = await historian.get_aggregated_stats(
            node_id=request.node_id,
            start_time=request.start_time,
            end_time=request.end_time,
            bucket_interval=request.bucket_interval
        )
        
        return {
            "node_id": request.node_id,
            "measurements": [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "voltage_kv": m.voltage_kv,
                    "current_a": m.current_a,
                    "power_mw": m.power_mw,
                    "frequency_hz": m.frequency_hz,
                    "breaker_closed": m.breaker_closed
                }
                for m in measurements
            ],
            "statistics": stats
        }
    
    except Exception as e:
        logger.error(f"Error querying historical data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/historian/latest/{node_id}")
async def get_latest_measurement(
    node_id: str,
    session_id: str = Depends(verify_token)
):
    """Get latest measurement for a node"""
    try:
        measurement = await historian.get_latest_measurement(node_id)
        
        if not measurement:
            raise HTTPException(status_code=404, detail="No data found")
        
        return {
            "node_id": node_id,
            "timestamp": measurement.timestamp.isoformat(),
            "voltage_kv": measurement.voltage_kv,
            "current_a": measurement.current_a,
            "power_mw": measurement.power_mw,
            "frequency_hz": measurement.frequency_hz,
            "breaker_closed": measurement.breaker_closed
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting latest measurement: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Audit & Security Endpoints
# ============================================================================

@app.get("/api/security/audit")
async def get_audit_events(
    limit: int = 100,
    event_type: Optional[str] = None,
    session_id: str = Depends(verify_token)
):
    """Get audit log events (admin only)"""
    try:
        events = scada_master.get_audit_events(
            session_id=session_id,
            filters={"event_type": event_type} if event_type else {}
        )
        
        # Limit results
        events = events[:limit]
        
        return {"events": events, "count": len(events)}
    
    except Exception as e:
        logger.error(f"Error getting audit events: {e}")
        raise HTTPException(status_code=403, detail="Access denied or error")

@app.get("/api/security/statistics")
async def get_security_statistics(session_id: str = Depends(verify_token)):
    """Get security statistics (admin only)"""
    try:
        stats = scada_master.get_security_statistics(session_id)
        return stats
    
    except Exception as e:
        logger.error(f"Error getting security statistics: {e}")
        raise HTTPException(status_code=403, detail="Access denied or error")

# ============================================================================
# WebSocket for Real-Time Updates
# ============================================================================

@app.websocket("/ws/realtime")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time data streaming"""
    await websocket.accept()
    websocket_clients.append(websocket)
    
    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep connection alive and send updates
        while True:
            try:
                # Wait for client messages (ping/pong)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                
                # Echo back (can implement commands here)
                await websocket.send_json({
                    "type": "echo",
                    "data": data,
                    "timestamp": datetime.now().isoformat()
                })
            
            except asyncio.TimeoutError:
                # Send periodic updates even without client messages
                pass
            
            # Small delay to prevent CPU overload
            await asyncio.sleep(0.1)
    
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
        websocket_clients.remove(websocket)
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in websocket_clients:
            websocket_clients.remove(websocket)

async def broadcast_update(message: dict):
    """Broadcast message to all connected WebSocket clients"""
    for client in websocket_clients[:]:  # Copy list to avoid modification during iteration
        try:
            await client.send_json(message)
        except Exception as e:
            logger.error(f"Error broadcasting to client: {e}")
            websocket_clients.remove(client)

# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "scada_master": "running" if scada_master else "not initialized",
        "historian": "connected" if historian and historian.is_connected else "disconnected"
    }

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "SCADA Dashboard API",
        "version": "1.0.0",
        "status": "running",
        "documentation": "/docs",
        "websocket": "/ws/realtime"
    }

# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
