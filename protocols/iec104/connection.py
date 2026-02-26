"""
IEC 60870-5-104 Connection State Machine
========================================

Manages the lifecycle of an IEC 104 connection between RTU and SCADA master.

Connection states:
    IDLE - Waiting for connection
    CONNECTED - TCP connected but not yet started
    STARTED - Data transfer active (STARTDT confirmed)
    STOPPED - Connection closed
    ERROR - Connection error

Sequence:
    1. Client connects (CONNECTED)
    2. Client sends STARTDT_ACT
    3. Server responds STARTDT_CON (STARTED)
    4. Data exchange
    5. Client/server sends STOPDT_ACT
    6. Respond STOPDT_CON (CONNECTED)
    7. Close connection (IDLE)

Keep-alive:
    - Periodically send TESTFR_ACT if no data for 30 seconds
    - Expect TESTFR_CON response
    - Timeout after 2 minutes of no activity
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio


class ConnectionState(Enum):
    """IEC 104 connection states"""
    IDLE = 0            # No connection
    CONNECTED = 1       # TCP connected, waiting for STARTDT
    STARTED = 2         # Data transfer active
    STOPPED = 3         # STOPDT received
    ERROR = 4           # Connection error
    TIMEOUT = 5         # No response to keep-alive


@dataclass
class ConnectionStateMachine:
    """
    IEC 104 connection state machine
    
    Attributes:
        state: Current connection state
        remote_address: Client TCP address
        send_sequence: Outgoing message sequence (0-32767)
        recv_sequence: Incoming message sequence (0-32767)
        last_send_time: Timestamp of last sent message
        last_recv_time: Timestamp of last received message
        testfr_active: Whether we're waiting for TESTFR_CON
    """
    
    remote_address: str
    send_sequence: int = 0
    recv_sequence: int = 0
    state: ConnectionState = ConnectionState.IDLE
    last_send_time: datetime = None
    last_recv_time: datetime = None
    testfr_active: bool = False
    rx_buffer: bytearray = None
    tx_queue: asyncio.Queue = None
    
    def __post_init__(self):
        self.last_send_time = datetime.now()
        self.last_recv_time = datetime.now()
        if self.rx_buffer is None:
            self.rx_buffer = bytearray()
        if self.tx_queue is None:
            self.tx_queue = asyncio.Queue()
    
    def on_connected(self):
        """Handle TCP connection established"""
        if self.state == ConnectionState.IDLE:
            self.state = ConnectionState.CONNECTED
            self.send_sequence = 0
            self.recv_sequence = 0
            self.last_recv_time = datetime.now()
            return True
        return False
    
    def on_startdt_act(self) -> bool:
        """Handle STARTDT activation request from client"""
        if self.state == ConnectionState.CONNECTED:
            self.state = ConnectionState.STARTED
            self.last_recv_time = datetime.now()
            return True
        return False
    
    def on_stopdt_act(self) -> bool:
        """Handle STOPDT activation request from client"""
        if self.state == ConnectionState.STARTED:
            self.state = ConnectionState.STOPPED
            self.last_recv_time = datetime.now()
            return True
        return False
    
    def on_testfr_act(self) -> bool:
        """Handle TESTFR activation from client (echo response)"""
        self.last_recv_time = datetime.now()
        return True
    
    def on_testfr_con(self) -> bool:
        """Handle TESTFR confirmation from client"""
        if self.testfr_active:
            self.testfr_active = False
            self.last_recv_time = datetime.now()
            return True
        return False
    
    def on_data_received(self):
        """Update timestamp when data received"""
        self.last_recv_time = datetime.now()
    
    def on_data_sent(self):
        """Update sequence and timestamp on send"""
        self.send_sequence = (self.send_sequence + 1) & 0x7FFF
        self.last_send_time = datetime.now()
    
    def on_recv_sequence_received(self, seq: int):
        """Update receive sequence from incoming frame"""
        self.recv_sequence = seq
    
    def next_send_sequence(self) -> int:
        """Get next send sequence number"""
        return self.send_sequence
    
    def next_recv_sequence(self) -> int:
        """Get expected receive sequence"""
        return self.recv_sequence
    
    def is_active(self) -> bool:
        """Check if connection is in active data transfer state"""
        return self.state == ConnectionState.STARTED
    
    def is_connected(self) -> bool:
        """Check if connection is TCP connected"""
        return self.state in [ConnectionState.CONNECTED, ConnectionState.STARTED]
    
    def check_timeout(self, idle_timeout_s: int = 120) -> bool:
        """
        Check for receive timeout
        
        Returns:
            True if timeout exceeded, False otherwise
        """
        if self.state == ConnectionState.IDLE:
            return False
        
        elapsed = (datetime.now() - self.last_recv_time).total_seconds()
        return elapsed > idle_timeout_s
    
    def check_keep_alive(self, keep_alive_s: int = 30) -> bool:
        """
        Check if keep-alive (TESTFR) transmission is needed
        
        Returns:
            True if TESTFR should be sent, False otherwise
        """
        if not self.is_active():
            return False
        
        if self.testfr_active:
            # Already waiting for TESTFR_CON
            return False
        
        elapsed = (datetime.now() - self.last_send_time).total_seconds()
        return elapsed > keep_alive_s
    
    def need_testfr(self) -> bool:
        """Check if we should send TESTFR_ACT"""
        keep_alive = self.check_keep_alive()
        if keep_alive:
            self.testfr_active = True
        return keep_alive
    
    def on_error(self, error: str):
        """Handle connection error"""
        self.state = ConnectionState.ERROR
        print(f"IEC104 Connection Error [{self.remote_address}]: {error}")
    
    def disconnect(self):
        """Mark connection as disconnected"""
        self.state = ConnectionState.IDLE
    
    def __str__(self):
        return (f"IEC104[{self.remote_address}] state={self.state.name} "
                f"tx={self.send_sequence} rx={self.recv_sequence} "
                f"testfr={self.testfr_active}")
