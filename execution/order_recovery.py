"""
Order Recovery - Handles startup recovery and discrepancy resolution.

This module recovers order state after system restarts and resolves
discrepancies between local state and exchange state.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .exchange_adapter import ExchangeAdapter, Order, OrderStatus
from .order_registry import OrderRegistry
from .order_state_manager import OrderStateManager

logger = logging.getLogger(__name__)


class RecoveryAction(Enum):
    """Actions that can be taken during recovery."""
    KEEP_LOCAL = "keep_local"
    UPDATE_FROM_EXCHANGE = "update_from_exchange"
    CANCEL_ORDER = "cancel_order"
    MANUAL_REVIEW = "manual_review"


@dataclass
class Discrepancy:
    """Represents a discrepancy between local and exchange state."""
    order_id: str
    client_order_id: str
    local_status: Optional[OrderStatus]
    exchange_status: Optional[OrderStatus]
    local_filled: float
    exchange_filled: float
    detected_at: datetime
    recommended_action: RecoveryAction
    notes: str = ""


@dataclass
class RecoveryResult:
    """Result of a recovery operation."""
    total_orders_checked: int
    orders_recovered: int
    discrepancies_found: int
    discrepancies_resolved: int
    manual_review_required: int
    timestamp: datetime


class OrderRecovery:
    """
    Handles order recovery after system restarts.
    
    Implements the critical rule: On system startup, recover ALL open orders
    from the DB by querying the exchange BEFORE accepting new orders.
    """
    
    def __init__(
        self,
        exchange_adapter: ExchangeAdapter,
        order_registry: OrderRegistry,
        order_state_manager: Optional[OrderStateManager] = None,
        timeout_seconds: int = 30,
    ):
        """
        Initialize the order recovery system.
        
        Args:
            exchange_adapter: Exchange adapter for querying order status
            order_registry: Persistent order storage
            order_state_manager: Optional state manager for tracking
            timeout_seconds: Timeout for exchange queries
        """
        self.exchange = exchange_adapter
        self.registry = order_registry
        self.state_manager = order_state_manager
        self.timeout_seconds = timeout_seconds
        logger.info("OrderRecovery initialized")
    
    def recover_all_orders(self) -> RecoveryResult:
        """
        Recover all open orders from the database and verify with exchange.
        
        This is the primary recovery method to be called on system startup.
        
        Returns:
            RecoveryResult with statistics
        """
        logger.info("Starting order recovery process...")
        
        # Get all open orders from registry
        open_orders = self.registry.get_open_orders()
        logger.info(f"Found {len(open_orders)} open orders in registry")
        
        recovered = 0
        discrepancies = 0
        resolved = 0
        manual_review = 0
        
        for order in open_orders:
            try:
                # Query exchange for current status
                exchange_order = self._query_exchange_order(order.id, order.symbol)
                
                if exchange_order:
                    # Compare and resolve
                    discrepancy = self._check_discrepancy(order, exchange_order)
                    if discrepancy:
                        discrepancies += 1
                        action_taken = self._resolve_discrepancy(discrepancy, exchange_order)
                        if action_taken != RecoveryAction.MANUAL_REVIEW:
                            resolved += 1
                        else:
                            manual_review += 1
                    else:
                        # No discrepancy, just update registry
                        self._update_registry(exchange_order)
                    
                    recovered += 1
                else:
                    # Order not found on exchange
                    logger.warning(
                        f"Order {order.id} not found on exchange. "
                        f"Local status: {order.status.name}"
                    )
                    self._handle_missing_order(order)
                    manual_review += 1
                    
            except Exception as e:
                logger.error(f"Error recovering order {order.id}: {e}")
                manual_review += 1
        
        result = RecoveryResult(
            total_orders_checked=len(open_orders),
            orders_recovered=recovered,
            discrepancies_found=discrepancies,
            discrepancies_resolved=resolved,
            manual_review_required=manual_review,
            timestamp=datetime.now(),
        )
        
        logger.info(
            f"Recovery complete: {result.orders_recovered}/{result.total_orders_checked} recovered, "
            f"{result.discrepancies_found} discrepancies, "
            f"{result.manual_review_required} require manual review"
        )
        
        return result
    
    def _query_exchange_order(
        self, 
        order_id: str, 
        symbol: str,
        max_retries: int = 3
    ) -> Optional[Order]:
        """
        Query exchange for order status with retry logic.
        
        Args:
            order_id: Exchange order ID
            symbol: Trading pair symbol
            max_retries: Maximum number of retry attempts
            
        Returns:
            Order from exchange or None if not found
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                order = self.exchange.get_order(order_id, symbol)
                if order:
                    logger.debug(f"Successfully retrieved order {order_id} from exchange")
                    return order
                else:
                    logger.debug(f"Order {order_id} not found on exchange")
                    return None
                    
            except Exception as e:
                last_error = e
                wait_time = min(2 ** attempt, 10)  # Exponential backoff, max 10s
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed for order {order_id}: {e}. "
                    f"Retrying in {wait_time}s..."
                )
                import time
                time.sleep(wait_time)
        
        logger.error(f"All {max_retries} attempts failed for order {order_id}: {last_error}")
        raise last_error
    
    def _check_discrepancy(self, local_order: Order, exchange_order: Order) -> Optional[Discrepancy]:
        """
        Check for discrepancies between local and exchange order state.
        
        Args:
            local_order: Local order record
            exchange_order: Order from exchange
            
        Returns:
            Discrepancy object if found, None otherwise
        """
        # Check status mismatch
        if local_order.status != exchange_order.status:
            logger.warning(
                f"Status mismatch for order {local_order.id}: "
                f"local={local_order.status.name}, exchange={exchange_order.status.name}"
            )
            
            # Determine recommended action based on states
            if exchange_order.status == OrderStatus.FILLED:
                action = RecoveryAction.UPDATE_FROM_EXCHANGE
                notes = "Exchange shows FILLED - trust exchange state"
            elif exchange_order.status == OrderStatus.CANCELLED:
                action = RecoveryAction.UPDATE_FROM_EXCHANGE
                notes = "Exchange shows CANCELLED - trust exchange state"
            elif exchange_order.status == OrderStatus.REJECTED:
                action = RecoveryAction.UPDATE_FROM_EXCHANGE
                notes = "Exchange shows REJECTED - trust exchange state"
            else:
                action = RecoveryAction.MANUAL_REVIEW
                notes = "Complex status mismatch requires manual review"
            
            return Discrepancy(
                order_id=local_order.id,
                client_order_id=local_order.client_order_id,
                local_status=local_order.status,
                exchange_status=exchange_order.status,
                local_filled=local_order.filled_amount,
                exchange_filled=exchange_order.filled_amount,
                detected_at=datetime.now(),
                recommended_action=action,
                notes=notes,
            )
        
        # Check filled amount mismatch
        fill_tolerance = 0.0001  # Small tolerance for rounding
        if abs(local_order.filled_amount - exchange_order.filled_amount) > fill_tolerance:
            logger.warning(
                f"Fill amount mismatch for order {local_order.id}: "
                f"local={local_order.filled_amount}, exchange={exchange_order.filled_amount}"
            )
            
            return Discrepancy(
                order_id=local_order.id,
                client_order_id=local_order.client_order_id,
                local_status=local_order.status,
                exchange_status=exchange_order.status,
                local_filled=local_order.filled_amount,
                exchange_filled=exchange_order.filled_amount,
                detected_at=datetime.now(),
                recommended_action=RecoveryAction.UPDATE_FROM_EXCHANGE,
                notes="Fill amount mismatch - trust exchange state",
            )
        
        # No discrepancy
        return None
    
    def _resolve_discrepancy(
        self, 
        discrepancy: Discrepancy, 
        exchange_order: Order
    ) -> RecoveryAction:
        """
        Resolve a detected discrepancy.
        
        Args:
            discrepancy: The detected discrepancy
            exchange_order: Current order from exchange
            
        Returns:
            Action taken
        """
        action = discrepancy.recommended_action
        
        if action == RecoveryAction.UPDATE_FROM_EXCHANGE:
            logger.info(
                f"Resolving discrepancy for order {discrepancy.order_id}: "
                f"updating from exchange state"
            )
            self._update_registry(exchange_order)
            
            # Also update state manager if available
            if self.state_manager:
                self.state_manager.update_order_status(
                    exchange_order.id,
                    exchange_order.status,
                    reason=f"Recovery: updated from exchange (was {discrepancy.local_status.name})",
                )
            
            return RecoveryAction.UPDATE_FROM_EXCHANGE
        
        elif action == RecoveryAction.CANCEL_ORDER:
            logger.info(f"Cancelling order {discrepancy.order_id} as part of recovery")
            try:
                self.exchange.cancel_order(discrepancy.order_id, exchange_order.symbol)
                return RecoveryAction.CANCEL_ORDER
            except Exception as e:
                logger.error(f"Failed to cancel order during recovery: {e}")
                return RecoveryAction.MANUAL_REVIEW
        
        else:
            # MANUAL_REVIEW
            logger.warning(
                f"Discrepancy for order {discrepancy.order_id} requires manual review: "
                f"{discrepancy.notes}"
            )
            return RecoveryAction.MANUAL_REVIEW
    
    def _update_registry(self, order: Order) -> None:
        """
        Update the registry with current order state.
        
        Args:
            order: Current order state
        """
        self.registry.save_order(order)
        self.registry.update_order_status(
            order.id,
            order.status,
            filled_amount=order.filled_amount,
            fee=order.fee if hasattr(order, 'fee') else None,
        )
        logger.debug(f"Registry updated for order {order.id}")
    
    def _handle_missing_order(self, local_order: Order) -> None:
        """
        Handle an order that exists locally but not on the exchange.
        
        Args:
            local_order: Local order record
        """
        # This is a critical situation - order exists in DB but not on exchange
        # Possible causes:
        # 1. Order was never successfully created (DB write before exchange confirm)
        # 2. Order was cancelled externally
        # 3. Exchange API issue
        
        if local_order.status == OrderStatus.OPEN:
            # We thought it was open, but it's not on exchange
            # Mark as unknown/rejected
            self.registry.update_order_status(
                local_order.id,
                OrderStatus.UNKNOWN,
                error_message="Order not found on exchange during recovery",
            )
            
            if self.state_manager:
                self.state_manager.update_order_status(
                    local_order.id,
                    OrderStatus.UNKNOWN,
                    reason="Order missing from exchange",
                )
            
            logger.critical(
                f"CRITICAL: Order {local_order.id} marked as UNKNOWN - "
                f"was OPEN locally but missing from exchange"
            )
    
    def get_stale_orders(self, max_age_hours: int = 24) -> List[Order]:
        """
        Find orders that have been open for too long.
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            List of stale orders
        """
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        all_orders = self.registry.get_all_orders(limit=10000)
        
        stale = []
        for order in all_orders:
            if order.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED):
                order_time = order.timestamp
                if hasattr(order_time, 'timestamp') and isinstance(order_time, datetime):
                    if order_time < cutoff:
                        stale.append(order)
                elif isinstance(order_time, str):
                    try:
                        order_dt = datetime.fromisoformat(order_time.replace('Z', '+00:00'))
                        if order_dt < cutoff:
                            stale.append(order)
                    except (ValueError, TypeError):
                        pass
        
        logger.info(f"Found {len(stale)} stale orders older than {max_age_hours}h")
        return stale
    
    def cleanup_stale_orders(self, max_age_hours: int = 24) -> int:
        """
        Cancel and clean up stale orders.
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of orders cleaned up
        """
        stale_orders = self.get_stale_orders(max_age_hours)
        cleaned = 0
        
        for order in stale_orders:
            try:
                # Try to cancel
                self.exchange.cancel_order(order.id, order.symbol)
                logger.info(f"Cancelled stale order {order.id}")
                cleaned += 1
            except Exception as e:
                logger.warning(f"Failed to cancel stale order {order.id}: {e}")
            
            # Update registry
            self.registry.update_order_status(
                order.id,
                OrderStatus.CANCELLED,
                error_message=f"Cancelled due to age ({max_age_hours}h)",
            )
        
        logger.info(f"Cleaned up {cleaned}/{len(stale_orders)} stale orders")
        return cleaned
    
    def verify_no_duplicate_client_ids(self) -> bool:
        """
        Verify that there are no duplicate client_order_ids in open orders.
        
        Returns:
            True if no duplicates found, False otherwise
        """
        open_orders = self.registry.get_open_orders()
        client_ids = [o.client_order_id for o in open_orders]
        
        duplicates = len(client_ids) - len(set(client_ids))
        if duplicates > 0:
            logger.error(f"Found {duplicates} duplicate client_order_ids in open orders!")
            return False
        
        logger.info("No duplicate client_order_ids found in open orders")
        return True
