"""Pydantic-based Configuration Management.

Modern configuration with validation, type safety, and environment support.
"""

import os
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, SecretStr, field_validator


class TradingMode(str, Enum):
    """Trading modes."""
    BACKTEST = "backtest"
    RESEARCH = "research"
    PAPER = "paper"
    SHADOW = "shadow"
    LIVE = "live"


class RiskConfig(BaseModel):
    """Risk management configuration."""

    max_drawdown: float = Field(0.15, ge=0.0, le=1.0, description="Maximum allowed drawdown")
    max_daily_loss: float = Field(0.03, ge=0.0, le=1.0, description="Maximum daily loss")
    max_position_size: float = Field(0.20, ge=0.0, le=1.0, description="Maximum position size")
    max_exposure: float = Field(1.0, ge=0.0, le=1.0, description="Maximum total exposure")
    risk_multiplier: float = Field(1.0, ge=0.0, le=1.0, description="Risk scaling factor")
    circuit_breaker_enabled: bool = True

    # Live mode thresholds (stricter)
    live_target_return: float = Field(0.0, description="Minimum target return for live mode")
    live_min_sharpe: float = Field(0.0, description="Minimum Sharpe ratio for live mode")
    live_max_single_asset: float = Field(0.40, ge=0.0, le=1.0)

    # Research mode thresholds (more permissive)
    research_target_return: float = Field(-0.05, description="Target return for research")
    research_max_drawdown: float = Field(0.25, ge=0.0, le=1.0)
    research_min_sharpe: float = Field(-1.0, description="Min Sharpe for research")

    @field_validator('max_drawdown', 'max_daily_loss', 'max_position_size', 'max_exposure')
    @classmethod
    def validate_risk_bounds(cls, v: float) -> float:
        """Validate risk parameters are in valid range."""
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"Risk parameter must be in [0, 1]: {v}")
        return v


class ExecutionConfig(BaseModel):
    """Execution configuration."""

    exchange: str = Field("binance", description="Exchange to trade on")
    symbols: List[str] = Field(["BTC/USDT", "ETH/USDT"], description="Trading symbols")
    max_retries: int = Field(3, ge=1, description="Max retries for API calls")
    retry_backoff: float = Field(2.0, ge=1.0, description="Exponential backoff factor")
    order_timeout: int = Field(30, ge=5, description="Order timeout in seconds")
    max_order_size: float = Field(10000.0, gt=0.0, description="Max order size in USD")
    min_order_size: float = Field(10.0, gt=0.0, description="Min order size in USD")

    # Fee structure
    maker_fee: float = Field(0.0004, ge=0.0, le=0.01, description="Maker fee rate")
    taker_fee: float = Field(0.0010, ge=0.0, le=0.01, description="Taker fee rate")
    default_spread_bps: int = Field(10, ge=0, description="Default spread in basis points")

    # Market impact
    market_impact_alpha: float = Field(0.01, ge=0.0, description="Market impact parameter")

    # Liquidity constraints
    max_position_pct_of_adv: float = Field(0.10, ge=0.0, le=1.0)
    max_volume_participation: float = Field(0.20, ge=0.0, le=1.0)
    min_liquidity_usd: float = Field(1_000_000.0, gt=0.0)
    max_spread_bps: int = Field(50, ge=0)


class DataConfig(BaseModel):
    """Data configuration."""

    sources: List[str] = Field(["coingecko", "binance"], description="Data sources")
    timeframe: str = Field("1d", description="Data timeframe")
    cache_enabled: bool = True
    cache_ttl: int = Field(3600, ge=60, description="Cache TTL in seconds")
    max_history_days: int = Field(730, ge=30, description="Max historical days")

    # Data quality
    min_history_bars: int = Field(50, ge=1, description="Minimum history bars required")
    default_lookback_bars: int = Field(30, ge=1)


class MLConfig(BaseModel):
    """ML configuration."""

    train_test_split: float = Field(0.80, ge=0.5, le=0.95)
    oos_ic_threshold: float = Field(0.02, ge=0.0, le=1.0)
    ensemble_rebalance_frequency: str = Field("daily", pattern="^(daily|weekly|monthly)$")
    min_training_samples: int = Field(1000, ge=100)
    retrain_interval_hours: int = Field(24, ge=1)


