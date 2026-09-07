"""
Order State Manager - Manages order state machine and transitions.

This module implements a state machine for order lifecycle management,
ensuring valid state transitions and tracking state history.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

from .exchange_adapter import Order, OrderStatus

logger = logging.getLogger(__name__)


class OrderStateTransition(Enum):
    """Valid order state transitions."""
    # Initial states
    PENDING_TO_OPEN = "PENDING -> OPEN"
    PENDING_TO_REJECTED = "PENDING -> REJECTED"
    
    # Open order transitions
    OPEN_TO_PARTIALLY_FILLED = "OPEN -> PARTIALLY_FILLED"
    OPEN_TO_FILLED = "OPEN -> FILLED"
    OPEN_TO_CANCELLED = "OPEN -> CANCELLED"
    OPEN_TO_EXPIRED = "OPEN -> EXPIRED"
    
    # Partially filled transitions
    PARTIALLY_FILLED_TO_FILLED = "PARTIALLY_FILLED -> FILLED"
    PARTIALLY_FILLED_TO_CANCELLED = "PARTIALLY_FILLED -> CANCELLED"
    
    # Terminal states (no transitions allowed)
    FILLED_TO_NONE = "FILLED (terminal)"
    CANCELLED_TO_NONE = "CANCELLED (terminal)"
    REJECTED_TO_NONE = "REJECTED (terminal)"
    EXPIRED_TO_NONE = "EXPIRED (terminal)"


@dataclass
class StateTransition:
    """Represents a state transition event."""
    from_status: OrderStatus
    to_status: OrderStatus
    timestamp: datetime
    reason: Optional[str] = None
    
    def __str__(self) -> str:
        return f"{self.from_status.name} -> {self.to_status.name} @ {self.timestamp.isoformat()}"


@dataclass
class OrderStateMachine:
    """State machine for a single order."""
    order_id: str
    client_order_id: str
    current_status: OrderStatus
    created_at: datetime
    transitions: List[StateTransition] = field(default_factory=list)
    is_terminal: bool = False
    
    def can_transition_to(self, new_status: OrderStatus) -> bool:
        """
        Check if a transition to the new status is valid.
        
        Args:
            new_status: The target status
            
        Returns:
            True if transition is valid, False otherwise
        """
        # Define valid transitions
        valid_transitions: Dict[OrderStatus, Set[OrderStatus]] = {
            OrderStatus.OPEN: {
                OrderStatus.PARTIALLY_FILLED,
                OrderStatus.FILLED,
                OrderStatus.CANCELLED,
                OrderStatus.EXPIRED,
            },
            OrderStatus.PARTIALLY_FILLED: {
                OrderStatus.FILLED,
                OrderStatus.CANCELLED,
            },
            OrderStatus.UNKNOWN: {
                OrderStatus.OPEN,
                OrderStatus.FILLED,
                OrderStatus.CANCELLED,
                OrderStatus.REJECTED,
                OrderStatus.EXPIRED,
            },
            # Terminal states have no valid transitions
            OrderStatus.FILLED: set(),
            OrderStatus.CANCELLED: set(),
            OrderStatus.REJECTED: set(),
            OrderStatus.EXPIRED: set(),
        }
        
        allowed = valid_transitions.get(self.current_status, set())
        return new_status in allowed
    
    def transition_to(self, new_status: OrderStatus, reason: Optional[str] = None) -> bool:
        """
        Attempt to transition to a new status.
        
        Args:
            new_status: The target status
            reason: Optional reason for the transition
            
        Returns:
            True if transition succeeded, False if invalid
        """
        if not self.can_transition_to(new_status):
            logger.warning(
                f"Invalid state transition: {self.current_status.name} -> {new_status.name} "
                f"for order {self.order_id}"
            )
            return False
        
        # Create transition record
        transition = StateTransition(
            from_status=self.current_status,
            to_status=new_status,
            timestamp=datetime.now(),
            reason=reason,
        )
        self.transitions.append(transition)
        
        # Update current status
        self.current_status = new_status
        
        # Check if we've reached a terminal state
        terminal_states = {
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        }
        if new_status in terminal_states:
            self.is_terminal = True
            logger.info(f"Order {self.order_id} reached terminal state: {new_status.name}")
        
        logger.debug(
            f"Order {self.order_id} state transition: {transition}"
        )
        return True
    
    def get_transition_history(self) -> List[StateTransition]:
        """Get the full transition history for this order."""
        return self.transitions.copy()
    
    def time_in_current_state(self) -> float:
        """
        Calculate time spent in the current state.
        
        Returns:
            Time in seconds since entering current state
        """
        if not self.transitions:
            return (datetime.now() - self.created_at).total_seconds()
        
        last_transition = self.transitions[-1]
        return (datetime.now() - last_transition.timestamp).total_seconds()


class OrderStateManager:
    """
    Manages state machines for all orders.
    
    Provides centralized state management with validation and auditing.
    """
    
    def __init__(self):
        self.state_machines: Dict[str, OrderStateMachine] = {}
        logger.info("OrderStateManager initialized")
    
    def register_order(self, order: Order) -> OrderStateMachine:
        """
        Register a new order and create its state machine.
        
        Args:
            order: The order to register
            
        Returns:
            The created state machine
        """
        if order.id in self.state_machines:
            logger.warning(f"Order {order.id} already registered, returning existing state machine")
            return self.state_machines[order.id]
        
        # Determine initial status
        initial_status = order.status
        if initial_status == OrderStatus.UNKNOWN:
            initial_status = OrderStatus.PENDING
        
        state_machine = OrderStateMachine(
            order_id=order.id,
            client_order_id=order.client_order_id,
            current_status=initial_status,
            created_at=order.timestamp if hasattr(order.timestamp, 'timestamp') else datetime.now(),
            is_terminal=initial_status in {
                OrderStatus.FILLED,
                OrderStatus.CANCELLED,
                OrderStatus.REJECTED,
                OrderStatus.EXPIRED,
            },
        )
        
        self.state_machines[order.id] = state_machine
        logger.debug(f"Registered order {order.id} with initial status {initial_status.name}")
        
        return state_machine
    
    def get_state_machine(self, order_id: str) -> Optional[OrderStateMachine]:
        """
        Get the state machine for an order.
        
        Args:
            order_id: Exchange order ID
            
        Returns:
            State machine if found, None otherwise
        """
        return self.state_machines.get(order_id)
    
    def update_order_status(
        self, 
        order_id: str, 
        new_status: OrderStatus, 
        reason: Optional[str] = None
    ) -> bool:
        """
        Update the status of an order.
        
        Args:
            order_id: Exchange order ID
            new_status: New status
            reason: Optional reason for the change
            
        Returns:
            True if update succeeded, False if order not found or invalid transition
        """
        state_machine = self.get_state_machine(order_id)
        if not state_machine:
            logger.error(f"Cannot update status: order {order_id} not found in state manager")
            return False
        
        if state_machine.is_terminal:
            logger.warning(
                f"Cannot update terminal order {order_id} (status={state_machine.current_status.name})"
            )
            return False
        
        success = state_machine.transition_to(new_status, reason)
        if not success:
            logger.warning(
                f"Failed to update order {order_id}: invalid transition "
                f"{state_machine.current_status.name} -> {new_status.name}"
            )
        
        return success
    
    def get_order_status(self, order_id: str) -> Optional[OrderStatus]:
        """
        Get the current status of an order.
        
        Args:
            order_id: Exchange order ID
            
        Returns:
            Current status if found, None otherwise
        """
        state_machine = self.get_state_machine(order_id)
        if state_machine:
            return state_machine.current_status
        return None
    
    def is_order_terminal(self, order_id: str) -> bool:
        """
        Check if an order has reached a terminal state.
        
        Args:
            order_id: Exchange order ID
            
        Returns:
            True if terminal, False otherwise
        """
        state_machine = self.get_state_machine(order_id)
        return state_machine.is_terminal if state_machine else False
    
    def get_open_order_ids(self) -> List[str]:
        """
        Get IDs of all non-terminal orders.
        
        Returns:
            List of order IDs
        """
        return [
            order_id for order_id, sm in self.state_machines.items()
            if not sm.is_terminal
        ]
    
    def get_terminal_order_ids(self) -> List[str]:
        """
        Get IDs of all terminal orders.
        
        Returns:
            List of order IDs
        """
        return [
            order_id for order_id, sm in self.state_machines.items()
            if sm.is_terminal
        ]
    
    def cleanup_terminal_orders(self, older_than_seconds: int = 3600) -> int:
        """
        Remove old terminal orders from memory.
        
        Args:
            older_than_seconds: Remove orders that became terminal more than this many seconds ago
            
        Returns:
            Number of orders cleaned up
        """
        to_remove = []
        now = datetime.now()
        
        for order_id, sm in self.state_machines.items():
            if sm.is_terminal and sm.transitions:
                last_transition = sm.transitions[-1]
                age = (now - last_transition.timestamp).total_seconds()
                if age > older_than_seconds:
                    to_remove.append(order_id)
        
        for order_id in to_remove:
            del self.state_machines[order_id]
        
        logger.info(f"Cleaned up {len(to_remove)} terminal orders older than {older_than_seconds}s")
        return len(to_remove)
    
    def get_all_active_orders(self) -> List[OrderStateMachine]:
        """
        Get all non-terminal order state machines.
        
        Returns:
            List of active state machines
        """
        return [sm for sm in self.state_machines.values() if not sm.is_terminal]
    
    def count_by_status(self) -> Dict[str, int]:
        """
        Count orders by their current status.
        
        Returns:
            Dictionary mapping status names to counts
        """
        counts: Dict[str, int] = {}
        for sm in self.state_machines.values():
            status_name = sm.current_status.name
            counts[status_name] = counts.get(status_name, 0) + 1
        return counts
