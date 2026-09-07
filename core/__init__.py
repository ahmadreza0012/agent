"""
Core module.

Provides fundamental domain models, interfaces, and configuration for the trading system.
"""

import warnings

# Domain models
from .domain.models import Order, Position, Balance, Trade, Signal
from .domain.models import OrderSide, OrderType, OrderStatus, TradingMode

# Domain interfaces
from .domain.interfaces import (
    DataProvider,
    Strategy,
    RiskEngine,
    ExchangeAdapter,
    PortfolioOptimizer,
    RegimeDetector,
)

# Configuration
from .config.settings import (
    RISK_FREE_RATE,
    DEFAULT_TRADING_MODE,
    LIVE_THRESHOLDS,
    RESEARCH_THRESHOLDS,
    MAKER_FEE,
    TAKER_FEE,
    get_trading_mode,
    is_live_mode,
    is_paper_mode,
    is_research_mode,
)

__all__ = [
    # Models
    'Order',
    'Position',
    'Balance',
    'Trade',
    'Signal',
    # Enums
    'OrderSide',
    'OrderType',
    'OrderStatus',
    'TradingMode',
    # Interfaces
    'DataProvider',
    'Strategy',
    'RiskEngine',
    'ExchangeAdapter',
    'PortfolioOptimizer',
    'RegimeDetector',
    # Configuration
    'RISK_FREE_RATE',
    'DEFAULT_TRADING_MODE',
    'LIVE_THRESHOLDS',
    'RESEARCH_THRESHOLDS',
    'MAKER_FEE',
    'TAKER_FEE',
    'get_trading_mode',
    'is_live_mode',
    'is_paper_mode',
    'is_research_mode',
]


def __getattr__(name):
    """
    Provide backward compatibility for old import paths.
    
    This allows existing code to continue working while warning about deprecated imports.
    """
    # Deprecated root-level imports - forward to new locations
    if name in ['Order', 'Position', 'Balance']:
        warnings.warn(
            f"Importing {name} from core is deprecated. "
            f"Please use 'from core.domain.models import {name}'.",
            DeprecationWarning,
            stacklevel=2
        )
        return globals()[name]
    
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
