"""
Centralized Risk Engine
=======================
Independent risk evaluation that can override strategy decisions.

The Risk Engine evaluates portfolio risk across multiple dimensions and
provides a decision that the strategy must follow.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

from .risk_limits import RiskLimits, DEFAULT_LIMITS
from .risk_metrics import RiskMetrics, calculate_risk_metrics

logger = logging.getLogger(__name__)


@dataclass
class RiskDecision:
    """
    Decision from risk engine.
    
    Attributes:
        allowed: Whether trading is allowed
        risk_multiplier: Scale factor for positions (0.0-1.0)
        max_exposure: Maximum allowed gross exposure
        max_position: Maximum allowed position per asset
        max_daily_loss: Maximum allowed daily loss
        max_drawdown: Maximum allowed drawdown
        reason: Human-readable reason for decision
        details: Additional details about the decision
    """
    allowed: bool = True
    risk_multiplier: float = 1.0
    max_exposure: float = 1.0
    max_position: float = 0.20
    max_daily_loss: float = 0.03
    max_drawdown: float = 0.12
    reason: str = "OK"
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'allowed': self.allowed,
            'risk_multiplier': self.risk_multiplier,
            'max_exposure': self.max_exposure,
            'max_position': self.max_position,
            'max_daily_loss': self.max_daily_loss,
            'max_drawdown': self.max_drawdown,
            'reason': self.reason,
            'details': self.details,
        }
    
    @classmethod
    def halt(cls, reason: str) -> 'RiskDecision':
        """Create a HALT decision."""
        return cls(
            allowed=False,
            risk_multiplier=0.0,
            reason=f"HALT: {reason}"
        )
    
    @classmethod
    def reduce(cls, multiplier: float, reason: str) -> 'RiskDecision':
        """Create a REDUCE decision with a multiplier."""
        return cls(
            allowed=True,
            risk_multiplier=multiplier,
            reason=f"REDUCE: {reason}"
        )


class RiskEngine:
    """
    Centralized risk management engine.
    
    Features:
    - Independent risk evaluation
    - Can override strategy decisions
    - Considers: exposure, position size, volatility, drawdown, correlation, liquidity
    - Stateful tracking of risk metrics over time
    - Configurable risk limits for different trading modes
    """
    
    def __init__(
        self,
        limits: Optional[RiskLimits] = None,
        mode: str = 'research',
        lookback: int = 252,
    ):
        """
        Initialize Risk Engine.
        
        Args:
            limits: Risk limits configuration
            mode: Trading mode ('research', 'paper', 'live', 'conservative', 'aggressive')
            lookback: Number of periods for rolling calculations
        """
        self.mode = mode
        self.lookback = lookback
        
        # Set limits based on mode
        if limits is None:
            self.limits = DEFAULT_LIMITS.get(mode, RiskLimits())
        else:
            self.limits = limits
        
        # State tracking
        self._history: List[Dict[str, Any]] = []
        self._current_metrics: Optional[RiskMetrics] = None
        self._last_decision: Optional[RiskDecision] = None
        self._decision_history: List[RiskDecision] = []
        
        # Recovery tracking
        self._drawdown_peak: float = 0.0
        self._drawdown_start: Optional[datetime] = None
        self._recovery_start: Optional[datetime] = None
        
        logger.info(f"RiskEngine initialized with mode={mode}, limits={self.limits.to_dict()}")
    
    def evaluate(
        self,
        portfolio_weights: Dict[str, float],
        positions: Optional[Dict[str, float]] = None,
        asset_returns: Optional[pd.DataFrame] = None,
        asset_prices: Optional[pd.DataFrame] = None,
        market_data: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> RiskDecision:
        """
        Evaluate risk and return decision.
        
        Args:
            portfolio_weights: Current portfolio weights {asset: weight}
            positions: Current positions {asset: size}
            asset_returns: Historical returns DataFrame
            asset_prices: Historical prices DataFrame
            market_data: Market data {asset: {price, volume, volatility, spread, ...}}
            timestamp: Decision timestamp
            
        Returns:
            RiskDecision with risk parameters
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Calculate risk metrics
        if asset_returns is not None and asset_prices is not None:
            volumes = {a: md.get('volume', 0) for a, md in (market_data or {}).items()}
            spreads = {a: md.get('spread', 0) for a, md in (market_data or {}).items()}
            
            metrics = calculate_risk_metrics(
                portfolio_weights=portfolio_weights,
                asset_returns=asset_returns,
                asset_prices=asset_prices,
                asset_volumes=volumes,
                asset_spreads=spreads,
                lookback=self.lookback,
            )
        else:
            # Simplified metrics without historical data
            metrics = self._calculate_simple_metrics(portfolio_weights, market_data)
        
        self._current_metrics = metrics
        
        # Evaluate each risk dimension
        decisions = []
        
        # 1. Exposure check
        if metrics.gross_exposure > self.limits.max_gross_exposure:
            decisions.append(("EXPOSURE", f"Exposure {metrics.gross_exposure:.1%} > {self.limits.max_gross_exposure:.1%}"))
        
        # 2. Position check
        if metrics.max_position > self.limits.max_single_position:
            decisions.append(("POSITION", f"Position {metrics.max_position:.1%} > {self.limits.max_single_position:.1%}"))
        
        # 3. Volatility check
        if metrics.portfolio_volatility > self.limits.max_volatility:
            decisions.append(("VOLATILITY", f"Vol {metrics.portfolio_volatility:.1%} > {self.limits.max_volatility:.1%}"))
        
        # 4. Drawdown check
        if metrics.current_drawdown < -self.limits.max_drawdown:
            decisions.append(("DRAWDOWN", f"DD {metrics.current_drawdown:.1%} < -{self.limits.max_drawdown:.1%}"))
        
        # 5. Daily loss check
        if metrics.daily_pnl < -self.limits.max_drawdown_daily:
            decisions.append(("DAILY_LOSS", f"Daily loss {metrics.daily_pnl:.1%} < -{self.limits.max_drawdown_daily:.1%}"))
        
        # 6. Correlation check
        if metrics.avg_correlation > self.limits.max_correlation:
            decisions.append(("CORRELATION", f"Corr {metrics.avg_correlation:.2f} > {self.limits.max_correlation:.2f}"))
        
        # 7. Liquidity check
        if metrics.min_liquidity < self.limits.min_liquidity:
            decisions.append(("LIQUIDITY", f"Liquidity ${metrics.min_liquidity:.0f} < ${self.limits.min_liquidity:.0f}"))
        
        # 8. Concentration check
        if metrics.hhi > self.limits.max_hhi:
            decisions.append(("CONCENTRATION", f"HHI {metrics.hhi:.3f} > {self.limits.max_hhi:.3f}"))
        
        # Determine decision
        if decisions:
            # Check for halt conditions (critical violations)
            halt_conditions = ['DRAWDOWN', 'DAILY_LOSS']
            halt_violations = [d for d in decisions if d[0] in halt_conditions]
            
            if halt_violations:
                reason = f"HALT: {halt_violations[0][1]}"
                decision = RiskDecision.halt(reason)
            else:
                # Calculate risk multiplier
                risk_multiplier = self._calculate_risk_multiplier(metrics, decisions)
                reason = f"REDUCE: {decisions[0][1]}"
                decision = RiskDecision.reduce(risk_multiplier, reason)
        else:
            # All checks passed
            decision = RiskDecision(
                allowed=True,
                risk_multiplier=1.0,
                max_exposure=self.limits.max_gross_exposure,
                max_position=self.limits.max_single_position,
                max_drawdown=self.limits.max_drawdown,
                max_daily_loss=self.limits.max_drawdown_daily,
                reason="OK",
                details={'metrics': metrics.to_dict()},
            )
        
        # Store decision
        self._last_decision = decision
        self._decision_history.append(decision)
        self._history.append({
            'timestamp': timestamp,
            'metrics': metrics.to_dict(),
            'decision': decision.to_dict(),
        })
        
        # Update state
        self._update_state(metrics, timestamp)
        
        return decision
    
    def _calculate_simple_metrics(
        self,
        portfolio_weights: Dict[str, float],
        market_data: Optional[Dict[str, Any]] = None,
    ) -> RiskMetrics:
        """Calculate simplified metrics without historical data."""
        assets = list(portfolio_weights.keys())
        weights = np.array([portfolio_weights.get(a, 0.0) for a in assets])
        
        metrics = RiskMetrics()
        metrics.gross_exposure = sum(abs(w) for w in weights)
        metrics.net_exposure = sum(weights)
        metrics.cash_weight = 1.0 - sum(weights)
        
        if len(weights) > 0:
            max_idx = np.argmax(abs(weights))
            metrics.max_position = abs(weights[max_idx])
            metrics.max_position_asset = assets[max_idx] if max_idx < len(assets) else ""
            metrics.hhi = sum(w ** 2 for w in weights)
        
        if market_data:
            volumes = [md.get('volume', 0) for md in market_data.values()]
            metrics.avg_liquidity = np.mean(volumes) if volumes else 0
            metrics.min_liquidity = np.min(volumes) if volumes else 0
            
            spreads = [md.get('spread', 0) for md in market_data.values()]
            metrics.avg_spread = np.mean(spreads) if spreads else 0
        
        return metrics
    
    def _calculate_risk_multiplier(self, metrics: RiskMetrics, violations: List[Tuple[str, str]]) -> float:
        """
        Calculate risk multiplier based on violations.
        
        The multiplier is reduced based on the severity of violations.
        """
        multiplier = 1.0
        
        # Exposure violation
        if metrics.gross_exposure > self.limits.max_gross_exposure:
            excess = metrics.gross_exposure / self.limits.max_gross_exposure - 1
            multiplier *= max(0.5, 1.0 - excess * 0.5)
        
        # Position violation
        if metrics.max_position > self.limits.max_single_position:
            excess = metrics.max_position / self.limits.max_single_position - 1
            multiplier *= max(0.5, 1.0 - excess * 0.5)
        
        # Volatility violation
        if metrics.portfolio_volatility > self.limits.max_volatility:
            excess = metrics.portfolio_volatility / self.limits.max_volatility - 1
            multiplier *= max(0.3, 1.0 - excess * 0.3)
        
        # Correlation violation
        if metrics.avg_correlation > self.limits.max_correlation:
            excess = (metrics.avg_correlation - self.limits.max_correlation) / (1 - self.limits.max_correlation)
            multiplier *= max(0.5, 1.0 - excess * 0.3)
        
        # Concentration violation
        if metrics.hhi > self.limits.max_hhi:
            excess = (metrics.hhi - self.limits.max_hhi) / (1 - self.limits.max_hhi)
            multiplier *= max(0.5, 1.0 - excess * 0.5)
        
        # Apply multiplier limits
        multiplier = max(self.limits.min_risk_multiplier, min(1.0, multiplier))
        
        return multiplier
    
    def _update_state(self, metrics: RiskMetrics, timestamp: datetime) -> None:
        """Update internal state based on metrics."""
        # Update drawdown tracking
        if metrics.current_drawdown < self._drawdown_peak:
            self._drawdown_peak = metrics.current_drawdown
            if self._drawdown_start is None:
                self._drawdown_start = timestamp
        
        # Check for recovery
        if self._drawdown_start is not None and metrics.current_drawdown > self.limits.drawdown_recovery_threshold:
            self._recovery_start = timestamp
    
    def get_state(self) -> Dict[str, Any]:
        """Get current risk state."""
        return {
            'mode': self.mode,
            'current_metrics': self._current_metrics.to_dict() if self._current_metrics else None,
            'last_decision': self._last_decision.to_dict() if self._last_decision else None,
            'drawdown_peak': self._drawdown_peak,
            'drawdown_start': self._drawdown_start,
            'recovery_start': self._recovery_start,
            'decision_count': len(self._decision_history),
            'recent_decisions': [d.to_dict() for d in self._decision_history[-5:]],
        }
    
    def get_risk_report(self) -> Dict[str, Any]:
        """Generate a comprehensive risk report."""
        if not self._history:
            return {'error': 'No risk data available'}
        
        # Calculate risk statistics
        decisions = [h['decision'] for h in self._history]
        metrics = [h['metrics'] for h in self._history]
        
        halted = sum(1 for d in decisions if not d['allowed'])
        reduced = sum(1 for d in decisions if d.get('risk_multiplier', 1.0) < 1.0 and d['allowed'])
        
        return {
            'total_evaluations': len(self._history),
            'halted_count': halted,
            'reduced_count': reduced,
            'halt_rate': halted / len(self._history) if self._history else 0,
            'avg_risk_multiplier': np.mean([d.get('risk_multiplier', 1.0) for d in decisions]) if decisions else 1.0,
            'avg_exposure': np.mean([m['gross_exposure'] for m in metrics]) if metrics else 0,
            'max_exposure': max([m['gross_exposure'] for m in metrics]) if metrics else 0,
            'avg_drawdown': np.mean([m['current_drawdown'] for m in metrics]) if metrics else 0,
            'max_drawdown': min([m['current_drawdown'] for m in metrics]) if metrics else 0,
            'current_state': self.get_state(),
        }
    
    def reset(self) -> None:
        """Reset risk engine state."""
        self._history = []
        self._decision_history = []
        self._current_metrics = None
        self._last_decision = None
        self._drawdown_peak = 0.0
        self._drawdown_start = None
        self._recovery_start = None
        logger.info("RiskEngine state reset")
    
    def set_limits(self, limits: RiskLimits) -> None:
        """Update risk limits."""
        self.limits = limits
        logger.info(f"Risk limits updated: {limits.to_dict()}")
    
    def set_mode(self, mode: str) -> None:
        """Set trading mode and update limits accordingly."""
        self.mode = mode
        if mode in DEFAULT_LIMITS:
            self.limits = DEFAULT_LIMITS[mode]
        logger.info(f"Risk mode set to {mode}")
