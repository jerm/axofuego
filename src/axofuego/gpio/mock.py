import logging
from typing import Dict
from .interface import GPIOInterface

logger = logging.getLogger(__name__)


class MockGPIO(GPIOInterface):
    """Mock GPIO implementation for testing and development."""
    
    def __init__(self):
        self._pins: Dict[int, bool] = {}
        self._setup_pins: Dict[int, bool] = {}
        
    def setup_pin(self, pin: int, active_high: bool = True) -> None:
        """Setup a mock GPIO pin."""
        self._setup_pins[pin] = active_high
        self._pins[pin] = False
        logger.info(f"Mock GPIO: Setup pin {pin} (active_high={active_high})")
    
    def set_pin(self, pin: int, value: bool) -> None:
        """Set a mock GPIO pin value."""
        if pin not in self._setup_pins:
            raise ValueError(f"Pin {pin} not setup")
        
        self._pins[pin] = value
        state = "HIGH" if value else "LOW"
        logger.info(f"Mock GPIO: Pin {pin} set to {state}")
    
    def get_pin(self, pin: int) -> bool:
        """Get a mock GPIO pin value."""
        if pin not in self._setup_pins:
            raise ValueError(f"Pin {pin} not setup")
        
        return self._pins.get(pin, False)
    
    def cleanup(self) -> None:
        """Cleanup mock GPIO resources."""
        logger.info("Mock GPIO: Cleanup called")
        self._pins.clear()
        self._setup_pins.clear()
    
    def get_pin_states(self) -> Dict[int, bool]:
        """Get all pin states (useful for testing)."""
        return self._pins.copy()