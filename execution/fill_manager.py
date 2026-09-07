"""
Fill Manager - Processes and reconciles order fills.

This module handles fill events, tracks filled amounts, detects partial fills,
updates positions based on fills, and calculates fees.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

from .exchange_adapter import Order, OrderStatus, OrderSide
from .position_manager import PositionManager
from .order_manager import OrderManager

logger = logging.getLogger(__name__)


@dataclass
class Fill:
    """Represents a single fill event."""
    order_id: str
    fill_id: str
    timestamp: datetime
    price: float
    amount: float
    fee: float = 0.0
    fee_currency: str = ''
    is_maker: bool = False
    
    @property
    def notional_value(self) -> float:
        """Calculate notional value of the fill."""
        return self.price * self.amount


class FillManager:
    """Processes and tracks order fills."""
    
    def __init__(
        self,
        position_manager: PositionManager,
        order_manager: OrderManager,
        default_fee_rate: float = 0.001,
    ):
        """
        Initialize the Fill Manager.
        
        Args:
            position_manager: Position manager instance for updating positions.
            order_manager: Order manager instance for tracking orders.
            default_fee_rate: Default fee rate (e.g., 0.001 = 0.1%).
        """
        self.position_manager = position_manager
        self.order_manager = order_manager
        self.default_fee_rate = default_fee_rate
        self.fills: Dict[str, List[Fill]] = {}  # order_id -> list of fills
        logger.info("FillManager initialized")
    
    def process_fill(
        self,
        order: Order,
        fill_data: Dict[str, Any],
        current_price: Optional[float] = None,
    ) -> Fill:
        """
        Process a fill event.
        
        Args:
            order: Order object associated with the fill.
            fill_data: Dictionary containing fill information.
                      Expected keys: price, amount, fee (optional), timestamp (optional)
            current_price: Current market price for PnL calculation.
        
        Returns:
            Fill object representing the processed fill.
        """
        # Extract fill information
        fill_price = fill_data.get('price', order.price or 0.0)
        fill_amount = fill_data.get('amount', 0.0)
        fill_info = fill_data.get('fee', {})
        fill_fee = fill_info.get('cost', 0.0) if isinstance(fill_info, dict) else 0.0
        fill_fee_currency = fill_info.get('currency', '') if isinstance(fill_info, dict) else ''
        is_maker = fill_data.get('maker', False)
        
        # Generate fill ID
        fill_id = f"{order.id}_{len(self.fills.get(order.id, [])) + 1}"
        fill_timestamp = fill_data.get('timestamp', datetime.now())
        if isinstance(fill_timestamp, (int, float)):
            fill_timestamp = datetime.fromtimestamp(fill_timestamp / 1000)
        
        # Create Fill object
        fill = Fill(
            order_id=order.id,
            fill_id=fill_id,
            timestamp=fill_timestamp if isinstance(fill_timestamp, datetime) else datetime.now(),
            price=fill_price,
            amount=fill_amount,
            fee=fill_fee,
            fee_currency=fill_fee_currency,
            is_maker=is_maker,
        )
        
        # Store fill
        if order.id not in self.fills:
            self.fills[order.id] = []
        self.fills[order.id].append(fill)
        
        # Update position
        try:
            self.position_manager.update_position(
                symbol=order.symbol,
                fill_price=fill_price,
                fill_amount=fill_amount,
                side=order.side,
                current_price=current_price,
            )
        except Exception as e:
            logger.error(f"Failed to update position for fill {fill_id}: {e}")
            raise
        
        logger.info(
            f"Fill processed: {fill_id} | {order.symbol} | {fill_amount} @ {fill_price} | "
            f"Fee: {fill_fee} {fill_fee_currency}"
        )
        
        return fill
    
    def get_fills(self, order_id: str) -> List[Fill]:
        """
        Get all fills for an order.
        
        Args:
            order_id: Order ID.
        
        Returns:
            List of Fill objects.
        """
        return self.fills.get(order_id, [])
    
    def calculate_fee(self, order: Order, fill_data: Dict[str, Any]) -> float:
        """
        Calculate fee for a fill.
        
        Args:
            order: Order object.
            fill_data: Fill information dictionary.
        
        Returns:
            Calculated fee amount.
        """
        # If fee is provided in fill data, use it
        fill_info = fill_data.get('fee', {})
        if isinstance(fill_info, dict) and 'cost' in fill_info:
            return fill_info['cost']
        
        # Otherwise calculate using fee rate
        fill_amount = fill_data.get('amount', 0.0)
        fill_price = fill_data.get('price', order.price or 0.0)
        notional_value = fill_amount * fill_price
        
        # Apply maker/taker fee rates if available
        if fill_data.get('maker', False):
            fee_rate = self.default_fee_rate * 0.8  # Maker discount
        else:
            fee_rate = self.default_fee_rate
        
        return notional_value * fee_rate
    
    def is_order_fully_filled(self, order: Order) -> bool:
        """
        Check if an order is fully filled.
        
        Args:
            order: Order object.
        
        Returns:
            True if order is fully filled.
        """
        # Check order status first
        if order.status == OrderStatus.FILLED:
            return True
        
        # Check if filled amount equals order amount
        if order.filled_amount >= order.amount:
            return True
        
        # Check accumulated fills
        fills = self.get_fills(order.id)
        total_filled = sum(f.amount for f in fills)
        return total_filled >= order.amount
    
    def get_total_filled(self, order_id: str) -> float:
        """
        Get total filled amount for an order.
        
        Args:
            order_id: Order ID.
        
        Returns:
            Total filled amount.
        """
        fills = self.fills.get(order_id, [])
        return sum(f.amount for f in fills)
    
    def get_total_fees(self, order_id: str, currency: Optional[str] = None) -> float:
        """
        Get total fees paid for an order.
        
        Args:
            order_id: Order ID.
            currency: Optional currency filter.
        
        Returns:
            Total fees paid.
        """
        fills = self.fills.get(order_id, [])
        if currency:
            return sum(f.fee for f in fills if f.fee_currency == currency)
        return sum(f.fee for f in fills)
    
    def get_partial_fill_info(self, order: Order) -> Optional[Dict[str, Any]]:
        """
        Get information about partial fills for an order.
        
        Args:
            order: Order object.
        
        Returns:
            Dictionary with partial fill information, or None if not partially filled.
        """
        if order.status != OrderStatus.PARTIALLY_FILLED:
            return None
        
        fills = self.get_fills(order.id)
        total_filled = sum(f.amount for f in fills)
        remaining = order.amount - total_filled
        
        return {
            'order_id': order.id,
            'total_amount': order.amount,
            'filled_amount': total_filled,
            'remaining_amount': remaining,
            'fill_count': len(fills),
            'average_fill_price': sum(f.price * f.amount for f in fills) / total_filled if total_filled > 0 else 0,
            'is_complete': remaining <= 0,
        }
    
    def reconcile_order(self, order: Order) -> bool:
        """
        Reconcile local fill records with order state.
        
        Args:
            order: Order object.
        
        Returns:
            True if reconciliation successful.
        """
        local_filled = self.get_total_filled(order.id)
        
        # Check if local fills match order's filled amount
        if abs(local_filled - order.filled_amount) > 0.000001:
            logger.warning(
                f"Fill reconciliation mismatch for {order.id}: "
                f"local={local_filled}, exchange={order.filled_amount}"
            )
            return False
        
        return True