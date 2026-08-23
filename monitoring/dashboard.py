"""
Phase 39: Post-Launch Monitoring & Optimization

Real-time monitoring dashboard for production trading system.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class LiveMetrics:
    """Real-time system metrics."""
    timestamp: datetime
    equity: float = 0.0
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    monthly_pnl: float = 0.0
    ytd_pnl: float = 0.0
    
    # Risk metrics
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    current_exposure: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0
    
    # Trading metrics
    open_positions: int = 0
    open_orders: int = 0
    orders_today: int = 0
    fills_today: int = 0
    trades_today: int = 0
    
    # Performance metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    
    # System metrics
    latency_ms: float = 0.0
    error_rate: float = 0.0
    uptime_percent: float = 100.0
    circuit_breaker_state: str = "NORMAL"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'equity': self.equity,
            'daily_pnl': self.daily_pnl,
            'weekly_pnl': self.weekly_pnl,
            'monthly_pnl': self.monthly_pnl,
            'ytd_pnl': self.ytd_pnl,
            'current_drawdown': self.current_drawdown,
            'max_drawdown': self.max_drawdown,
            'current_exposure': self.current_exposure,
            'var_95': self.var_95,
            'cvar_95': self.cvar_95,
            'open_positions': self.open_positions,
            'open_orders': self.open_orders,
            'orders_today': self.orders_today,
            'fills_today': self.fills_today,
            'trades_today': self.trades_today,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'latency_ms': self.latency_ms,
            'error_rate': self.error_rate,
            'uptime_percent': self.uptime_percent,
            'circuit_breaker_state': self.circuit_breaker_state
        }


@dataclass
class Alert:
    """Alert data structure."""
    id: str
    timestamp: datetime
    severity: str
    title: str
    message: str
    component: str
    details: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'severity': self.severity,
            'title': self.title,
            'message': self.message,
            'component': self.component,
            'details': self.details,
            'acknowledged': self.acknowledged
        }


class LiveDashboard:
    """
    Real-time monitoring dashboard.
    
    Collects, stores, and visualizes system metrics.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.metrics_history: List[LiveMetrics] = []
        self.alerts: List[Alert] = []
        self.alert_handlers: List[callable] = []
        self.max_history_length = self.config.get('max_history_length', 10000)
        self.update_interval_seconds = self.config.get('update_interval_seconds', 60)
        
        # Thresholds for alerts
        self.thresholds = {
            'drawdown_warning': 0.10,
            'drawdown_critical': 0.15,
            'daily_loss_warning': -0.03,
            'daily_loss_critical': -0.05,
            'error_rate_warning': 0.05,
            'latency_warning_ms': 1000,
            'exposure_warning': 0.70
        }
        self.thresholds.update(self.config.get('thresholds', {}))
        
        logger.info("LiveDashboard initialized")
    
    def update(self) -> LiveMetrics:
        """Update dashboard with latest metrics."""
        metrics = self.collect_metrics()
        self.metrics_history.append(metrics)
        
        # Trim history if needed
        if len(self.metrics_history) > self.max_history_length:
            self.metrics_history = self.metrics_history[-self.max_history_length:]
        
        # Check for alerts
        self.check_alerts(metrics)
        
        return metrics
    
    def collect_metrics(self) -> LiveMetrics:
        """Collect all real-time metrics from the system."""
        try:
            # Import system components
            from risk.circuit_breaker import CircuitBreaker
            from db_manager import DatabaseManager
            
            db = DatabaseManager()
            
            # Get portfolio metrics
            portfolio = self._get_portfolio_metrics(db)
            
            # Get risk metrics
            risk = self._get_risk_metrics(db)
            
            # Get trading metrics
            trading = self._get_trading_metrics(db)
            
            # Get system metrics
            system = self._get_system_metrics()
            
            # Get circuit breaker state
            cb = CircuitBreaker()
            cb_state = cb.get_state().value if hasattr(cb.get_state(), 'value') else str(cb.get_state())
            
            metrics = LiveMetrics(
                timestamp=datetime.utcnow(),
                **portfolio,
                **risk,
                **trading,
                **system,
                circuit_breaker_state=cb_state
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            return LiveMetrics(timestamp=datetime.utcnow())
    
    def _get_portfolio_metrics(self, db) -> Dict[str, float]:
        """Get portfolio metrics from database."""
        try:
            # Query portfolio value
            result = db.session.execute(
                "SELECT SUM(value) FROM positions WHERE closed_at IS NULL"
            ).fetchone()
            equity = float(result[0]) if result and result[0] else 100000.0
            
            # Calculate PnL
            daily_pnl = self._calculate_daily_pnl(db)
            weekly_pnl = self._calculate_period_pnl(db, days=7)
            monthly_pnl = self._calculate_period_pnl(db, days=30)
            ytd_pnl = self._calculate_ytd_pnl(db)
            
            return {
                'equity': equity,
                'daily_pnl': daily_pnl,
                'weekly_pnl': weekly_pnl,
                'monthly_pnl': monthly_pnl,
                'ytd_pnl': ytd_pnl
            }
        except Exception as e:
            logger.error(f"Error getting portfolio metrics: {e}")
            return {'equity': 100000.0, 'daily_pnl': 0.0, 'weekly_pnl': 0.0, 
                    'monthly_pnl': 0.0, 'ytd_pnl': 0.0}
    
    def _get_risk_metrics(self, db) -> Dict[str, float]:
        """Get risk metrics."""
        try:
            # Calculate drawdown
            current_equity = self._get_portfolio_metrics(db)['equity']
            peak_equity = self._get_peak_equity(db)
            drawdown = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0.0
            
            # Calculate exposure
            exposure = self._calculate_exposure(db)
            
            # Calculate VaR and CVaR
            returns = self._get_recent_returns(db, days=30)
            var_95, cvar_95 = self._calculate_var_cvar(returns)
            
            return {
                'current_drawdown': abs(min(0, drawdown)),
                'max_drawdown': self._get_max_drawdown(db),
                'current_exposure': exposure,
                'var_95': abs(var_95),
                'cvar_95': abs(cvar_95)
            }
        except Exception as e:
            logger.error(f"Error getting risk metrics: {e}")
            return {'current_drawdown': 0.0, 'max_drawdown': 0.0, 
                    'current_exposure': 0.0, 'var_95': 0.0, 'cvar_95': 0.0}
    
    def _get_trading_metrics(self, db) -> Dict[str, Any]:
        """Get trading activity metrics."""
        try:
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Count positions and orders
            open_positions = db.session.execute(
                "SELECT COUNT(*) FROM positions WHERE closed_at IS NULL"
            ).fetchone()[0]
            
            open_orders = db.session.execute(
                "SELECT COUNT(*) FROM orders WHERE status = 'open'"
            ).fetchone()[0]
            
            orders_today = db.session.execute(
                "SELECT COUNT(*) FROM orders WHERE created_at >= :today",
                {'today': today_start}
            ).fetchone()[0]
            
            fills_today = db.session.execute(
                "SELECT COUNT(*) FROM orders WHERE status = 'filled' AND updated_at >= :today",
                {'today': today_start}
            ).fetchone()[0]
            
            # Calculate performance metrics
            trades = self._get_recent_trades(db, days=30)
            sharpe, sortino, win_rate, profit_factor = self._calculate_performance_metrics(trades)
            
            return {
                'open_positions': open_positions or 0,
                'open_orders': open_orders or 0,
                'orders_today': orders_today or 0,
                'fills_today': fills_today or 0,
                'trades_today': fills_today or 0,
                'sharpe_ratio': sharpe,
                'sortino_ratio': sortino,
                'win_rate': win_rate,
                'profit_factor': profit_factor
            }
        except Exception as e:
            logger.error(f"Error getting trading metrics: {e}")
            return {'open_positions': 0, 'open_orders': 0, 'orders_today': 0,
                    'fills_today': 0, 'trades_today': 0, 'sharpe_ratio': 0.0,
                    'sortino_ratio': 0.0, 'win_rate': 0.0, 'profit_factor': 0.0}
    
    def _get_system_metrics(self) -> Dict[str, float]:
        """Get system health metrics."""
        try:
            # Calculate latency (average API response time)
            latency = self._measure_latency()
            
            # Calculate error rate
            error_rate = self._calculate_error_rate()
            
            # Calculate uptime
            uptime = self._calculate_uptime()
            
            return {
                'latency_ms': latency,
                'error_rate': error_rate,
                'uptime_percent': uptime
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {'latency_ms': 0.0, 'error_rate': 0.0, 'uptime_percent': 100.0}
    
    def check_alerts(self, metrics: LiveMetrics):
        """Check for alert conditions and trigger alerts."""
        alerts_to_send = []
        
        # Drawdown alerts
        if metrics.current_drawdown > self.thresholds['drawdown_critical']:
            alerts_to_send.append(self._create_alert(
                severity='critical',
                title='Drawdown Critical',
                message=f"Drawdown exceeded critical threshold: {metrics.current_drawdown:.2%}",
                component='risk',
                details={'drawdown': metrics.current_drawdown}
            ))
        elif metrics.current_drawdown > self.thresholds['drawdown_warning']:
            alerts_to_send.append(self._create_alert(
                severity='warning',
                title='Drawdown Warning',
                message=f"Drawdown exceeded warning threshold: {metrics.current_drawdown:.2%}",
                component='risk',
                details={'drawdown': metrics.current_drawdown}
            ))
        
        # Daily loss alerts
        if metrics.daily_pnl < self.thresholds['daily_loss_critical']:
            alerts_to_send.append(self._create_alert(
                severity='critical',
                title='Daily Loss Critical',
                message=f"Daily loss exceeded critical threshold: {metrics.daily_pnl:.2%}",
                component='trading',
                details={'daily_pnl': metrics.daily_pnl}
            ))
        elif metrics.daily_pnl < self.thresholds['daily_loss_warning']:
            alerts_to_send.append(self._create_alert(
                severity='warning',
                title='Daily Loss Warning',
                message=f"Daily loss exceeded warning threshold: {metrics.daily_pnl:.2%}",
                component='trading',
                details={'daily_pnl': metrics.daily_pnl}
            ))
        
        # Error rate alert
        if metrics.error_rate > self.thresholds['error_rate_warning']:
            alerts_to_send.append(self._create_alert(
                severity='warning',
                title='High Error Rate',
                message=f"Error rate exceeded threshold: {metrics.error_rate:.2%}",
                component='system',
                details={'error_rate': metrics.error_rate}
            ))
        
        # Latency alert
        if metrics.latency_ms > self.thresholds['latency_warning_ms']:
            alerts_to_send.append(self._create_alert(
                severity='warning',
                title='High Latency',
                message=f"System latency is high: {metrics.latency_ms:.0f}ms",
                component='system',
                details={'latency_ms': metrics.latency_ms}
            ))
        
        # Send alerts
        for alert in alerts_to_send:
            self._send_alert(alert)
    
    def _create_alert(self, severity: str, title: str, message: str, 
                      component: str, details: Dict) -> Alert:
        """Create an alert object."""
        alert_id = f"{severity}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{component}"
        return Alert(
            id=alert_id,
            timestamp=datetime.utcnow(),
            severity=severity,
            title=title,
            message=message,
            component=component,
            details=details
        )
    
    def _send_alert(self, alert: Alert):
        """Send alert through configured channels."""
        self.alerts.append(alert)
        
        # Call registered handlers
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")
        
        # Log alert
        logger.warning(f"ALERT [{alert.severity.upper()}]: {alert.title} - {alert.message}")
    
    def register_alert_handler(self, handler: callable):
        """Register a callback for alerts."""
        self.alert_handlers.append(handler)
    
    def get_current_metrics(self) -> Optional[LiveMetrics]:
        """Get the latest metrics."""
        return self.metrics_history[-1] if self.metrics_history else None
    
    def get_metrics_history(self, hours: int = 24) -> List[LiveMetrics]:
        """Get metrics history for specified period."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [m for m in self.metrics_history if m.timestamp >= cutoff]
    
    def get_alerts(self, hours: int = 24, severity: Optional[str] = None) -> List[Alert]:
        """Get recent alerts."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        alerts = [a for a in self.alerts if a.timestamp >= cutoff]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return alerts
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate dashboard summary."""
        current = self.get_current_metrics()
        if not current:
            return {'status': 'no_data'}
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'healthy' if current.circuit_breaker_state == 'NORMAL' else 'degraded',
            'metrics': current.to_dict(),
            'recent_alerts': len(self.get_alerts(hours=24)),
            'system_health': {
                'latency_ok': current.latency_ms < self.thresholds['latency_warning_ms'],
                'error_rate_ok': current.error_rate < self.thresholds['error_rate_warning'],
                'drawdown_ok': current.current_drawdown < self.thresholds['drawdown_warning'],
                'circuit_breaker': current.circuit_breaker_state
            }
        }
    
    # Helper methods - these would be implemented based on actual system structure
    def _calculate_daily_pnl(self, db) -> float:
        """Calculate daily PnL."""
        # Implementation depends on database schema
        return 0.0
    
    def _calculate_period_pnl(self, db, days: int) -> float:
        """Calculate PnL for a period."""
        return 0.0
    
    def _calculate_ytd_pnl(self, db) -> float:
        """Calculate YTD PnL."""
        return 0.0
    
    def _get_peak_equity(self, db) -> float:
        """Get peak equity value."""
        return 100000.0
    
    def _calculate_exposure(self, db) -> float:
        """Calculate current exposure."""
        return 0.0
    
    def _get_recent_returns(self, db, days: int) -> List[float]:
        """Get recent returns for VaR calculation."""
        return []
    
    def _calculate_var_cvar(self, returns: List[float], confidence: float = 0.95) -> Tuple[float, float]:
        """Calculate VaR and CVaR."""
        if not returns:
            return 0.0, 0.0
        series = pd.Series(returns)
        var = series.quantile(1 - confidence)
        cvar = series[series <= var].mean() if len(series[series <= var]) > 0 else var
        return var, cvar
    
    def _get_max_drawdown(self, db) -> float:
        """Get maximum historical drawdown."""
        return 0.0
    
    def _get_recent_trades(self, db, days: int) -> List[Dict]:
        """Get recent trades."""
        return []
    
    def _calculate_performance_metrics(self, trades: List[Dict]) -> Tuple[float, float, float, float]:
        """Calculate Sharpe, Sortino, win rate, and profit factor."""
        if not trades:
            return 0.0, 0.0, 0.0, 0.0
        
        # Calculate returns
        returns = [t.get('pnl', 0) / t.get('value', 1) for t in trades if t.get('value', 0) > 0]
        if not returns:
            return 0.0, 0.0, 0.0, 0.0
        
        series = pd.Series(returns)
        
        # Sharpe ratio (annualized)
        sharpe = (series.mean() / series.std()) * (252 ** 0.5) if series.std() > 0 else 0.0
        
        # Sortino ratio
        downside = series[series < 0]
        sortino = (series.mean() / downside.std()) * (252 ** 0.5) if len(downside) > 0 and downside.std() > 0 else 0.0
        
        # Win rate
        wins = len(series[series > 0])
        win_rate = wins / len(series) if len(series) > 0 else 0.0
        
        # Profit factor
        gross_profit = series[series > 0].sum()
        gross_loss = abs(series[series < 0].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        return sharpe, sortino, win_rate, min(profit_factor, 10.0)
    
    def _measure_latency(self) -> float:
        """Measure system latency."""
        # Placeholder - would measure actual API response times
        return 50.0
    
    def _calculate_error_rate(self) -> float:
        """Calculate recent error rate."""
        # Placeholder - would calculate from error logs
        return 0.01
    
    def _calculate_uptime(self) -> float:
        """Calculate system uptime percentage."""
        # Placeholder - would calculate from health checks
        return 99.9


def run_dashboard(config: Optional[Dict] = None):
    """Run the live dashboard."""
    dashboard = LiveDashboard(config)
    
    logger.info("Starting live dashboard...")
    
    import time
    while True:
        try:
            metrics = dashboard.update()
            logger.info(f"Dashboard updated - Equity: ${metrics.equity:,.2f}, "
                       f"Daily PnL: {metrics.daily_pnl:.2%}, "
                       f"Drawdown: {metrics.current_drawdown:.2%}")
            time.sleep(dashboard.update_interval_seconds)
        except KeyboardInterrupt:
            logger.info("Dashboard stopped by user")
            break
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            time.sleep(60)  # Wait before retrying


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Live Trading Dashboard")
    parser.add_argument('--config', type=str, help='Config file path')
    parser.add_argument('--interval', type=int, default=60, help='Update interval in seconds')
    args = parser.parse_args()
    
    config = {}
    if args.config:
        with open(args.config) as f:
            config = json.load(f)
    config['update_interval_seconds'] = args.interval
    
    run_dashboard(config)
