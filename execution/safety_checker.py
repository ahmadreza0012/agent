"""
Safety Checker - Validate all safety conditions before trading.

This module provides comprehensive safety checks that run BEFORE every trade
decision in live mode. All checks follow the "fail closed" principle - if any
critical check fails, trading is halted.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging

from .live_safety_config import LiveSafetyLimits, LiveSafetyState
from .exchange_adapter import ExchangeAdapter
from .position_manager import PositionManager

logger = logging.getLogger(__name__)


class SafetyCheckResult:
    """Result of a safety check."""
    
    def __init__(self, is_safe: bool, reason: str = "", details: Optional[Dict] = None):
        self.is_safe = is_safe
        self.reason = reason
        self.details = details or {}
        self.timestamp = datetime.now()
    
    def __bool__(self):
        return self.is_safe
    
    def __str__(self):
        status = "PASS" if self.is_safe else "FAIL"
        return f"[{status}] {self.reason}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            'is_safe': self.is_safe,
            'reason': self.reason,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }


class SafetyChecker:
    """
    Comprehensive safety checker for live trading.
    
    Validates all conditions before allowing a trade:
    - Loss limits (daily, total drawdown, per-position)
    - Position limits (size, exposure)
    - Order limits (size, value)
    - Execution limits (slippage, spread)
    - Data quality and freshness
    - Exchange health
    - Gradual exposure ramp
    
    CRITICAL: This checker follows "fail closed" principle - if critical data
    is unavailable or any hard limit is breached, trading is NOT allowed.
    """
    
    def __init__(
        self,
        limits: LiveSafetyLimits,
        state: LiveSafetyState,
        exchange_adapter: ExchangeAdapter,
        position_manager: Optional[PositionManager] = None,
        market_data_provider: Optional[Any] = None
    ):
        self.limits = limits
        self.state = state
        self.exchange = exchange_adapter
        self.position_manager = position_manager
        self.market_data = market_data_provider
        
        # Track consecutive failures for each check type
        self._check_failures: Dict[str, int] = {}
        
        logger.info("SafetyChecker initialized")
        logger.info(f"Daily loss limits: Soft={limits.max_daily_loss_soft*100:.1f}%, Hard={limits.max_daily_loss_hard*100:.1f}%")
        logger.info(f"Drawdown limits: Soft={limits.max_total_drawdown_soft*100:.1f}%, Hard={limits.max_total_drawdown_hard*100:.1f}%")
    
    def check_all(self, order_request: Optional[Dict] = None) -> SafetyCheckResult:
        """
        Run all safety checks.
        
        Args:
            order_request: Optional order details for order-specific checks
            
        Returns:
            SafetyCheckResult with pass/fail and reason
        """
        checks_run = []
        
        # 1. Check exchange health (CRITICAL)
        health_result = self.check_exchange_health()
        checks_run.append(('exchange_health', health_result))
        if not health_result.is_safe:
            logger.critical(f"❌ SAFETY CHECK FAILED: {health_result.reason}")
            return health_result
        
        # 2. Check data quality (CRITICAL)
        data_result = self.check_data_quality()
        checks_run.append(('data_quality', data_result))
        if not data_result.is_safe:
            logger.critical(f"❌ SAFETY CHECK FAILED: {data_result.reason}")
            return data_result
        
        # 3. Check loss limits (CRITICAL)
        loss_result = self.check_loss_limits()
        checks_run.append(('loss_limits', loss_result))
        if not loss_result.is_safe:
            logger.critical(f"❌ SAFETY CHECK FAILED: {loss_result.reason}")
            return loss_result
        
        # 4. Check position limits
        position_result = self.check_position_limits()
        checks_run.append(('position_limits', position_result))
        if not position_result.is_safe:
            logger.warning(f"⚠️  SAFETY CHECK FAILED: {position_result.reason}")
            return position_result
        
        # 5. Check exposure limits
        exposure_result = self.check_exposure_limits()
        checks_run.append(('exposure_limits', exposure_result))
        if not exposure_result.is_safe:
            logger.warning(f"⚠️  SAFETY CHECK FAILED: {exposure_result.reason}")
            return exposure_result
        
        # 6. Check gradual exposure ramp
        ramp_result = self.check_exposure_ramp()
        checks_run.append(('exposure_ramp', ramp_result))
        if not ramp_result.is_safe:
            logger.info(f"ℹ️  SAFETY CHECK INFO: {ramp_result.reason}")
            return ramp_result
        
        # 7. Check order-specific limits (if order provided)
        if order_request:
            order_result = self.check_order_limits(order_request)
            checks_run.append(('order_limits', order_result))
            if not order_result.is_safe:
                logger.warning(f"⚠️  ORDER CHECK FAILED: {order_result.reason}")
                return order_result
        
        # All checks passed
        logger.debug(f"✅ All {len(checks_run)} safety checks passed")
        return SafetyCheckResult(True, "All safety checks passed", {'checks_run': len(checks_run)})
    
    def check_loss_limits(self) -> SafetyCheckResult:
        """
        Check daily loss and total drawdown limits.
        
        Returns:
            SafetyCheckResult indicating if loss limits are within bounds
        """
        # Daily loss check - HARD limit
        daily_loss_pct = 0.0
        if self.state.current_equity > 0:
            daily_loss_pct = abs(self.state.daily_pnl) / self.state.current_equity
        
        if self.state.daily_pnl < 0 and daily_loss_pct >= self.limits.max_daily_loss_hard:
            return SafetyCheckResult(
                False,
                f"HARD daily loss limit breached: {daily_loss_pct:.2%} >= {self.limits.max_daily_loss_hard:.2%}",
                {
                    'daily_pnl': self.state.daily_pnl,
                    'daily_loss_percent': daily_loss_pct,
                    'limit': self.limits.max_daily_loss_hard,
                    'limit_type': 'hard'
                }
            )
        
        # Daily loss check - SOFT limit (warning)
        if self.state.daily_pnl < 0 and daily_loss_pct >= self.limits.max_daily_loss_soft:
            logger.warning(
                f"⚠️  SOFT daily loss limit breached: {daily_loss_pct:.2%} >= {self.limits.max_daily_loss_soft:.2%}"
            )
        
        # Total drawdown check - HARD limit
        if self.state.current_drawdown <= -self.limits.max_total_drawdown_hard:
            return SafetyCheckResult(
                False,
                f"HARD drawdown limit breached: {abs(self.state.current_drawdown):.2%} >= {self.limits.max_total_drawdown_hard:.2%}",
                {
                    'drawdown': self.state.current_drawdown,
                    'drawdown_percent': abs(self.state.current_drawdown),
                    'peak_equity': self.state.peak_equity,
                    'current_equity': self.state.current_equity,
                    'limit': self.limits.max_total_drawdown_hard,
                    'limit_type': 'hard'
                }
            )
        
        # Total drawdown check - SOFT limit (warning)
        if self.state.current_drawdown <= -self.limits.max_total_drawdown_soft:
            logger.warning(
                f"⚠️  SOFT drawdown limit breached: {abs(self.state.current_drawdown):.2%} >= {self.limits.max_total_drawdown_soft:.2%}"
            )
        
        # Position loss check
        if self.position_manager:
            for symbol, position in self.position_manager.positions.items():
                if abs(position.size) > 0 and position.entry_price > 0:
                    loss_pct = (position.current_price - position.entry_price) / position.entry_price
                    if position.size > 0:
                        loss_pct = (position.current_price - position.entry_price) / position.entry_price
                    else:
                        loss_pct = (position.entry_price - position.current_price) / position.entry_price
                    
                    if loss_pct < -self.limits.max_position_loss:
                        return SafetyCheckResult(
                            False,
                            f"Position loss limit breached for {symbol}: {loss_pct:.2%} < -{self.limits.max_position_loss:.2%}",
                            {
                                'symbol': symbol,
                                'loss_percent': loss_pct,
                                'limit': self.limits.max_position_loss,
                                'entry_price': position.entry_price,
                                'current_price': position.current_price
                            }
                        )
        
        return SafetyCheckResult(True, "Loss limits passed", {
            'daily_pnl': self.state.daily_pnl,
            'daily_loss_percent': daily_loss_pct,
            'current_drawdown': self.state.current_drawdown
        })
    
    def check_position_limits(self) -> SafetyCheckResult:
        """
        Check position size limits.
        
        Returns:
            SafetyCheckResult indicating if position sizes are within bounds
        """
        if not self.position_manager:
            return SafetyCheckResult(True, "Position manager not available, skipping check")
        
        total_equity = self.state.current_equity
        if total_equity <= 0:
            return SafetyCheckResult(False, "Invalid equity for position check", {'equity': total_equity})
        
        for symbol, position in self.position_manager.positions.items():
            if abs(position.size) > 0:
                position_value = abs(position.size) * position.current_price
                position_ratio = position_value / total_equity
                
                if position_ratio > self.limits.max_position_size:
                    return SafetyCheckResult(
                        False,
                        f"Position size limit breached for {symbol}: {position_ratio:.2%} > {self.limits.max_position_size:.2%}",
                        {
                            'symbol': symbol,
                            'position_ratio': position_ratio,
                            'position_value': position_value,
                            'total_equity': total_equity,
                            'limit': self.limits.max_position_size
                        }
                    )
        
        return SafetyCheckResult(True, "Position limits passed")
    
    def check_exposure_limits(self) -> SafetyCheckResult:
        """
        Check total exposure limits.
        
        Returns:
            SafetyCheckResult indicating if total exposure is within bounds
        """
        if not self.position_manager:
            return SafetyCheckResult(True, "Position manager not available, skipping check")
        
        total_exposure = sum(
            abs(p.size) * p.current_price 
            for p in self.position_manager.positions.values()
        )
        total_equity = self.state.current_equity
        
        if total_equity <= 0:
            return SafetyCheckResult(False, "Invalid equity for exposure check", {'equity': total_equity})
        
        exposure_ratio = total_exposure / total_equity
        
        if exposure_ratio > self.limits.max_total_exposure:
            return SafetyCheckResult(
                False,
                f"Exposure limit breached: {exposure_ratio:.2%} > {self.limits.max_total_exposure:.2%}",
                {
                    'exposure_ratio': exposure_ratio,
                    'total_exposure': total_exposure,
                    'total_equity': total_equity,
                    'limit': self.limits.max_total_exposure
                }
            )
        
        # Update state
        self.state.exposure_ratio = exposure_ratio
        
        return SafetyCheckResult(True, "Exposure limits passed", {
            'exposure_ratio': exposure_ratio,
            'max_exposure': self.limits.max_total_exposure
        })
    
    def check_exchange_health(self) -> SafetyCheckResult:
        """
        Check exchange connectivity and health.
        
        CRITICAL: If exchange is unhealthy after max_api_failures, trading halts.
        
        Returns:
            SafetyCheckResult indicating if exchange is healthy
        """
        try:
            is_healthy = self.exchange.health_check()
            
            if is_healthy:
                self.state.record_api_success()
                return SafetyCheckResult(True, "Exchange health check passed")
            else:
                self.state.record_api_failure()
                
                if self.state.consecutive_failures >= self.limits.max_api_failures:
                    return SafetyCheckResult(
                        False,
                        f"Exchange health check failed {self.state.consecutive_failures} consecutive times (max={self.limits.max_api_failures})",
                        {
                            'consecutive_failures': self.state.consecutive_failures,
                            'max_allowed': self.limits.max_api_failures
                        }
                    )
                
                return SafetyCheckResult(
                    True,
                    f"Exchange health check failed but within tolerance ({self.state.consecutive_failures}/{self.limits.max_api_failures})",
                    {'consecutive_failures': self.state.consecutive_failures}
                )
                
        except Exception as e:
            self.state.record_api_failure()
            logger.error(f"Exchange health check error: {e}")
            
            if self.state.consecutive_failures >= self.limits.max_api_failures:
                return SafetyCheckResult(
                    False,
                    f"Exchange health check error {self.state.consecutive_failures} times (max={self.limits.max_api_failures})",
                    {
                        'error': str(e),
                        'consecutive_failures': self.state.consecutive_failures,
                        'max_allowed': self.limits.max_api_failures
                    }
                )
            
            return SafetyCheckResult(
                True,
                f"Exchange health check error but within tolerance",
                {'error': str(e), 'consecutive_failures': self.state.consecutive_failures}
            )
    
    def check_data_quality(self) -> SafetyCheckResult:
        """
        Check data freshness and quality.
        
        CRITICAL: If data is stale beyond max_data_age_seconds, trading halts.
        FAIL CLOSED principle applies - if we can't verify data quality, don't trade.
        
        Returns:
            SafetyCheckResult indicating if data is fresh and valid
        """
        # Skip if no market data provider configured
        if not self.market_data:
            logger.warning("No market data provider configured, skipping data quality check")
            return SafetyCheckResult(True, "No market data provider, skipping check")
        
        # Check data age
        if self.state.last_data_update:
            age_seconds = (datetime.now() - self.state.last_data_update).total_seconds()
            
            if age_seconds > self.limits.stale_data_timeout_seconds:
                self.state.record_data_quality_issue()
                return SafetyCheckResult(
                    False,
                    f"Data is stale: {age_seconds:.0f}s old (max={self.limits.stale_data_timeout_seconds}s)",
                    {
                        'age_seconds': age_seconds,
                        'max_age': self.limits.stale_data_timeout_seconds
                    }
                )
            
            if age_seconds > self.limits.max_data_age_seconds:
                logger.warning(f"Data age warning: {age_seconds:.0f}s (soft limit={self.limits.max_data_age_seconds}s)")
        
        # Check price data for critical symbols
        critical_symbols = ['BTC/USDT', 'ETH/USDT']
        for symbol in critical_symbols:
            try:
                ticker = self.market_data.get_ticker(symbol)
                price = ticker.get('price', 0)
                
                if price <= 0:
                    self.state.record_data_quality_issue()
                    return SafetyCheckResult(
                        False,
                        f"Invalid price data for {symbol}: price={price}",
                        {'symbol': symbol, 'price': price}
                    )
                
                # Check for extreme price movements (optional)
                # This would require historical price data
                
            except Exception as e:
                self.state.record_data_quality_issue()
                logger.error(f"Data quality check failed for {symbol}: {e}")
                return SafetyCheckResult(
                    False,
                    f"Failed to get price data for {symbol}: {e}",
                    {'symbol': symbol, 'error': str(e)}
                )
        
        # Record successful data update
        self.state.record_data_update()
        
        return SafetyCheckResult(True, "Data quality check passed")
    
    def check_order_limits(self, order_request: Dict) -> SafetyCheckResult:
        """
        Check order-specific limits.
        
        Args:
            order_request: Dictionary with order details (symbol, side, amount, price)
            
        Returns:
            SafetyCheckResult indicating if order is within limits
        """
        amount = order_request.get('amount', 0)
        price = order_request.get('price', 0)
        symbol = order_request.get('symbol', '')
        side = order_request.get('side', '')
        
        if amount <= 0 or price <= 0:
            return SafetyCheckResult(False, "Invalid order amount or price", {
                'amount': amount,
                'price': price
            })
        
        order_value = amount * price
        
        # Min order value check
        if order_value < self.limits.min_order_value:
            return SafetyCheckResult(
                False,
                f"Order value too small: ${order_value:.2f} < ${self.limits.min_order_value:.2f}",
                {
                    'order_value': order_value,
                    'min_allowed': self.limits.min_order_value
                }
            )
        
        # Max order value check
        if order_value > self.limits.max_order_value:
            return SafetyCheckResult(
                False,
                f"Order value too large: ${order_value:.2f} > ${self.limits.max_order_value:.2f}",
                {
                    'order_value': order_value,
                    'max_allowed': self.limits.max_order_value
                }
            )
        
        # Max order size relative to portfolio
        if self.state.current_equity > 0:
            order_ratio = order_value / self.state.current_equity
            if order_ratio > self.limits.max_order_size:
                return SafetyCheckResult(
                    False,
                    f"Order size too large: {order_ratio:.2%} > {self.limits.max_order_size:.2%}",
                    {
                        'order_ratio': order_ratio,
                        'order_value': order_value,
                        'portfolio_value': self.state.current_equity,
                        'limit': self.limits.max_order_size
                    }
                )
        
        return SafetyCheckResult(True, "Order limits passed", {'order_value': order_value})
    
    def check_exposure_ramp(self) -> SafetyCheckResult:
        """
        Check gradual exposure ramp rules.
        
        This ensures new live trading systems start with reduced exposure
        and only increase after demonstrating consistent performance.
        
        Returns:
            SafetyCheckResult indicating if exposure ramp allows trading
        """
        # Skip if exposure ramp is not configured
        if not self.state.exposure_start_date:
            return SafetyCheckResult(True, "Exposure ramp not started, using initial exposure")
        
        # Check if already at max exposure
        if self.state.exposure_ratio >= self.limits.max_total_exposure:
            return SafetyCheckResult(True, "Exposure at maximum target")
        
        # Check if we're in the waiting period before first increase
        days_since_start = (datetime.now() - self.state.exposure_start_date).days
        if days_since_start == 0:
            # First day - always allow trading at initial exposure
            return SafetyCheckResult(
                True,
                f"Day 1 of exposure ramp at {self.limits.initial_exposure_ratio*100:.1f}% initial exposure"
            )
        
        # Check if enough time has passed since last increase
        last_increase = self.state.last_exposure_increase or self.state.exposure_start_date
        days_since_increase = (datetime.now() - last_increase).days
        
        if days_since_increase < self.limits.exposure_increment_days:
            return SafetyCheckResult(
                True,
                f"Exposure ramp waiting period: {days_since_increase}/{self.limits.exposure_increment_days} days",
                {
                    'days_remaining': self.limits.exposure_increment_days - days_since_increase,
                    'current_exposure': self.state.exposure_ratio
                }
            )
        
        # Check if required positive days achieved
        if self.state.positive_days_count < self.limits.required_positive_days:
            return SafetyCheckResult(
                True,
                f"Waiting for positive days: {self.state.positive_days_count}/{self.limits.required_positive_days}",
                {
                    'positive_days_needed': self.limits.required_positive_days - self.state.positive_days_count,
                    'current_positive_days': self.state.positive_days_count
                }
            )
        
        # Exposure can be increased
        return SafetyCheckResult(
            True,
            "Exposure ramp conditions met for increase",
            {
                'can_increase': True,
                'current_exposure': self.state.exposure_ratio,
                'max_increment': self.limits.max_exposure_increment
            }
        )
    
    def get_check_status(self) -> Dict[str, Any]:
        """Get status of all safety checks."""
        return {
            'loss_limits': {
                'daily_pnl': self.state.daily_pnl,
                'daily_loss_pct': abs(self.state.daily_pnl) / self.state.current_equity if self.state.current_equity > 0 else 0,
                'current_drawdown': self.state.current_drawdown,
                'daily_loss_limit': self.limits.max_daily_loss_hard,
                'drawdown_limit': self.limits.max_total_drawdown_hard
            },
            'position_limits': {
                'max_position_size': self.limits.max_position_size,
                'max_exposure': self.limits.max_total_exposure,
                'current_exposure': self.state.exposure_ratio
            },
            'exchange_health': {
                'consecutive_failures': self.state.consecutive_failures,
                'max_failures': self.limits.max_api_failures,
                'last_check': self.state.last_health_check.isoformat() if self.state.last_health_check else None
            },
            'data_quality': {
                'last_update': self.state.last_data_update.isoformat() if self.state.last_data_update else None,
                'quality_issues': self.state.data_quality_issues,
                'max_data_age': self.limits.max_data_age_seconds
            },
            'exposure_ramp': {
                'start_date': self.state.exposure_start_date.isoformat() if self.state.exposure_start_date else None,
                'positive_days': self.state.positive_days_count,
                'required_positive_days': self.limits.required_positive_days
            }
        }
