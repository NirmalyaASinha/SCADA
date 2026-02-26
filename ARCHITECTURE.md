# SCADA Simulator - Production-Faithful Architecture

## Project Status

### ✅ Completed Modules

#### 1. Configuration (`config.py`)
- Complete grid topology (15 nodes: 3 GEN, 7 SUB, 5 DIST)
- Line impedance matrix for DC power flow
- Generator parameters (coal, hydro, solar)
- Transformer thermal parameters (IEC 60076-7)
- OLTC configuration
- Protection relay settings (ANSI 27, 51, 59, 81, 87T)
- AGC parameters
- Indian load profile data
- Equipment reliability data (IEEE Std 493)
- Protocol configurations (Modbus, IEC104, DNP3)
- Network topology (Docker subnets)
- Data quality flags (IEC 61968)

#### 2. Electrical Foundation (`electrical/`)

**`power_flow.py`** - DC Power Flow Solver
- 15-bus DC susceptance matrix
- Newton-Raphson solver (simplified DC approximation)
- Line flow calculations
- Loss calculations (I²R method)
- Per-unit to physical unit conversion
- Power balance validation

**`frequency_model.py`** - System Frequency Dynamics
- Swing equation implementation
- Multi-generator system inertia
- Governor droop response (primary control)
- First-order governor lag (0.3-0.8s time constants)
- AGC PI controller (secondary control, 4s interval)
- Frequency status classification (NORMAL/LOW/HIGH/EMERGENCY)
- Rate of change of frequency (ROCOF) calculation

**`thermal_model.py`** - Transformer Thermal Model
- IEC 60076-7 top-oil temperature dynamics
- Hot-spot temperature calculation
- Loading-dependent thermal response (K^n exponent)
- Alarm/trip threshold monitoring
- Thermal margin calculations
- Emergency loading limits
- Degradation factor simulation (for ML training data)

**`protection.py`** - Protection Relay Logic
- ANSI 51: Inverse-time overcurrent (IEC Standard Inverse curve)
- ANSI 59: Overvoltage (definite time)
- ANSI 27: Undervoltage (definite time)
- ANSI 81: Underfrequency load shedding (3-stage)
- ANSI 87T: Transformer differential
- Trip logging for SOE recording
- Protection coordination logic

**`load_profile.py`** - Indian Load Profile
- Hourly load profile (24-hour curve)
- Seasonal multipliers (summer +20%, monsoon baseline, winter -5%)
- Weekend reduction (-15%)
- Festival load spikes (Diwali +25% at 20:00)
- Solar generation profile (Gaussian irradiance, cloud effects)
- Per-node load distribution

**`economic_despatch.py`** - Economic Despatch
- Merit order despatch (solar → hydro → coal)
- Quadratic cost curves (a*P² + b*P + c)
- Marginal cost calculation
- Generator constraint enforcement
- Under-generation handling
- System marginal price determination

#### 3. Protocol Layer - Modbus TCP (`protocols/modbus/`)

**`register_map.py`** - Modbus Register Map
- Register address allocation per node type
- Generation registers (MW, MVAR, governor setpoint, AVR setpoint)
- Substation registers (transformer load, oil temp, hot-spot, OLTC tap, line currents)
- Distribution registers (feeder load, energy meter)
- Discrete inputs (breaker status, protection trips, alarms)
- Coils (breaker commands, OLTC raise/lower, mode controls)
- Data encoding/decoding (voltage, current, power, frequency, temperature)
- Quality register mapping (+100 offset)

**`data_quality.py`** - Data Quality Manager
- IEC 61968 quality flags (GOOD, SUSPECT, BAD, OVERFLOW, UNDERRANGE)
- Quality degradation on communication timeout (3 misses → SUSPECT, 10 → BAD)
- Range checking (sensor limits)
- Quality summary reporting

### 🚧 In Progress / Next Steps

#### 4. Protocol Layer - Remaining Components

**Modbus TCP Server** (`protocols/modbus/server.py`) - NEEDED
- Modbus TCP state machine (IDLE → PROCESSING → RESPONDING)
- Function code handlers (FC01, FC03, FC05, FC06, FC16)
- Response timing simulation (8-40ms based on FC)
- Exception code generation (illegal function, address, value)
- Transaction ID management
- Multi-threaded request handling

