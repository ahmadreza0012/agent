"""
Unit tests for Phase 21 Live Trading Safety.

Tests cover:
- LiveSafetyLimits configuration and validation
- LiveSafetyState tracking
- SafetyChecker validations
- LiveSafetyEngine orchestration
- Integration with KillSwitch
"""

import sys
sys.path.insert(0, '/workspace')

import unittest
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from unittest.mock import Mock, MagicMock

from execution.live_safety_config import LiveSafetyLimits, LiveSafetyState
from execution.safety_checker import SafetyChecker, SafetyCheckResult
from execution.live_safety_engine import LiveSafetyEngine
from execution.kill_switch import KillSwitch
from execution.exchange_adapter import ExchangeAdapter, Balance, Position


class MockExchangeForSafety(ExchangeAdapter):
    """Mock exchange adapter for safety testing."""
    
    def __init__(self, healthy: bool = True):
        self._healthy = healthy
        self._failure_count = 0
        self._balances = {
            'USDT': Balance('USDT', 10000.0, 10000.0, 0.0),
            'BTC': Balance('BTC', 0.1, 0.1, 0.0)
        }
        self._positions = []
        self._orders = {}
    
    def health_check(self) -> bool:
        self._failure_count += 1
        return self._healthy
    
    def get_balance(self, asset: Optional[str] = None) -> Dict[str, Balance]:
        if asset:
            return {asset: self._balances.get(asset, Balance(asset, 0, 0, 0))}
        return self._balances.copy()
    
    def get_positions(self) -> list:
        return self._positions
    
    def set_healthy(self, healthy: bool):
        self._healthy = healthy
    
    # Implement required abstract methods
    def get_ticker(self, symbol: str) -> Dict[str, float]:
        return {'price': 50000.0, 'volume': 1000.0}
    
    def create_order(self, symbol: str, side: Any, order_type: Any,
                     amount: float, price: Optional[float] = None,
                     client_order_id: Optional[str] = None) -> Any:
        from execution.exchange_adapter import Order, OrderStatus
        order = Order(
            id=f"mock_{len(self._orders)}",
            client_order_id=client_order_id or f"client_{len(self._orders)}",
            symbol=symbol,
            side=side,
            type=order_type,
            price=price or 50000.0,
            amount=amount,
            filled_amount=amount,
            status=OrderStatus.FILLED,
            timestamp=datetime.now()
        )
        self._orders[order.id] = order
        return order
    
    def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        if order_id in self._orders:
            self._orders[order_id].status = OrderStatus.CANCELLED
            return True
        return False
    
    def get_order(self, order_id: str, symbol: Optional[str] = None) -> Optional[Any]:
        return self._orders.get(order_id)


class MockPositionManager:
    """Mock position manager for testing."""
    
    def __init__(self):
        self.positions = {}
    
    def get_positions(self):
        return list(self.positions.values())


class MockMarketData:
    """Mock market data provider."""
    
    def __init__(self, prices: Optional[Dict[str, float]] = None):
        self.prices = prices or {'BTC/USDT': 50000.0, 'ETH/USDT': 3000.0}
    
    def get_ticker(self, symbol: str) -> Dict[str, float]:
        price = self.prices.get(symbol, 0.0)
        return {'price': price, 'volume': 1000.0}


# ============================================================================
# Test LiveSafetyLimits
# ============================================================================

class TestLiveSafetyLimits(unittest.TestCase):
    """Test LiveSafetyLimits configuration."""
    
    def setUp(self):
        self.limits = LiveSafetyLimits()
    
    def test_default_values(self):
        """Test default limit values are reasonable."""
        self.assertEqual(self.limits.max_daily_loss_soft, 0.02)
        self.assertEqual(self.limits.max_daily_loss_hard, 0.05)
        self.assertEqual(self.limits.max_total_drawdown_soft, 0.10)
        self.assertEqual(self.limits.max_total_drawdown_hard, 0.15)
        self.assertEqual(self.limits.max_position_size, 0.20)
        self.assertEqual(self.limits.max_total_exposure, 0.60)
    
    def test_validation_passes(self):
        """Test that valid limits pass validation."""
        result = self.limits.validate()
        self.assertTrue(result)
    
    def test_validation_fails_invalid_daily_loss(self):
        """Test validation fails when hard <= soft for daily loss."""
        limits = LiveSafetyLimits(max_daily_loss_soft=0.05, max_daily_loss_hard=0.03)
        with self.assertRaises(ValueError):
            limits.validate()
    
    def test_validation_fails_invalid_drawdown(self):
        """Test validation fails when hard <= soft for drawdown."""
        limits = LiveSafetyLimits(max_total_drawdown_soft=0.15, max_total_drawdown_hard=0.10)
        with self.assertRaises(ValueError):
            limits.validate()
    
    def test_validation_fails_invalid_position_size(self):
        """Test validation fails for position size outside 0-1."""
        limits = LiveSafetyLimits(max_position_size=1.5)
        with self.assertRaises(ValueError):
            limits.validate()
    
    def test_log_configuration(self):
        """Test logging configuration doesn't raise errors."""
        # Should not raise any exceptions
        self.limits.log_configuration()


