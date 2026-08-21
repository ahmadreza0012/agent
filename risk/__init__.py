"""
Risk Management Module
======================
Centralized risk management for crypto portfolio optimization.

Components:
- RiskEngine: Independent risk evaluation
- RiskDecision: Risk decision output
- RiskMetrics: Risk metric calculation
- RiskLimits: Risk limit configuration
- CircuitBreaker: Stateful circuit breaker
- BreakerState: Circuit breaker states
"""

from .risk_engine import RiskEngine, RiskDecision
from .risk_limits import RiskLimits, DEFAULT_LIMITS
from .risk_metrics import RiskMetrics, calculate_risk_metrics
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig, BreakerState

__all__ = [
    'RiskEngine',
    'RiskDecision',
    'RiskLimits',
    'DEFAULT_LIMITS',
    'RiskMetrics',
    'calculate_risk_metrics',
    'CircuitBreaker',
    'CircuitBreakerConfig',
    'BreakerState',
]
