"""
Atomic Operations - Multi-order atomic execution.

This module provides transaction-like semantics for multi-order operations,
ensuring all-or-nothing execution for related orders.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager

from .exchange_adapter import ExchangeAdapter, Order, OrderSide, OrderType, OrderStatus
from .order_registry import OrderRegistry
from .order_state_manager import OrderStateManager

logger = logging.getLogger(__name__)


class AtomicOperationStatus(Enum):
    """Status of an atomic operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class AtomicOrder:
    """Represents an order within an atomic operation."""
    symbol: str
    side: OrderSide
    order_type: OrderType
    amount: float
    price: Optional[float] = None
    client_order_id: Optional[str] = None
    executed_order: Optional[Order] = None
    success: bool = False
    error: Optional[str] = None


@dataclass
class AtomicOperationResult:
    """Result of an atomic operation."""
    operation_id: str
    status: AtomicOperationStatus
    orders_submitted: int
    orders_successful: int
    orders_failed: int
    created_orders: List[Order] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def is_success(self) -> bool:
        return self.status == AtomicOperationStatus.COMPLETED
    
    @property
    def is_failure(self) -> bool:
        return self.status in (AtomicOperationStatus.FAILED, AtomicOperationStatus.ROLLED_BACK)


class AtomicOperations:
    """
    Provides atomic execution of multiple orders.
    
    Ensures that either all orders in a group succeed, or none are executed.
    This is critical for strategies that require simultaneous execution
    of multiple legs (e.g., pairs trading, arbitrage).
    """
    
    def __init__(
        self,
        exchange_adapter: ExchangeAdapter,
        order_registry: OrderRegistry,
        order_state_manager: Optional[OrderStateManager] = None,
    ):
        """
        Initialize atomic operations manager.
        
        Args:
            exchange_adapter: Exchange adapter for order submission
            order_registry: Persistent order storage
            order_state_manager: Optional state manager
        """
        self.exchange = exchange_adapter
        self.registry = order_registry
        self.state_manager = order_state_manager
        self._operation_counter = 0
        logger.info("AtomicOperations initialized")
    
    def _generate_operation_id(self) -> str:
        """Generate a unique operation ID."""
        self._operation_counter += 1
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"atomic_{timestamp}_{self._operation_counter:04d}"
    
    def execute_atomic(
        self,
        orders: List[AtomicOrder],
        rollback_on_failure: bool = True,
    ) -> AtomicOperationResult:
        """
        Execute multiple orders atomically.
        
        Args:
            orders: List of orders to execute
            rollback_on_failure: If True, cancel successful orders on failure
            
        Returns:
            AtomicOperationResult with execution details
        """
        operation_id = self._generate_operation_id()
        logger.info(f"Starting atomic operation {operation_id} with {len(orders)} orders")
        
        result = AtomicOperationResult(
            operation_id=operation_id,
            status=AtomicOperationStatus.IN_PROGRESS,
            orders_submitted=len(orders),
            orders_successful=0,
            orders_failed=0,
        )
        
        executed_orders: List[Order] = []
        
        try:
            # Phase 1: Submit all orders
            for i, atomic_order in enumerate(orders):
                try:
                    order = self._submit_order(atomic_order, operation_id)
                    atomic_order.executed_order = order
                    atomic_order.success = True
                    executed_orders.append(order)
                    result.orders_successful += 1
                    
                    logger.debug(
                        f"Atomic order {i+1}/{len(orders)} submitted: "
                        f"{order.id} ({atomic_order.side.name} {atomic_order.amount} {atomic_order.symbol})"
                    )
                    
                except Exception as e:
                    atomic_order.success = False
                    atomic_order.error = str(e)
                    result.orders_failed += 1
                    result.errors.append(f"Order {i+1} failed: {e}")
                    
                    logger.error(f"Atomic order {i+1}/{len(orders)} failed: {e}")
                    
                    if rollback_on_failure:
                        logger.warning(f"Rolling back {len(executed_orders)} successful orders...")
                        self._rollback_orders(executed_orders, operation_id)
                        result.status = AtomicOperationStatus.ROLLED_BACK
                        return result
            
            # All orders succeeded
            result.status = AtomicOperationStatus.COMPLETED
            result.created_orders = executed_orders
            
            logger.info(
                f"Atomic operation {operation_id} completed successfully: "
                f"{result.orders_successful}/{result.orders_submitted} orders"
            )
            
        except Exception as e:
            result.status = AtomicOperationStatus.FAILED
            result.errors.append(f"Atomic operation failed: {e}")
            logger.error(f"Atomic operation {operation_id} failed: {e}")
            
            if rollback_on_failure and executed_orders:
                logger.warning(f"Rolling back {len(executed_orders)} orders due to critical failure...")
                self._rollback_orders(executed_orders, operation_id)
                result.status = AtomicOperationStatus.ROLLED_BACK
        
        return result
    
    def _submit_order(self, atomic_order: AtomicOrder, operation_id: str) -> Order:
        """
        Submit a single order as part of an atomic operation.
        
        Args:
            atomic_order: Order to submit
            operation_id: Parent operation ID for tracking
            
        Returns:
            Submitted Order
        """
        # Generate client_order_id if not provided
        client_order_id = atomic_order.client_order_id
        if not client_order_id:
            import uuid
            client_order_id = f"atomic_{operation_id}_{uuid.uuid4().hex[:8]}"
        
        # Check for idempotency
        if self.registry.exists_client_order_id(client_order_id):
            existing = self.registry.get_order_by_client_id(client_order_id)
            if existing:
                logger.warning(f"Reusing existing order for client_id: {client_order_id}")
                return existing
        
        # Submit to exchange
        order = self.exchange.create_order(
            symbol=atomic_order.symbol,
            side=atomic_order.side,
            order_type=atomic_order.order_type,
            amount=atomic_order.amount,
            price=atomic_order.price,
            client_order_id=client_order_id,
        )
        
        # Save to registry
        metadata = {'atomic_operation_id': operation_id}
        self.registry.save_order(order, metadata)
        
        # Register with state manager
        if self.state_manager:
            self.state_manager.register_order(order)
        
        return order
    
    def _rollback_orders(self, orders: List[Order], operation_id: str) -> int:
        """
        Cancel a list of orders (rollback).
        
        Args:
            orders: Orders to cancel
            operation_id: Operation ID for logging
            
        Returns:
            Number of orders successfully cancelled
        """
        cancelled = 0
        
        for order in orders:
            try:
                # Only cancel if order is still open
                if order.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED):
                    self.exchange.cancel_order(order.id, order.symbol)
                    self.registry.update_order_status(
                        order.id,
                        OrderStatus.CANCELLED,
                        error_message=f"Rolled back from atomic operation {operation_id}",
                    )
                    cancelled += 1
                    logger.info(f"Rolled back order {order.id} from operation {operation_id}")
                else:
                    logger.debug(f"Order {order.id} already in terminal state, skipping rollback")
                    
            except Exception as e:
                logger.error(f"Failed to rollback order {order.id}: {e}")
        
        logger.info(f"Rolled back {cancelled}/{len(orders)} orders from operation {operation_id}")
        return cancelled
    
    def execute_pairs_trade(
        self,
        leg1_symbol: str,
        leg1_side: OrderSide,
        leg1_amount: float,
        leg2_symbol: str,
        leg2_side: OrderSide,
        leg2_amount: float,
        leg1_price: Optional[float] = None,
        leg2_price: Optional[float] = None,
    ) -> AtomicOperationResult:
        """
        Execute a pairs trade (two-legged atomic order).
        
        Args:
            leg1_symbol: First leg symbol
            leg1_side: First leg side (BUY/SELL)
            leg1_amount: First leg amount
            leg2_symbol: Second leg symbol
            leg2_side: Second leg side (BUY/SELL)
            leg2_amount: Second leg amount
            leg1_price: Optional limit price for leg 1
            leg2_price: Optional limit price for leg 2
            
        Returns:
            AtomicOperationResult
        """
        orders = [
            AtomicOrder(
                symbol=leg1_symbol,
                side=leg1_side,
                order_type=OrderType.LIMIT if leg1_price else OrderType.MARKET,
                amount=leg1_amount,
                price=leg1_price,
            ),
            AtomicOrder(
                symbol=leg2_symbol,
                side=leg2_side,
                order_type=OrderType.LIMIT if leg2_price else OrderType.MARKET,
                amount=leg2_amount,
                price=leg2_price,
            ),
        ]
        
        logger.info(
            f"Executing pairs trade: {leg1_side.name} {leg1_amount} {leg1_symbol} vs "
            f"{leg2_side.name} {leg2_amount} {leg2_symbol}"
        )
        
        return self.execute_atomic(orders, rollback_on_failure=True)
    
    def execute_arbitrage(
        self,
        buy_symbol: str,
        buy_amount: float,
        buy_price: float,
        sell_symbol: str,
        sell_amount: float,
        sell_price: float,
    ) -> AtomicOperationResult:
        """
        Execute an arbitrage trade (buy one venue, sell another).
        
        Note: This assumes the exchange adapter handles multi-venue routing.
        For true cross-exchange arbitrage, you'd need multiple adapters.
        
        Args:
            buy_symbol: Symbol to buy
            buy_amount: Amount to buy
            buy_price: Buy limit price
            sell_symbol: Symbol to sell
            sell_amount: Amount to sell
            sell_price: Sell limit price
            
        Returns:
            AtomicOperationResult
        """
        orders = [
            AtomicOrder(
                symbol=buy_symbol,
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                amount=buy_amount,
                price=buy_price,
            ),
            AtomicOrder(
                symbol=sell_symbol,
                side=OrderSide.SELL,
                order_type=OrderType.LIMIT,
                amount=sell_amount,
                price=sell_price,
            ),
        ]
        
        logger.info(
            f"Executing arbitrage: BUY {buy_amount} {buy_symbol} @ {buy_price} / "
            f"SELL {sell_amount} {sell_symbol} @ {sell_price}"
        )
        
        return self.execute_atomic(orders, rollback_on_failure=True)
    
    @contextmanager
    def atomic_context(self, orders: List[AtomicOrder]):
        """
        Context manager for atomic operations.
        
        Usage:
            with atomic_ops.atomic_context(orders) as result:
                # Do something with result
                if result.is_failure:
                    # Handle failure
                    pass
        
        Args:
            orders: List of orders to execute atomically
            
        Yields:
            AtomicOperationResult
        """
        result = self.execute_atomic(orders, rollback_on_failure=True)
        try:
            yield result
        finally:
            # Cleanup or notification logic here
            if result.is_failure:
                logger.warning(f"Atomic operation {result.operation_id} ended in failure state")