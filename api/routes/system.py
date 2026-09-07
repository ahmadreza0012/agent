"""
System Routes - System control operations.

CRITICAL SECURITY NOTE:
These endpoints are MOCK implementations for testing purposes only.
They do NOT actually control the trading system.

For production system control, use:
1. The KillSwitchManager in execution/kill_switch_manager.py
2. The LiveSafetyEngine in execution/live_safety_engine.py
3. Environment-based configuration
4. Process supervisors (systemd, Docker, etc.)

Direct API control of trading processes is intentionally disabled for safety.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
import logging
import os

from ..models import SystemControlRequest, SystemControlResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["System"])


def _require_admin_auth():
    """Require explicit admin authentication for system control."""
    admin_token = os.getenv("ADMIN_CONTROL_TOKEN")
    if not admin_token or admin_token == "change-me-in-production":
        raise HTTPException(
            status_code=503,
            detail="System control is disabled. Set ADMIN_CONTROL_TOKEN environment variable to enable."
        )
    return admin_token


@router.post("/pause", response_model=SystemControlResponse)
async def pause_system(request: SystemControlRequest, admin_token: str = Depends(_require_admin_auth)):
    """Pause trading (MOCK - does not actually pause)."""
    logger.warning(f"PAUSE REQUEST (MOCK): {request.reason}")
    return SystemControlResponse(
        success=False,
        action="pause_mock",
        message=f"Pause request logged but NOT executed. Use KillSwitchManager.",
        timestamp=datetime.now(timezone.utc)
    )


@router.post("/resume", response_model=SystemControlResponse)
async def resume_system(request: SystemControlRequest, admin_token: str = Depends(_require_admin_auth)):
    """Resume trading (MOCK - does not actually resume)."""
    logger.warning(f"RESUME REQUEST (MOCK): {request.reason}")
    return SystemControlResponse(
        success=False,
        action="resume_mock",
        message=f"Resume request logged but NOT executed. Use KillSwitchManager.",
        timestamp=datetime.now(timezone.utc)
    )


@router.post("/halt", response_model=SystemControlResponse)
async def halt_system(request: SystemControlRequest, admin_token: str = Depends(_require_admin_auth)):
    """Halt trading (MOCK - does not actually halt)."""
    logger.critical(f"HALT REQUEST (MOCK): {request.reason}")
    return SystemControlResponse(
        success=False,
        action="halt_mock",
        message=f"Halt request logged but NOT executed. Use KillSwitchManager directly.",
        timestamp=datetime.now(timezone.utc)
    )


@router.post("/kill", response_model=SystemControlResponse)
async def emergency_kill(request: SystemControlRequest, admin_token: str = Depends(_require_admin_auth)):
    """Emergency kill (MOCK - does not terminate process)."""
    logger.critical(f"KILL REQUEST (MOCK): {request.reason}")
    return SystemControlResponse(
        success=False,
        action="kill_mock",
        message=f"Kill request logged but NOT executed. Terminate via supervisor.",
        timestamp=datetime.now(timezone.utc)
    )


@router.post("/rebalance")
async def trigger_rebalance(request: SystemControlRequest, admin_token: str = Depends(_require_admin_auth)):
    """Trigger rebalance (MOCK)."""
    logger.info(f"REBALANCE REQUEST (MOCK): {request.reason}")
    return {"success": False, "message": "Rebalance request logged but NOT executed."}


@router.get("/config")
async def get_config():
    """Get system configuration (sanitized)."""
    return {
        "mode": os.getenv("TRADING_MODE", "paper"),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "limits": {
            "max_daily_loss": float(os.getenv("MAX_DAILY_LOSS_PCT", "0.05")),
            "max_drawdown": float(os.getenv("MAX_DRAWDOWN_PCT", "0.15")),
        },
        "version": "2.0.0",
        "safety_note": "Live trading requires TRADING_MODE=live and LIVE_TRADING_ENABLED=true"
    }
