"""
Kill Switch State Manager - Persistence for kill switch component state.

Manages kill switch trigger state, level, and history.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from .state_manager import StateManager
from .persistence_manager import PersistenceManager

logger = logging.getLogger(__name__)


class KillSwitchStateEnum(Enum):
    """Kill switch states."""
    NORMAL = "normal"
    PAUSE = "pause"
    DERISK = "derisk"
    HALT = "halt"
    EMERGENCY = "emergency"


@dataclass
class KillSwitchState:
    """Kill switch system state."""
    level: KillSwitchStateEnum = KillSwitchStateEnum.NORMAL
    is_triggered: bool = False
    trigger_reason: Optional[str] = None
    trigger_timestamp: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolved_timestamp: Optional[datetime] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class KillSwitchStateManager(StateManager[KillSwitchState]):
    """State manager for kill switch component."""
    
    def __init__(self, persistence_manager: PersistenceManager):
        super().__init__(persistence_manager, 'kill_switch')
    
    def serialize(self, state: KillSwitchState) -> Dict[str, Any]:
        return {
            'level': state.level.value,
            'is_triggered': state.is_triggered,
            'trigger_reason': state.trigger_reason,
            'trigger_timestamp': state.trigger_timestamp.isoformat() if state.trigger_timestamp else None,
            'resolved_by': state.resolved_by,
            'resolved_timestamp': state.resolved_timestamp.isoformat() if state.resolved_timestamp else None,
            'history': state.history,
            'metadata': state.metadata
        }
    
    def deserialize(self, data: Dict[str, Any]) -> KillSwitchState:
        state = KillSwitchState()
        state.level = KillSwitchStateEnum(data.get('level', 'normal'))
        state.is_triggered = data.get('is_triggered', False)
        state.trigger_reason = data.get('trigger_reason')
        trigger_ts = data.get('trigger_timestamp')
        state.trigger_timestamp = datetime.fromisoformat(trigger_ts) if trigger_ts else None
        state.resolved_by = data.get('resolved_by')
        resolved_ts = data.get('resolved_timestamp')
        state.resolved_timestamp = datetime.fromisoformat(resolved_ts) if resolved_ts else None
        state.history = data.get('history', [])
        state.metadata = data.get('metadata', {})
        return state
    
    def get_default_state(self) -> KillSwitchState:
        return KillSwitchState()
    
    def trigger(self, level: KillSwitchStateEnum, reason: str, triggered_by: str = "system") -> None:
        """Trigger the kill switch."""
        state = self.get_current()
        
        # Record in history
        event = {
            'action': 'trigger',
            'level': level.value,
            'reason': reason,
            'triggered_by': triggered_by,
            'timestamp': datetime.now().isoformat()
        }
        state.history.append(event)
        
        # Update state
        state.level = level
        state.is_triggered = True
        state.trigger_reason = reason
        state.trigger_timestamp = datetime.now()
        state.resolved_by = None
        state.resolved_timestamp = None
        
        self.set_current(state)
        self.save_current()
        
        logger.critical(f"KILL SWITCH TRIGGERED: {level.value} - {reason} (by {triggered_by})")
    
    def resolve(self, resolved_by: str = "operator") -> None:
        """Resolve/Reset the kill switch."""
        state = self.get_current()
        
        # Record in history
        event = {
            'action': 'resolve',
            'previous_level': state.level.value,
            'resolved_by': resolved_by,
            'timestamp': datetime.now().isoformat()
        }
        state.history.append(event)
        
        # Update state
        old_level = state.level
        state.level = KillSwitchStateEnum.NORMAL
        state.is_triggered = False
        state.resolved_by = resolved_by
        state.resolved_timestamp = datetime.now()
        state.trigger_reason = None
        
        self.set_current(state)
        self.save_current()
        
        logger.info(f"Kill switch resolved (was {old_level.value}) by {resolved_by}")
    
    def is_active(self) -> bool:
        """Check if kill switch is currently triggered."""
        state = self.get_current()
        return state.is_triggered
    
    def can_trade(self) -> bool:
        """Check if trading is allowed."""
        state = self.get_current()
        return not state.is_triggered or state.level == KillSwitchStateEnum.PAUSE
    
    def update_metadata(self, key: str, value: Any) -> None:
        """Update kill switch metadata."""
        state = self.get_current()
        state.metadata[key] = value
        state.last_update = datetime.now() if hasattr(state, 'last_update') else None
        self.set_current(state)
        self.save_current()
