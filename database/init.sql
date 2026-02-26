-- SCADA Critical Infrastructure Simulator - Database Schema
-- PostgreSQL 15 + TimescaleDB Extension
-- Initializes all tables for the distributed SCADA system

-- Create extension if not exists
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================================
-- TABLE: nodes
-- Stores metadata about all 15 node services
-- ============================================================================
CREATE TABLE IF NOT EXISTS nodes (
    node_id VARCHAR(20) PRIMARY KEY,
    node_type VARCHAR(15) NOT NULL CHECK (node_type IN ('GEN', 'SUB', 'DIST')),
    description TEXT,
    location VARCHAR(100),
    capacity_mw DECIMAL(10,2),
    nominal_voltage_kv DECIMAL(8,2),
    rest_port INTEGER NOT NULL,
    ws_port INTEGER NOT NULL,
    modbus_port INTEGER NOT NULL,
    iec104_port INTEGER NOT NULL,
    node_ip VARCHAR(15) NOT NULL,
    status VARCHAR(15) DEFAULT 'OFFLINE' CHECK (status IN ('ONLINE', 'OFFLINE', 'DISABLED')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on node_type for faster queries
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status);

-- ============================================================================
-- TABLE: telemetry
-- Time-series telemetry measurements from all nodes
-- Hypertable for efficient time-series storage
-- ============================================================================
CREATE TABLE IF NOT EXISTS telemetry (
    time TIMESTAMP NOT NULL,
    node_id VARCHAR(20) NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    voltage_kv DECIMAL(8,2),
    current_a DECIMAL(8,2),
    real_power_mw DECIMAL(10,2),
    reactive_power_mvar DECIMAL(10,2),
    power_factor DECIMAL(4,3),
    frequency_hz DECIMAL(8,3),
    temperature_c DECIMAL(6,2),
    breaker_state VARCHAR(10) CHECK (breaker_state IN ('OPEN', 'CLOSED', 'TRIPPED')),
    energy_delivered_mwh DECIMAL(12,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Convert to hypertable for time-series
SELECT create_hypertable('telemetry', 'time', if_not_exists => TRUE);

-- Create index on node_id and time for efficient queries
CREATE INDEX IF NOT EXISTS idx_telemetry_node_time ON telemetry (node_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_time ON telemetry (time DESC);

-- Drop old chunks older than 30 days automatically
SELECT add_retention_policy('telemetry', INTERVAL '30 days', if_not_exists => TRUE);

-- ============================================================================
-- TABLE: alarms
-- Historical alarm records from all nodes
-- ============================================================================
CREATE TABLE IF NOT EXISTS alarms (
    alarm_id SERIAL PRIMARY KEY,
    node_id VARCHAR(20) NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    alarm_code VARCHAR(20) NOT NULL,
    alarm_text VARCHAR(255) NOT NULL,
    severity VARCHAR(15) NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL')),
    status VARCHAR(15) DEFAULT 'RAISED' CHECK (status IN ('RAISED', 'ACKNOWLEDGED', 'CLEARED')),
    raised_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP,
    acknowledged_by VARCHAR(50),
    cleared_at TIMESTAMP,
    details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alarms_node_time ON alarms(node_id, raised_at DESC);
CREATE INDEX IF NOT EXISTS idx_alarms_severity ON alarms(severity);
CREATE INDEX IF NOT EXISTS idx_alarms_status ON alarms(status);
CREATE INDEX IF NOT EXISTS idx_alarms_raised_at ON alarms(raised_at DESC);

-- ============================================================================
-- TABLE: events
-- Sequence of Events (SOE) log for operator actions and state changes
-- ============================================================================
CREATE TABLE IF NOT EXISTS events (
    event_id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    node_id VARCHAR(20) REFERENCES nodes(node_id) ON DELETE SET NULL,
    operator_id VARCHAR(50),
    action VARCHAR(100),
    parameters JSONB,
    status VARCHAR(15),
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_node ON events(node_id);
CREATE INDEX IF NOT EXISTS idx_events_operator ON events(operator_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);

-- ============================================================================
-- TABLE: connections
-- Real-time and historical connection log
-- Tracks all client connections (Modbus, IEC104, REST, WebSocket)
-- ============================================================================
CREATE TABLE IF NOT EXISTS connections (
    connection_id SERIAL PRIMARY KEY,
    node_id VARCHAR(20) NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    client_ip VARCHAR(15) NOT NULL,
    client_port INTEGER,
    protocol VARCHAR(20) NOT NULL CHECK (protocol IN ('REST', 'WEBSOCKET', 'MODBUS', 'IEC104')),
    is_authorized BOOLEAN DEFAULT FALSE,
    connected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    disconnected_at TIMESTAMP,
    requests_count INTEGER DEFAULT 0,
    bytes_sent BIGINT DEFAULT 0,
    bytes_received BIGINT DEFAULT 0,
    alerts_raised INTEGER DEFAULT 0,
    details JSONB
);

CREATE INDEX IF NOT EXISTS idx_connections_node_time ON connections(node_id, connected_at DESC);
CREATE INDEX IF NOT EXISTS idx_connections_ip ON connections(client_ip);
CREATE INDEX IF NOT EXISTS idx_connections_auth ON connections(is_authorized);
CREATE INDEX IF NOT EXISTS idx_connections_protocol ON connections(protocol);

-- ============================================================================
-- TABLE: security_alerts
-- Security monitoring and anomaly detection
-- Tracks unknown connections, policy violations, anomalies
-- ============================================================================
CREATE TABLE IF NOT EXISTS security_alerts (
    alert_id SERIAL PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(15) DEFAULT 'WARNING' CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL')),
    node_id VARCHAR(20) REFERENCES nodes(node_id) ON DELETE CASCADE,
    client_ip VARCHAR(15),
    protocol VARCHAR(20),
    description VARCHAR(255),
    action_taken VARCHAR(100),
    acknowledged_by VARCHAR(50),
    acknowledged_at TIMESTAMP,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_security_alerts_node ON security_alerts(node_id);
CREATE INDEX IF NOT EXISTS idx_security_alerts_time ON security_alerts(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_security_alerts_ip ON security_alerts(client_ip);
CREATE INDEX IF NOT EXISTS idx_security_alerts_severity ON security_alerts(severity);

-- ============================================================================
-- TABLE: audit_log
-- Complete audit trail of all operator actions and system events
-- ============================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    log_id SERIAL PRIMARY KEY,
    operator_id VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(50),
    old_value TEXT,
    new_value TEXT,
    ip_address VARCHAR(15),
    status VARCHAR(15) DEFAULT 'SUCCESS' CHECK (status IN ('SUCCESS', 'FAILURE', 'DENIED')),
    result_message VARCHAR(255),
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_audit_log_operator ON audit_log(operator_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_resource ON audit_log(resource_type, resource_id);

-- ============================================================================
-- TABLE: users
-- User accounts with role-based access control
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    email VARCHAR(100),
    role VARCHAR(20) NOT NULL CHECK (role IN ('viewer', 'operator', 'engineer', 'admin')),
    status VARCHAR(15) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'DISABLED', 'LOCKED')),
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- ============================================================================
-- TABLE: grid_metrics
-- Pre-calculated aggregate grid metrics for dashboard
-- ============================================================================
CREATE TABLE IF NOT EXISTS grid_metrics (
    time TIMESTAMP NOT NULL,
    total_generation_mw DECIMAL(10,2),
    total_load_mw DECIMAL(10,2),
    system_frequency_hz DECIMAL(8,3),
    grid_losses_mw DECIMAL(10,2),
    nodes_online INTEGER,
    nodes_offline INTEGER,
    active_alarms INTEGER,
    critical_alarms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Convert to hypertable
SELECT create_hypertable('grid_metrics', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_grid_metrics_time ON grid_metrics(time DESC);

-- Drop old metrics older than 7 days
SELECT add_retention_policy('grid_metrics', INTERVAL '7 days', if_not_exists => TRUE);

-- ============================================================================
-- INITIAL DATA INSERTS
-- ============================================================================

-- Insert all 15 nodes
INSERT INTO nodes (node_id, node_type, description, location, capacity_mw, nominal_voltage_kv, rest_port, ws_port, modbus_port, iec104_port, node_ip)
VALUES
    -- Generation Nodes
    ('GEN-001', 'GEN', 'Thermal Generator 1', 'North Power Plant', 500.00, 230.0, 8101, 8102, 5020, 2401, '10.1.1.1'),
    ('GEN-002', 'GEN', 'Thermal Generator 2', 'North Power Plant', 500.00, 230.0, 8103, 8104, 5021, 2402, '10.1.1.2'),
    ('GEN-003', 'GEN', 'Wind Farm', 'Coastal Region', 300.00, 138.0, 8105, 8106, 5022, 2403, '10.1.1.3'),
    -- Transmission Substations
    ('SUB-001', 'SUB', 'Central Substation A', 'Downtown', 1000.00, 230.0, 8111, 8112, 5030, 2411, '10.2.1.1'),
    ('SUB-002', 'SUB', 'Central Substation B', 'Downtown', 1000.00, 230.0, 8113, 8114, 5031, 2412, '10.2.1.2'),
    ('SUB-003', 'SUB', 'Eastern Substation', 'East District', 750.00, 138.0, 8115, 8116, 5032, 2413, '10.2.1.3'),
    ('SUB-004', 'SUB', 'Western Substation', 'West District', 750.00, 138.0, 8117, 8118, 5033, 2414, '10.2.1.4'),
    ('SUB-005', 'SUB', 'Northern Substation', 'North Region', 600.00, 138.0, 8119, 8120, 5034, 2415, '10.2.1.5'),
    ('SUB-006', 'SUB', 'Southern Substation', 'South Region', 600.00, 138.0, 8121, 8122, 5035, 2416, '10.2.1.6'),
    ('SUB-007', 'SUB', 'Industrial Hub', 'Industrial Zone', 500.00, 69.0, 8123, 8124, 5036, 2417, '10.2.1.7'),
    -- Distribution Feeders
    ('DIST-001', 'DIST', 'Downtown Distribution', 'Downtown', 200.00, 13.8, 8131, 8132, 5040, 2421, '10.3.1.1'),
    ('DIST-002', 'DIST', 'Residential North', 'North District', 180.00, 13.8, 8133, 8134, 5041, 2422, '10.3.1.2'),
    ('DIST-003', 'DIST', 'Residential South', 'South District', 180.00, 13.8, 8135, 8136, 5042, 2423, '10.3.1.3'),
    ('DIST-004', 'DIST', 'Commercial East', 'East District', 220.00, 13.8, 8137, 8138, 5043, 2424, '10.3.1.4'),
    ('DIST-005', 'DIST', 'Industrial Feed', 'Industrial Zone', 150.00, 13.8, 8139, 8140, 5044, 2425, '10.3.1.5')
ON CONFLICT (node_id) DO NOTHING;

-- Insert default users
INSERT INTO users (username, password_hash, full_name, email, role)
VALUES
    ('admin', '$2b$12$uVnLlgV1LE4TPWQ2qkFRLOFQBb7W7xXyDfVNPV1qL4HNuUXVL5Yg.', 'System Administrator', 'admin@scada.local', 'admin'),
    ('operator', '$2b$12$kN2xF7V9pR4mZ8qL.JYv.eH6kM2xC9dF5V2qN7xL9qR3pZ8tW.', 'SCADA Operator', 'operator@scada.local', 'operator'),
    ('engineer', '$2b$12$pQ5xM3dN8rL2vK4jH9sG.eK7fL6mN9pQ3sR8uV5wX2yZ9aB.', 'Control Engineer', 'engineer@scada.local', 'engineer'),
    ('viewer', '$2b$12$xT7yU4vZ2cW8aS1pL3eQ.nR5xK8jM4dO7fP9sJ2vL4xN6tQ.', 'Monitoring Viewer', 'viewer@scada.local', 'viewer')
ON CONFLICT (username) DO NOTHING;

-- Create views for common queries
CREATE OR REPLACE VIEW v_active_alarms AS
SELECT a.alarm_id, a.node_id, a.alarm_code, a.alarm_text, a.severity, 
       a.raised_at, a.acknowledged_by, n.description as node_description
FROM alarms a
JOIN nodes n ON a.node_id = n.node_id
WHERE a.status = 'RAISED'
ORDER BY a.raised_at DESC;

CREATE OR REPLACE VIEW v_online_nodes AS
SELECT node_id, description, node_type, status, capacity_mw
FROM nodes
WHERE status = 'ONLINE'
ORDER BY node_type, node_id;

CREATE OR REPLACE VIEW v_unknown_connections AS
SELECT c.connection_id, c.node_id, c.client_ip, c.protocol, 
       c.connected_at, n.description as node_description
FROM connections c
JOIN nodes n ON c.node_id = n.node_id
WHERE c.is_authorized = FALSE
ORDER BY c.connected_at DESC;

-- ============================================================================
-- TABLE: auth_log
-- Logs all authentication attempts (success and failure)
-- ============================================================================
CREATE TABLE IF NOT EXISTS auth_log (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    ip_address INET,
    success BOOLEAN NOT NULL,
    failure_reason VARCHAR(100),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    user_agent TEXT,
    session_id UUID
);

CREATE INDEX IF NOT EXISTS idx_auth_log_username ON auth_log(username);
CREATE INDEX IF NOT EXISTS idx_auth_log_timestamp ON auth_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_auth_log_success ON auth_log(success);

-- ============================================================================
-- TABLE: operator_actions
-- Logs all operator actions (SBO, isolation, etc.)
-- ============================================================================
CREATE TABLE IF NOT EXISTS operator_actions (
    id SERIAL PRIMARY KEY,
    session_id UUID,
    operator_id VARCHAR(50) NOT NULL,
    operator_ip INET,
    node_id VARCHAR(20),
    action_type VARCHAR(50) NOT NULL,
    action_detail JSONB,
    selected_at TIMESTAMPTZ,
    operated_at TIMESTAMPTZ,
    result VARCHAR(20),
    response_ms INTEGER,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_operator_actions_operator ON operator_actions(operator_id);
CREATE INDEX IF NOT EXISTS idx_operator_actions_timestamp ON operator_actions(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_operator_actions_node ON operator_actions(node_id);

-- ============================================================================
-- TABLE: security_events
-- Logs security-related events (unknown connections, alerts, etc.)
-- ============================================================================
CREATE TABLE IF NOT EXISTS security_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    node_id VARCHAR(20),
    source_ip INET,
    protocol VARCHAR(20),
    port INTEGER,
    description TEXT,
    raw_data JSONB,
    acknowledged BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_security_events_type ON security_events(event_type);
CREATE INDEX IF NOT EXISTS idx_security_events_severity ON security_events(severity);
CREATE INDEX IF NOT EXISTS idx_security_events_timestamp ON security_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_security_events_node ON security_events(node_id);

-- ============================================================================
-- TABLE: audit_log
-- Full audit log of all system actions
-- ============================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    session_id UUID,
    username VARCHAR(50),
    ip_address INET,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(100),
    detail JSONB,
    result VARCHAR(20) CHECK (result IN ('success', 'failure')),
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_username ON audit_log(username);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);

-- Grant permissions
GRANT CONNECT ON DATABASE scadadb TO scada;
GRANT USAGE ON SCHEMA public TO scada;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO scada;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO scada;

-- Success message
\echo 'SCADA Database initialization complete!'
