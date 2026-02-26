"""
SCADA Master Integration with Historian

Extends SCADA Master to automatically store measurements and alarms
in the TimescaleDB historian for historical analysis and reporting.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from scada_master import SCADAMaster, NodeConnection
from historians import TimescaleDBHistorian, MeasurementPoint

logger = logging.getLogger(__name__)


class SCADAMasterWithHistorian(SCADAMaster):
    """
    SCADA Master that integrates with TimescaleDB historian.
    
    Automatically stores all measurements and alarms for historical
    analysis, reporting, and trend analysis.
    """
    
    def __init__(self, historian: Optional[TimescaleDBHistorian] = None):
        """
        Initialize SCADA Master with historian.
        
        Args:
            historian: TimescaleDBHistorian instance (creates new if None)
        """
        super().__init__()
        
        self.historian = historian
        if self.historian is None:
            # Create historian in mock mode (no database required)
            self.historian = TimescaleDBHistorian(use_mock=True)
        
        self.historian_enabled = False
    
    async def start_with_historian(self):
        """
        Start SCADA Master with historian enabled.
        
        Connects historian and begins storing measurements.
        """
        try:
            # Connect historian
            connected = await self.historian.connect()
            if not connected:
                logger.error("Failed to connect historian")
                return
            
            self.historian_enabled = True
            logger.info("Historian enabled")
            
            # Start main polling loop
            await self.start()
            
        except Exception as e:
            logger.error(f"Failed to start with historian: {e}")
    
    async def stop(self):
        """Stop SCADA Master and historian."""
        await super().stop()
        
        if self.historian:
            await self.historian.disconnect()
            self.historian_enabled = False
    
    async def _poll_node(self, node_id: str, conn) -> bool:
        """
        Poll node and store measurements in historian.
        
        Overrides parent to add historian storage.
        """
        # Call parent polling logic
        success = await super()._poll_node(node_id, conn)
        
        # Store measurement if successful and historian enabled
        if success and self.historian_enabled:
            try:
                if conn:
                    measurement = MeasurementPoint(
                        time=datetime.utcnow(),
                        node_id=node_id,
                        voltage_kv=conn.voltage_kv,
                        current_a=conn.current_a,
                        power_mw=conn.power_mw,
                        frequency_hz=conn.frequency_hz,
                        breaker_closed=conn.breaker_closed
                    )
                    await self.historian.store_measurement(measurement)
            except Exception as e:
                logger.error(f"Failed to store measurement: {e}")
        
        return success
    
    def _check_alarms(self, conn):
        """
        Check for alarms and store in historian.
        
        Overrides parent to add alarm storage.
        """
        # Call parent alarm checking
        super()._check_alarms(conn)
        
        # Store alarms in historian
        if self.historian_enabled and conn:
            try:
                # Check voltage alarm
                if conn.voltage_kv is not None:
                    if conn.voltage_kv < 200 or conn.voltage_kv > 250:
                        asyncio.create_task(self.historian.store_alarm(
                            node_id=conn.node_id,
                            alarm_type='voltage',
                            alarm_value=conn.voltage_kv,
                            severity='high' if conn.voltage_kv < 190 or conn.voltage_kv > 260 else 'medium',
                            description=f'Voltage out of range: {conn.voltage_kv:.2f} kV'
                        ))
                
                # Check frequency alarm
                if conn.frequency_hz is not None:
                    if conn.frequency_hz < 49.5 or conn.frequency_hz > 50.5:
                        asyncio.create_task(self.historian.store_alarm(
                            node_id=conn.node_id,
                            alarm_type='frequency',
                            alarm_value=conn.frequency_hz,
                            severity='high' if conn.frequency_hz < 49 or conn.frequency_hz > 51 else 'medium',
                            description=f'Frequency out of range: {conn.frequency_hz:.2f} Hz'
                        ))
            except Exception as e:
                logger.error(f"Failed to store alarms: {e}")
    
    async def get_measurement_history(self, 
                                     node_id: str,
                                     limit: int = 100) -> list:
        """
        Retrieve historical measurements for a node.
        
        Args:
            node_id: Node to query
            limit: Maximum measurements to return
            
        Returns:
            List of measurement points
        """
        if not self.historian_enabled:
            return []
        
        try:
            measurements = await self.historian.get_measurements(
                node_id=node_id,
                limit=limit
            )
            return [m.to_dict() for m in measurements]
        except Exception as e:
            logger.error(f"Failed to get measurement history: {e}")
            return []
    
    async def get_node_statistics(self, node_id: str) -> dict:
        """
        Get statistical summary for a node.
        
        Args:
            node_id: Node to analyze
            
        Returns:
            Dictionary with statistics
        """
        if not self.historian_enabled:
            return {}
        
        try:
            stats = await self.historian.get_node_stats(node_id)
            return stats
        except Exception as e:
            logger.error(f"Failed to get node statistics: {e}")
            return {}
    
    async def get_aggregated_data(self,
                                 node_id: Optional[str] = None,
                                 bucket_interval: str = '1 hour') -> dict:
        """
        Get aggregated hourly or daily statistics.
        
        Args:
            node_id: Optional node filter
            bucket_interval: 'hourly' or 'daily'
            
        Returns:
            Dictionary with aggregated statistics
        """
        if not self.historian_enabled:
            return {}
        
        try:
            return await self.historian.get_aggregated_stats(
                node_id=node_id,
                bucket_interval='1 ' + bucket_interval.rstrip('y')
            )
        except Exception as e:
            logger.error(f"Failed to get aggregated data: {e}")
            return {}
    
    async def get_recent_alarms(self, 
                               node_id: Optional[str] = None,
                               limit: int = 100) -> list:
        """
        Retrieve recent alarms.
        
        Args:
            node_id: Optional node filter
            limit: Maximum alarms to return
            
        Returns:
            List of alarm events
        """
        if not self.historian_enabled:
            return []
        
        try:
            alarms = await self.historian.get_alarms(
                node_id=node_id,
                limit=limit
            )
            return alarms
        except Exception as e:
            logger.error(f"Failed to get recent alarms: {e}")
            return []
    
    def get_historian_stats(self) -> dict:
        """
        Get historian operational statistics.
        
        Returns:
            Dictionary with historian stats
        """
        if not self.historian:
            return {}
        
        return self.historian.get_stats()