# ============================================================================
# Test LiveSafetyState
# ============================================================================

class TestLiveSafetyState(unittest.TestCase):
    """Test LiveSafetyState tracking."""
    
    def setUp(self):
        self.state = LiveSafetyState()
    
    def test_initial_state(self):
        """Test initial state values."""
        self.assertFalse(self.state.is_active)
        self.assertFalse(self.state.is_halted)
        self.assertEqual(self.state.daily_pnl, 0.0)
        self.assertEqual(self.state.daily_trades, 0)
        self.assertEqual(self.state.current_drawdown, 0.0)
        self.assertEqual(self.state.peak_equity, 0.0)
    
    def test_reset_daily(self):
        """Test daily reset functionality."""
        self.state.daily_pnl = -500.0
        self.state.daily_trades = 10
        self.state.daily_turnover = 50000.0
        
        self.state.reset_daily()
        
        self.assertEqual(self.state.daily_pnl, 0.0)
        self.assertEqual(self.state.daily_trades, 0)
        self.assertEqual(self.state.daily_turnover, 0.0)
        self.assertIsNotNone(self.state.last_reset_date)
    
    def test_record_trade(self):
        """Test trade recording."""
        self.state.record_trade(pnl=100.0, turnover=5000.0, symbol='BTC/USDT', side='BUY')
        
        self.assertEqual(self.state.daily_pnl, 100.0)
        self.assertEqual(self.state.daily_trades, 1)
        self.assertEqual(self.state.daily_turnover, 5000.0)
        self.assertEqual(self.state.daily_loss_count, 0)
    
    def test_record_trade_loss(self):
        """Test recording a losing trade."""
        self.state.record_trade(pnl=-100.0, turnover=5000.0)
        
        self.assertEqual(self.state.daily_pnl, -100.0)
        self.assertEqual(self.state.daily_loss_count, 1)
    
    def test_update_equity_drawdown(self):
        """Test equity update and drawdown calculation."""
        self.state.update_equity(10000.0)  # Initial equity
        self.assertEqual(self.state.peak_equity, 10000.0)
        self.assertEqual(self.state.current_drawdown, 0.0)
        
        self.state.update_equity(9000.0)  # 10% drop
        self.assertEqual(self.state.peak_equity, 10000.0)
        self.assertAlmostEqual(self.state.current_drawdown, -0.10, places=2)
        
        self.state.update_equity(11000.0)  # New peak
        self.assertEqual(self.state.peak_equity, 11000.0)
        self.assertEqual(self.state.current_drawdown, 0.0)
    
    def test_api_failure_tracking(self):
        """Test API failure counting."""
        self.state.record_api_failure()
        self.state.record_api_failure()
        
        self.assertEqual(self.state.consecutive_failures, 2)
        
        self.state.record_api_success()
        self.assertEqual(self.state.consecutive_failures, 0)
    
    def test_positive_days_tracking(self):
        """Test positive days counter for exposure ramp."""
        self.state.increment_positive_days()
        self.state.increment_positive_days()
        
        self.assertEqual(self.state.positive_days_count, 2)
        
        self.state.reset_positive_days()
        self.assertEqual(self.state.positive_days_count, 0)
    
    def test_can_increase_exposure(self):
        """Test exposure increase conditions."""
        limits = LiveSafetyLimits()
        self.state.exposure_start_date = datetime.now() - timedelta(days=10)
        self.state.positive_days_count = 6
        
        # Should be able to increase (enough days and positive days)
        self.assertTrue(self.state.can_increase_exposure(limits))
        
        # Not enough positive days
        self.state.positive_days_count = 3
        self.assertFalse(self.state.can_increase_exposure(limits))
    
    def test_get_status_summary(self):
        """Test status summary generation."""
        self.state.current_equity = 10000.0
        self.state.daily_pnl = 100.0
        self.state.current_drawdown = -0.05
        
        summary = self.state.get_status_summary()
        
        self.assertIn('is_active', summary)
        self.assertIn('daily_pnl', summary)
        self.assertIn('current_drawdown', summary)


