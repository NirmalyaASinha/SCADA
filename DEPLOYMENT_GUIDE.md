# SCADA Master & Dashboard Deployment Guide

## ✅ WHAT HAS BEEN BUILT

### PART 1: SCADA MASTER SERVICE (Ports 9000/9001)

Complete microservices backend with:

**Authentication System:**
- JWT token-based authentication
- Role-based access control (viewer, operator, engineer, admin)
- Hardcoded users: admin/scada@2024, operator1/ops@2024, engineer1/eng@2024, viewer1/view@2024
- Session management and audit logging

**Node Management:**
- WebSocket connections to all 15 node services
- Automatic reconnection with exponential backoff
- Health monitoring and state tracking
- Telemetry aggregation

**Grid Operations:**
- Real-time grid state aggregation (generation, load, frequency, loss)
- Grid topology with 15 nodes (3 generation, 7 transmission, 5 distribution)
- Frequency trending (10-minute history)
- Voltage violation detection

**Control Features:**
- Select-Before-Operate (SBO) breaker control
- Node isolation capability (engineer+ role)
- Operator action audit logging
- Response time tracking

**Security:**
- Unknown connection detection
- Security event logging
- Connection monitoring across all nodes
- Audit trail for all actions

**WebSocket Server:**
- Real-time dashboard updates
- Event broadcasting (telemetry, alarms, security events)
- Throttled updates (1Hz per node for telemetry)
- Client state management

### PART 2: REACT DASHBOARD (Port 3000)

Production-grade React 18 application with:

**Features:**
- Dark-themed professional UI
- Login page with authentication
- Grid overview with KPI metrics
- Node list and individual node detail pages
- Control panel for breaker operations
- Alarm management
- **Critical: Security Console** with connection monitoring
- Historian for historical data queries
- Settings page

**Technical Stack:**
- Vite + React 18 + Tailwind CSS
- Zustand for state management
- Axios with JWT interceptor
- WebSocket for real-time updates
- React Flow (for future topology visualization)
- Recharts for graphs
- React Hot Toast for notifications
- Lucide React icons

**Security Console (Critical Feature):**
- Real-time connection monitor showing all active connections
- Purple highlighting for unknown/unauthorized connections
- Automatic alerts when new unknown connections detected
- Toast notifications with connection details
- Block button to isolate compromised nodes
- Live badge counter in sidebar

### PART 3: INFRASTRUCTURE

**Docker Compose Setup:**
- 15 Node services (gen001-003, sub001-007, dist001-005)
- TimescaleDB (telemetry storage)
- Redis (caching, sessions)
- Prometheus (metrics)
- Grafana (visualization)
- NTP Server (time synchronization)
- SCADA Master (central hub)
- React Dashboard (frontend)
- Nginx (reverse proxy)

**Database Schema:**
- Node metadata and configuration
- Time-series telemetry (TimescaleDB hypertable)
- Alarms history
- Connections tracking
- **NEW:** Authentication log
- **NEW:** Operator actions audit
- **NEW:** Security events log
- **NEW:** Full audit trail

**Networking:**
- generation_net: 10.1.0.0/16 (3 generator nodes)
- transmission_net: 10.2.0.0/16 (7 substation nodes)
- distribution_net: 10.3.0.0/16 (5 distribution nodes)
- occ_net: 10.0.0.0/16 (central operations network)

## 📋 DEPLOYMENT STEPS

### 1. Replace Old Files with New Implementations

```bash
cd /home/nirmalya/Desktop/SCADA_SIM

# SCADA Master
cp scada_master/main_new.py scada_master/main.py
rm scada_master/main_new.py
cp scada_master/Dockerfile_new scada_master/Dockerfile
rm scada_master/Dockerfile_new

# Dashboard
cp dashboard/src/App_new.jsx dashboard/src/App.jsx
rm dashboard/src/App_new.jsx
cp dashboard/Dockerfile_new dashboard/Dockerfile
rm dashboard/Dockerfile_new
```

### 2. Update Requirements

The SCADA Master requires these new packages:
- fastapi==0.104.1
- uvicorn==0.24.0
- python-jose==3.3.0
- passlib==1.7.4
- bcrypt==4.1.1
- websockets==12.0
- aiohttp==3.9.1
- pydantic==2.5.0

These are already in scada_master/requirements.txt

### 3. Deploy Using New Launch Script

```bash
chmod +x launch_new.sh
./launch_new.sh
```

This will:
1. Start infrastructure (DB, Redis, Prometheus, Grafana)
2. Initialize database with new tables
3. Start all 15 node services
4. Build and start SCADA Master
5. Build and start React Dashboard
6. Start Nginx reverse proxy
7. Display access information

### 4. Access the System

**Dashboard Login:**
- URL: http://localhost:3000
- Username: admin
- Password: scada@2024

**Default Users:**
- admin / scada@2024 (full admin rights)
- operator1 / ops@2024 (breaker control, alarms)
- engineer1 / eng@2024 (node isolation, security console)
- viewer1 / view@2024 (read-only access)

