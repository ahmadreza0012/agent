"""Custom Exceptions for Trading System.

Proper exception hierarchy with context information.
"""

from typing import Any, Dict, Optional


class TradingSystemError(Exception):
    """Base exception for trading system."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        if self.context:
            return f"{self.message} (context: {self.context})"
        return self.message


class DataError(TradingSystemError):
    """Raised when data operations fail."""
    pass


class DataValidationError(DataError):
    """Raised when data validation fails."""

    def __init__(
        self,
        message: str,
        errors: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, context)
        self.errors = errors or {}


class DataSourceError(DataError):
    """Raised when data source is unavailable."""

    def __init__(
        self,
        message: str,
        source: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, context)
        self.source = source


class ExchangeError(TradingSystemError):
    """Raised when exchange operations fail."""

    def __init__(
        self,
        message: str,
        exchange: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, context)
        self.exchange = exchange


class ExchangeConnectionError(ExchangeError):
    """Raised when exchange connection fails."""
    pass


class ExchangeRateLimitError(ExchangeError):
    """Raised when exchange rate limit is exceeded."""
    pass


class OrderError(TradingSystemError):
    """Raised when order operations fail."""

    def __init__(
        self,
        message: str,
        order_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, context)
        self.order_id = order_id


class OrderRejectedError(OrderError):
    """Raised when order is rejected by exchange."""
    pass


class OrderTimeoutError(OrderError):
    """Raised when order times out."""
    pass


class RiskError(TradingSystemError):
    """Raised when risk limits are breached."""

    def __init__(
        self,
        message: str,
        metric: Optional[str] = None,
        value: Optional[float] = None,
        limit: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, context)
        self.metric = metric
        self.value = value
        self.limit = limit


class CircuitBreakerError(RiskError):
    """Raised when circuit breaker is tripped."""

    def __init__(
        self,
        message: str,
        state: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, context=context)
        self.state = state


class DrawdownExceededError(RiskError):
    """Raised when drawdown limit is exceeded."""
    pass


class PositionLimitError(RiskError):
    """Raised when position limit is exceeded."""
    pass


class ReconciliationError(TradingSystemError):
    """Raised when reconciliation fails."""

    def __init__(
        self,
        message: str,
        mismatches: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, context)
        self.mismatches = mismatches or {}


class ConfigurationError(TradingSystemError):
    """Raised when configuration is invalid."""
    pass


class ValidationError(TradingSystemError):
    """Raised when validation fails."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, context)
        self.field = field
        self.value = value


class APIError(TradingSystemError):
    """Raised when API operations fail."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        endpoint: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, context)
        self.status_code = status_code
        self.endpoint = endpoint


class AuthenticationError(APIError):
    """Raised when authentication fails."""
    pass


class DatabaseError(TradingSystemError):
    """Raised when database operations fail."""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, context)
        self.operation = operation


class ModelError(TradingSystemError):
    """Raised when ML model operations fail."""

    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, context)
        self.model_name = model_name


class StrategyError(TradingSystemError):
    """Raised when strategy operations fail."""

    def __init__(
        self,
        message: str,
        strategy_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, context)
        self.strategy_name = strategy_name
