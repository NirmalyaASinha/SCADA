"""
IEC 60870-5-104 Message Structures and Type Codes
==================================================

APDU (Application Protocol Data Unit): IEC 104 message frame
    - APCI (3 bytes): Application Protocol Control Information
    - ASDU (payload): Actual transmission unit with data

APCI format:
    Byte 0: Start byte (always 0x68)
    Byte 1: Length of ASDU
    Byte 2-3: Send Sequence Number (SSN) - 15 bits in bits 1-15
    Byte 4-5: Receive Sequence Number (RSN) - 15 bits in bits 1-15

APDU types:
    - I frame (Information): bit 0=0, SSN and RSN both present (data transfer)
    - S frame (Supervisory): bits 0-1=10, SSN not used, only RSN (flow control)
    - U frame (Unnumbered): bits 0-3=11, both SSN/RSN not used (connection control)
"""

from dataclasses import dataclass, asdict
from enum import IntEnum
from typing import List, Optional, Tuple
import struct


class TypeID(IntEnum):
    """IEC 60870-5-101/104 Object Information Types"""
    
    # Monitoring data (M)
    M_SP_NA_1 = 1      # Single point information
    M_DP_NA_1 = 3      # Double point information
    M_ST_NA_1 = 5      # Step position information
    M_BO_NA_1 = 7      # Bitstring of 32 bits
    M_ME_NA_1 = 9      # Measured value (normalized)
    M_ME_TA_1 = 10     # Measured value with time tag
    M_ME_NB_1 = 11     # Scaled integer measurement
    M_ME_TE_1 = 12     # Scaled integer with time tag
    M_ME_NC_1 = 13     # Short floating point measurement
    M_ME_TF_1 = 14     # Short floating point with time tag
    M_IT_NA_1 = 15     # Integrated totals
    M_PS_NA_1 = 20     # Packed single point
    M_ME_ND_1 = 21     # Normalized float without time tag
    
    # Control commands (C)
    C_SC_NA_1 = 45     # Single command (on/off)
    C_DC_NA_1 = 46     # Double command (raise/lower)
    C_RC_NA_1 = 47     # Regulating step command
    C_SE_NA_1 = 48     # Set point command (normalized)
    C_SE_NB_1 = 49     # Set point command (scaled)
    C_SE_NC_1 = 50     # Set point command (floating point)
    C_BO_NA_1 = 51     # Bitstring command
    
    # System commands
    C_IC_NA_1 = 100    # Interrogation command
    C_CI_NA_1 = 101    # Counter interrogation
    C_RD_NA_1 = 102    # Read command
    C_CD_NA_1 = 103    # Clock synchronization command
    C_TE_NA_1 = 104    # Test command
    C_EX_NA_1 = 105    # Extended interrogation


class CauseOfTransmission(IntEnum):
    """Cause Of Transmission codes"""
    
    NOT_USED = 0
    PER_CYCLIC = 1     # Periodic cyclic
    BACKGROUND = 2     # Background scan
    SPONTANEOUS = 3    # Spontaneous transmission
    INITIALIZED = 4    # Initialized
    REQUEST = 5        # Requested by master
    ACTIVATION = 6     # Activation
    ACTIVATION_CONF = 7  # Activation confirmation
    DEACTIVATION = 8   # Deactivation
    DEACTIVATION_CONF = 9  # Deactivation confirmation
    ACTIVATION_TERM = 10   # Activation termination
    RETURN_INFO_LOCAL = 11 # Return information local
    RETURN_INFO_REMOTE = 12 # Return information remote
    COMMUNICATION_LOST = 13 # Communication lost
    COMMUNICATION_RESTORED = 14 # Communication restored
    INTERROGATION = 20 # Interrogation or interrogation cycle
    INTERROGATION_CONF = 21 # Interrogation confirmation
    UNKNOWN_OBJECT = 44 # Unknown object address
    UNKNOWN_TYPE = 45  # Unknown type identification


@dataclass
class ObjectAddress:
    """IEC 104 object address and data"""
    information_object_address: int  # 3 bytes
    type_id: TypeID
    cause: CauseOfTransmission
    value: float
    quality: int = 0x00  # 0x00=good, 0x01=overflow, 0x02=bad, 0x80=reserved
    timestamp_ms: Optional[int] = None  # For types with time tag


