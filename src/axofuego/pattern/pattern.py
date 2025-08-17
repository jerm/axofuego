from typing import Dict, List, Set
from dataclasses import dataclass, field


@dataclass
class FireEvent:
    """Represents a single fire event in a pattern."""
    poofer_id: int
    tick: int
    duration: float = 0.2
    velocity: float = 1.0  # Velocity multiplier for duration


@dataclass 
class Pattern:
    """Represents a fire pattern with events across multiple poofers."""
    name: str
    events: List[FireEvent] = field(default_factory=list)
    length_ticks: int = 0
    loop: bool = True
    
    def add_event(self, poofer_id: int, tick: int, duration: float = 0.2, velocity: float = 1.0) -> None:
        """Add a fire event to the pattern."""
        event = FireEvent(poofer_id=poofer_id, tick=tick, duration=duration, velocity=velocity)
        self.events.append(event)
        self.length_ticks = max(self.length_ticks, tick + 1)
    
    def remove_event(self, poofer_id: int, tick: int) -> bool:
        """Remove a fire event from the pattern."""
        for i, event in enumerate(self.events):
            if event.poofer_id == poofer_id and event.tick == tick:
                del self.events[i]
                return True
        return False
    
    def get_events_at_tick(self, tick: int) -> List[FireEvent]:
        """Get all events that should fire at a specific tick."""
        return [event for event in self.events if event.tick == tick]
    
    def get_active_poofers(self) -> Set[int]:
        """Get set of all poofer IDs used in this pattern."""
        return {event.poofer_id for event in self.events}
    
    def get_ticks_with_events(self) -> Set[int]:
        """Get set of all ticks that have events."""
        return {event.tick for event in self.events}
    
    def clone(self) -> 'Pattern':
        """Create a copy of this pattern."""
        cloned = Pattern(name=f"{self.name}_copy", length_ticks=self.length_ticks, loop=self.loop)
        cloned.events = [
            FireEvent(
                poofer_id=event.poofer_id,
                tick=event.tick,
                duration=event.duration,
                velocity=event.velocity
            )
            for event in self.events
        ]
        return cloned
    
    def to_dict(self) -> Dict:
        """Convert pattern to dictionary for serialization."""
        return {
            'name': self.name,
            'length_ticks': self.length_ticks,
            'loop': self.loop,
            'events': [
                {
                    'poofer_id': event.poofer_id,
                    'tick': event.tick,
                    'duration': event.duration,
                    'velocity': event.velocity
                }
                for event in self.events
            ]
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Pattern':
        """Create pattern from dictionary."""
        pattern = cls(
            name=data['name'],
            length_ticks=data.get('length_ticks', 0),
            loop=data.get('loop', True)
        )
        
        for event_data in data.get('events', []):
            pattern.add_event(
                poofer_id=event_data['poofer_id'],
                tick=event_data['tick'],
                duration=event_data.get('duration', 0.2),
                velocity=event_data.get('velocity', 1.0)
            )
        
        return pattern