"""
Risk State Manager - Persistence for risk component state.

Manages drawdown, equity, daily PnL, exposure, and halt state persistence.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime
import logging

from .state_manager import StateManager
from .persistence_manager import PersistenceManager

logger = logging.getLogger(__name__)


@dataclass
class RiskState:
    """Risk system state."""
    current_drawdown: float = 0.0
    peak_equity: float = 0.0
    current_equity: float = 0.0
    daily_pnl: float = 0.0
    daily_trades: int = 0
    daily_turnover: float = 0.0
    exposure_ratio: float = 0.0
    is_halted: bool = False
    halt_reason: Optional[str] = None
    last_update: Optional[datetime] = None


class RiskStateManager(StateManager[RiskState]):
    """State manager for risk component."""
    
    def __init__(self, persistence_manager: PersistenceManager):
        super().__init__(persistence_manager, 'risk')
    
    def serialize(self, state: RiskState) -> Dict[str, Any]:
        return {
            'current_drawdown': state.current_drawdown,
            'peak_equity': state.peak_equity,
            'current_equity': state.current_equity,
            'daily_pnl': state.daily_pnl,
            'daily_trades': state.daily_trades,
            'daily_turnover': state.daily_turnover,
            'exposure_ratio': state.exposure_ratio,
            'is_halted': state.is_halted,
            'halt_reason': state.halt_reason,
            'last_update': state.last_update.isoformat() if state.last_update else None
        }
    
    def deserialize(self, data: Dict[str, Any]) -> RiskState:
        state = RiskState()
        state.current_drawdown = data.get('current_drawdown', 0.0)
        state.peak_equity = data.get('peak_equity', 0.0)
        state.current_equity = data.get('current_equity', 0.0)
        state.daily_pnl = data.get('daily_pnl', 0.0)
        state.daily_trades = data.get('daily_trades', 0)
        state.daily_turnover = data.get('daily_turnover', 0.0)
        state.exposure_ratio = data.get('exposure_ratio', 0.0)
        state.is_halted = data.get('is_halted', False)
        state.halt_reason = data.get('halt_reason')
        last_update = data.get('last_update')
        state.last_update = datetime.fromisoformat(last_update) if last_update else None
        return state
    
    def get_default_state(self) -> RiskState:
        return RiskState()
    
    def update_equity(self, equity: float) -> None:
        """Update current equity and calculate drawdown."""
        state = self.get_current()
        state.current_equity = equity
        if equity > state.peak_equity:
            state.peak_equity = equity
        if state.peak_equity > 0:
            state.current_drawdown = (equity - state.peak_equity) / state.peak_equity
        state.last_update = datetime.now()
        self.set_current(state)
        self.save_current()
    
    def record_trade(self, pnl: float, turnover: float) -> None:
        """Record a trade for daily tracking."""
        state = self.get_current()
        state.daily_pnl += pnl
        state.daily_trades += 1
        state.daily_turnover += turnover
        state.last_update = datetime.now()
        self.set_current(state)
        self.save_current()
    
    def set_halt(self, reason: str) -> None:
        """Set trading halt state."""
        state = self.get_current()
        state.is_halted = True
        state.halt_reason = reason
        state.last_update = datetime.now()
        self.set_current(state)
        self.save_current()
        logger.warning(f"Trading halted: {reason}")
    
    def clear_halt(self) -> None:
        """Clear trading halt state."""
        state = self.get_current()
        state.is_halted = False
        state.halt_reason = None
        state.last_update = datetime.now()
        self.set_current(state)
        self.save_current()
        logger.info("Trading halt cleared")
    
    def reset_daily(self) -> None:
        """Reset daily counters (call at day start)."""
        state = self.get_current()
        state.daily_pnl = 0.0
        state.daily_trades = 0
        state.daily_turnover = 0.0
        state.last_update = datetime.now()
        self.set_current(state)
        self.save_current()
        logger.info("Daily risk counters reset")
