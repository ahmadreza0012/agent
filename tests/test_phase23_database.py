"""
Unit tests for Phase 23 Database.

Tests database manager, repositories, and migration service.
"""

import sys
sys.path.insert(0, '/workspace')

import unittest
import tempfile
import os
from datetime import datetime, timedelta

from database.database_manager import DatabaseManager
from database.repositories.order_repository import OrderRepository
from database.repositories.trade_repository import TradeRepository
from database.repositories.performance_repository import PerformanceRepository
from database.repositories.risk_event_repository import RiskEventRepository
from database.migrations import MigrationService


class TestDatabaseManager(unittest.TestCase):
    """Test DatabaseManager functionality."""
    
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()
        
        self.db_manager = DatabaseManager({
            'type': 'sqlite',
            'path': self.db_path
        })
    
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_health_check(self):
        """Test database health check."""
        self.assertTrue(self.db_manager.health_check())
    
    def test_execute_select(self):
        """Test executing a SELECT query."""
        # Create a test table
        self.db_manager.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
        self.db_manager.execute("INSERT INTO test (value) VALUES ('test_value')")
        
        # Query the table
        result = self.db_manager.execute("SELECT * FROM test")
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['value'], 'test_value')
    
    def test_execute_transaction(self):
        """Test transaction execution."""
        # Create a test table
        self.db_manager.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
        
        # Execute transaction
        operations = [
            ("INSERT INTO test (value) VALUES (?)", ('value1',)),
            ("INSERT INTO test (value) VALUES (?)", ('value2',)),
        ]
        
        result = self.db_manager.execute_transaction(operations)
        self.assertTrue(result)
        
        # Verify
        results = self.db_manager.execute("SELECT * FROM test")
        self.assertEqual(len(results), 2)
    
    def test_execute_many(self):
        """Test batch execution."""
        self.db_manager.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
        
        params_list = [
            ('batch1',),
            ('batch2',),
            ('batch3',),
        ]
        
        count = self.db_manager.execute_many("INSERT INTO test (value) VALUES (?)", params_list)
        self.assertEqual(count, 3)
        
        results = self.db_manager.execute("SELECT * FROM test")
        self.assertEqual(len(results), 3)


