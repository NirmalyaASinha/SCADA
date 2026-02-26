-- TimescaleDB Initialization Script for SCADA Historian
-- This script runs automatically when the TimescaleDB container starts

\c scada_historian;

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Main measurements hypertable
CREATE TABLE IF NOT EXISTS measurements (
    time TIMESTAMP NOT NULL,
    node_id VARCHAR(50) NOT NULL,
    voltage_kv FLOAT8,
    current_a FLOAT8,
    power_mw FLOAT8,
    frequency_hz FLOAT8,
    breaker_closed BOOLEAN
);

-- Create hypertable
SELECT create_hypertable('measurements', 'time', if_not_exists => TRUE);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_measurements_node_time 
    ON measurements (node_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_measurements_node 
    ON measurements (node_id);

-- Alarms table
CREATE TABLE IF NOT EXISTS alarms (
    time TIMESTAMP NOT NULL,
    node_id VARCHAR(50) NOT NULL,
    alarm_type VARCHAR(50) NOT NULL,
    alarm_value FLOAT8,
    severity VARCHAR(10),
    description TEXT
);

-- Create hypertable
SELECT create_hypertable('alarms', 'time', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_alarms_node_time 
    ON alarms (node_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_alarms_type_time 
    ON alarms (alarm_type, time DESC);

-- Audit logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    time TIMESTAMP NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    username VARCHAR(50),
    source_ip VARCHAR(45),
    node_id VARCHAR(50),
    action VARCHAR(100),
    result VARCHAR(50),
    details JSONB
);

-- Create hypertable
SELECT create_hypertable('audit_logs', 'time', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_audit_logs_time 
    ON audit_logs (time DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user 
    ON audit_logs (username, time DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event 
    ON audit_logs (event_type, time DESC);

-- Create continuous aggregate for hourly statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS measurements_hourly WITH (
    timescaledb.continuous,
    timescaledb.materialized_only = false
) AS
SELECT
    time_bucket('1 hour', time) AS hour,
    node_id,
    AVG(voltage_kv) AS avg_voltage_kv,
    MIN(voltage_kv) AS min_voltage_kv,
    MAX(voltage_kv) AS max_voltage_kv,
    AVG(current_a) AS avg_current_a,
    MIN(current_a) AS min_current_a,
    MAX(current_a) AS max_current_a,
    AVG(power_mw) AS avg_power_mw,
    MIN(power_mw) AS min_power_mw,
    MAX(power_mw) AS max_power_mw,
    AVG(frequency_hz) AS avg_frequency_hz,
    MIN(frequency_hz) AS min_frequency_hz,
    MAX(frequency_hz) AS max_frequency_hz,
    COUNT(*) AS sample_count
FROM measurements
GROUP BY hour, node_id;

-- Create continuous aggregate for daily statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS measurements_daily WITH (
    timescaledb.continuous,
    timescaledb.materialized_only = false
) AS
SELECT
    time_bucket('1 day', time) AS day,
    node_id,
    AVG(voltage_kv) AS avg_voltage_kv,
    MIN(voltage_kv) AS min_voltage_kv,
    MAX(voltage_kv) AS max_voltage_kv,
    AVG(current_a) AS avg_current_a,
    MIN(current_a) AS min_current_a,
    MAX(current_a) AS max_current_a,
    AVG(power_mw) AS avg_power_mw,
    MIN(power_mw) AS min_power_mw,
    MAX(power_mw) AS max_power_mw,
    AVG(frequency_hz) AS avg_frequency_hz,
    MIN(frequency_hz) AS min_frequency_hz,
    MAX(frequency_hz) AS max_frequency_hz,
    COUNT(*) AS sample_count
FROM measurements
GROUP BY day, node_id;

-- Add data retention policies
-- Keep raw measurements for 7 days
SELECT add_retention_policy('measurements', INTERVAL '7 days', if_not_exists => TRUE);

-- Keep alarms for 30 days
SELECT add_retention_policy('alarms', INTERVAL '30 days', if_not_exists => TRUE);

-- Keep audit logs for 90 days
SELECT add_retention_policy('audit_logs', INTERVAL '90 days', if_not_exists => TRUE);

-- Add compression policy (compress data older than 1 day)
SELECT add_compression_policy('measurements', INTERVAL '1 day', if_not_exists => TRUE);
SELECT add_compression_policy('alarms', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_compression_policy('audit_logs', INTERVAL '30 days', if_not_exists => TRUE);

-- Grant permissions to scada user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO scada;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO scada;

-- Create sample views for common queries
CREATE OR REPLACE VIEW latest_measurements AS
SELECT DISTINCT ON (node_id)
    node_id,
    time,
    voltage_kv,
    current_a,
    power_mw,
    frequency_hz,
    breaker_closed
FROM measurements
ORDER BY node_id, time DESC;

CREATE OR REPLACE VIEW active_alarms AS
SELECT *
FROM alarms
WHERE time > NOW() - INTERVAL '1 hour'
ORDER BY time DESC;

-- Show table info
SELECT * FROM timescaledb_information.hypertables;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'TimescaleDB initialization complete!';
    RAISE NOTICE 'Hypertables created: measurements, alarms, audit_logs';
    RAISE NOTICE 'Continuous aggregates: measurements_hourly, measurements_daily';
    RAISE NOTICE 'Retention policies: 7 days (measurements), 30 days (alarms), 90 days (audit)';
END$$;
