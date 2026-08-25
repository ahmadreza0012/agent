"""
Unit tests for Phase 28 Static Quality improvements.
"""

import sys
sys.path.insert(0, '/workspace')

import unittest
import os
import tempfile
import json
from pathlib import Path


class TestExceptions(unittest.TestCase):
    """Test custom exception classes."""
    
    def test_trading_system_error(self) -> None:
        """Test base TradingSystemError."""
        from exceptions import TradingSystemError
        
        error = TradingSystemError("Test error")
        self.assertEqual(str(error), "Test error")
        
        error_with_context = TradingSystemError("Test error", {"key": "value"})
        self.assertIn("context", str(error_with_context))
    
    def test_data_error(self) -> None:
        """Test DataError."""
        from exceptions import DataError
        
        error = DataError("Data fetch failed")
        self.assertIsInstance(error, Exception)
    
    def test_data_validation_error(self) -> None:
        """Test DataValidationError with errors dict."""
        from exceptions import DataValidationError
        
        errors = {"field1": "invalid", "field2": "missing"}
        error = DataValidationError("Validation failed", errors=errors)
        self.assertEqual(error.errors, errors)
    
    def test_exchange_error(self) -> None:
        """Test ExchangeError with exchange name."""
        from exceptions import ExchangeError
        
        error = ExchangeError("Connection failed", exchange="binance")
        self.assertEqual(error.exchange, "binance")
    
    def test_order_error(self) -> None:
        """Test OrderError with order_id."""
        from exceptions import OrderError
        
        error = OrderError("Order rejected", order_id="12345")
        self.assertEqual(error.order_id, "12345")
    
    def test_risk_error(self) -> None:
        """Test RiskError with metric info."""
        from exceptions import RiskError
        
        error = RiskError(
            "Drawdown exceeded",
            metric="drawdown",
            value=0.20,
            limit=0.15
        )
        self.assertEqual(error.metric, "drawdown")
        self.assertEqual(error.value, 0.20)
        self.assertEqual(error.limit, 0.15)
    
    def test_circuit_breaker_error(self) -> None:
        """Test CircuitBreakerError with state."""
        from exceptions import CircuitBreakerError
        
        error = CircuitBreakerError("Circuit breaker tripped", state="HALT")
        self.assertEqual(error.state, "HALT")
    
    def test_configuration_error(self) -> None:
        """Test ConfigurationError."""
        from exceptions import ConfigurationError
        
        error = ConfigurationError("Invalid config")
        self.assertIsInstance(error, Exception)


class TestConfigNew(unittest.TestCase):
    """Test new Pydantic configuration."""
    
    def test_default_config(self) -> None:
        """Test default configuration values."""
        from config_new import Config, TradingMode
        
        config = Config()
        self.assertEqual(config.mode, TradingMode.RESEARCH)
        self.assertEqual(config.environment, "development")
        self.assertFalse(config.debug)
    
    def test_risk_config_validation(self) -> None:
        """Test risk config validation."""
        from config_new import RiskConfig
        
        # Valid values
        config = RiskConfig(max_drawdown=0.15)
        self.assertEqual(config.max_drawdown, 0.15)
        
        # Invalid value should raise
        with self.assertRaises(ValueError):
            RiskConfig(max_drawdown=1.5)
    
    def test_live_mode_requires_enable(self) -> None:
        """Test that live mode requires explicit enable."""
        from config_new import Config
        
        # Should fail without ENABLE_LIVE_TRADING
        with self.assertRaises(ValueError):
            Config(mode="live")
    
    def test_is_methods(self) -> None:
        """Test mode checking methods."""
        from config_new import Config, TradingMode
        
        config_research = Config(mode=TradingMode.RESEARCH)
        self.assertTrue(config_research.is_research_mode())
        self.assertFalse(config_research.is_live_mode())
        
        config_paper = Config(mode=TradingMode.PAPER)
        self.assertTrue(config_paper.is_paper_mode())
    
    def test_get_risk_thresholds(self) -> None:
        """Test getting risk thresholds based on mode."""
        from config_new import Config, TradingMode
        
        # Research mode thresholds
        config_research = Config(mode=TradingMode.RESEARCH)
        thresholds = config_research.get_risk_thresholds()
        self.assertIn('target_return', thresholds)
        self.assertIn('max_drawdown', thresholds)
        
        # Test paper mode thresholds (same as live but without enforcement)
        config_paper = Config(mode=TradingMode.PAPER)
        thresholds_paper = config_paper.get_risk_thresholds()
        self.assertIn('target_return', thresholds_paper)
    
    def test_from_env(self) -> None:
        """Test loading config from environment."""
        from config_new import Config, reset_config
        
        # Set env vars
        os.environ['MAX_DRAWDOWN'] = '0.10'
        
        try:
            config = Config.from_env()
            self.assertEqual(config.risk.max_drawdown, 0.10)
        finally:
            del os.environ['MAX_DRAWDOWN']
            reset_config()


class TestLoggingConfig(unittest.TestCase):
    """Test logging configuration."""
    
    def test_structured_formatter(self) -> None:
        """Test structured JSON formatter."""
        from logging_config import StructuredFormatter
        import logging
        
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        parsed = json.loads(output)
        
        self.assertEqual(parsed['level'], 'INFO')
        self.assertEqual(parsed['message'], 'Test message')
        self.assertIn('timestamp', parsed)
    
    def test_console_formatter(self) -> None:
        """Test console formatter."""
        from logging_config import ConsoleFormatter
        import logging
        
        formatter = ConsoleFormatter(use_colors=False)
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        self.assertIn('ERROR', output)
        self.assertIn('Error message', output)
    
    def test_setup_logging(self) -> None:
        """Test setup_logging function."""
        from logging_config import setup_logging, get_logger
        import tempfile
        
        log_file = tempfile.mktemp('.log')
        setup_logging(level='DEBUG', json_output=True, log_file=log_file)
        
        logger = get_logger('test_logger')
        logger.info('Test log entry')
        
        # Verify file was created
        self.assertTrue(Path(log_file).exists())
        
        # Verify content
        with open(log_file) as f:
            lines = f.readlines()
            self.assertGreater(len(lines), 0)
            entry = json.loads(lines[0])
            self.assertEqual(entry['message'], 'Test log entry')
    
    def test_get_logger(self) -> None:
        """Test get_logger function."""
        from logging_config import get_logger
        import logging
        
        logger = get_logger('my_module')
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, 'my_module')


class TestTypeAnnotations(unittest.TestCase):
    """Verify type annotations are present."""
    
    def test_exceptions_have_annotations(self) -> None:
        """Test that exception classes have type annotations."""
        import inspect
        from exceptions import TradingSystemError
        
        # Get __init__ signature
        sig = inspect.signature(TradingSystemError.__init__)
        params = sig.parameters
        
        self.assertIn('message', params)
        self.assertEqual(params['message'].annotation, str)
    
    def test_config_has_annotations(self) -> None:
        """Test that config classes have type annotations."""
        import inspect
        from config_new import Config
        
        # Pydantic models use field annotations
        annotations = Config.__annotations__
        self.assertIn('mode', annotations)
        self.assertIn('risk', annotations)


if __name__ == '__main__':
    unittest.main()
