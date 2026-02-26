# SCADA Web Dashboard - User Guide

## 📊 Overview

The SCADA Web Dashboard provides a comprehensive, real-time monitoring and control interface for the power grid simulation system. Built with **Streamlit** (frontend) and **FastAPI** (backend), it offers:

- **Real-time Monitoring:** Live electrical measurements from all grid nodes
- **Interactive Controls:** Send commands to breakers, generators, and transformers
- **Historical Analysis:** Time-series charts with customizable ranges
- **Alarm Management:** View, filter, and acknowledge system alarms
- **Security Audit:** Complete audit trail of all user actions
- **Role-Based Access:** Viewer, Operator, Engineer, Supervisor, Administrator roles

---

## 🚀 Quick Start

### Option 1: Docker Deployment (Recommended)

```bash
# Start all services including dashboard
./deploy-docker.sh up

# Access dashboard in browser
http://localhost:8501
```

### Option 2: Local Development

```bash
# Terminal 1: Start API Server
python3 api_server.py

# Terminal 2: Start Dashboard
streamlit run dashboard.py

# Access in browser
http://localhost:8501
```

---

## 🔐 Login Credentials

Default users for testing:

| Username | Password | Role | Permissions |
|----------|----------|------|-------------|
| `admin` | `admin123` | Administrator | Full access (all 13 permissions) |
| `operator` | `operator123` | Operator | Read + basic control (6 permissions) |
| `viewer` | `viewer123` | Viewer | Read-only (4 permissions) |

---

## 📱 Dashboard Features

### 1. System Overview

**Navigation:** 📊 System Overview

**Features:**
- Total nodes count and connection status
- Aggregate power generation (MW)
- Active alarms summary (Critical, Warning, Info)
- Real-time timestamp

**Metrics Displayed:**
```
┌─────────────┬──────────────┬────────────────┬──────────────┐
│ Total Nodes │ Total Power  │ Critical Alarms│ Total Alarms │
│     15      │   180.5 MW   │       2        │      5       │
└─────────────┴──────────────┴────────────────┴──────────────┘
```

---

### 2. Node List

**Navigation:** ⚙️ Node List

**Features:**
- Interactive table of all grid nodes
- Node ID, IP address, protocols, connection status
- Select node for detailed view
- Filter and sort capabilities

**Example Output:**
```
Node ID    | IP Address    | Protocols         | Connected
-----------|---------------|-------------------|----------
GEN-001    | 172.20.0.10   | modbus, iec104    | ✓
SUB-T1     | 172.20.0.11   | modbus, iec104    | ✓
DIST-F1    | 172.20.0.20   | modbus            | ✓
```

---

### 3. Node Details

**Navigation:** 🔍 Node Details

**Prerequisites:** Select node from Node List first

**Electrical Measurements:**
- **Voltage (kV)** - Real-time bus voltage
- **Current (A)** - Line current
- **Power (MW)** - Active power
- **Frequency (Hz)** - System frequency

**Breaker Status:**
- 🟢 CLOSED - Breaker is closed, power flowing
- 🔴 OPEN - Breaker is open, no power flow

**Control Buttons:**

| Button | Action | Required Permission |
|--------|--------|---------------------|
| Close Breaker | Close circuit breaker | `CONTROL_BREAKER` |
| Open Breaker | Open circuit breaker | `CONTROL_BREAKER` |
| Reset Alarms | Clear acknowledged alarms | `WRITE_COMMAND` |

**Node-Specific Alarms:**
- Displays active alarms for selected node
- Color-coded by severity (Red=Critical, Yellow=Warning)

---

### 4. Alarm Management

**Navigation:** 🚨 Alarms

**Filters:**
- **Severity:** All, CRITICAL, WARNING, INFO
- **Node ID:** Filter by specific node

**Alarm Details:**
```
🔴 GEN-001 - OVERVOLTAGE
   Severity: CRITICAL
   Value: 145.2 kV
   Time: 2026-02-26 19:30:15
   Description: Voltage above safe threshold (max: 145 kV)
```

**Color Coding:**
- 🔴 CRITICAL - Immediate action required
- 🟡 WARNING - Attention needed
- 🔵 INFO - Normal operational event

---

### 5. Historical Data

**Navigation:** 📈 Historical Data

**Features:**
- Time-range selection (1-24 hours)
- Aggregation intervals (1 min, 5 min, 15 min, 1 hour)
- Interactive Plotly charts with zoom/pan
- Multiple measurement types

**Charts Available:**

1. **Voltage Over Time**
   - Line chart showing kV variations
   - Hover for exact values
   - Zoom to specific time ranges

2. **Power Over Time**
   - Area chart showing MW production/consumption
   - Fill-to-zero for easy visualization
   - Export to PNG/CSV

3. **Frequency Over Time**
   - Line chart with nominal frequency reference (60 Hz)
   - Detect frequency deviations
   - Critical for grid stability

