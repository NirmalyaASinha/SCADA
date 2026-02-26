# SCADA Critical Infrastructure Simulator

A **production-grade distributed SCADA (Supervisory Control and Data Acquisition) system** with 15 independent microservices simulating a realistic electrical grid network with real-time telemetry, security monitoring, and operator control capabilities.

## 🏗️ System Architecture

### Overview
- **15 Independent Node Services**: 3 generators (GEN), 7 transmission substations (SUB), 5 distribution feeders (DIST)
- **Central SCADA Master API**: FastAPI with JWT authentication and real-time WebSocket aggregation
- **Supporting Database Services**: PostgreSQL/TimescaleDB (telemetry historian), Redis (caching/sessions)
- **Monitoring Stack**: Prometheus (metrics), Grafana (visualization), NTP (time sync)
- **Security Features**: JWT RBAC authentication, audit logging, network isolation via Docker

### Service Topology

```
SCADA Master (9000-9001)
    ├── Generation Layer (GEN-001 to GEN-003)
    │   ├── REST APIs (8101, 8103, 8105)
    │   └── WebSocket (8102, 8104, 8106)
    │
    ├── Transmission Layer (SUB-001 to SUB-007)
    │   ├── REST APIs (8111-8124, odd ports)
    │   └── WebSocket (8112-8124, even ports)
    │
    ├── Distribution Layer (DIST-001 to DIST-005)
    │   ├── REST APIs (8131-8140, odd ports)
    │   └── WebSocket (8132-8140, even ports)
    │
    └── Backend Services
        ├── TimescaleDB (5432) - Historical data
        ├── Redis (6379) - Sessions & cache
        ├── Prometheus (9090) - Metrics collection
        ├── Grafana (3001) - Dashboard visualization
        └── NTP (123) - Time synchronization
```

## 📁 Project Structure

```
SCADA_SIM/
├── docker-compose-production.yml    # 20-service Docker Compose configuration
├── scada_master/                    # Central SCADA aggregator API
│   ├── main_new.py                  # FastAPI application (9000)
│   ├── Dockerfile_new               # Multi-stage build for master
│   ├── requirements.txt              # Python dependencies
│   ├── nodes/
│   │   ├── registry.py              # Node tracking & state management
│   │   ├── connector.py             # WebSocket connection handler
│   │   └── routes.py                # API endpoints for node control
│   ├── grid/
│   │   ├── aggregator.py            # Real-time grid state calculation
│   │   └── power_flow.py            # DC power flow solver
│   ├── auth/
│   │   ├── routes.py                # JWT authentication endpoints
│   │   └── models.py                # User/role models
│   └── logs/                        # Master audit logs
│
├── node_service/                    # Shared node simulation logic
│   ├── main.py                      # FastAPI node service (ports 8101-8140)
│   ├── Dockerfile                   # Single Dockerfile for all node services
│   ├── requirements.txt              # Dependencies (FastAPI, asyncio, etc)
│   ├── simulator.py                 # Grid physics & power flow
│   ├── config.py                    # Node configurations (loads, generators)
│   └── protocols/
│       ├── modbus.py               # TCP Modbus server
│       └── iec104.py               # IEC 60870-5-104 protocol handler
│
├── anomaly_engine/                  # ML-based anomaly detection
│   ├── main.py                      # FastAPI service
│   ├── models.py                    # Anomaly detection models
│   └── Dockerfile                   # Container image
│
├── monitor.py                       # 🎯 CLI monitoring tool for operators
├── check-grid.sh                    # Quick bash health check script
├── simulator.py                     # Python power grid simulator
├── config.py                        # Global configuration
│
└── logs/
    ├── audit.log                    # Authentication & control audit trail
    └── simulation.log               # Grid simulation events
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose (v20+)
- Python 3.8+ (for CLI tools)
- 8GB+ RAM, 10GB+ disk space
- Linux/Mac/Windows with Bash

### Start the System

```bash
cd /path/to/SCADA_SIM

# Start all 20 services
docker compose -f docker-compose-production.yml up -d

# Wait ~10 seconds for services to start and stabilize
sleep 10

# Verify system is operational
curl http://localhost:9000/health | python3 -m json.tool
```

### Verify System Health

```bash
# Quick health check - should show all 15 nodes connected
curl http://localhost:9000/health | python3 -m json.tool

# Expected output:
# {
#   "status": "healthy",
#   "version": "1.0.0",
#   "nodes_connected": 15,
#   "nodes_offline": 0
# }
```

## 📊 Monitoring & Operations

### Primary Monitoring Tool: `monitor.py`

The main tool for operators to check grid status:

```bash
# Single status check
cd /home/nirmalya/Desktop/SCADA_SIM
python3 monitor.py

# Continuous monitoring (updates every 5 seconds)
python3 monitor.py -c -i 5
```

**Output displays:**
- Real-time grid metrics (frequency, generation, load, transmission losses)
- All 15 nodes with connection status (CONNECTED/OFFLINE)
- Service health status (SCADA Master, TimescaleDB, Redis, Prometheus)

### Alternative Monitoring

```bash
# Quick bash health check
./check-grid.sh

