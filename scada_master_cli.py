#!/usr/bin/env python3
"""
SCADA Master CLI Interface

Interactive command-line interface for the SCADA master control station.

Usage:
    python3 scada_master_cli.py

Commands:
    start           - Start polling all nodes
    status          - Show current node status
    nodes           - List all configured nodes
    poll <node_id>  - Force poll specific node
    cmd <node_id> <action> [value]  - Send command to node
    help            - Show help
    exit            - Exit program
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent))

from scada_master import SCADAMaster


class SCADAMasterCLI:
    """Interactive CLI for SCADA master."""
    
    def __init__(self):
        """Initialize CLI."""
        self.master = SCADAMaster(log_level=logging.WARNING)
        self.running = False
        self.config_built = False
    
    def setup_nodes(self):
        """Configure the 15 nodes from IEEE test case."""
        print("Setting up 15-node SCADA system (IEEE test case)...\n")
        
        # Generation nodes (3)
        self.master.add_node("GEN-001", "127.0.0.1", modbus_port=502, iec104_port=2414)
        self.master.add_node("GEN-002", "127.0.0.1", modbus_port=502, iec104_port=None)
        self.master.add_node("GEN-003", "127.0.0.1", modbus_port=502, iec104_port=None)
        
        # Substation nodes (7)
        for i in range(1, 8):
            iec_port = 2514 if i == 1 else None
            self.master.add_node(f"SUB-{i:03d}", "127.0.0.1", 
                               modbus_port=502, iec104_port=iec_port)
        
        # Distribution nodes (5)
        for i in range(1, 6):
            iec_port = 2614 if i == 1 else None
            self.master.add_node(f"DIST-{i:03d}", "127.0.0.1",
                               modbus_port=502, iec104_port=iec_port)
        
        print(f"✅ Configured {len(self.master.nodes)} nodes\n")
        self.config_built = True
    
    async def run_interactive(self):
        """Run interactive CLI."""
        self.setup_nodes()
        
        print("="*70)
        print("SCADA Master Control Station - Interactive CLI")
        print("="*70)
        print("\nType 'help' for available commands\n")
        
        loop = asyncio.get_event_loop()
        
        while True:
            try:
                # Get user input
                cmd = await loop.run_in_executor(None, input, "\nSCADA> ")
                cmd = cmd.strip()
                
                if not cmd:
                    continue
                
                parts = cmd.split()
                command = parts[0].lower()
                args = parts[1:] if len(parts) > 1 else []
                
                if command == 'help':
                    self.show_help()
                
                elif command == 'start':
                    await self.cmd_start()
                
                elif command == 'status':
                    self.cmd_status()
                
                elif command == 'nodes':
                    self.cmd_list_nodes()
                
                elif command == 'poll' and args:
                    await self.cmd_poll(args[0])
                
                elif command == 'cmd' and len(args) >= 2:
                    value = float(args[2]) if len(args) > 2 else None
                    await self.cmd_send(args[0], args[1], value)
                
                elif command == 'exit' or command == 'quit':
                    print("\nExiting SCADA master...")
                    break
                
                else:
                    print("Unknown command. Type 'help' for available commands.")
            
            except KeyboardInterrupt:
                print("\n\nExiting SCADA master...")
                break
            except Exception as e:
                print(f"Error: {e}")
    
    def show_help(self):
        """Show help for available commands."""
        help_text = """
Available Commands:
  start               - Start polling all nodes (runs indefinitely)
  status              - Show current status of all nodes
  nodes               - List all configured nodes
  poll <node_id>      - Force immediate poll of specific node
  cmd <node_id> <action> [value]
                      - Send command to node
                        Actions: close_breaker, open_breaker, raise_oltc, lower_oltc
  help                - Show this help message
  exit/quit           - Exit the program

Examples:
  start
  status
  poll GEN-001
  cmd GEN-001 close_breaker
  cmd SUB-001 raise_oltc

Note: Full functionality requires running 'python3 simulator.py' 
in another terminal to simulate RTU nodes.
        """
        print(help_text)
    
    async def cmd_start(self):
        """Start continuous polling."""
        print("Starting SCADA master polling... (Ctrl+C to stop)")
        print("="*70)
        
        try:
            await self.master.start()
        except KeyboardInterrupt:
            print("\n\nPolling stopped.")
            await self.master.stop()
        except Exception as e:
            print(f"Error during polling: {e}")
            await self.master.stop()
    
    def cmd_status(self):
        """Show current status."""
        if not self.config_built:
            print("No nodes configured. Run 'start' first or 'setup'.")
            return
        
        self.master._print_status()
    
    def cmd_list_nodes(self):
        """List all nodes."""
        if not self.config_built:
            print("No nodes configured.")
            return
        
        print("\nConfigured Nodes:")
        print("-" * 70)
        
        for node_type in ['GEN', 'SUB', 'DIST']:
            nodes = [n for n in sorted(self.master.nodes.keys()) 
                    if n.startswith(node_type)]
            if nodes:
                print(f"\n{node_type} (Generation)" if node_type == 'GEN' 
                      else f"{node_type} (Substation)" if node_type == 'SUB'
                      else f"{node_type} (Distribution):")
                for node_id in nodes:
                    print(f"  - {node_id}")
    
    async def cmd_poll(self, node_id: str):
        """Poll specific node."""
        if node_id not in self.master.nodes:
            print(f"Unknown node: {node_id}")
            return
        
        print(f"Polling {node_id}...")
        conn = self.master.nodes[node_id]
        result = await self.master._poll_node(node_id, conn)
        
        if result:
            print(f"✓ {conn}")
        else:
            print(f"✗ Poll failed - {node_id} may not have running Modbus server")
    
    async def cmd_send(self, node_id: str, action: str, value: float = None):
        """Send command to node."""
        if node_id not in self.master.nodes:
            print(f"Unknown node: {node_id}")
            return
        
        valid_actions = ['close_breaker', 'open_breaker', 'raise_oltc', 'lower_oltc']
        if action not in valid_actions:
            print(f"Unknown action: {action}")
            print(f"Valid actions: {', '.join(valid_actions)}")
            return
        
        await self.master.send_command(node_id, action, value)
        print(f"✓ Command queued: {node_id} - {action}")


async def main():
    """Main entry point."""
    cli = SCADAMasterCLI()
    
    try:
        await cli.run_interactive()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
