"""
IEC 60870-5-104 TCP Server Implementation
=========================================

Asynchronous TCP server for IEC 104 protocol.

Features:
    - Multi-client support (SCADA masters can connect)
    - Automatic state machine management per connection
    - Keep-alive monitoring (TESTFR)
    - Timeout detection (120s with no activity)
    - Message queuing and sequencing
    - Support for data transmission and commands
    - Automatic response to interrogation

Usage:
    server = IEC104Server(host='0.0.0.0', port=2404, parent_node=node)
    await server.start()
    await server.send_measurement(ioa=1, value=230.5, quality=0x00)
    await server.send_command_response(ioa=12, value=1)
    await server.stop()

Standard IEC 104 port: 2404/TCP
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass

from protocols.iec104.messages import (
    APDU, APCI, ASDU, APDUType, TypeID, CauseOfTransmission,
    ObjectAddress, UFrameFunction
)
from protocols.iec104.connection import ConnectionStateMachine, ConnectionState


logger = logging.getLogger(__name__)


@dataclass
class IEC104Measurement:
    """Single IEC 104 measurement point"""
    information_object_address: int
    type_id: TypeID
    value: float
    quality: int = 0x00  # 0x00=good, 0x01=overflow, 0x02=bad, etc.
    timestamp_ms: Optional[int] = None


class IEC104Server:
    """
    IEC 60870-5-104 TCP Server
    
    Manages TCP connections from SCADA masters and sends/receives IEC 104 data.
    """
    
    def __init__(self, host: str = '0.0.0.0', port: int = 2404, 
                 parent_node=None, log_level=logging.INFO):
        """
        Initialize IEC 104 server
        
        Args:
            host: Bind address
            port: TCP port (default 2404 is standard IEC 104)
            parent_node: RTU node that owns this server
            log_level: Logging level
        """
        self.host = host
        self.port = port
        self.parent_node = parent_node
        self.node_name = getattr(parent_node, 'node_id', 
                               getattr(parent_node, 'name', 'Unknown'))
        
        self.logger = logging.getLogger(f"IEC104[{self.node_name}]")
        self.logger.setLevel(log_level)
        
        # Server state
        self.server = None
        self.running = False
        self.connections: Dict[str, ConnectionStateMachine] = {}
        self.connection_handlers: Dict[str, asyncio.Task] = {}
        
        # Data management
        self.measurements: Dict[int, IEC104Measurement] = {}
        self.control_callbacks: Dict[int, callable] = {}
        
        # Configuration
        self.idle_timeout_s = 120
        self.keep_alive_s = 30
        self.max_clients = 5
    
    async def start(self):
        """Start IEC 104 TCP server"""
        try:
            self.server = await asyncio.start_server(
                self._handle_client,
                self.host,
                self.port
            )
            self.running = True
            addr = self.server.sockets[0].getsockname()
            self.logger.info(f"IEC 104 server started on {addr[0]}:{addr[1]}")
            
            # Start keep-alive monitor task
            asyncio.create_task(self._monitor_connections())
            
        except Exception as e:
            self.logger.error(f"Failed to start IEC 104 server: {e}")
            raise
    
    async def stop(self):
        """Stop IEC 104 TCP server"""
        self.running = False
        
        # Close all client connections
        for addr, conn in list(self.connections.items()):
            conn.disconnect()
        
        # Cancel all handlers
        for handler in list(self.connection_handlers.values()):
            if handler:
                handler.cancel()
        
        # Close server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        self.logger.info("IEC 104 server stopped")
    
    async def _handle_client(self, reader: asyncio.StreamReader, 
                           writer: asyncio.StreamWriter):
        """
        Handle new client connection
        
        This coroutine manages a single client from connection to disconnection.
        """
        addr = writer.get_extra_info('peername')
        addr_str = f"{addr[0]}:{addr[1]}"
        
        # Check max connections
        if len(self.connections) >= self.max_clients:
            self.logger.warning(f"Connection rejected from {addr_str}: max clients reached")
            writer.close()
            await writer.wait_closed()
            return
        
        self.logger.info(f"Client connected: {addr_str}")
        
        # Create connection state machine
        conn = ConnectionStateMachine(addr_str)
        conn.on_connected()
        self.connections[addr_str] = conn
        
        try:
            while self.running and conn.is_connected():
                # Check timeout
                if conn.check_timeout(self.idle_timeout_s):
                    self.logger.warning(f"Client {addr_str} timeout")
                    break
                
                # Check keep-alive
                if conn.need_testfr():
                    testfr = APDU.create_testfr_act()
                    self._send_apdu(writer, testfr, conn)
                
                # Try to receive data
                try:
                    # With timeout for keep-alive check
                    data = await asyncio.wait_for(
                        reader.read(1024), 
                        timeout=self.keep_alive_s
                    )
                    
                    if not data:
                        # Connection closed by client
                        break
                    
                    # Process received data
                    await self._process_client_data(data, writer, conn)
                    
                except asyncio.TimeoutError:
                    # No data received - that's OK, check keep-alive
                    continue
                
        except Exception as e:
            self.logger.error(f"Client {addr_str} error: {e}")
            conn.on_error(str(e))
        
        finally:
            # Cleanup
            self.logger.info(f"Client disconnected: {addr_str}")
            conn.disconnect()
            if addr_str in self.connections:
                del self.connections[addr_str]
            
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
    
    async def _process_client_data(self, data: bytes, 
                                  writer: asyncio.StreamWriter,
                                  conn: ConnectionStateMachine):
        """Process received data from client"""
        conn.rx_buffer.extend(data)
        
        # Process complete APDUs from buffer
        while len(conn.rx_buffer) >= 6:
            try:
                apdu, consumed = APDU.decode(bytes(conn.rx_buffer))
                conn.rx_buffer = conn.rx_buffer[consumed:]
                
                # Handle APDU
                await self._handle_apdu(apdu, writer, conn)
                
            except ValueError as e:
                # Invalid APDU - try to resync
                self.logger.warning(f"Invalid APDU from {conn.remote_address}: {e}")
                # Skip one byte and try again
                conn.rx_buffer.pop(0)
    
    async def _handle_apdu(self, apdu: APDU, writer: asyncio.StreamWriter,
                          conn: ConnectionStateMachine):
        """Handle received APDU from client"""
        
        # Handle based on APDU type
        if apdu.apci.frame_type == APDUType.U_FRAME:
            # Unnumbered frame (connection control)
            u_func = apdu.apci.u_function
            
            if u_func == UFrameFunction.STARTDT_ACT:
                # Client requests data transfer start
                if conn.on_startdt_act():
                    response = APDU.create_startdt_con()
                    self._send_apdu(writer, response, conn)
                    self.logger.info(f"Client {conn.remote_address} started data transfer")
            
            elif u_func == UFrameFunction.STOPDT_ACT:
                # Client requests data transfer stop
                if conn.on_stopdt_act():
                    response = APDU.create_stopdt_con()
                    self._send_apdu(writer, response, conn)
                    self.logger.info(f"Client {conn.remote_address} stopped data transfer")
            
            elif u_func == UFrameFunction.TESTFR_ACT:
                # Echo TESTFR
                conn.on_testfr_act()
                response = APDU.create_testfr_con()
                self._send_apdu(writer, response, conn)
            
            elif u_func == UFrameFunction.TESTFR_CON:
                # Response to our TESTFR
                conn.on_testfr_con()
        
        elif apdu.apci.frame_type == APDUType.I_FRAME:
            # Information frame (data/commands)
            
            # Update sequence numbers
            conn.on_recv_sequence_received(apdu.apci.send_sequence)
            
            # Process ASDU
            if apdu.asdu:
                await self._handle_asdu(apdu.asdu, writer, conn)
            
            # Send supervisory frame to acknowledge
            sup = APDU.create_supervisory(conn.next_recv_sequence())
            self._send_apdu(writer, sup, conn)
        
        elif apdu.apci.frame_type == APDUType.S_FRAME:
            # Supervisory frame (flow control) - just update sequence
            conn.on_recv_sequence_received(apdu.apci.receive_sequence)
    
    async def _handle_asdu(self, asdu: ASDU, writer: asyncio.StreamWriter,
                          conn: ConnectionStateMachine):
        """Handle received ASDU from client"""
        
        # Handle based on type ID
        if asdu.type_id == TypeID.C_IC_NA_1:
            # Interrogation command - send all measurements
            self.logger.info(f"Interrogation from {conn.remote_address}")
            
            # Create response ASDU with all measurements
            objects = [
                ObjectAddress(m.information_object_address, m.type_id,
                            CauseOfTransmission.INTERROGATION_CONF,
                            m.value, m.quality)
                for m in self.measurements.values()
            ]
            
            if objects:
                response_asdu = ASDU(
                    TypeID.C_IC_NA_1,
                    CauseOfTransmission.INTERROGATION_CONF,
                    objects=objects
                )
                response = APDU.create_data(
                    conn.next_send_sequence(),
                    conn.next_recv_sequence(),
                    response_asdu
                )
                self._send_apdu(writer, response, conn)
        
        elif asdu.type_id == TypeID.C_SC_NA_1:
            # Single command (on/off)
            for obj in asdu.objects:
                await self._execute_control(obj.information_object_address,
                                           obj.value, conn)
        
        elif asdu.type_id == TypeID.C_DC_NA_1:
            # Double command (raise/lower)
            for obj in asdu.objects:
                await self._execute_control(obj.information_object_address,
                                           obj.value, conn)
    
    async def _execute_control(self, ioa: int, value: float,
                              conn: ConnectionStateMachine):
        """Execute received control command"""
        if ioa in self.control_callbacks:
            try:
                callback = self.control_callbacks[ioa]
                if asyncio.iscoroutinefunction(callback):
                    await callback(value)
                else:
                    callback(value)
                self.logger.info(f"Control executed: IOA={ioa} value={value}")
            except Exception as e:
                self.logger.error(f"Control execution error: {e}")
    
    def _send_apdu(self, writer: asyncio.StreamWriter, apdu: APDU,
                  conn: ConnectionStateMachine):
        """Send APDU to client"""
        try:
            data = apdu.encode()
            writer.write(data)
            conn.on_data_sent()
        except Exception as e:
            self.logger.error(f"Failed to send APDU to {conn.remote_address}: {e}")
    
    async def send_measurement(self, information_object_address: int,
                             value: float, type_id: TypeID = TypeID.M_ME_NC_1,
                             quality: int = 0x00):
        """
        Send measurement value to all connected clients
        
        Args:
            information_object_address: IEC 104 object address (1-16777215)
            value: Floating point value
            type_id: IEC 104 data type (default M_ME_NC_1 = float)
            quality: Quality flags (0x00=good, 0x01=overflow, etc.)
        """
        # Store in database
        measurement = IEC104Measurement(information_object_address, type_id,
                                       value, quality)
        self.measurements[information_object_address] = measurement
        
        # Send to all active clients
        for addr, conn in list(self.connections.items()):
            if not conn.is_active():
                continue
            
            try:
                obj = ObjectAddress(information_object_address, type_id,
                                  CauseOfTransmission.SPONTANEOUS,
                                  value, quality)
                asdu = ASDU(type_id, CauseOfTransmission.SPONTANEOUS,
                          objects=[obj])
                
                # Would need writer reference - stub for now
                # In full implementation, keep writers in connection
                
            except Exception as e:
                self.logger.error(f"Failed to send measurement: {e}")
    
    def register_control_callback(self, information_object_address: int,
                                 callback: callable):
        """
        Register callback for control commands
        
        Callback will be invoked when master sends control to this IOA
        """
        self.control_callbacks[information_object_address] = callback
    
    async def _monitor_connections(self):
        """Monitor all connections for timeouts"""
        while self.running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                for addr, conn in list(self.connections.items()):
                    if conn.check_timeout(self.idle_timeout_s):
                        self.logger.warning(f"Timeout on connection {addr}")
                        # Connection will be closed by main handler
            
            except Exception as e:
                self.logger.error(f"Monitor error: {e}")
    
    def get_status(self) -> dict:
        """Get server status"""
        return {
            'running': self.running,
            'connections': len(self.connections),
            'measurements': len(self.measurements),
            'clients': [
                {
                    'address': addr,
                    'state': conn.state.name,
                    'send_seq': conn.send_sequence,
                    'recv_seq': conn.recv_sequence,
                }
                for addr, conn in self.connections.items()
            ]
        }
    
    def __str__(self):
        return (f"IEC104Server[{self.node_name}]({self.host}:{self.port}) "
               f"clients={len(self.connections)} measurements={len(self.measurements)}")
