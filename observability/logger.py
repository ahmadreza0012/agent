"""
Structured Logger - JSON-formatted logging with context.
"""

import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pythonjsonlogger import jsonlogger


# --- Custom JSON Formatter ---
class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record['timestamp'] = datetime.now(timezone.utc).isoformat()
        log_record['level'] = record.levelname
        log_record['component'] = getattr(record, 'component', 'unknown')
        log_record['request_id'] = getattr(record, 'request_id', None)
        
        if record.exc_info:
            log_record['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exc()
            }


# --- Logger Factory ---
class LoggerFactory:
    """Factory for creating structured loggers."""
    
    _loggers: Dict[str, logging.Logger] = {}
    
    @classmethod
    def get_logger(cls, name: str, component: str = "unknown", level: str = "INFO") -> logging.Logger:
        """Get or create a structured logger."""
        if name in cls._loggers:
            return cls._loggers[name]
        
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        
        # Remove existing handlers
        logger.handlers = []
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(component)s %(request_id)s %(message)s'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        cls._loggers[name] = logger
        return logger
    
    @classmethod
    def get_trading_logger(cls) -> logging.Logger:
        """Get logger for trading operations."""
        return cls.get_logger('trading', 'trading', 'INFO')
    
    @classmethod
    def get_risk_logger(cls) -> logging.Logger:
        """Get logger for risk operations."""
        return cls.get_logger('risk', 'risk', 'INFO')
    
    @classmethod
    def get_execution_logger(cls) -> logging.Logger:
        """Get logger for execution operations."""
        return cls.get_logger('execution', 'execution', 'INFO')
    
    @classmethod
    def get_api_logger(cls) -> logging.Logger:
        """Get logger for API operations."""
        return cls.get_logger('api', 'api', 'INFO')
    
    @classmethod
    def get_system_logger(cls) -> logging.Logger:
        """Get logger for system operations."""
        return cls.get_logger('system', 'system', 'INFO')


# --- Context Manager ---
class LogContext:
    """Context manager for adding context to logs."""
    
    def __init__(self, logger: logging.Logger, **kwargs):
        self.logger = logger
        self.context = kwargs
        self._old_context = {}
    
    def __enter__(self):
        for key, value in self.context.items():
            if hasattr(self.logger, key):
                self._old_context[key] = getattr(self.logger, key)
                setattr(self.logger, key, value)
        return self
    
    def __exit__(self, *args):
        for key, value in self._old_context.items():
            setattr(self.logger, key, value)


# --- Convenience Functions ---
def log_trade(logger, trade_data: Dict[str, Any]) -> None:
    """Log a trade with full details."""
    logger.info(json.dumps({
        'event': 'trade',
        'symbol': trade_data.get('symbol'),
        'side': trade_data.get('side'),
        'price': trade_data.get('price'),
        'amount': trade_data.get('amount'),
        'fee': trade_data.get('fee'),
        'pnl': trade_data.get('pnl'),
        'order_id': trade_data.get('order_id'),
        'strategy': trade_data.get('strategy'),
        'timestamp': datetime.now(timezone.utc).isoformat()
    }))


def log_decision(logger, decision: Dict[str, Any]) -> None:
    """Log a trading decision."""
    logger.info(json.dumps({
        'event': 'decision',
        'strategy': decision.get('strategy'),
        'signal': decision.get('signal'),
        'confidence': decision.get('confidence'),
        'weight': decision.get('weight'),
        'asset': decision.get('asset'),
        'regime': decision.get('regime'),
        'timestamp': datetime.now(timezone.utc).isoformat()
    }))


def log_risk_event(logger, event: Dict[str, Any]) -> None:
    """Log a risk event."""
    logger.warning(json.dumps({
        'event': 'risk_event',
        'type': event.get('type'),
        'severity': event.get('severity'),
        'description': event.get('description'),
        'details': event.get('details'),
        'timestamp': datetime.now(timezone.utc).isoformat()
    }))
