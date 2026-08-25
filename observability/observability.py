"""
Observability - Central observability integration.
"""

from typing import Dict, Any, Optional, List
import time
from datetime import datetime

from .logger import LoggerFactory, LogContext, log_trade, log_decision, log_risk_event
from .metrics import get_metrics_manager
from .audit import AuditLogger, AuditContext
from .alerts import AlertManager, Alert, AlertTemplates


class Observability:
    """
    Central observability hub.
    
    Integrates:
    - Structured logging
    - Metrics collection
    - Audit trail
    - Alerting
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        # Initialize components
        self.logger = LoggerFactory.get_system_logger()
        self.metrics = get_metrics_manager()
        self.audit = AuditLogger()
        self.alerts = AlertManager(self.config.get('alerts', {}))
        
        # Set mode
        self.metrics.set_mode(self.config.get('mode', 'unknown'))
        
        self._start_time = time.time()
        self.logger.info(f"Observability initialized in {self.config.get('mode', 'unknown')} mode")
    
    # --- Logging ---
    def log_trade(self, trade_data: Dict) -> None:
        log_trade(self.logger, trade_data)
    
    def log_decision(self, decision: Dict) -> None:
        log_decision(self.logger, decision)
    
    def log_risk_event(self, event: Dict) -> None:
        log_risk_event(self.logger, event)
    
    # --- Metrics ---
    def record_trade(self, symbol: str, side: str, strategy: str,
                     amount: float, price: float, pnl: float) -> None:
        self.metrics.record_trade(symbol, side, strategy, amount, price, pnl)
    
    def record_order(self, symbol: str, status: str, value: float) -> None:
        self.metrics.record_order(symbol, status, value)
    
    def update_risk(self, drawdown: float, equity: float, exposure: float,
                    daily_pnl: float, max_drawdown: float) -> None:
        self.metrics.update_risk(drawdown, equity, exposure, daily_pnl, max_drawdown)
    
    def update_performance(self, sharpe: float, win_rate: float,
                           turnover: float, fees: float, slippage: float) -> None:
        self.metrics.update_performance(sharpe, win_rate, turnover, fees, slippage)
    
    def record_latency(self, operation: str, duration: float) -> None:
        self.metrics.record_latency(operation, duration)
    
    # --- Audit ---
    def audit(self, event_type: str, component: str, action: str,
              details: Dict, user_id: Optional[str] = None,
              ip_address: Optional[str] = None) -> None:
        self.audit.log(event_type, component, action, details, user_id, ip_address)
    
    def audit_context(self, event_type: str, component: str, action: str,
                      user_id: Optional[str] = None,
                      ip_address: Optional[str] = None) -> AuditContext:
        return AuditContext(self.audit, event_type, component, action, user_id, ip_address)
    
    # --- Alerts ---
    def send_alert(self, alert: Alert) -> bool:
        return self.alerts.send_alert(alert)
    
    def alert_trade_failure(self, error: str, trade_data: Dict) -> None:
        alert = AlertTemplates.trade_failure(error, trade_data)
        self.send_alert(alert)
    
    def alert_risk_breach(self, risk_data: Dict) -> None:
        alert = AlertTemplates.risk_breach(risk_data)
        self.send_alert(alert)
    
    def alert_kill_switch(self, reason: str, details: Dict) -> None:
        alert = AlertTemplates.kill_switch_triggered(reason, details)
        self.send_alert(alert)
    
    # --- System ---
    def update_system_health(self, health: bool) -> None:
        self.metrics.update_system(health)
        self.metrics.update_component('system', health)
    
    def update_component_health(self, component: str, healthy: bool) -> None:
        self.metrics.update_component(component, healthy)
        if not healthy:
            alert = AlertTemplates.system_health_check_failed(component, "Component unhealthy")
            self.send_alert(alert)
    
    def get_metrics(self) -> bytes:
        return self.metrics.get_all_metrics()
    
    def get_audit_events(self, **kwargs) -> List[Dict]:
        return self.audit.query(**kwargs)


# --- Singleton ---
_observability: Optional[Observability] = None

def get_observability(config: Optional[Dict] = None) -> Observability:
    """Get singleton observability instance."""
    global _observability
    if _observability is None:
        _observability = Observability(config)
    return _observability
