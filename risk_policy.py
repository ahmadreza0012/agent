"""
Risk Policy Module - State Machine with Circuit Breakers
=========================================================

This module implements a risk state machine that enforces capital protection rules.

Key Features:
- RESEARCH_MODE: Loosened thresholds for learning (cannot issue real orders)
- LIVE_MODE: Strict thresholds with automatic circuit breaker
- Paper trading mode for validation

Risk Officer Veto: Any change to LIVE_THRESHOLDS requires explicit approval.
"""

import os
import logging
from enum import Enum
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class TradingMode(Enum):
    """Trading mode enumeration."""
    RESEARCH = 'research'
    PAPER = 'paper'
    LIVE = 'live'


@dataclass
class RiskThresholds:
    """Risk threshold configuration."""
    target_return: float  # Minimum acceptable annualized return
    max_drawdown: float   # Maximum acceptable drawdown (circuit breaker level)
    min_sharpe: float     # Minimum acceptable Sharpe ratio
    max_position_single_asset: float  # Max weight in any single asset
    max_gross_exposure: float  # Maximum total exposure (1.0 = no leverage)


# Default thresholds by mode
RESEARCH_THRESHOLDS = RiskThresholds(
    target_return=-0.05,      # Allow -5% for learning
    max_drawdown=0.25,        # 25% DD tolerance in research
    min_sharpe=-1.0,          # Allow negative Sharpe
    max_position_single_asset=1.0,
    max_gross_exposure=1.0,
)

PAPER_THRESHOLDS = RiskThresholds(
    target_return=-0.02,      # Slightly stricter than research
    max_drawdown=0.15,        # 15% DD in paper
    min_sharpe=-0.5,          # Near-zero Sharpe minimum
    max_position_single_asset=0.50,
    max_gross_exposure=1.0,
)

LIVE_THRESHOLDS = RiskThresholds(
    target_return=0.0,        # Must be profitable
    max_drawdown=0.12,        # 12% DD circuit breaker
    min_sharpe=0.0,           # Must be non-negative Sharpe
    max_position_single_asset=0.40,  # 40% max concentration
    max_gross_exposure=1.0,   # No leverage
)


class RiskState(Enum):
    """Current risk state of the system."""
    ACTIVE = 'active'              # Normal operation
    WARNING = 'warning'            # Approaching limits
    CIRCUIT_BREAKER = 'circuit_breaker'  # Limits breached, trading halted
    RECOVERING = 'recovering'      # In cooldown period after circuit breaker


