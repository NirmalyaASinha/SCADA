# Production-Faithful SCADA Simulator for Indian Power Grid

A high-fidelity simulation of Indian power grid SCADA infrastructure for cybersecurity research, anomaly detection training, and ICS protocol analysis.

## Overview

This simulator replicates a 15-node power grid with:
- **3 Generation stations** (500MW coal, 300MW hydro, 200MW solar)
- **7 Transmission substations** (400kV)
- **5 Distribution substations** (132kV)

Implements real electrical engineering, authentic ICS protocols, and operational procedures matching actual Indian grid (GRID-INDIA/POSOCO) characteristics.

## Why We Built This System

This system exists to provide a realistic, controllable, and auditable SCADA environment for:
- cybersecurity research and attack/defense simulation
- anomaly detection training with ground-truth telemetry
- protocol behavior analysis (Modbus TCP, IEC 60870-5-104)
- operator training and control workflow validation

## How This System Can Be Used

Use it as a repeatable lab environment to:
- generate realistic operational data for ML and analytics
- evaluate detection pipelines using real protocol traffic
- rehearse SCADA workflows (polling, alarms, commands, audit)
- validate historian queries and dashboards under load

## Key Features (Utilized)

### Electrical System
- **DC Power Flow**: 15-bus Newton-Raphson solver with line losses
- **Frequency Dynamics**: Swing equation, governor droop, AGC
- **Transformer Thermal Model**: IEC 60076-7 with oil/hot-spot temperatures
- **Protection Relays**: ANSI 27/51/59/81/87T with real trip curves
- **Indian Load Profile**: Time-of-day, seasonal, festival patterns
- **Economic Despatch**: Merit order (solar → hydro → coal)

### SCADA Protocols
- **Modbus TCP**: Production-faithful RTU behavior (8-40ms response times)
- **IEC 60870-5-104**: Spontaneous transmission, time tagging

### Operational Workflow
- **SCADA Master**: Multi-node polling with command dispatch
- **Alarm Management**: Priority-based alarms with audit trail
- **SOE Recording**: Sequence-of-events logging for node actions

### Data Infrastructure
- **TimescaleDB Historian**: Time-series storage and aggregation
- **Security Logging**: Authentication, authorization, and audit events
- **Web Dashboard**: FastAPI + Streamlit monitoring and control

## Quick Start

### Prerequisites
```bash
# System requirements
- Docker & Docker Compose
- Python 3.10+
- 8GB RAM minimum (16GB recommended)
- 50GB disk space
```

### Installation
```bash
# Clone repository
git clone https://github.com/NirmalyaASinha/SCADA.git
cd SCADA_SIM

# Create virtual environment (optional for Docker)
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Note: IEC 104 is implemented in pure Python (no external lib needed)
# DNP3 is not implemented yet

# Start TimescaleDB (historian database)
docker-compose up -d timescaledb

# Initialize database schema
python database/init_db.py
```

### Running Tests
```bash
# Test electrical modules
python electrical/power_flow.py
python electrical/frequency_model.py
python electrical/thermal_model.py
python electrical/protection.py

# Expected output: Power flow convergence, frequency recovery plots, thermal trips
```

### Running the System
```bash
# Option 1: Docker Deployment (Recommended)
./deploy-docker.sh up

# Access Web Dashboard
http://localhost:8501
# Default login: admin/admin123

# Access API Documentation
http://localhost:8000/docs

# Option 2: Manual Start
# Terminal 1: Simulator
python3 simulator.py

# Terminal 2: API Server
python3 api_server.py

# Terminal 3: Web Dashboard
streamlit run dashboard.py

# Terminal 4: SCADA Master CLI (optional)
python3 scada_master_cli.py
```

### Workflow (Docker-First)

```bash
# 1) Start all services
./deploy-docker.sh up

# 2) Verify services
docker compose ps

# 3) Open dashboard
./deploy-docker.sh dashboard
# Login: admin / admin123

# 4) View logs (optional)
./deploy-docker.sh logs

# 5) Stop services when done
./deploy-docker.sh down
```

### Workflow (Local Development)

```bash
# Terminal 1: Simulator
python3 simulator.py

# Terminal 2: API Server
python3 api_server.py

# Terminal 3: Web Dashboard
streamlit run dashboard.py

# Terminal 4: SCADA Master CLI (optional)
python3 scada_master_cli.py
```

## Troubleshooting

### Docker Build Errors

**Error: "No matching distribution found for lib60870"**
- **Fixed:** IEC 104 protocol is implemented in pure Python (no external library needed)
- **Solution:** Use latest requirements.txt from repository

**Error: "Could not find a version that satisfies the requirement"**
- **Cause:** Python version mismatch (requires Python 3.10+)
- **Solution:** Update Dockerfile base image or use `python:3.10-slim`

**Error: "Port already in use"**
```bash
# Find and kill process using port
sudo lsof -i :8501  # or :8000, :502, etc.
sudo kill -9 <PID>

# Or stop existing containers
./deploy-docker.sh down
```

