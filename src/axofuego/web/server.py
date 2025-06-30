import asyncio
import logging
import json
import time
import websockets
from websockets.server import serve
from typing import Set, Optional
from ..fire.engine import PyroEngine
from ..pattern.engine import PatternEngine
from ..config.config import Config

logger = logging.getLogger(__name__)


class WebServer:
    """WebSocket server for fire control."""
    
    def __init__(self, config: Config, pyro_engine: PyroEngine, pattern_engine: PatternEngine):
        self.config = config
        self.pyro_engine = pyro_engine
        self.pattern_engine = pattern_engine
        
        self.connected_clients: Set = set()
        self._server: Optional[websockets.WebSocketServer] = None
        
        # Legacy endpoint mapping from original burninate.py
        self.stalks = {
            'right-outside': 1,
            'right-middle': 2,
            'right-inside': 3,
            'left-inside': 4,
            'left-middle': 5,
            'left-outside': 6,
            'tail': 7
        }
    
    async def start(self):
        """Start the WebSocket server."""
        self._server = await serve(
            self.handle_client,
            self.config.web.host,
            self.config.web.port
        )
        logger.info(f"WebSocket server started on {self.config.web.host}:{self.config.web.port}")
    
    async def stop(self):
        """Stop the WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("WebSocket server stopped")
    
    async def handle_client(self, websocket):
        """Handle client connections."""
        endpoint = websocket.path.split('/')[2] if len(websocket.path.split('/')) > 2 else ''
        logger.info(f"Client connected to endpoint: {endpoint}")
        
        if endpoint == 'cputemp':
            await self._handle_cputemp(websocket)
        elif endpoint == 'control':
            await self._handle_control(websocket)
        elif endpoint == 'status':
            await self._handle_status(websocket)
        elif endpoint == 'sequence1':
            await self._handle_sequence1(websocket)
        elif endpoint == 'sequence2':
            await self._handle_sequence2(websocket)
        elif endpoint == 'sequence3':
            await self._handle_sequence3(websocket)
        elif endpoint == 'all':
            await self._handle_all(websocket)
        elif endpoint in self.stalks:
            await self._handle_stalk(websocket, endpoint)
        else:
            await self._handle_generic(websocket)
    
    async def _handle_cputemp(self, websocket):
        """Handle CPU temperature monitoring."""
        self.connected_clients.add(websocket)
        try:
            # Start CPU temp monitoring task
            task = asyncio.create_task(self._cpu_temp_monitor(websocket))
            await websocket.wait_closed()
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.connected_clients.discard(websocket)
            if 'task' in locals():
                task.cancel()
    
    async def _cpu_temp_monitor(self, websocket):
        """Monitor and send CPU temperature."""
        while True:
            try:
                # Get CPU temperature (mock for now)
                cpu_temp = 45.0  # TODO: Implement actual CPU temp reading
                message = f"CPU Temperature: {cpu_temp:.1f} C"
                await websocket.send(message)
            except websockets.exceptions.ConnectionClosed:
                break
            except Exception as e:
                logger.error(f"CPU temp monitor error: {e}")
            
            await asyncio.sleep(10)
    
    async def _handle_status(self, websocket):
        """Handle real-time system status updates."""
        self.connected_clients.add(websocket)
        try:
            # Start status monitoring task
            task = asyncio.create_task(self._status_monitor(websocket))
            await websocket.wait_closed()
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.connected_clients.discard(websocket)
            if 'task' in locals():
                task.cancel()
    
    async def _status_monitor(self, websocket):
        """Monitor and send system status including GPIO states."""
        while True:
            try:
                # Get complete system status
                status = self.pyro_engine.get_all_status()
                status_message = json.dumps({
                    'type': 'status_update',
                    'timestamp': time.time(),
                    'poofers': status['poofers'],
                    'emergency_stop': status['emergency_stop'],
                    'pattern_status': {
                        'playing': self.pattern_engine.is_playing,
                        'current_pattern': self.pattern_engine.get_current_pattern_name(),
                        'bpm': self.pattern_engine.get_bpm()
                    }
                })
                await websocket.send(status_message)
            except websockets.exceptions.ConnectionClosed:
                break
            except Exception as e:
                logger.error(f"Status monitor error: {e}")
            
            await asyncio.sleep(0.1)  # Update 10x per second for responsive UI
    
    async def _handle_control(self, websocket):
        """Handle fire control commands via JSON messages."""
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    action = data.get('action')
                    target = data.get('target')
                    
                    if action == 'fire':
                        if target == 'all':
                            await self.pyro_engine.fire_multiple(list(range(1, 8)))
                            await websocket.send(json.dumps({'status': 'firing', 'target': 'all'}))
                        elif target in self.stalks:
                            poofer_id = self.stalks[target]
                            success = await self.pyro_engine.fire_poofer(poofer_id)
                            await websocket.send(json.dumps({'status': 'firing' if success else 'failed', 'target': target}))
                        elif target.startswith('sequence'):
                            await websocket.send(json.dumps({'status': 'sequence_started', 'target': target}))
                            if target == 'sequence1':
                                await self._fire_pattern_sequence1()
                            elif target == 'sequence2':
                                await self._fire_pattern_sequence2()
                            elif target == 'sequence3':
                                await self._fire_pattern_sequence3()
                            await websocket.send(json.dumps({'status': 'sequence_complete', 'target': target}))
                    
                    elif action == 'stop':
                        if target == 'all':
                            self.pyro_engine.stop_all()
                            await websocket.send(json.dumps({'status': 'stopped', 'target': 'all'}))
                        elif target in self.stalks:
                            poofer_id = self.stalks[target]
                            self.pyro_engine.stop_poofer(poofer_id)
                            await websocket.send(json.dumps({'status': 'stopped', 'target': target}))
                    
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received: {message}")
                    try:
                        await websocket.send(json.dumps({'error': 'Invalid JSON'}))
                    except:
                        pass
                except Exception as e:
                    logger.error(f"Control message error: {e}")
                    try:
                        await websocket.send(json.dumps({'error': str(e)}))
                    except:
                        pass
        except websockets.exceptions.ConnectionClosed:
            logger.info("Control WebSocket connection closed")
            # Stop all poofers when control connection is lost
            self.pyro_engine.stop_all()
        except Exception as e:
            logger.error(f"Control WebSocket error: {e}")
            # Stop all poofers on any error
            self.pyro_engine.stop_all()
    
    async def _handle_sequence1(self, websocket):
        """Handle sequence1 pattern (legacy)."""
        try:
            while True:
                # Fire pattern similar to original sequence1
                await self._fire_pattern_sequence1()
                await asyncio.sleep(0.1)  # Brief pause
        except websockets.exceptions.ConnectionClosed:
            pass
    
    async def _fire_pattern_sequence1(self):
        """Fire the sequence1 pattern."""
        # Original: [1,3,5] for .375s, 3 reps and [2,4,6] for .250s, 5 reps
        tasks = []
        tasks.append(self._ignition_timer([1, 3, 5], 0.375, 3))
        tasks.append(self._ignition_timer([2, 4, 6], 0.250, 5))
        await asyncio.gather(*tasks)
    
    async def _handle_sequence2(self, websocket):
        """Handle sequence2 pattern (legacy)."""
        try:
            while True:
                await self._fire_pattern_sequence2()
                await asyncio.sleep(0.1)
        except websockets.exceptions.ConnectionClosed:
            pass
    
    async def _fire_pattern_sequence2(self):
        """Fire the sequence2 pattern."""
        # Sequential firing pattern
        delays = [0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8]
        poofers = [1, 2, 3, 4, 5, 6, 5, 4, 3, 2]
        
        tasks = []
        for poofer, delay in zip(poofers, delays):
            tasks.append(self._ignition_timer([poofer], 0.2, 1, delay))
        
        await asyncio.gather(*tasks)
    
    async def _handle_sequence3(self, websocket):
        """Handle sequence3 pattern (legacy)."""
        try:
            while True:
                await self._fire_pattern_sequence3()
                await asyncio.sleep(0.1)
        except websockets.exceptions.ConnectionClosed:
            pass
    
    async def _fire_pattern_sequence3(self):
        """Fire the sequence3 pattern."""
        # Synchronized pattern with different start delays
        tasks = []
        tasks.append(self._ignition_timer([1, 6], 0.2, 1, 0.0))
        tasks.append(self._ignition_timer([2, 5], 0.2, 1, 0.5))
        tasks.append(self._ignition_timer([3, 4], 0.2, 1, 1.0))
        tasks.append(self._ignition_timer([7], 0.2, 1, 1.5))
        await asyncio.gather(*tasks)
    
    async def _handle_all(self, websocket):
        """Handle 'all' endpoint - fire all poofers."""
        try:
            # Fire all poofers
            await self.pyro_engine.fire_multiple(list(range(1, 8)))
            
            # Keep connection alive
            async for message in websocket:
                await websocket.send(message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            # Emergency stop all poofers
            self.pyro_engine.stop_all()
    
    async def _handle_stalk(self, websocket, stalk_name):
        """Handle individual stalk firing."""
        poofer_id = self.stalks[stalk_name]
        
        try:
            logger.info(f"Firing stalk {stalk_name} (poofer {poofer_id})")
            await self.pyro_engine.fire_poofer(poofer_id)
            
            # Keep connection alive
            async for message in websocket:
                await websocket.send(message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            # Stop the specific poofer
            self.pyro_engine.stop_poofer(poofer_id)
            logger.info(f"Stopped stalk {stalk_name}")
    
    async def _handle_generic(self, websocket):
        """Handle generic connections."""
        try:
            async for message in websocket:
                # Echo back for now
                await websocket.send(f"Echo: {message}")
        except websockets.exceptions.ConnectionClosed:
            pass
    
    async def _ignition_timer(self, poofers, duration, repetitions=1, start_delay=0):
        """Fire specific poofers with timing (legacy compatibility)."""
        if start_delay > 0:
            await asyncio.sleep(start_delay)
        
        for rep in range(repetitions):
            # Fire all poofers in the list
            await self.pyro_engine.fire_multiple(poofers, duration)
            
            # Wait for duration
            await asyncio.sleep(duration)
            
            # Stop all poofers (they should auto-stop but ensure)
            for poofer_id in poofers:
                self.pyro_engine.stop_poofer(poofer_id)
            
            # Inter-repetition delay
            if rep < repetitions - 1:
                await asyncio.sleep(duration)