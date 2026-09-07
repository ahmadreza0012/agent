"""
Metrics Collector - Prometheus-compatible metrics.
"""

from prometheus_client import (
    Counter, Gauge, Histogram, Summary, Info,
    generate_latest, REGISTRY, CollectorRegistry
)
from typing import Dict, Any, Optional
import time
from datetime import datetime

# --- Registries ---
TRADING_REGISTRY = CollectorRegistry()
SYSTEM_REGISTRY = CollectorRegistry()

# --- Trading Metrics ---
trade_counter = Counter('trades_total', 'Total number of trades', 
                        ['symbol', 'side', 'strategy'], registry=TRADING_REGISTRY)
trade_volume = Counter('trade_volume_total', 'Total trading volume', 
                       ['symbol'], registry=TRADING_REGISTRY)
trade_pnl = Counter('trade_pnl_total', 'Total PnL', 
                    ['symbol', 'strategy'], registry=TRADING_REGISTRY)

order_counter = Counter('orders_total', 'Total number of orders',
                        ['symbol', 'status'], registry=TRADING_REGISTRY)
order_value = Counter('order_value_total', 'Total order value',
                      ['symbol'], registry=TRADING_REGISTRY)

# --- Risk Metrics ---
risk_drawdown = Gauge('risk_drawdown', 'Current drawdown', registry=TRADING_REGISTRY)
risk_equity = Gauge('risk_equity', 'Current equity', registry=TRADING_REGISTRY)
risk_exposure = Gauge('risk_exposure', 'Current exposure', registry=TRADING_REGISTRY)
risk_daily_pnl = Gauge('risk_daily_pnl', 'Daily PnL', registry=TRADING_REGISTRY)
risk_drawdown_max = Gauge('risk_drawdown_max', 'Maximum drawdown', registry=TRADING_REGISTRY)

# --- Performance Metrics ---
sharpe_ratio = Gauge('sharpe_ratio', 'Sharpe ratio', registry=TRADING_REGISTRY)
win_rate = Gauge('win_rate', 'Win rate', registry=TRADING_REGISTRY)
turnover = Gauge('turnover', 'Turnover', registry=TRADING_REGISTRY)
fees_total = Counter('fees_total', 'Total fees', registry=TRADING_REGISTRY)
slippage_total = Counter('slippage_total', 'Total slippage', registry=TRADING_REGISTRY)

# --- Latency Metrics ---
execution_latency = Histogram('execution_latency_seconds', 'Order execution latency',
                               buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
                               registry=TRADING_REGISTRY)
decision_latency = Histogram('decision_latency_seconds', 'Decision making latency',
                              buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
                              registry=TRADING_REGISTRY)
api_latency = Histogram('api_latency_seconds', 'API request latency',
                         buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
                         registry=TRADING_REGISTRY)

# --- System Metrics ---
system_uptime = Gauge('system_uptime_seconds', 'System uptime', registry=SYSTEM_REGISTRY)
system_health = Gauge('system_health', 'System health (1=healthy, 0=unhealthy)', 
                       registry=SYSTEM_REGISTRY)
component_status = Gauge('component_status', 'Component status (1=healthy, 0=unhealthy)',
                          ['component'], registry=SYSTEM_REGISTRY)

# --- Metadata ---
system_info = Info('system', 'System information', registry=SYSTEM_REGISTRY)


# --- Metrics Manager ---
class MetricsManager:
    """Manager for collecting and exposing metrics."""
    
    def __init__(self):
        self._start_time = time.time()
        system_info.info({
            'version': '2.0.0',
            'mode': 'unknown',
            'environment': 'production'
        })
    
    def record_trade(self, symbol: str, side: str, strategy: str, 
                     amount: float, price: float, pnl: float):
        """Record a trade."""
        trade_counter.labels(symbol=symbol, side=side, strategy=strategy).inc()
        trade_volume.labels(symbol=symbol).inc(amount * price)
        if pnl > 0:
            trade_pnl.labels(symbol=symbol, strategy=strategy).inc(pnl)
    
    def record_order(self, symbol: str, status: str, value: float):
        """Record an order."""
        order_counter.labels(symbol=symbol, status=status).inc()
        order_value.labels(symbol=symbol).inc(value)
    
    def update_risk(self, drawdown: float, equity: float, exposure: float, 
                    daily_pnl: float, max_drawdown: float):
        """Update risk metrics."""
        risk_drawdown.set(drawdown)
        risk_equity.set(equity)
        risk_exposure.set(exposure)
        risk_daily_pnl.set(daily_pnl)
        risk_drawdown_max.set(max_drawdown)
    
    def update_performance(self, sharpe: float, win_rate_val: float, 
                           turnover_val: float, fees: float, slippage: float):
        """Update performance metrics."""
        sharpe_ratio.set(sharpe)
        win_rate.set(win_rate_val)
        turnover.set(turnover_val)
        fees_total.inc(fees)
        slippage_total.inc(slippage)
    
    def record_latency(self, operation: str, duration: float):
        """Record operation latency."""
        if operation == 'execution':
            execution_latency.observe(duration)
        elif operation == 'decision':
            decision_latency.observe(duration)
        elif operation == 'api':
            api_latency.observe(duration)
    
    def update_system(self, health: bool, uptime: Optional[float] = None):
        """Update system metrics."""
        system_health.set(1 if health else 0)
        if uptime:
            system_uptime.set(uptime)
        else:
            system_uptime.set(time.time() - self._start_time)
    
    def update_component(self, component: str, healthy: bool):
        """Update component status."""
        component_status.labels(component=component).set(1 if healthy else 0)
    
    def set_mode(self, mode: str):
        """Set system mode."""
        system_info.info({'mode': mode})
    
    def get_trading_metrics(self) -> bytes:
        """Get trading registry metrics."""
        return generate_latest(TRADING_REGISTRY)
    
    def get_system_metrics(self) -> bytes:
        """Get system registry metrics."""
        return generate_latest(SYSTEM_REGISTRY)
    
    def get_all_metrics(self) -> bytes:
        """Get all metrics."""
        return generate_latest(REGISTRY)
    
    def reset_trading_metrics(self):
        """Reset trading metrics (for testing)."""
        # This is intentionally limited - some metrics shouldn't be resettable
        pass


# --- Singleton ---
_metrics_manager: Optional[MetricsManager] = None

def get_metrics_manager() -> MetricsManager:
    """Get singleton metrics manager."""
    global _metrics_manager
    if _metrics_manager is None:
        _metrics_manager = MetricsManager()
    return _metrics_manager
