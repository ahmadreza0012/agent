"""Structured Logging Configuration.

Provides JSON-formatted structured logging for better observability.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class StructuredFormatter(logging.Formatter):
    """Structured JSON formatter for logs.
    
    Produces machine-readable log entries with consistent fields.
    """

    def __init__(
        self,
        extra_fields: Optional[Dict[str, Any]] = None,
        include_timestamp: bool = True,
        include_source: bool = True,
    ) -> None:
        """Initialize structured formatter.
        
        Args:
            extra_fields: Additional fields to include in every log entry
            include_timestamp: Whether to include timestamp field
            include_source: Whether to include source location (module, function, line)
        """
        super().__init__()
        self.extra_fields = extra_fields or {}
        self.include_timestamp = include_timestamp
        self.include_source = include_source

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON string representation of log entry
        """
        log_entry: Dict[str, Any] = {}

        # Add timestamp if requested
        if self.include_timestamp:
            log_entry["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Standard fields
        log_entry["level"] = record.levelname
        log_entry["logger"] = record.name
        log_entry["message"] = record.getMessage()

        # Add source location if requested
        if self.include_source:
            log_entry["module"] = record.module
            log_entry["function"] = record.funcName
            log_entry["line"] = record.lineno

        # Add extra fields
        log_entry.update(self.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Unknown",
                "message": str(record.exc_info[1]) if record.exc_info[1] else "",
                "traceback": self.formatException(record.exc_info) if record.exc_info[2] else None,
            }

        # Add extra attributes from record
        reserved_keys = {
            "args", "asctime", "created", "exc_info", "exc_text", "filename",
            "funcName", "id", "levelname", "levelno", "lineno", "module",
            "msecs", "message", "msg", "name", "pathname", "process",
            "processName", "relativeCreated", "stack_info", "thread", "threadName",
        }

        for key, value in record.__dict__.items():
            if key not in reserved_keys:
                try:
                    # Try to serialize the value
                    json.dumps(value)
                    log_entry[key] = value
                except (TypeError, ValueError):
                    # Skip non-serializable values
                    log_entry[key] = str(value)

        return json.dumps(log_entry, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable console formatter with colors.
    """

    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True) -> None:
        """Initialize console formatter.
        
        Args:
            use_colors: Whether to use colored output
        """
        super().__init__()
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        """Format log record for console output.
        
        Args:
            record: Log record to format
            
        Returns:
            Formatted string
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname

        if self.use_colors:
            color = self.COLORS.get(level, "")
            reset = self.RESET
            level_str = f"{color}{level:^8}{reset}"
        else:
            level_str = f"{level:^8}"

        message = record.getMessage()

        # Add exception info if present
        if record.exc_info:
            exception_str = self.formatException(record.exc_info)
            return f"{timestamp} | {level_str} | {record.name} | {message}\n{exception_str}"

        return f"{timestamp} | {level_str} | {record.name} | {message}"


def setup_logging(
    level: str = "INFO",
    json_output: bool = True,
    log_file: Optional[Path | str] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
    console: bool = True,
    use_colors: bool = True,
    max_file_size_mb: int = 100,
    backup_count: int = 5,
) -> logging.Logger:
    """Setup logging configuration.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: Whether to use JSON formatting
        log_file: Optional path to log file
        extra_fields: Extra fields to include in structured logs
        console: Whether to log to console
        use_colors: Whether to use colored console output
        max_file_size_mb: Maximum log file size in MB
        backup_count: Number of backup log files to keep
        
    Returns:
        Root logger instance
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create formatter based on output type
    if json_output:
        formatter = StructuredFormatter(extra_fields=extra_fields)
    else:
        formatter = ConsoleFormatter(use_colors=use_colors)

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        # Convert to Path if string
        log_path = Path(log_file) if isinstance(log_file, str) else log_file

        # Ensure parent directory exists
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Use rotating file handler
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max_file_size_mb * 1024 * 1024,
            backupCount=backup_count,
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Reduce noise from third-party libraries
    noisy_loggers = [
        "urllib3",
        "requests",
        "ccxt",
        "sqlalchemy",
        "asyncio",
    ]

    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LogContext:
    """Context manager for adding temporary log context.
    
    Usage:
        with LogContext("user_id", "123"):
            logger.info("Processing user")
    """

    def __init__(self, key: str, value: Any) -> None:
        """Initialize log context.
        
        Args:
            key: Context key
            value: Context value
        """
        self.key = key
        self.value = value
        self.logger: Optional[logging.Logger] = None

    def __enter__(self) -> "LogContext":
        """Enter context."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context."""
        pass

    def bind(self, logger: logging.Logger) -> "BoundLogContext":
        """Bind context to a logger.
        
        Args:
            logger: Logger to bind to
            
        Returns:
            Bound context manager
        """
        return BoundLogContext(logger, self.key, self.value)


class BoundLogContext:
    """Logger-bound context."""

    def __init__(self, logger: logging.Logger, key: str, value: Any) -> None:
        self.logger = logger
        self.key = key
        self.value = value
        self.old_factory = logging.getLogRecordFactory()

    def __enter__(self) -> logging.Logger:
        """Enter context and add field to log records."""
        def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
            record = self.old_factory(*args, **kwargs)
            setattr(record, self.key, self.value)
            return record

        logging.setLogRecordFactory(factory)
        return self.logger

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context and restore original factory."""
        logging.setLogRecordFactory(self.old_factory)