**Modbus State Machine** (`protocols/modbus/state_machine.py`) - NEEDED
- Request validation
- Processing delays (realistic RTU behavior)
- Response construction
- Error handling

**IEC 60870-5-104 Server** (`protocols/iec104/`) - NEEDED
- ASDU type implementations (M_ME_NB_1, M_SP_NA_1, C_SC_NA_1, etc.)
- APCI (sequence numbers, START/STOP/TEST frames)
- Time tagging (CP56Time2a format)
- Spontaneous transmission (deadband-based)
- General Interrogation response

**DNP3 Server** (`protocols/dnp3/`) - NEEDED
- DNP3 object groups (Group 1, 10, 20, 30, 40, etc.)
- Unsolicited responses
- Event buffering
- Class 0/1/2/3 data organization

#### 5. Node Models (`nodes/`)

**Base Node** - NEEDED
- Integration of electrical models (power flow, frequency, thermal, protection)
- Integration of protocol servers (Modbus, IEC104, DNP3)
- Register update logic
- Discrete input/coil handling
- State management

**Generation Node** - NEEDED
- Generator output calculation
- Governor control
- AVR control
- Breaker simulation

**Substation Node** - NEEDED
- Transformer loading calculation
- OLTC operation
- Thermal monitoring
- Protection integration

**Distribution Node** - NEEDED
- Load tracking
- Energy metering
- Capacitor bank switching
- UFLS implementation

**Failure Model** - NEEDED
- Weibull failure time generation
- Degradation signatures (pre-failure anomalies)
- Communication failure simulation
- Relay failures

#### 6. OCC Layer (`occ/`)

**SCADA Master** - NEEDED
- Multi-node polling (2s critical, 10s normal, 0.5s discrete)
- Protocol client implementations
- Data archiving to historian
- Alarm processing

**AVR Loop** - NEEDED
- Voltage monitoring
- OLTC tap change commands
- Coordination logic (prevent hunting)

**Alarm Manager** - NEEDED
- IEC 62682 alarm priorities (1-4)
- Alarm state machine (UNACK/ACK/CLEARED)
- Alarm shelving
- Flood detection

**SOE Recorder** - NEEDED
- 1ms timestamp resolution
- Discrete state change logging
- Protection event recording
- COMTRADE export

**Select-Before-Operate** - NEEDED
- SBO command sequence
- 10-second timeout
- Command validation

#### 7. Historian (`historian/`)

**TimescaleDB Writer** - NEEDED
- Hypertable configuration
- 1-day chunk intervals
- Compression after 7 days
- Tag-based data model

**Aggregator** - NEEDED
- 1-minute rollup (min, max, avg, std)
- 1-hour rollup
- Continuous aggregates

**Historian API** - NEEDED
- REST API on port 8001
- Raw data query
- Aggregate query
- Multi-tag query for dashboards

#### 8. Security Instrumentation (`security/`)

**Transaction Logger** - NEEDED
- Per-transaction logging (protocol, FC, address, value, timestamp)
- Source/dest IP tracking
- Response time measurement
- Authorized vs unauthorized write detection

**Feature Extractor** - NEEDED
- Per-node, per-minute feature calculation
- Transaction count, R/W ratio, response time stats
- Source IP diversity
- Function code distribution
- Register address entropy
- Value change rate

#### 9. Database Layer (`database/`)

**Models** - NEEDED
- PostgreSQL table schemas:
    - raw_scan_data (TimescaleDB hypertable)
    - protocol_transactions (security log)
    - node_traffic_features (ML training data)
    - alarm_log (IEC 62682 alarm history)
    - soe_log (sequence of events)
    - equipment_status
    - node_configuration

**Connection Manager** - NEEDED
- SQLAlchemy connection pooling
- Retry logic
- Health checking

#### 10. Docker Infrastructure (`docker/`)

**Docker Compose** - NEEDED
```yaml
services:
  - scada_simulator (main engine)
  - scada_occ (SCADA master)
  - timescaledb
  - prometheus
  - grafana
  - ntp_server
  - network_router (iptables)
```

**Network Configuration** - NEEDED
- Virtual networks (10.1.1.0/24, 10.2.1.0/24, 10.3.1.0/24, 10.0.0.0/24)
- Inter-subnet routing
- Backup path simulation (latency injection, packet loss)
- Failover logic

#### 11. Main Simulation Engine (`main.py`)

