"""
State Manager - Base class for component-specific state managers.

Provides a generic interface for serializing, deserializing, saving, and loading
component state with automatic persistence.
"""

from typing import Dict, Any, Optional, TypeVar, Generic, List
from datetime import datetime
import logging
from abc import ABC, abstractmethod

from .persistence_manager import PersistenceManager

logger = logging.getLogger(__name__)

T = TypeVar('T')


class StateManager(ABC, Generic[T]):
    """Base class for component-specific state managers."""
    
    def __init__(self, persistence_manager: PersistenceManager, state_type: str):
        self.persistence = persistence_manager
        self.state_type = state_type
        self._state: Optional[T] = None
        logger.info(f"StateManager initialized for {state_type}")
    
    @abstractmethod
    def serialize(self, state: T) -> Dict[str, Any]:
        """Serialize state to dictionary for persistence."""
        pass
    
    @abstractmethod
    def deserialize(self, data: Dict[str, Any]) -> T:
        """Deserialize dictionary to state object."""
        pass
    
    @abstractmethod
    def get_default_state(self) -> T:
        """Get default state when no persisted state exists."""
        pass
    
    def save(self, state: T) -> bool:
        """Save state to persistent storage."""
        return self.persistence.save_state(self.state_type, self.serialize(state))
    
    def load(self) -> Optional[T]:
        """Load state from persistent storage."""
        data = self.persistence.load_state(self.state_type)
        if data is None:
            return self.get_default_state()
        try:
            return self.deserialize(data)
        except Exception as e:
            logger.error(f"Failed to deserialize {self.state_type}: {e}")
            return self.get_default_state()
    
    def save_current(self) -> bool:
        """Save current in-memory state."""
        if self._state is None:
            return False
        return self.save(self._state)
    
    def load_current(self) -> Optional[T]:
        """Load state into memory."""
        state = self.load()
        if state is not None:
            self._state = state
        return self._state
    
    def get_current(self) -> T:
        """Get current state (load from disk if not in memory)."""
        if self._state is None:
            self._state = self.load()
        return self._state
    
    def set_current(self, state: T) -> None:
        """Set current in-memory state."""
        self._state = state
    
    def update_and_save(self, **kwargs) -> T:
        """Update current state with provided fields and save."""
        state = self.get_current()
        if hasattr(state, '__dataclass_fields__'):
            # Dataclass
            from dataclasses import replace
            state = replace(state, **kwargs)
        else:
            # Regular object
            for key, value in kwargs.items():
                setattr(state, key, value)
        self.set_current(state)
        self.save_current()
        return state
