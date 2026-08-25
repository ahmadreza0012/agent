"""
Mode Factory - Factory for creating trading mode adapters.

This module provides a factory pattern for creating the appropriate
adapter based on the trading mode.
"""

from typing import Optional, Any, Dict
import logging

from .trading_modes import TradingMode, TradingConfig
from .exchange_adapter import ExchangeAdapter
from .paper_adapter import PaperTradingAdapter
from .shadow_adapter import ShadowTradingAdapter

logger = logging.getLogger(__name__)


class ModeFactory:
    """Factory for creating trading mode adapters."""
    
    @staticmethod
    def create_adapter(
        mode: TradingMode,
        config: TradingConfig,
        exchange_config: Optional[Dict] = None,
        market_data_provider: Optional[Any] = None,
        live_adapter: Optional[ExchangeAdapter] = None
    ) -> ExchangeAdapter:
        """
        Create an adapter for the specified trading mode.
        
        Args:
            mode: The trading mode
            config: Trading configuration
            exchange_config: Exchange configuration (required for LIVE mode)
            market_data_provider: Provider for real-time market data
            live_adapter: Live adapter (required for SHADOW mode)
        
        Returns:
            An ExchangeAdapter instance for the specified mode
        
        Raises:
            ValueError: If required parameters are missing for the mode
        """
        if mode == TradingMode.PAPER:
            logger.info("Creating PaperTradingAdapter")
            return PaperTradingAdapter(config, market_data_provider)
        
        elif mode == TradingMode.SHADOW:
            logger.info("Creating ShadowTradingAdapter")
            if not live_adapter:
                raise ValueError("SHADOW mode requires a live adapter")
            return ShadowTradingAdapter(config, live_adapter, market_data_provider)
        
        elif mode == TradingMode.LIVE:
            logger.warning("Creating LIVE trading adapter - REAL CAPITAL WILL BE USED")
            if not exchange_config:
                raise ValueError("LIVE mode requires exchange configuration")
            # Import here to avoid circular dependencies
            from .exchange_adapter import CCXTExchangeAdapter
            return CCXTExchangeAdapter(exchange_config)
        
        elif mode == TradingMode.BACKTEST:
            logger.info("Creating Backtest adapter (using PaperTradingAdapter)")
            # For backtest mode, we use paper adapter but with historical data
            return PaperTradingAdapter(config, market_data_provider)
        
        else:
            raise ValueError(f"Unknown trading mode: {mode}")
    
    @staticmethod
    def create_default_configs() -> Dict[TradingMode, TradingConfig]:
        """Create default configurations for all modes."""
        return {
            mode: TradingConfig.default_for_mode(mode)
            for mode in TradingMode
        }
    
    @staticmethod
    def create_all_adapters(
        configs: Dict[TradingMode, TradingConfig],
        exchange_config: Optional[Dict] = None,
        market_data_provider: Optional[Any] = None
    ) -> Dict[TradingMode, ExchangeAdapter]:
        """
        Create adapters for all modes.
        
        Args:
            configs: Dictionary of configurations per mode
            exchange_config: Exchange configuration for LIVE mode
            market_data_provider: Provider for real-time market data
        
        Returns:
            Dictionary mapping modes to their adapters
        """
        adapters = {}
        
        # Create paper adapter first (needed for shadow)
        if TradingMode.PAPER in configs:
            adapters[TradingMode.PAPER] = ModeFactory.create_adapter(
                TradingMode.PAPER,
                configs[TradingMode.PAPER],
                market_data_provider=market_data_provider
            )
        
        # Create backtest adapter
        if TradingMode.BACKTEST in configs:
            adapters[TradingMode.BACKTEST] = ModeFactory.create_adapter(
                TradingMode.BACKTEST,
                configs[TradingMode.BACKTEST],
                market_data_provider=market_data_provider
            )
        
        # Create live adapter (needed for shadow)
        if TradingMode.LIVE in configs and exchange_config:
            adapters[TradingMode.LIVE] = ModeFactory.create_adapter(
                TradingMode.LIVE,
                configs[TradingMode.LIVE],
                exchange_config=exchange_config
            )
        
        # Create shadow adapter (requires live adapter)
        if TradingMode.SHADOW in configs and TradingMode.LIVE in adapters:
            adapters[TradingMode.SHADOW] = ModeFactory.create_adapter(
                TradingMode.SHADOW,
                configs[TradingMode.SHADOW],
                live_adapter=adapters[TradingMode.LIVE],
                market_data_provider=market_data_provider
            )
        
        return adapters
    
    @staticmethod
    def validate_configuration(config: TradingConfig) -> bool:
        """
        Validate a trading configuration.
        
        Args:
            config: The configuration to validate
        
        Returns:
            True if valid
        
        Raises:
            ValueError: If configuration is invalid
        """
        return config.validate()
    
    @staticmethod
    def get_mode_info(mode: TradingMode) -> Dict[str, Any]:
        """
        Get information about a trading mode.
        
        Args:
            mode: The trading mode
        
        Returns:
            Dictionary with mode information
        """
        info = {
            'mode': mode.value,
            'is_simulated': mode.is_simulated,
            'uses_real_capital': mode.uses_real_capital,
            'is_read_only': mode.is_read_only,
        }
        
        config = TradingConfig.default_for_mode(mode)
        info['default_initial_capital'] = config.initial_capital
        info['default_slippage_model'] = config.slippage_model
        info['default_fee_model'] = config.fee_model
        info['requires_confirmation'] = config.requires_confirmation
        
        return info
