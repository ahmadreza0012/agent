"""
Risk Limits Configuration
=========================
Configurable risk limits for the Risk Engine.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any


@dataclass
class RiskLimits:
    """Risk limit configuration."""
    
    # Exposure limits
    max_gross_exposure: float = 1.0  # 100% max gross exposure
    max_net_exposure: float = 0.8    # 80% max net exposure
    
    # Position limits
    max_single_position: float = 0.20  # 20% max per asset
    max_position_adv: float = 0.01     # 1% of average daily volume
    
    # Volatility limits
    max_volatility: float = 0.50       # 50% annualized volatility
    max_volatility_multiplier: float = 2.0  # 2x baseline
    
    # Drawdown limits
    max_drawdown: float = 0.12         # 12% max drawdown
    max_drawdown_daily: float = 0.03   # 3% max daily loss
    
    # Correlation limits
    max_correlation: float = 0.80      # 80% max avg correlation
    
    # Liquidity limits
    min_liquidity: float = 10000       # $10,000 minimum daily volume
    max_spread: float = 0.01           # 1% max spread
    
    # Concentration limits
    max_hhi: float = 0.25              # 25% Herfindahl-Hirschman Index
    
    # Risk multiplier limits
    min_risk_multiplier: float = 0.0   # 0 = halt
    max_risk_multiplier: float = 1.0   # 1 = normal
    
    # Recovery thresholds
    drawdown_recovery_threshold: float = 0.05  # 5% recovery to resume
    daily_loss_recovery_threshold: float = 0.01  # 1% recovery to resume
    
    # Time-based limits
    max_consecutive_losses: int = 5    # Max consecutive losing days
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {k: v for k, v in self.__dict__.items()}
    
    def update(self, **kwargs) -> 'RiskLimits':
        """Update limits with kwargs."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self


# Default limits for different trading modes
DEFAULT_LIMITS = {
    'research': RiskLimits(
        max_drawdown=0.25,
        max_single_position=0.40,
        max_gross_exposure=1.5,
        max_volatility=0.80,
    ),
    'paper': RiskLimits(
        max_drawdown=0.15,
        max_single_position=0.30,
        max_gross_exposure=1.0,
        max_volatility=0.60,
    ),
    'live': RiskLimits(
        max_drawdown=0.10,
        max_single_position=0.20,
        max_gross_exposure=0.8,
        max_volatility=0.50,
        max_hhi=0.20,
    ),
    'conservative': RiskLimits(
        max_drawdown=0.05,
        max_single_position=0.10,
        max_gross_exposure=0.5,
        max_volatility=0.30,
        max_hhi=0.15,
        max_correlation=0.60,
    ),
    'aggressive': RiskLimits(
        max_drawdown=0.20,
        max_single_position=0.30,
        max_gross_exposure=1.5,
        max_volatility=0.70,
        max_hhi=0.35,
        max_correlation=0.90,
    ),
}
