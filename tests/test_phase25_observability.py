"""
Unit tests for Phase 25 Observability.
"""

import sys
sys.path.insert(0, '/workspace')

import unittest
import json
import tempfile
import os
from datetime import datetime

from observability.logger import LoggerFactory, LogContext
from observability.metrics import get_metrics_manager
from observability.audit import AuditLogger
from observability.alerts import Alert, AlertManager, AlertSeverity, AlertChannel


class TestLogger(unittest.TestCase):
    
    def test_logger_creation(self):
        logger = LoggerFactory.get_logger('test', 'test')
        self.assertIsNotNone(logger)
    
    def test_log_context(self):
        logger = LoggerFactory.get_logger('test_ctx')
        with LogContext(logger, request_id='test-123'):
            logger.info("Test message")
        # No assertion needed - just verify it runs
    
    def test_specialized_loggers(self):
        trading_logger = LoggerFactory.get_trading_logger()
        risk_logger = LoggerFactory.get_risk_logger()
        execution_logger = LoggerFactory.get_execution_logger()
        api_logger = LoggerFactory.get_api_logger()
        system_logger = LoggerFactory.get_system_logger()
        
        self.assertIsNotNone(trading_logger)
        self.assertIsNotNone(risk_logger)
        self.assertIsNotNone(execution_logger)
        self.assertIsNotNone(api_logger)
        self.assertIsNotNone(system_logger)


class TestMetrics(unittest.TestCase):
    
    def test_metrics_recording(self):
        metrics = get_metrics_manager()
        metrics.record_trade('BTC/USDT', 'buy', 'test', 1.0, 50000.0, 1000.0)
        metrics.update_risk(-0.05, 100000.0, 0.5, -5000.0, -0.10)
        metrics.update_system(True)
        # No assertion - just verify it runs
    
    def test_metrics_export(self):
        metrics = get_metrics_manager()
        data = metrics.get_all_metrics()
        self.assertIsNotNone(data)
        self.assertGreater(len(data), 0)
    
    def test_latency_recording(self):
        metrics = get_metrics_manager()
        metrics.record_latency('execution', 0.05)
        metrics.record_latency('decision', 0.02)
        metrics.record_latency('api', 0.01)
        # No assertion - just verify it runs
    
    def test_component_status(self):
        metrics = get_metrics_manager()
        metrics.update_component('database', True)
        metrics.update_component('exchange', False)
        # No assertion - just verify it runs


class TestAudit(unittest.TestCase):
    
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()
        self.audit = AuditLogger(self.db_path)
    
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_audit_log(self):
        result = self.audit.log(
            event_type='test',
            component='test',
            action='test_action',
            details={'key': 'value'}
        )
        self.assertTrue(result)
    
    def test_audit_query(self):
        self.audit.log('test', 'test', 'action1', {'key': 'value1'})
        self.audit.log('test', 'test', 'action2', {'key': 'value2'})
        
        events = self.audit.query(limit=10)
        self.assertEqual(len(events), 2)
    
    def test_audit_get_recent(self):
        for i in range(5):
            self.audit.log('test', 'test', f'action{i}', {'index': i})
        
        recent = self.audit.get_recent(limit=3)
        self.assertEqual(len(recent), 3)
    
    def test_audit_count_by_type(self):
        self.audit.log('type1', 'test', 'action1', {})
        self.audit.log('type1', 'test', 'action2', {})
        self.audit.log('type2', 'test', 'action3', {})
        
        count1 = self.audit.count_by_type('type1')
        count2 = self.audit.count_by_type('type2')
        
        self.assertEqual(count1, 2)
        self.assertEqual(count2, 1)
    
    def test_audit_context_manager(self):
        from observability.audit import AuditContext
        
        with AuditContext(self.audit, 'test_event', 'test_comp', 'test_action') as ctx:
            ctx.set_details(key='value')
        
        events = self.audit.query(event_type='test_event', limit=1)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['details']['key'], 'value')


class TestAlerts(unittest.TestCase):
    
    def test_alert_creation(self):
        alert = Alert(
            severity=AlertSeverity.WARNING,
            title="Test Alert",
            message="This is a test alert",
            component="test"
        )
        self.assertEqual(alert.severity, AlertSeverity.WARNING)
        self.assertEqual(alert.title, "Test Alert")
        self.assertEqual(alert.component, "test")
    
    def test_alert_to_dict(self):
        alert = Alert(
            severity=AlertSeverity.INFO,
            title="Test",
            message="Test message",
            component="test",
            details={'key': 'value'}
        )
        alert_dict = alert.to_dict()
        
        self.assertIn('id', alert_dict)
        self.assertEqual(alert_dict['severity'], AlertSeverity.INFO)
        self.assertEqual(alert_dict['title'], "Test")
        self.assertEqual(alert_dict['details']['key'], 'value')
    
    def test_alert_manager_disabled(self):
        manager = AlertManager({
            'enabled': False  # Disable for tests
        })
        alert = Alert(AlertSeverity.INFO, "Test", "Test message", "test")
        result = manager.send_alert(alert)
        self.assertTrue(result)
    
    def test_alert_severity_threshold(self):
        manager = AlertManager({
            'enabled': False,
            'min_severity': 'warning'
        })
        
        # Info should not pass threshold
        self.assertFalse(manager._should_send(AlertSeverity.INFO))
        
        # Warning and above should pass
        self.assertTrue(manager._should_send(AlertSeverity.WARNING))
        self.assertTrue(manager._should_send(AlertSeverity.CRITICAL))
        self.assertTrue(manager._should_send(AlertSeverity.EMERGENCY))
    
    def test_alert_templates(self):
        from observability.alerts import AlertTemplates
        
        trade_alert = AlertTemplates.trade_success({'symbol': 'BTC/USDT', 'side': 'buy', 'amount': 1.0})
        self.assertEqual(trade_alert.severity, AlertSeverity.INFO)
        
        failure_alert = AlertTemplates.trade_failure('Error', {'symbol': 'BTC/USDT'})
        self.assertEqual(failure_alert.severity, AlertSeverity.WARNING)
        
        risk_alert = AlertTemplates.risk_breach({'reason': 'Drawdown exceeded'})
        self.assertEqual(risk_alert.severity, AlertSeverity.CRITICAL)
        
        kill_alert = AlertTemplates.kill_switch_triggered('Manual trigger', {})
        self.assertEqual(kill_alert.severity, AlertSeverity.EMERGENCY)
        
        health_alert = AlertTemplates.system_health_check_failed('database', 'Connection failed')
        self.assertEqual(health_alert.severity, AlertSeverity.WARNING)


if __name__ == '__main__':
    unittest.main()
