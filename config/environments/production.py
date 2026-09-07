"""
Production Environment Configuration
=====================================

Configuration for live trading with real capital:
- LIVE trading mode (required)
- Warning log level (reduce noise)
- PostgreSQL database for reliability
- Full alerts enabled
- Strictest safety limits
- No debug mode
"""

from ..settings import Settings, Environment, LogLevel, ExchangeConfig, DatabaseConfig, APIConfig, AlertConfig, SafetyConfig, TradingLimitsConfig, LoggingConfig


def get_config() -> Settings:
    """Get production environment configuration."""
    return Settings(
        environment=Environment.PRODUCTION,
        debug=False,
        log_level=LogLevel.WARNING,
        trading_mode="live",
        exchange=ExchangeConfig(
            name="binance",
            sandbox=False,
            timeout_seconds=10,
            retry_attempts=5,
            retry_backoff=2.0,
        ),
        database=DatabaseConfig(
            type="postgresql",
            host="localhost",
            port=5432,
            database="trading",
            max_connections=20,
        ),
        api=APIConfig(
            host="0.0.0.0",
            port=8000,
            rate_limit=30,
            debug=False,
        ),
        alerts=AlertConfig(
            enabled=True,
            min_severity="warning",
        ),
        safety=SafetyConfig(
            kill_switch_enabled=True,
            auto_derisk=True,
            halt_on_discrepancy=True,
            max_api_failures=3,
            health_check_interval_seconds=5,
        ),
        limits=TradingLimitsConfig(
            max_daily_loss=0.03,
            max_total_drawdown=0.12,
            max_position_size=0.15,
            max_exposure=0.50,
            max_leverage=1.0,
            max_order_size=0.08,
            max_turnover_per_day=1.5,
        ),
        logging=LoggingConfig(
            level=LogLevel.WARNING,
            format="json",
            file_path="logs/trading.log",
            max_file_size_mb=500,
            backup_count=10,
        ),
        data_dir="data",
        logs_dir="logs",
        models_dir="models",
    )
