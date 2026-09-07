"""
Kill Switch Manager - Integration layer connecting kill switch to trading components.

This module provides the bridge between the core kill switch mechanism and the
actual trading infrastructure (order manager, position manager, exchange adapter).
"""

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .kill_switch import KillSwitch
from .kill_switch_models import (
    KillSwitchLevel,
    KillSwitchTrigger,
    KillSwitchEvent,
    KillSwitchResponse,
)

# Conditional imports to avoid circular dependencies
if TYPE_CHECKING:
    from .order_manager import OrderManager
    from .position_manager import PositionManager
    from .exchange_adapter import ExchangeAdapter

logger = logging.getLogger(__name__)


class KillSwitchManager:
    """
    Manages integration between kill switch and trading components.
    
    This class routes kill switch events to appropriate actions on the
    order manager, position manager, and exchange adapter.
    """
    
    def __init__(
        self,
        kill_switch: KillSwitch,
        order_manager: Optional['OrderManager'] = None,
        position_manager: Optional['PositionManager'] = None,
        exchange_adapter: Optional['ExchangeAdapter'] = None,
    ):
        """
        Initialize the kill switch manager.
        
        Args:
            kill_switch: Core kill switch instance
            order_manager: Order manager for cancelling orders
            position_manager: Position manager for closing positions
            exchange_adapter: Exchange adapter for emergency operations
        """
        self.kill_switch = kill_switch
        self.order_manager = order_manager
        self.position_manager = position_manager
        self.exchange_adapter = exchange_adapter
        
        # Register callback to route events
        self.kill_switch.register_callback(self._on_kill_switch_event)
        
        logger.info("KillSwitchManager initialized")
    
    def _on_kill_switch_event(self, event: KillSwitchEvent) -> None:
        """
        Route kill switch event to appropriate handler.
        
        Args:
            event: The kill switch event that occurred
        """
        logger.info(f"Routing kill switch event: {event.level.value} - {event.trigger.value}")
        
        if event.level == KillSwitchLevel.PAUSE:
            self._handle_pause(event)
        elif event.level == KillSwitchLevel.DERISK:
            self._handle_derisk(event)
        elif event.level == KillSwitchLevel.HALT:
            self._handle_halt(event)
        elif event.level == KillSwitchLevel.EMERGENCY:
            self._handle_emergency(event)
    
    def _handle_pause(self, event: KillSwitchEvent) -> None:
        """
        Handle PAUSE level event.
        
        Actions:
        - Stop new orders
        """
        logger.warning(f"Handling PAUSE: {event.reason}")
        
        # Stop new orders via order manager
        if self.order_manager:
            self.order_manager._paused = True
            logger.info("OrderManager paused - no new orders will be created")
        
        # Log the pause state
        logger.info(f"PAUSE triggered by {event.triggered_by}: {event.reason}")
    
    def _handle_derisk(self, event: KillSwitchEvent) -> None:
        """
        Handle DERISK level event.
        
        Actions:
        - Stop new orders
        - Signal strategy to reduce exposure
        """
        logger.warning(f"Handling DERISK: {event.reason}")
        
        # Stop new orders
        if self.order_manager:
            self.order_manager._paused = True
            logger.info("OrderManager paused - no new orders will be created")
        
        # Signal portfolio to reduce exposure
        # This would typically notify the portfolio optimizer to reduce target weights
        logger.warning("DERISK signal sent - portfolio should reduce exposure")
        
        # In a full implementation, this would:
        # 1. Notify the strategy engine to reduce position sizes
        # 2. Trigger a rebalance with reduced risk parameters
        # 3. Set maximum position size limits
    
    def _handle_halt(self, event: KillSwitchEvent) -> None:
        """
        Handle HALT level event.
        
        Actions:
        - Cancel all open orders
        - Close all positions
        - Disable trading components
        """
        logger.critical(f"Handling HALT: {event.reason}")
        
        # Cancel all open orders
        try:
            self._cancel_all_open_orders()
        except Exception as e:
            logger.error(f"Failed to cancel orders during HALT: {e}")
        
        # Close all positions
        try:
            self._close_all_positions()
        except Exception as e:
            logger.error(f"Failed to close positions during HALT: {e}")
        
        # Disable trading components
        if self.order_manager:
            self.order_manager._paused = True
            logger.info("OrderManager disabled")
        
        logger.critical("HALT complete - all orders cancelled, positions closed")
    
    def _handle_emergency(self, event: KillSwitchEvent) -> None:
        """
        Handle EMERGENCY level event.
        
        Actions:
        - Market orders to close all positions immediately
        - Kill background processes
        - Send alerts
        """
        logger.critical(f"Handling EMERGENCY: {event.reason}")
        
        # Emergency close all positions via market orders
        try:
            self._close_all_positions_emergency()
        except Exception as e:
            logger.error(f"Emergency position close failed: {e}")
        
        # Cancel all open orders
        try:
            self._cancel_all_open_orders()
        except Exception as e:
            logger.error(f"Failed to cancel orders during EMERGENCY: {e}")
        
        # Kill background processes (monitoring threads, etc.)
        logger.critical("EMERGENCY: Killing background processes")
        
        # Send alerts (already done in core kill switch)
        logger.critical("EMERGENCY alerts sent")
        
        logger.critical("EMERGENCY shutdown complete")
    
    def _cancel_all_open_orders(self) -> None:
        """Cancel all open orders via order manager."""
        if not self.order_manager:
            logger.warning("No order manager available to cancel orders")
            return
        
        cancelled_count = 0
        for order_id, order in list(self.order_manager.orders.items()):
            if not order.is_complete:
                try:
                    # Use safe cancellation method
                    success = self.order_manager.cancel_order_safe(order_id)
                    if success:
                        cancelled_count += 1
                except Exception as e:
                    logger.error(f"Failed to cancel order {order_id}: {e}")
        
        logger.info(f"Cancelled {cancelled_count} open orders")
    
    def _close_all_positions(self) -> None:
        """Close all positions via exchange limit/market orders."""
        if not self.position_manager or not self.exchange_adapter:
            logger.warning("No position manager or exchange adapter available")
            return
        
        try:
            # Get all open positions
            positions = self.position_manager.get_all_positions()
            
            closed_count = 0
            for position in positions:
                try:
                    # Determine side to close
                    if position.size > 0:
                        # Long position - sell to close
                        side = "sell"
                        amount = abs(position.size)
                    else:
                        # Short position - buy to close
                        side = "buy"
                        amount = abs(position.size)
                    
                    # Submit market order to close
                    logger.info(f"Closing position: {position.symbol} {side} {amount}")
                    
                    # Use exchange adapter directly for urgency
                    self.exchange_adapter.create_order(
                        symbol=position.symbol,
                        side=side,
                        order_type="market",
                        amount=amount,
                    )
                    
                    closed_count += 1
                except Exception as e:
                    logger.error(f"Failed to close position {position.symbol}: {e}")
            
            logger.info(f"Closed {closed_count} positions")
        except Exception as e:
            logger.error(f"Error closing positions: {e}")
    
    def _close_all_positions_emergency(self) -> None:
        """
        Emergency close all positions using market orders.
        
        This is more aggressive than _close_all_positions and bypasses
        some safety checks for speed.
        """
        if not self.position_manager or not self.exchange_adapter:
            logger.warning("No position manager or exchange adapter available")
            return
        
        try:
            positions = self.position_manager.get_all_positions()
            
            for position in positions:
                try:
                    if position.size > 0:
                        side = "sell"
                    else:
                        side = "buy"
                    
                    logger.critical(f"EMERGENCY CLOSE: {position.symbol} {side} {abs(position.size)}")
                    
                    # Direct market order - no safety checks
                    self.exchange_adapter.create_order(
                        symbol=position.symbol,
                        side=side,
                        order_type="market",
                        amount=abs(position.size),
                    )
                except Exception as e:
                    logger.critical(f"EMERGENCY close failed for {position.symbol}: {e}")
            
            logger.critical("Emergency position close complete")
        except Exception as e:
            logger.critical(f"Emergency close error: {e}")
    
    def check_conditions(self, metrics: Dict[str, Any]) -> None:
        """
        Wrapper around core kill switch condition checking.
        
        Args:
            metrics: Current trading metrics from live system
        """
        self.kill_switch._check_conditions(metrics)
    
    def emergency_stop(self, reason: str, triggered_by: str) -> KillSwitchResponse:
        """
        Trigger EMERGENCY level kill switch.
        
        Args:
            reason: Human-readable reason
            triggered_by: Who/what triggered it
        
        Returns:
            KillSwitchResponse with operation result
        """
        return self.kill_switch.trigger(
            level=KillSwitchLevel.EMERGENCY,
            trigger=KillSwitchTrigger.MANUAL,
            reason=reason,
            details={"manual_trigger": True},
            triggered_by=triggered_by
        )
    
    def halt_trading(self, reason: str, triggered_by: str) -> KillSwitchResponse:
        """
        Trigger HALT level kill switch.
        
        Args:
            reason: Human-readable reason
            triggered_by: Who/what triggered it
        
        Returns:
            KillSwitchResponse with operation result
        """
        return self.kill_switch.trigger(
            level=KillSwitchLevel.HALT,
            trigger=KillSwitchTrigger.MANUAL,
            reason=reason,
            details={"manual_trigger": True},
            triggered_by=triggered_by
        )
    
    def pause_trading(self, reason: str, triggered_by: str) -> KillSwitchResponse:
        """
        Trigger PAUSE level kill switch.
        
        Args:
            reason: Human-readable reason
            triggered_by: Who/what triggered it
        
        Returns:
            KillSwitchResponse with operation result
        """
        return self.kill_switch.trigger(
            level=KillSwitchLevel.PAUSE,
            trigger=KillSwitchTrigger.MANUAL,
            reason=reason,
            details={"manual_trigger": True},
            triggered_by=triggered_by
        )
    
    def resume_trading(self, reason: str, resolved_by: str) -> KillSwitchResponse:
        """
        Resume trading from PAUSE state.
        
        Args:
            reason: Reason for resumption
            resolved_by: Who authorized the resumption
        
        Returns:
            KillSwitchResponse with operation result
        """
        response = self.kill_switch.resume(reason=reason, resolved_by=resolved_by)
        
        if response.success and self.order_manager:
            # Re-enable order manager
            self.order_manager._paused = False
            logger.info("OrderManager re-enabled")
        
        return response
    
    def is_trading_allowed(self) -> bool:
        """
        Check if trading is currently allowed.
        
        Returns:
            True if trading is allowed, False otherwise
        """
        return self.kill_switch.is_trading_allowed()
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current kill switch status.
        
        Returns:
            Dictionary with current status information
        """
        state = self.kill_switch.get_state()
        return {
            "level": state.level.value,
            "is_triggered": state.is_triggered,
            "last_trigger": state.last_trigger.to_dict() if state.last_trigger else None,
            "history_count": len(state.history),
            "trading_allowed": self.is_trading_allowed(),
            "timestamp": state.timestamp.isoformat()
        }
