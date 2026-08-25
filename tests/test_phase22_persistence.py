"""
Unit tests for Phase 22 Persistence.

Tests state persistence, recovery, and atomic operations.
"""

import sys
sys.path.insert(0, '/workspace')

import unittest
import tempfile
import shutil
import os
from datetime import datetime

from persistence.persistence_manager import PersistenceManager
from persistence.trading_state_manager import TradingStateManager, TradingState
from persistence.risk_state_manager import RiskStateManager, RiskState
from persistence.circuit_breaker_state_manager import CircuitBreakerStateManager, CircuitBreakerStateEnum
from persistence.kill_switch_state_manager import KillSwitchStateManager, KillSwitchStateEnum
from persistence.state_recovery import StateRecovery


class TestPersistenceManager(unittest.TestCase):
    """Test PersistenceManager functionality."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = PersistenceManager(self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_save_and_load_state(self):
        """Test basic save and load."""
        test_data = {'key': 'value', 'number': 42}
        result = self.manager.save_state('test', test_data)
        self.assertTrue(result)
        
        loaded = self.manager.load_state('test')
        self.assertEqual(loaded, test_data)
    
    def test_load_nonexistent_state(self):
        """Test loading state that doesn't exist."""
        loaded = self.manager.load_state('nonexistent')
        self.assertIsNone(loaded)
    
    def test_backup_creation(self):
        """Test automatic backup creation."""
        self.manager.save_state('test', {'value': 1})
        self.manager.save_state('test', {'value': 2})
        
        backups = list(self.manager.backup_dir.glob('test_*.json'))
        self.assertGreater(len(backups), 0)
    
    def test_checksum_validation(self):
        """Test checksum validation on load."""
        self.manager.save_state('test', {'value': 123})
        
        # Corrupt the file
        filepath = self.manager.state_dir / 'test_state.json'
        with open(filepath, 'r') as f:
            content = f.read()
        corrupted = content.replace('"value": 123', '"value": 999')
        with open(filepath, 'w') as f:
            f.write(corrupted)
        
        # Should fail checksum validation
        loaded = self.manager.load_state('test')
        self.assertIsNone(loaded)
    
    def test_delete_state(self):
        """Test state deletion."""
        self.manager.save_state('test', {'value': 1})
        result = self.manager.delete_state('test')
        self.assertTrue(result)
        
        loaded = self.manager.load_state('test')
        self.assertIsNone(loaded)
    
    def test_health_check(self):
        """Test health check."""
        result = self.manager.health_check()
        self.assertTrue(result)
    
    def test_get_all_state(self):
        """Test getting all state."""
        self.manager.save_state('trading', {'portfolio': {'BTC': 1.0}})
        self.manager.save_state('risk', {'equity': 10000.0})
        
        all_state = self.manager.get_all_state()
        self.assertIn('trading', all_state)
        self.assertIn('risk', all_state)


