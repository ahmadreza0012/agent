"""
Capital Preservation System
============================
Comprehensive capital preservation framework for crypto trading.

This module implements multi-layer protection to ensure capital preservation
is the primary objective, with profit as a secondary concern.

Components:
- CapitalPreservationEngine: Main engine for preserving capital
- CapitalPreservationConfig: Configuration for risk controls
- CapitalPosition: Current capital position tracking
- CapitalPreservationAction: Actions to preserve capital
- PreservationLevel: Levels of capital preservation
- RiskStatus: Current risk status indicators
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import pandas as pd
import numpy as np
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PreservationLevel(Enum):
    """Levels of capital preservation."""
    MAXIMUM = "maximum"          # Extreme caution
    HIGH = "high"                # Strong preservation
    MEDIUM = "medium"            # Balanced approach
    LOW = "low"                  # More aggressive
    NONE = "none"                # No preservation (not recommended)


class RiskStatus(Enum):
    """Current risk status."""
    SAFE = "safe"
    WARNING = "warning"
    DANGER = "danger"
    CRITICAL = "critical"
    RUIN = "ruin"


@dataclass
class CapitalPreservationConfig:
    """Configuration for capital preservation."""
    max_drawdown_limit: float = 0.25          # 25% maximum drawdown
    max_daily_loss_limit: float = 0.05        # 5% daily loss limit
    max_position_size: float = 0.20           # 20% max position
    max_correlation: float = 0.70             # 0.70 max asset correlation
    min_cash_ratio: float = 0.10              # 10% minimum cash
    max_leverage: float = 1.0                 # No leverage
    drawdown_action_threshold: float = 0.15   # 15% drawdown triggers action
    critical_drawdown_threshold: float = 0.20 # 20% drawdown is critical
    stop_trading_threshold: float = 0.25      # 25% drawdown stops trading
    recovery_factor: float = 0.70             # 70% recovery after drawdown


@dataclass
class CapitalPosition:
    """Current capital position."""
    total_capital: float
    invested_capital: float
    cash_capital: float
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    total_return: float
    current_drawdown: float
    max_drawdown: float
    daily_loss_today: float


@dataclass
class CapitalPreservationAction:
    """Action to preserve capital."""
    action_type: str
    severity: RiskStatus
    reason: str
    actions: List[str]
    multiplier: float
    timestamp: str = field(default_factory=lambda: str(datetime.now()))


class CapitalPreservationEngine:
    """
    Engine for preserving capital through risk management.
    
    This engine implements multiple layers of protection:
    1. Drawdown monitoring and control
    2. Daily loss limits
    3. Position concentration limits
    4. Correlation risk monitoring
    5. Cash ratio requirements
    6. Market condition assessment
    
    The engine returns a multiplier that scales position sizing based on
    current risk conditions. A multiplier of 1.0 means normal operations,
    while 0.0 means halt all trading.
    """
    
    def __init__(self, config: CapitalPreservationConfig = None):
        self.config = config or CapitalPreservationConfig()
        self.history: List[Dict] = []
        self.current_status = RiskStatus.SAFE
        self.position = None
        self._drawdown_history = []
        
    def evaluate(
        self,
        capital: CapitalPosition,
        portfolio_metrics: Dict[str, float],
        market_data: pd.DataFrame,
        regime: str
    ) -> CapitalPreservationAction:
        """
        Evaluate capital preservation status and take actions.
        
        Args:
            capital: Current capital position
            portfolio_metrics: Portfolio risk metrics
            market_data: Current market data
            regime: Current market regime
        
        Returns:
            Capital preservation action
        """
        actions = []
        severity = RiskStatus.SAFE
        multiplier = 1.0
        
        # 1. Check drawdown
        drawdown_action = self._check_drawdown(capital.current_drawdown)
        if drawdown_action:
            actions.extend(drawdown_action.actions)
            severity = self._max_severity(severity, drawdown_action.severity)
            multiplier *= drawdown_action.multiplier
        
        # 2. Check daily loss
        daily_loss_action = self._check_daily_loss(capital.daily_loss_today)
        if daily_loss_action:
            actions.extend(daily_loss_action.actions)
            severity = self._max_severity(severity, daily_loss_action.severity)
            multiplier *= daily_loss_action.multiplier
        
        # 3. Check position concentration
        concentration_action = self._check_concentration(portfolio_metrics)
        if concentration_action:
            actions.extend(concentration_action.actions)
            severity = self._max_severity(severity, concentration_action.severity)
            multiplier *= concentration_action.multiplier
        
        # 4. Check correlation risk
        correlation_action = self._check_correlation(portfolio_metrics)
        if correlation_action:
            actions.extend(correlation_action.actions)
            severity = self._max_severity(severity, correlation_action.severity)
            multiplier *= correlation_action.multiplier
        
        # 5. Check cash ratio
        cash_action = self._check_cash_ratio(capital)
        if cash_action:
            actions.extend(cash_action.actions)
            severity = self._max_severity(severity, cash_action.severity)
            multiplier *= cash_action.multiplier
        
        # 6. Check market conditions
        market_action = self._check_market_conditions(market_data, regime)
        if market_action:
            actions.extend(market_action.actions)
            severity = self._max_severity(severity, market_action.severity)
            multiplier *= market_action.multiplier
        
        # Update status
        self.current_status = severity
        self.position = capital
        
        # Record history
        self.history.append({
            'timestamp': datetime.now(),
            'status': severity.value,
            'multiplier': multiplier,
            'actions': actions,
            'drawdown': capital.current_drawdown,
            'capital': capital.total_capital,
        })
        
        return CapitalPreservationAction(
            action_type="capital_preservation",
            severity=severity,
            reason=f"Risk status: {severity.value}, actions: {len(actions)}",
            actions=actions,
            multiplier=max(0.0, min(1.0, multiplier))  # Clamp between 0 and 1
        )
    
    def _max_severity(self, s1: RiskStatus, s2: RiskStatus) -> RiskStatus:
        """Return the more severe of two risk statuses."""
        order = ['safe', 'warning', 'danger', 'critical', 'ruin']
        idx1 = order.index(s1.value)
        idx2 = order.index(s2.value)
        return s1 if idx1 >= idx2 else s2
    
    def _check_drawdown(self, current_drawdown: float) -> Optional[CapitalPreservationAction]:
        """Check drawdown level and take appropriate action."""
        if current_drawdown >= self.config.stop_trading_threshold:
            return CapitalPreservationAction(
                action_type="drawdown",
                severity=RiskStatus.RUIN,
                reason=f"Drawdown {current_drawdown:.1%} exceeds stop trading threshold {self.config.stop_trading_threshold:.1%}",
                actions=["HALT_ALL_TRADING", "CLOSE_ALL_POSITIONS", "EMERGENCY_KILL_SWITCH"],
                multiplier=0.0
            )
        elif current_drawdown >= self.config.critical_drawdown_threshold:
            return CapitalPreservationAction(
                action_type="drawdown",
                severity=RiskStatus.CRITICAL,
                reason=f"Drawdown {current_drawdown:.1%} exceeds critical threshold {self.config.critical_drawdown_threshold:.1%}",
                actions=["REDUCE_EXPOSURE_50%", "INCREASE_CASH_50%", "DERISK_ALL_POSITIONS"],
                multiplier=0.5
            )
        elif current_drawdown >= self.config.drawdown_action_threshold:
            return CapitalPreservationAction(
                action_type="drawdown",
                severity=RiskStatus.DANGER,
                reason=f"Drawdown {current_drawdown:.1%} exceeds action threshold {self.config.drawdown_action_threshold:.1%}",
                actions=["REDUCE_EXPOSURE_25%", "INCREASE_CASH_25%"],
                multiplier=0.75
            )
        return None
    
    def _check_daily_loss(self, daily_loss: float) -> Optional[CapitalPreservationAction]:
        """Check daily loss and take appropriate action."""
        if daily_loss >= self.config.max_daily_loss_limit:
            return CapitalPreservationAction(
                action_type="daily_loss",
                severity=RiskStatus.DANGER,
                reason=f"Daily loss {daily_loss:.1%} exceeds limit {self.config.max_daily_loss_limit:.1%}",
                actions=["HALT_TRADING_FOR_DAY", "REVIEW_POSITIONS"],
                multiplier=0.0
            )
        elif daily_loss >= self.config.max_daily_loss_limit * 0.7:
            return CapitalPreservationAction(
                action_type="daily_loss",
                severity=RiskStatus.WARNING,
                reason=f"Daily loss {daily_loss:.1%} approaching limit {self.config.max_daily_loss_limit:.1%}",
                actions=["REDUCE_NEW_POSITIONS", "MONITOR_CLOSELY"],
                multiplier=0.8
            )
        return None
    
    def _check_concentration(self, metrics: Dict[str, float]) -> Optional[CapitalPreservationAction]:
        """Check position concentration."""
        max_position = metrics.get('max_position_size', 0)
        if max_position > self.config.max_position_size * 1.5:
            return CapitalPreservationAction(
                action_type="concentration",
                severity=RiskStatus.DANGER,
                reason=f"Position concentration {max_position:.1%} exceeds limits",
                actions=["REDUCE_LARGEST_POSITION", "DIVERSIFY"],
                multiplier=0.7
            )
        elif max_position > self.config.max_position_size:
            return CapitalPreservationAction(
                action_type="concentration",
                severity=RiskStatus.WARNING,
                reason=f"Position concentration {max_position:.1%} exceeds target {self.config.max_position_size:.1%}",
                actions=["REDUCE_CONCENTRATION"],
                multiplier=0.9
            )
        return None
    
    def _check_correlation(self, metrics: Dict[str, float]) -> Optional[CapitalPreservationAction]:
        """Check correlation risk."""
        max_correlation = metrics.get('max_correlation', 0)
        if max_correlation > self.config.max_correlation * 1.2:
            return CapitalPreservationAction(
                action_type="correlation",
                severity=RiskStatus.WARNING,
                reason=f"Correlation {max_correlation:.2f} exceeds limits",
                actions=["DIVERSIFY_CORRELATION", "ADD_UNCORRELATED_ASSETS"],
                multiplier=0.85
            )
        return None
    
    def _check_cash_ratio(self, capital: CapitalPosition) -> Optional[CapitalPreservationAction]:
        """Check cash ratio."""
        cash_ratio = capital.cash_capital / capital.total_capital if capital.total_capital > 0 else 0
        if cash_ratio < self.config.min_cash_ratio * 0.5:
            return CapitalPreservationAction(
                action_type="cash_ratio",
                severity=RiskStatus.DANGER,
                reason=f"Cash ratio {cash_ratio:.1%} below emergency level",
                actions=["SELL_ASSETS", "INCREASE_CASH_TO_10%"],
                multiplier=0.7
            )
        elif cash_ratio < self.config.min_cash_ratio:
            return CapitalPreservationAction(
                action_type="cash_ratio",
                severity=RiskStatus.WARNING,
                reason=f"Cash ratio {cash_ratio:.1%} below target {self.config.min_cash_ratio:.1%}",
                actions=["REDUCE_POSITIONS", "INCREASE_CASH"],
                multiplier=0.9
            )
        return None
    
    def _check_market_conditions(self, market_data: pd.DataFrame, regime: str) -> Optional[CapitalPreservationAction]:
        """Check market conditions for risk."""
        # Check volatility
        if len(market_data) > 0 and 'returns' in market_data.columns:
            recent_vol = market_data['returns'].tail(20).std()
            historical_vol = market_data['returns'].std()
            vol_ratio = recent_vol / historical_vol if historical_vol > 0 else 1
            
            if vol_ratio > 2.0:
                return CapitalPreservationAction(
                    action_type="market_volatility",
                    severity=RiskStatus.DANGER,
                    reason=f"Volatility spike: {vol_ratio:.1f}x normal",
                    actions=["REDUCE_EXPOSURE_50%", "STOP_NEW_POSITIONS"],
                    multiplier=0.5
                )
            elif vol_ratio > 1.5:
                return CapitalPreservationAction(
                    action_type="market_volatility",
                    severity=RiskStatus.WARNING,
                    reason=f"Elevated volatility: {vol_ratio:.1f}x normal",
                    actions=["REDUCE_POSITION_SIZING"],
                    multiplier=0.75
                )
        
        # Check regime
        dangerous_regimes = ['CRASH', 'LIQUIDITY_CRISIS', 'PANIC']
        if regime in dangerous_regimes:
            return CapitalPreservationAction(
                action_type="regime",
                severity=RiskStatus.CRITICAL,
                reason=f"Dangerous market regime: {regime}",
                actions=["REDUCE_EXPOSURE_75%", "INCREASE_CASH", "HALT_AGGRESSIVE_TRADING"],
                multiplier=0.25
            )
        
        return None
    
    def get_status(self) -> Dict:
        """Get current capital preservation status."""
        return {
            'status': self.current_status.value,
            'position': self.position,
            'config': self.config,
            'history_length': len(self.history),
        }
    
    def get_recovery_recommendations(self) -> List[str]:
        """Get recommendations for recovering from losses."""
        if self.current_status in [RiskStatus.CRITICAL, RiskStatus.RUIN]:
            return [
                "STOP ALL TRADING IMMEDIATELY",
                "Review all positions",
                "Assess root cause of losses",
                "Reduce exposure to minimum",
                "Focus on capital preservation",
                "Re-evaluate strategy assumptions",
                "Consider adjusting risk parameters",
            ]
        elif self.current_status == RiskStatus.DANGER:
            return [
                "Reduce trading activity",
                "Review risk limits",
                "Adjust position sizing",
                "Increase cash reserves",
                "Monitor closely for further deterioration",
            ]
        elif self.current_status == RiskStatus.WARNING:
            return [
                "Monitor positions closely",
                "Consider slight reduction in risk",
                "Review market conditions",
                "Ensure stop-losses are in place",
            ]
        else:
            return ["Continue normal operations with standard risk management"]
    
    def get_history(self) -> pd.DataFrame:
        """Get history of capital preservation evaluations."""
        if not self.history:
            return pd.DataFrame()
        return pd.DataFrame(self.history)
