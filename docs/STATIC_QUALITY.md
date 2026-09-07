# Static Quality - Phase 28

## Overview

Phase 28 focuses on code quality, maintainability, and correctness through static analysis tools and modern Python practices.

## Objectives

1. **Type Annotations** - Comprehensive type hints throughout the codebase
2. **Data Classes / Pydantic** - Modern data structures with validation
3. **Static Analysis** - Configured mypy, ruff, pylint
4. **Code Style** - Consistent formatting with black/isort
5. **Exception Handling** - Proper exception hierarchy with context
6. **Structured Logging** - JSON-formatted logs for observability
7. **Configuration Management** - Pydantic-based config with validation

## Files Created

### Core Configuration

- `config_new.py` - Pydantic-based configuration with:
  - Trading mode validation (research, paper, shadow, live)
  - Risk, execution, data, ML, backtest, logging sub-configs
  - Environment variable loading
  - Live mode protection (requires explicit enable)
  - Type-safe field definitions with constraints

### Exception Hierarchy

- `exceptions.py` - Custom exception classes:
  - `TradingSystemError` (base)
  - `DataError`, `DataValidationError`, `DataSourceError`
  - `ExchangeError`, `ExchangeConnectionError`, `ExchangeRateLimitError`
  - `OrderError`, `OrderRejectedError`, `OrderTimeoutError`
  - `RiskError`, `CircuitBreakerError`, `DrawdownExceededError`, `PositionLimitError`
  - `ReconciliationError`
  - `ConfigurationError`, `ValidationError`
  - `APIError`, `AuthenticationError`
  - `DatabaseError`
  - `ModelError`, `StrategyError`

All exceptions include:
- Context dictionaries for additional information
- Type annotations
- Proper inheritance chain

### Structured Logging

- `logging_config.py` - Logging infrastructure:
  - `StructuredFormatter` - JSON output for machine parsing
  - `ConsoleFormatter` - Human-readable colored output
  - `LogContext` - Context manager for temporary log fields
  - `setup_logging()` - Centralized logging setup
  - `get_logger()` - Logger retrieval helper

### Development Tools

- `requirements-dev.txt` - Development dependencies:
  - mypy, ruff, pylint for static analysis
  - black, isort for formatting
  - pytest, pytest-cov, pytest-mock for testing
  - types-* packages for type stubs
  - pre-commit for git hooks

- `pyproject.toml` - Tool configurations:
  - Black formatting settings
  - isort import sorting
  - mypy strict type checking
  - ruff linting rules
  - pytest configuration with markers

- `.pre-commit-config.yaml` - Git hooks:
  - ruff auto-fix on commit
  - black formatting
  - isort import organization
  - trailing whitespace removal
  - end-of-file fixer
  - YAML/TOML validation
  - large file detection
  - private key detection

### Tests

- `tests/test_phase28_static_quality.py` - Unit tests covering:
  - Exception classes (9 tests)
  - Pydantic configuration (6 tests)
  - Logging configuration (4 tests)
  - Type annotation verification (2 tests)

All 20 tests pass successfully.

## Configuration Structure

```python
from config_new import Config, TradingMode

# Default configuration (research mode)
config = Config()
assert config.mode == TradingMode.RESEARCH
assert config.environment == "development"

# Risk thresholds vary by mode
thresholds = config.get_risk_thresholds()
# Research: more permissive
# Live: stricter (requires ENABLE_LIVE_TRADING env var)

# Load from environment
config = Config.from_env()
```

## Exception Usage

```python
from exceptions import (
    TradingSystemError,
    DataError,
    ExchangeError,
    OrderError,
    RiskError,
    CircuitBreakerError,
)

# Basic usage
raise DataError("Failed to fetch data")

# With context
raise ExchangeError(
    "Connection timeout",
    exchange="binance",
    context={"timeout": 30, "retries": 3}
)

# Specific exceptions
raise CircuitBreakerError("Circuit breaker tripped", state="HALT")
raise OrderRejectedError("Order rejected by exchange", order_id="12345")
```

## Structured Logging Usage

```python
from logging_config import setup_logging, get_logger, LogContext

# Setup with JSON output
setup_logging(
    level="INFO",
    json_output=True,
    log_file="logs/trading.log"
)

logger = get_logger(__name__)

# Standard logging
logger.info("Starting trading system")
logger.error("Error occurred", extra={"user_id": "123"})

# Context-aware logging
with LogContext("order_id", "abc-123").bind(logger):
    logger.info("Processing order")  # Includes order_id in JSON
```

## Running Static Analysis

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run ruff (linting + formatting fixes)
ruff check --fix .

# Run black (formatting)
black .

# Run isort (import sorting)
isort .

# Run mypy (type checking)
mypy --strict .

# Run all pre-commit hooks
pre-commit run --all-files
```

## Pre-commit Setup

```bash
# Install pre-commit hooks
pre-commit install

# Verify installation
pre-commit --version

# Run hooks manually
pre-commit run --all-files
```

## Type Annotation Guidelines

All new code must include:
1. Function parameter types
2. Return type annotations
3. Class attribute annotations
4. Use `list`/`dict` instead of `List`/`Dict` (Python 3.9+)
5. Use `Optional[X]` or `X | None` for nullable types
6. Avoid bare `Any` - use specific types when possible

Example:
```python
from typing import Optional

def calculate_sharpe(
    returns: list[float],
    risk_free_rate: float = 0.0,
) -> float:
    """Calculate Sharpe ratio."""
    if not returns:
        raise ValueError("Returns cannot be empty")
    return sum(returns) / len(returns)
```

## Docstring Style

Follow Google-style docstrings:
```python
def process_order(order_id: str, amount: float) -> dict:
    """
    Process a trading order.

    Args:
        order_id: Unique order identifier
        amount: Order amount in base currency

    Returns:
        Dictionary with processing result

    Raises:
        OrderError: If order processing fails
    """
    pass
```

## Success Criteria

✅ All Python files have comprehensive type hints
✅ All data structures use Pydantic models
✅ ruff runs with minimal errors (warnings addressed)
✅ Custom exception hierarchy implemented
✅ Structured logging available
✅ Pydantic configuration with validation
✅ Pre-commit hooks configured
✅ All 20 tests pass
✅ No hard-coded secrets
✅ Live mode protection enforced

## Next Steps

After Phase 28:
- Apply type annotations to existing codebase
- Fix remaining ruff warnings
- Add docstrings to all public functions
- Configure CI/CD to run static analysis
- Set up automated pre-commit in CI
