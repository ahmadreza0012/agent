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
# Phase 17: Idempotency & Order Recovery
from .order_registry import OrderRegistry
from .order_state_manager import OrderStateManager, StateTransition, OrderStateMachine
from .order_recovery import OrderRecovery, Discrepancy, RecoveryResult, RecoveryAction
from .atomic_operations import AtomicOperations, AtomicOrder, AtomicOperationResult, AtomicOperationStatus
# Phase 19: Kill Switch
from .kill_switch_models import (
    KillSwitchLevel,
    KillSwitchTrigger,
    KillSwitchEvent,
    KillSwitchState,
    KillSwitchResponse,
)
from .kill_switch import KillSwitch
from .kill_switch_manager import KillSwitchManager
# Phase 20: Paper & Shadow Trading
from .trading_modes import TradingMode, TradingConfig
from .paper_adapter import PaperTradingAdapter
from .shadow_adapter import ShadowTradingAdapter
from .mode_manager import TradingModeManager, ModeTransitionError
from .mode_factory import ModeFactory

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
    # Phase 17: Idempotency & Order Recovery
    'OrderRegistry',
    'OrderStateManager',
    'StateTransition',
    'OrderStateMachine',
    'OrderRecovery',
    'Discrepancy',
    'RecoveryResult',
    'RecoveryAction',
    'AtomicOperations',
    'AtomicOrder',
    'AtomicOperationResult',
    'AtomicOperationStatus',
    # Phase 19: Kill Switch
    'KillSwitchLevel',
    'KillSwitchTrigger',
    'KillSwitchEvent',
    'KillSwitchState',
    'KillSwitchResponse',
    'KillSwitch',
    'KillSwitchManager',
    # Phase 20: Paper & Shadow Trading
    'TradingMode',
    'TradingConfig',
    'PaperTradingAdapter',
    'ShadowTradingAdapter',
    'TradingModeManager',
    'ModeTransitionError',
    'ModeFactory',
]