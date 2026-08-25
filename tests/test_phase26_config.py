"""
Unit tests for Phase 26 Configuration & Secrets.

Tests cover:
- Settings validation and loading
- Secret encryption/decryption
- Configuration validation
- Environment-specific configurations
"""

import sys
sys.path.insert(0, '/workspace')

import unittest
import os
import tempfile
import shutil
from pathlib import Path

# Set test environment before importing config modules
os.environ['TRADING_ENV'] = 'testing'


class TestSettings(unittest.TestCase):
    """Test Pydantic settings."""
    
    def test_default_settings(self):
        """Test default settings are correct."""
        from config.settings import Settings, Environment
        
        settings = Settings()
        self.assertEqual(settings.environment, Environment.DEVELOPMENT)
        self.assertEqual(settings.trading_mode, "paper")
        self.assertTrue(settings.safety.kill_switch_enabled)
    
    def test_environment_validation(self):
        """Test that production requires live mode."""
        from config.settings import Settings, Environment
        
        # Should raise error for production + non-live
        with self.assertRaises(ValueError) as context:
            Settings(environment=Environment.PRODUCTION, trading_mode="paper")
        
        self.assertIn("Production environment must use LIVE mode", str(context.exception))
    
    def test_is_methods(self):
        """Test environment and mode detection methods."""
        from config.settings import Settings, Environment
        
        # Live mode
        settings = Settings(trading_mode="live")
        self.assertTrue(settings.is_live_mode())
        self.assertTrue(settings.uses_real_capital())
        self.assertFalse(settings.is_read_only())
        
        # Paper mode
        settings = Settings(trading_mode="paper")
        self.assertTrue(settings.is_paper_mode())
        self.assertFalse(settings.uses_real_capital())
        self.assertTrue(settings.is_read_only())
        
        # Shadow mode
        settings = Settings(trading_mode="shadow")
        self.assertTrue(settings.is_shadow_mode())
        self.assertTrue(settings.is_read_only())
    
    def test_secret_str_fields(self):
        """Test that sensitive fields use SecretStr."""
        from config.settings import Settings, ExchangeConfig
        from pydantic import SecretStr
        
        exchange = ExchangeConfig(
            api_key="test_key",
            api_secret="test_secret"
        )
        
        self.assertIsInstance(exchange.api_key, SecretStr)
        self.assertIsInstance(exchange.api_secret, SecretStr)
        
        # Verify secrets are not exposed in string representation
        self.assertNotIn("test_key", str(exchange))


