"""
Circuit Breaker State Manager - Persistence for circuit breaker component state.

Manages circuit breaker state, transitions, and trigger history.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from .state_manager import StateManager
from .persistence_manager import PersistenceManager

logger = logging.getLogger(__name__)


class CircuitBreakerStateEnum(Enum):
    """Circuit breaker states."""
    NORMAL = "normal"
    WARNING = "warning"
    DERISK = "derisk"
    HALT = "halt"
    RECOVERY = "recovery"


@dataclass
class CircuitBreakerState:
    """Circuit breaker system state."""
    state: CircuitBreakerStateEnum = CircuitBreakerStateEnum.NORMAL
    transition_history: List[Dict[str, Any]] = field(default_factory=list)
    last_transition: Optional[datetime] = None
    trigger_reason: Optional[str] = None
    state_metadata: Dict[str, Any] = field(default_factory=dict)
    consecutive_failures: int = 0


class CircuitBreakerStateManager(StateManager[CircuitBreakerState]):
    """State manager for circuit breaker component."""
    
    def __init__(self, persistence_manager: PersistenceManager):
        super().__init__(persistence_manager, 'circuit_breaker')
    
    def serialize(self, state: CircuitBreakerState) -> Dict[str, Any]:
        return {
            'state': state.state.value,
            'transition_history': state.transition_history,
            'last_transition': state.last_transition.isoformat() if state.last_transition else None,
            'trigger_reason': state.trigger_reason,
            'state_metadata': state.state_metadata,
            'consecutive_failures': state.consecutive_failures
        }
    
    def deserialize(self, data: Dict[str, Any]) -> CircuitBreakerState:
        state = CircuitBreakerState()
        state.state = CircuitBreakerStateEnum(data.get('state', 'normal'))
        state.transition_history = data.get('transition_history', [])
        last_transition = data.get('last_transition')
        state.last_transition = datetime.fromisoformat(last_transition) if last_transition else None
        state.trigger_reason = data.get('trigger_reason')
        state.state_metadata = data.get('state_metadata', {})
        state.consecutive_failures = data.get('consecutive_failures', 0)
        return state
    
    def get_default_state(self) -> CircuitBreakerState:
        return CircuitBreakerState()
    
    def transition_to(self, new_state: CircuitBreakerStateEnum, reason: str) -> None:
        """Transition to a new state."""
        state = self.get_current()
        old_state = state.state
        
        # Record transition
        transition = {
            'from': old_state.value,
            'to': new_state.value,
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        }
        state.transition_history.append(transition)
        
        # Update state
        state.state = new_state
        state.last_transition = datetime.now()
        state.trigger_reason = reason
        state.last_update = datetime.now()
        
        self.set_current(state)
        self.save_current()
        
        logger.warning(f"Circuit breaker transition: {old_state.value} -> {new_state.value} ({reason})")
    
    def increment_failures(self) -> int:
        """Increment consecutive failure count."""
        state = self.get_current()
        state.consecutive_failures += 1
        state.last_update = datetime.now()
        self.set_current(state)
        self.save_current()
        return state.consecutive_failures
    
    def reset_failures(self) -> None:
        """Reset consecutive failure count."""
        state = self.get_current()
        state.consecutive_failures = 0
        state.last_update = datetime.now()
        self.set_current(state)
        self.save_current()
    
    def update_metadata(self, key: str, value: Any) -> None:
        """Update state metadata."""
        state = self.get_current()
        state.state_metadata[key] = value
        state.last_update = datetime.now()
        self.set_current(state)
        self.save_current()
    
    def is_halted(self) -> bool:
        """Check if circuit breaker is in halt state."""
        state = self.get_current()
        return state.state == CircuitBreakerStateEnum.HALT
    
    def can_trade(self) -> bool:
        """Check if trading is allowed."""
        state = self.get_current()
        return state.state in (CircuitBreakerStateEnum.NORMAL, CircuitBreakerStateEnum.RECOVERY)