# Grid metrics via API (requires login)
TOKEN=$(curl -s -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"scada@2024"}' | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:9000/grid/overview | python3 -m json.tool
```

### Web-Based Monitoring

| Service | URL | Purpose |
|---------|-----|---------|
| **SCADA Master API** | http://localhost:9000 | REST + WebSocket endpoints |
| **Grafana Dashboards** | http://localhost:3001 | Metrics visualization |
| **Prometheus** | http://localhost:9090 | Metrics browser |

## 🔐 Authentication

All API endpoints (except /health) require JWT authentication.

### Default Credentials

```
Admin User:
  Username: admin
  Password: scada@2024

Other Users:
  operator / scada@2024 (operator access)
  engineer / scada@2024 (engineer access)
  viewer / scada@2024 (read-only)
```

### Get Authentication Token

```bash
curl -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"scada@2024"}'
```

### Use Token in Requests

```bash
TOKEN="<token_from_login_response>"

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:9000/grid/overview
```

## 📡 Key API Endpoints

### Health (No Auth)
```
GET /health
Returns: System status, node counts, uptime
```

### Authentication
```
POST /auth/login
Body: {"username": "admin", "password": "scada@2024"}
Returns: {"access_token": "...", "token_type": "bearer"}
```

### Grid Data (Requires Auth)
```
GET /grid/overview
Returns: Frequency, generation, load, losses, node stats

GET /nodes
Returns: List of all 15 nodes with current state

WS /ws/grid
WebSocket: Real-time grid updates (~1-2 Hz)
```

## 🔌 Node Details

### Node Services (15 Total)

- **Generation (3)**: GEN-001, GEN-002, GEN-003 (ports 8101, 8103, 8105)
- **Transmission (7)**: SUB-001 to SUB-007 (ports 8111-8124)
- **Distribution (5)**: DIST-001 to DIST-005 (ports 8131-8140)

### Node Status States

- **CONNECTING**: Initial connection attempt
- **CONNECTED**: Successfully connected to SCADA Master
- **RECONNECTING**: Lost connection, retrying
- **DEGRADED**: Connection unstable
- **OFFLINE**: No connection to master

## 🛠️ Development

### Common Tasks

#### Check Node Connection Status
```bash
# View real-time node status
python3 monitor.py

# Check master logs
docker logs scada_master_prod | grep "GEN-001"
```

#### Restart a Node
```bash
docker compose -f docker-compose-production.yml restart node_gen001
```

#### View All Nodes via API
```bash
TOKEN=$(curl -s -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"scada@2024"}' | \
  python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:9000/nodes | python3 -m json.tool
```

#### View Service Logs
```bash
# Master logs
docker logs scada_master_prod -f --tail 50

# Node logs (e.g., GEN-001)
docker logs scada_node_gen001 -f --tail 50

# All services
docker compose -f docker-compose-production.yml logs -f
```

### System Management

#### Restart All Services
```bash
docker compose -f docker-compose-production.yml restart
```

#### Stop System
```bash
docker compose -f docker-compose-production.yml down
```

#### Full Reset (Clears Data)
```bash
docker compose -f docker-compose-production.yml down -v
docker compose -f docker-compose-production.yml up -d
```

## 🚨 Troubleshooting

### Nodes Not Connecting

```bash
# Check if nodes are running
docker compose ps | grep node_

# Check master connection attempts
docker logs scada_master_prod | grep "Connection\|failed"

# Check node health
curl http://localhost:8101/health
```

### Services Not Starting

```bash
# View full logs
docker compose logs

# Check Docker disk space
docker system df

# Rebuild images
docker compose build --no-cache
```

## ✅ Verification Checklist

When system is running, verify:

- [ ] Health endpoint: `curl http://localhost:9000/health` → healthy
- [ ] All 15 nodes: `python3 monitor.py` → 15/15 CONNECTED
- [ ] Login works: `curl -X POST http://localhost:9000/auth/login ...`
- [ ] Grid data: `curl -H "Authorization: Bearer $TOKEN" http://localhost:9000/grid/overview`
- [ ] Grafana: http://localhost:3001 (admin/admin)

## 👥 For New Team Members

### Getting Started
1. Clone repository and navigate to SCADA_SIM directory
2. Run: `docker compose -f docker-compose-production.yml up -d`
3. Monitor: `python3 monitor.py`
4. Explore: Review curl commands in API section
5. Investigate: Check logs with `docker compose logs`

### Key Files
- **README.md** - This file (overview and reference)
- **docker-compose-production.yml** - All service definitions
- **scada_master/main_new.py** - Master API logic
- **node_service/main.py** - Individual node implementation

---

**Version**: 1.0.0 - Production Ready  
**Last Updated**: February 26, 2026  
**Status**: ✅ All 15 nodes operational and connected
