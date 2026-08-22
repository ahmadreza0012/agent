"""
Observability Module - Structured logging, metrics, audit, and alerts.
"""

from .logger import LoggerFactory, LogContext, log_trade, log_decision, log_risk_event
from .metrics import get_metrics_manager, MetricsManager
from .audit import AuditLogger, AuditContext
from .alerts import AlertManager, Alert, AlertSeverity, AlertChannel, AlertTemplates
from .observability import Observability, get_observability

__all__ = [
    'LoggerFactory',
    'LogContext',
    'log_trade',
    'log_decision',
    'log_risk_event',
    'get_metrics_manager',
    'MetricsManager',
    'AuditLogger',
    'AuditContext',
    'AlertManager',
    'Alert',
    'AlertSeverity',
    'AlertChannel',
    'AlertTemplates',
    'Observability',
    'get_observability',
]
