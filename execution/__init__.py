"""
Execution Engine - Production-grade cryptocurrency trading execution layer.

This module provides a safe, reliable, and production-grade interface to cryptocurrency exchanges.
"""

from .exchange_adapter import (
    ExchangeAdapter,
    CCXTExchangeAdapter,
    Order,
    OrderSide,
    OrderType,
    OrderStatus,
    Position,
    Balance,
    Ticker,
)
from .order_manager import OrderManager
from .position_manager import PositionManager, PositionLimits
from .fill_manager import FillManager, Fill
from .reconciler import (
    PortfolioReconciler,
    ReconciliationResult,
    PositionMismatch,
    BalanceMismatch,
)

__all__ = [
    # Exchange Adapter
    'ExchangeAdapter',
    'CCXTExchangeAdapter',
    'Order',
    'OrderSide',
    'OrderType',
    'OrderStatus',
    'Position',
    'Balance',
    'Ticker',
    # Order Manager
    'OrderManager',
    # Position Manager
    'PositionManager',
    'PositionLimits',
    # Fill Manager
    'FillManager',
    'Fill',
    # Reconciler
    'PortfolioReconciler',
    'ReconciliationResult',
    'PositionMismatch',
    'BalanceMismatch',
]