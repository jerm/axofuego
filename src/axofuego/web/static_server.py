import asyncio
import logging
import mimetypes
import os
from pathlib import Path
from typing import Optional
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

logger = logging.getLogger(__name__)


class StaticFileHandler(SimpleHTTPRequestHandler):
    """Custom handler for serving static files."""
    
    def __init__(self, *args, static_directory: str = None, **kwargs):
        self.static_directory = static_directory
        super().__init__(*args, **kwargs)
    
    def translate_path(self, path):
        """Translate URL path to filesystem path."""
        # Remove query parameters
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]
        
        # Convert to relative path
        if path.startswith('/'):
            path = path[1:]
        
        # If empty path, serve index.html
        if not path:
            path = 'index.html'
        
        # Join with static directory
        return os.path.join(self.static_directory, path)
    
    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.info(f"HTTP {format % args}")


class StaticServer:
    """Simple HTTP server for static files."""
    
    def __init__(self, static_dir: str, host: str = "0.0.0.0", port: int = 8080):
        self.static_dir = Path(static_dir).resolve()
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        
    def start(self) -> bool:
        """Start the static file server."""
        if not self.static_dir.exists():
            logger.error(f"Static directory does not exist: {self.static_dir}")
            return False
        
        try:
            # Create handler class with static directory
            handler_class = lambda *args, **kwargs: StaticFileHandler(
                *args, static_directory=str(self.static_dir), **kwargs
            )
            
            # Create server
            self.server = HTTPServer((self.host, self.port), handler_class)
            
            # Start in separate thread
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            
            logger.info(f"Static server started on http://{self.host}:{self.port}")
            logger.info(f"Serving files from: {self.static_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start static server: {e}")
            return False
    
    def stop(self) -> None:
        """Stop the static file server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("Static server stopped")
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)