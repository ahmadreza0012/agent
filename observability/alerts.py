"""
Alert Manager - Send alerts for critical events.
"""

import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import logging
import json
import os

logger = logging.getLogger(__name__)


class AlertSeverity:
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertChannel:
    """Alert channel types."""
    SLACK = "slack"
    TELEGRAM = "telegram"
    EMAIL = "email"
    PAGERDUTY = "pagerduty"
    WEBHOOK = "webhook"


class Alert:
    """Alert data structure."""
    
    def __init__(self, severity: str, title: str, message: str,
                 component: str, details: Optional[Dict] = None):
        self.severity = severity
        self.title = title
        self.message = message
        self.component = component
        self.details = details or {}
        self.timestamp = datetime.now()
        self.id = f"{severity}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{component}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'severity': self.severity,
            'title': self.title,
            'message': self.message,
            'component': self.component,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }


class AlertManager:
    """
    Central alert manager.
    
    Supports multiple channels:
    - Slack
    - Telegram
    - Email
    - PagerDuty
    - Custom webhooks
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._handlers: Dict[str, List[Callable]] = {}
        self._channels = self.config.get('channels', {})
        self._enabled = self.config.get('enabled', True)
        self._min_severity = self.config.get('min_severity', 'warning')
    
    def send_alert(self, alert: Alert) -> bool:
        """Send an alert through all configured channels."""
        if not self._enabled:
            logger.info(f"Alert manager disabled - would send: {alert.title}")
            return True
        
        # Check if severity meets threshold
        if not self._should_send(alert.severity):
            return False
        
        success = True
        for channel, config in self._channels.items():
            if config.get('enabled', True):
                try:
                    self._send_to_channel(channel, alert, config)
                    logger.info(f"Alert sent to {channel}: {alert.id}")
                except Exception as e:
                    logger.error(f"Failed to send alert to {channel}: {e}")
                    success = False
        
        return success
    
    def _should_send(self, severity: str) -> bool:
        """Check if severity meets threshold."""
        levels = ['info', 'warning', 'critical', 'emergency']
        return levels.index(severity) >= levels.index(self._min_severity)
    
    def _send_to_channel(self, channel: str, alert: Alert, config: Dict):
        """Send alert to a specific channel."""
        if channel == AlertChannel.SLACK:
            self._send_slack(alert, config)
        elif channel == AlertChannel.TELEGRAM:
            self._send_telegram(alert, config)
        elif channel == AlertChannel.EMAIL:
            self._send_email(alert, config)
        elif channel == AlertChannel.PAGERDUTY:
            self._send_pagerduty(alert, config)
        elif channel == AlertChannel.WEBHOOK:
            self._send_webhook(alert, config)
    
    def _send_slack(self, alert: Alert, config: Dict):
        """Send alert to Slack."""
        webhook_url = config.get('webhook_url')
        if not webhook_url:
            raise ValueError("Slack webhook URL required")
        
        color = self._get_slack_color(alert.severity)
        message = {
            'attachments': [{
                'color': color,
                'title': f"[{alert.severity.upper()}] {alert.title}",
                'text': alert.message,
                'fields': [
                    {'title': 'Component', 'value': alert.component, 'short': True},
                    {'title': 'Time', 'value': alert.timestamp.isoformat(), 'short': True},
                ],
                'footer': f"Alert ID: {alert.id}"
            }]
        }
        
        if alert.details:
            message['attachments'][0]['fields'].append({
                'title': 'Details',
                'value': json.dumps(alert.details, indent=2),
                'short': False
            })
        
        response = requests.post(webhook_url, json=message, timeout=10)
        response.raise_for_status()
    
    def _send_telegram(self, alert: Alert, config: Dict):
        """Send alert to Telegram."""
        bot_token = config.get('bot_token')
        chat_id = config.get('chat_id')
        if not bot_token or not chat_id:
            raise ValueError("Telegram bot token and chat ID required")
        
        message_text = (
            f"🔔 *{alert.severity.upper()}*: {alert.title}\n"
            f"{alert.message}\n\n"
            f"Component: {alert.component}\n"
            f"Time: {alert.timestamp.isoformat()}\n"
            f"ID: `{alert.id}`"
        )
        
        if alert.details:
            message_text += f"\n\nDetails:\n```\n{json.dumps(alert.details, indent=2)}\n```"
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        response = requests.post(url, json={
            'chat_id': chat_id,
            'text': message_text,
            'parse_mode': 'Markdown'
        }, timeout=10)
        response.raise_for_status()
    
    def _send_email(self, alert: Alert, config: Dict):
        """Send alert via email."""
        smtp_server = config.get('smtp_server')
        smtp_port = config.get('smtp_port', 587)
        username = config.get('username')
        password = config.get('password')
        to_email = config.get('to_email')
        from_email = config.get('from_email')
        
        if not all([smtp_server, username, password, to_email, from_email]):
            raise ValueError("Email configuration incomplete")
        
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = f"[{alert.severity.upper()}] {alert.title}"
        
        body = f"""
        Alert: {alert.title}
        Severity: {alert.severity}
        Component: {alert.component}
        Time: {alert.timestamp.isoformat()}
        
        Message: {alert.message}
        
        Details:
        {json.dumps(alert.details, indent=2)}
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(msg)
    
    def _send_pagerduty(self, alert: Alert, config: Dict):
        """Send alert to PagerDuty."""
        service_key = config.get('service_key')
        if not service_key:
            raise ValueError("PagerDuty service key required")
        
        data = {
            'service_key': service_key,
            'event_type': 'trigger',
            'description': f"[{alert.severity.upper()}] {alert.title}",
            'details': alert.to_dict()
        }
        
        response = requests.post(
            'https://events.pagerduty.com/generic/2010-04-15/create_event.json',
            json=data,
            timeout=10
        )
        response.raise_for_status()
    
    def _send_webhook(self, alert: Alert, config: Dict):
        """Send alert to custom webhook."""
        webhook_url = config.get('webhook_url')
        method = config.get('method', 'POST')
        
        if not webhook_url:
            raise ValueError("Webhook URL required")
        
        response = requests.request(
            method=method,
            url=webhook_url,
            json=alert.to_dict(),
            timeout=10
        )
        response.raise_for_status()
    
    def _get_slack_color(self, severity: str) -> str:
        """Get Slack color for severity."""
        colors = {
            'info': '#36a64f',
            'warning': '#ffa500',
            'critical': '#ff0000',
            'emergency': '#8b0000'
        }
        return colors.get(severity, '#808080')


