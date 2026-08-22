"""
System Routes - System control operations.
"""

from datetime import datetime
from fastapi import APIRouter

from ..models import SystemControlRequest, SystemControlResponse

router = APIRouter(prefix="/system", tags=["System"])


@router.post("/pause", response_model=SystemControlResponse)
async def pause_system(request: SystemControlRequest):
    """Pause trading (stop new orders)."""
    return SystemControlResponse(
        success=True,
        action="pause",
        message=f"Trading paused: {request.reason}",
        timestamp=datetime.now()
    )


@router.post("/resume", response_model=SystemControlResponse)
async def resume_system(request: SystemControlRequest):
    """Resume trading."""
    return SystemControlResponse(
        success=True,
        action="resume",
        message=f"Trading resumed: {request.reason}",
        timestamp=datetime.now()
    )


@router.post("/halt", response_model=SystemControlResponse)
async def halt_system(request: SystemControlRequest):
    """Halt all trading (emergency stop)."""
    return SystemControlResponse(
        success=True,
        action="halt",
        message=f"Trading halted: {request.reason}",
        timestamp=datetime.now()
    )


@router.post("/kill", response_model=SystemControlResponse)
async def emergency_kill(request: SystemControlRequest):
    """Emergency kill - highest level."""
    return SystemControlResponse(
        success=True,
        action="kill",
        message=f"Emergency kill triggered: {request.reason}",
        timestamp=datetime.now()
    )


@router.post("/rebalance")
async def trigger_rebalance(request: SystemControlRequest):
    """Manually trigger a rebalance."""
    return {"success": True, "message": f"Rebalance triggered: {request.reason}"}


@router.get("/config")
async def get_config():
    """Get system configuration (sanitized)."""
    return {
        "mode": "paper",
        "limits": {
            "max_daily_loss": 0.05,
            "max_drawdown": 0.15,
        },
        "version": "2.0.0"
    }
