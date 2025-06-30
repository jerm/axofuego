import asyncio
import time
import logging
from typing import List, Dict, Optional
from .channel import Poofer
from ..gpio.interface import GPIOInterface, RealGPIO
from ..gpio.mock import MockGPIO
from ..config.config import Config

logger = logging.getLogger(__name__)


class PyroEngine:
    """Central fire control engine managing all poofers with safety controls."""
    
    def __init__(self, config: Config):
        self.config = config
        self._lock = asyncio.Lock()
        self._emergency_stop = False
        self._last_activity = time.time()
        
        # Initialize GPIO interface
        if config.gpio.mock_mode:
            self.gpio_interface = MockGPIO()
            logger.info("PyroEngine initialized with Mock GPIO")
        else:
            self.gpio_interface = RealGPIO()
            logger.info("PyroEngine initialized with Real GPIO")
        
        # Create poofers
        self.poofers: Dict[int, Poofer] = {}
        for i, pin in enumerate(config.gpio.pins, 1):  # 1-indexed like original
            poofer = Poofer(
                channel_id=i,
                gpio_pin=pin,
                gpio_interface=self.gpio_interface,
                max_duration=config.safety.max_fire_duration,
                hardware_delay=config.gpio.hardware_delay
            )
            self.poofers[i] = poofer
        
        logger.info(f"PyroEngine created {len(self.poofers)} poofers")
        
        # Safety monitor task
        self._safety_monitor_task: Optional[asyncio.Task] = None
    
    def start_safety_monitor(self) -> None:
        """Start the safety monitoring task."""
        if self._safety_monitor_task is None:
            self._safety_monitor_task = asyncio.create_task(self._safety_monitor())
            logger.info("Safety monitor started")
    
    async def fire_poofer(self, poofer_id: int, duration: Optional[float] = None) -> bool:
        """Fire a specific poofer."""
        if self._emergency_stop:
            logger.warning(f"Emergency stop active - ignoring fire command for poofer {poofer_id}")
            return False
        
        if poofer_id not in self.poofers:
            logger.error(f"Invalid poofer ID: {poofer_id}")
            return False
        
        async with self._lock:
            self._last_activity = time.time()
            success = self.poofers[poofer_id].fire(duration)
            
            if success:
                logger.info(f"Firing poofer {poofer_id} for {duration or self.config.safety.max_fire_duration}s")
            else:
                logger.warning(f"Failed to fire poofer {poofer_id} - already active")
            
            return success
    
    def stop_poofer(self, poofer_id: int) -> bool:
        """Stop a specific poofer."""
        if poofer_id not in self.poofers:
            logger.error(f"Invalid poofer ID: {poofer_id}")
            return False
        
        success = self.poofers[poofer_id].stop()
        if success:
            logger.info(f"Stopped poofer {poofer_id}")
        return success
    
    async def fire_multiple(self, poofer_ids: List[int], duration: Optional[float] = None) -> List[bool]:
        """Fire multiple poofers simultaneously."""
        if self._emergency_stop:
            logger.warning("Emergency stop active - ignoring fire command for multiple poofers")
            return [False] * len(poofer_ids)
        
        results = []
        async with self._lock:
            self._last_activity = time.time()
            for poofer_id in poofer_ids:
                if poofer_id in self.poofers:
                    success = self.poofers[poofer_id].fire(duration)
                    results.append(success)
                else:
                    logger.error(f"Invalid poofer ID: {poofer_id}")
                    results.append(False)
        
        active_count = sum(results)
        logger.info(f"Fired {active_count}/{len(poofer_ids)} poofers")
        return results
    
    def stop_all(self) -> None:
        """Stop all poofers immediately."""
        for poofer in self.poofers.values():
            poofer.stop()
        logger.warning("All poofers stopped")
    
    def emergency_stop(self) -> None:
        """Activate emergency stop - stops all poofers and prevents new firing."""
        self._emergency_stop = True
        self.stop_all()
        logger.critical("EMERGENCY STOP ACTIVATED")
    
    def reset_emergency_stop(self) -> None:
        """Reset emergency stop condition."""
        self._emergency_stop = False
        logger.info("Emergency stop reset")
    
    def is_emergency_stopped(self) -> bool:
        """Check if emergency stop is active."""
        return self._emergency_stop
    
    def get_poofer_status(self, poofer_id: int) -> Optional[Dict]:
        """Get status of a specific poofer."""
        if poofer_id not in self.poofers:
            return None
        
        poofer = self.poofers[poofer_id]
        return {
            'id': poofer_id,
            'active': poofer.is_active(),
            'time_remaining': poofer.get_time_remaining(),
            'gpio_pin': poofer.gpio_pin
        }
    
    def get_all_status(self) -> Dict:
        """Get status of all poofers and system."""
        poofer_statuses = {}
        active_count = 0
        
        for poofer_id, poofer in self.poofers.items():
            status = {
                'active': poofer.is_active(),
                'time_remaining': poofer.get_time_remaining(),
                'gpio_pin': poofer.gpio_pin
            }
            poofer_statuses[poofer_id] = status
            if status['active']:
                active_count += 1
        
        return {
            'poofers': poofer_statuses,
            'active_count': active_count,
            'total_count': len(self.poofers),
            'emergency_stop': self._emergency_stop,
            'last_activity': self._last_activity
        }
    
    async def _safety_monitor(self) -> None:
        """Safety monitoring coroutine."""
        while True:
            try:
                # Check for auto-shutoff timeout
                if (time.time() - self._last_activity) > self.config.safety.auto_shutoff_timeout:
                    if any(poofer.is_active() for poofer in self.poofers.values()):
                        logger.warning("Auto-shutoff timeout reached - stopping all poofers")
                        self.stop_all()
                
                await asyncio.sleep(1.0)  # Check every second
                
            except Exception as e:
                logger.error(f"Safety monitor error: {e}")
                await asyncio.sleep(5.0)
    
    def cleanup(self) -> None:
        """Cleanup all resources."""
        logger.info("PyroEngine cleanup started")
        self.stop_all()
        
        for poofer in self.poofers.values():
            poofer.cleanup()
        
        self.gpio_interface.cleanup()
        logger.info("PyroEngine cleanup completed")