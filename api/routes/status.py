"""
Status Routes - System status information.
"""

from datetime import datetime
from fastapi import APIRouter

from ..models import SystemStatusResponse

router = APIRouter(prefix="/status", tags=["Status"])


@router.get("", response_model=SystemStatusResponse)
async def get_status():
    """Get current system status."""
    # Mock status for testing
    return SystemStatusResponse(
        mode="paper",
        trading_allowed=True,
        kill_switch_active=False,
        circuit_breaker_state="normal",
        reconciliation_state="consistent",
        last_update=datetime.now(),
        daily_pnl=0.0,
        current_drawdown=0.0,
        exposure_ratio=0.0,
        active_positions=0,
        open_orders=0
    )
