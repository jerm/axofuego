#!/usr/bin/env python3

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from axofuego.config import Config
from axofuego.fire import PyroEngine
from axofuego.pattern import PatternEngine
from axofuego.web import WebServer, StaticServer
from axofuego.input import KeypadHandler

logger = logging.getLogger(__name__)


class AxofuegoApp:
    """Main Axofuego application."""
    
    def __init__(self):
        self.config = Config.from_env()
        self.pyro_engine = PyroEngine(self.config)
        self.pattern_engine = PatternEngine(self.config, self.pyro_engine)
        self.web_server = WebServer(self.config, self.pyro_engine, self.pattern_engine)
        self.static_server = StaticServer(
            static_dir=self.config.web.static_path,
            host=self.config.web.host,
            port=self.config.web.http_port
        )
        self.keypad_handler = KeypadHandler(self.pyro_engine, self.pattern_engine)
        
        self._shutdown_event = asyncio.Event()
        
    async def start(self):
        """Start all application components."""
        logger.info("Starting Axofuego Fire Control System")
        
        # Start safety monitor
        self.pyro_engine.start_safety_monitor()
        
        # Start web servers
        await self.web_server.start()
        
        # Start static file server
        static_started = self.static_server.start()
        if static_started:
            logger.info(f"Web UI available at http://{self.config.web.host}:{self.config.web.http_port}")
        else:
            logger.warning("Static file server failed to start")
        
        # Start keypad (if available - skip on non-Pi systems)
        try:
            import evdev
            keypad_started = await self.keypad_handler.start()
            if keypad_started:
                logger.info("Keypad input enabled")
            else:
                logger.info("Keypad not available - continuing without keypad")
        except ImportError:
            logger.info("evdev not available - skipping keypad (normal on non-Pi systems)")
        except Exception as e:
            logger.warning(f"Could not start keypad: {e}")
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        logger.info("Axofuego started successfully")
        
        # Wait for shutdown
        await self._shutdown_event.wait()
        
    async def shutdown(self):
        """Shutdown all application components."""
        logger.info("Shutting down Axofuego")
        
        # Stop pattern playback
        self.pattern_engine.stop()
        
        # Stop web servers
        await self.web_server.stop()
        self.static_server.stop()
        
        # Stop keypad
        try:
            self.keypad_handler.stop()
        except Exception as e:
            logger.warning(f"Error stopping keypad: {e}")
        
        # Stop all poofers
        self.pyro_engine.stop_all()
        
        # Cleanup resources
        self.pyro_engine.cleanup()
        self.pattern_engine.cleanup()
        
        logger.info("Axofuego shutdown complete")
        
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            signal_name = 'SIGINT' if signum == signal.SIGINT else 'SIGTERM' if signum == signal.SIGTERM else f'SIGNAL-{signum}'
            logger.info(f"Received shutdown signal: {signal_name}")
            self._shutdown_event.set()
        
        # Handle SIGINT and SIGTERM
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, signal_handler)


async def main():
    """Main entry point."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('burningator.log'),
            logging.StreamHandler()
        ]
    )
    
    app = AxofuegoApp()
    
    try:
        await app.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        import traceback
        logger.error(f"Application error: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        raise  # Re-raise to see the full error
    finally:
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())