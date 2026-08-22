"""
Orders Routes - Order management.
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException
from typing import List, Optional

from ..models import OrderRequest, OrderResponse, OrderSide, OrderType, OrderStatus

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("", response_model=OrderResponse)
async def create_order(request: OrderRequest):
    """Create a new order."""
    # Mock order creation for testing
    return OrderResponse(
        id=f"order_{datetime.now().timestamp()}",
        client_order_id=f"client_{datetime.now().timestamp()}",
        symbol=request.symbol,
        side=request.side,
        order_type=request.order_type,
        price=request.price or 0.0,
        amount=request.amount,
        filled_amount=request.amount,
        status=OrderStatus.FILLED,
        fee=0.0,
        fee_currency='USDT',
        created_at=datetime.now(),
        updated_at=datetime.now()
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
