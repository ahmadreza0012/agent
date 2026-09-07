"""
Live Safety Integration - Connect safety engine to trading system.

This module provides the integration layer that wraps all trading operations
with comprehensive safety checks.
"""

from typing import Dict, Any, Optional
import logging

from .live_safety_engine import LiveSafetyEngine
from .order_manager import EnhancedOrderManager
from .position_manager import PositionManager
from .risk_engine import RiskEngine

logger = logging.getLogger(__name__)


class LiveSafetyIntegration:
    """
    Integrates the safety engine with the trading system.
    
    This class wraps all trading operations with safety checks, ensuring
    that no trade can execute without passing all safety validations.
    
    Usage:
        # Initialize
        integration = LiveSafetyIntegration(
            safety_engine=safety_engine,
            order_manager=order_manager,
            position_manager=position_manager,
            risk_engine=risk_engine
        )
        
        # Execute trades safely
        result = integration.execute_order_safely(order_request)
        if not result['success']:
            logger.error(f"Trade blocked: {result['error']}")
    """
    
    def __init__(
        self,
        safety_engine: LiveSafetyEngine,
        order_manager: EnhancedOrderManager,
        position_manager: PositionManager,
        risk_engine: Optional[RiskEngine] = None
    ):
        """
        Initialize the live safety integration.
        
        Args:
            safety_engine: Live safety engine for pre/post trade checks
            order_manager: Order manager for executing trades
            position_manager: Position manager for tracking positions
            risk_engine: Optional risk engine for additional risk checks
        """
        self.safety_engine = safety_engine
        self.order_manager = order_manager
        self.position_manager = position_manager
        self.risk_engine = risk_engine
        
        logger.info("LiveSafetyIntegration initialized")
        logger.info(f"Safety Engine: {safety_engine.__class__.__name__}")
        logger.info(f"Order Manager: {order_manager.__class__.__name__}")
        logger.info(f"Position Manager: {position_manager.__class__.__name__}")
        logger.info(f"Risk Engine: {risk_engine.__class__.__name__ if risk_engine else 'None'}")
    
    def execute_order_safely(self, order_request: Dict) -> Dict[str, Any]:
        """
        Execute an order with full safety checks.
        
        This is the PRIMARY entry point for ALL live trades. It ensures:
        1. Pre-trade safety checks pass
        2. Risk engine approval (if configured)
        3. Order execution
        4. Post-trade state update
        
        Args:
            order_request: Dictionary with order details:
                - symbol: Trading pair (e.g., 'BTC/USDT')
                - side: 'BUY' or 'SELL'
                - amount: Order amount
                - price: Optional limit price
                - type: Optional order type ('MARKET' or 'LIMIT')
        
        Returns:
            Dictionary with execution result:
                - success: bool
                - order: Order object (if successful)
                - error: Error message (if failed)
                - safety_result: Safety check result
                - risk_result: Risk engine result (if configured)
        """
        logger.info(f"Attempting safe order execution: {order_request}")
        
        # Step 1: Run pre-trade safety checks
        logger.debug("Step 1: Running pre-trade safety checks...")
        safety_result = self.safety_engine.pre_trade_check(order_request)
        
        if not safety_result.is_safe:
            error_msg = f"Safety check failed: {safety_result.reason}"
            logger.warning(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'safety_result': safety_result.to_dict(),
                'blocked_by': 'safety_engine'
            }
        
        logger.debug("✅ Pre-trade safety checks passed")
        
        # Step 2: Run risk engine (if configured)
        if self.risk_engine:
            logger.debug("Step 2: Running risk engine evaluation...")
            try:
                risk_result = self.risk_engine.evaluate()
                
                if not risk_result.get('allowed', False):
                    error_msg = f"Risk engine rejected: {risk_result.get('reason', 'Unknown risk')}"
                    logger.warning(f"❌ {error_msg}")
                    return {
                        'success': False,
                        'error': error_msg,
                        'risk_result': risk_result,
                        'blocked_by': 'risk_engine'
                    }
                
                logger.debug("✅ Risk engine approved")
                
            except Exception as e:
                error_msg = f"Risk engine error: {str(e)}"
                logger.error(f"❌ {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'blocked_by': 'risk_engine_error'
                }
        
        # Step 3: Execute order
        logger.debug("Step 3: Executing order...")
        try:
            order = self.order_manager.submit_order(order_request)
            
            logger.info(
                f"✅ Order executed successfully: {order.id} | "
                f"{order.side.value} {order.amount} {order.symbol} @ {order.price}"
            )
            
            # Step 4: Update safety state
            logger.debug("Step 4: Updating safety state...")
            self.safety_engine.post_trade_update({
                'pnl': 0,  # Will be updated when position closes
                'turnover': order.amount * order.price,
                'symbol': order.symbol,
                'side': order.side.value,
                'amount': order.amount,
                'price': order.price
            })
            
            return {
                'success': True,
                'order': order,
                'safety_result': safety_result.to_dict(),
                'executed_at': order.timestamp.isoformat() if order.timestamp else None
            }
            
        except Exception as e:
            error_msg = f"Order execution failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'exception_type': type(e).__name__
            }
    
    def get_safety_status(self) -> Dict[str, Any]:
        """
        Get comprehensive safety status.
        
        Returns:
            Dictionary with current safety status including:
            - Engine status
            - Check status details
            - Kill switch state
            - Can trade flag
        """
        engine_status = self.safety_engine.get_status()
        check_status = self.safety_engine.get_check_status()
        
        return {
            'engine': engine_status,
            'checks': check_status,
            'can_trade': engine_status.get('can_trade', False),
            'timestamp': engine_status.get('timestamp')
        }
    
    def is_safe_to_trade(self) -> bool:
        """
        Quick check if it's currently safe to trade.
        
        Returns:
            True if all safety checks would pass
        """
        return self.safety_engine.can_trade()
    
    def force_halt(self, reason: str) -> Dict[str, Any]:
        """
        Force an immediate trading halt.
        
        Args:
            reason: Human-readable reason for the halt
            
        Returns:
            Status dictionary confirming the halt
        """
        logger.critical(f"🛑 FORCE HALT REQUESTED: {reason}")
        self.safety_engine.force_halt(reason)
        
        return {
            'halted': True,
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        }
    
    def reset_daily_limits(self) -> Dict[str, Any]:
        """
        Reset daily safety limits.
        
        Should be called at the start of each trading day.
        
        Returns:
            Status dictionary confirming the reset
        """
        self.safety_engine.reset_daily_limits()
        
        return {
            'reset': True,
            'timestamp': datetime.now().isoformat()
        }
    
    def attempt_exposure_increase(self) -> Dict[str, Any]:
        """
        Attempt to increase exposure based on ramp rules.
        
        Returns:
            Result of the exposure increase attempt
        """
        result = self.safety_engine.attempt_exposure_increase()
        
        return {
            'success': result.is_safe,
            'message': result.reason,
            'details': result.details
        }


# Import datetime for the halt method
from datetime import datetime