class BacktestConfig(BaseModel):
    """Backtester configuration."""

    initial_capital: float = Field(100_000.0, gt=0.0)
    transaction_cost_rate: float = Field(0.0010, ge=0.0, le=0.01)
    slippage_rate: float = Field(0.0005, ge=0.0, le=0.01)
    rebalance_frequency: str = Field("daily", pattern="^(daily|weekly|monthly)$")

    # Monte Carlo
    n_simulations: int = Field(1000, ge=100)
    bootstrap_block_size: int = Field(20, ge=1)
    ruin_threshold: float = Field(0.50, ge=0.0, le=1.0)
    confidence_level: float = Field(0.90, ge=0.0, le=1.0)


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field("INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    format: str = Field(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format"
    )
    file_path: Optional[Path] = None
    structured: bool = True
    max_file_size_mb: int = Field(100, ge=10)
    backup_count: int = Field(5, ge=1)


class Config(BaseModel):
    """Main application configuration."""

    mode: TradingMode = Field(TradingMode.RESEARCH, description="Trading mode")
    risk: RiskConfig = Field(default_factory=RiskConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    ml: MLConfig = Field(default_factory=MLConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Secrets (loaded from environment)
    exchange_api_key: Optional[SecretStr] = None
    exchange_api_secret: Optional[SecretStr] = None

    # Environment
    environment: str = Field("development", pattern="^(development|testing|paper|shadow|production)$")
    debug: bool = False

    class Config:
        env_prefix = "TRADING_"
        env_nested_delimiter = "__"

    @field_validator('mode')
    @classmethod
    def validate_mode(cls, v: TradingMode) -> TradingMode:
        """Validate trading mode."""
        if v == TradingMode.LIVE and not os.getenv("ENABLE_LIVE_TRADING"):
            raise ValueError("Live trading requires explicit enable with ENABLE_LIVE_TRADING")
        return v

    def is_live_mode(self) -> bool:
        """Check if in live trading mode."""
        return self.mode == TradingMode.LIVE

    def is_paper_mode(self) -> bool:
        """Check if in paper trading mode."""
        return self.mode == TradingMode.PAPER

    def is_research_mode(self) -> bool:
        """Check if in research mode."""
        return self.mode == TradingMode.RESEARCH

    def get_risk_thresholds(self) -> Dict[str, float]:
        """Get appropriate risk thresholds based on mode."""
        if self.is_live_mode():
            return {
                'target_return': self.risk.live_target_return,
                'max_drawdown': self.risk.max_drawdown,
                'min_sharpe': self.risk.live_min_sharpe,
                'max_position_single_asset': self.risk.live_max_single_asset,
                'max_gross_exposure': self.risk.max_exposure,
            }
        else:  # research
            return {
                'target_return': self.risk.research_target_return,
                'max_drawdown': self.risk.research_max_drawdown,
                'min_sharpe': self.risk.research_min_sharpe,
                'max_position_single_asset': 1.0,
                'max_gross_exposure': self.risk.max_exposure,
            }

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        config_data = {}

        # Load secrets from environment
        if os.getenv("EXCHANGE_API_KEY"):
            config_data["exchange_api_key"] = SecretStr(os.getenv("EXCHANGE_API_KEY"))
        if os.getenv("EXCHANGE_API_SECRET"):
            config_data["exchange_api_secret"] = SecretStr(os.getenv("EXCHANGE_API_SECRET"))

        # Load nested configs
        if os.getenv("MAX_DRAWDOWN"):
            config_data.setdefault("risk", {})["max_drawdown"] = float(os.getenv("MAX_DRAWDOWN"))
        if os.getenv("MAX_DAILY_LOSS"):
            config_data.setdefault("risk", {})["max_daily_loss"] = float(os.getenv("MAX_DAILY_LOSS"))

        return cls(**config_data)


# Global configuration instance (lazy loaded)
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create global configuration instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def reset_config() -> None:
    """Reset global configuration (useful for testing)."""
    global _config
    _config = None
