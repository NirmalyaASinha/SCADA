"""
IEC 104 TCP Client Wrapper
==========================

Wrapper around IEC 104 protocol for SCADA master communication.

Features:
    - Connection management with STARTDT/STOPDT handshake
    - Measurement reading (interrogation)
    - Control command sending
    - Keep-alive (TESTFR) handling
    - Event logging
"""

import asyncio
import logging
from typing import Optional, Dict, List
from datetime import datetime

from protocols.iec104.messages import (
    APDU, APCI, ASDU, APDUType, TypeID, CauseOfTransmission,
    ObjectAddress, UFrameFunction
)


logger = logging.getLogger(__name__)


class IEC104Client:
    """
    IEC 104 TCP client for communication with RTU nodes.
    
    Handles connection lifecycle, message exchange, and measurement retrieval.
    """
    
    def __init__(self, host: str, port: int = 2404, timeout_s: float = 5.0):
        """
        Initialize IEC 104 client.
        
        Args:
            host: RTU IP address
            port: IEC 104 TCP port (default 2404)
            timeout_s: Connection timeout
        """
        self.host = host
        self.port = port
        self.timeout_s = timeout_s
        
        # Connection state
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self.started = False  # Data transfer active
        
        # Sequence numbers
        self.send_sequence = 0
        self.recv_sequence = 0
        
        # Keep-alive
        self.testfr_active = False
        self.last_activity = datetime.now()
        
        # Data
        self.measurements: Dict[int, float] = {}
        self.rx_buffer = bytearray()
        
        # Statistics
        self.stats = {
            'connections': 0,
            'disconnections': 0,
            'commands_sent': 0,
            'interrogations': 0,
            'errors': 0,
        }
    
    async def connect(self) -> bool:
        """
        Connect to IEC 104 server.
        
        Returns:
            True if connection and STARTDT successful
        """
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout_s
            )
            self.connected = True
            self.stats['connections'] += 1
            logger.info(f"IEC 104 connected to {self.host}:{self.port}")
            
            # Send STARTDT
            if await self._send_startdt():
                self.started = True
                return True
            else:
                self.connected = False
                return False
        
        except Exception as e:
            logger.error(f"IEC 104 connection failed to {self.host}: {e}")
            self.stats['errors'] += 1
            return False
    
    async def disconnect(self):
        """Disconnect from IEC 104 server."""
        if self.connected:
            try:
                # Send STOPDT
                await self._send_stopdt()
            except:
                pass
            
            if self.writer:
                self.writer.close()
                try:
                    await self.writer.wait_closed()
                except:
                    pass
        
        self.connected = False
        self.started = False
        self.stats['disconnections'] += 1
        logger.info(f"IEC 104 disconnected from {self.host}")
    
    async def _send_startdt(self) -> bool:
        """Send STARTDT activation and wait for confirmation."""
        try:
            apdu = APDU.create_startdt_act()
            await self._send_apdu(apdu)
            
            # Wait for STARTDT_CON
            response = await self._receive_apdu(timeout=self.timeout_s)
            if response and response.apci.u_function == UFrameFunction.STARTDT_CON:
                logger.info(f"IEC 104 STARTDT confirmed")
                return True
            return False
        except Exception as e:
            logger.error(f"STARTDT failed: {e}")
            return False
    
    async def _send_stopdt(self):
        """Send STOPDT activation and wait for confirmation."""
        try:
            apdu = APDU.create_stopdt_act()
            await self._send_apdu(apdu)
            
            # Wait for STOPDT_CON
            response = await self._receive_apdu(timeout=self.timeout_s)
            if response and response.apci.u_function == UFrameFunction.STOPDT_CON:
                logger.info(f"IEC 104 STOPDT confirmed")
        except Exception as e:
            logger.error(f"STOPDT failed: {e}")
    
    async def interrogate(self) -> bool:
        """
        Request all measurements from RTU (interrogation).
        
        Returns:
            True if interrogation successful
        """
        if not self.started:
            return False
        
        try:
            # Create interrogation command (C_IC_NA_1)
            obj = ObjectAddress(0, TypeID.C_IC_NA_1, CauseOfTransmission.INTERROGATION, 0.0)
            asdu = ASDU(TypeID.C_IC_NA_1, CauseOfTransmission.INTERROGATION, objects=[obj])
            apdu = APDU.create_data(self.send_sequence, self.recv_sequence, asdu)
            
            await self._send_apdu(apdu)
            self.send_sequence = (self.send_sequence + 1) & 0x7FFF
            self.stats['interrogations'] += 1
            
            # Receive response (may be multiple ASDUs)
            for _ in range(10):  # Allow multiple responses
                response = await self._receive_apdu(timeout=1.0)
                if response and response.asdu:
                    self._process_asdu(response.asdu)
            
            return True
        
        except Exception as e:
            logger.error(f"Interrogation failed: {e}")
            self.stats['errors'] += 1
            return False
    
    async def send_command(self, information_object_address: int, value: float,
                          command_type: TypeID = TypeID.C_SC_NA_1) -> bool:
        """
        Send control command to RTU.
        
        Args:
            information_object_address: IOA of control point
            value: Command value
            command_type: Type of command (default single command)
        
        Returns:
            True if command accepted
        """
        if not self.started:
            return False
        
        try:
            obj = ObjectAddress(information_object_address, command_type,
                              CauseOfTransmission.ACTIVATION, value)
            asdu = ASDU(command_type, CauseOfTransmission.ACTIVATION, objects=[obj])
            apdu = APDU.create_data(self.send_sequence, self.recv_sequence, asdu)
            
            await self._send_apdu(apdu)
            self.send_sequence = (self.send_sequence + 1) & 0x7FFF
            self.stats['commands_sent'] += 1
            
            logger.info(f"Sent IEC 104 command: IOA={information_object_address} value={value}")
            return True
        
        except Exception as e:
            logger.error(f"Send command failed: {e}")
            self.stats['errors'] += 1
            return False
    
    async def _send_apdu(self, apdu: APDU):
        """Send APDU to server."""
        if not self.writer:
            raise Exception("Not connected")
        
        data = apdu.encode()
        self.writer.write(data)
        await self.writer.drain()
        self.last_activity = datetime.now()
    
    async def _receive_apdu(self, timeout: float = 5.0) -> Optional[APDU]:
        """Receive APDU from server."""
        if not self.reader:
            return None
        
        try:
            # Receive data with timeout
            while len(self.rx_buffer) < 6:
                chunk = await asyncio.wait_for(
                    self.reader.read(1024),
                    timeout=timeout
                )
                if not chunk:
                    raise Exception("Connection closed")
                self.rx_buffer.extend(chunk)
            
            # Try to decode APDU
            try:
                apdu, consumed = APDU.decode(bytes(self.rx_buffer))
                self.rx_buffer = self.rx_buffer[consumed:]
                self.last_activity = datetime.now()
                return apdu
            except ValueError:
                # Invalid APDU, skip one byte
                self.rx_buffer.pop(0)
                return None
        
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Receive error: {e}")
            raise
    
    def _process_asdu(self, asdu: ASDU):
        """Process received ASDU and store measurements."""
        if asdu.type_id in [TypeID.M_ME_NC_1, TypeID.M_ME_NB_1]:
            for obj in asdu.objects:
                self.measurements[obj.information_object_address] = obj.value
                logger.debug(f"Measurement: IOA={obj.information_object_address} "
                           f"value={obj.value} quality=0x{obj.quality:02x}")
    
    def get_measurement(self, information_object_address: int) -> Optional[float]:
        """Get previously received measurement."""
        return self.measurements.get(information_object_address)
    
    def is_healthy(self) -> bool:
        """Check if connection is healthy."""
        if not self.connected or not self.started:
            return False
        
        # Check for timeout
        if (datetime.now() - self.last_activity).total_seconds() > 30:
            return False
        
        return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("IEC 104 TCP client module - import and use IEC104Client class")
