#!/usr/bin/env python3
"""
SCADA System Monitor - Real-time status and grid monitoring
Shows power grid status, node health, and real-time metrics
"""

import requests
import json
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

# Configuration
SCADA_MASTER_URL = "http://localhost:9000"
CREDENTIALS = {
    "username": "admin",
    "password": "scada@2024"
}

class SCIDAMonitor:
    def __init__(self):
        self.token = None
        self.session = requests.Session()
        
    def login(self) -> bool:
        """Authenticate with SCADA Master"""
        try:
            response = self.session.post(
                f"{SCADA_MASTER_URL}/auth/login",
                json=CREDENTIALS,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get('access_token')
                self.session.headers.update({
                    'Authorization': f'Bearer {self.token}'
                })
                return True
            return False
        except Exception as e:
            print(f"❌ Login failed: {e}")
            return False

    def get_grid_status(self) -> Optional[Dict]:
        """Get current grid overview"""
        try:
            response = self.session.get(
                f"{SCADA_MASTER_URL}/grid/overview",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"❌ Grid status error: {e}")
            return None

    def get_nodes(self) -> Optional[List[Dict]]:
        """Get all nodes status"""
        try:
            response = self.session.get(
                f"{SCADA_MASTER_URL}/nodes",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                # Extract nodes list from response
                return data.get('nodes', []) if isinstance(data, dict) else data
            return None
        except Exception as e:
            print(f"❌ Nodes error: {e}")
            return None

    def print_grid_status(self, grid_data: Dict):
        """Display grid status in formatted table"""
        print("\n" + "="*80)
        print("⚡ POWER GRID STATUS".center(80))
        print("="*80)
        
        if not grid_data:
            print("❌ No grid data available")
            return
        
        # Current metrics
        print("\n📊 CURRENT METRICS")
        print("-" * 80)
        
        freq = grid_data.get('system_frequency_hz', 50.0)
        freq_status = "✅ NORMAL" if 49.8 <= freq <= 50.2 else "⚠️ WARNING"
        print(f"  Frequency           : {freq:.3f} Hz {freq_status}")
        
        gen = grid_data.get('total_generation_mw', 0)
        print(f"  Total Generation    : {gen:.1f} MW")
        
        load = grid_data.get('total_load_mw', 0)
        print(f"  System Load         : {load:.1f} MW")
        
        loss = grid_data.get('grid_losses_mw', 0)
        print(f"  Transmission Loss   : {loss:.1f} MW")
        
        balance = gen - load - loss
        print(f"  Power Balance       : {balance:+.1f} MW")
        
        # Node count
        node_online = grid_data.get('nodes_online', 0)
        node_offline = grid_data.get('nodes_offline', 0)
        node_total = node_online + node_offline
        print(f"  Nodes Connected     : {node_online}/{node_total} ✅")
        
        # Timestamp
        timestamp = grid_data.get('last_updated', '')
        if timestamp:
            print(f"  Last Update         : {timestamp}")

    def print_nodes_table(self, nodes: List[Dict]):
        """Display nodes in a formatted table"""
        print("\n" + "="*80)
        print("🔗 NODE STATUS".center(80))
        print("="*80)
        
        if not nodes:
            print("❌ No nodes available")
            return
            
        # Header
        print(f"\n{'ID':<8} {'Type':<12} {'State':<12} {'Port':<8}")
        print("-" * 80)
        
        # Nodes
        healthy_count = 0
        for node in nodes:
            node_id = node.get('node_id', '?')
            node_type = node.get('type', 'unknown')[:11]
            state = node.get('state', 'UNKNOWN')
            rest_port = node.get('rest_port', '?')
            
            # Status indicator
            if state == 'CONNECTED':
                state_icon = "✅ CONNECTED"
                healthy_count += 1
            elif state == 'CONNECTING':
                state_icon = "🔄 CONNECTING"
            elif state == 'RECONNECTING':
                state_icon = "🔄 RECONNECTING"
            elif state == 'DEGRADED':
                state_icon = "⚠️ DEGRADED"
            elif state == 'OFFLINE':
                state_icon = "❌ OFFLINE"
            else:
                state_icon = f"❓ {state}"
            
            print(f"{node_id:<8} {node_type:<12} {state_icon:<12} {rest_port:<8}")
        
        print("-" * 80)
        print(f"Summary: {healthy_count}/{len(nodes)} nodes CONNECTED ✅")

    def print_health_check(self) -> bool:
        """Check service health"""
        print("\n" + "="*80)
        print("🏥 SERVICE HEALTH".center(80))
        print("="*80 + "\n")
        
        services = {
            "SCADA Master": f"{SCADA_MASTER_URL}/health",
            "TimescaleDB": "tcp://localhost:5432",
            "Redis": "tcp://localhost:6379",
            "Prometheus": "http://localhost:9090/-/healthy",
        }
        
        all_healthy = True
        
        # Check SCADA Master
        try:
            response = self.session.get(f"{SCADA_MASTER_URL}/health", timeout=2)
            status = "✅ HEALTHY" if response.status_code == 200 else "❌ FAILED"
            print(f"  SCADA Master       : {status}")
        except:
            print(f"  SCADA Master       : ❌ UNREACHABLE")
            all_healthy = False
        
        # Check Docker services via docker command
        try:
            import subprocess
            result = subprocess.run(
                ["docker", "compose", "-f", "docker-compose-production.yml", "ps", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd="/home/nirmalya/Desktop/SCADA_SIM"
            )
            if result.returncode == 0:
                services_list = json.loads(result.stdout)
                critical = ["scada_timescaledb", "scada_redis", "scada_prometheus", "scada_master_prod"]
                for svc in critical:
                    for s in services_list:
                        if s.get('Name') == svc:
                            state = s.get('State', 'unknown')
                            status = "✅ HEALTHY" if state == "running" else f"⚠️ {state.upper()}"
                            svc_name = svc.replace("scada_", "").replace("_prod", "").upper()
                            print(f"  {svc_name:<18} : {status}")
        except Exception as e:
            print(f"  Docker Services    : ⚠️ Could not check: {e}")
        
        return all_healthy

    def run_continuous_monitor(self, interval: int = 5):
        """Run continuous monitoring"""
        print("\n🔄 Starting continuous monitoring (Press Ctrl+C to stop)...\n")
        
        try:
            while True:
                # Clear screen (works on Linux/Mac)
                print("\033[H\033[J", end='')
                
                print(f"⏱️  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                grid = self.get_grid_status()
                if grid:
                    self.print_grid_status(grid)
                
                nodes = self.get_nodes()
                if nodes:
                    self.print_nodes_table(nodes)
                
                self.print_health_check()
                
                print(f"\n⏳ Refreshing in {interval}s... (Ctrl+C to exit)")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n✅ Monitor stopped")
            sys.exit(0)

    def run_once(self):
        """Run single status check"""
        print(f"📍 Status Check - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        grid = self.get_grid_status()
        if grid:
            self.print_grid_status(grid)
        
        nodes = self.get_nodes()
        if nodes:
            self.print_nodes_table(nodes)
        
        self.print_health_check()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="SCADA System Monitor")
    parser.add_argument("-c", "--continuous", action="store_true", help="Continuous monitoring mode")
    parser.add_argument("-i", "--interval", type=int, default=5, help="Refresh interval in seconds (default: 5)")
    parser.add_argument("--url", default="http://localhost:9000", help="SCADA Master URL")
    
    args = parser.parse_args()
    
    monitor = SCIDAMonitor()
    
    # Update URL if provided
    global SCADA_MASTER_URL
    SCADA_MASTER_URL = args.url
    monitor.session.timeout = 5
    
    print("🔐 Authenticating with SCADA Master...")
    if not monitor.login():
        print("❌ Authentication failed!")
        print(f"✓ Ensure SCADA Master is running at {SCADA_MASTER_URL}")
        sys.exit(1)
    
    print("✅ Authentication successful!\n")
    
    if args.continuous:
        monitor.run_continuous_monitor(args.interval)
    else:
        monitor.run_once()

if __name__ == "__main__":
    main()
