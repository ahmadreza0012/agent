"""
Orders Routes - Order management.

CRITICAL SECURITY NOTE:
This endpoint is for PAPER TRADING ONLY. It does NOT execute real exchange orders.
For live trading, orders must flow through the canonical execution pipeline:
    Signal → Portfolio Target → Order Intent → Risk Engine → Live Safety Engine 
    → Kill Switch → Circuit Breaker → Order Manager → Exchange Adapter
"""

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
import logging

from ..models import OrderRequest, OrderResponse, OrderSide, OrderType, OrderStatus
from ..middleware import AuthMiddleware

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("", response_model=OrderResponse)
async def create_order(request: OrderRequest):
    """
    Create a new order (PAPER TRADING ONLY).
    
    CRITICAL: This endpoint does NOT execute real exchange orders.
    It returns a mock response for testing purposes only.
    
    For live trading, use the canonical execution pipeline through the main trading loop.
    Direct API order creation bypasses critical safety checks and is disabled in production.
    """
    logger.warning(
        f"PAPER ORDER REQUEST: {request.side.value} {request.amount} {request.symbol} "
        f"- This is NOT a real order. Live orders require canonical execution pipeline."
    )
    
    # Return mock response for paper/testing mode only
    return OrderResponse(
        id=f"paper_order_{datetime.now(timezone.utc).timestamp()}",
        client_order_id=f"client_{datetime.now(timezone.utc).timestamp()}",
        symbol=request.symbol,
        side=request.side,
        order_type=request.order_type,
        price=request.price or 0.0,
        amount=request.amount,
        filled_amount=0.0,  # Not filled - this is paper only
        status=OrderStatus.PENDING,  # Not FILLED - paper orders need simulation
        fee=0.0,
        fee_currency='USDT',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        is_paper_order=True  # Explicitly mark as paper order
    )


@router.get("", response_model=List[OrderResponse])
async def get_orders(status_filter: Optional[OrderStatus] = None, symbol: Optional[str] = None):
    """Get orders."""
    # Mock orders for testing
    return []


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str):
    """Get order by ID."""
    # Mock order lookup
    raise HTTPException(status_code=404, detail=f"Order {order_id} not found")


@router.delete("/{order_id}")
async def cancel_order(order_id: str):
    """Cancel an order."""
    # Mock order cancellation
    raise HTTPException(status_code=404, detail=f"Order {order_id} not found or couldn't be cancelled")
