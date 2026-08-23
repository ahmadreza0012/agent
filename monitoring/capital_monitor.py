"""
Capital Preservation Monitoring Module
=======================================
Real-time monitoring for capital preservation.

This module provides continuous monitoring of capital preservation status,
generating alerts and recommendations when risk thresholds are breached.

Components:
- CapitalMonitor: Real-time capital monitoring
- AlertSystem: Alert generation and management
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class CapitalMonitor:
    """
    Monitor capital preservation status in real-time.
    
    This monitor continuously tracks:
    - Drawdown levels
    - Daily losses
    - Cash ratios
    - Position concentrations
    - Market conditions
    
    It generates alerts and recommendations based on configurable thresholds.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.alert_thresholds = {
            'drawdown_warning': self.config.get('drawdown_warning', 0.10),
            'drawdown_danger': self.config.get('drawdown_danger', 0.15),
            'drawdown_critical': self.config.get('drawdown_critical', 0.20),
            'drawdown_ruin': self.config.get('drawdown_ruin', 0.25),
            'daily_loss_warning': self.config.get('daily_loss_warning', 0.03),
            'daily_loss_danger': self.config.get('daily_loss_danger', 0.05),
            'cash_low_warning': self.config.get('cash_low_warning', 0.05),
            'cash_low_danger': self.config.get('cash_low_danger', 0.03),
        }
        self.alerts = []
        self.history = []
        
    def monitor(
        self,
        capital: Dict[str, float],
        positions: List[Dict],
        market_data: pd.DataFrame
    ) -> Dict:
        """
        Monitor capital preservation status.
        
        Args:
            capital: Current capital metrics
            positions: List of current positions
            market_data: Market data for analysis
        
        Returns:
            Monitoring status and alerts
        """
        status = {
            'timestamp': datetime.now(),
            'capital': capital,
            'positions': positions,
            'status': 'SAFE',
            'alerts': [],
            'recommendations': [],
        }
        
        # Check drawdown
        drawdown = capital.get('current_drawdown', 0)
        if drawdown >= self.alert_thresholds['drawdown_ruin']:
            status['status'] = 'RUIN'
            status['alerts'].append(f"RUIN: Drawdown {drawdown:.1%}")
            status['recommendations'].append("STOP ALL TRADING")
        elif drawdown >= self.alert_thresholds['drawdown_critical']:
            status['status'] = 'CRITICAL'
            status['alerts'].append(f"CRITICAL: Drawdown {drawdown:.1%}")
            status['recommendations'].append("REDUCE EXPOSURE 75%")
        elif drawdown >= self.alert_thresholds['drawdown_danger']:
            status['status'] = 'DANGER'
            status['alerts'].append(f"DANGER: Drawdown {drawdown:.1%}")
            status['recommendations'].append("REDUCE EXPOSURE 50%")
        elif drawdown >= self.alert_thresholds['drawdown_warning']:
            status['status'] = 'WARNING'
            status['alerts'].append(f"WARNING: Drawdown {drawdown:.1%}")
            status['recommendations'].append("REDUCE EXPOSURE 25%")
        
        # Check daily loss
        daily_loss = capital.get('daily_loss', 0)
        if daily_loss >= self.alert_thresholds['daily_loss_danger']:
            status['alerts'].append(f"Daily loss {daily_loss:.1%} exceeds danger threshold")
            status['recommendations'].append("HALT TRADING FOR DAY")
        elif daily_loss >= self.alert_thresholds['daily_loss_warning']:
            status['alerts'].append(f"Daily loss {daily_loss:.1%} exceeds warning threshold")
            status['recommendations'].append("REDUCE POSITION SIZING")
        
        # Check cash ratio
        cash_ratio = capital.get('cash_ratio', 0)
        if cash_ratio < self.alert_thresholds['cash_low_danger']:
            status['alerts'].append(f"Cash ratio {cash_ratio:.1%} critically low")
            status['recommendations'].append("SELL ASSETS IMMEDIATELY")
        elif cash_ratio < self.alert_thresholds['cash_low_warning']:
            status['alerts'].append(f"Cash ratio {cash_ratio:.1%} low")
            status['recommendations'].append("REDUCE POSITIONS")
        
        # Check position concentration
        max_position = capital.get('max_position_size', 0)
        if max_position > 0.30:
            status['alerts'].append(f"Position concentration {max_position:.1%} too high")
            status['recommendations'].append("DIVERSIFY POSITIONS")
        
        # Store history
        self.history.append(status)
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
        
        # Record alerts
        if status['alerts']:
            self.alerts.extend(status['alerts'])
            logger.warning(f"CAPITAL MONITOR: {status['status']} - {status['alerts']}")
        
        return status
    
    def get_summary(self) -> Dict:
        """Get monitoring summary."""
        if not self.history:
            return {'status': 'NO_DATA'}
        
        latest = self.history[-1]
        return {
            'latest_status': latest['status'],
            'total_alerts': len(self.alerts),
            'recent_alerts': self.alerts[-5:] if self.alerts else [],
            'history_count': len(self.history),
            'recommendations': latest['recommendations'],
        }
    
    def get_history_df(self) -> pd.DataFrame:
        """Get monitoring history as DataFrame."""
        if not self.history:
            return pd.DataFrame()
        
        records = []
        for h in self.history:
            record = {
                'timestamp': h['timestamp'],
                'status': h['status'],
                'alert_count': len(h['alerts']),
                'drawdown': h['capital'].get('current_drawdown', 0),
                'daily_loss': h['capital'].get('daily_loss', 0),
                'cash_ratio': h['capital'].get('cash_ratio', 0),
            }
            records.append(record)
        
        return pd.DataFrame(records)
    
    def generate_report(self) -> str:
        """Generate a monitoring report."""
        summary = self.get_summary()
        
        lines = [
            "=" * 80,
            "CAPITAL PRESERVATION MONITOR REPORT",
            "=" * 80,
            "",
            f"Latest Status: {summary['latest_status']}",
            f"Total Alerts: {summary['total_alerts']}",
            f"History Records: {summary['history_count']}",
            "",
            "RECENT ALERTS:",
            "-" * 40,
        ]
        
        for alert in summary['recent_alerts']:
            lines.append(f"• {alert}")
        
        if not summary['recent_alerts']:
            lines.append("No recent alerts")
        
        lines.extend([
            "",
            "RECOMMENDATIONS:",
            "-" * 40,
        ])
        
        for rec in summary['recommendations']:
            lines.append(f"• {rec}")
        
        if not summary['recommendations']:
            lines.append("No immediate recommendations - continue normal operations")
        
        lines.extend([
            "",
            "=" * 80,
        ])
        
        return "\n".join(lines)
    
    def clear_alerts(self):
        """Clear all recorded alerts."""
        self.alerts = []
        logger.info("Capital monitor alerts cleared")


