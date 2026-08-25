"""
Unit tests for Phase 15 Stateful Circuit Breaker.
"""

import sys
sys.path.insert(0, '/workspace')

import unittest
import json
import os
import tempfile
from datetime import datetime, timedelta
from risk.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, BreakerState


class TestCircuitBreaker(unittest.TestCase):
    """Test circuit breaker functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_path = self.temp_file.name
        self.temp_file.close()
        
        self.config = CircuitBreakerConfig(
            warning_drawdown=0.05,
            derisk_drawdown=0.08,
            halt_drawdown=0.12,
            recovery_drawdown=0.05,
            normal_drawdown=0.02,
        )
        self.cb = CircuitBreaker(
            config=self.config,
            persistence_path=self.temp_path,
        )
    
    def tearDown(self):
        """Clean up test files."""
        if os.path.exists(self.temp_path):
            os.remove(self.temp_path)
    
    def test_initial_state(self):
        """Test initial state is NORMAL."""
        self.assertEqual(self.cb.get_state(), BreakerState.NORMAL)
        self.assertTrue(self.cb.can_trade())
        self.assertEqual(self.cb.get_multiplier(), 1.0)
    
    def test_transition_to_warning(self):
        """Test transition from NORMAL to WARNING."""
        self.cb.update(drawdown=-0.06, daily_pnl=-0.01, win=False, force=True)
        
        self.assertEqual(self.cb.get_state(), BreakerState.WARNING)
        self.assertTrue(self.cb.can_trade())
        self.assertEqual(self.cb.get_multiplier(), 0.7)
    
    def test_transition_to_derisk(self):
        """Test transition from WARNING to DERISK."""
        self.cb.update(drawdown=-0.06, daily_pnl=-0.01, win=False, force=True)
        self.assertEqual(self.cb.get_state(), BreakerState.WARNING)
        
        self.cb.update(drawdown=-0.09, daily_pnl=-0.02, win=False, force=True)
        self.assertEqual(self.cb.get_state(), BreakerState.DERISK)
        self.assertEqual(self.cb.get_multiplier(), 0.4)
    
    def test_transition_to_halt(self):
        """Test transition to HALT."""
        self.cb.update(drawdown=-0.13, daily_pnl=-0.01, win=False, force=True)
        self.assertEqual(self.cb.get_state(), BreakerState.HALT)
        self.assertFalse(self.cb.can_trade())
        self.assertEqual(self.cb.get_multiplier(), 0.0)
    
    def test_halt_by_daily_loss(self):
        """Test halt triggered by daily loss."""
        self.cb.update(drawdown=-0.05, daily_pnl=-0.035, win=False, force=True)
        self.assertEqual(self.cb.get_state(), BreakerState.HALT)
    
    def test_recovery_from_halt(self):
        """Test recovery from HALT to RECOVERY."""
        # First go to HALT
        self.cb.update(drawdown=-0.13, daily_pnl=-0.01, win=False, force=True)
        self.assertEqual(self.cb.get_state(), BreakerState.HALT)
        
        # Simulate recovery
        self.cb.update(drawdown=-0.04, daily_pnl=-0.005, win=True, force=True)
        self.assertEqual(self.cb.get_state(), BreakerState.RECOVERY)
        self.assertEqual(self.cb.get_multiplier(), 0.5)
    
    def test_full_cycle(self):
        """Test full cycle: NORMAL → WARNING → DERISK → HALT → RECOVERY → NORMAL."""
        # NORMAL → WARNING
        self.cb.update(drawdown=-0.06, daily_pnl=-0.01, win=False, force=True)
        self.assertEqual(self.cb.get_state(), BreakerState.WARNING)
        
        # WARNING → DERISK
        self.cb.update(drawdown=-0.09, daily_pnl=-0.02, win=False, force=True)
        self.assertEqual(self.cb.get_state(), BreakerState.DERISK)
        
        # DERISK → HALT
        self.cb.update(drawdown=-0.13, daily_pnl=-0.01, win=False, force=True)
        self.assertEqual(self.cb.get_state(), BreakerState.HALT)
        
        # HALT → RECOVERY
        self.cb.update(drawdown=-0.04, daily_pnl=-0.005, win=True, force=True)
        self.assertEqual(self.cb.get_state(), BreakerState.RECOVERY)
        
        # RECOVERY → NORMAL
        self.cb.update(drawdown=-0.01, daily_pnl=-0.001, win=True, force=True)
        self.assertEqual(self.cb.get_state(), BreakerState.NORMAL)
    
    def test_persistence(self):
        """Test state persistence across instances."""
        # Save state
        self.cb.update(drawdown=-0.06, daily_pnl=-0.01, win=False, force=True)
        self.assertEqual(self.cb.get_state(), BreakerState.WARNING)
        
        # Create new instance with same persistence path
        cb2 = CircuitBreaker(
            config=self.config,
            persistence_path=self.temp_path,
        )
        
        # Should load the saved state
        self.assertEqual(cb2.get_state(), BreakerState.WARNING)
    
    def test_manual_force_halt(self):
        """Test manual halt override."""
        self.cb.force_halt("Test emergency")
        self.assertEqual(self.cb.get_state(), BreakerState.HALT)
        self.assertFalse(self.cb.can_trade())
        
        # Check that transition was recorded
        history = self.cb.get_transition_history()
        self.assertGreater(len(history), 0)
        self.assertEqual(history[-1]['to_state'], 'halt')
        self.assertIn('MANUAL', history[-1]['reason'])
    
    def test_manual_force_resume(self):
        """Test manual resume override."""
        # First go to HALT
        self.cb.update(drawdown=-0.13, daily_pnl=-0.01, win=False, force=True)
        self.assertEqual(self.cb.get_state(), BreakerState.HALT)
        
        # Force resume
        self.cb.force_resume()
        self.assertEqual(self.cb.get_state(), BreakerState.RECOVERY)
        self.assertTrue(self.cb.can_trade())
    
    def test_deterministic_transitions(self):
        """Test that transitions are deterministic."""
        # Two circuit breakers with same config should behave identically
        cb1 = CircuitBreaker(config=self.config)
        cb2 = CircuitBreaker(config=self.config)
        
        # Apply same updates
        updates = [
            {'drawdown': -0.06, 'daily_pnl': -0.01, 'win': False},
            {'drawdown': -0.09, 'daily_pnl': -0.02, 'win': False},
            {'drawdown': -0.04, 'daily_pnl': -0.005, 'win': True},
        ]
        
        for update in updates:
            state1 = cb1.update(**update, force=True)
            state2 = cb2.update(**update, force=True)
            self.assertEqual(state1, state2)
    
    def test_state_info(self):
        """Test state info method."""
        self.cb.update(drawdown=-0.06, daily_pnl=-0.01, win=False, force=True)
        
        info = self.cb.get_state_info()
        self.assertEqual(info['state'], BreakerState.WARNING.value)
        self.assertTrue(info['can_trade'])
        self.assertEqual(info['multiplier'], 0.7)
        self.assertIsNotNone(info['state_enter_time'])
    
    def test_status_report(self):
        """Test status report generation."""
        # Perform some transitions
        self.cb.update(drawdown=-0.06, daily_pnl=-0.01, win=False, force=True)
        self.cb.update(drawdown=-0.09, daily_pnl=-0.02, win=False, force=True)
        
        report = self.cb.get_status_report()
        self.assertEqual(report['current']['state'], BreakerState.DERISK.value)
        self.assertGreaterEqual(report['statistics']['total_transitions'], 1)
        self.assertIn('current', report)
        self.assertIn('statistics', report)
    
    def test_reset(self):
        """Test reset functionality."""
        # Go to WARNING
        self.cb.update(drawdown=-0.06, daily_pnl=-0.01, win=False, force=True)
        self.assertEqual(self.cb.get_state(), BreakerState.WARNING)
        
        # Reset
        self.cb.reset()
        self.assertEqual(self.cb.get_state(), BreakerState.NORMAL)
        self.assertEqual(self.cb.get_multiplier(), 1.0)
    
    def test_multiplier_by_state(self):
        """Test multiplier values for each state."""
        self.assertEqual(BreakerState.NORMAL.multiplier, 1.0)
        self.assertEqual(BreakerState.WARNING.multiplier, 0.7)
        self.assertEqual(BreakerState.DERISK.multiplier, 0.4)
        self.assertEqual(BreakerState.HALT.multiplier, 0.0)
        self.assertEqual(BreakerState.RECOVERY.multiplier, 0.5)
    
    def test_can_trade_by_state(self):
        """Test can_trade for each state."""
        self.assertTrue(BreakerState.NORMAL.can_trade)
        self.assertTrue(BreakerState.WARNING.can_trade)
        self.assertTrue(BreakerState.DERISK.can_trade)
        self.assertFalse(BreakerState.HALT.can_trade)
        self.assertTrue(BreakerState.RECOVERY.can_trade)
    
    def test_apply_to_risk_decision(self):
        """Test applying circuit breaker to risk decision."""
        risk_decision = {
            'allowed': True,
            'risk_multiplier': 0.8,
            'max_exposure': 1.0,
            'max_position': 0.20,
            'reason': 'OK',
        }
        
        # NORMAL state - no change
        result = self.cb.apply_to_risk_decision(risk_decision)
        self.assertEqual(result['risk_multiplier'], 0.8)
        
        # WARNING state - apply multiplier
        self.cb.update(drawdown=-0.06, daily_pnl=-0.01, win=False, force=True)
        result = self.cb.apply_to_risk_decision(risk_decision)
        self.assertEqual(result['risk_multiplier'], 0.8 * 0.7)
        self.assertIn('CB:', result['reason'])
        
        # HALT state - block trading
        self.cb.update(drawdown=-0.13, daily_pnl=-0.01, win=False, force=True)
        result = self.cb.apply_to_risk_decision(risk_decision)
        self.assertFalse(result['allowed'])
        self.assertEqual(result['risk_multiplier'], 0.0)


if __name__ == '__main__':
    unittest.main()