**Simulator** - NEEDED
- Time loop (1s resolution, 5s power flow interval)
- Node orchestration
- Electrical state updates
- Protocol server management
- Monitoring and metrics
- Graceful shutdown

---

## Architecture Principles

### Electrical Fidelity
1. **Kirchhoff's Laws enforced** at every node
2. **Frequency is global** - all generators share same frequency
3. **Thermal time constants realistic** (180 min for transformer oil)
4. **Protection operates per IEC/IEEE standards** (not simplified approximations)

### Protocol Fidelity
1. **Response times match real RTUs** (8-40ms for Modbus)
2. **State machines mirror real devices** (IDLE/PROCESSING/RESPONDING)
3. **Data quality on every value** (IEC 61968 flags)
4. **Exception codes correct** (illegal function/address/value)

### Operational Fidelity
1. **SCADA poll rates realistic** (2s critical, 10s normal)
2. **AGC interval matches practice** (4 seconds)
3. **OLTC delays realistic** (30-45s mechanical delay)
4. **Alarm priorities follow IEC 62682**

### Indian Grid Characteristics
1. **Load profile matches POSOCO data** (morning peak, evening peak, afternoon dip)
2. **Frequency tolerance wider** (49.7-50.3 Hz normal band)
3. **Seasonal patterns** (summer +20% due to AC load)
4. **Festival spikes** (Diwali +25% at 20:00)

---

## Data Flow

```
Simulation Timeline (1-second time steps):

  t=0s: 
    - Initialize all nodes (electrical state at ambient/nominal)
    - Start protocol servers (Modbus TCP port 502, IEC104 port 2404, DNP3 port 20000)
    - Connect SCADA master to all nodes
    
  Every 1s:
    - Update load profile based on time-of-day
    - Update solar generation based on irradiance
    - Update frequency model (swing equation, governors, AGC)
    - Update each generator thermal state
    - Update each transformer thermal state
    - Update protection relays (check trip conditions)
    
  Every 5s:
    - Run DC power flow solver
    - Calculate line flows and losses
    - Update bus voltages and angles
    - If power flow doesn't converge → alarm
    
  SCADA Master Polling:
    - Every 0.5s: Poll discrete inputs (breaker status, trips)
    - Every 2s: Poll critical analogs (voltage, current, power, frequency)
    - Every 10s: Poll non-critical analogs (temperature, tap position)
    
  On Value Change (Spontaneous if IEC104):
    - Check deadband (0.5% voltage, 1.0% current, 0.5% power, 0.01 Hz frequency)
    - If exceeded → send spontaneous message to SCADA master
    
  On Protection Trip:
    - Generate SOE record (1ms timestamp)
    - Set discrete input (trip flag)
    - Generate SCADA alarm (priority based on function)
    - Open breaker (if trip confirmed)
    - Log to database
    
  Historian:
    - Every 2s: Write raw scan data to TimescaleDB
    - Every 1min: Calculate and write minute aggregates
    - Every 1hour: Calculate and write hour aggregates
    
  Security Logging:
    - Every Modbus transaction: Log to protocol_transactions table
    - Every minute: Calculate node traffic features, write to node_traffic_features
```

---

## File Structure

