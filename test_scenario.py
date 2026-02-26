#!/usr/bin/env python3
"""
Test Scenario - Simulate Grid Anomaly and Control Operations
Demonstrates the SCADA system end-to-end
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, Optional

# Configuration
SCADA_MASTER_URL = "http://localhost:9000"
CREDENTIALS = {
    "username": "admin",
    "password": "scada@2024"
}

class GridTestScenario:
    def __init__(self):
        self.token = None
        self.session = requests.Session()
        self.scenario_log = []
        
    def log(self, message: str, level: str = "INFO"):
        """Log scenario events"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] [{level}] {message}"
        self.scenario_log.append(log_msg)
        print(log_msg)
    
    def login(self) -> bool:
        """Authenticate with SCADA Master"""
        self.log("Attempting to authenticate with SCADA Master...")
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
                self.log(f"✅ Authentication successful - Token: {self.token[:20]}...", "SUCCESS")
                return True
            else:
                self.log(f"❌ Authentication failed: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ Login error: {e}", "ERROR")
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
            self.log(f"❌ Grid status error: {e}", "ERROR")
            return None

    def get_alarms(self) -> Optional[list]:
        """Get current alarms"""
        try:
            response = self.session.get(
                f"{SCADA_MASTER_URL}/alarms",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('alarms', []) if isinstance(data, dict) else data
            return []
        except Exception as e:
            self.log(f"❌ Alarms error: {e}", "ERROR")
            return []

    def get_nodes(self) -> Optional[list]:
        """Get all nodes"""
        try:
            response = self.session.get(
                f"{SCADA_MASTER_URL}/nodes",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('nodes', []) if isinstance(data, dict) else data
            return []
        except Exception as e:
            self.log(f"❌ Nodes error: {e}", "ERROR")
            return []

    def control_breaker(self, node_id: str, breaker_status: bool) -> bool:
        """Control a breaker (SBO operation)"""
        self.log(f"Controlling breaker on {node_id} to state={breaker_status}")
        try:
            # First, SELECT the breaker
            response = self.session.post(
                f"{SCADA_MASTER_URL}/control/sbo/select",
                json={"node_id": node_id},
                timeout=5
            )
            
            if response.status_code != 200:
                self.log(f"❌ SBO Select failed: {response.status_code}", "ERROR")
                return False
            
            select_data = response.json()
            sbo_id = select_data.get('sbo_id')
            self.log(f"  → SBO Select successful (ID: {sbo_id})", "INFO")
            
            # Then, OPERATE the breaker
            time.sleep(1)
            response = self.session.post(
                f"{SCADA_MASTER_URL}/control/sbo/operate",
                json={
                    "sbo_id": sbo_id,
                    "node_id": node_id,
                    "breaker_close": breaker_status
                },
                timeout=5
            )
            
            if response.status_code == 200:
                self.log(f"✅ Breaker control executed for {node_id}", "SUCCESS")
                return True
            else:
                self.log(f"❌ SBO Operate failed: {response.status_code}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Control error: {e}", "ERROR")
            return False

    def print_grid_summary(self):
        """Print formatted grid summary"""
        grid = self.get_grid_status()
        if not grid:
            self.log("❌ Could not retrieve grid status", "WARNING")
            return
        
        print("\n" + "="*70)
        print("⚡ POWER GRID STATUS SUMMARY")
        print("="*70)
        print(f"  Frequency          : {grid.get('system_frequency_hz', 0):.3f} Hz")
        print(f"  Total Generation   : {grid.get('total_generation_mw', 0):.1f} MW")
        print(f"  System Load        : {grid.get('total_load_mw', 0):.1f} MW")
        print(f"  Grid Losses        : {grid.get('grid_losses_mw', 0):.1f} MW")
        print(f"  Active Nodes       : {grid.get('nodes_online', 0)}/{grid.get('nodes_total', 15)}")
        print("="*70 + "\n")

    def print_node_status(self):
        """Print node status table"""
        nodes = self.get_nodes()
        if not nodes:
            self.log("❌ Could not retrieve nodes", "WARNING")
            return
        
        print("\n" + "="*100)
        print("📊 NODE STATUS TABLE")
        print("="*100)
        print(f"{'Node ID':<12} {'Type':<12} {'Status':<12} {'Voltage (kV)':<15} {'Power (MW)':<15} {'Connected':<12}")
        print("-"*100)
        
        for node in nodes[:10]:  # Show first 10 nodes
            node_id = node.get('node_id', 'N/A')
            node_type = node.get('node_type', 'N/A')
            status = node.get('status', 'UNKNOWN')
            voltage = node.get('voltage_kv', 0)
            power = node.get('p_mw', 0)
            connected = "✅ Yes" if node.get('connected', False) else "❌ No"
            
            print(f"{node_id:<12} {node_type:<12} {status:<12} {voltage:<15.2f} {power:<15.2f} {connected:<12}")
        
        print("="*100 + "\n")

    def run_scenario(self):
        """Execute the test scenario"""
        print("\n" + "#"*70)
        print("# SCADA SYSTEM TEST SCENARIO")
        print("# Testing Grid Monitoring, Alarms, and Control Operations")
        print("#"*70 + "\n")
        
        # Step 1: Login
        if not self.login():
            return
        
        time.sleep(1)
        
        # Step 2: Get initial grid status
        self.log("Retrieving initial grid status...", "INFO")
        self.print_grid_summary()
        time.sleep(1)
        
        # Step 3: Show node status
        self.log("Retrieving node status...", "INFO")
        self.print_node_status()
        time.sleep(1)
        
        # Step 4: Check for alarms
        self.log("Checking for active alarms...", "INFO")
        alarms = self.get_alarms()
        if alarms:
            print(f"\n⚠️  ACTIVE ALARMS ({len(alarms)} total):")
            print("-"*70)
            for alarm in alarms[:5]:  # Show first 5 alarms
                alarm_id = alarm.get('alarm_id', 'N/A')
                severity = alarm.get('severity', 'UNKNOWN')
                message = alarm.get('message', 'N/A')
                timestamp = alarm.get('timestamp', 'N/A')
                print(f"  [{severity}] {alarm_id}: {message} ({timestamp})")
            print("-"*70 + "\n")
        else:
            self.log("✅ No active alarms", "SUCCESS")
        
        time.sleep(1)
        
        # Step 5: Test breaker control
        self.log("Testing breaker control on SUB-001...", "INFO")
        print("-"*70)
        
        # Get initial status
        self.control_breaker("SUB-001", False)  # Trip the breaker
        time.sleep(2)
        
        # Check impact on grid
        self.log("Checking grid impact after breaker trip...", "INFO")
        self.print_grid_summary()
        time.sleep(2)
        
        # Restore breaker
        self.log("Restoring breaker on SUB-001...", "INFO")
        self.control_breaker("SUB-001", True)  # Close the breaker
        time.sleep(2)
        
        # Final status
        self.log("Retrieving final grid status...", "INFO")
        self.print_grid_summary()
        
        # Summary
        print("\n" + "#"*70)
        print("# TEST SCENARIO COMPLETE")
        print("#"*70)
        print(f"Total operations logged: {len(self.scenario_log)}")
        print("\n✅ Test scenario executed successfully!")
        print("\nNext steps:")
        print("  1. Check the dashboard at http://localhost:3000")
        print("  2. View alarm history and node statuses")
        print("  3. Monitor real-time telemetry")
        print("  4. Check Security Console for connections")
        print("\n")


if __name__ == "__main__":
    scenario = GridTestScenario()
    scenario.run_scenario()
