"""
Mode Manager - Manage trading mode transitions and adapter registration.

This module provides centralized management for switching between trading modes
(BACKTEST, PAPER, SHADOW, LIVE) with safety checks and proper validation.
"""

from typing import Dict, Optional, Any
from datetime import datetime
import logging

from .trading_modes import TradingMode, TradingConfig
from .exchange_adapter import ExchangeAdapter

logger = logging.getLogger(__name__)


class ModeTransitionError(Exception):
    """Exception raised when a mode transition fails."""
    pass


class TradingModeManager:
    """
    Manage trading mode transitions and adapter lifecycle.
    
    This class ensures safe switching between trading modes with proper
    validation, confirmation requirements, and adapter management.
    """
    
    def __init__(self, config: Optional[Dict[TradingMode, TradingConfig]] = None):
        """
        Initialize the mode manager.
        
        Args:
            config: Optional dictionary of configurations per mode
        """
        self.config = config or {}
        self.current_mode = TradingMode.PAPER  # Default to safe paper mode
        self._adapters: Dict[TradingMode, ExchangeAdapter] = {}
        self._is_initialized = False
        self._mode_history: list = []
        
        logger.info("TradingModeManager created (not yet initialized)")
    
    def initialize(
        self,
        initial_mode: TradingMode = TradingMode.PAPER,
        adapters: Optional[Dict[TradingMode, ExchangeAdapter]] = None
    ) -> None:
        """
        Initialize the mode manager with adapters.
        
        Args:
            initial_mode: The starting trading mode
            adapters: Dictionary mapping modes to their adapters
        """
        if self._is_initialized:
            logger.warning("TradingModeManager already initialized")
            return
        
        self._adapters = adapters or {}
        self.current_mode = initial_mode
        self._is_initialized = True
        
        # Log initialization with mode indicator
        mode_indicator = self._get_mode_indicator(initial_mode)
        logger.info(f"{mode_indicator} TradingModeManager initialized with mode: {initial_mode.value}")
        self._log_mode_properties(initial_mode)
        
        self._mode_history.append({
            'timestamp': datetime.now(),
            'action': 'initialize',
            'mode': initial_mode.value
        })
    
    def register_adapter(self, mode: TradingMode, adapter: ExchangeAdapter) -> None:
        """
        Register an adapter for a specific mode.
        
        Args:
            mode: The trading mode
            adapter: The adapter instance
        """
        self._adapters[mode] = adapter
        logger.info(f"Registered adapter for {mode.value} mode: {adapter.__class__.__name__}")
    
    def switch_mode(
        self,
        new_mode: TradingMode,
        confirm: bool = False
    ) -> Dict[str, Any]:
        """
        Switch to a new trading mode.
        
        Args:
            new_mode: The target trading mode
            confirm: Explicit confirmation (required for LIVE mode)
        
        Returns:
            Dictionary with transition details
        
        Raises:
            ModeTransitionError: If transition is not allowed
        """
        if not self._is_initialized:
            raise ModeTransitionError("ModeManager not initialized. Call initialize() first.")
        
        old_mode = self.current_mode
        
        # Safety check: LIVE mode requires explicit confirmation
        if new_mode == TradingMode.LIVE and not confirm:
            raise ModeTransitionError(
                "LIVE mode requires explicit confirmation (confirm=True). "
                "This is a safety measure to prevent accidental live trading."
            )
        
        # Check if adapter exists for target mode
        if new_mode not in self._adapters:
            raise ModeTransitionError(f"No adapter registered for mode: {new_mode.value}")
        
        # Log the transition
        logger.info(f"Switching mode: {old_mode.value} -> {new_mode.value}")
        
        # Perform the switch
        self.current_mode = new_mode
        
        # Log mode change with indicator
        mode_indicator = self._get_mode_indicator(new_mode)
        logger.warning(f"{mode_indicator} MODE CHANGED: {old_mode.value.upper()} -> {new_mode.value.upper()}")
        self._log_mode_properties(new_mode)
        
        # Record in history
        self._mode_history.append({
            'timestamp': datetime.now(),
            'action': 'switch',
            'old_mode': old_mode.value,
            'new_mode': new_mode.value
        })
        
        return {
            'success': True,
            'old_mode': old_mode.value,
            'new_mode': new_mode.value,
            'timestamp': datetime.now(),
            'requires_restart': self._requires_restart(old_mode, new_mode)
        }
    
    def _requires_restart(self, old_mode: TradingMode, new_mode: TradingMode) -> bool:
        """Check if mode switch requires a system restart."""
        # Restart required when transitioning to/from LIVE mode
        return (
            (old_mode in (TradingMode.PAPER, TradingMode.SHADOW) and new_mode == TradingMode.LIVE) or
            (old_mode == TradingMode.LIVE and new_mode in (TradingMode.PAPER, TradingMode.SHADOW))
        )
    
    def get_current_adapter(self) -> Optional[ExchangeAdapter]:
        """Get the adapter for the current mode."""
        return self._adapters.get(self.current_mode)
    
    def get_adapter_for_mode(self, mode: TradingMode) -> Optional[ExchangeAdapter]:
        """Get the adapter for a specific mode."""
        return self._adapters.get(mode)
    
    def is_simulated(self) -> bool:
        """Check if current mode uses simulated execution."""
        return self.current_mode.is_simulated
    
    def uses_real_capital(self) -> bool:
        """Check if current mode uses real capital."""
        return self.current_mode.uses_real_capital
    
    def is_read_only(self) -> bool:
        """Check if current mode is read-only."""
        return self.current_mode.is_read_only
    
    def get_current_mode(self) -> TradingMode:
        """Get the current trading mode."""
        return self.current_mode
    
    def get_mode_history(self) -> list:
        """Get history of mode changes."""
        return self._mode_history.copy()
    
    def _get_mode_indicator(self, mode: TradingMode) -> str:
        """Get a visual indicator for the mode."""
        indicators = {
            TradingMode.BACKTEST: "[BACKTEST]",
            TradingMode.PAPER: "[PAPER MODE]",
            TradingMode.SHADOW: "[SHADOW MODE]",
            TradingMode.LIVE: "[!!! LIVE MODE !!!]"
        }
        return indicators.get(mode, f"[{mode.value}]")
    
    def _log_mode_properties(self, mode: TradingMode) -> None:
        """Log properties of the current mode."""
        config = self.config.get(mode)
        if config:
            logger.info(f"Mode: {mode.value}")
            logger.info(f"  Is Simulated: {mode.is_simulated}")
            logger.info(f"  Uses Real Capital: {mode.uses_real_capital}")
            logger.info(f"  Is Read-Only: {mode.is_read_only}")
            logger.info(f"  Requires Confirmation: {config.requires_confirmation}")
        else:
            logger.info(f"Mode: {mode.value} (no config available)")
    
    def validate_mode_safety(self) -> Dict[str, Any]:
        """Validate current mode safety settings."""
        return {
            'current_mode': self.current_mode.value,
            'is_safe': self.is_simulated(),
            'uses_real_capital': self.uses_real_capital(),
            'is_read_only': self.is_read_only(),
            'warning': "LIVE MODE ACTIVE - REAL CAPITAL AT RISK" if self.uses_real_capital() else None
        }
    
    def force_paper_mode(self) -> None:
        """Force switch to paper mode (safety override)."""
        if TradingMode.PAPER in self._adapters:
            old_mode = self.current_mode
            self.current_mode = TradingMode.PAPER
            logger.critical(
                f"[SAFETY OVERRIDE] Force-switched from {old_mode.value} to PAPER mode"
            )
            self._mode_history.append({
                'timestamp': datetime.now(),
                'action': 'force_paper',
                'old_mode': old_mode.value,
                'new_mode': TradingMode.PAPER.value
            })
        else:
            raise ModeTransitionError("Cannot force paper mode: no paper adapter registered")
