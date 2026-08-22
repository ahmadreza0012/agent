"""
Kill Switch API Routes - FastAPI endpoints for kill switch control.

This module provides REST API endpoints for triggering, resuming, and monitoring
the kill switch system.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

try:
    from fastapi import APIRouter, HTTPException
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    APIRouter = object
    HTTPException = Exception

from execution.kill_switch_models import KillSwitchLevel, KillSwitchTrigger

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/kill-switch", tags=["kill-switch"])


class KillSwitchRequest(BaseModel):
    """Request model for triggering kill switch."""
    level: str = Field(..., description="Kill switch level: normal, pause, derisk, halt, emergency")
    trigger: str = Field(default="manual", description="Trigger reason")
    reason: str = Field(..., description="Human-readable reason")
    triggered_by: str = Field(default="api_user", description="Who triggered it")


class ResumeRequest(BaseModel):
    """Request model for resuming trading."""
    reason: str = Field(..., description="Reason for resumption")
    resolved_by: str = Field(default="api_user", description="Who authorized resumption")


class KillSwitchStatusResponse(BaseModel):
    """Response model for kill switch status."""
    level: str
    is_triggered: bool
    last_trigger: Optional[Dict[str, Any]]
    history_count: int
    trading_allowed: bool
    timestamp: str


class KillSwitchActionResponse(BaseModel):
    """Response model for kill switch actions."""
    success: bool
    level: str
    message: str
    timestamp: str
    actions_taken: list
    requires_review: bool


@router.post("/trigger", response_model=KillSwitchActionResponse)
async def trigger_kill_switch(request: KillSwitchRequest):
    """
    Trigger the kill switch via API.
    
    This endpoint allows manual triggering of the kill switch at any level.
    Requires appropriate authorization in production.
    
    Args:
        request: KillSwitchRequest with level, trigger, reason, triggered_by
    
    Returns:
        KillSwitchActionResponse with operation result
    
    Raises:
        HTTPException: If invalid level or trigger specified
    """
    # Validate level
    try:
        level = KillSwitchLevel(request.level.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid level: {request.level}. Must be one of: {[l.value for l in KillSwitchLevel]}"
        )
    
    # Validate trigger
    try:
        trigger = KillSwitchTrigger(request.trigger.lower())
    except ValueError:
        # Default to MANUAL if not recognized
        trigger = KillSwitchTrigger.MANUAL
        logger.warning(f"Unknown trigger '{request.trigger}', defaulting to MANUAL")
    
    # Get kill switch from app state (injected by FastAPI app)
    kill_switch = getattr(router, 'kill_switch', None)
    if not kill_switch:
        raise HTTPException(status_code=503, detail="Kill switch not initialized")
    
    # Trigger the kill switch
    response = kill_switch.trigger(
        level=level,
        trigger=trigger,
        reason=request.reason,
        details={"api_request": True},
        triggered_by=request.triggered_by
    )
    
    return KillSwitchActionResponse(
        success=response.success,
        level=response.level.value,
        message=response.message,
        timestamp=response.timestamp.isoformat(),
        actions_taken=response.actions_taken,
        requires_review=response.requires_review
    )


@router.post("/resume", response_model=KillSwitchActionResponse)
async def resume_trading(request: ResumeRequest):
    """
    Resume trading after kill switch activation.
    
    Note: HALT and EMERGENCY levels require manual review and cannot be
    resumed via API without proper authorization.
    
    Args:
        request: ResumeRequest with reason and resolved_by
    
    Returns:
        KillSwitchActionResponse with operation result
    
    Raises:
        HTTPException: If resume fails or requires manual review
    """
    kill_switch = getattr(router, 'kill_switch', None)
    if not kill_switch:
        raise HTTPException(status_code=503, detail="Kill switch not initialized")
    
    # Attempt to resume
    response = kill_switch.resume(
        reason=request.reason,
        resolved_by=request.resolved_by
    )
    
    if not response.success:
        if response.requires_review:
            raise HTTPException(
                status_code=403,
                detail=f"{response.message}. Manual review required."
            )
        else:
            raise HTTPException(status_code=400, detail=response.message)
    
    return KillSwitchActionResponse(
        success=response.success,
        level=response.level.value,
        message=response.message,
        timestamp=response.timestamp.isoformat(),
        actions_taken=response.actions_taken,
        requires_review=response.requires_review
    )


@router.get("/status", response_model=KillSwitchStatusResponse)
async def get_kill_switch_status():
    """
    Get current kill switch status.
    
    Returns:
        KillSwitchStatusResponse with current state information
    
    Raises:
        HTTPException: If kill switch not initialized
    """
    kill_switch = getattr(router, 'kill_switch', None)
    if not kill_switch:
        raise HTTPException(status_code=503, detail="Kill switch not initialized")
    
    state = kill_switch.get_state()
    
    return KillSwitchStatusResponse(
        level=state.level.value,
        is_triggered=state.is_triggered,
        last_trigger=state.last_trigger.to_dict() if state.last_trigger else None,
        history_count=len(state.history),
        trading_allowed=kill_switch.is_trading_allowed(),
        timestamp=state.timestamp.isoformat()
    )


@router.post("/emergency-stop", response_model=KillSwitchActionResponse)
async def emergency_stop(reason: str = "Emergency stop via API", triggered_by: str = "api_emergency"):
    """
    Emergency stop - bypasses validation to guarantee execution.
    
    This endpoint should only be used in genuine emergencies when the system
    is broken and normal shutdown procedures have failed.
    
    Args:
        reason: Reason for emergency stop
        triggered_by: Who triggered it
    
    Returns:
        KillSwitchActionResponse with operation result
    
    Raises:
        HTTPException: If kill switch not initialized
    """
    kill_switch = getattr(router, 'kill_switch', None)
    if not kill_switch:
        raise HTTPException(status_code=503, detail="Kill switch not initialized")
    
    # Direct emergency trigger - minimal validation
    response = kill_switch.trigger(
        level=KillSwitchLevel.EMERGENCY,
        trigger=KillSwitchTrigger.MANUAL,
        reason=reason,
        details={"emergency_api": True, "bypass_validation": True},
        triggered_by=triggered_by
    )
    
    return KillSwitchActionResponse(
        success=response.success,
        level=response.level.value,
        message=response.message,
        timestamp=response.timestamp.isoformat(),
        actions_taken=response.actions_taken,
        requires_review=True  # Always requires review after emergency
    )


def setup_kill_switch_router(kill_switch_instance):
    """
    Configure the router with a kill switch instance.
    
    This function should be called during FastAPI app initialization.
    
    Args:
        kill_switch_instance: The KillSwitch instance to use
    
    Returns:
        The configured router
    """
    router.kill_switch = kill_switch_instance
    logger.info("Kill switch router configured")
    return router
