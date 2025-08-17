import asyncio
import logging
from typing import Optional, Callable, Dict
from ..fire.engine import PyroEngine
from ..pattern.engine import PatternEngine

try:
    from evdev import InputDevice, categorize, ecodes, KeyEvent, list_devices
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False
    # Mock classes for when evdev is not available
    class InputDevice:
        pass
    class ecodes:
        EV_KEY = None
    class KeyEvent:
        key_down = None
        key_up = None

logger = logging.getLogger(__name__)


class KeypadHandler:
    """Handle keypad input for fire control."""
    
    def __init__(self, pyro_engine: PyroEngine, pattern_engine: PatternEngine):
        self.pyro_engine = pyro_engine
        self.pattern_engine = pattern_engine
        
        # Key mapping from original burninate.py
        self.button_mapping = {
            "KEY_BACKSPACE": 1,
            "KEY_KPASTERISK": 2,
            "KEY_KP9": 3,
            "KEY_KP6": 4,
            "KEY_KP3": 5,
            "KEY_KPDOT": 6,
            "KEY_KP8": 7,
            "KEY_KP5": 7,  # Both KP8 and KP5 map to poofer 7
        }
        
        self._device: Optional[InputDevice] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        # Pattern control state
        self._pattern_active = False
    
    def find_keyboard_device(self) -> Optional[InputDevice]:
        """Find the control keypad device."""
        if not EVDEV_AVAILABLE:
            return None
            
        devices = [InputDevice(path) for path in list_devices()]
        for device in devices:
            if device.name == 'CX 2.4G Wireless Receiver' and "input0" in device.phys:
                return device
        return None
    
    async def start(self) -> bool:
        """Start keypad monitoring."""
        self._device = self.find_keyboard_device()
        if not self._device:
            logger.error("Control Keypad Not Found")
            return False
        
        logger.info(f"Using input device: {self._device.path} ({self._device.name})")
        self._device.grab()
        
        self._running = True
        self._task = asyncio.create_task(self._read_keyboard())
        
        return True
    
    def stop(self) -> None:
        """Stop keypad monitoring."""
        self._running = False
        if self._task:
            self._task.cancel()
        
        if self._device:
            self._device.ungrab()
            self._device.close()
    
    async def _read_keyboard(self) -> None:
        """Read keyboard events asynchronously."""
        if not self._device:
            return
        
        try:
            async for event in self._device.async_read_loop():
                if not self._running:
                    break
                
                if event.type == ecodes.EV_KEY:
                    key_event = categorize(event)
                    keycode = key_event.keycode if isinstance(key_event.keycode, str) else key_event.keycode[0]
                    
                    if key_event.keystate == KeyEvent.key_down:
                        await self._on_key_press(keycode)
                    elif key_event.keystate == KeyEvent.key_up:
                        await self._on_key_release(keycode)
        
        except Exception as e:
            logger.error(f"Keyboard read error: {e}")
    
    async def _on_key_press(self, keycode: str) -> None:
        """Handle key press events."""
        logger.info(f"Key Pressed: {keycode}")
        
        # Individual poofer control
        if keycode in self.button_mapping:
            poofer_id = self.button_mapping[keycode]
            logger.warning(f"Firing poofer {poofer_id} from keycode {keycode}")
            await self.pyro_engine.fire_poofer(poofer_id)
            return
        
        # Special function keys
        if keycode == "KEY_ESC":
            logger.warning("Emergency stop - stopping all poofers")
            self.pyro_engine.emergency_stop()
            
        elif keycode == "KEY_KP0":
            logger.warning("Firing all poofers")
            await self.pyro_engine.fire_multiple(list(range(1, 8)))
            
        elif keycode == "KEY_KP7":
            logger.info("Starting automatic pattern")
            self._pattern_active = True
            # TODO: Start a predefined pattern
            
        elif keycode == "KEY_KP1":
            logger.info("Stopping automatic pattern")
            self._pattern_active = False
            self.pattern_engine.stop()
            
        else:
            logger.debug(f"UNKNOWN: key with code {keycode} was pressed")
    
    async def _on_key_release(self, keycode: str) -> None:
        """Handle key release events."""
        logger.info(f"Key Released: {keycode}")
        
        # Stop individual poofers on key release
        if keycode in self.button_mapping:
            poofer_id = self.button_mapping[keycode]
            self.pyro_engine.stop_poofer(poofer_id)
            return
        
        # Special function key releases
        if keycode == "KEY_ESC":
            logger.info("ESC released - resetting emergency stop")
            self.pyro_engine.reset_emergency_stop()
            
        elif keycode == "KEY_KP0":
            logger.warning("Stopping all poofers")
            self.pyro_engine.stop_all()
            
        elif keycode == "KEY_KP7":
            logger.info("Pattern key released - stopping pattern")
            self._pattern_active = False
            self.pattern_engine.stop()
            
        else:
            logger.debug(f"UNKNOWN key with code {keycode} was RELEASED")