import time
import threading
from typing import Optional
from ..gpio.interface import GPIOInterface


class Poofer:
    """Represents a single fire output channel (poofer)."""
    
    def __init__(self, channel_id: int, gpio_pin: int, gpio_interface: GPIOInterface, 
                 max_duration: float = 5.0, hardware_delay: float = 0.01):
        self.channel_id = channel_id
        self.gpio_pin = gpio_pin
        self.gpio_interface = gpio_interface
        self.max_duration = max_duration
        self.hardware_delay = hardware_delay
        
        self._lock = threading.Lock()
        self._is_active = False
        self._end_time: Optional[float] = None
        self._timer: Optional[threading.Timer] = None
        
        # Setup GPIO pin
        self.gpio_interface.setup_pin(gpio_pin, active_high=False)  # Active low for cheap relays
    
    def is_active(self) -> bool:
        """Check if the poofer is currently active."""
        with self._lock:
            if self._is_active and self._end_time:
                if time.time() >= self._end_time:
                    self._stop_fire()
            return self._is_active
    
    def get_time_remaining(self) -> float:
        """Get remaining fire time in seconds."""
        with self._lock:
            if not self._is_active or not self._end_time:
                return 0.0
            
            remaining = self._end_time - time.time()
            return max(0.0, remaining)
    
    def fire(self, duration: Optional[float] = None) -> bool:
        """Start firing the poofer for the specified duration."""
        if duration is None:
            duration = self.max_duration
        
        # Clamp duration to maximum
        duration = min(duration, self.max_duration)
        
        with self._lock:
            if self._is_active:
                return False  # Already firing
            
            self._is_active = True
            self._end_time = time.time() + duration
            
            # Cancel any existing timer
            if self._timer:
                self._timer.cancel()
            
            # Set GPIO pin
            self.gpio_interface.set_pin(self.gpio_pin, True)
            
            # Set timer to stop fire
            self._timer = threading.Timer(duration, self._stop_fire)
            self._timer.start()
            
            return True
    
    def stop(self) -> bool:
        """Stop firing the poofer immediately."""
        with self._lock:
            if not self._is_active:
                return False
            
            self._stop_fire()
            return True
    
    def _stop_fire(self) -> None:
        """Internal method to stop fire (assumes lock is held or called from timer)."""
        if not self._is_active:
            return
            
        self._is_active = False
        self._end_time = None
        
        # Cancel timer if it exists
        if self._timer:
            self._timer.cancel()
            self._timer = None
        
        # Stop GPIO pin
        self.gpio_interface.set_pin(self.gpio_pin, False)
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        self.stop()
    
    def __repr__(self) -> str:
        return f"Poofer(id={self.channel_id}, pin={self.gpio_pin}, active={self.is_active()})"