# --- Alert Templates ---
class AlertTemplates:
    """Pre-defined alert templates."""
    
    @staticmethod
    def trade_success(trade_data: Dict) -> Alert:
        return Alert(
            severity=AlertSeverity.INFO,
            title="Trade Executed",
            message=f"Trade executed: {trade_data.get('side')} {trade_data.get('amount')} {trade_data.get('symbol')}",
            component="trading",
            details=trade_data
        )
    
    @staticmethod
    def trade_failure(error: str, trade_data: Dict) -> Alert:
        return Alert(
            severity=AlertSeverity.WARNING,
            title="Trade Failed",
            message=f"Trade failed: {error}",
            component="trading",
            details={'error': error, 'trade': trade_data}
        )
    
    @staticmethod
    def risk_breach(risk_data: Dict) -> Alert:
        return Alert(
            severity=AlertSeverity.CRITICAL,
            title="Risk Limit Breach",
            message=f"Risk limit breached: {risk_data.get('reason')}",
            component="risk",
            details=risk_data
        )
    
    @staticmethod
    def kill_switch_triggered(reason: str, details: Dict) -> Alert:
        return Alert(
            severity=AlertSeverity.EMERGENCY,
            title="Kill Switch Triggered",
            message=f"Kill switch activated: {reason}",
            component="safety",
            details=details
        )
    
    @staticmethod
    def system_health_check_failed(component: str, error: str) -> Alert:
        return Alert(
            severity=AlertSeverity.WARNING,
            title="Health Check Failed",
            message=f"Health check failed for {component}: {error}",
            component="system",
            details={'component': component, 'error': error}
        )
