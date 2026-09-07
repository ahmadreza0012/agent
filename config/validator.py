"""
Configuration Validator - Validate configuration on startup.

This module validates all configuration settings before the application starts,
ensuring that required values are present and configurations are compatible.
"""

import os
import socket
from typing import Dict, Any, List, Tuple
from pathlib import Path
import logging

from .settings import Settings
from .secrets import get_secret_manager

logger = logging.getLogger(__name__)


class ConfigValidator:
    """Validate configuration on startup."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """Run all validations."""
        self._validate_paths()
        self._validate_exchange()
        self._validate_database()
        self._validate_api()
        self._validate_alerts()
        self._validate_mode_environment()
        
        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings
    
    def _validate_paths(self):
        """Validate required paths."""
        paths = [
            self.settings.data_dir,
            self.settings.logs_dir,
            self.settings.models_dir,
        ]
        
        for path in paths:
            p = Path(path)
            try:
                p.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.errors.append(f"Cannot create directory {path}: {e}")
    
    def _validate_exchange(self):
        """Validate exchange configuration."""
        exchange = self.settings.exchange
        
        if exchange.sandbox:
            self.warnings.append("Exchange in sandbox mode")
        
        if self.settings.uses_real_capital():
            # Check for API credentials (they could be in env vars)
            env_api_key = os.environ.get('TRADING_EXCHANGE__API_KEY')
            env_api_secret = os.environ.get('TRADING_EXCHANGE__API_SECRET')
            
            if exchange.api_key is None and not env_api_key:
                self.errors.append("API key required for LIVE mode")
            if exchange.api_secret is None and not env_api_secret:
                self.errors.append("API secret required for LIVE mode")
    
    def _validate_database(self):
        """Validate database configuration."""
        db = self.settings.database
        
        if db.type == "postgresql":
            required = ['host', 'database', 'user']
            for field in required:
                value = getattr(db, field, None)
                env_value = os.environ.get(f'TRADING_DATABASE__{field.upper()}')
                if value is None and not env_value:
                    self.errors.append(f"Database {field} required for PostgreSQL")
        elif db.type == "sqlite":
            if db.path:
                Path(db.path).parent.mkdir(parents=True, exist_ok=True)
    
    def _validate_api(self):
        """Validate API configuration."""
        api = self.settings.api
        
        if self.settings.is_production():
            env_api_key = os.environ.get('TRADING_API__API_KEY')
            # Check if api_key is set (SecretStr) or in env
            has_api_key = api.api_key is not None or env_api_key is not None
            if not has_api_key:
                self.errors.append("API key required for production")
            
            if api.debug:
                self.warnings.append("Debug mode enabled in production")
        
        # Validate host/port availability (non-blocking check)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex((api.host, api.port))
                if result == 0:
                    self.warnings.append(f"Port {api.port} may be in use on {api.host}")
        except Exception:
            pass  # Can't check, skip validation
    
    def _validate_alerts(self):
        """Validate alert configuration."""
        alerts = self.settings.alerts
        
        if alerts.enabled:
            channels = 0
            if alerts.slack_webhook_url:
                channels += 1
            if alerts.telegram_bot_token:
                channels += 1
            if alerts.email_smtp_server:
                channels += 1
            
            # Check environment variables for alert configs
            if os.environ.get('TRADING_ALERTS__SLACK_WEBHOOK_URL'):
                channels += 1
            if os.environ.get('TRADING_ALERTS__TELEGRAM_BOT_TOKEN'):
                channels += 1
            
            if channels == 0:
                self.warnings.append("Alerts enabled but no channels configured")
    
    def _validate_mode_environment(self):
        """Validate mode and environment compatibility."""
        mode = self.settings.trading_mode
        env = self.settings.environment.value if hasattr(self.settings.environment, 'value') else str(self.settings.environment)
        
        if env == "production" and mode != "live":
            self.errors.append("Production environment must use LIVE mode")
        
        if mode == "live" and env != "production":
            self.warnings.append("LIVE mode in non-production environment")


# --- Validation Result ---
class ValidationResult:
    """Result of configuration validation."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.is_valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def add_error(self, error: str):
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        self.warnings.append(warning)
    
    def report(self) -> str:
        lines = ["Configuration Validation Report"]
        lines.append("=" * 40)
        env_value = self.settings.environment.value if hasattr(self.settings.environment, 'value') else str(self.settings.environment)
        lines.append(f"Environment: {env_value}")
        lines.append(f"Mode: {self.settings.trading_mode}")
        lines.append(f"Valid: {self.is_valid}")
        
        if self.warnings:
            lines.append(f"Warnings ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"  ⚠ {w}")
        
        if self.errors:
            lines.append(f"Errors ({len(self.errors)}):")
            for e in self.errors:
                lines.append(f"  ❌ {e}")
        
        return "\n".join(lines)
