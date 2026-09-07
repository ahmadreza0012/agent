"""
Phase 15: Stateful Circuit Breaker
==================================
Deterministic state machine for trading circuit breaker with persistence.
State transitions: NORMAL → WARNING → DERISK → HALT → RECOVERY → NORMAL

Features:
- Deterministic state transitions
- Persistent state across restarts
- Integration with Risk Engine
- Manual override support
- State history tracking
"""

from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
import json
import os
import logging

logger = logging.getLogger(__name__)


class BreakerState(Enum):
    """Circuit breaker states."""
    NORMAL = "normal"
    WARNING = "warning"
    DERISK = "derisk"
    HALT = "halt"
    RECOVERY = "recovery"
    
    @property
    def multiplier(self) -> float:
        """Get position multiplier for this state."""
        return {
            BreakerState.NORMAL: 1.0,
            BreakerState.WARNING: 0.7,
            BreakerState.DERISK: 0.4,
            BreakerState.HALT: 0.0,
            BreakerState.RECOVERY: 0.5,
        }[self]
    
    @property
    def can_trade(self) -> bool:
        """Check if trading is allowed in this state."""
        return self != BreakerState.HALT
    
    @property
    def is_risk_reduced(self) -> bool:
        """Check if risk is reduced in this state."""
        return self in [BreakerState.WARNING, BreakerState.DERISK, BreakerState.RECOVERY]


@dataclass
class StateTransition:
    """Record of a state transition."""
    timestamp: datetime
    from_state: BreakerState
    to_state: BreakerState
    reason: str
    drawdown: float
    daily_pnl: float
    consecutive_losses: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'from_state': self.from_state.value,
            'to_state': self.to_state.value,
            'reason': self.reason,
            'drawdown': self.drawdown,
            'daily_pnl': self.daily_pnl,
            'consecutive_losses': self.consecutive_losses,
        }


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    
    # Thresholds for state transitions
    warning_drawdown: float = 0.05        # 5% drawdown triggers WARNING
    derisk_drawdown: float = 0.08         # 8% drawdown triggers DERISK
    halt_drawdown: float = 0.12           # 12% drawdown triggers HALT
    recovery_drawdown: float = 0.05       # 5% recovery from peak triggers RECOVERY
    normal_drawdown: float = 0.02         # 2% drawdown returns to NORMAL
    
    # Daily loss thresholds
    warning_daily_loss: float = 0.015     # 1.5% daily loss triggers WARNING
    derisk_daily_loss: float = 0.020      # 2.0% daily loss triggers DERISK
    halt_daily_loss: float = 0.030        # 3.0% daily loss triggers HALT
    recovery_daily_loss: float = 0.010    # 1.0% daily loss recovery
    normal_daily_loss: float = 0.005      # 0.5% daily loss returns to NORMAL
    
    # Consecutive losses
    warning_losses: int = 3               # 3 consecutive losses triggers WARNING
    derisk_losses: int = 5                # 5 consecutive losses triggers DERISK
    halt_losses: int = 8                  # 8 consecutive losses triggers HALT
    recovery_losses: int = 2              # 2 consecutive wins triggers RECOVERY
    normal_wins: int = 5                  # 5 consecutive wins returns to NORMAL
    
    # Minimum time in state (hours)
    min_time_warning: float = 1.0
    min_time_derisk: float = 2.0
    min_time_halt: float = 24.0           # Minimum 24 hours in HALT
    min_time_recovery: float = 6.0
    
    # Manual override flags
    allow_manual_override: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {k: v for k, v in self.__dict__.items()}


