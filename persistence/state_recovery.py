"""
State Recovery - Recover state on system startup.

Provides comprehensive state recovery after restarts, crashes, or failures.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from .persistence_manager import PersistenceManager
from .trading_state_manager import TradingStateManager
from .risk_state_manager import RiskStateManager
from .circuit_breaker_state_manager import CircuitBreakerStateManager
from .kill_switch_state_manager import KillSwitchStateManager

logger = logging.getLogger(__name__)


class RecoveryResult:
    """Result of state recovery operation."""
    
    def __init__(self):
        self.success: bool = True
        self.recovered_states: List[str] = []
        self.failed_states: List[str] = []
        self.errors: List[Dict[str, str]] = []
        self.timestamp: datetime = datetime.now()
        self.is_fresh_start: bool = False
    
    def summary(self) -> str:
        """Get recovery summary string."""
        status = "SUCCESS" if self.success else "PARTIAL" if self.recovered_states else "FAILED"
        return f"Recovery {status}: Recovered={len(self.recovered_states)}, Failed={len(self.failed_states)}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'success': self.success,
            'recovered_states': self.recovered_states,
            'failed_states': self.failed_states,
            'errors': self.errors,
            'timestamp': self.timestamp.isoformat(),
            'is_fresh_start': self.is_fresh_start
        }


class StateRecovery:
    """State recovery service for system startup."""
    
    def __init__(self, persistence_manager: PersistenceManager):
        self.persistence = persistence_manager
        self.trading = TradingStateManager(persistence_manager)
        self.risk = RiskStateManager(persistence_manager)
        self.circuit_breaker = CircuitBreakerStateManager(persistence_manager)
        self.kill_switch = KillSwitchStateManager(persistence_manager)
        logger.info("StateRecovery initialized")
    
    def recover_all(self) -> RecoveryResult:
        """Recover all persisted state."""
        result = RecoveryResult()
        logger.info("Starting full state recovery...")
        
        managers = [
            ('trading', self.trading),
            ('risk', self.risk),
            ('circuit_breaker', self.circuit_breaker),
            ('kill_switch', self.kill_switch),
        ]
        
        recovered_count = 0
        for state_type, manager in managers:
            try:
                # Check if state file exists
                state_data = self.persistence.load_state(state_type)
                if state_data is None:
                    logger.debug(f"No persisted state found for {state_type}")
                    manager.load()  # Load default
                else:
                    state = manager.load()
                    manager.set_current(state)
                    recovered_count += 1
                
                result.recovered_states.append(state_type)
                logger.info(f"Recovered {state_type} state")
                
            except Exception as e:
                result.failed_states.append(state_type)
                result.errors.append({'state': state_type, 'error': str(e)})
                result.success = False
                logger.error(f"Failed to recover {state_type}: {e}")
        
        if recovered_count == 0:
            result.is_fresh_start = True
            logger.info("Fresh start - no persisted state found")
        elif recovered_count < len(managers):
            logger.warning(f"Partial recovery: {recovered_count}/{len(managers)} states recovered")
        else:
            logger.info(f"Full recovery: {recovered_count}/{len(managers)} states recovered")
        
        logger.info(f"Recovery complete: {result.summary()}")
        return result
    
    def get_all_state(self) -> Dict[str, Any]:
        """Get all current state."""
        return {
            'trading': self._serialize_state(self.trading.get_current()),
            'risk': self._serialize_state(self.risk.get_current()),
            'circuit_breaker': self._serialize_state(self.circuit_breaker.get_current()),
            'kill_switch': self._serialize_state(self.kill_switch.get_current()),
        }
    
    def _serialize_state(self, state) -> Dict[str, Any]:
        """Serialize state object to dict."""
        if hasattr(state, '__dataclass_fields__'):
            from dataclasses import asdict
            return asdict(state)
        elif hasattr(state, '__dict__'):
            return state.__dict__
        else:
            return str(state)
    
    def validate_recovery(self) -> bool:
        """Validate recovered state consistency."""
        try:
            risk_state = self.risk.get_current()
            kill_switch_state = self.kill_switch.get_current()
            
            # Check consistency: if kill switch is triggered, risk should be halted
            if kill_switch_state.is_triggered and not risk_state.is_halted:
                logger.warning("State inconsistency: kill switch triggered but risk not halted")
                # Auto-correct
                risk_state.is_halted = True
                self.risk.save_current()
            
            return True
        except Exception as e:
            logger.error(f"Recovery validation failed: {e}")
            return False
    
    def force_reset(self, state_types: Optional[List[str]] = None) -> None:
        """Force reset specific or all states (emergency use only)."""
        if state_types is None:
            state_types = ['trading', 'risk', 'circuit_breaker', 'kill_switch']
        
        for state_type in state_types:
            try:
                self.persistence.delete_state(state_type)
                logger.warning(f"Force reset {state_type} state")
            except Exception as e:
                logger.error(f"Failed to reset {state_type}: {e}")
        
        logger.critical(f"Force reset completed for: {state_types}")
