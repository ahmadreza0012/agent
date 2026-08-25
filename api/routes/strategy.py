"""
Strategy Routes - Strategy information and control.
"""

from datetime import datetime
from fastapi import APIRouter

router = APIRouter(prefix="/strategy", tags=["Strategy"])


@router.get("/status")
async def get_strategy_status():
    """Get current strategy status."""
    return {
        "active_strategies": [],
        "weights": {},
        "last_signal": None,
        "timestamp": datetime.now()
    }


@router.get("/performance")
async def get_strategy_performance():
    """Get strategy performance metrics."""
    return {
        "strategies": [],
        "timestamp": datetime.now()
    }