# ============================================================================
# Test SafetyChecker
# ============================================================================

class TestSafetyChecker(unittest.TestCase):
    """Test SafetyChecker validations."""
    
    def setUp(self):
        self.limits = LiveSafetyLimits()
        self.state = LiveSafetyState()
        self.exchange = MockExchangeForSafety(healthy=True)
        self.checker = SafetyChecker(
            limits=self.limits,
            state=self.state,
            exchange_adapter=self.exchange
        )
    
    def test_initial_check_passes(self):
        """Test that initial checks pass with healthy system."""
        self.state.current_equity = 10000.0
        result = self.checker.check_all()
        self.assertTrue(result.is_safe)
    
    def test_daily_loss_hard_limit(self):
        """Test hard daily loss limit triggers failure."""
        self.state.current_equity = 10000.0
        self.state.daily_pnl = -600.0  # -6% (hard limit is 5%)
        
        result = self.checker.check_loss_limits()
        
        self.assertFalse(result.is_safe)
        self.assertIn("HARD daily loss limit", result.reason)
    
    def test_daily_loss_soft_limit_warning(self):
        """Test soft daily loss limit generates warning but passes."""
        self.state.current_equity = 10000.0
        self.state.daily_pnl = -250.0  # -2.5% (between soft 2% and hard 5%)
        
        result = self.checker.check_loss_limits()
        
        # Should pass but log warning (soft limit)
        self.assertTrue(result.is_safe)
    
    def test_drawdown_hard_limit(self):
        """Test hard drawdown limit triggers failure."""
        self.state.current_equity = 8500.0
        self.state.peak_equity = 10000.0
        self.state.current_drawdown = -0.15  # -15% (hard limit)
        
        result = self.checker.check_loss_limits()
        
        self.assertFalse(result.is_safe)
        self.assertIn("HARD drawdown limit", result.reason)
    
    def test_exchange_health_failure(self):
        """Test exchange health check failure."""
        self.exchange.set_healthy(False)
        
        # Need multiple failures to trigger halt
        for _ in range(3):
            result = self.checker.check_exchange_health()
        
        self.assertFalse(result.is_safe)
    
    def test_order_limits_min_value(self):
        """Test minimum order value check."""
        order_request = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'amount': 0.0001,
            'price': 50000.0
        }
        # Order value = $5, which is below $10 min
        
        result = self.checker.check_order_limits(order_request)
        
        self.assertFalse(result.is_safe)
        self.assertIn("too small", result.reason)
    
    def test_order_limits_max_value(self):
        """Test maximum order value check."""
        self.state.current_equity = 10000.0
        order_request = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'amount': 5.0,
            'price': 50000.0
        }
        # Order value = $250,000, which exceeds $100,000 max
        
        result = self.checker.check_order_limits(order_request)
        
        self.assertFalse(result.is_safe)
        self.assertIn("too large", result.reason)
    
    def test_check_all_runs_all_checks(self):
        """Test that check_all runs all checks."""
        self.state.current_equity = 10000.0
        
        result = self.checker.check_all()
        
        self.assertTrue(result.is_safe)
        self.assertIn("All safety checks passed", result.reason)


# ============================================================================
# Test LiveSafetyEngine
# ============================================================================

import os

