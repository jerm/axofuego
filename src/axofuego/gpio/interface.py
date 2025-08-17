from abc import ABC, abstractmethod
from typing import List


class GPIOInterface(ABC):
    """Abstract interface for GPIO operations."""
    
    @abstractmethod
    def setup_pin(self, pin: int, active_high: bool = True) -> None:
        """Setup a GPIO pin for output."""
        pass
    
    @abstractmethod
    def set_pin(self, pin: int, value: bool) -> None:
        """Set a GPIO pin value."""
        pass
    
    @abstractmethod
    def get_pin(self, pin: int) -> bool:
        """Get a GPIO pin value."""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup GPIO resources."""
        pass


class RealGPIO(GPIOInterface):
    """Real GPIO implementation using gpiozero."""
    
    def __init__(self):
        self._devices = {}
        
    def setup_pin(self, pin: int, active_high: bool = True) -> None:
        """Setup a GPIO pin for output using gpiozero."""
        from gpiozero import DigitalOutputDevice
        
        if pin in self._devices:
            return
            
        self._devices[pin] = DigitalOutputDevice(
            pin=pin,
            active_high=active_high,
            initial_value=False
        )
    
    def set_pin(self, pin: int, value: bool) -> None:
        """Set a GPIO pin value."""
        if pin not in self._devices:
            raise ValueError(f"Pin {pin} not setup")
        
        device = self._devices[pin]
        if value:
            device.on()
        else:
            device.off()
    
    def get_pin(self, pin: int) -> bool:
        """Get a GPIO pin value."""
        if pin not in self._devices:
            raise ValueError(f"Pin {pin} not setup")
        
        return self._devices[pin].is_active
    
    def cleanup(self) -> None:
        """Cleanup GPIO resources."""
        for device in self._devices.values():
            device.close()
        self._devices.clear()