"""
Portfolio Routes - Portfolio and position information.
"""

from datetime import datetime
from fastapi import APIRouter, Query
from typing import List, Optional

from ..models import PortfolioResponse, PositionResponse

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


@router.get("", response_model=PortfolioResponse)
async def get_portfolio():
    """Get current portfolio state."""
    # Mock portfolio for testing
    return PortfolioResponse(
        total_equity=100000.0,
        cash=50000.0,
        positions_value=50000.0,
        positions=[],
        weights={},
        timestamp=datetime.now()
    )


@router.get("/positions")
async def get_positions(symbol: Optional[str] = None):
    """Get current positions."""
    # Mock positions for testing
    return []


@router.get("/history")
async def get_portfolio_history(days: int = Query(30, ge=1, le=365)):
    """Get portfolio history."""
    # Would fetch from database
    return {"days": days, "history": []}