class APDUType(IntEnum):
    """APDU message type classification"""
    I_FRAME = 0        # Information frame (data transfer)
    S_FRAME = 1        # Supervisory frame (flow control)
    U_FRAME = 2        # Unnumbered frame (connection control)


class UFrameFunction(IntEnum):
    """U frame function codes"""
    STARTDT_ACT = 0x01     # Start data transfer (activation)
    STARTDT_CON = 0x81     # Start data transfer (confirmation)
    STOPDT_ACT = 0x02      # Stop data transfer (activation)
    STOPDT_CON = 0x82      # Stop data transfer (confirmation)
    TESTFR_ACT = 0x03      # Test frame (activation)
    TESTFR_CON = 0x83      # Test frame (confirmation)


@dataclass
class APCI:
    """Application Protocol Control Information"""
    frame_type: APDUType
    send_sequence: int = 0      # For I frames (15 bits)
    receive_sequence: int = 0   # For I, S frames (15 bits)
    u_function: Optional[UFrameFunction] = None  # For U frames
    
    def encode(self) -> bytes:
        """
        Encode APCI to 4 bytes
        
        Format:
            Bytes 0-1: Control octet and send sequence
            Bytes 2-3: Control octet and receive sequence
        
        I frame: bit 0 of byte 0 = 0
            b0: SSN[0:7] | control[1] | control[0]=0
            b1: SSN[8:14] | control[15]
            b2: RSN[0:7] | control[1]=1(?) | control[0]=0(?)
            b3: RSN[8:14] | control[15]=?
        """
        if self.frame_type == APDUType.I_FRAME:
            # I frame: control bits = 0x00 in position 0-1
            # SSN split: bits 1-15 of bytes 0-1
            # RSN split: bits 1-15 of bytes 2-3
            byte0 = (self.send_sequence << 1) & 0xFF
            byte1 = (self.send_sequence >> 7) & 0xFF
            byte2 = (self.receive_sequence << 1) & 0xFF
            byte3 = (self.receive_sequence >> 7) & 0xFF
            return bytes([byte0, byte1, byte2, byte3])
            
        elif self.frame_type == APDUType.S_FRAME:
            # S frame: control bits = 0x01 in position 0-1 (bit 0=1)
            # SSN unused, only RSN in bytes 2-3
            byte0 = 0x01  # Control=01b
            byte1 = 0x00
            byte2 = (self.receive_sequence << 1) & 0xFF
            byte3 = (self.receive_sequence >> 7) & 0xFF
            return bytes([byte0, byte1, byte2, byte3])
            
        elif self.frame_type == APDUType.U_FRAME:
            # U frame: control bits = 0x03 in position 0-3
            # Bits 2-7 contain function code
            byte0 = 0x03 | ((self.u_function & 0x3F) << 2)
            byte1 = 0x00
            byte2 = 0x00
            byte3 = 0x00
            return bytes([byte0, byte1, byte2, byte3])
        
        return b''
    
    @staticmethod
    def decode(data: bytes) -> Tuple['APCI', int]:
        """Decode APCI from 4 bytes"""
        if len(data) < 4:
            raise ValueError("APCI too short")
        
        b0, b1, b2, b3 = data[0], data[1], data[2], data[3]
        
        # Determine frame type from bit 0
        bit0 = b0 & 0x01
        bit1 = (b0 >> 1) & 0x01
        
        if bit0 == 0:  # I frame (control bit 0 = 0)
            # Extract SSN from bits 1-15 of bytes 0-1
            # Byte 0 bits 1-7 = SSN[0:7], Byte 1 bits 0-7 = SSN[7:15]
            send_seq = ((b0 >> 1) & 0x7F) | ((b1 & 0xFF) << 7)
            # Extract RSN from bits 1-15 of bytes 2-3
            recv_seq = ((b2 >> 1) & 0x7F) | ((b3 & 0xFF) << 7)
            return APCI(APDUType.I_FRAME, send_seq, recv_seq), 4
            
        elif bit0 == 1 and bit1 == 0:  # S frame (control bits = 01b)
            # No SSN, only RSN in bytes 2-3
            recv_seq = ((b2 >> 1) & 0x7F) | ((b3 & 0xFF) << 7)
            return APCI(APDUType.S_FRAME, 0, recv_seq), 4
            
        elif (b0 & 0x03) == 0x03:  # U frame (control bits = 11b)
            # Function code in bits 2-7
            u_func = (b0 >> 2) & 0x3F
            return APCI(APDUType.U_FRAME, 0, 0, UFrameFunction(u_func)), 4
        
        raise ValueError(f"Invalid APCI control bits in byte 0: 0x{b0:02x}")