**Usage Example:**
```
1. Select Node: GEN-001
2. Set Hours: 6 hours
3. Set Interval: 15 minutes
4. View interactive charts
5. Hover for exact timestamps/values
6. Click and drag to zoom
7. Double-click to reset zoom
```

---

### 6. Security Audit Log

**Navigation:** 🔐 Audit Log

**Required Permission:** `ADMIN_SECURITY` (Supervisor or Administrator only)

**Features:**
- Complete audit trail of all system events
- Filter by event type
- Configurable result limit (10-1000 events)

**Event Types:**
- `LOGIN_SUCCESS` - Successful authentication
- `LOGIN_FAILURE` - Failed login attempt
- `COMMAND_ISSUED` - Control command sent
- `ACCESS_DENIED` - Permission denied
- `CONFIG_CHANGED` - Configuration modification
- And 10 more event types...

**Audit Entry Example:**
```
Timestamp: 2026-02-26 19:35:42
Event: COMMAND_ISSUED
User: operator
Node: GEN-001
Action: close_breaker
Result: success
Details: {"source_ip": "192.168.1.100", "reason": "scheduled_maintenance"}
```

---

### 7. System Statistics

**Navigation:** 📊 Statistics

**Metrics:**
- Total audit events logged
- Active user sessions
- Total registered users

**Charts:**
- **Events by Type** - Bar chart showing distribution
- **Events by Severity** - Pie chart
- **Events Over Time** - Time-series trend

---

## 🎛️ User Roles & Permissions

### Viewer (Read-Only)
**Permissions (4):**
- ✓ READ_STATUS - View node status
- ✓ READ_MEASUREMENTS - View electrical data
- ✓ READ_ALARMS - View alarms
- ✓ READ_HISTORY - View historical data

**Access:**
- ✓ System Overview
- ✓ Node List
- ✓ Node Details (view only)
- ✓ Alarms (view only)
- ✓ Historical Data
- ✗ Controls (disabled)
- ✗ Audit Log
- ✗ Statistics

---

### Operator (Basic Control)
**Permissions (6):**
- All Viewer permissions +
- ✓ WRITE_COMMAND - Send basic commands
- ✓ CONTROL_BREAKER - Control circuit breakers

**Access:**
- All Viewer access +
- ✓ Breaker controls (Open/Close)
- ✗ Advanced controls (OLTC, Generator)
- ✗ Audit Log

---

### Engineer (Full Control)
**Permissions (9):**
- All Operator permissions +
- ✓ WRITE_CONFIG - Modify configuration
- ✓ CONTROL_OLTC - Control tap changers
- ✓ CONTROL_GENERATOR - Control generators

**Access:**
- All Operator access +
- ✓ Configuration changes
- ✓ Advanced equipment control
- ✗ User management
- ✗ Audit Log

---

### Supervisor (Team Management)
**Permissions (10):**
- All Engineer permissions +
- ✓ ADMIN_USER_MANAGEMENT - Manage users

**Access:**
- All Engineer access +
- ✓ User creation/deletion
- ✓ Audit Log (view only)

---

### Administrator (Full Access)
**Permissions (13):**
- All permissions

**Access:**
- ✓ Everything
- ✓ Full audit log access
- ✓ Security statistics
- ✓ System administration

---

## 🔧 Advanced Features

### Auto-Refresh

**Location:** Sidebar

**Options:**
- Toggle: Enable/Disable auto-refresh
- Rate: 1-10 seconds (default: 2s)

**Behavior:**
- When enabled, dashboard refreshes automatically
- Useful for monitoring real-time changes
- Disable for manual control

---

### WebSocket Real-Time Updates

**Endpoint:** `ws://localhost:8000/ws/realtime`

**Features:**
- Low-latency event streaming
- Bi-directional communication
- Automatic reconnection

**Usage (Advanced):**
```python
import websocket
ws = websocket.WebSocket()
ws.connect("ws://localhost:8000/ws/realtime")
data = ws.recv()
print(f"Received: {data}")
```

---

## 🌐 API Endpoints

The dashboard uses the following REST API endpoints:

### Authentication
- `POST /api/auth/login` - Authenticate user
- `POST /api/auth/logout` - Destroy session

### System Status
- `GET /api/system/overview` - System metrics
- `GET /api/nodes` - List all nodes
- `GET /api/nodes/{node_id}/status` - Node details

### Control
- `POST /api/nodes/{node_id}/command` - Send command

### Alarms
- `GET /api/alarms` - Get alarms (with filters)

### Historical Data
- `POST /api/historian/query` - Query time-series data
- `GET /api/historian/latest/{node_id}` - Latest measurement

### Security
- `GET /api/security/audit` - Audit log (admin only)
- `GET /api/security/statistics` - Security stats (admin only)

### Health
- `GET /health` - API health check
- `GET /` - API information

**Full API Documentation:** http://localhost:8000/docs (Swagger UI)

---

## 🐛 Troubleshooting

### Dashboard Shows "Cannot Connect to API Server"

**Cause:** API server is not running

