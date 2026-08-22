"""
Live Safety Configuration - All safety limits for live trading.

This module defines comprehensive safety limits and state tracking for live trading.
All limits have both SOFT (warning) and HARD (stop trading) boundaries.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class LiveSafetyLimits:
    """
    Hard and soft limits for live trading safety.
    
    All limits follow the pattern:
    - SOFT limit: Triggers warning/alert
    - HARD limit: Stops trading immediately
    """
    
    # ===== LOSS LIMITS =====
    # Daily loss limits (reset at day start)
    max_daily_loss_soft: float = 0.02      # 2% - triggers warning
    max_daily_loss_hard: float = 0.05      # 5% - stops trading
    
    # Total drawdown limits (cumulative from peak equity)
    max_total_drawdown_soft: float = 0.10  # 10% - triggers warning
    max_total_drawdown_hard: float = 0.15  # 15% - stops trading
    
    # Per-position loss limit
    max_position_loss: float = 0.10        # 10% per position
    
    # ===== POSITION LIMITS =====
    # Maximum position size as % of portfolio
    max_position_size: float = 0.20        # 20% of portfolio per position
    
    # Maximum total exposure as % of portfolio
    max_total_exposure: float = 0.60       # 60% of portfolio total
    
    # Leverage limits
    max_leverage: float = 1.0              # No leverage by default
    
    # Daily turnover limit (% of portfolio)
    max_turnover_per_day: float = 2.0      # 200% daily turnover
    
    # ===== ORDER LIMITS =====
    # Maximum order size as % of portfolio
    max_order_size: float = 0.10           # 10% of portfolio per order
    
    # Absolute order value limits (USD)
    max_order_value: float = 100000.0      # Maximum USD per order
    min_order_value: float = 10.0          # Minimum USD per order
    
    # ===== EXECUTION LIMITS =====
    # Maximum acceptable slippage
    max_slippage: float = 0.005            # 0.5% max slippage
    
    # Maximum acceptable bid-ask spread
    max_spread: float = 0.01               # 1% max spread
    
    # Maximum execution time before timeout
    max_execution_time_ms: float = 5000    # 5 second timeout
    
    # ===== DATA LIMITS =====
    # Time before data is considered stale
    stale_data_timeout_seconds: int = 60   # 1 minute
    
    # Maximum age of price data for trading decisions
    max_data_age_seconds: int = 10         # 10 seconds for price data
    
    # ===== EXCHANGE LIMITS =====
    # How often to check exchange health
    exchange_health_check_seconds: int = 10
    
    # Consecutive API failures before halt
    max_api_failures: int = 3              # 3 failures before halt
    
    # ===== GRADUAL EXPOSURE =====
    # Start with reduced exposure
    initial_exposure_ratio: float = 0.10   # Start with 10% exposure
    
    # Days between exposure increases
    exposure_increment_days: int = 7       # Increase every 7 days
    
    # Maximum exposure increase per step
    max_exposure_increment: float = 0.10   # Max 10% increase per step
    
    # Required positive days before increasing exposure
    required_positive_days: int = 5        # Need 5 positive days
    
    def validate(self) -> bool:
        """Validate that all limits are within reasonable bounds."""
        errors = []
        
        # Loss limits must be negative (representing losses)
        if self.max_daily_loss_soft <= 0 or self.max_daily_loss_hard <= 0:
            errors.append("Daily loss limits must be positive values")
        if self.max_daily_loss_hard <= self.max_daily_loss_soft:
            errors.append("Hard daily loss must be greater than soft limit")
        
        # Drawdown limits
        if self.max_total_drawdown_soft <= 0 or self.max_total_drawdown_hard <= 0:
            errors.append("Drawdown limits must be positive values")
        if self.max_total_drawdown_hard <= self.max_total_drawdown_soft:
            errors.append("Hard drawdown must be greater than soft limit")
        
        # Position limits must be between 0 and 1
        if not 0 < self.max_position_size <= 1:
            errors.append("Max position size must be between 0 and 1")
        if not 0 < self.max_total_exposure <= 1:
            errors.append("Max total exposure must be between 0 and 1")
        
        # Order limits
        if self.min_order_value <= 0:
            errors.append("Min order value must be positive")
        if self.max_order_value <= self.min_order_value:
            errors.append("Max order value must be greater than min")
        
        # Execution limits
        if self.max_slippage <= 0 or self.max_slippage > 0.1:
            errors.append("Max slippage must be between 0 and 10%")
        if self.max_spread <= 0 or self.max_spread > 0.2:
            errors.append("Max spread must be between 0 and 20%")
        
        # Data limits
        if self.max_data_age_seconds <= 0:
            errors.append("Max data age must be positive")
        if self.stale_data_timeout_seconds <= self.max_data_age_seconds:
            errors.append("Stale timeout must be greater than max data age")
        
        if errors:
            for error in errors:
                logger.error(f"LiveSafetyLimits validation error: {error}")
            raise ValueError(f"Invalid LiveSafetyLimits: {'; '.join(errors)}")
        
        return True
    
    def log_configuration(self) -> None:
        """Log the current safety configuration."""
        logger.info("=" * 60)
        logger.info("LIVE SAFETY LIMITS CONFIGURATION")
        logger.info("=" * 60)
        logger.info(f"Daily Loss Limits:     Soft={self.max_daily_loss_soft*100:.1f}% | Hard={self.max_daily_loss_hard*100:.1f}%")
        logger.info(f"Drawdown Limits:       Soft={self.max_total_drawdown_soft*100:.1f}% | Hard={self.max_total_drawdown_hard*100:.1f}%")
        logger.info(f"Position Loss Limit:   {self.max_position_loss*100:.1f}%")
        logger.info("-" * 60)
        logger.info(f"Max Position Size:     {self.max_position_size*100:.1f}% of portfolio")
        logger.info(f"Max Total Exposure:    {self.max_total_exposure*100:.1f}% of portfolio")
        logger.info(f"Max Leverage:          {self.max_leverage}x")
        logger.info(f"Max Daily Turnover:    {self.max_turnover_per_day*100:.1f}%")
        logger.info("-" * 60)
        logger.info(f"Max Order Size:        {self.max_order_size*100:.1f}% of portfolio")
        logger.info(f"Order Value Range:     ${self.min_order_value:.2f} - ${self.max_order_value:,.2f}")
        logger.info("-" * 60)
        logger.info(f"Max Slippage:          {self.max_slippage*100:.2f}%")
        logger.info(f"Max Spread:            {self.max_spread*100:.2f}%")
        logger.info(f"Max Execution Time:    {self.max_execution_time_ms:.0f}ms")
        logger.info("-" * 60)
        logger.info(f"Max Data Age:          {self.max_data_age_seconds}s")
        logger.info(f"Stale Data Timeout:    {self.stale_data_timeout_seconds}s")
        logger.info("-" * 60)
        logger.info(f"Health Check Interval: {self.exchange_health_check_seconds}s")
        logger.info(f"Max API Failures:      {self.max_api_failures}")
        logger.info("-" * 60)
        logger.info(f"Initial Exposure:      {self.initial_exposure_ratio*100:.1f}%")
        logger.info(f"Exposure Increment:    Every {self.exposure_increment_days}d (+{self.max_exposure_increment*100:.1f}%)")
        logger.info(f"Required Positive Days: {self.required_positive_days}")
        logger.info("=" * 60)


@dataclass
class LiveSafetyState:
    """
    Current state of live safety systems.
    
    This tracks all real-time metrics needed for safety checks.
    """
    
    # System state
    is_active: bool = False
    is_halted: bool = False
    halt_reason: Optional[str] = None
    halt_timestamp: Optional[datetime] = None
    
    # P&L tracking (daily)
    daily_pnl: float = 0.0
    daily_trades: int = 0
    daily_turnover: float = 0.0
    daily_loss_count: int = 0
    last_reset_date: Optional[datetime] = None
    
    # Drawdown tracking (cumulative)
    current_drawdown: float = 0.0
    peak_equity: float = 0.0
    current_equity: float = 0.0
    
    # Exposure tracking
    exposure_ratio: float = 0.0
    current_position_weights: Dict[str, float] = field(default_factory=dict)
    
    # Exchange health
    api_failure_count: int = 0
    last_health_check: Optional[datetime] = None
    consecutive_failures: int = 0
    
    # Data quality
    last_data_update: Optional[datetime] = None
    data_quality_issues: int = 0
    
    # Gradual exposure ramp
    exposure_step: int = 0
    exposure_start_date: Optional[datetime] = None
    positive_days_count: int = 0
    last_exposure_increase: Optional[datetime] = None
    
    # Trade history for analysis
    recent_trades: List[Dict] = field(default_factory=list)
    max_recent_trades: int = 100
    
    def reset_daily(self, reset_date: Optional[datetime] = None) -> None:
        """
        Reset daily counters.
        
        Should be called at the start of each trading day.
        """
        reset_date = reset_date or datetime.now()
        
        old_daily_pnl = self.daily_pnl
        old_daily_trades = self.daily_trades
        
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.daily_turnover = 0.0
        self.daily_loss_count = 0
        self.last_reset_date = reset_date
        
        logger.info(
            f"Daily safety limits reset | Previous day: PnL=${old_daily_pnl:,.2f}, "
            f"Trades={old_daily_trades}"
        )
    
    def record_trade(self, pnl: float, turnover: float, symbol: str = "", 
                     side: str = "", amount: float = 0.0, price: float = 0.0) -> None:
        """
        Record a trade for daily tracking.
        
        Args:
            pnl: Realized P&L from the trade
            turnover: Dollar turnover of the trade
            symbol: Trading pair symbol
            side: BUY or SELL
            amount: Trade amount
            price: Trade price
        """
        self.daily_pnl += pnl
        self.daily_trades += 1
        self.daily_turnover += turnover
        
        if pnl < 0:
            self.daily_loss_count += 1
        
        # Add to recent trades history
        trade_record = {
            'timestamp': datetime.now(),
            'symbol': symbol,
            'side': side,
            'amount': amount,
            'price': price,
            'pnl': pnl,
            'turnover': turnover
        }
        self.recent_trades.append(trade_record)
        
        # Trim history if too long
        if len(self.recent_trades) > self.max_recent_trades:
            self.recent_trades = self.recent_trades[-self.max_recent_trades:]
        
        logger.debug(
            f"Trade recorded | {symbol} {side} | PnL=${pnl:,.2f} | "
            f"Daily PnL=${self.daily_pnl:,.2f} | Trades={self.daily_trades}"
        )
    
    def update_equity(self, new_equity: float) -> None:
        """
        Update equity and recalculate drawdown.
        
        Args:
            new_equity: Current total equity
        """
        self.current_equity = new_equity
        
        # Update peak equity
        if self.peak_equity == 0:
            self.peak_equity = new_equity
        elif new_equity > self.peak_equity:
            self.peak_equity = new_equity
        
        # Recalculate drawdown
        if self.peak_equity > 0:
            self.current_drawdown = (self.current_equity - self.peak_equity) / self.peak_equity
        else:
            self.current_drawdown = 0.0
    
    def record_api_failure(self) -> None:
        """Record an API failure."""
        self.api_failure_count += 1
        self.consecutive_failures += 1
        logger.warning(f"API failure recorded (consecutive={self.consecutive_failures})")
    
    def record_api_success(self) -> None:
        """Record a successful API call."""
        self.consecutive_failures = 0
        self.last_health_check = datetime.now()
    
    def record_data_update(self) -> None:
        """Record a successful data update."""
        self.last_data_update = datetime.now()
        self.data_quality_issues = 0
    
    def record_data_quality_issue(self) -> None:
        """Record a data quality issue."""
        self.data_quality_issues += 1
        logger.warning(f"Data quality issue recorded (total={self.data_quality_issues})")
    
    def increment_positive_days(self) -> None:
        """Increment the positive days counter for exposure ramp."""
        self.positive_days_count += 1
        logger.info(f"Positive days count: {self.positive_days_count}")
    
    def reset_positive_days(self) -> None:
        """Reset positive days counter (after a losing day)."""
        self.positive_days_count = 0
        logger.info("Positive days count reset due to losing day")
    
    def can_increase_exposure(self, limits: LiveSafetyLimits) -> bool:
        """
        Check if exposure can be increased based on ramp rules.
        
        Args:
            limits: Safety limits configuration
            
        Returns:
            True if exposure can be increased
        """
        if not self.exposure_start_date:
            return False
        
        # Check if enough time has passed since last increase
        last_increase = self.last_exposure_increase or self.exposure_start_date
        days_since_increase = (datetime.now() - last_increase).days
        
        if days_since_increase < limits.exposure_increment_days:
            return False
        
        # Check if required positive days achieved
        if self.positive_days_count < limits.required_positive_days:
            return False
        
        return True
    
    def get_status_summary(self) -> Dict[str, any]:
        """Get a summary of current safety state."""
        return {
            'is_active': self.is_active,
            'is_halted': self.is_halted,
            'halt_reason': self.halt_reason,
            'daily_pnl': self.daily_pnl,
            'daily_pnl_percent': f"{(self.daily_pnl / self.current_equity * 100):.2f}%" if self.current_equity > 0 else "N/A",
            'daily_trades': self.daily_trades,
            'current_drawdown': f"{self.current_drawdown * 100:.2f}%",
            'current_equity': f"${self.current_equity:,.2f}",
            'peak_equity': f"${self.peak_equity:,.2f}",
            'exposure_ratio': f"{self.exposure_ratio * 100:.2f}%",
            'api_consecutive_failures': self.consecutive_failures,
            'positive_days_count': self.positive_days_count,
            'last_data_update_age': f"{(datetime.now() - self.last_data_update).seconds if self.last_data_update else 'N/A'}s"
        }
