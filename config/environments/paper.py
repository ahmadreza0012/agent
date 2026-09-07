"""
Paper Trading Environment Configuration
========================================

Configuration for paper trading (simulated trading with real market data):
- Paper trading mode
- Info log level
- SQLite database with persistent storage
- Alerts enabled for monitoring
- Full safety systems enabled
"""

from ..settings import Settings, Environment, LogLevel, ExchangeConfig, DatabaseConfig, APIConfig, AlertConfig, SafetyConfig, TradingLimitsConfig


def get_config() -> Settings:
    """Get paper trading environment configuration."""
    return Settings(
        environment=Environment.PAPER,
        debug=False,
        log_level=LogLevel.INFO,
        trading_mode="paper",
        exchange=ExchangeConfig(
            name="binance",
            sandbox=True,
            timeout_seconds=30,
            retry_attempts=3,
        ),
        database=DatabaseConfig(
            type="sqlite",
            path="data/trading_paper.db",
        ),
        api=APIConfig(
            host="0.0.0.0",
            port=8000,
            rate_limit=60,
            debug=False,
        ),
        alerts=AlertConfig(
            enabled=True,
            min_severity="warning",
        ),
        safety=SafetyConfig(
            kill_switch_enabled=True,
            auto_derisk=True,
            max_api_failures=3,
        ),
        limits=TradingLimitsConfig(
            max_daily_loss=0.02,
            max_total_drawdown=0.10,
        ),
        data_dir="data",
        logs_dir="logs",
        models_dir="models",
    )
