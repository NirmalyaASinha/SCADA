"""
TimescaleDB Schema Definitions

Defines the database schema for time-series measurement storage
and creates hypertables for efficient data management.
"""

# SQL statements for schema creation
CREATE_EXTENSION = """
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
"""

# Main measurements hypertable
CREATE_MEASUREMENTS_TABLE = """
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
"""

# Alarms table
CREATE_ALARMS_TABLE = """
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
"""

# Continuous aggregate for hourly statistics
CREATE_HOURLY_STATS = """
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
"""

# Daily statistics view
CREATE_DAILY_STATS = """
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
"""

# Data retention policy: Keep raw data for 7 days, compressed
DROP_RETENTION_POLICY = """
SELECT remove_retention_policy('measurements', if_exists => TRUE);
SELECT remove_retention_policy('alarms', if_exists => TRUE);
"""

CREATE_RETENTION_POLICIES = """
-- Keep raw measurements for 7 days, compress after 1 day
SELECT add_retention_policy('measurements', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_compression_policy(
    'measurements',
    INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Keep alarms for 30 days
SELECT add_retention_policy('alarms', INTERVAL '30 days', if_not_exists => TRUE);
"""

# List of all schema creation statements
SCHEMA_SCRIPTS = [
    CREATE_EXTENSION,
    CREATE_MEASUREMENTS_TABLE,
    CREATE_ALARMS_TABLE,
    CREATE_HOURLY_STATS,
    CREATE_DAILY_STATS,
    CREATE_RETENTION_POLICIES,
]
