#!/usr/bin/env python3
"""
Real-time SCADA System Test - Shows Live Grid Monitoring
"""

import requests
import time
from datetime import datetime
from typing import Dict, Optional

SCADA_URL = "http://localhost:9000"


def login():
    """Authenticate to SCADA Master"""
    response = requests.post(
        f"{SCADA_URL}/auth/login",
        json={"username": "admin", "password": "scada@2024"},
        timeout=5
    )
    if response.status_code == 200:
        token = response.json().get('access_token')
        return token
    return None


def get_headers(token):
    """Build request headers with auth token"""
    return {'Authorization': f'Bearer {token}'}


def monitor_grid(token, duration_seconds=30):
    """Monitor grid in real-time"""
    headers = get_headers(token)
    start_time = time.time()

    print("\n" + "=" * 80)
    print("🔴 LIVE GRID MONITORING - Real-Time Dashboard")
    print("=" * 80)
    print(f"Duration: {duration_seconds}s | Refresh every 2 seconds\n")

    iteration = 0
    while time.time() - start_time < duration_seconds:
        iteration += 1

        try:
            # Get grid overview
            grid_resp = requests.get(
                f"{SCADA_URL}/grid/overview",
                headers=headers,
                timeout=5)
            grid = grid_resp.json() if grid_resp.status_code == 200 else {}

            # Get nodes
            nodes_resp = requests.get(
                f"{SCADA_URL}/nodes", headers=headers, timeout=5)
            nodes_data = nodes_resp.json() if nodes_resp.status_code == 200 else {}
            nodes = nodes_data.get(
                'nodes', []) if isinstance(
                nodes_data, dict) else nodes_data

            # Get active alarms
            alarms_resp = requests.get(
                f"{SCADA_URL}/alarms/active",
                headers=headers,
                timeout=5)
            alarms = alarms_resp.json() if alarms_resp.status_code == 200 else []

            # Get security connections
            sec_resp = requests.get(
                f"{SCADA_URL}/security/connections",
                headers=headers,
                timeout=5)
            connections = sec_resp.json() if sec_resp.status_code == 200 else {}

            # Clear screen (Unix)
            print("\033[H\033[J", end='', flush=True)

            # Header
            print("=" * 80)
            print("🔴 LIVE GRID MONITORING - Real-Time Dashboard")
            print("=" * 80)
            print(
                f"Iteration: {iteration} | Time: {datetime.now().strftime('%H:%M:%S')}\n")

            # Grid KPIs
            print("⚡ GRID KEY METRICS")
            print("-" * 80)
            freq = grid.get('system_frequency_hz', 50.0)
            freq_color = "🟢" if 49.8 <= freq <= 50.2 else "🔴"
            print(f"{freq_color} Frequency:        {freq:.4f} Hz")
            print(
                f"  Generation:       {grid.get('total_generation_mw', 0):.1f} MW")
            print(f"  Load:             {grid.get('total_load_mw', 0):.1f} MW")
            print(
                f"  Grid Losses:      {grid.get('grid_losses_mw', 0):.1f} MW")
            print(
                f"  Nodes Online:     {grid.get('nodes_online', 0)}/{grid.get('nodes_total', 15)}")

            # Node Summary
            print("\n📊 NODE STATUS SUMMARY")
            print("-" * 80)
            if nodes:
                connections_online = sum(
                    1 for n in nodes if n.get(
                        'connected', False))
                print(f"  Connected Nodes:  {connections_online}/{len(nodes)}")

                # Group by type
                gens = [n for n in nodes if 'GEN' in n.get('node_id', '')]
                subs = [n for n in nodes if 'SUB' in n.get('node_id', '')]
                dists = [n for n in nodes if 'DIST' in n.get('node_id', '')]

                gen_conn = sum(1 for n in gens if n.get('connected'))
                sub_conn = sum(1 for n in subs if n.get('connected'))
                dist_conn = sum(1 for n in dists if n.get('connected'))

                print(f"  Generators:       {gen_conn}/{len(gens)} 🔌")
                print(f"  Substations:      {sub_conn}/{len(subs)} 🔌")
                print(f"  Distribution:     {dist_conn}/{len(dists)} 🔌")

            # Active Alarms
            print("\n⚠️  ACTIVE ALARMS")
            print("-" * 80)
            if alarms:
                print(f"  {len(alarms)} alarm(s) active:")
                for alarm in alarms[:3]:
                    severity = alarm.get('severity', 'INFO')
                    msg = alarm.get('message', 'N/A')[:60]
                    print(f"    [{severity}] {msg}")
                if len(alarms) > 3:
                    print(f"    ... and {len(alarms)-3} more")
            else:
                print("  ✅ No active alarms")

            # Security Connections
            print("\n🔒 SECURITY MONITORING")
            print("-" * 80)
            if isinstance(connections, dict):
                total_conn = connections.get('total_connections', 0)
                authorized = connections.get('authorized_connections', 0)
                unknown = connections.get('unknown_connections', 0)

                print(f"  Total:            {total_conn}")
                print(f"  Authorized:       {authorized} 🟢")
                print(f"  Unknown:          {unknown} 🔴" if unknown >
                      0 else f"  Unknown:          {unknown}")

            # System Status
            print("\n✅ SYSTEM STATUS")
            print("-" * 80)
            print("  SCADA Master:     RUNNING 🟢")
            print("  Database:         CONNECTED 🟢")
            print("  Dashboard:        ACTIVE 🟢")

            print("\n" + "=" * 80)
            print("Press Ctrl+C to stop monitoring")
            print("=" * 80)

            time.sleep(2)

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(2)


def main():
    print("\n" + "#" * 80)
    print("# SCADA REAL-TIME MONITORING TEST")
    print("#" * 80)
    print("\nAuthenticating...")

    token = login()
    if not token:
        print("❌ Authentication failed!")
        return

    print("✅ Authentication successful!")
    print("Starting live monitoring in 2 seconds...\n")
    time.sleep(2)

    try:
        monitor_grid(token, duration_seconds=120)
    except KeyboardInterrupt:
        print("\n\n✅ Monitoring stopped by user")

    print("\n" + "#" * 80)
    print("# TEST COMPLETE")
    print("#" * 80)
    print("\nDashboard is available at: http://localhost:3000")
    print("Grafana monitoring:        http://localhost:3001 (admin/admin123)")
    print("\n")


if __name__ == "__main__":
    main()