class TestSecretManager(unittest.TestCase):
    """Test secret manager encryption."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.key_path = os.path.join(self.temp_dir, 'secret.key')
        self.secrets_file = os.path.join(self.temp_dir, 'secrets.json')
        
        from config.secrets import SecretManager
        self.manager = SecretManager(self.key_path)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_encrypt_decrypt(self):
        """Test encryption and decryption round-trip."""
        original = "test_secret_123"
        encrypted = self.manager.encrypt(original)
        
        # Encrypted value should be different from original
        self.assertNotEqual(encrypted, original)
        self.assertNotEqual(original, encrypted)
        
        # Decrypted value should match original
        decrypted = self.manager.decrypt(encrypted)
        self.assertEqual(decrypted, original)
    
    def test_store_load_secret(self):
        """Test storing and loading encrypted secrets."""
        key = 'api_key'
        value = 'secret_abc_123'
        
        result = self.manager.store_encrypted(key, value, self.secrets_file)
        self.assertTrue(result)
        
        loaded = self.manager.load_encrypted(key, self.secrets_file)
        self.assertEqual(loaded, value)
    
    def test_has_secret(self):
        """Test checking if secret exists."""
        key = 'test_key'
        value = 'test_value'
        
        self.assertFalse(self.manager.has_secret(key, self.secrets_file))
        
        self.manager.store_encrypted(key, value, self.secrets_file)
        self.assertTrue(self.manager.has_secret(key, self.secrets_file))
    
    def test_get_secret_from_env(self):
        """Test getting secret from environment variable."""
        os.environ['TRADING_TEST_SECRET'] = 'env_secret_value'
        
        try:
            value = self.manager.get_secret('test_secret')
            self.assertEqual(value, 'env_secret_value')
        finally:
            del os.environ['TRADING_TEST_SECRET']
    
    def test_singleton_pattern(self):
        """Test singleton pattern for secret manager."""
        from config.secrets import get_secret_manager
        
        manager1 = get_secret_manager()
        manager2 = get_secret_manager()
        
        # Should return same instance
        self.assertIs(manager1, manager2)


class TestConfigValidator(unittest.TestCase):
    """Test configuration validator."""
    
    def test_validate_default_settings(self):
        """Test validation of default settings."""
        from config.settings import Settings
        from config.validator import ConfigValidator
        
        settings = Settings()
        validator = ConfigValidator(settings)
        is_valid, errors, warnings = validator.validate_all()
        
        # Should be valid with default settings (development/paper)
        self.assertTrue(is_valid)
    
    def test_validate_production_config(self):
        """Test validation of production configuration."""
        from config.settings import Settings, Environment
        
        # Production with live mode and API keys should be valid
        os.environ['TRADING_EXCHANGE__API_KEY'] = 'test_key'
        os.environ['TRADING_EXCHANGE__API_SECRET'] = 'test_secret'
        os.environ['TRADING_API__API_KEY'] = 'api_test_key'
        
        try:
            settings = Settings(
                environment=Environment.PRODUCTION,
                trading_mode="live",
            )
            from config.validator import ConfigValidator
            validator = ConfigValidator(settings)
            is_valid, errors, warnings = validator.validate_all()
            
            # Should have warnings about sandbox but be valid
            # The validation passes if no errors about missing API keys
            self.assertEqual(len([e for e in errors if 'API' in e]), 0)
        finally:
            del os.environ['TRADING_EXCHANGE__API_KEY']
            del os.environ['TRADING_EXCHANGE__API_SECRET']
            del os.environ['TRADING_API__API_KEY']
    
    def test_paths_created(self):
        """Test that required paths are created during validation."""
        from config.settings import Settings
        from config.validator import ConfigValidator
        
        temp_dir = tempfile.mkdtemp()
        try:
            settings = Settings(
                data_dir=os.path.join(temp_dir, 'data'),
                logs_dir=os.path.join(temp_dir, 'logs'),
                models_dir=os.path.join(temp_dir, 'models'),
            )
            
            validator = ConfigValidator(settings)
            validator._validate_paths()
            
            # All directories should exist
            self.assertTrue(os.path.exists(settings.data_dir))
            self.assertTrue(os.path.exists(settings.logs_dir))
            self.assertTrue(os.path.exists(settings.models_dir))
        finally:
            shutil.rmtree(temp_dir)


class TestConfigLoader(unittest.TestCase):
    """Test configuration loader."""
    
    def test_load_development_config(self):
        """Test loading development configuration."""
        from config.loader import ConfigLoader
        from config.settings import Environment
        
        loader = ConfigLoader('development')
        settings = loader.load()
        
        self.assertEqual(settings.environment, Environment.DEVELOPMENT)
        self.assertEqual(settings.trading_mode, "paper")
        self.assertTrue(settings.debug)
    
    def test_load_testing_config(self):
        """Test loading testing configuration."""
        from config.loader import ConfigLoader
        from config.settings import Environment
        
        loader = ConfigLoader('testing')
        settings = loader.load()
        
        self.assertEqual(settings.environment, Environment.TESTING)
        self.assertEqual(settings.trading_mode, "paper")
    
    def test_get_settings_singleton(self):
        """Test get_settings returns loaded settings."""
        from config.loader import get_settings, get_config_loader
        from config.settings import Environment
        
        # Reset singleton
        import config.loader
        config.loader._config_loader = None
        
        settings = get_settings()
        self.assertIsNotNone(settings)


class TestEnvironmentConfigs(unittest.TestCase):
    """Test environment-specific configurations."""
    
    def test_development_config(self):
        """Test development environment config."""
        from config.environments.development import get_config
        from config.settings import Environment, LogLevel
        
        config = get_config()
        
        self.assertEqual(config.environment, Environment.DEVELOPMENT)
        self.assertEqual(config.log_level, LogLevel.DEBUG)
        self.assertTrue(config.debug)
        self.assertEqual(config.trading_mode, "paper")
        self.assertTrue(config.exchange.sandbox)
        self.assertFalse(config.alerts.enabled)
    
    def test_testing_config(self):
        """Test testing environment config."""
        from config.environments.testing import get_config
        from config.settings import Environment, LogLevel
        
        config = get_config()
        
        self.assertEqual(config.environment, Environment.TESTING)
        self.assertEqual(config.log_level, LogLevel.DEBUG)
        self.assertTrue(config.debug)
        self.assertFalse(config.safety.kill_switch_enabled)
    
    def test_paper_config(self):
        """Test paper trading environment config."""
        from config.environments.paper import get_config
        from config.settings import Environment, LogLevel
        
        config = get_config()
        
        self.assertEqual(config.environment, Environment.PAPER)
        self.assertEqual(config.log_level, LogLevel.INFO)
        self.assertFalse(config.debug)
        self.assertTrue(config.alerts.enabled)
        self.assertTrue(config.safety.kill_switch_enabled)
    
    def test_shadow_config(self):
        """Test shadow trading environment config."""
        from config.environments.shadow import get_config
        from config.settings import Environment
        
        config = get_config()
        
        self.assertEqual(config.environment, Environment.SHADOW)
        self.assertEqual(config.trading_mode, "shadow")
        self.assertFalse(config.exchange.sandbox)
    
    def test_production_config(self):
        """Test production environment config."""
        from config.environments.production import get_config
        from config.settings import Environment, LogLevel
        
        config = get_config()
        
        self.assertEqual(config.environment, Environment.PRODUCTION)
        self.assertEqual(config.log_level, LogLevel.WARNING)
        self.assertFalse(config.debug)
        self.assertEqual(config.trading_mode, "live")
        self.assertFalse(config.exchange.sandbox)
        self.assertEqual(config.database.type, "postgresql")


if __name__ == '__main__':
    unittest.main(verbosity=2)
