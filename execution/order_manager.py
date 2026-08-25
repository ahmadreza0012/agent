"""
Order Manager - Tracks and manages order lifecycle.

This module handles order creation, tracking, idempotency, and status management.
It ensures that orders are properly tracked from creation to completion.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set
import logging

from .exchange_adapter import Order, OrderSide, OrderType, OrderStatus, ExchangeAdapter

logger = logging.getLogger(__name__)


class OrderManager:
    """Manages orders with idempotency and state tracking."""
    
    def __init__(self, exchange_adapter: ExchangeAdapter):
        """
        Initialize the Order Manager.
        
        Args:
            exchange_adapter: Exchange adapter instance for executing orders.
        """
        self.exchange = exchange_adapter
        self.orders: Dict[str, Order] = {}  # order_id -> Order
        self.client_order_ids: Set[str] = set()  # For idempotency
        self._order_counter = 0
        logger.info("OrderManager initialized")
    
    def _generate_client_order_id(self) -> str:
        """
        Generate a unique client order ID for idempotency.
        
        Format: client_{timestamp}_{uuid_hex}
        Example: client_20240115_143022_a1b2c3d4
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = uuid.uuid4().hex[:8]
        return f"client_{timestamp}_{unique_id}"
    
    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        amount: float,
        price: Optional[float] = None,
        client_order_id: Optional[str] = None,
    ) -> Order:
        """
        Create and track a new order with idempotency.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT').
            side: Order side (BUY or SELL).
            order_type: Order type (MARKET, LIMIT, etc.).
            amount: Amount to buy/sell.
            price: Price for limit orders (None for market orders).
            client_order_id: Unique client order ID for idempotency.
        
        Returns:
            Order object with order details.
        
        Raises:
            Exception: If order creation fails.
        """
        # Idempotency check - if client_order_id exists, return existing order
        if client_order_id and client_order_id in self.client_order_ids:
            logger.warning(f"Duplicate client_order_id detected: {client_order_id}. Returning existing order.")
            for order in self.orders.values():
                if order.client_order_id == client_order_id:
                    return order
            # Client order ID found in set but not in orders dict - this shouldn't happen
            # Log warning but proceed to create new order
            logger.warning(f"Client order ID {client_order_id} found in set but order not tracked. Creating anyway.")
        
        # Generate client_order_id if not provided
        if not client_order_id:
            client_order_id = self._generate_client_order_id()
        
        # Send order to exchange
        try:
            order = self.exchange.create_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                amount=amount,
                price=price,
                client_order_id=client_order_id,
            )
            
            # Track the order locally
            self.orders[order.id] = order
            self.client_order_ids.add(client_order_id)
            
            logger.info(
                f"Order created: {order.id} | {side.value.upper()} {amount} {symbol} @ {price or 'MARKET'} | "
                f"Status: {order.status.value}"
            )
            return order
            
        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            raise
    
    def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """
        Cancel an existing order.
        
        Args:
            order_id: Exchange order ID.
            symbol: Trading pair symbol (optional for some exchanges).
        
        Returns:
            True if cancellation was successful.
        """
        try:
            result = self.exchange.cancel_order(order_id, symbol)
            if result:
                logger.info(f"Order cancelled: {order_id}")
                # Update local state
                if order_id in self.orders:
                    self.orders[order_id].status = OrderStatus.CANCELLED
            return result
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise
    
    def update_order_status(self, order_id: str, symbol: Optional[str] = None) -> Optional[Order]:
        """
        Refresh order status from exchange.
        
        Args:
            order_id: Exchange order ID.
            symbol: Trading pair symbol (optional for some exchanges).
        
        Returns:
            Updated Order object or None if not found.
        """
        try:
            order = self.exchange.get_order(order_id, symbol)
            if order and order_id in self.orders:
                # Update local state with latest from exchange
                self.orders[order_id] = order
                logger.debug(f"Order {order_id} status updated: {order.status.value}")
            return order
        except Exception as e:
            logger.error(f"Failed to get order {order_id}: {e}")
            return None
    
    def get_order(self, order_id: str, symbol: Optional[str] = None) -> Optional[Order]:
        """
        Get order by ID, refreshing status from exchange.
        
        Args:
            order_id: Exchange order ID.
            symbol: Trading pair symbol (optional).
        
        Returns:
            Order object or None if not found.
        """
        # First check local cache
        if order_id in self.orders:
            # Refresh from exchange
            return self.update_order_status(order_id, symbol)
        
        # Not in local cache, fetch from exchange
        return self.exchange.get_order(order_id, symbol)
    
    def get_open_orders(self) -> List[Order]:
        """
        Get all tracked open orders.
        
        Returns:
            List of Order objects with OPEN or PARTIALLY_FILLED status.
        """
        return [
            o for o in self.orders.values() 
            if o.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)
        ]
    
    def is_order_complete(self, order_id: str) -> bool:
        """
        Check if an order is complete (filled, cancelled, rejected, expired).
        
        Args:
            order_id: Exchange order ID.
        
        Returns:
            True if order is complete.
        """
        if order_id not in self.orders:
            return False
        status = self.orders[order_id].status
        return status in (
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED
        )
    
    def get_orders_by_symbol(self, symbol: str) -> List[Order]:
        """
        Get all orders for a specific symbol.
        
        Args:
            symbol: Trading pair symbol.
        
        Returns:
            List of Order objects for the symbol.
        """
        return [o for o in self.orders.values() if o.symbol == symbol]
    
    def get_completed_orders(self) -> List[Order]:
        """
        Get all completed orders.
        
        Returns:
            List of Order objects with complete status.
        """
        return [
            o for o in self.orders.values()
            if o.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED)
        ]