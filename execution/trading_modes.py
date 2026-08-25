"""
Trading Modes - Enum and configuration for different trading modes.

This module defines the trading modes (BACKTEST, PAPER, SHADOW, LIVE) 
and their associated configurations.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TradingMode(Enum):
    """Trading mode enumeration."""
    BACKTEST = "backtest"      # Historical data only
    PAPER = "paper"            # Virtual capital, simulated execution
    SHADOW = "shadow"          # Live capital (read-only), simulated execution
    LIVE = "live"              # Real capital, real execution
    
    @property
    def is_simulated(self) -> bool:
        """Check if this mode uses simulated execution."""
        return self in (TradingMode.BACKTEST, TradingMode.PAPER, TradingMode.SHADOW)
    
    @property
    def uses_real_capital(self) -> bool:
        """Check if this mode uses real capital."""
        return self == TradingMode.LIVE
    
    @property
    def is_read_only(self) -> bool:
        """Check if this mode is read-only (no actual order execution)."""
        return self != TradingMode.LIVE
    
    def __str__(self) -> str:
        return self.value


@dataclass
class TradingConfig:
    """Configuration for a trading mode."""
    mode: TradingMode
    initial_capital: float
    max_position_size: float
    max_exposure: float
    slippage_model: str  # 'fixed', 'dynamic', 'real'
    fee_model: str       # 'taker', 'maker', 'real'
    data_source: str     # 'historical', 'realtime'
    execution_delay_ms: int
    log_level: str
    requires_confirmation: bool = True
    
    @classmethod
    def default_for_mode(cls, mode: TradingMode) -> 'TradingConfig':
        """Get default configuration for a trading mode."""
        configs = {
            TradingMode.BACKTEST: cls(
                mode=TradingMode.BACKTEST,
                initial_capital=100000.0,
                max_position_size=0.20,
                max_exposure=0.60,
                slippage_model="fixed",
                fee_model="taker",
                data_source="historical",
                execution_delay_ms=0,
                log_level="INFO",
                requires_confirmation=False
            ),
            TradingMode.PAPER: cls(
                mode=TradingMode.PAPER,
                initial_capital=100000.0,
                max_position_size=0.20,
                max_exposure=0.60,
                slippage_model="dynamic",
                fee_model="taker",
                data_source="realtime",
                execution_delay_ms=50,
                log_level="INFO",
                requires_confirmation=False
            ),
            TradingMode.SHADOW: cls(
                mode=TradingMode.SHADOW,
                initial_capital=0.0,
                max_position_size=0.20,
                max_exposure=0.60,
                slippage_model="dynamic",
                fee_model="taker",
                data_source="realtime",
                execution_delay_ms=50,
                log_level="INFO",
                requires_confirmation=False
            ),
            TradingMode.LIVE: cls(
                mode=TradingMode.LIVE,
                initial_capital=0.0,
                max_position_size=0.15,
                max_exposure=0.50,
                slippage_model="real",
                fee_model="real",
                data_source="realtime",
                execution_delay_ms=0,
                log_level="WARNING",
                requires_confirmation=True
            )
        }
        return configs[mode]
    
    def validate(self) -> bool:
        """Validate the configuration."""
        if self.initial_capital < 0:
            raise ValueError("Initial capital cannot be negative")
        if not 0 <= self.max_position_size <= 1:
            raise ValueError("Max position size must be between 0 and 1")
        if not 0 <= self.max_exposure <= 1:
            raise ValueError("Max exposure must be between 0 and 1")
        if self.execution_delay_ms < 0:
            raise ValueError("Execution delay cannot be negative")
        
        valid_slippage_models = {'fixed', 'dynamic', 'real'}
        if self.slippage_model not in valid_slippage_models:
            raise ValueError(f"Invalid slippage model: {self.slippage_model}")
        
        valid_fee_models = {'taker', 'maker', 'real'}
        if self.fee_model not in valid_fee_models:
            raise ValueError(f"Invalid fee model: {self.fee_model}")
        
        valid_data_sources = {'historical', 'realtime'}
        if self.data_source not in valid_data_sources:
            raise ValueError(f"Invalid data source: {self.data_source}")
        
        return True
    
    def log_configuration(self) -> None:
        """Log the current configuration."""
        logger.info(f"TradingConfig for {self.mode.value}:")
        logger.info(f"  Initial Capital: ${self.initial_capital:,.2f}")
        logger.info(f"  Max Position Size: {self.max_position_size * 100:.1f}%")
        logger.info(f"  Max Exposure: {self.max_exposure * 100:.1f}%")
        logger.info(f"  Slippage Model: {self.slippage_model}")
        logger.info(f"  Fee Model: {self.fee_model}")
        logger.info(f"  Data Source: {self.data_source}")
        logger.info(f"  Execution Delay: {self.execution_delay_ms}ms")
        logger.info(f"  Requires Confirmation: {self.requires_confirmation}")
        logger.info(f"  Is Simulated: {self.mode.is_simulated}")
        logger.info(f"  Uses Real Capital: {self.mode.uses_real_capital}")
        logger.info(f"  Is Read-Only: {self.mode.is_read_only}")
