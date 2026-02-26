"""
SCADA Master Control Station
============================

Coordinates communication with all 15 RTU nodes via Modbus and IEC 104 protocols.

Features:
    - Multi-protocol support (Modbus TCP + IEC 104)
    - Asynchronous polling of all connected nodes
    - Measurement data aggregation
    - Command execution (breaker control, OLTC, etc.)
    - Alarm/event handling
    - Connection health monitoring
    - Real-time dashboard output
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import time

from protocols.modbus.client import ModbusClient
from protocols.iec104.client import IEC104Client


logger = logging.getLogger(__name__)


class NodeConnection:
    """Connection to a single RTU node with protocol options."""
    
    def __init__(self, node_id: str, ip: str, modbus_port: int = 502,
                 iec104_port: Optional[int] = None):
        """
        Initialize node connection.
        
        Args:
            node_id: E.g. "GEN-001", "SUB-003", "DIST-001"
            ip: IP address or hostname
            modbus_port: Modbus TCP port
            iec104_port: IEC 104 port (optional)
        """
        self.node_id = node_id
        self.ip = ip
        
        # Clients
        self.modbus: Optional[ModbusClient] = ModbusClient(ip, modbus_port)
        self.iec104: Optional[IEC104Client] = None
        if iec104_port:
            self.iec104 = IEC104Client(ip, iec104_port)
        
        # Last known state
        self.voltage_kv: float = 0.0
        self.current_a: float = 0.0
        self.power_mw: float = 0.0
        self.frequency_hz: float = 50.0
        self.breaker_closed: bool = True
        
        # Connection status
        self.preferred_protocol = 'modbus'  # Try modbus first
        self.last_poll_time: Optional[datetime] = None
        self.is_healthy: bool = False
    
    def __str__(self):
        return (f"{self.node_id} @ {self.ip} "
               f"- V={self.voltage_kv:.1f}kV P={self.power_mw:.1f}MW F={self.frequency_hz:.2f}Hz "
               f"OK={self.is_healthy}")


class SCADAMaster:
    """
    SCADA Master Control Station.
    
    Manages 15 RTU nodes, performs periodic polling, and handles commands.
    """
    
    def __init__(self, log_level=logging.INFO):
        """
        Initialize SCADA master.
        
        Args:
            log_level: Logging level for console output
        """
        self.logger = logging.getLogger("SCADAMaster")
        self.logger.setLevel(log_level)
        
        # Node management
        self.nodes: Dict[str, NodeConnection] = {}
        self.polling_interval_s = 1.0  # Poll all nodes every second
        self.running = False
        
        # Measurements history
        self.measurements_buffer: Dict[str, List[Dict]] = {}
        
        # Commands queue
        self.command_queue: asyncio.Queue = None
        
        # Statistics
        self.stats = {
            'start_time': datetime.now(),
            'total_polls': 0,
            'successful_polls': 0,
            'failed_polls': 0,
            'alarms_generated': 0,
        }
        
        self._setup_logging()
    
    def _setup_logging(self):
        """Configure logging output."""
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def add_node(self, node_id: str, ip: str, modbus_port: int = 502,
                iec104_port: Optional[int] = None):
        """
        Add RTU node to monitoring.
        
        Args:
            node_id: Node identifier (e.g., "GEN-001")
            ip: IP address
            modbus_port: Modbus TCP port
            iec104_port: Optional IEC 104 port
        """
        conn = NodeConnection(node_id, ip, modbus_port, iec104_port)
        self.nodes[node_id] = conn
        self.measurements_buffer[node_id] = []
        self.logger.info(f"Added node: {node_id} @ {ip}")
    
    async def start(self):
        """Start SCADA master polling and command processing."""
        self.running = True
        self.command_queue = asyncio.Queue()
        self.logger.info("="*70)
        self.logger.info("SCADA MASTER - Starting")
        self.logger.info(f"Nodes: {len(self.nodes)} | Polling interval: {self.polling_interval_s}s")
        self.logger.info("="*70)
        
        # Start polling and command tasks
        tasks = [
            asyncio.create_task(self._polling_loop()),
            asyncio.create_task(self._command_handler()),
            asyncio.create_task(self._status_reporter()),
        ]
        
        try:
            await asyncio.gather(*tasks)
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop SCADA master."""
        self.running = False
        
        # Disconnect all nodes
        for node_id, conn in self.nodes.items():
            if conn.modbus and conn.modbus.connected:
                conn.modbus.disconnect()
            if conn.iec104 and conn.iec104.connected:
                await conn.iec104.disconnect()
        
        self.logger.info("SCADA Master stopped")
    
    async def _polling_loop(self):
        """Main polling loop - connects to nodes and reads measurements."""
        while self.running:
            poll_start = datetime.now()
            
            # Poll all nodes concurrently
            tasks = [self._poll_node(node_id, conn) 
                    for node_id, conn in self.nodes.items()]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            self.stats['total_polls'] += len(results)
            for result in results:
                if result is True:
                    self.stats['successful_polls'] += 1
                else:
                    self.stats['failed_polls'] += 1
            
            # Maintain polling interval
            elapsed = (datetime.now() - poll_start).total_seconds()
            wait_time = max(0, self.polling_interval_s - elapsed)
            
            if wait_time > 0:
                await asyncio.sleep(wait_time)
    
    async def _poll_node(self, node_id: str, conn: NodeConnection) -> bool:
        """
        Poll single node for measurements.
        
        Returns:
            True if poll successful
        """
        try:
            # Try preferred protocol first
            if conn.preferred_protocol == 'modbus' and conn.modbus:
                if await self._poll_modbus(conn):
                    conn.is_healthy = True
                    conn.last_poll_time = datetime.now()
                    return True
                elif conn.iec104:
                    # Fallback to IEC 104
                    return await self._poll_iec104(conn)
            
            elif conn.iec104:
                if await self._poll_iec104(conn):
                    conn.is_healthy = True
                    conn.last_poll_time = datetime.now()
                    return True
            
            conn.is_healthy = False
            return False
        
        except Exception as e:
            self.logger.error(f"Poll error for {node_id}: {e}")
            conn.is_healthy = False
            return False
    
    async def _poll_modbus(self, conn: NodeConnection) -> bool:
        """Poll node via Modbus TCP."""
        try:
            if not conn.modbus.connected:
                if not conn.modbus.connect():
                    return False
            
            # Read voltage (register 3000)
            voltage_raw = conn.modbus.read_input_registers(3000, 1)
            if voltage_raw:
                conn.voltage_kv = voltage_raw[0] / 27.0  # 0.037037 kV/LSB
            
            # Read current (register 3001)
            current_raw = conn.modbus.read_input_registers(3001, 1)
            if current_raw:
                conn.current_a = current_raw[0] / 10.0  # 0.1 A/LSB
            
            # Read power (register 3002)
            power_raw = conn.modbus.read_input_registers(3002, 1)
            if power_raw:
                conn.power_mw = power_raw[0] / 100.0  # 0.01 MW/LSB
            
            # Read frequency (register 3003)
            freq_raw = conn.modbus.read_input_registers(3003, 1)
            if freq_raw:
                conn.frequency_hz = freq_raw[0] / 1000.0  # 0.001 Hz/LSB
            
            # Read breaker status (coil 0)
            breaker_state = conn.modbus.read_coils(0, 1)
            if breaker_state:
                conn.breaker_closed = breaker_state[0]
            
            # Store measurement
            self._store_measurement(conn)
            return True
        
        except Exception as e:
            self.logger.error(f"Modbus poll failed: {e}")
            return False
    
    async def _poll_iec104(self, conn: NodeConnection) -> bool:
        """Poll node via IEC 104."""
        try:
            if not conn.iec104.connected:
                if not await conn.iec104.connect():
                    return False
            
            # Interrogate all measurements
            if await conn.iec104.interrogate():
                # Read measurements from client buffer
                conn.voltage_kv = conn.iec104.get_measurement(1) or conn.voltage_kv
                conn.current_a = conn.iec104.get_measurement(2) or conn.current_a
                conn.power_mw = conn.iec104.get_measurement(3) or conn.power_mw
                conn.frequency_hz = conn.iec104.get_measurement(4) or conn.frequency_hz
                
                self._store_measurement(conn)
                return True
            
            return False
        
        except Exception as e:
            self.logger.error(f"IEC 104 poll failed: {e}")
            return False
    
    def _store_measurement(self, conn: NodeConnection):
        """Store measurement in history."""
        measurement = {
            'timestamp': datetime.now(),
            'voltage_kv': conn.voltage_kv,
            'current_a': conn.current_a,
            'power_mw': conn.power_mw,
            'frequency_hz': conn.frequency_hz,
        }
        
        buffer = self.measurements_buffer[conn.node_id]
        buffer.append(measurement)
        
        # Keep last 1000 measurements per node
        if len(buffer) > 1000:
            buffer.pop(0)
        
        # Trigger alarms
        self._check_alarms(conn)
    
    def _check_alarms(self, conn: NodeConnection):
        """Check for alarm conditions."""
        alarms = []
        
        # Overvoltage
        if conn.voltage_kv > 250:
            alarms.append(f"Overvoltage: {conn.voltage_kv:.1f} kV")
        
        # Undervoltage
        if conn.voltage_kv < 200 and conn.voltage_kv > 0:
            alarms.append(f"Undervoltage: {conn.voltage_kv:.1f} kV")
        
        # Overfrequency
        if conn.frequency_hz > 50.5:
            alarms.append(f"Overfrequency: {conn.frequency_hz:.2f} Hz")
        
        # Underfrequency
        if conn.frequency_hz < 49.5:
            alarms.append(f"Underfrequency: {conn.frequency_hz:.2f} Hz")
        
        for alarm in alarms:
            self.logger.warning(f"ALARM [{conn.node_id}]: {alarm}")
            self.stats['alarms_generated'] += 1
    
    async def _command_handler(self):
        """Process command queue (sending commands to nodes)."""
        while self.running:
            try:
                # Get command with timeout
                command = await asyncio.wait_for(
                    self.command_queue.get(),
                    timeout=1.0
                )
                
                await self._execute_command(command)
            
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Command handler error: {e}")
    
    async def _execute_command(self, command: Dict):
        """
        Execute command on RTU node.
        
        Command format:
        {
            'node_id': 'GEN-001',
            'action': 'close_breaker',  # 'close_breaker', 'open_breaker', 'raise_oltc', ...
            'value': 1,  # Optional value
        }
        """
        node_id = command.get('node_id')
        action = command.get('action')
        value = command.get('value')
        
        if node_id not in self.nodes:
            self.logger.error(f"Unknown node: {node_id}")
            return
        
        conn = self.nodes[node_id]
        
        if action == 'close_breaker':
            # Write to breaker coil
            if conn.modbus.connected:
                if conn.modbus.write_coil(0, True):
                    self.logger.info(f"Command executed: {node_id} - CLOSE BREAKER")
        
        elif action == 'open_breaker':
            if conn.modbus.connected:
                if conn.modbus.write_coil(0, False):
                    self.logger.info(f"Command executed: {node_id} - OPEN BREAKER")
        
        elif action == 'raise_oltc':
            if conn.modbus.connected:
                if conn.modbus.write_register(4009, 1):  # OLTC raise command
                    self.logger.info(f"Command executed: {node_id} - RAISE OLTC")
        
        elif action == 'lower_oltc':
            if conn.modbus.connected:
                if conn.modbus.write_register(4009, -1):  # OLTC lower command
                    self.logger.info(f"Command executed: {node_id} - LOWER OLTC")
    
    async def _status_reporter(self):
        """Periodic status reporting."""
        while self.running:
            await asyncio.sleep(5)  # Report every 5 seconds
            self._print_status()
    
    def _print_status(self):
        """Print current status of all nodes."""
        healthy = sum(1 for c in self.nodes.values() if c.is_healthy)
        total = len(self.nodes)
        
        self.logger.info("-" * 70)
        self.logger.info(f"SCADA Status: {healthy}/{total} nodes healthy")
        self.logger.info(f"Total polls: {self.stats['total_polls']} "
                        f"(Success: {self.stats['successful_polls']}, "
                        f"Failed: {self.stats['failed_polls']})")
        self.logger.info("-" * 70)
        
        # List nodes
        for node_id in sorted(self.nodes.keys()):
            self.logger.info(str(self.nodes[node_id]))
    
    async def send_command(self, node_id: str, action: str, value: Optional[float] = None):
        """
        Queue command for execution.
        
        Args:
            node_id: Target node
            action: Command action
            value: Optional value
        """
        command = {'node_id': node_id, 'action': action}
        if value is not None:
            command['value'] = value
        
        await self.command_queue.put(command)
        self.logger.info(f"Queued command: {node_id} - {action}")
    
    def get_node_data(self, node_id: str) -> Optional[NodeConnection]:
        """Get data for single node."""
        return self.nodes.get(node_id)
    
    def get_all_nodes(self) -> Dict[str, NodeConnection]:
        """Get all nodes."""
        return self.nodes


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("SCADA Master module - import and use SCADAMaster class")
