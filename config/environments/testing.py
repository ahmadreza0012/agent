"""
Testing Environment Configuration
==================================

Configuration for automated tests:
- Paper trading mode
- Debug enabled for verbose output
- Separate SQLite database (can be deleted after tests)
- Relaxed safety limits for testing
- No alerts
"""

from ..settings import Settings, Environment, LogLevel, ExchangeConfig, DatabaseConfig, APIConfig, AlertConfig, SafetyConfig


def get_config() -> Settings:
    """Get testing environment configuration."""
    return Settings(
        environment=Environment.TESTING,
        debug=True,
        log_level=LogLevel.DEBUG,
        trading_mode="paper",
        exchange=ExchangeConfig(
            name="binance",
            sandbox=True,
            timeout_seconds=10,
            retry_attempts=2,
        ),
        database=DatabaseConfig(
            type="sqlite",
            path="data/trading_test.db",
        ),
        api=APIConfig(
            host="127.0.0.1",
            port=8000,
            rate_limit=100,
            debug=True,
        ),
        alerts=AlertConfig(
            enabled=False,
        ),
        safety=SafetyConfig(
            kill_switch_enabled=False,
            auto_derisk=False,
            max_api_failures=1,
        ),
        data_dir="data_test",
        logs_dir="logs_test",
        models_dir="models_test",
    )
