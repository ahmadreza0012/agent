"""
Core domain module.

Provides fundamental domain models and interfaces for the trading system.
"""

from .models import Order, Position, Balance, Trade, Signal
from .models import OrderSide, OrderType, OrderStatus, TradingMode
from .interfaces import (
    DataProvider,
    Strategy,
    RiskEngine,
    ExchangeAdapter,
    PortfolioOptimizer,
    RegimeDetector,
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
]