class TestOrderRepository(unittest.TestCase):
    """Test OrderRepository functionality."""
    
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()
        
        self.db_manager = DatabaseManager({
            'type': 'sqlite',
            'path': self.db_path
        })
        
        # Initialize schema
        self.migration = MigrationService(self.db_manager)
        self.migration.initialize_schema()
        
        self.repo = OrderRepository(self.db_manager)
    
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_create_order(self):
        """Test creating an order."""
        order_data = {
            'order_id': 'test_123',
            'client_order_id': 'client_123',
            'symbol': 'BTC/USDT',
            'side': 'buy',
            'order_type': 'market',
            'price': 50000.0,
            'amount': 0.1,
            'filled_amount': 0.1,
            'status': 'filled',
            'fee': 5.0,
            'fee_currency': 'USDT',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        created = self.repo.create_order(order_data)
        self.assertIsNotNone(created)
        self.assertEqual(created['order_id'], 'test_123')
    
    def test_get_by_order_id(self):
        """Test getting order by exchange order ID."""
        order_data = {
            'order_id': 'test_456',
            'client_order_id': 'client_456',
            'symbol': 'ETH/USDT',
            'side': 'sell',
            'order_type': 'limit',
            'price': 3000.0,
            'amount': 1.0,
            'filled_amount': 0.0,
            'status': 'open',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        self.repo.create_order(order_data)
        
        found = self.repo.get_by_order_id('test_456')
        self.assertIsNotNone(found)
        self.assertEqual(found['symbol'], 'ETH/USDT')
    
    def test_get_by_client_id(self):
        """Test getting order by client order ID."""
        order_data = {
            'order_id': 'test_789',
            'client_order_id': 'client_789',
            'symbol': 'BTC/USDT',
            'side': 'buy',
            'order_type': 'market',
            'price': 50000.0,
            'amount': 0.1,
            'filled_amount': 0.1,
            'status': 'filled',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        self.repo.create_order(order_data)
        
        found = self.repo.get_by_client_id('client_789')
        self.assertIsNotNone(found)
        self.assertEqual(found['order_id'], 'test_789')
    
    def test_update_status(self):
        """Test updating order status."""
        order_data = {
            'order_id': 'test_update',
            'client_order_id': 'client_update',
            'symbol': 'BTC/USDT',
            'side': 'buy',
            'order_type': 'market',
            'price': 50000.0,
            'amount': 0.1,
            'filled_amount': 0.0,
            'status': 'open',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        self.repo.create_order(order_data)
        
        updated = self.repo.update_status('test_update', 'cancelled')
        self.assertIsNotNone(updated)
        self.assertEqual(updated['status'], 'cancelled')
    
    def test_get_open_orders(self):
        """Test getting open orders."""
        # Create multiple orders
        for i in range(3):
            order_data = {
                'order_id': f'open_{i}',
                'client_order_id': f'client_open_{i}',
                'symbol': 'BTC/USDT',
                'side': 'buy',
                'order_type': 'limit',
                'price': 50000.0,
                'amount': 0.1,
                'filled_amount': 0.0,
                'status': 'open',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            self.repo.create_order(order_data)
        
        open_orders = self.repo.get_open_orders()
        self.assertEqual(len(open_orders), 3)


class TestTradeRepository(unittest.TestCase):
    """Test TradeRepository functionality."""
    
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()
        
        self.db_manager = DatabaseManager({
            'type': 'sqlite',
            'path': self.db_path
        })
        
        # Initialize schema
        self.migration = MigrationService(self.db_manager)
        self.migration.initialize_schema()
        
        self.repo = TradeRepository(self.db_manager)
    
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_create_trade(self):
        """Test creating a trade."""
        trade_data = {
            'order_id': 'test_123',
            'symbol': 'BTC/USDT',
            'side': 'buy',
            'price': 50000.0,
            'amount': 0.1,
            'fee': 5.0,
            'fee_currency': 'USDT',
            'exchange_id': 'exchange_123',
            'timestamp': datetime.now().isoformat()
        }
        
        created = self.repo.create_trade(trade_data)
        self.assertIsNotNone(created)
    
    def test_get_by_order_id(self):
        """Test getting trades by order ID."""
        trade_data = {
            'order_id': 'test_order',
            'symbol': 'BTC/USDT',
            'side': 'buy',
            'price': 50000.0,
            'amount': 0.1,
            'fee': 5.0,
            'fee_currency': 'USDT',
            'exchange_id': 'ex_1',
            'timestamp': datetime.now().isoformat()
        }
        
        self.repo.create_trade(trade_data)
        
        trades = self.repo.get_by_order_id('test_order')
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]['symbol'], 'BTC/USDT')


class TestPerformanceRepository(unittest.TestCase):
    """Test PerformanceRepository functionality."""
    
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()
        
        self.db_manager = DatabaseManager({
            'type': 'sqlite',
            'path': self.db_path
        })
        
        # Initialize schema
        self.migration = MigrationService(self.db_manager)
        self.migration.initialize_schema()
        
        self.repo = PerformanceRepository(self.db_manager)
    
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_create_metrics(self):
        """Test creating performance metrics."""
        perf_data = {
            'timestamp': datetime.now().isoformat(),
            'period_start': datetime.now().isoformat(),
            'period_end': datetime.now().isoformat(),
            'returns': 0.05,
            'volatility': 0.02,
            'sharpe': 2.5,
            'drawdown': -0.03,
            'turnover': 0.5,
            'fees': 0.01,
            'slippage': 0.005
        }
        
        created = self.repo.create_metrics(perf_data)
        self.assertIsNotNone(created)
    
    def test_get_daily_performance(self):
        """Test getting daily performance."""
        # Create some metrics
        for i in range(3):
            perf_data = {
                'timestamp': (datetime.now() - timedelta(days=i)).isoformat(),
                'period_start': (datetime.now() - timedelta(days=i)).isoformat(),
                'period_end': datetime.now().isoformat(),
                'returns': 0.01 * i,
                'volatility': 0.02,
                'sharpe': 1.5 + i,
                'drawdown': -0.01,
                'turnover': 0.3,
                'fees': 0.005,
                'slippage': 0.002
            }
            self.repo.create_metrics(perf_data)
        
        daily = self.repo.get_daily_performance(7)
        self.assertEqual(len(daily), 3)


class TestRiskEventRepository(unittest.TestCase):
    """Test RiskEventRepository functionality."""
    
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()
        
        self.db_manager = DatabaseManager({
            'type': 'sqlite',
            'path': self.db_path
        })
        
        # Initialize schema
        self.migration = MigrationService(self.db_manager)
        self.migration.initialize_schema()
        
        self.repo = RiskEventRepository(self.db_manager)
    
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_create_event(self):
        """Test creating a risk event."""
        event_data = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'drawdown_warning',
            'severity': 'warning',
            'description': 'Drawdown exceeded soft limit',
            'details': '{"drawdown": -0.12, "limit": -0.10}'
        }
        
        created = self.repo.create_event(event_data)
        self.assertIsNotNone(created)
    
    def test_get_unresolved(self):
        """Test getting unresolved events."""
        # Create resolved and unresolved events
        event1 = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'loss_limit',
            'severity': 'critical',
            'description': 'Daily loss limit breached',
            'details': '{}',
            'resolved_at': None,
            'resolved_by': None
        }
        
        event2 = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'reconciliation',
            'severity': 'warning',
            'description': 'Position mismatch detected',
            'details': '{}',
            'resolved_at': datetime.now().isoformat(),
            'resolved_by': 'system'
        }
        
        self.repo.create_event(event1)
        self.repo.create_event(event2)
        
        unresolved = self.repo.get_unresolved()
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0]['severity'], 'critical')
    
    def test_resolve_event(self):
        """Test resolving an event."""
        event_data = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'test_event',
            'severity': 'warning',
            'description': 'Test event',
            'details': '{}'
        }
        
        created = self.repo.create_event(event_data)
        self.assertIsNone(created['resolved_at'])
        
        resolved = self.repo.resolve_event(created['id'], 'test_user')
        self.assertIsNotNone(resolved['resolved_at'])
        self.assertEqual(resolved['resolved_by'], 'test_user')


class TestMigrationService(unittest.TestCase):
    """Test MigrationService functionality."""
    
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()
        
        self.db_manager = DatabaseManager({
            'type': 'sqlite',
            'path': self.db_path
        })
        
        self.migration = MigrationService(self.db_manager)
    
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_initialize_schema(self):
        """Test schema initialization."""
        result = self.migration.initialize_schema()
        self.assertTrue(result)
        
        current = self.migration.get_current_version()
        self.assertEqual(current, '1.0.5')
    
    def test_migration_tracking(self):
        """Test migration version tracking."""
        self.migration.initialize_schema()
        
        applied = self.migration.get_applied_migrations()
        self.assertEqual(len(applied), 6)  # 6 migrations
        
        # Check specific versions
        self.assertTrue(self.migration.is_migration_applied('1.0.0'))
        self.assertTrue(self.migration.is_migration_applied('1.0.5'))
        self.assertFalse(self.migration.is_migration_applied('2.0.0'))


if __name__ == '__main__':
    unittest.main()