## 🧪 TESTING THE SYSTEM

### Test 1: Grid Status
```bash
curl http://localhost:9000/health
```

### Test 2: Login and Get Token (REST API)
```bash
TOKEN=$(curl -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"scada@2024"}' | jq -r '.access_token')
echo $TOKEN
```

### Test 3: Get All Nodes
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:9000/nodes
```

### Test 4: Get Grid Overview
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:9000/grid/overview
```

### Test 5: Security Test - Trigger Unknown Connection Alert

From a second terminal on the same network:
```python
from pymodbus.client import ModbusTcpClient
import time

# Use localhost if on same machine, or host IP if on another machine
client = ModbusTcpClient('localhost', port=5032)
client.connect()

# Read some registers - this will appear as unknown connection
for i in range(5):
    result = client.read_holding_registers(0, 5, slave=6)
    print(f"Read {i}: {result.registers if hasattr(result, 'registers') else result}")
    time.sleep(1)

client.close()
```

Then check the **Security Console** on the dashboard (port 3000):
- You should see a purple-highlighted row with your IP
- Marked as "UNKNOWN" connection
- A toast notification should appear with connection details

### Test 6: SBO Control Test

Login as operator1 (ops@2024) and:
1. Go to Control Panel
2. Select a node and breaker
3. Click SELECT - counts down 10 seconds
4. Within 10 seconds, click OPERATE
5. Should see confirmation message

## 📊 MONITORING

- **Grafana**: http://localhost:3001 (admin/admin123)
- **Prometheus**: http://localhost:9090
- **TimescaleDB**: Access via pgAdmin if configured
- **Redis**: Access via Redis CLI on port 6379

## 🛑 STOPPING & CLEANUP

```bash
# Stop all services
./stop.sh

# Check status
./status.sh

# Full reset (WARNING: Deletes all data)
./reset.sh
```

## 🔧 TROUBLESHOOTING

### SCADA Master won't start
```bash
docker compose -f docker-compose-production.yml logs scada_master
```

### Dashboard won't connect
- Ensure SCADA Master is running: `curl http://localhost:9000/health`
- Check browser console for WebSocket errors
- Verify token is valid

### Unknown connections not showing
- Ensure you're connecting from a different IP/container
- Check that the pymodbus connection is successful
- Refresh Security Console page

### Node services failing
- All 15 nodes must be running first
- Check individual node health: `curl http://localhost:8101/health`
- Verify all ports (8101-8139) are accessible

## 📝 KEY FILES CREATED/MODIFIED

**SCADA Master:**
- scada_master/main_new.py (→ main.py)
- scada_master/Dockerfile_new (→ Dockerfile)
- scada_master/requirements.txt (updated)
- scada_master/auth/ (models, jwt_handler, routes)
- scada_master/nodes/ (registry, connector)
- scada_master/grid/ (aggregator)
- scada_master/control/ (sbo)
- scada_master/websocket/ (manager)

**Dashboard:**
- dashboard/src/App_new.jsx (→ App.jsx)
- dashboard/src/index.css (global styles + Tailwind)
- dashboard/src/index.js (React entry point)
- dashboard/src/api/ (client, auth, grid, nodes, control, security, alarms)
- dashboard/src/store/ (auth, grid, nodes, alarms, security)
- dashboard/src/hooks/ (useGridWebSocket)
- dashboard/Dockerfile_new (→ Dockerfile)
- dashboard/tailwind.config.js
- dashboard/postcss.config.js
- dashboard/package.json (updated dependencies)

**Infrastructure:**
- docker-compose-production.yml (updated service definitions)
- nginx/nginx_simple.conf (new simplified config)
- database/init.sql (added tables)
- launch_new.sh (→ launch.sh)

## ✨ CRITICAL FEATURE: SECURITY CONSOLE

The Security Console is THE central security feature of the dashboard:

1. **Real-time Connection Monitoring**
   - Shows ALL connections on ALL nodes
   - Groups by node, protocol, IP address
   - Updated automatically via WebSocket

2. **Unknown Connection Detection**
   - Purple highlighting for unauthorized connections
   - Pulsing animation on unknown rows
   - Automatic toast notifications

3. **Evidence of Security**
   - When an unknown client connects to any node via Modbus TCP, IEC104, or REST
   - Immediately visible in Security Console
   - Can block/isolate node from same panel

4. **Tests**:
   - From another machine, run Modbus client
   - Should see your IP in purple on dashboard instantly
   - Click BLOCK to isolate that node

## 🎯 NEXT STEPS

1. **Run launch_new.sh** to deploy everything
2. **Login to dashboard** at http://localhost:3000
3. **Verify all 15 nodes** visible and green
4. **Test Security Console** with Modbus client from another machine
5. **Test SBO Control** with operator login
6. **Monitor via Grafana** at http://localhost:3001

All services will be running on your local network and accessible from other machines on the same network!