### Dashboard Connection Issues

**"Cannot connect to API server"**
```bash
# Check if API server is running
docker-compose ps

# Check API health
curl http://localhost:8000/health

# Restart services
./deploy-docker.sh restart
```

**"No nodes available"**
- Wait 10-30 seconds for simulator to initialize
- Check simulator logs: `docker-compose logs simulator`

### Quick Reference

```bash
# View logs
./deploy-docker.sh logs

# Check status
./deploy-docker.sh status

# Clean restart
./deploy-docker.sh down
./deploy-docker.sh up

# Access dashboard
./deploy-docker.sh dashboard
```

See [QUICK_START.md](QUICK_START.md) for detailed guide.

## Architecture

The system is structured as a grid simulator + protocol servers feeding a
secured SCADA master, historian, and web dashboard. Data flows from simulated
nodes through Modbus/IEC 104 to the SCADA master, then into TimescaleDB and the
API for visualization and control.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system design.

```
┌─────────────────────────────────────────────────────────────┐
│                      SCADA MASTER (OCC)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ Polling  │  │   AVR    │  │  Alarm   │  │     SOE     │  │
│  │  Engine  │  │  Control │  │ Manager  │  │  Recorder   │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────┘  │
└────────┬──────────────────────────────────────────┬─────────┘
         │ Modbus/IEC104/DNP3                       │
         ▼                                          ▼
┌─────────────────────────────────┐      ┌──────────────────┐
│    RTU Nodes (15)               │      │  TimescaleDB     │
│  ┌──────────────────────────┐   │      │   Historian      │
│  │  Electrical Simulation   │   │      │  ┌────────────┐  │
│  │  - Power Flow            │   │      │  │ Raw Scans  │  │
│  │  - Frequency Model       │   │      │  │ (2s rate)  │  │
│  │  - Thermal Model         │   │      │  ├────────────┤  │
│  │  - Protection Relays     │   │      │  │ 1-min agg  │  │
│  └──────────┬───────────────┘   │      │  ├────────────┤  │
│             ▼                   │      │  │ 1-hour agg │  │
│  ┌──────────────────────────┐   │      │  └────────────┘  │
│  │  Protocol Servers        │   │      └──────────────────┘
│  │  - Modbus TCP :502       │   │
│  │  - IEC 104 :2404         │   │      ┌──────────────────┐
│  │  - DNP3 :20000           │   │      │  Security Log    │
│  │  - Data Quality Flags    │   │      │  ┌────────────┐  │
│  └──────────────────────────┘   │      │  │ Protocol   │  │
└──┬──────────────────────────────┘      │  │Transaction │  │
   │                                     │  ├────────────┤  │
   ▼                                     │  │  Traffic   │  │
┌──────────────────────────┐             │  │  Features  │  │
│  Equipment Failures      │             │  └────────────┘  │
│  - Weibull Reliability   │             └──────────────────┘
│  - Degradation Modes     │
│  - Communication Loss    │                        │
└──────────────────────────┘                        ▼
                                         ┌──────────────────┐
                                         │  ML Training     │
                                         │  - Isolation     │
                                         │    Forest        │
                                         │  - LSTM          │
                                         │  - Transformer   │
                                         └──────────────────┘
```

## Project Philosophy

**Every design decision answers the question:**  
> "Is this how a real substation/grid actually behaves?"

If the answer is no — we fix it.

### Electrical Fidelity
- Kirchhoff's laws enforced at every node
- Frequency is global (all generators share same frequency)
- Thermal time constants match IEC 60076-7 (180 min for transformer oil)
- Protection operates per ANSI standards (not approximations)

### Protocol Fidelity
- Response times match real RTUs (8-15ms for Modbus FC01, 12-25ms for FC03)
- State machines mirror actual devices (IDLE/PROCESSING/RESPONDING)
- Data quality on every measurement (IEC 61968 flags)
- Exception codes match specification

### Operational Fidelity
- SCADA poll rates realistic (2s critical, 10s normal, 0.5s discrete)
- AGC interval matches practice (4 seconds)
- OLTC delays realistic (30-45s mechanical delay)
- Alarm priorities per IEC 62682

### Indian Grid Characteristics
- Load profile matches POSOCO data (evening peak at 20:00, afternoon dip)
- Frequency tolerance wider than European grids (49.7-50.3 Hz normal)
- Seasonal patterns (summer +20% AC load, monsoon baseline)
- Festival spikes (Diwali +25% at 20:00)

## Utilized Components