class TestLiveSafetyEngine(unittest.TestCase):
    """Test LiveSafetyEngine orchestration."""
    
    def setUp(self):
        # Clean up any existing kill switch state file
        try:
            os.remove('/tmp/ks_test.json')
        except FileNotFoundError:
            pass
        
        self.limits = LiveSafetyLimits()
        self.kill_switch = KillSwitch(state_file='/tmp/ks_test.json')
        self.exchange = MockExchangeForSafety(healthy=True)
        self.position_manager = MockPositionManager()
        self.market_data = MockMarketData()
        
        self.engine = LiveSafetyEngine(
            limits=self.limits,
            kill_switch=self.kill_switch,
            exchange_adapter=self.exchange,
            position_manager=self.position_manager,
            market_data_provider=self.market_data
        )
    
    def test_initial_can_trade(self):
        """Test that trading is allowed initially."""
        self.state = self.engine.state
        self.state.current_equity = 10000.0
        
        self.assertTrue(self.engine.can_trade())
    
    def test_pre_trade_check_passes(self):
        """Test pre-trade check passes with healthy system."""
        self.engine.state.current_equity = 10000.0
        
        result = self.engine.pre_trade_check()
        
        self.assertTrue(result.is_safe)
    
    def test_pre_trade_check_fails_on_kill_switch(self):
        """Test pre-trade check fails when kill switch is active."""
        from execution.kill_switch_models import KillSwitchLevel, KillSwitchTrigger
        self.kill_switch.trigger(
            level=KillSwitchLevel.HALT,
            trigger=KillSwitchTrigger.MANUAL,
            reason='Test halt',
            details={},
            triggered_by='test'
        )
        self.engine.state.current_equity = 10000.0
        
        result = self.engine.pre_trade_check()
        
        self.assertFalse(result.is_safe)
        self.assertIn("Kill switch", result.reason)
    
    def test_post_trade_update(self):
        """Test post-trade state update."""
        self.engine.state.current_equity = 10000.0
        
        self.engine.post_trade_update({
            'pnl': 100.0,
            'turnover': 5000.0,
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'amount': 0.1,
            'price': 50000.0
        })
        
        self.assertEqual(self.engine.state.daily_pnl, 100.0)
        self.assertEqual(self.engine.state.daily_trades, 1)
    
    def test_get_status(self):
        """Test status retrieval."""
        self.engine.state.current_equity = 10000.0
        
        status = self.engine.get_status()
        
        self.assertIn('can_trade', status)
        self.assertIn('daily_pnl', status)
        self.assertIn('current_drawdown', status)
        self.assertIn('is_active', status)
    
    def test_reset_daily_limits(self):
        """Test daily limits reset."""
        self.engine.state.daily_pnl = -500.0
        self.engine.state.daily_trades = 5
        
        self.engine.reset_daily_limits()
        
        self.assertEqual(self.engine.state.daily_pnl, 0.0)
        self.assertEqual(self.engine.state.daily_trades, 0)
    
    def test_initialize_exposure_ramp(self):
        """Test exposure ramp initialization."""
        self.engine.initialize_exposure_ramp()
        
        self.assertIsNotNone(self.engine.state.exposure_start_date)
        self.assertEqual(self.engine.state.exposure_ratio, self.limits.initial_exposure_ratio)
        self.assertEqual(self.engine.state.positive_days_count, 0)
    
    def test_force_halt(self):
        """Test force halt functionality."""
        self.engine.force_halt("Test emergency")
        
        self.assertTrue(self.engine.state.is_halted)
        self.assertEqual(self.engine.state.halt_reason, "Test emergency")
        self.assertIsNotNone(self.engine.state.halt_timestamp)


# ============================================================================
# Test SafetyCheckResult
# ============================================================================

class TestSafetyCheckResult(unittest.TestCase):
    """Test SafetyCheckResult class."""
    
    def test_bool_conversion(self):
        """Test boolean conversion."""
        safe_result = SafetyCheckResult(True, "All good")
        unsafe_result = SafetyCheckResult(False, "Problem")
        
        self.assertTrue(bool(safe_result))
        self.assertFalse(bool(unsafe_result))
    
    def test_string_representation(self):
        """Test string representation."""
        safe_result = SafetyCheckResult(True, "All good")
        unsafe_result = SafetyCheckResult(False, "Problem")
        
        self.assertIn("PASS", str(safe_result))
        self.assertIn("FAIL", str(unsafe_result))
    
    def test_to_dict(self):
        """Test dictionary conversion."""
        result = SafetyCheckResult(True, "Test", {'key': 'value'})
        
        d = result.to_dict()
        
        self.assertTrue(d['is_safe'])
        self.assertEqual(d['reason'], "Test")
        self.assertEqual(d['details'], {'key': 'value'})
        self.assertIn('timestamp', d)


if __name__ == '__main__':
    unittest.main(verbosity=2)