@dataclass
class ASDU:
    """Application Service Data Unit"""
    type_id: TypeID
    cause: CauseOfTransmission
    originator: int = 0  # Originator address (0 in station)
    common_address: int = 1  # Common ASDU address
    objects: List[ObjectAddress] = None
    
    def __post_init__(self):
        if self.objects is None:
            self.objects = []
    
    def encode(self) -> bytes:
        """Encode ASDU to bytes"""
        result = bytearray()
        
        # Type ID (1 byte)
        result.append(self.type_id)
        
        # Variable structure qualifier (1 byte)
        # bit 7=1 (no sequence), bits 0-6=number of objects
        num_objects = len(self.objects)
        result.append(0x80 | (num_objects & 0x7F))
        
        # Cause of Transmission (2 bytes)
        # bit 7=0 (positive), bits 0-5=COT code, bits 6=test, bit 7=negative
        test_bit = 0x00
        cot_byte = (self.cause & 0x3F) | test_bit
        result.append(cot_byte)
        result.append(self.originator)
        
        # Common address (2 bytes, little-endian)
        result.append(self.common_address & 0xFF)
        result.append((self.common_address >> 8) & 0xFF)
        
        # Information objects
        for obj in self.objects:
            obj_bytes = self._encode_object(obj)
            result.extend(obj_bytes)
        
        return bytes(result)
    
    def _encode_object(self, obj: ObjectAddress) -> bytes:
        """Encode single information object"""
        result = bytearray()
        
        # Object address (3 bytes, little-endian)
        result.append(obj.information_object_address & 0xFF)
        result.append((obj.information_object_address >> 8) & 0xFF)
        result.append((obj.information_object_address >> 16) & 0xFF)
        
        # Value encoding depends on type ID
        if obj.type_id == TypeID.M_SP_NA_1:  # Single point (0/1)
            result.append(obj.quality | (1 if obj.value else 0))
            
        elif obj.type_id == TypeID.M_DP_NA_1:  # Double point (0/1/transitional)
            dp_value = int(obj.value) & 0x03
            result.append(obj.quality | dp_value)
            
        elif obj.type_id == TypeID.M_ME_NB_1:  # Scaled integer
            val = int(obj.value) & 0xFFFF
            result.append(val & 0xFF)
            result.append((val >> 8) & 0xFF)
            result.append(obj.quality)
            
        elif obj.type_id == TypeID.M_ME_NC_1:  # Short floating point
            # IEEE 754 single precision (4 bytes)
            import struct
            float_bytes = struct.pack('<f', obj.value)
            result.extend(float_bytes)
            result.append(obj.quality)
            
        elif obj.type_id in [TypeID.C_SC_NA_1, TypeID.C_DC_NA_1]:
            # Control command
            result.append(int(obj.value) & 0x01)
        
        return bytes(result)