| Component | Utilized | Files | Notes |
|-----------|----------|-------|-------|
| Configuration | Yes | config.py | Grid topology and defaults |
| Power Flow | Yes | electrical/power_flow.py | 15-bus DC solver |
| Frequency Model | Yes | electrical/frequency_model.py | Swing equation |
| Thermal Model | Yes | electrical/thermal_model.py | IEC 60076-7 |
| Protection Relays | Yes | electrical/protection.py | ANSI 27/51/59/81/87T |
| Load Profile | Yes | electrical/load_profile.py | Indian grid profile |
| Economic Despatch | Yes | electrical/economic_despatch.py | Merit order |
| Modbus Register Map | Yes | protocols/modbus/register_map.py | RTU mapping |
| Data Quality | Yes | protocols/modbus/data_quality.py | IEC flags |
| Modbus Server | Yes | protocols/modbus/server.py | RTU server |
| IEC 104 Server | Yes | protocols/iec104/ | Protocol stack |
| DNP3 Server | No | protocols/dnp3/ | Reserved placeholder |
| Node Models | Yes | nodes/ | GEN/SUB/DIST |
| SCADA Master | Yes | scada_master.py | Multi-protocol polling |
| Historian | Yes | historians/ | Time-series storage |
| Security Logging | Yes | security/ | Auth + audit |
| API Server | Yes | api_server.py | FastAPI dashboard API |
| Web Dashboard | Yes | dashboard.py | Streamlit UI |
| Docker Infrastructure | Yes | Dockerfile, docker-compose.yml | Deployment |

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed status.

## Testing Individual Modules

Each electrical module has embedded tests:

```bash
# DC Power Flow - 15-bus system
python electrical/power_flow.py
# Output: Bus angles, line flows, losses (should show ~5% loss)

# Frequency Dynamics - Load step response
python electrical/frequency_model.py
# Output: Frequency recovery from 50 MW step (should recover in 30s)

# Transformer Thermal - Overload scenario
python electrical/thermal_model.py
# Output: Oil/hot-spot temps during 120% overload

# Protection Relay - Overcurrent trip
python electrical/protection.py
# Output: IEC inverse curve trip time calculation

# Load Profile - 24-hour Indian curve
python electrical/load_profile.py
# Output: Hourly load with evening peak at 20:00

# Economic Despatch - Merit order
python electrical/economic_despatch.py
# Output: Solar → Hydro → Coal loading sequence
```

## Configuration

Key parameters in `config.py`:

```python
# Grid topology
GENERATOR_CONFIG["GEN-001"]["rated_mw"] = 500.0  # Coal plant
GENERATOR_CONFIG["GEN-002"]["rated_mw"] = 300.0  # Hydro plant
GENERATOR_CONFIG["GEN-003"]["rated_mw"] = 200.0  # Solar plant

# Line impedances (per-unit on 100 MVA base)
LINE_IMPEDANCES[("GEN-001", "SUB-001")] = (0.02, 0.06, 0.03)  # R, X, B

# Protection settings
PROTECTION_CONFIG["ANSI_51"]["pickup_percent"] = 120.0  # 120% overcurrent pickup
PROTECTION_CONFIG["ANSI_59"]["pickup_percent"] = 110.0  # 110% overvoltage

# Modbus timing
MODBUS_CONFIG["poll_interval_critical_s"] = 2.0
MODBUS_CONFIG["response_times_ms"]["FC03"] = (12, 25)  # Min, max response time

# Simulation
SIMULATION_CONFIG["time_step_s"] = 1.0
SIMULATION_CONFIG["power_flow_interval_s"] = 5.0
```

## Data Output

### Historian Tags (IEC 61968 CIM Naming)
```
SUB001.TR1.BusVoltage.A          (kV)
SUB001.TR1.OilTemperature        (°C)
SUB001.TR1.HotSpotTemperature    (°C)
SUB001.TR1.TapPosition           (1-17)
GEN001.GEN1.ActivePower          (MW)
GEN001.GEN1.Frequency            (Hz)
DIST001.FEEDER1.Current.A        (A)
```

### Security Log Schema
```sql
CREATE TABLE protocol_transactions (
    timestamp TIMESTAMPTZ NOT NULL,
    node_id VARCHAR(20),
    source_ip INET,
    dest_ip INET,
    protocol VARCHAR(10),
    function_code INT,
    register_address INT,
    value INT,
    response_time_ms FLOAT,
    data_quality INT,
    is_write BOOLEAN,
    is_authorized BOOLEAN
);
```

## References

- **IEC 60076-7**: Power transformers - Loading guide for oil-immersed power transformers
- **IEC 60255**: Measuring relays and protection equipment
- **IEC 60870-5-104**: Telecontrol equipment and systems - Part 5-104: Transmission protocols
- **IEEE Std 493-2007**: Gold Book - Design of Reliable Industrial and Commercial Power Systems
- **IEEE C37.2**: Standard Electrical Power System Device Function Numbers
- **IEC 61968**: Application integration at electric utilities - System interfaces for distribution management
- **IEC 62682**: Management of alarms systems for the process industries
- **GRID-INDIA/POSOCO**: Indian grid operational data and grid code

## License

[Specify license]

## Contributing

This is a research/educational project. Contributions welcome following electrical engineering and ICS security best practices.

## Contact

[Specify contact information]

---

**Building authentic SCADA infrastructure for cybersecurity research — one relay trip at a time.**
