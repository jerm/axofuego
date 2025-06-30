import os
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class GPIOConfig:
    pins: List[int]
    mock_mode: bool
    active_high: bool
    hardware_delay: float


@dataclass
class SafetyConfig:
    max_fire_duration: float
    emergency_stop_pin: Optional[int]
    auto_shutoff_timeout: float


@dataclass
class WebConfig:
    host: str
    port: int
    static_path: str
    http_port: int


@dataclass
class PatternConfig:
    default_bpm: int
    min_bpm: int
    max_bpm: int
    tick_resolution: int


@dataclass
class LogConfig:
    level: str
    file_path: str
    max_size: int
    backup_count: int


@dataclass
class Config:
    gpio: GPIOConfig
    safety: SafetyConfig
    web: WebConfig
    pattern: PatternConfig
    log: LogConfig

    @classmethod
    def from_env(cls) -> 'Config':
        """Load configuration from environment variables with defaults."""
        
        # GPIO Configuration
        gpio_pins_str = _get_env_str('FIRE_GPIO_PINS', '17,22,27,4,23,24,25,9')
        gpio_pins = [int(pin.strip()) for pin in gpio_pins_str.split(',')]
        
        gpio = GPIOConfig(
            pins=gpio_pins,
            mock_mode=_get_env_bool('FIRE_GPIO_MOCK', False),
            active_high=_get_env_bool('FIRE_GPIO_ACTIVE_HIGH', False),
            hardware_delay=_get_env_float('FIRE_GPIO_HARDWARE_DELAY', 0.01)
        )
        
        # Safety Configuration
        safety = SafetyConfig(
            max_fire_duration=_get_env_float('FIRE_SAFETY_MAX_DURATION', 5.0),
            emergency_stop_pin=_get_env_int('FIRE_SAFETY_ESTOP_PIN', None),
            auto_shutoff_timeout=_get_env_float('FIRE_SAFETY_AUTO_SHUTOFF', 30.0)
        )
        
        # Web Configuration
        web = WebConfig(
            host=_get_env_str('FIRE_WEB_HOST', '0.0.0.0'),
            port=_get_env_int('FIRE_WEB_PORT', 8765),
            static_path=_get_env_str('FIRE_WEB_STATIC', 'html'),
            http_port=_get_env_int('FIRE_WEB_HTTP_PORT', 8080)
        )
        
        # Pattern Configuration
        pattern = PatternConfig(
            default_bpm=_get_env_int('FIRE_PATTERN_DEFAULT_BPM', 120),
            min_bpm=_get_env_int('FIRE_PATTERN_MIN_BPM', 60),
            max_bpm=_get_env_int('FIRE_PATTERN_MAX_BPM', 200),
            tick_resolution=_get_env_int('FIRE_PATTERN_TICK_RESOLUTION', 16)
        )
        
        # Log Configuration
        log = LogConfig(
            level=_get_env_str('FIRE_LOG_LEVEL', 'INFO'),
            file_path=_get_env_str('FIRE_LOG_FILE', 'burningator.log'),
            max_size=_get_env_int('FIRE_LOG_MAX_SIZE', 10 * 1024 * 1024),  # 10MB
            backup_count=_get_env_int('FIRE_LOG_BACKUP_COUNT', 5)
        )
        
        return cls(
            gpio=gpio,
            safety=safety,
            web=web,
            pattern=pattern,
            log=log
        )


def _get_env_str(key: str, default: str) -> str:
    """Get string environment variable with default."""
    return os.getenv(key, default)


def _get_env_int(key: str, default: Optional[int]) -> Optional[int]:
    """Get integer environment variable with default."""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_env_float(key: str, default: float) -> float:
    """Get float environment variable with default."""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_env_bool(key: str, default: bool) -> bool:
    """Get boolean environment variable with default."""
    value = os.getenv(key)
    if value is None:
        return default
    return value.lower() in ('true', '1', 'yes', 'on')