@dataclass
class APDU:
    """Application Protocol Data Unit (complete message)"""
    apci: APCI
    asdu: Optional[ASDU] = None
    
    def encode(self) -> bytes:
        """Encode complete APDU to bytes"""
        # Encode ASDU if present
        asdu_bytes = self.asdu.encode() if self.asdu else b''
        
        # APDU header: start byte + length
        result = bytearray()
        result.append(0x68)  # Start byte
        result.append(len(asdu_bytes) + 4)  # Length (ASDU + APCI)
        
        # Encode APCI (4 bytes)
        apci_bytes = self.apci.encode()
        result.extend(apci_bytes)
        
        # Add ASDU
        result.extend(asdu_bytes)
        
        return bytes(result)
    
    @staticmethod
    def decode(data: bytes) -> Tuple['APDU', int]:
        """Decode APDU and return consumed bytes"""
        if len(data) < 6:
            raise ValueError("APDU too short")
        
        if data[0] != 0x68:
            raise ValueError(f"Invalid start byte: 0x{data[0]:02x}")
        
        length = data[1]
        if len(data) < 2 + length:
            raise ValueError("Incomplete APDU")
        
        # Decode APCI
        apci_bytes = data[2:6]
        apci, _ = APCI.decode(apci_bytes)
        
        # Decode ASDU if present
        asdu = None
        if length > 4:
            asdu_bytes = data[6:2+length]
            asdu = ASDU.decode_from_bytes(asdu_bytes)
        
        return APDU(apci, asdu), 2 + length
    
    @staticmethod
    def create_startdt_act() -> 'APDU':
        """Create STARTDT activation frame"""
        return APDU(APCI(APDUType.U_FRAME, u_function=UFrameFunction.STARTDT_ACT))
    
    @staticmethod
    def create_startdt_con() -> 'APDU':
        """Create STARTDT confirmation frame"""
        return APDU(APCI(APDUType.U_FRAME, u_function=UFrameFunction.STARTDT_CON))
    
    @staticmethod
    def create_stopdt_act() -> 'APDU':
        """Create STOPDT activation frame"""
        return APDU(APCI(APDUType.U_FRAME, u_function=UFrameFunction.STOPDT_ACT))
    
    @staticmethod
    def create_stopdt_con() -> 'APDU':
        """Create STOPDT confirmation frame"""
        return APDU(APCI(APDUType.U_FRAME, u_function=UFrameFunction.STOPDT_CON))
    
    @staticmethod
    def create_testfr_act() -> 'APDU':
        """Create TESTFR activation frame"""
        return APDU(APCI(APDUType.U_FRAME, u_function=UFrameFunction.TESTFR_ACT))
    
    @staticmethod
    def create_testfr_con() -> 'APDU':
        """Create TESTFR confirmation frame"""
        return APDU(APCI(APDUType.U_FRAME, u_function=UFrameFunction.TESTFR_CON))
    
    @staticmethod
    def create_data(send_seq: int, recv_seq: int, asdu: ASDU) -> 'APDU':
        """Create I frame with data"""
        return APDU(APCI(APDUType.I_FRAME, send_seq, recv_seq), asdu)
    
    @staticmethod
    def create_supervisory(recv_seq: int) -> 'APDU':
        """Create S frame (flow control)"""
        return APDU(APCI(APDUType.S_FRAME, 0, recv_seq))


# Add decode method to ASDU
def asdu_decode_from_bytes(data: bytes) -> ASDU:
    """Decode ASDU from bytes"""
    if len(data) < 6:
        raise ValueError("ASDU too short")
    
    type_id = TypeID(data[0])
    vsq = data[1]  # Variable structure qualifier
    num_objects = vsq & 0x7F
    cot_byte = data[2]
    originator = data[3]
    common_address = data[4] | (data[5] << 8)
    
    cause = CauseOfTransmission(cot_byte & 0x3F)
    
    objects = []
    pos = 6
    
    # Decode objects (simplified - would depend on type_id)
    for i in range(num_objects):
        if pos + 3 > len(data):
            break
        ioa = data[pos] | (data[pos+1] << 8) | (data[pos+2] << 16)
        pos += 3
        
        # Decode value based on type ID
        value = 0.0
        quality = 0x00
        
        if type_id == TypeID.M_SP_NA_1 and pos < len(data):
            quality = data[pos] & 0xF0
            value = float(data[pos] & 0x01)
            pos += 1
            
        elif type_id == TypeID.M_ME_NC_1 and pos + 4 < len(data):
            value = struct.unpack('<f', data[pos:pos+4])[0]
            quality = data[pos+4]
            pos += 5
        
        obj = ObjectAddress(ioa, type_id, cause, value, quality)
        objects.append(obj)
    
    return ASDU(type_id, cause, originator, common_address, objects)

ASDU.decode_from_bytes = staticmethod(asdu_decode_from_bytes)