```
scada_simulator/
├── config.py                       ✅ COMPLETE
├── main.py                         ⏳ TODO
├── requirements.txt                ✅ COMPLETE
├── README.md                       ✅ THIS FILE
├── ARCHITECTURE.md                 ✅ THIS FILE
│
├── electrical/                     ✅ COMPLETE
│   ├── __init__.py
│   ├── power_flow.py
│   ├── frequency_model.py
│   ├── thermal_model.py
│   ├── protection.py
│   ├── load_profile.py
│   └── economic_despatch.py
│
├── protocols/
│   ├── modbus/
│   │   ├── __init__.py             ⏳ TODO
│   │   ├── register_map.py         ✅ COMPLETE
│   │   ├── data_quality.py         ✅ COMPLETE
│   │   ├── server.py               ⏳ TODO
│   │   └── state_machine.py        ⏳ TODO
│   ├── iec104/
│   │   ├── __init__.py             ⏳ TODO
│   │   ├── server.py               ⏳ TODO
│   │   ├── asdu.py                 ⏳ TODO
│   │   ├── apci.py                 ⏳ TODO
│   │   └── spontaneous.py          ⏳ TODO
│   └── dnp3/
│       ├── __init__.py             ⏳ TODO
│       ├── server.py               ⏳ TODO
│       ├── objects.py              ⏳ TODO
│       └── unsolicited.py          ⏳ TODO
│
├── nodes/
│   ├── __init__.py                 ⏳ TODO
│   ├── base_node.py                ⏳ TODO
│   ├── generation_node.py          ⏳ TODO
│   ├── substation_node.py          ⏳ TODO
│   ├── distribution_node.py        ⏳ TODO
│   ├── node_registry.py            ⏳ TODO
│   └── failure_model.py            ⏳ TODO
│
├── occ/
│   ├── __init__.py                 ⏳ TODO
│   ├── scada_master.py             ⏳ TODO
│   ├── avr_loop.py                 ⏳ TODO
│   ├── alarm_manager.py            ⏳ TODO
│   ├── soe_recorder.py             ⏳ TODO
│   └── select_before_operate.py    ⏳ TODO
│
├── historian/
│   ├── __init__.py                 ⏳ TODO
│   ├── timescale_writer.py         ⏳ TODO
│   ├── aggregator.py               ⏳ TODO
│   └── api.py                      ⏳ TODO
│
├── network/
│   ├── __init__.py                 ⏳ TODO
│   ├── topology.py                 ⏳ TODO
│   ├── redundancy.py               ⏳ TODO
│   └── time_sync.py                ⏳ TODO
│
├── security/
│   ├── __init__.py                 ⏳ TODO
│   ├── transaction_logger.py       ⏳ TODO
│   └── feature_extractor.py        ⏳ TODO
│
├── database/
│   ├── __init__.py                 ⏳ TODO
│   ├── connection.py               ⏳ TODO
│   ├── models.py                   ⏳ TODO
│   └── writer.py                   ⏳ TODO
│
├── utils/
│   ├── __init__.py                 ⏳ TODO
│   ├── logger.py                   ⏳ TODO
│   ├── validators.py               ⏳ TODO
│   └── comtrade.py                 ⏳ TODO
│
└── docker/
    ├── docker-compose.yml          ⏳ TODO
    ├── Dockerfile.simulator        ⏳ TODO
    ├── Dockerfile.occ              ⏳ TODO
    └── network-config/             ⏳ TODO
```

---

## Testing Strategy

Each module has embedded `if __name__ == "__main__"` test code:

- **power_flow.py**: Test 15-bus power flow with sample generation/load
- **frequency_model.py**: Test 50 MW load step, observe frequency recovery
- **thermal_model.py**: Test 120% transformer overload, observe thermal trip
- **protection.py**: Test overcurrent trip with IEC inverse curve
- **load_profile.py**: Generate 24-hour Indian load profile
- **economic_despatch.py**: Test merit order despatch at various demands

Run individual modules:
```bash
python electrical/power_flow.py
python electrical/frequency_model.py
python electrical/thermal_model.py
```

---

## Next Implementation Priority

1. **Modbus TCP Server** - Critical path for protocol communication
2. **Base Node** - Integration layer between electrical and protocols
3. **Main Simulator** - Orchestration engine
4. **SCADA Master** - Client-side polling
5. **Database Models** - Data persistence
6. **Docker Compose** - Deployment infrastructure

---

## Quality Metrics

The system will be validated against:

1. **Electrical accuracy**: Power balance error < 0.1 MW, frequency recovery within 30s
2. **Protocol conformance**: Modbus timing 8-40ms, IEC104 sequence numbers correct
3. **Operational realism**: Can a real SCADA engineer recognize behavior as authentic?
4. **Statistical validity**: Load/generation patterns pass Kolmogorov-Smirnov test vs real data
5. **Stability**: 72-hour continuous run without crashes or memory leaks

---

## References

- IEC 60076-7: Power transformers - Loading guide
- IEC 60255: Measuring relays and protection equipment
- IEC 60870-5-104: Telecontrol equipment - Network access for IEC 60870-5-101
- IEEE Std 493: Gold Book - Design of Reliable Industrial and Commercial Power Systems
- IEEE C37.2: Standard Electrical Power System Device Function Numbers
- IEC 61968: Application integration at electric utilities - System interfaces
- IEC 62682: Management of alarms systems for the process industries
- GRID-INDIA/POSOCO: Operational data and grid code

---

**Project Philosophy**: 
> Every line of code must answer: "Is this how a real substation actually behaves?"  
> If the answer is no — fix it.
