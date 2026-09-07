"""
Live Safety Engine - Orchestrates all live safety checks and actions.

This module provides the central orchestrator for live trading safety,
integrating safety checks, kill switch, and continuous monitoring.
"""

from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
import logging
import threading

from .live_safety_config import LiveSafetyLimits, LiveSafetyState
from .safety_checker import SafetyChecker, SafetyCheckResult
from .kill_switch import KillSwitch
from .kill_switch_models import KillSwitchLevel, KillSwitchTrigger
from .exchange_adapter import ExchangeAdapter
from .position_manager import PositionManager

logger = logging.getLogger(__name__)


class LiveSafetyEngine:
    """
    Central orchestrator for live trading safety.
    
    Features:
    - Continuous safety monitoring
    - Pre-trade safety checks
    - Post-trade state updates
    - Automatic risk reduction via kill switch
    - Gradual exposure ramp management
    - Performance tracking
    - Alert system integration
    
    CRITICAL: This engine follows "fail closed" principle - if any critical
    check fails or data is unavailable, trading is halted immediately.
    """
    
    def __init__(
        self,
        limits: LiveSafetyLimits,
        kill_switch: KillSwitch,
        exchange_adapter: ExchangeAdapter,
        position_manager: Optional[PositionManager] = None,
        market_data_provider: Optional[Any] = None,
        alert_callback: Optional[Callable[[str, str], None]] = None
    ):
        """
        Initialize the live safety engine.
        
        Args:
            limits: Safety limits configuration
            kill_switch: Kill switch instance for emergency halts
            exchange_adapter: Exchange adapter for health checks
            position_manager: Position manager for position limits
            market_data_provider: Provider for real-time market data
            alert_callback: Optional callback for alerts (level, message)
        """
        self.limits = limits
        self.kill_switch = kill_switch
        self.exchange = exchange_adapter
        self.position_manager = position_manager
        self.market_data = market_data_provider
        self.alert_callback = alert_callback
        
        # Initialize state
        self.state = LiveSafetyState()
        
        # Initialize safety checker
        self.safety_checker = SafetyChecker(
            limits=limits,
            state=self.state,
            exchange_adapter=exchange_adapter,
            position_manager=position_manager,
            market_data_provider=market_data_provider
        )
        
        # Monitoring state
        self._is_monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        
        # Validate limits on startup
        try:
            limits.validate()
            logger.info("LiveSafetyEngine initialized with validated limits")
        except ValueError as e:
            logger.error(f"Invalid safety limits: {e}")
            raise
        
        logger.info("=" * 60)
        logger.info("LIVE SAFETY ENGINE INITIALIZED")
        logger.info("=" * 60)
        logger.info(f"Kill Switch: {'Active' if kill_switch else 'None'}")
        logger.info(f"Exchange Adapter: {exchange_adapter.__class__.__name__}")
        logger.info(f"Position Manager: {position_manager.__class__.__name__ if position_manager else 'None'}")
        logger.info(f"Market Data Provider: {market_data_provider.__class__.__name__ if market_data_provider else 'None'}")
        logger.info(f"Alert Callback: {'Configured' if alert_callback else 'None'}")
        logger.info("=" * 60)
    
    def pre_trade_check(self, order_request: Optional[Dict] = None) -> SafetyCheckResult:
        """
        Run safety checks BEFORE allowing a trade.
        
        This is the primary entry point for safety validation. Every trade
        request MUST pass through this method before execution.
        
        Args:
            order_request: Optional order details for order-specific checks
            
        Returns:
            SafetyCheckResult indicating if trade is allowed
            
        CRITICAL: If this returns False, the trade MUST NOT be executed.
        """
        # Update state from current positions
        self._update_state()
        
        # Check if kill switch is already active
        if not self.kill_switch.is_trading_allowed():
            return SafetyCheckResult(
                False,
                "Kill switch is active - trading halted",
                {'kill_switch_state': self.kill_switch.get_state().level.value}
            )
        
        # Run all safety checks
        result = self.safety_checker.check_all(order_request)
        
        if not result.is_safe:
            logger.critical(f"❌ PRE-TRADE CHECK FAILED: {result.reason}")
            self._send_alert("CRITICAL", f"Pre-trade safety check failed: {result.reason}")
            
            # Trigger safety halt for critical failures
            if result.details.get('limit_type') == 'hard':
                self._trigger_safety_halt(result)
            
            return result
        
        logger.debug(f"✅ Pre-trade check passed: {order_request.get('symbol', 'N/A') if order_request else 'No order'}")
        return result
    
    def post_trade_update(self, trade_result: Dict) -> None:
        """
        Update safety state AFTER a trade executes.
        
        Args:
            trade_result: Dictionary with trade details including:
                - pnl: Realized P&L
                - turnover: Dollar turnover
                - symbol: Trading pair
                - side: BUY/SELL
                - amount: Trade amount
                - price: Trade price
        """
        pnl = trade_result.get('pnl', 0.0)
        turnover = trade_result.get('turnover', 0.0)
        symbol = trade_result.get('symbol', '')
        side = trade_result.get('side', '')
        amount = trade_result.get('amount', 0.0)
        price = trade_result.get('price', 0.0)
        
        # Record trade in state
        self.state.record_trade(
            pnl=pnl,
            turnover=turnover,
            symbol=symbol,
            side=side,
            amount=amount,
            price=price
        )
        
        # Update equity and drawdown
        self._update_state()
        
        # Check if day was positive (for exposure ramp)
        if self.state.daily_pnl > 0:
            self.state.increment_positive_days()
        else:
            self.state.reset_positive_days()
        
        logger.debug(
            f"Post-trade update | PnL=${pnl:,.2f} | Daily PnL=${self.state.daily_pnl:,.2f} | "
            f"Trades={self.state.daily_trades}"
        )
    
    def _update_state(self) -> None:
        """Update safety state from current market data and positions."""
        try:
            # Calculate current equity
            total_equity = self._calculate_equity()
            
            # Update state with new equity
            self.state.update_equity(total_equity)
            
            # Update exposure ratio
            if self.position_manager and total_equity > 0:
                total_exposure = sum(
                    abs(p.size) * p.current_price 
                    for p in self.position_manager.positions.values()
                )
                self.state.exposure_ratio = total_exposure / total_equity
                
                # Update position weights
                for symbol, position in self.position_manager.positions.items():
                    value = abs(position.size) * position.current_price
                    self.state.current_position_weights[symbol] = value / total_equity
            
            # Mark state as active
            self.state.is_active = True
            
        except Exception as e:
            logger.error(f"Failed to update safety state: {e}")
            self.state.record_data_quality_issue()
    
    def _calculate_equity(self) -> float:
        """Calculate current total equity."""
        try:
            # Get balances from exchange
            balances = self.exchange.get_balance()
            total = sum(b.total for b in balances.values())
            
            # Add position values
            if self.position_manager:
                positions = self.position_manager.get_positions()
                total += sum(p.size * p.current_price for p in positions)
            else:
                positions = self.exchange.get_positions()
                total += sum(p.size * p.current_price for p in positions)
            
            return total
            
        except Exception as e:
            logger.error(f"Failed to calculate equity: {e}")
            # Return last known equity on error
            return self.state.current_equity
    
    def _trigger_safety_halt(self, result: SafetyCheckResult) -> None:
        """
        Trigger a safety halt via the kill switch.
        
        Args:
            result: The safety check result that triggered the halt
        """
        # Determine trigger type
        trigger = KillSwitchTrigger.SYSTEM_ERROR
        if 'drawdown' in result.reason.lower():
            trigger = KillSwitchTrigger.DRAWDOWN
        elif 'daily loss' in result.reason.lower():
            trigger = KillSwitchTrigger.DAILY_LOSS
        elif 'position' in result.reason.lower():
            trigger = KillSwitchTrigger.POSITION_LIMIT
        elif 'exposure' in result.reason.lower():
            trigger = KillSwitchTrigger.POSITION_LIMIT
        elif 'exchange' in result.reason.lower():
            trigger = KillSwitchTrigger.EXCHANGE_ERROR
        elif 'data' in result.reason.lower():
            trigger = KillSwitchTrigger.DATA_ERROR
        
        # Trigger kill switch at HALT level
        self.kill_switch.trigger(
            level=KillSwitchLevel.HALT,
            trigger=trigger,
            reason=f"Safety check failed: {result.reason}",
            details=result.details,
            triggered_by="safety_engine"
        )
        
        # Update state
        self.state.is_halted = True
        self.state.halt_reason = result.reason
        self.state.halt_timestamp = datetime.now()
        
        logger.critical(
            f"🛑 SAFETY HALT TRIGGERED | Reason: {result.reason} | "
            f"Trigger: {trigger.value} | Level: {KillSwitchLevel.HALT.value}"
        )
        
        self._send_alert("EMERGENCY", f"Safety halt triggered: {result.reason}")
    
    def start_monitoring(self) -> None:
        """Start continuous safety monitoring in background thread."""
        if self._is_monitoring:
            logger.warning("Safety monitoring already running")
            return
        
        self._is_monitoring = True
        self._stop_monitoring.clear()
        
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="SafetyMonitor"
        )
        self._monitor_thread.start()
        
        logger.info("Live safety monitoring started")
        self._send_alert("INFO", "Safety monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop continuous safety monitoring."""
        if not self._is_monitoring:
            return
        
        self._stop_monitoring.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        
        self._is_monitoring = False
        logger.info("Live safety monitoring stopped")
        self._send_alert("INFO", "Safety monitoring stopped")
    
    def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while not self._stop_monitoring.is_set():
            try:
                # Update state
                self._update_state()
                
                # Check exchange health
                health_result = self.safety_checker.check_exchange_health()
                if not health_result.is_safe:
                    logger.warning(f"Continuous monitoring: {health_result.reason}")
                
                # Check data quality
                data_result = self.safety_checker.check_data_quality()
                if not data_result.is_safe:
                    logger.warning(f"Continuous monitoring: {data_result.reason}")
                
                # Check loss limits (without order request)
                loss_result = self.safety_checker.check_loss_limits()
                if not loss_result.is_safe and loss_result.details.get('limit_type') == 'hard':
                    self._trigger_safety_halt(loss_result)
                
                # Sleep until next check
                self._stop_monitoring.wait(self.limits.exchange_health_check_seconds)
                
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                self._stop_monitoring.wait(1.0)  # Brief pause on error
    
    def get_status(self) -> Dict[str, Any]:
        """Get current safety status summary."""
        return {
            'is_active': self.state.is_active,
            'is_halted': self.state.is_halted,
            'halt_reason': self.state.halt_reason,
            'halt_timestamp': self.state.halt_timestamp.isoformat() if self.state.halt_timestamp else None,
            'daily_pnl': self.state.daily_pnl,
            'daily_pnl_percent': (self.state.daily_pnl / self.state.current_equity * 100) if self.state.current_equity > 0 else 0,
            'daily_trades': self.state.daily_trades,
            'daily_turnover': self.state.daily_turnover,
            'current_drawdown': self.state.current_drawdown,
            'current_equity': self.state.current_equity,
            'peak_equity': self.state.peak_equity,
            'exposure_ratio': self.state.exposure_ratio,
            'can_trade': self.can_trade(),
            'kill_switch_allowed': self.kill_switch.is_trading_allowed(),
            'api_consecutive_failures': self.state.consecutive_failures,
            'positive_days_count': self.state.positive_days_count,
            'timestamp': datetime.now().isoformat()
        }
    
    def can_trade(self) -> bool:
        """Check if trading is currently allowed."""
        return (
            not self.state.is_halted and
            self.kill_switch.is_trading_allowed() and
            self.state.consecutive_failures < self.limits.max_api_failures
        )
    
    def reset_daily_limits(self) -> None:
        """
        Reset daily limits (should be called at day start).
        
        This resets daily P&L, trade count, and turnover counters.
        """
        self.state.reset_daily()
        logger.info("Daily safety limits reset")
        self._send_alert("INFO", "Daily safety limits reset")
    
    def initialize_exposure_ramp(self) -> None:
        """Initialize the gradual exposure ramp."""
        self.state.exposure_start_date = datetime.now()
        self.state.exposure_ratio = self.limits.initial_exposure_ratio
        self.state.positive_days_count = 0
        logger.info(
            f"Exposure ramp initialized at {self.limits.initial_exposure_ratio*100:.1f}% "
            f"initial exposure"
        )
    
    def attempt_exposure_increase(self) -> SafetyCheckResult:
        """
        Attempt to increase exposure based on ramp rules.
        
        Returns:
            SafetyCheckResult indicating if increase is allowed
        """
        if not self.state.can_increase_exposure(self.limits):
            return SafetyCheckResult(
                False,
                "Exposure increase conditions not met",
                {
                    'positive_days': self.state.positive_days_count,
                    'required': self.limits.required_positive_days
                }
            )
        
        # Calculate new exposure
        current_exposure = self.state.exposure_ratio
        max_increment = self.limits.max_exposure_increment
        target_exposure = self.limits.max_total_exposure
        
        new_exposure = min(current_exposure + max_increment, target_exposure)
        
        # Update state
        self.state.exposure_ratio = new_exposure
        self.state.last_exposure_increase = datetime.now()
        self.state.exposure_step += 1
        
        logger.info(
            f"Exposure increased: {current_exposure*100:.1f}% -> {new_exposure*100:.1f}% "
            f"(step {self.state.exposure_step})"
        )
        
        self._send_alert("INFO", f"Exposure increased to {new_exposure*100:.1f}%")
        
        return SafetyCheckResult(
            True,
            f"Exposure increased to {new_exposure*100:.1f}%",
            {'new_exposure': new_exposure, 'step': self.state.exposure_step}
        )
    
    def _send_alert(self, level: str, message: str) -> None:
        """Send an alert via configured callback."""
        if self.alert_callback:
            try:
                self.alert_callback(level, message)
            except Exception as e:
                logger.error(f"Failed to send alert: {e}")
        else:
            # Log alert if no callback configured
            log_level = {
                'INFO': logging.INFO,
                'WARNING': logging.WARNING,
                'CRITICAL': logging.CRITICAL,
                'EMERGENCY': logging.CRITICAL
            }.get(level, logging.INFO)
            logger.log(log_level, f"[ALERT] {message}")
    
    def get_check_status(self) -> Dict[str, Any]:
        """Get detailed status of all safety checks."""
        return self.safety_checker.get_check_status()
    
    def force_halt(self, reason: str) -> None:
        """
        Force an immediate safety halt.
        
        Args:
            reason: Human-readable reason for the halt
        """
        logger.critical(f"🛑 FORCE HALT TRIGGERED: {reason}")
        
        self.kill_switch.trigger(
            level=KillSwitchLevel.HALT,
            trigger=KillSwitchTrigger.MANUAL,
            reason=reason,
            details={},
            triggered_by="safety_engine_force"
        )
        
        self.state.is_halted = True
        self.state.halt_reason = reason
        self.state.halt_timestamp = datetime.now()
        
        self._send_alert("EMERGENCY", f"Force halt: {reason}")
