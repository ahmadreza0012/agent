"""
Metrics Routes - Prometheus metrics endpoint and performance data.
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Response, Query
from typing import List

from ..models import PerformanceMetricsResponse, DailySnapshotResponse

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("")
async def get_prometheus_metrics():
    """Get Prometheus metrics."""
    from ...observability import get_observability
    obs = get_observability()
    metrics_data = obs.get_metrics()
    return Response(content=metrics_data, media_type="text/plain")


@router.get("/performance", response_model=PerformanceMetricsResponse)
async def get_performance_metrics(
    days: int = Query(30, ge=1, le=365)
):
    """Get performance metrics."""
    now = datetime.now()
    return PerformanceMetricsResponse(
        total_return=0.0,
        annualized_return=0.0,
        volatility=0.0,
        sharpe_ratio=0.0,
        sortino_ratio=0.0,
        max_drawdown=0.0,
        win_rate=0.0,
        profit_factor=0.0,
        total_fees=0.0,
        total_slippage=0.0,
        turnover=0.0,
        num_trades=0,
        period_start=now - timedelta(days=days),
        period_end=now
    )


@router.get("/daily", response_model=List[DailySnapshotResponse])
async def get_daily_snapshots(
    days: int = Query(30, ge=1, le=365)
):
    """Get daily snapshots."""
    # Mock daily snapshots
    return []


@router.get("/audit")
async def get_audit_events(limit: int = 50):
    """Get recent audit events."""
    from ...observability import get_observability
    obs = get_observability()
    events = obs.get_audit_events(limit=limit)
    return {"events": events, "count": len(events)}