**Solution:**
```bash
# Start API server
python3 api_server.py

# Or with Docker
./deploy-docker.sh up
```

**Verify:** Check http://localhost:8000/health

---

### Login Fails with Valid Credentials

**Possible Causes:**
1. API server restarted (sessions cleared)
2. Session expired
3. Account locked (brute-force protection)

**Solution:**
1. Logout and login again
2. Wait for lockout timeout (default: 15 minutes)
3. Check API server logs: `tail -f logs/audit.log`

---

### "No Nodes Available"

**Cause:** Simulator not running or nodes not added

**Solution:**
```bash
# Start simulator
python3 simulator.py

# Or check simulator logs
docker-compose logs simulator
```

---

### Historical Charts Show "No Data"

**Cause:** Historian not storing data or time range too old

**Solution:**
1. Verify historian is connected: `GET /health`
2. Check if measurements are being stored
3. Try shorter time range (1 hour instead of 24)
4. Ensure polling is active on SCADA Master

---

### Permission Denied Errors

**Cause:** User role lacks required permission

**Solution:**
1. Check your role in sidebar
2. Login with higher-privilege account
3. Contact administrator to update permissions

**Permission Reference:**
```
Action                  | Required Permission
------------------------|---------------------
View Status            | READ_STATUS
Control Breaker        | CONTROL_BREAKER
Control Generator      | CONTROL_GENERATOR
View Audit Log         | ADMIN_SECURITY
```

---

## 📊 Performance Tips

### For Large Grids (50+ Nodes)

1. **Reduce Auto-Refresh Rate**
   - Set to 5-10 seconds instead of 2s
   - Or disable for manual refresh

2. **Limit Historical Data Range**
   - Use 1-6 hours instead of 24 hours
   - Increase aggregation interval (15 min or 1 hour)

3. **Filter Alarms**
   - Filter by severity (CRITICAL only)
   - Filter by specific nodes

---

### For Slow Networks

1. **Use Aggregated Data**
   - Historical charts with 15-min or 1-hour buckets
   - Reduces data transfer

2. **Selective Monitoring**
   - Focus on critical nodes only
   - Use alarm filters

---

## 🖥️ Browser Compatibility

**Recommended Browsers:**
- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Edge 90+
- ✅ Safari 14+

**Features Requiring Modern Browser:**
- WebSocket support
- Plotly interactive charts
- Streamlit widgets

---

## 📱 Mobile Support

**Status:** Partial support

**Working Features:**
- Login
- System Overview
- Node List
- Alarms (view only)

**Limited Features:**
- Historical charts (zoom/pan may be difficult)
- Small screen navigation

**Recommended:** Use desktop browser for full experience

---

## 🔒 Security Best Practices

1. **Change Default Passwords**
   ```python
   # In production, update default user passwords
   auth_manager.create_user("admin", "STRONG_PASSWORD", Role.ADMINISTRATOR)
   ```

2. **Use HTTPS in Production**
   - Configure SSL certificates
   - Update API_BASE_URL to https://

3. **Limit Session Timeout**
   - Default: 30 minutes
   - Strict mode: 15 minutes
   - Configure in `security/security_config.py`

4. **Monitor Audit Log**
   - Review failed login attempts
   - Check for suspicious activity
   - Set up alerts for SECURITY_VIOLATION events

5. **Disable Auto-Refresh on Public Networks**
   - Reduces data exposure
   - Manual refresh for sensitive operations

---

## 🔄 Update & Maintenance

### Update Dashboard Code

```bash
# Pull latest code
git pull origin main

# Install new dependencies
pip install -r requirements.txt

# Restart services
./deploy-docker.sh restart
```

### Clear Browser Cache

If dashboard shows stale data:
1. Hard refresh: `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac)
2. Clear browser cache
3. Restart browser

---

## 📖 Additional Resources

- **API Documentation:** http://localhost:8000/docs
- **Project Status:** [PROJECT_STATUS.md](PROJECT_STATUS.md)
- **Docker Guide:** [DOCKER_README.md](DOCKER_README.md)
- **GitHub Repository:** https://github.com/NirmalyaASinha/SCADA

---

## 💡 Tips & Tricks

### Keyboard Shortcuts

- `Ctrl+R` - Refresh page
- `Ctrl+/` - Toggle sidebar (in some browsers)
- `Esc` - Close popups/modals

### URL Parameters

Access specific pages directly:
```
http://localhost:8501/?page=alarms
http://localhost:8501/?page=historical
```

### Export Data

**Historical Charts:**
1. Hover over chart
2. Click camera icon (top-right)
3. Save as PNG

**Audit Log:**
1. View audit log table
2. Right-click → Save As
3. Or copy to clipboard

---

## 🆘 Support

**Issues:** Report bugs at https://github.com/NirmalyaASinha/SCADA/issues

**Questions:** Check PROJECT_STATUS.md for comprehensive documentation

---

**Version:** 1.0.0  
**Last Updated:** February 26, 2026  
**Author:** Nirmalya A Sinha
