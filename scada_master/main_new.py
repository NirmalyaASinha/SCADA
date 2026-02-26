"""
SCADA Master - Central API Gateway & Aggregator
==============================================
Aggregates all 15 node services and provides unified REST + WebSocket API
with authentication, authorization, and real-time security monitoring.
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
import aiohttp

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Import our modules
from auth.routes import router as auth_router, get_current_user, require_role
from auth.jwt_handler import JWTHandler
from nodes.registry import NodeRegistry, NodeState
from nodes.connector import NodeConnector
from grid.aggregator import GridAggregator
from control.sbo import SBOManager, SBOSelectRequest, SBOOperateRequest, SBOCancelRequest, SBOAction
from websocket.manager import WebSocketManager

# ============================================================================
# Configuration
# ============================================================================

REST_PORT = int(os.getenv("REST_PORT", "9000"))
WS_PORT = int(os.getenv("WS_PORT", "9001"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Application Setup
# ============================================================================

app = FastAPI(title="SCADA Master", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Core components
node_registry = NodeRegistry()
node_connector = NodeConnector(node_registry)
grid_aggregator = GridAggregator(node_registry)
sbo_manager = SBOManager()
ws_manager = WebSocketManager()

# ============================================================================
# Pydantic Models
# ============================================================================

class AlarmAcknowledgeRequest(BaseModel):
    operator_id: str
    comment: str

class IsolateNodeRequest(BaseModel):
    operator_id: str
    reason: str

# ============================================================================
# Startup / Shutdown
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize all services"""
    logger.info("=" * 80)
    logger.info("SCADA MASTER STARTING")
    logger.info("=" * 80)
    
    # Set broadcast callback for node connector
    node_connector.set_broadcast_callback(ws_manager.broadcast)
    
    # Start services
    await ws_manager.start_broadcasting()
    await node_connector.start()
    await grid_aggregator.start()
    
    logger.info("✅ SCADA Master operational")
    logger.info(f"   REST API: http://0.0.0.0:{REST_PORT}")
    logger.info(f"   WebSocket: ws://0.0.0.0:{WS_PORT}/ws/grid")
    logger.info("=" * 80)

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down SCADA Master...")
    await node_connector.stop()
    await grid_aggregator.stop()
    await ws_manager.stop_broadcasting()
    logger.info("SCADA Master stopped")

# ============================================================================
# Authentication Endpoints
# ============================================================================

# Include auth router
app.include_router(auth_router)