class CircuitBreaker:
    """
    Stateful circuit breaker for trading system.
    
    Features:
    - Deterministic state transitions based on metrics
    - Persistent state across restarts
    - Integration with Risk Engine
    - Manual override for emergencies
    - State history tracking
    
    Usage:
        cb = CircuitBreaker()
        state = cb.update(drawdown=-0.06, daily_pnl=-0.02, win=False)
        if cb.can_trade():
            # Execute trades
            pass
    """
    
    def __init__(
        self,
        config: Optional[CircuitBreakerConfig] = None,
        persistence_path: Optional[str] = None,
        initial_state: BreakerState = BreakerState.NORMAL,
    ):
        """
        Initialize circuit breaker.
        
        Args:
            config: Circuit breaker configuration
            persistence_path: Path to persist state
            initial_state: Initial state (default: NORMAL)
        """
        self.config = config or CircuitBreakerConfig()
        self.persistence_path = persistence_path or '/workspace/data/circuit_breaker_state.json'
        self._state = initial_state
        self._last_update: Optional[datetime] = None
        self._state_enter_time: Optional[datetime] = None
        self._transitions: List[StateTransition] = []
        self._metrics_history: List[Dict[str, Any]] = []
        
        # Load persistent state
        self._load_state()
        
        # Initialize state enter time
        if self._state_enter_time is None:
            self._state_enter_time = datetime.now()
        
        logger.info(f"Circuit breaker initialized: state={self._state.value}, path={self.persistence_path}")
    
    def update(
        self,
        drawdown: float,
        daily_pnl: float,
        win: bool,
        timestamp: Optional[datetime] = None,
        force: bool = False,
    ) -> BreakerState:
        """
        Update circuit breaker state based on current metrics.
        
        Args:
            drawdown: Current drawdown (negative value, e.g., -0.06)
            daily_pnl: Daily PnL (negative for loss)
            win: Whether the last trade was profitable
            timestamp: Current timestamp
            force: Force update even if minimum time in state not met
            
        Returns:
            Updated BreakerState
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        self._last_update = timestamp
        previous_state = self._state
        
        # Record metrics
        self._metrics_history.append({
            'timestamp': timestamp.isoformat(),
            'drawdown': drawdown,
            'daily_pnl': daily_pnl,
            'win': win,
            'state': self._state.value,
        })
        # Keep only last 1000 records
        if len(self._metrics_history) > 1000:
            self._metrics_history = self._metrics_history[-1000:]
        
        # Check minimum time in state (unless forced)
        if not force and not self._min_time_elapsed(timestamp):
            return self._state
        
        # Determine next state based on current state and metrics
        next_state = self._determine_next_state(drawdown, daily_pnl, win)
        
        # Apply state transition if changed
        if next_state != self._state:
            reason = self._get_transition_reason(previous_state, next_state, drawdown, daily_pnl, win)
            self._transition_to(next_state, reason, drawdown, daily_pnl, win, timestamp)
        
        # Save persistent state
        self._save_state()
        
        return self._state
    
    def _determine_next_state(
        self,
        drawdown: float,
        daily_pnl: float,
        win: bool,
    ) -> BreakerState:
        """
        Determine next state based on metrics and current state.
        
        Returns:
            Next BreakerState
        """
        # Use absolute values for comparison (drawdown is negative)
        dd = abs(drawdown)
        
        # === HALT checks (highest priority) ===
        if dd >= self.config.halt_drawdown:
            return BreakerState.HALT
        if daily_pnl <= -self.config.halt_daily_loss:
            return BreakerState.HALT
        
        # If already in HALT, check recovery conditions
        if self._state == BreakerState.HALT:
            if dd < self.config.recovery_drawdown:
                return BreakerState.RECOVERY
            return BreakerState.HALT
        
        # === DERISK checks ===
        if dd >= self.config.derisk_drawdown:
            return BreakerState.DERISK
        if daily_pnl <= -self.config.derisk_daily_loss:
            return BreakerState.DERISK
        
        # If already in DERISK, check recovery
        if self._state == BreakerState.DERISK:
            if dd < self.config.warning_drawdown and daily_pnl > -self.config.warning_daily_loss:
                return BreakerState.WARNING
            return BreakerState.DERISK
        
        # === WARNING checks ===
        if dd >= self.config.warning_drawdown:
            return BreakerState.WARNING
        if daily_pnl <= -self.config.warning_daily_loss:
            return BreakerState.WARNING
        
        # If already in WARNING, check recovery
        if self._state == BreakerState.WARNING:
            if dd < self.config.normal_drawdown and daily_pnl > -self.config.normal_daily_loss:
                return BreakerState.NORMAL
            return BreakerState.WARNING
        
        # === RECOVERY checks ===
        if self._state == BreakerState.RECOVERY:
            if dd < self.config.normal_drawdown and daily_pnl > -self.config.normal_daily_loss:
                return BreakerState.NORMAL
            return BreakerState.RECOVERY
        
        # Default: NORMAL
        return BreakerState.NORMAL
    
    def _get_transition_reason(
        self,
        from_state: BreakerState,
        to_state: BreakerState,
        drawdown: float,
        daily_pnl: float,
        win: bool,
    ) -> str:
        """Get human-readable reason for state transition."""
        dd = abs(drawdown)
        
        reasons = {
            (BreakerState.NORMAL, BreakerState.WARNING): f"Drawdown {dd:.1%} > {self.config.warning_drawdown:.1%}",
            (BreakerState.WARNING, BreakerState.DERISK): f"Drawdown {dd:.1%} > {self.config.derisk_drawdown:.1%}",
            (BreakerState.DERISK, BreakerState.HALT): f"Drawdown {dd:.1%} > {self.config.halt_drawdown:.1%}",
            (BreakerState.HALT, BreakerState.RECOVERY): f"Recovery to {dd:.1%} < {self.config.recovery_drawdown:.1%}",
            (BreakerState.RECOVERY, BreakerState.NORMAL): f"Normalized to {dd:.1%} < {self.config.normal_drawdown:.1%}",
            (BreakerState.WARNING, BreakerState.NORMAL): f"Recovered to {dd:.1%} < {self.config.normal_drawdown:.1%}",
            (BreakerState.DERISK, BreakerState.WARNING): f"Recovered to {dd:.1%} < {self.config.warning_drawdown:.1%}",
        }
        
        # Check daily loss reasons
        if daily_pnl <= -self.config.halt_daily_loss:
            return f"Daily loss {abs(daily_pnl):.1%} > {self.config.halt_daily_loss:.1%}"
        if daily_pnl <= -self.config.derisk_daily_loss:
            return f"Daily loss {abs(daily_pnl):.1%} > {self.config.derisk_daily_loss:.1%}"
        if daily_pnl <= -self.config.warning_daily_loss:
            return f"Daily loss {abs(daily_pnl):.1%} > {self.config.warning_daily_loss:.1%}"
        
        return reasons.get((from_state, to_state), f"Transition from {from_state.value} to {to_state.value}")
    
    def _transition_to(
        self,
        new_state: BreakerState,
        reason: str,
        drawdown: float,
        daily_pnl: float,
        win: bool,
        timestamp: datetime,
    ) -> None:
        """Execute state transition."""
        old_state = self._state
        
        # Record transition
        transition = StateTransition(
            timestamp=timestamp,
            from_state=old_state,
            to_state=new_state,
            reason=reason,
            drawdown=drawdown,
            daily_pnl=daily_pnl,
            consecutive_losses=0,  # Will be updated by caller
        )
        self._transitions.append(transition)
        
        # Update state
        self._state = new_state
        self._state_enter_time = timestamp
        
        # Log transition
        level = logging.WARNING if new_state in [BreakerState.WARNING, BreakerState.DERISK] else logging.INFO
        if new_state == BreakerState.HALT:
            level = logging.ERROR
        logger.log(level, f"Circuit breaker: {old_state.value} → {new_state.value} - {reason}")
        
        # Keep only last 100 transitions
        if len(self._transitions) > 100:
            self._transitions = self._transitions[-100:]
    
    def _min_time_elapsed(self, timestamp: datetime) -> bool:
        """Check if minimum time in current state has elapsed."""
        if self._state_enter_time is None:
            return True
        
        elapsed = (timestamp - self._state_enter_time).total_seconds() / 3600.0
        
        min_times = {
            BreakerState.WARNING: self.config.min_time_warning,
            BreakerState.DERISK: self.config.min_time_derisk,
            BreakerState.HALT: self.config.min_time_halt,
            BreakerState.RECOVERY: self.config.min_time_recovery,
            BreakerState.NORMAL: 0.0,
        }
        
        min_time = min_times.get(self._state, 0.0)
        return elapsed >= min_time
    
    # ==============================================
    # Query Methods
    # ==============================================
    
    def can_trade(self) -> bool:
        """Check if trading is allowed."""
        return self._state.can_trade
    
    def get_multiplier(self) -> float:
        """Get position multiplier for current state."""
        return self._state.multiplier
    
    def get_state(self) -> BreakerState:
        """Get current state."""
        return self._state
    
    def get_state_info(self) -> Dict[str, Any]:
        """Get comprehensive state information."""
        return {
            'state': self._state.value,
            'can_trade': self.can_trade(),
            'multiplier': self.get_multiplier(),
            'state_enter_time': self._state_enter_time.isoformat() if self._state_enter_time else None,
            'last_update': self._last_update.isoformat() if self._last_update else None,
            'total_transitions': len(self._transitions),
            'last_transition': self._transitions[-1].to_dict() if self._transitions else None,
            'recent_transitions': [t.to_dict() for t in self._transitions[-5:]],
            'config': self.config.to_dict(),
        }
    
    def get_transition_history(self) -> List[Dict[str, Any]]:
        """Get full transition history."""
        return [t.to_dict() for t in self._transitions]
    
    def get_metrics_history(self) -> List[Dict[str, Any]]:
        """Get metrics history."""
        return self._metrics_history[-100:]  # Return last 100
    
    def get_status_report(self) -> Dict[str, Any]:
        """Generate comprehensive status report."""
        return {
            'current': {
                'state': self._state.value,
                'can_trade': self.can_trade(),
                'multiplier': self.get_multiplier(),
                'time_in_state': self._time_in_state(),
            },
            'statistics': {
                'total_transitions': len(self._transitions),
                'states_visited': list(set(t.to_state.value for t in self._transitions)),
                'halt_count': sum(1 for t in self._transitions if t.to_state == BreakerState.HALT),
                'recovery_count': sum(1 for t in self._transitions if t.to_state == BreakerState.RECOVERY),
            },
            'latest_transition': self._transitions[-1].to_dict() if self._transitions else None,
        }
    
    def _time_in_state(self) -> float:
        """Get time in current state in hours."""
        if self._state_enter_time is None:
            return 0.0
        return (datetime.now() - self._state_enter_time).total_seconds() / 3600.0
    
    # ==============================================
    # Manual Override Methods
    # ==============================================
    
    def force_halt(self, reason: str = "Manual halt") -> None:
        """Manually force halt."""
        if not self.config.allow_manual_override:
            raise ValueError("Manual override is disabled")
        
        timestamp = datetime.now()
        self._transition_to(
            new_state=BreakerState.HALT,
            reason=f"MANUAL: {reason}",
            drawdown=self._get_latest_drawdown(),
            daily_pnl=self._get_latest_daily_pnl(),
            win=False,
            timestamp=timestamp,
        )
        self._save_state()
    
    def force_resume(self) -> None:
        """Manually force resume to RECOVERY state."""
        if not self.config.allow_manual_override:
            raise ValueError("Manual override is disabled")
        
        if self._state != BreakerState.HALT:
            logger.warning(f"Force resume called while in {self._state.value}")
        
        timestamp = datetime.now()
        self._transition_to(
            new_state=BreakerState.RECOVERY,
            reason="MANUAL: Force resume",
            drawdown=self._get_latest_drawdown(),
            daily_pnl=self._get_latest_daily_pnl(),
            win=True,
            timestamp=timestamp,
        )
        self._save_state()
    
    def force_state(self, state: BreakerState, reason: str = "Manual override") -> None:
        """Manually force a specific state."""
        if not self.config.allow_manual_override:
            raise ValueError("Manual override is disabled")
        
        timestamp = datetime.now()
        self._transition_to(
            new_state=state,
            reason=f"MANUAL: {reason}",
            drawdown=self._get_latest_drawdown(),
            daily_pnl=self._get_latest_daily_pnl(),
            win=True,
            timestamp=timestamp,
        )
        self._save_state()
    
    def reset(self) -> None:
        """Reset to NORMAL state."""
        timestamp = datetime.now()
        self._transition_to(
            new_state=BreakerState.NORMAL,
            reason="RESET",
            drawdown=0.0,
            daily_pnl=0.0,
            win=True,
            timestamp=timestamp,
        )
        self._metrics_history = []
        self._save_state()
    
    # ==============================================
    # Persistence Methods
    # ==============================================
    
    def _get_latest_drawdown(self) -> float:
        """Get latest drawdown from metrics history."""
        if not self._metrics_history:
            return 0.0
        return self._metrics_history[-1].get('drawdown', 0.0)
    
    def _get_latest_daily_pnl(self) -> float:
        """Get latest daily PnL from metrics history."""
        if not self._metrics_history:
            return 0.0
        return self._metrics_history[-1].get('daily_pnl', 0.0)
    
    def _save_state(self) -> None:
        """Persist circuit breaker state to disk."""
        try:
            # Create directory if needed
            os.makedirs(os.path.dirname(self.persistence_path), exist_ok=True)
            
            state_data = {
                'state': self._state.value,
                'state_enter_time': self._state_enter_time.isoformat() if self._state_enter_time else None,
                'last_update': self._last_update.isoformat() if self._last_update else None,
                'transitions': [t.to_dict() for t in self._transitions[-20:]],  # Keep last 20
                'config': self.config.to_dict(),
            }
            
            with open(self.persistence_path, 'w') as f:
                json.dump(state_data, f, indent=2)
            
            logger.debug(f"Circuit breaker state saved to {self.persistence_path}")
        except Exception as e:
            logger.error(f"Failed to save circuit breaker state: {e}")
    
    def _load_state(self) -> None:
        """Load persistent circuit breaker state from disk."""
        if not os.path.exists(self.persistence_path):
            logger.info(f"No persistent state found at {self.persistence_path}")
            return
        
        try:
            with open(self.persistence_path, 'r') as f:
                state_data = json.load(f)
            
            # Restore state
            state_value = state_data.get('state')
            if state_value:
                self._state = BreakerState(state_value)
            
            # Restore state enter time
            enter_time = state_data.get('state_enter_time')
            if enter_time:
                self._state_enter_time = datetime.fromisoformat(enter_time)
            
            # Restore last update time
            last_update = state_data.get('last_update')
            if last_update:
                self._last_update = datetime.fromisoformat(last_update)
            
            logger.info(f"Circuit breaker state loaded: {self._state.value} from {self.persistence_path}")
        except Exception as e:
            logger.error(f"Failed to load circuit breaker state: {e}")
    
    def clear_persistence(self) -> None:
        """Clear persistent state file."""
        if os.path.exists(self.persistence_path):
            os.remove(self.persistence_path)
            logger.info(f"Cleared persistent state at {self.persistence_path}")
    
    # ==============================================
    # Integration with Risk Engine
    # ==============================================
    
    def apply_to_risk_decision(self, risk_decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply circuit breaker multiplier to risk decision.
        
        Args:
            risk_decision: Risk decision from Risk Engine
            
        Returns:
            Modified risk decision with circuit breaker applied
        """
        if not self.can_trade():
            return {
                'allowed': False,
                'risk_multiplier': 0.0,
                'max_exposure': 0.0,
                'max_position': 0.0,
                'reason': f"CIRCUIT_BREAKER: {self._state.value}",
            }
        
        # Apply multiplier to risk limits
        multiplier = self.get_multiplier()
        return {
            'allowed': risk_decision.get('allowed', True),
            'risk_multiplier': risk_decision.get('risk_multiplier', 1.0) * multiplier,
            'max_exposure': risk_decision.get('max_exposure', 1.0) * multiplier,
            'max_position': risk_decision.get('max_position', 0.20) * multiplier,
            'reason': f"{risk_decision.get('reason', 'OK')} | CB: {self._state.value}",
        }
