"""
Configuration & Secrets Management Module
==========================================

This module provides secure configuration and secrets management for the trading system.

Features:
- Environment-based configuration (dev/test/paper/shadow/production)
- Secret encryption at rest using Fernet
- Pydantic-based validation
- Graceful degradation with safe defaults
- Audit trail for config changes

Usage:
    from config.loader import get_settings
    
    settings = get_settings()
    print(settings.environment)
    print(settings.trading_mode)
"""

from .settings import (
    Settings,
    Environment,
    LogLevel,
    ExchangeConfig,
    DatabaseConfig,
    RedisConfig,
    TradingLimitsConfig,
    SafetyConfig,
    AlertConfig,
    APIConfig,
    LoggingConfig,
    MLConfig,
    load_settings,
)
from .secrets import (
    SecretManager,
    get_secret_manager,
    get_required_secret,
    get_optional_secret,
)
from .validator import ConfigValidator, ValidationResult
from .loader import ConfigLoader, get_config_loader, get_settings

__all__ = [
    # Settings
    'Settings',
    'Environment',
    'LogLevel',
    'ExchangeConfig',
    'DatabaseConfig',
    'RedisConfig',
    'TradingLimitsConfig',
    'SafetyConfig',
    'AlertConfig',
    'APIConfig',
    'LoggingConfig',
    'MLConfig',
    'load_settings',
    
    # Secrets
    'SecretManager',
    'get_secret_manager',
    'get_required_secret',
    'get_optional_secret',
    
    # Validation
    'ConfigValidator',
    'ValidationResult',
    
    # Loader
    'ConfigLoader',
    'get_config_loader',
    'get_settings',
]