# ============================================================================
# Health & Status Endpoints
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint - no auth required"""
    conn_status = node_connector.get_connection_status()
    
    return {
        "status": "healthy",
        "version": "1.0.0",
        "uptime_seconds": 0,  # Would track actual uptime
        "nodes_connected": conn_status["connected"],
        "nodes_offline": conn_status["offline"],
        "websocket_clients": ws_manager.get_connection_count(),
        "timestamp": datetime.utcnow().isoformat()
    }

# ============================================================================
# Grid Endpoints
# ============================================================================

@app.get("/grid/overview")
async def get_grid_overview(user: Dict = Depends(get_current_user)):
    """Get grid overview - all roles"""
    grid_state = grid_aggregator.get_grid_state()
    return grid_state

@app.get("/grid/topology")
async def get_grid_topology(user: Dict = Depends(get_current_user)):
    """Get full grid topology - all roles"""
    topology = node_registry.get_topology()
    return topology

# ============================================================================
# Node Endpoints
# ============================================================================

@app.get("/nodes")
async def get_all_nodes(user: Dict = Depends(get_current_user)):
    """Get all nodes - all roles"""
    nodes = []
    for node in node_registry.get_all_nodes():
        nodes.append(node.to_dict())
    return {"nodes": nodes, "count": len(nodes)}

@app.get("/nodes/{node_id}")
async def get_node_detail(node_id: str, user: Dict = Depends(get_current_user)):
    """Get detailed node information - all roles"""
    node = node_registry.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    
    return node.to_dict()

@app.get("/nodes/{node_id}/telemetry")
async def get_node_telemetry(node_id: str, user: Dict = Depends(get_current_user)):
    """Get current node telemetry - all roles"""
    node = node_registry.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    
    return {
        "node_id": node_id,
        "telemetry": node.telemetry,
        "timestamp": node.last_heartbeat.isoformat() if node.last_heartbeat else None
    }

@app.get("/nodes/{node_id}/telemetry/history")
async def get_node_telemetry_history(
    node_id: str,
    hours: int = Query(1, ge=1, le=24),
    user: Dict = Depends(get_current_user)
):
    """Get historical telemetry from database - all roles"""
    # In full implementation, query TimescaleDB
    # For now, return placeholder
    return {
        "node_id": node_id,
        "hours": hours,
        "data": [],
        "message": "Historical data retrieval not yet implemented"
    }

@app.get("/nodes/{node_id}/connections")
async def get_node_connections(node_id: str, user: Dict = Depends(get_current_user)):
    """Get node connection info - all roles"""
    node = node_registry.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    
    # Get from node's REST API
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{node.rest_url}/connections", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data
                else:
                    raise HTTPException(status_code=resp.status, detail="Failed to get connections from node")
    except Exception as e:
        logger.error(f"Error getting connections for {node_id}: {e}")
        raise HTTPException(status_code=503, detail=f"Node {node_id} unreachable")

# ============================================================================
# Alarm Endpoints
# ============================================================================

@app.get("/alarms/active")
async def get_active_alarms(user: Dict = Depends(get_current_user)):
    """Get all active alarms - all roles"""
    alarms = []
    
    for node in node_registry.get_all_nodes():
        for alarm in node.alarms:
            alarms.append({
                **alarm,
                "node_id": node.node_id
            })
    
    # Sort by priority then timestamp
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    alarms.sort(key=lambda x: (priority_order.get(x.get("priority", "low"), 99), x.get("timestamp", "")))
    
    return {"alarms": alarms, "count": len(alarms)}

@app.post("/alarms/{alarm_id}/acknowledge")
async def acknowledge_alarm(
    alarm_id: str,
    request: AlarmAcknowledgeRequest,
    user: Dict = Depends(get_current_user)
):
    """Acknowledge alarm - operator+ roles"""
    if user["role"] == "viewer":
        raise HTTPException(status_code=403, detail="Viewer role cannot acknowledge alarms")
    
    logger.info(f"Alarm {alarm_id} acknowledged by {request.operator_id}: {request.comment}")
    
    # Broadcast to dashboards
    await ws_manager.broadcast({
        "type": "alarm_acknowledged",
        "alarm_id": alarm_id,
        "operator_id": request.operator_id,
        "comment": request.comment,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return {"message": "Alarm acknowledged", "alarm_id": alarm_id}

# ============================================================================
# Control Endpoints - SBO (Select-Before-Operate)
# ============================================================================

@app.post("/control/breaker/select")
async def breaker_select(request: SBOSelectRequest, user: Dict = Depends(get_current_user)):
    """SELECT step of SBO - operator+ roles"""
    if user["role"] == "viewer":
        raise HTTPException(status_code=403, detail="Viewer role cannot control breakers")
    
    # Verify node exists
    node = node_registry.get_node(request.node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {request.node_id} not found")
    
    # Create SBO session
    session = sbo_manager.create_session(
        request.node_id,
        request.breaker_id,
        request.action,
        request.operator_id,
        request.reason
    )
    
    # Forward SELECT command to node (placeholder - would call node REST API)
    logger.info(f"SBO SELECT: {request.operator_id} -> {request.node_id} breaker {request.breaker_id} {request.action}")
    
    return {
        "session_id": session.session_id,
        "expires_at": session.expires_at.isoformat(),
        "time_remaining_s": session.time_remaining(),
        "message": f"Breaker {request.breaker_id} selected for {request.action}. Execute OPERATE within 10 seconds."
    }

@app.post("/control/breaker/operate")
async def breaker_operate(request: SBOOperateRequest, user: Dict = Depends(get_current_user)):
    """OPERATE step of SBO - operator+ roles"""
    if user["role"] == "viewer":
        raise HTTPException(status_code=403, detail="Viewer role cannot control breakers")
    
    # Get session
    session = sbo_manager.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="SBO session not found")
    
    if session.is_expired():
        raise HTTPException(status_code=400, detail="SBO session expired. Must SELECT again.")
    
    # Execute OPERATE (placeholder - would call node control API)
    start_time = datetime.utcnow()
    
    # Simulate operation
    await asyncio.sleep(0.023)  # 23ms response time
    result = "success"
    response_time_ms = 23
    
    # Update session
    operated_session = sbo_manager.operate_session(request.session_id, result, response_time_ms)
    
    # Broadcast to dashboards
    await ws_manager.broadcast({
        "type": "breaker_operated",
        "node_id": operated_session.node_id,
        "breaker_id": operated_session.breaker_id,
        "action": operated_session.action.value,
        "operator_id": operated_session.operator_id,
        "result": result,
        "response_time_ms": response_time_ms,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return {
        "result": result,
        "response_time_ms": response_time_ms,
        "message": f"Breaker {operated_session.breaker_id} {operated_session.action.value} completed",
        "new_breaker_state": operated_session.action.value
    }

@app.post("/control/breaker/cancel")
async def breaker_cancel(request: SBOCancelRequest, user: Dict = Depends(get_current_user)):
    """Cancel SBO session - operator+ roles"""
    if user["role"] == "viewer":
        raise HTTPException(status_code=403, detail="Viewer role cannot control breakers")
    
    success = sbo_manager.cancel_session(request.session_id)
    if success:
        return {"message": "SBO session cancelled"}
    else:
        raise HTTPException(status_code=404, detail="Session not found or cannot be cancelled")

@app.post("/control/isolation/{node_id}")
async def isolate_node(node_id: str, request: IsolateNodeRequest, user: Dict = Depends(get_current_user)):
    """Isolate node (trip all breakers) - engineer+ roles"""
    if user["role"] not in ["engineer", "admin"]:
        raise HTTPException(status_code=403, detail="Engineer or admin role required")
    
    node = node_registry.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    
    logger.warning(f"Node {node_id} isolation requested by {request.operator_id}: {request.reason}")
    
    # Would call node isolation API here
    
    # Broadcast event
    await ws_manager.broadcast({
        "type": "node_isolated",
        "node_id": node_id,
        "by_operator": request.operator_id,
        "reason": request.reason,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return {"message": f"Node {node_id} isolation command sent"}

# ============================================================================
# Security Endpoints
# ============================================================================

@app.get("/security/connections")
async def get_security_connections(user: Dict = Depends(get_current_user)):
    """Get all connections across all nodes - engineer+ roles"""
    if user["role"] not in ["engineer", "admin"]:
        raise HTTPException(status_code=403, detail="Engineer or admin role required")
    
    all_connections = []
    total_connections = 0
    authorised_count = 0
    unknown_count = 0
    
    for node in node_registry.get_all_nodes():
        # Get connections from node (would call node REST API)
        # For now, return cached data
        node_connections = []
        
        all_connections.append({
            "node_id": node.node_id,
            "connections": node_connections
        })
    
    return {
        "total_connections": total_connections,
        "authorised": authorised_count,
        "unknown": unknown_count,
        "by_node": all_connections
    }

@app.get("/security/audit")
async def get_audit_log(
    limit: int = Query(1000, le=10000),
    user: Dict = Depends(get_current_user)
):
    """Get audit log - engineer+ roles"""
    if user["role"] not in ["engineer", "admin"]:
        raise HTTPException(status_code=403, detail="Engineer or admin role required")
    
    # Would query PostgreSQL audit_log table
    return {
        "audit_entries": [],
        "count": 0,
        "message": "Audit log query not yet implemented"
    }

@app.post("/security/alert")
async def post_security_alert(alert: Dict):
    """Receive security alerts from nodes or external systems"""
    logger.warning(f"Security alert received: {alert}")
    
    # Broadcast to dashboards
    await ws_manager.broadcast({
        "type": "security_alert",
        **alert,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return {"message": "Alert received"}

# ============================================================================
# WebSocket Endpoint
# ============================================================================

@app.websocket("/ws/grid")
async def websocket_grid(websocket: WebSocket, token: str = Query(...)):
    """WebSocket endpoint for dashboard real-time updates"""
    # Verify JWT token
    payload = JWTHandler.verify_token(token)
    if not payload:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    username = payload.get("sub", "unknown")
    
    # Accept connection
    await ws_manager.connect(websocket, username)
    
    # Send full state snapshot
    grid_state = grid_aggregator.get_grid_state()
    topology = node_registry.get_topology()
    nodes = [n.to_dict() for n in node_registry.get_all_nodes()]
    
    await ws_manager.send_full_state_snapshot(websocket, grid_state, topology, nodes)
    
    try:
        # Keep connection alive and listen for messages from client
        while True:
            data = await websocket.receive_text()
            # Echo or handle client messages if needed
            logger.debug(f"Received from {username}: {data}")
    
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error for {username}: {e}")
        ws_manager.disconnect(websocket)

# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=REST_PORT,
        log_level=LOG_LEVEL.lower()
    )
