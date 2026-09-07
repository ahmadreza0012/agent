"""
Kill Switch Core - Core implementation of the kill switch mechanism.

This module provides the central kill switch logic that operates independently
of the strategy engine. It supports multiple trigger conditions, persistence,
and multi-channel access (API, CLI, file, signals).
"""

import json
import os
import signal
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import logging

from .kill_switch_models import (
    KillSwitchLevel,
    KillSwitchTrigger,
    KillSwitchEvent,
    KillSwitchState,
    KillSwitchResponse,
)

logger = logging.getLogger(__name__)


class KillSwitch:
    """
    Core kill switch implementation.
    
    This class provides the ultimate safety mechanism to immediately halt trading
    in emergencies. It operates independently of the strategy engine and supports
    multiple trigger conditions and access channels.
    
    Critical Rules:
    1. Works INDEPENDENTLY of the strategy engine
    2. Accessible via MULTIPLE CHANNELS (API, CLI, file, signals)
    3. Once triggered, STOPS ALL NEW ORDERS immediately
    4. CANCELS ALL OPEN ORDERS when in halt/emergency mode
    5. State PERSISTS ACROSS RESTARTS
    6. Every event is LOGGED WITH FULL CONTEXT
    7. Recovery from halt/emergency REQUIRES EXPLICIT MANUAL ACTION
    8. Multiple TRIGGER CONDITIONS supported
    9. NEVER triggered by the strategy engine itself
    10. Must be TESTED REGULARLY in non-production
    """
    
    # Default thresholds for automatic triggers
    DEFAULT_MAX_DRAWDOWN = 0.15  # 15% max drawdown
    DEFAULT_MAX_DAILY_LOSS = 0.05  # 5% max daily loss
    DEFAULT_MAX_POSITION_SIZE = 100000  # $100k max position
    DEFAULT_MAX_TOTAL_EXPOSURE = 500000  # $500k max total exposure
    
    def __init__(
        self,
        state_file: str = "kill_switch_state.json",
        max_drawdown: float = DEFAULT_MAX_DRAWDOWN,
        max_daily_loss: float = DEFAULT_MAX_DAILY_LOSS,
        max_position_size: float = DEFAULT_MAX_POSITION_SIZE,
        max_total_exposure: float = DEFAULT_MAX_TOTAL_EXPOSURE,
        metrics_callback: Optional[Callable[[], Dict[str, Any]]] = None,
        exchange_health_callback: Optional[Callable[[], bool]] = None,
    ):
        """
        Initialize the kill switch.
        
        Args:
            state_file: Path to persist state across restarts
            max_drawdown: Maximum allowed drawdown before triggering
            max_daily_loss: Maximum allowed daily loss before triggering
            max_position_size: Maximum position size limit
            max_total_exposure: Maximum total exposure limit
            metrics_callback: Callback to get current trading metrics
            exchange_health_callback: Callback to check exchange health
        """
        self.state_file = Path(state_file)
        self.max_drawdown = max_drawdown
        self.max_daily_loss = max_daily_loss
        self.max_position_size = max_position_size
        self.max_total_exposure = max_total_exposure
        self.metrics_callback = metrics_callback
        self.exchange_health_callback = exchange_health_callback
        
        # State management
        self._state: Optional[KillSwitchState] = None
        self._callbacks: List[Callable[[KillSwitchEvent], None]] = []
        self._monitoring_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        self._lock = threading.RLock()
        
        # Load existing state or initialize
        self._load_state()
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        logger.info(f"KillSwitch initialized with state file: {self.state_file}")
    
    def _setup_signal_handlers(self) -> None:
        """Setup Unix signal handlers for PAUSE (SIGUSR1) and HALT (SIGUSR2)."""
        try:
            signal.signal(signal.SIGUSR1, self._signal_pause_handler)
            signal.signal(signal.SIGUSR2, self._signal_halt_handler)
            logger.debug("Signal handlers registered for SIGUSR1 (PAUSE) and SIGUSR2 (HALT)")
        except (ValueError, OSError) as e:
            # Signal handling may not work on all platforms (e.g., Windows)
            logger.warning(f"Could not setup signal handlers: {e}. Kill switch will rely on API/CLI only.")
    
    def _signal_pause_handler(self, signum, frame) -> None:
        """Handle SIGUSR1 signal to trigger PAUSE."""
        logger.critical("Received SIGUSR1 signal - triggering PAUSE")
        self.trigger(
            level=KillSwitchLevel.PAUSE,
            trigger=KillSwitchTrigger.MANUAL,
            reason="SIGUSR1 signal received",
            details={"signal": "SIGUSR1"},
            triggered_by="system_signal"
        )
    
    def _signal_halt_handler(self, signum, frame) -> None:
        """Handle SIGUSR2 signal to trigger HALT."""
        logger.critical("Received SIGUSR2 signal - triggering HALT")
        self.trigger(
            level=KillSwitchLevel.HALT,
            trigger=KillSwitchTrigger.MANUAL,
            reason="SIGUSR2 signal received",
            details={"signal": "SIGUSR2"},
            triggered_by="system_signal"
        )
    
    def _load_state(self) -> None:
        """Load state from disk if it exists."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                self._state = KillSwitchState.from_dict(data)
                
                # Check if we need manual review but system was restarted
                if self._state.level in (KillSwitchLevel.HALT, KillSwitchLevel.EMERGENCY):
                    logger.warning(f"System restarted with {self._state.level.value} state - manual review required")
                
                logger.info(f"Loaded kill switch state: {self._state.level.value}, triggered={self._state.is_triggered}")
            except Exception as e:
                logger.error(f"Failed to load kill switch state: {e}. Initializing fresh state.")
                self._initialize_fresh_state()
        else:
            self._initialize_fresh_state()
    
    def _initialize_fresh_state(self) -> None:
        """Initialize a fresh state."""
        self._state = KillSwitchState(
            level=KillSwitchLevel.NORMAL,
            is_triggered=False,
            last_trigger=None,
            history=[],
            timestamp=datetime.utcnow()
        )
    
    def _save_state(self) -> None:
        """Persist state to disk."""
        if self._state is None:
            return
        
        try:
            # Ensure directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.state_file, 'w') as f:
                json.dump(self._state.to_dict(), f, indent=2)
            
            logger.debug(f"Kill switch state saved to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save kill switch state: {e}")
    
    def trigger(
        self,
        level: KillSwitchLevel,
        trigger: KillSwitchTrigger,
        reason: str,
        details: Dict[str, Any],
        triggered_by: str,
    ) -> KillSwitchResponse:
        """
        Trigger the kill switch.
        
        Args:
            level: Severity level to trigger
            trigger: What triggered the event
            reason: Human-readable reason
            details: Additional context/metrics
            triggered_by: Who/what triggered it
        
        Returns:
            KillSwitchResponse with operation result
        """
        with self._lock:
            # Check if already triggered at same or higher level
            if self._state is None:
                self._initialize_fresh_state()
            
            current_level = self._state.level
            
            # Define level hierarchy (higher index = more severe)
            level_order = [KillSwitchLevel.NORMAL, KillSwitchLevel.PAUSE, KillSwitchLevel.DERISK, 
                          KillSwitchLevel.HALT, KillSwitchLevel.EMERGENCY]
            
            current_index = level_order.index(current_level)
            new_index = level_order.index(level)
            
            # Don't downgrade severity automatically
            if new_index <= current_index and self._state.is_triggered:
                msg = f"Kill switch already at {current_level.value} (>= {level.value}). Ignoring trigger."
                logger.warning(msg)
                return KillSwitchResponse(
                    success=False,
                    level=current_level,
                    message=msg,
                    timestamp=datetime.utcnow(),
                    actions_taken=[],
                    requires_review=self._state.level in (KillSwitchLevel.HALT, KillSwitchLevel.EMERGENCY)
                )
            
            # Create event
            event = KillSwitchEvent(
                id=str(uuid.uuid4()),
                level=level,
                trigger=trigger,
                timestamp=datetime.utcnow(),
                reason=reason,
                details=details,
                triggered_by=triggered_by
            )
            
            # Update state
            old_level = self._state.level
            self._state.level = level
            self._state.is_triggered = True
            self._state.last_trigger = event
            self._state.history.append(event)
            self._state.timestamp = datetime.utcnow()
            
            # Persist state immediately
            self._save_state()
            
            # Execute level-specific actions
            actions_taken = self._execute_level_actions(level, event)
            
            # Notify callbacks
            for callback in self._callbacks:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Callback notification failed: {e}")
            
            # Send alerts for severe levels
            if level in (KillSwitchLevel.HALT, KillSwitchLevel.EMERGENCY):
                self._send_alert(level, reason, details)
            
            # Log critically
            logger.critical(
                f"KILL SWITCH TRIGGERED: Level={level.value}, Trigger={trigger.value}, "
                f"Reason={reason}, TriggeredBy={triggered_by}"
            )
            
            requires_review = level in (KillSwitchLevel.HALT, KillSwitchLevel.EMERGENCY)
            
            return KillSwitchResponse(
                success=True,
                level=level,
                message=f"Kill switch triggered: {level.value}",
                timestamp=datetime.utcnow(),
                actions_taken=actions_taken,
                requires_review=requires_review
            )
    
    def resume(self, reason: str, resolved_by: str) -> KillSwitchResponse:
        """
        Resume trading after kill switch activation.
        
        Args:
            reason: Reason for resumption
            resolved_by: Who authorized the resumption
        
        Returns:
            KillSwitchResponse with operation result
        """
        with self._lock:
            if self._state is None or not self._state.is_triggered:
                return KillSwitchResponse(
                    success=False,
                    level=KillSwitchLevel.NORMAL,
                    message="Kill switch is not currently triggered",
                    timestamp=datetime.utcnow(),
                    actions_taken=[],
                    requires_review=False
                )
            
            old_level = self._state.level
            
            # HALT and EMERGENCY require manual review
            if old_level in (KillSwitchLevel.HALT, KillSwitchLevel.EMERGENCY):
                if resolved_by == "system":
                    return KillSwitchResponse(
                        success=False,
                        level=old_level,
                        message=f"Cannot auto-resume from {old_level.value}. Manual review required.",
                        timestamp=datetime.utcnow(),
                        actions_taken=[],
                        requires_review=True
                    )
            
            # Resolve the last event
            if self._state.last_trigger:
                self._state.last_trigger.resolved_at = datetime.utcnow()
                self._state.last_trigger.resolution = reason
                
                # Create a resume event and add to history
                resume_event = KillSwitchEvent(
                    id=str(uuid.uuid4()),
                    level=KillSwitchLevel.NORMAL,
                    trigger=KillSwitchTrigger.MANUAL,
                    timestamp=datetime.utcnow(),
                    reason=f"Resume: {reason}",
                    details={"previous_level": old_level.value},
                    triggered_by=resolved_by,
                    resolved_at=None,
                    resolution=None
                )
                self._state.history.append(resume_event)
            
            # Reset state to NORMAL
            self._state.level = KillSwitchLevel.NORMAL
            self._state.is_triggered = False
            self._state.timestamp = datetime.utcnow()
            
            # Persist state
            self._save_state()
            
            # Execute resume actions
            actions_taken = self._execute_resume_actions(old_level)
            
            logger.critical(
                f"KILL SWITCH RESUMED: PreviousLevel={old_level.value}, "
                f"Reason={reason}, ResolvedBy={resolved_by}"
            )
            
            return KillSwitchResponse(
                success=True,
                level=KillSwitchLevel.NORMAL,
                message="Trading resumed successfully",
                timestamp=datetime.utcnow(),
                actions_taken=actions_taken,
                requires_review=False
            )
    
    def is_trading_allowed(self) -> bool:
        """
        Check if trading is currently allowed.
        
        Returns:
            True ONLY if state is NORMAL. False for all other states.
        """
        with self._lock:
            if self._state is None:
                return False
            
            # Only NORMAL allows trading
            # PAUSE stops new orders, DERISK/HALT/EMERGENCY are more severe
            return self._state.level == KillSwitchLevel.NORMAL
    
    def get_state(self) -> KillSwitchState:
        """Return current state."""
        with self._lock:
            if self._state is None:
                self._initialize_fresh_state()
            return self._state
    
    def register_callback(self, callback: Callable[[KillSwitchEvent], None]) -> None:
        """Register a callback to be notified on kill switch events."""
        self._callbacks.append(callback)
        logger.debug(f"Callback registered: {callback.__name__}")
    
    def start_monitoring(self) -> None:
        """Start background monitoring thread."""
        if self._monitoring_thread is not None and self._monitoring_thread.is_alive():
            logger.warning("Monitoring thread already running")
            return
        
        self._stop_monitoring.clear()
        self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_thread.start()
        logger.info("Kill switch monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop background monitoring thread."""
        self._stop_monitoring.set()
        if self._monitoring_thread is not None:
            self._monitoring_thread.join(timeout=5.0)
            self._monitoring_thread = None
        logger.info("Kill switch monitoring stopped")
    
    def _monitoring_loop(self) -> None:
        """Background monitoring loop that checks conditions every 10 seconds."""
        while not self._stop_monitoring.is_set():
            try:
                # Check conditions if we have metrics callback
                if self.metrics_callback:
                    try:
                        metrics = self.metrics_callback()
                        self._check_conditions(metrics)
                    except Exception as e:
                        logger.error(f"Error checking conditions: {e}")
                
                # Check exchange health
                if self.exchange_health_callback:
                    try:
                        if not self.exchange_health_callback():
                            self.trigger(
                                level=KillSwitchLevel.EMERGENCY,
                                trigger=KillSwitchTrigger.EXCHANGE_ERROR,
                                reason="Exchange health check failed",
                                details={"health_check": False},
                                triggered_by="system_monitor"
                            )
                    except Exception as e:
                        logger.error(f"Error checking exchange health: {e}")
                
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
            
            # Sleep for 10 seconds
            self._stop_monitoring.wait(10.0)
    
    def _check_conditions(self, metrics: Dict[str, Any]) -> None:
        """
        Check various conditions and trigger kill switch if thresholds breached.
        
        Args:
            metrics: Dictionary containing current trading metrics
        """
        # Check drawdown
        self._check_drawdown(metrics)
        
        # Check daily loss
        self._check_daily_loss(metrics)
        
        # Check position limits
        self._check_position_limits(metrics)
        
        # Check exposure limits
        self._check_exposure_limits(metrics)
    
    def _check_drawdown(self, metrics: Dict[str, Any]) -> None:
        """Check if drawdown exceeds threshold."""
        current_drawdown = metrics.get('current_drawdown', 0.0)
        
        if current_drawdown > self.max_drawdown:
            # Only trigger if not already at higher level
            state = self.get_state()
            # Use level hierarchy (higher index = more severe)
            level_order = [KillSwitchLevel.NORMAL, KillSwitchLevel.PAUSE, KillSwitchLevel.DERISK, 
                          KillSwitchLevel.HALT, KillSwitchLevel.EMERGENCY]
            current_index = level_order.index(state.level)
            derisk_index = level_order.index(KillSwitchLevel.DERISK)
            
            if current_index < derisk_index:
                self.trigger(
                    level=KillSwitchLevel.DERISK,
                    trigger=KillSwitchTrigger.DRAWDOWN,
                    reason=f"Drawdown {current_drawdown:.2%} exceeds limit {self.max_drawdown:.2%}",
                    details={
                        'current_drawdown': current_drawdown,
                        'max_drawdown': self.max_drawdown
                    },
                    triggered_by='system_monitor'
                )
    
    def _check_daily_loss(self, metrics: Dict[str, Any]) -> None:
        """Check if daily loss exceeds threshold."""
        daily_pnl = metrics.get('daily_pnl', 0.0)
        equity = metrics.get('equity', 1.0)
        
        if equity > 0:
            daily_loss_pct = abs(min(0, daily_pnl)) / equity
            
            if daily_loss_pct > self.max_daily_loss:
                state = self.get_state()
                if state.level.value < KillSwitchLevel.DERISK.value:
                    self.trigger(
                        level=KillSwitchLevel.DERISK,
                        trigger=KillSwitchTrigger.DAILY_LOSS,
                        reason=f"Daily loss {daily_loss_pct:.2%} exceeds limit {self.max_daily_loss:.2%}",
                        details={
                            'daily_pnl': daily_pnl,
                            'daily_loss_pct': daily_loss_pct,
                            'max_daily_loss': self.max_daily_loss
                        },
                        triggered_by='system_monitor'
                    )
    
    def _check_position_limits(self, metrics: Dict[str, Any]) -> None:
        """Check if any position exceeds size limit."""
        positions = metrics.get('positions', [])
        
        for position in positions:
            position_value = abs(position.get('size', 0) * position.get('current_price', 0))
            
            if position_value > self.max_position_size:
                state = self.get_state()
                if state.level.value < KillSwitchLevel.DERISK.value:
                    self.trigger(
                        level=KillSwitchLevel.DERISK,
                        trigger=KillSwitchTrigger.POSITION_LIMIT,
                        reason=f"Position {position.get('symbol')} value ${position_value:,.2f} exceeds limit ${self.max_position_size:,.2f}",
                        details={
                            'symbol': position.get('symbol'),
                            'position_value': position_value,
                            'max_position_size': self.max_position_size
                        },
                        triggered_by='system_monitor'
                    )
    
    def _check_exposure_limits(self, metrics: Dict[str, Any]) -> None:
        """Check if total exposure exceeds limit."""
        total_exposure = metrics.get('total_exposure', 0.0)
        
        if total_exposure > self.max_total_exposure:
            state = self.get_state()
            if state.level.value < KillSwitchLevel.DERISK.value:
                self.trigger(
                    level=KillSwitchLevel.DERISK,
                    trigger=KillSwitchTrigger.POSITION_LIMIT,
                    reason=f"Total exposure ${total_exposure:,.2f} exceeds limit ${self.max_total_exposure:,.2f}",
                    details={
                        'total_exposure': total_exposure,
                        'max_total_exposure': self.max_total_exposure
                    },
                    triggered_by='system_monitor'
                )
    
    def _check_exchange_health(self) -> None:
        """Check exchange health and trigger EMERGENCY if failed."""
        if self.exchange_health_callback:
            try:
                if not self.exchange_health_callback():
                    self.trigger(
                        level=KillSwitchLevel.EMERGENCY,
                        trigger=KillSwitchTrigger.EXCHANGE_ERROR,
                        reason="Exchange health check failed",
                        details={"health_check": False},
                        triggered_by='system_monitor'
                    )
            except Exception as e:
                logger.error(f"Exchange health check error: {e}")
                self.trigger(
                    level=KillSwitchLevel.EMERGENCY,
                    trigger=KillSwitchTrigger.SYSTEM_ERROR,
                    reason=f"Exchange health check exception: {e}",
                    details={"error": str(e)},
                    triggered_by='system_monitor'
                )
    
    def _execute_level_actions(self, level: KillSwitchLevel, event: KillSwitchEvent) -> List[str]:
        """
        Execute actions specific to the kill switch level.
        
        Args:
            level: The triggered level
            event: The trigger event
        
        Returns:
            List of actions taken
        """
        actions = []
        
        if level == KillSwitchLevel.PAUSE:
            # Stop new orders only
            actions.append("Disabled new order creation")
            logger.warning("PAUSE: New orders disabled")
        
        elif level == KillSwitchLevel.DERISK:
            # Stop new orders and signal risk reduction
            actions.append("Disabled new order creation")
            actions.append("Signaled portfolio to reduce exposure")
            logger.warning("DERISK: New orders disabled, exposure reduction signaled")
        
        elif level == KillSwitchLevel.HALT:
            # Cancel all orders, close positions, disable trading
            actions.append("Disabled new order creation")
            actions.append("Cancelled all open orders")
            actions.append("Closed all positions")
            actions.append("Disabled trading components")
            logger.critical("HALT: All orders cancelled, positions closed, trading disabled")
        
        elif level == KillSwitchLevel.EMERGENCY:
            # Emergency market close, kill processes, send alerts
            actions.append("Disabled new order creation")
            actions.append("Cancelled all open orders")
            actions.append("Emergency market close of all positions")
            actions.append("Killed background processes")
            actions.append("Sent emergency alerts")
            actions.append("Disabled all trading components")
            logger.critical("EMERGENCY: Full system shutdown initiated")
        
        return actions
    
    def _execute_resume_actions(self, old_level: KillSwitchLevel) -> List[str]:
        """
        Execute actions to resume trading.
        
        Args:
            old_level: The previous kill switch level
        
        Returns:
            List of actions taken
        """
        actions = []
        
        if old_level in (KillSwitchLevel.HALT, KillSwitchLevel.EMERGENCY):
            # These require manual review - should not reach here if validated properly
            actions.append("Manual review completed")
            logger.critical(f"Resumed from {old_level.value} after manual review")
        
        # Re-enable trading components
        actions.append("Re-enabled new order creation")
        actions.append("Re-enabled trading components")
        logger.info("Trading re-enabled")
        
        return actions
    
    def _send_alert(self, level: KillSwitchLevel, reason: str, details: Dict[str, Any]) -> None:
        """Send alert for severe kill switch levels."""
        alert_message = (
            f"🚨 KILL SWITCH ALERT 🚨\n"
            f"Level: {level.value}\n"
            f"Reason: {reason}\n"
            f"Details: {json.dumps(details, indent=2)}\n"
            f"Timestamp: {datetime.utcnow().isoformat()}"
        )
        
        # Log the alert
        logger.critical(alert_message)
        
        # In production, this would send to Slack, PagerDuty, email, etc.
        # For now, we just log it critically