class TestStateManagers(unittest.TestCase):
    """Test component-specific state managers."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.persistence = PersistenceManager(self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_trading_state_manager(self):
        """Test TradingStateManager."""
        manager = TradingStateManager(self.persistence)
        state = manager.get_default_state()
        state.portfolio = {'BTC': 1.0, 'ETH': 10.0}
        state.balances = {'USDT': 10000.0}
        manager.save(state)
        
        loaded = manager.load()
        self.assertEqual(loaded.portfolio, {'BTC': 1.0, 'ETH': 10.0})
        self.assertEqual(loaded.balances, {'USDT': 10000.0})
    
    def test_trading_add_position(self):
        """Test adding position to trading state."""
        manager = TradingStateManager(self.persistence)
        manager.add_position({'symbol': 'BTC/USDT', 'size': 0.5, 'entry_price': 50000.0})
        
        loaded = manager.load()
        self.assertEqual(len(loaded.positions), 1)
        self.assertEqual(loaded.positions[0]['symbol'], 'BTC/USDT')
    
    def test_risk_state_manager(self):
        """Test RiskStateManager."""
        manager = RiskStateManager(self.persistence)
        state = manager.get_default_state()
        state.current_drawdown = -0.05
        state.peak_equity = 100000.0
        state.current_equity = 95000.0
        manager.save(state)
        
        loaded = manager.load()
        self.assertEqual(loaded.current_drawdown, -0.05)
        self.assertEqual(loaded.peak_equity, 100000.0)
    
    def test_risk_update_equity(self):
        """Test equity update in risk state."""
        manager = RiskStateManager(self.persistence)
        manager.update_equity(100000.0)
        manager.update_equity(95000.0)
        
        loaded = manager.get_current()
        self.assertEqual(loaded.peak_equity, 100000.0)
        self.assertEqual(loaded.current_equity, 95000.0)
        self.assertAlmostEqual(loaded.current_drawdown, -0.05, places=4)
    
    def test_risk_set_halt(self):
        """Test setting halt state."""
        manager = RiskStateManager(self.persistence)
        manager.set_halt("Daily loss limit exceeded")
        
        loaded = manager.get_current()
        self.assertTrue(loaded.is_halted)
        self.assertEqual(loaded.halt_reason, "Daily loss limit exceeded")
    
    def test_circuit_breaker_state_manager(self):
        """Test CircuitBreakerStateManager."""
        manager = CircuitBreakerStateManager(self.persistence)
        state = manager.get_default_state()
        state.state = CircuitBreakerStateEnum.WARNING
        state.consecutive_failures = 2
        manager.save(state)
        
        loaded = manager.load()
        self.assertEqual(loaded.state, CircuitBreakerStateEnum.WARNING)
        self.assertEqual(loaded.consecutive_failures, 2)
    
    def test_circuit_breaker_transition(self):
        """Test circuit breaker state transition."""
        manager = CircuitBreakerStateManager(self.persistence)
        manager.transition_to(CircuitBreakerStateEnum.WARNING, "High volatility")
        
        loaded = manager.get_current()
        self.assertEqual(loaded.state, CircuitBreakerStateEnum.WARNING)
        self.assertEqual(len(loaded.transition_history), 1)
        self.assertEqual(loaded.transition_history[0]['to'], 'warning')
    
    def test_kill_switch_state_manager(self):
        """Test KillSwitchStateManager."""
        manager = KillSwitchStateManager(self.persistence)
        state = manager.get_default_state()
        state.level = KillSwitchStateEnum.HALT
        state.is_triggered = True
        manager.save(state)
        
        loaded = manager.load()
        self.assertEqual(loaded.level, KillSwitchStateEnum.HALT)
        self.assertTrue(loaded.is_triggered)
    
    def test_kill_switch_trigger(self):
        """Test kill switch trigger."""
        manager = KillSwitchStateManager(self.persistence)
        manager.trigger(KillSwitchStateEnum.HALT, "Maximum drawdown exceeded", "risk_engine")
        
        loaded = manager.get_current()
        self.assertTrue(loaded.is_triggered)
        self.assertEqual(loaded.level, KillSwitchStateEnum.HALT)
        self.assertEqual(loaded.trigger_reason, "Maximum drawdown exceeded")
        self.assertEqual(len(loaded.history), 1)
    
    def test_kill_switch_resolve(self):
        """Test kill switch resolve."""
        manager = KillSwitchStateManager(self.persistence)
        manager.trigger(KillSwitchStateEnum.HALT, "Test reason")
        manager.resolve("operator")
        
        loaded = manager.get_current()
        self.assertFalse(loaded.is_triggered)
        self.assertEqual(loaded.level, KillSwitchStateEnum.NORMAL)
        self.assertEqual(loaded.resolved_by, "operator")


class TestStateRecovery(unittest.TestCase):
    """Test state recovery functionality."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.persistence = PersistenceManager(self.temp_dir)
        self.recovery = StateRecovery(self.persistence)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_recover_all_fresh_start(self):
        """Test recovery with no persisted state."""
        result = self.recovery.recover_all()
        
        self.assertTrue(result.success)
        self.assertTrue(result.is_fresh_start)
        self.assertEqual(len(result.recovered_states), 4)
    
    def test_recover_all_with_state(self):
        """Test recovery with persisted state."""
        # Save some state
        trading = TradingStateManager(self.persistence)
        state = trading.get_default_state()
        state.portfolio = {'BTC': 1.0}
        trading.save(state)
        
        result = self.recovery.recover_all()
        
        self.assertTrue(result.success)
        self.assertIn('trading', result.recovered_states)
        
        recovered = self.recovery.get_all_state()
        self.assertEqual(recovered['trading']['portfolio'], {'BTC': 1.0})
    
    def test_validate_recovery(self):
        """Test recovery validation."""
        result = self.recovery.validate_recovery()
        self.assertTrue(result)
    
    def test_force_reset(self):
        """Test force reset."""
        # Save some state
        self.persistence.save_state('trading', {'test': 1})
        self.persistence.save_state('risk', {'test': 2})
        
        # Force reset
        self.recovery.force_reset(['trading'])
        
        # Verify trading is gone but risk remains
        trading = self.persistence.load_state('trading')
        risk = self.persistence.load_state('risk')
        
        self.assertIsNone(trading)
        self.assertIsNotNone(risk)


class TestAtomicOperations(unittest.TestCase):
    """Test atomic write operations."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = PersistenceManager(self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_concurrent_writes(self):
        """Test concurrent writes don't corrupt state."""
        import threading
        
        errors = []
        
        def writer(value):
            try:
                self.manager.save_state('concurrent', {'value': value})
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertEqual(len(errors), 0)
        
        # Verify final state is valid
        loaded = self.manager.load_state('concurrent')
        self.assertIsNotNone(loaded)
        self.assertIn('value', loaded)


if __name__ == '__main__':
    unittest.main(verbosity=2)
