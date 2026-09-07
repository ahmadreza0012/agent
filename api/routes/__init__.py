"""
API Routes module.
"""

from .health import router as health_router
from .status import router as status_router
from .portfolio import router as portfolio_router
from .orders import router as orders_router
from .risk import router as risk_router
from .strategy import router as strategy_router
from .system import router as system_router
from .metrics import router as metrics_router

__all__ = [
    'health_router',
    'status_router',
    'portfolio_router',
    'orders_router',
    'risk_router',
    'strategy_router',
    'system_router',
    'metrics_router',
]