class AlertSystem:
    """
    System for managing and distributing capital preservation alerts.
    
    This system can:
    - Generate alerts with severity levels
    - Track alert history
    - Send notifications (extensible)
    - Aggregate alerts for reporting
    """
    
    def __init__(self):
        self.alerts = []
        self.subscribers = []
        
    def subscribe(self, callback):
        """Subscribe to receive alerts."""
        self.subscribers.append(callback)
        
    def unsubscribe(self, callback):
        """Unsubscribe from alerts."""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
    
    def send_alert(
        self,
        level: str,
        message: str,
        source: str = "capital_monitor",
        metadata: Dict = None
    ):
        """
        Send an alert to all subscribers.
        
        Args:
            level: Alert level (INFO, WARNING, DANGER, CRITICAL)
            message: Alert message
            source: Source of the alert
            metadata: Additional metadata
        """
        alert = {
            'timestamp': datetime.now(),
            'level': level,
            'message': message,
            'source': source,
            'metadata': metadata or {},
        }
        
        self.alerts.append(alert)
        
        # Notify subscribers
        for subscriber in self.subscribers:
            try:
                subscriber(alert)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}")
        
        # Log alert
        log_func = logger.info
        if level == 'WARNING':
            log_func = logger.warning
        elif level in ['DANGER', 'CRITICAL']:
            log_func = logger.critical
        
        log_func(f"ALERT [{level}]: {message}")
    
    def get_recent_alerts(self, count: int = 10, level: str = None) -> List[Dict]:
        """Get recent alerts, optionally filtered by level."""
        alerts = self.alerts[-count*2:]  # Get extra to filter
        
        if level:
            alerts = [a for a in alerts if a['level'] == level]
        
        return alerts[-count:]
    
    def get_alert_summary(self) -> Dict:
        """Get summary of alerts."""
        if not self.alerts:
            return {'total': 0}
        
        by_level = {}
        for alert in self.alerts:
            level = alert['level']
            by_level[level] = by_level.get(level, 0) + 1
        
        return {
            'total': len(self.alerts),
            'by_level': by_level,
            'latest': self.alerts[-1] if self.alerts else None,
            'oldest': self.alerts[0] if self.alerts else None,
        }
    
    def clear_old_alerts(self, days: int = 7):
        """Clear alerts older than specified days."""
        cutoff = datetime.now() - timedelta(days=days)
        self.alerts = [a for a in self.alerts if a['timestamp'] > cutoff]
        logger.info(f"Cleared alerts older than {days} days")
