"""
Health Routes - System health checks.
"""

import time
from datetime import datetime
from fastapi import APIRouter
from typing import Dict

from ..models import HealthResponse, HealthStatus

router = APIRouter(prefix="/health", tags=["Health"])
_start_time = time.time()


@router.get("", response_model=HealthResponse)
async def health_check():
    """Check system health."""
    # Mock components for testing
    components = {
        "database": True,
        "exchange": True,
        "engine": True,
    }
    
    status = HealthStatus.HEALTHY
    uptime = time.time() - _start_time
    
    return HealthResponse(
        status=status,
        version="2.0.0",
        uptime_seconds=uptime,
        components=components,
        timestamp=datetime.now()
    )


@router.get("/live")
async def liveness():
    """Kubernetes liveness probe."""
    return {"status": "alive"}


@router.get("/ready")
async def readiness():
    """Kubernetes readiness probe."""
    # Mock readiness check
    return {"status": "ready"}
