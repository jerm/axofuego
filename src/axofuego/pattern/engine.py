import asyncio
import time
import logging
from typing import Dict, Optional, Callable
from .pattern import Pattern
from ..fire.engine import PyroEngine
from ..config.config import Config

logger = logging.getLogger(__name__)


class PatternEngine:
    """Engine for playing beat-synchronized fire patterns."""
    
    def __init__(self, config: Config, pyro_engine: PyroEngine):
        self.config = config
        self.pyro_engine = pyro_engine
        
        self._bpm = config.pattern.default_bpm
        self._tick_resolution = config.pattern.tick_resolution  # Ticks per beat (16th notes)
        
        self._current_pattern: Optional[Pattern] = None
        self._playing = False
        self._current_tick = 0
        self._pattern_loop_count = 0
        
        self._playback_task: Optional[asyncio.Task] = None
        
        # Callback for pattern events
        self._on_pattern_event: Optional[Callable] = None
        
        logger.info(f"PatternEngine initialized - BPM: {self._bpm}, Resolution: {self._tick_resolution}")
    
    @property
    def bpm(self) -> int:
        """Current BPM setting."""
        return self._bpm
    
    @bpm.setter
    def bpm(self, value: int) -> None:
        """Set BPM with bounds checking."""
        value = max(self.config.pattern.min_bpm, min(self.config.pattern.max_bpm, value))
        if value != self._bpm:
            self._bpm = value
            logger.info(f"BPM changed to {self._bpm}")
    
    @property
    def is_playing(self) -> bool:
        """Check if a pattern is currently playing."""
        return self._playing
    
    @property
    def current_pattern(self) -> Optional[Pattern]:
        """Get the currently loaded pattern."""
        return self._current_pattern
    
    @property
    def current_tick(self) -> int:
        """Get the current playback tick."""
        return self._current_tick
    
    def load_pattern(self, pattern: Pattern) -> None:
        """Load a pattern for playback."""
        if self._playing:
            self.stop()
        
        self._current_pattern = pattern
        self._current_tick = 0
        self._pattern_loop_count = 0
        logger.info(f"Loaded pattern: {pattern.name} ({len(pattern.events)} events)")
    
    async def play(self, pattern: Optional[Pattern] = None) -> bool:
        """Start playing a pattern."""
        if pattern:
            self.load_pattern(pattern)
        
        if not self._current_pattern:
            logger.error("No pattern loaded")
            return False
        
        if self._playing:
            logger.warning("Pattern already playing")
            return False
        
        self._playing = True
        
        self._playback_task = asyncio.create_task(self._playback_loop())
        
        logger.info(f"Started playing pattern: {self._current_pattern.name}")
        return True
    
    def stop(self) -> None:
        """Stop pattern playback."""
        if not self._playing:
            return
        
        self._playing = False
        
        if self._playback_task and not self._playback_task.done():
            self._playback_task.cancel()
        
        # Stop any active poofers
        self.pyro_engine.stop_all()
        
        logger.info("Pattern playback stopped")
    
    def pause(self) -> None:
        """Pause pattern playback (can be resumed)."""
        if self._playing:
            self._playing = False
            logger.info("Pattern playback paused")
    
    def resume(self) -> None:
        """Resume paused pattern playback."""
        if not self._playing and self._current_pattern:
            self.play()
            logger.info("Pattern playback resumed")
    
    def set_tick(self, tick: int) -> None:
        """Set the current playback position."""
        if self._current_pattern:
            self._current_tick = max(0, min(tick, self._current_pattern.length_ticks - 1))
            logger.info(f"Playback position set to tick {self._current_tick}")
    
    def get_status(self) -> Dict:
        """Get current pattern engine status."""
        return {
            'playing': self._playing,
            'bpm': self._bpm,
            'current_tick': self._current_tick,
            'pattern_name': self._current_pattern.name if self._current_pattern else None,
            'pattern_length': self._current_pattern.length_ticks if self._current_pattern else 0,
            'loop_count': self._pattern_loop_count,
            'tick_resolution': self._tick_resolution
        }
    
    def set_event_callback(self, callback: Callable) -> None:
        """Set callback function for pattern events."""
        self._on_pattern_event = callback
    
    async def _playback_loop(self) -> None:
        """Main playback loop running in separate thread."""
        if not self._current_pattern:
            return
        
        # Calculate timing
        beats_per_second = self._bpm / 60.0
        ticks_per_second = beats_per_second * self._tick_resolution
        tick_duration = 1.0 / ticks_per_second
        
        logger.info(f"Playback timing: {tick_duration:.4f}s per tick")
        
        start_time = time.time()
        
        while self._playing and not self._stop_event.is_set():
            try:
                # Calculate current tick based on elapsed time
                elapsed = time.time() - start_time
                calculated_tick = int(elapsed * ticks_per_second)
                
                # Process any missed ticks
                while self._current_tick <= calculated_tick and self._playing:
                    await self._process_tick(self._current_tick)
                    self._current_tick += 1
                    
                    # Handle pattern looping
                    if self._current_tick >= self._current_pattern.length_ticks:
                        if self._current_pattern.loop:
                            self._current_tick = 0
                            self._pattern_loop_count += 1
                            start_time = time.time()  # Reset timing
                            logger.debug(f"Pattern loop {self._pattern_loop_count}")
                        else:
                            logger.info("Pattern completed (no loop)")
                            self._playing = False
                            break
                
                # Sleep until next tick
                next_tick_time = start_time + (self._current_tick * tick_duration)
                sleep_time = next_tick_time - time.time()
                if sleep_time > 0:
                    await asyncio.sleep(min(sleep_time, 0.01))  # Cap sleep to prevent long waits
                
            except Exception as e:
                logger.error(f"Playback loop error: {e}")
                self._playing = False
                break
        
        logger.info("Playback loop ended")
    
    async def _process_tick(self, tick: int) -> None:
        """Process events for a specific tick."""
        if not self._current_pattern:
            return
        
        events = self._current_pattern.get_events_at_tick(tick)
        if not events:
            return
        
        # Fire events
        for event in events:
            # Calculate actual duration based on velocity
            actual_duration = event.duration * event.velocity
            
            # Fire the poofer
            success = await self.pyro_engine.fire_poofer(event.poofer_id, actual_duration)
            
            if success:
                logger.debug(f"Tick {tick}: Fired poofer {event.poofer_id} for {actual_duration:.3f}s")
            
            # Call event callback if set
            if self._on_pattern_event:
                try:
                    self._on_pattern_event(tick, event, success)
                except Exception as e:
                    logger.error(f"Event callback error: {e}")
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("PatternEngine cleanup")
        self.stop()