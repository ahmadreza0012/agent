"""
Development Environment Configuration
======================================

Safe defaults for local development:
- Paper trading mode
- Debug enabled
- SQLite database
- No alerts (to avoid noise)
"""

from ..settings import Settings, Environment, LogLevel, ExchangeConfig, DatabaseConfig, APIConfig, AlertConfig, SafetyConfig


def get_config() -> Settings:
    """Get development environment configuration."""
    return Settings(
        environment=Environment.DEVELOPMENT,
        debug=True,
        log_level=LogLevel.DEBUG,
        trading_mode="paper",
        exchange=ExchangeConfig(
            name="binance",
            sandbox=True,
            timeout_seconds=30,
            retry_attempts=3,
        ),
        database=DatabaseConfig(
            type="sqlite",
            path="data/trading_dev.db",
        ),
        api=APIConfig(
            host="127.0.0.1",
            port=8000,
            rate_limit=60,
            debug=True,
        ),
        alerts=AlertConfig(
            enabled=False,
        ),
        safety=SafetyConfig(
            kill_switch_enabled=True,
            auto_derisk=True,
            max_api_failures=3,
        ),
        data_dir="data",
        logs_dir="logs",
        models_dir="models",
    )
