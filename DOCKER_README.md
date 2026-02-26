# SCADA Simulator - Docker Deployment Guide

## Overview

This directory contains Docker configuration for deploying the complete SCADA Simulator system with all components:

- **TimescaleDB**: Time-series database for historian data
- **Simulator**: 15-node IEEE grid simulation with Modbus TCP & IEC 104
- **SCADA Master**: Multi-protocol polling and control
- **Secure Master**: Authentication, authorization, and audit logging

## Quick Start

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 2GB RAM minimum
- 10GB disk space

### Deploy

```bash
# Build and start all services
./deploy-docker.sh up

# View logs
./deploy-docker.sh logs

# Check status
./deploy-docker.sh status
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Docker Network                      │
│            (172.20.0.0/16)                      │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌──────────────┐       ┌──────────────┐       │
│  │  TimescaleDB │◄──────┤  Simulator   │       │
│  │   Port 5432  │       │  15-node Grid│       │
│  └──────────────┘       │  Modbus: 502 │       │
│         ▲               │  IEC104: 2404│       │
│         │               └──────────────┘       │
│         │                      ▲                │
│         │                      │                │
│  ┌──────┴───────┐       ┌─────┴────────┐      │
│  │ SCADA Master │       │Secure Master │      │
│  │  (CLI Mode)  │       │  API: 8080   │      │
│  └──────────────┘       └──────────────┘      │
│                                                  │
└─────────────────────────────────────────────────┘
```

## Services

### TimescaleDB

**Container**: `scada_timescaledb`  
**Image**: `timescale/timescaledb:latest-pg15`  
**Ports**: 5432  
**Purpose**: Stores measurement history, alarms, audit logs

**Connection**:
```bash
psql -h localhost -U scada -d scada_historian
# Password: scada_secure_password
```

### Simulator

**Container**: `scada_simulator`  
**Image**: Built from Dockerfile  
**Ports**: 502 (Modbus), 2404 (IEC 104)  
**Purpose**: Simulates 15-node electrical grid with RTU nodes

**Nodes**:
- 3 Generators (GEN-001, GEN-002, GEN-003)
- 7 Substations (SUB-001 through SUB-007)
- 5 Distribution (DIST-001 through DIST-005)

### SCADA Master

**Container**: `scada_master`  
**Image**: Built from Dockerfile  
**Purpose**: Interactive CLI for monitoring and control

**Access**:
```bash
docker attach scada_master
```

### Secure Master

**Container**: `scada_secure_master`  
**Image**: Built from Dockerfile  
**Ports**: 8080 (API)  
**Purpose**: Authenticated SCADA operations with audit logging

**Default Users**:
- `admin` / `admin123` (Administrator)
- `operator` / `operator123` (Operator)
- `viewer` / `viewer123` (Read-only)

## Deployment Commands

### Build Images

```bash
./deploy-docker.sh build
```

### Start Services

```bash
# Start all services in background
./deploy-docker.sh up

# Start with logs visible
docker compose up
```

### Stop Services

```bash
./deploy-docker.sh down
```

### Restart Services

```bash
./deploy-docker.sh restart
```

### View Logs

```bash
# All services
./deploy-docker.sh logs

# Specific service
docker compose logs -f simulator
docker compose logs -f timescaledb
```

### Check Status

```bash
./deploy-docker.sh status
```

## Data Persistence

### Volumes

- `timescale_data`: PostgreSQL/TimescaleDB data
- `audit_logs`: Security audit logs
- `./logs`: Application logs (bind mount)

### Backup Database

```bash
docker exec scada_timescaledb pg_dump -U scada scada_historian > backup.sql
```

### Restore Database

```bash
cat backup.sql | docker exec -i scada_timescaledb psql -U scada scada_historian
```

## Testing

### Run All Tests

```bash
./deploy-docker.sh test
```

### Run Specific Test

```bash
docker compose run --rm simulator python3 test_security.py
docker compose run --rm simulator python3 test_historian.py
```

## Networking

### Access from Host

All services are accessible from host machine:

- Modbus TCP: `localhost:502`
- IEC 104: `localhost:2404`
- TimescaleDB: `localhost:5432`
- API: `localhost:8080`

### Inter-Container Communication

Containers use service names:

- Database: `timescaledb:5432`
- Simulator: `simulator:502`, `simulator:2404`

## Environment Variables

### Simulator

```yaml
SCADA_MODE: simulator
TIMESCALE_DB_URL: postgresql://scada:password@timescaledb:5432/scada_historian
```

### Secure Master

```yaml
SCADA_MODE: secure_master
AUDIT_LOG_FILE: /app/logs/audit.log
TIMESCALE_DB_URL: postgresql://scada:password@timescaledb:5432/scada_historian
```

## Security

### Change Default Passwords

Edit `docker-compose.yml`:

```yaml
environment:
  POSTGRES_PASSWORD: your_secure_password
  TIMESCALE_DB_URL: postgresql://scada:your_secure_password@...
```

### Network Isolation

Services run on isolated bridge network (172.20.0.0/16).  
Only expose necessary ports to host.

### Audit Logging

All authenticated operations logged to:
- Container: `/app/logs/audit/audit.log`
- Host: `./logs/audit/audit.log`

## Troubleshooting

### Database Not Starting

```bash
# Check logs
docker compose logs timescaledb

# Verify health
docker compose ps timescaledb
```

### Can't Connect to Modbus

```bash
# Check simulator is running
docker compose ps simulator

# Verify port binding
docker compose port simulator 502
```

### Out of Memory

Increase Docker memory limit in Docker Desktop settings.  
Minimum: 2GB, Recommended: 4GB

### Permission Denied on Logs

```bash
chmod -R 777 logs/
```

## Cleanup

### Remove All Containers and Networks

```bash
./deploy-docker.sh down
```

### Remove Including Volumes

```bash
./deploy-docker.sh clean
```

**WARNING**: This deletes all historical data!

## Development

### Rebuild After Code Changes

```bash
docker compose build simulator
docker compose up -d simulator
```

### Live Code Editing

Mount source as volume in `docker-compose.yml`:

```yaml
volumes:
  - .:/app
```

**Note**: Requires container restart for Python changes.

## Production Deployment

### Recommendations

1. **Change default passwords**
2. **Enable HTTPS** for API
3. **Use Docker secrets** for sensitive data
4. **Set up log rotation**
5. **Configure backup strategy**
6. **Monitor resource usage**
7. **Implement health checks**

### Docker Swarm / Kubernetes

For production orchestration, convert `docker-compose.yml`:

```bash
# Convert to Kubernetes
kompose convert

# Deploy to swarm
docker stack deploy -c docker-compose.yml scada
```

## Support

For issues or questions:
- Check logs: `./deploy-docker.sh logs`
- Review container status: `./deploy-docker.sh status`
- Run tests: `./deploy-docker.sh test`

## License

Industrial SCADA Simulator - Educational/Testing Purpose