class RiskPolicy:
    """
    Risk policy manager with state machine and circuit breakers.
    
    Usage:
        policy = RiskPolicy()
        
        # Check if trade is allowed
        allowed, reason = policy.check_trade_allowed(metrics)
        
        # Update state based on new metrics
        policy.update_state(current_dd, current_sharpe, current_return)
        
        # Get current state
        state = policy.get_state()
    """
    
    def __init__(self, 
                 mode: Optional[TradingMode] = None,
                 custom_thresholds: Optional[RiskThresholds] = None):
        """
        Initialize risk policy.
        
        Args:
            mode: Trading mode (auto-detected from env if None)
            custom_thresholds: Override default thresholds for this mode
        """
        self._mode = mode or self._detect_mode()
        self._thresholds = custom_thresholds or self._get_thresholds_for_mode(self._mode)
        self._state = RiskState.ACTIVE
        self._circuit_breaker_triggered_at: Optional[float] = None
        self._cooldown_seconds = 3600  # 1 hour cooldown after circuit breaker
        
        logger.info(f"RiskPolicy initialized: mode={self._mode.value}, "
                   f"max_dd={self._thresholds.max_drawdown:.2f}")
    
    def _detect_mode(self) -> TradingMode:
        """Detect trading mode from environment."""
        mode_str = os.environ.get('TRADING_MODE', 'research').lower()
        try:
            return TradingMode(mode_str)
        except ValueError:
            logger.warning(f"Unknown TRADING_MODE='{mode_str}', defaulting to research")
            return TradingMode.RESEARCH
    
    def _get_thresholds_for_mode(self, mode: TradingMode) -> RiskThresholds:
        """Get thresholds appropriate for the trading mode."""
        if mode == TradingMode.LIVE:
            return LIVE_THRESHOLDS
        elif mode == TradingMode.PAPER:
            return PAPER_THRESHOLDS
        else:  # RESEARCH
            return RESEARCH_THRESHOLDS
    
    @property
    def mode(self) -> TradingMode:
        """Get current trading mode."""
        return self._mode
    
    @property
    def thresholds(self) -> RiskThresholds:
        """Get current risk thresholds."""
        return self._thresholds
    
    @property
    def state(self) -> RiskState:
        """Get current risk state."""
        return self._state
    
    def is_live_mode(self) -> bool:
        """Check if in live trading mode."""
        return self._mode == TradingMode.LIVE
    
    def can_issue_real_orders(self) -> bool:
        """
        Check if system can issue real orders.
        
        Returns:
            True only if in LIVE mode AND circuit breaker not triggered
        """
        if self._mode != TradingMode.LIVE:
            return False
        if self._state == RiskState.CIRCUIT_BREAKER:
            return False
        return True
    
    def check_trade_allowed(self, metrics: Dict[str, float]) -> Tuple[bool, str]:
        """
        Check if a trade is allowed given current metrics.
        
        Args:
            metrics: Dict with keys:
                - drawdown: Current drawdown (as decimal, e.g., 0.10 = 10%)
                - sharpe: Current Sharpe ratio
                - annualized_return: Annualized return
            
        Returns:
            (allowed: bool, reason: str)
        """
        dd = metrics.get('drawdown', 0.0)
        sharpe = metrics.get('sharpe', 0.0)
        ret = metrics.get('annualized_return', 0.0)
        
        # Check circuit breaker first
        if self._state == RiskState.CIRCUIT_BREAKER:
            # Check if cooldown has passed
            import time
            if time.time() - self._circuit_breaker_triggered_at < self._cooldown_seconds:
                return False, "Circuit breaker active - trading halted"
            else:
                self._state = RiskState.RECOVERING
                logger.info("Circuit breaker cooldown complete, entering recovery state")
        
        # Check drawdown limit
        if abs(dd) > self._thresholds.max_drawdown:
            return False, f"Drawdown {dd:.2%} exceeds limit {self._thresholds.max_drawdown:.2%}"
        
        # Check Sharpe limit (only in live mode)
        if self._mode == TradingMode.LIVE and sharpe < self._thresholds.min_sharpe:
            return False, f"Sharpe {sharpe:.2f} below minimum {self._thresholds.min_sharpe:.2f}"
        
        # Check return limit (only in live mode)
        if self._mode == TradingMode.LIVE and ret < self._thresholds.target_return:
            return False, f"Return {ret:.2%} below target {self._thresholds.target_return:.2%}"
        
        return True, "Trade allowed"
    
    def update_state(self, 
                     current_dd: float,
                     current_sharpe: float,
                     current_return: float) -> RiskState:
        """
        Update risk state based on current metrics.
        
        Args:
            current_dd: Current drawdown (negative value, e.g., -0.10 = 10% DD)
            current_sharpe: Current Sharpe ratio
            current_return: Current annualized return
        
        Returns:
            New risk state
        """
        import time
        
        old_state = self._state
        
        # Check for circuit breaker trigger
        if abs(current_dd) > self._thresholds.max_drawdown:
            if self._state != RiskState.CIRCUIT_BREAKER:
                self._state = RiskState.CIRCUIT_BREAKER
                self._circuit_breaker_triggered_at = time.time()
                logger.critical(
                    f"CIRCUIT BREAKER TRIGGERED: Drawdown {current_dd:.2%} "
                    f"exceeds limit {self._thresholds.max_drawdown:.2%}"
                )
                # In live mode, this would trigger position closure
                if self._mode == TradingMode.LIVE:
                    logger.critical("LIVE MODE: Emergency position closure required")
        elif self._state == RiskState.CIRCUIT_BREAKER:
            # Still in cooldown
            if time.time() - self._circuit_breaker_triggered_at >= self._cooldown_seconds:
                self._state = RiskState.RECOVERING
                logger.info("Circuit breaker cooldown complete")
        elif self._state == RiskState.RECOVERING:
            # Check if metrics are back within limits
            if (abs(current_dd) < self._thresholds.max_drawdown * 0.8 and
                current_sharpe >= self._thresholds.min_sharpe):
                self._state = RiskState.ACTIVE
                logger.info("Risk metrics recovered, returning to active state")
        
        # Check warning state (approaching limits)
        if self._state == RiskState.ACTIVE:
            dd_warning_threshold = self._thresholds.max_drawdown * 0.8
            if abs(current_dd) > dd_warning_threshold:
                self._state = RiskState.WARNING
                logger.warning(
                    f"WARNING: Drawdown {current_dd:.2%} approaching "
                    f"limit {self._thresholds.max_drawdown:.2%}"
                )
            elif current_sharpe < self._thresholds.min_sharpe * 0.5:
                self._state = RiskState.WARNING
                logger.warning(f"WARNING: Sharpe {current_sharpe:.2f} deteriorating")
        
        if old_state != self._state:
            logger.info(f"Risk state transition: {old_state.value} → {self._state.value}")
        
        return self._state
    
    def force_circuit_breaker(self, reason: str = "Manual override") -> None:
        """
        Manually trigger circuit breaker.
        
        Args:
            reason: Reason for manual trigger
        """
        import time
        self._state = RiskState.CIRCUIT_BREAKER
        self._circuit_breaker_triggered_at = time.time()
        logger.critical(f"MANUAL CIRCUIT BREAKER: {reason}")
    
    def reset_to_active(self) -> None:
        """Reset state to active (requires human confirmation in live mode)."""
        if self._mode == TradingMode.LIVE and self._state == RiskState.CIRCUIT_BREAKER:
            logger.warning("Cannot reset circuit breaker in LIVE mode without manual confirmation")
            raise RuntimeError("Manual confirmation required to reset circuit breaker in live mode")
        
        self._state = RiskState.ACTIVE
        self._circuit_breaker_triggered_at = None
        logger.info("Risk state reset to active")
    
    def get_status_report(self) -> Dict:
        """
        Get comprehensive risk status report.
        
        Returns:
            Dict with current state, thresholds, and mode info
        """
        return {
            'mode': self._mode.value,
            'state': self._state.value,
            'can_trade_real': self.can_issue_real_orders(),
            'thresholds': {
                'target_return': self._thresholds.target_return,
                'max_drawdown': self._thresholds.max_drawdown,
                'min_sharpe': self._thresholds.min_sharpe,
                'max_position': self._thresholds.max_position_single_asset,
                'max_exposure': self._thresholds.max_gross_exposure,
            },
            'circuit_breaker_active': self._state == RiskState.CIRCUIT_BREAKER,
            'cooldown_remaining': self._get_cooldown_remaining(),
        }
    
    def _get_cooldown_remaining(self) -> Optional[float]:
        """Get remaining cooldown time in seconds, or None if not applicable."""
        if self._state != RiskState.CIRCUIT_BREAKER or self._circuit_breaker_triggered_at is None:
            return None
        import time
        elapsed = time.time() - self._circuit_breaker_triggered_at
        remaining = max(0, self._cooldown_seconds - elapsed)
        return remaining


# Convenience functions for simple usage
_default_policy: Optional[RiskPolicy] = None


def get_default_policy() -> RiskPolicy:
    """Get or create default risk policy singleton."""
    global _default_policy
    if _default_policy is None:
        _default_policy = RiskPolicy()
    return _default_policy


def check_trade_allowed(metrics: Dict[str, float]) -> Tuple[bool, str]:
    """Check if trade is allowed using default policy."""
    return get_default_policy().check_trade_allowed(metrics)


def is_live_mode() -> bool:
    """Check if system is in live mode."""
    return get_default_policy().is_live_mode()


def can_issue_real_orders() -> bool:
    """Check if real orders can be issued."""
    return get_default_policy().can_issue_real_orders()
