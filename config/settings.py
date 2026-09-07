"""
Settings - Pydantic-based configuration management.

This module defines all configuration options for the trading system using Pydantic.
All sensitive data is handled via SecretStr to prevent accidental logging.
"""

import os
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, validator, SecretStr, root_validator
from pydantic_settings import BaseSettings
from pathlib import Path


class Environment(str, Enum):
    """Supported environments."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PAPER = "paper"
    SHADOW = "shadow"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Supported log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ExchangeConfig(BaseModel):
    """Exchange configuration."""
    name: str = "binance"
    api_key: Optional[SecretStr] = None
    api_secret: Optional[SecretStr] = None
    api_passphrase: Optional[SecretStr] = None
    sandbox: bool = True
    timeout_seconds: int = 30
    retry_attempts: int = 3
    retry_backoff: float = 1.0


class DatabaseConfig(BaseModel):
    """Database configuration."""
    type: str = "sqlite"  # sqlite or postgresql
    path: str = "data/trading.db"
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[SecretStr] = None
    max_connections: int = 10
    pool_timeout: int = 30


class RedisConfig(BaseModel):
    """Redis configuration."""
    host: Optional[str] = None
    port: int = 6379
    password: Optional[SecretStr] = None
    db: int = 0
    ssl: bool = False
    timeout_seconds: int = 5


class TradingLimitsConfig(BaseModel):
    """Trading limits configuration."""
    max_daily_loss: float = 0.05
    max_total_drawdown: float = 0.15
    max_position_size: float = 0.20
    max_exposure: float = 0.60
    max_leverage: float = 1.0
    max_order_size: float = 0.10
    max_turnover_per_day: float = 2.0


class SafetyConfig(BaseModel):
    """Safety configuration."""
    kill_switch_enabled: bool = True
    auto_derisk: bool = True
    halt_on_discrepancy: bool = True
    max_api_failures: int = 3
    stale_data_timeout_seconds: int = 60
    health_check_interval_seconds: int = 10


class AlertConfig(BaseModel):
    """Alert configuration."""
    enabled: bool = True
    min_severity: str = "warning"
    slack_webhook_url: Optional[SecretStr] = None
    telegram_bot_token: Optional[SecretStr] = None
    telegram_chat_id: Optional[str] = None
    email_smtp_server: Optional[str] = None
    email_smtp_port: int = 587
    email_username: Optional[str] = None
    email_password: Optional[SecretStr] = None
    email_from: Optional[str] = None
    email_to: Optional[str] = None


class APIConfig(BaseModel):
    """API configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    api_key: Optional[SecretStr] = None
    rate_limit: int = 60
    cors_origins: List[str] = ["http://localhost:3000"]
    allowed_hosts: List[str] = ["*"]
    debug: bool = False


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: LogLevel = LogLevel.INFO
    format: str = "json"
    file_path: Optional[str] = None
    max_file_size_mb: int = 100
    backup_count: int = 5
    include_timestamp: bool = True
    include_component: bool = True


class MLConfig(BaseModel):
    """ML configuration."""
    enabled: bool = True
    model_path: str = "models"
    feature_path: str = "features"
    retrain_interval_hours: int = 24
    min_training_samples: int = 1000
    purge_period_days: int = 30
    embargo_period_days: int = 5


class Settings(BaseSettings):
    """Main application settings."""
    
    # --- Environment ---
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    log_level: LogLevel = LogLevel.INFO
    
    # --- Mode ---
    trading_mode: str = "paper"  # backtest, paper, shadow, live
    
    # --- Components ---
    exchange: ExchangeConfig = ExchangeConfig()
    database: DatabaseConfig = DatabaseConfig()
    redis: Optional[RedisConfig] = None
    
    # --- Limits ---
    limits: TradingLimitsConfig = TradingLimitsConfig()
    
    # --- Safety ---
    safety: SafetyConfig = SafetyConfig()
    
    # --- Alerts ---
    alerts: AlertConfig = AlertConfig()
    
    # --- API ---
    api: APIConfig = APIConfig()
    
    # --- Logging ---
    logging: LoggingConfig = LoggingConfig()
    
    # --- ML ---
    ml: MLConfig = MLConfig()
    
    # --- Paths ---
    data_dir: str = "data"
    logs_dir: str = "logs"
    models_dir: str = "models"
    
    class Config:
        env_prefix = "TRADING_"
        env_nested_delimiter = "__"
        case_sensitive = False
        extra = "ignore"
    
    @root_validator(pre=True)
    def validate_mode(cls, values):
        """Validate mode based on environment."""
        mode = values.get('trading_mode', 'paper')
        env = values.get('environment', 'development')
        
        if env == Environment.PRODUCTION and mode != 'live':
            raise ValueError("Production environment must use LIVE mode")
        
        return values
    
    @validator('data_dir')
    def validate_data_dir(cls, v):
        """Validate data directory exists or can be created."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)
    
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION
    
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT
    
    def is_testing(self) -> bool:
        return self.environment == Environment.TESTING
    
    def is_paper_mode(self) -> bool:
        return self.trading_mode == "paper"
    
    def is_live_mode(self) -> bool:
        return self.trading_mode == "live"
    
    def is_shadow_mode(self) -> bool:
        return self.trading_mode == "shadow"
    
    def uses_real_capital(self) -> bool:
        return self.trading_mode == "live"
    
    def uses_real_execution(self) -> bool:
        return self.trading_mode == "live"
    
    def is_read_only(self) -> bool:
        return self.trading_mode != "live"


# --- Load Settings ---
def load_settings(env_file: Optional[str] = None) -> Settings:
    """Load settings from environment and optional file."""
    if env_file and os.path.exists(env_file):
        import dotenv
        dotenv.load_dotenv(env_file)
    
    return Settings()
