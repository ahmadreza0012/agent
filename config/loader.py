"""
Config Loader - Load configuration based on environment.

This module provides a unified interface for loading and validating configuration
based on the current environment (development, testing, paper, shadow, production).
"""

import os
from typing import Optional, Dict, Any
from pathlib import Path
import logging

from .settings import Settings, load_settings
from .validator import ConfigValidator, ValidationResult
from .secrets import get_secret_manager

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Load and validate configuration."""
    
    ENV_MAP = {
        "development": "config.environments.development",
        "testing": "config.environments.testing",
        "paper": "config.environments.paper",
        "shadow": "config.environments.shadow",
        "production": "config.environments.production",
    }
    
    def __init__(self, env: Optional[str] = None):
        self.env = env or os.environ.get("TRADING_ENV", "development")
        self.settings: Optional[Settings] = None
        self.validation: Optional[ValidationResult] = None
    
    def load(self) -> Settings:
        """Load configuration for the current environment."""
        logger.info(f"Loading configuration for environment: {self.env}")
        
        # Load settings from environment variables
        self.settings = load_settings()
        
        # Override with environment-specific config if available
        self._apply_environment_config()
        
        # Validate
        self.validation = self._validate()
        
        if not self.validation.is_valid:
            logger.error("Configuration validation failed:")
            for error in self.validation.errors:
                logger.error(f"  ❌ {error}")
            raise ValueError("Configuration validation failed")
        
        for warning in self.validation.warnings:
            logger.warning(f"  ⚠ {warning}")
        
        logger.info(f"Configuration loaded successfully: {self.settings.environment}")
        return self.settings
    
    def _apply_environment_config(self):
        """Apply environment-specific configuration."""
        try:
            # Import environment-specific config
            module_name = self.ENV_MAP.get(self.env)
            if module_name:
                module = __import__(module_name, fromlist=['get_config'])
                if hasattr(module, 'get_config'):
                    env_config = module.get_config()
                    # Replace settings entirely with env_config
                    self.settings = env_config
        except ImportError as e:
            logger.warning(f"Environment config not found for {self.env}: {e}")
        except Exception as e:
            logger.error(f"Failed to apply environment config: {e}")
    
    def _merge_settings(self, env_config: Settings):
        """Merge environment config into current settings."""
        if self.settings is None:
            return
        
        # Update top-level fields
        for key, value in env_config.model_dump().items():
            if hasattr(self.settings, key):
                current_value = getattr(self.settings, key)
                # For nested models, merge them
                if hasattr(current_value, 'model_dump') and hasattr(value, '__class__') and not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                    # Both are Pydantic models, merge field by field
                    if hasattr(value, 'model_dump'):
                        for sub_key, sub_value in value.model_dump().items():
                            if hasattr(current_value, sub_key):
                                setattr(current_value, sub_key, sub_value)
                elif not isinstance(current_value, (list, dict)):
                    setattr(self.settings, key, value)
    
    def _validate(self) -> ValidationResult:
        """Validate configuration."""
        result = ValidationResult(self.settings)
        
        # Run validations
        validator = ConfigValidator(self.settings)
        is_valid, errors, warnings = validator.validate_all()
        
        result.is_valid = is_valid
        result.errors = errors
        result.warnings = warnings
        
        return result
    
    def get_settings(self) -> Settings:
        """Get loaded settings."""
        if self.settings is None:
            self.load()
        return self.settings
    
    def get_validation_report(self) -> str:
        """Get validation report."""
        if self.validation is None:
            return "Configuration not loaded"
        return self.validation.report()


# --- Singleton ---
_config_loader: Optional[ConfigLoader] = None

def get_config_loader(env: Optional[str] = None) -> ConfigLoader:
    """Get singleton config loader."""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader(env)
    return _config_loader

def get_settings() -> Settings:
    """Get loaded settings."""
    return get_config_loader().get_settings()
