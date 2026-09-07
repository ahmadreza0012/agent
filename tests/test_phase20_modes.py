"""
Tests for Phase 20: Paper & Shadow Trading.

This module contains comprehensive tests for the paper trading adapter,
shadow trading adapter, mode manager, and mode factory.
"""

import unittest
from datetime import datetime
from typing import Dict, Any

from execution.trading_modes import TradingMode, TradingConfig
from execution.paper_adapter import PaperTradingAdapter
from execution.shadow_adapter import ShadowTradingAdapter
from execution.mode_manager import TradingModeManager, ModeTransitionError
from execution.mode_factory import ModeFactory
from execution.exchange_adapter import OrderSide, OrderType, OrderStatus, Balance


class MockMarketData:
    """Mock market data provider for testing."""
    
    def __init__(self):
        self.prices = {
            'BTC/USDT': 50000.0,
            'ETH/USDT': 3000.0,
            'SOL/USDT': 100.0
        }
        self.volume = 1000.0
    
    def get_ticker(self, symbol: str) -> Dict[str, float]:
        """Get ticker for a symbol."""
        return {
            'price': self.prices.get(symbol, 0.0),
            'volume': self.volume
        }
    
    def set_price(self, symbol: str, price: float) -> None:
        """Set price for testing."""
        self.prices[symbol] = price


class MockLiveAdapter:
    """Mock live adapter for shadow testing."""
    
    def __init__(self):
        self._balances = {
            'USDT': Balance('USDT', 100000.0, 90000.0, 10000.0),
            'BTC': Balance('BTC', 1.0, 1.0, 0.0)
        }
        self._positions = []
    
    def get_balance(self, asset=None):
        """Get balance(s)."""
        if asset:
            return {asset: self._balances.get(asset, Balance(asset, 0, 0, 0))}
        return self._balances.copy()
    
    def get_positions(self):
        """Get positions."""
        return self._positions
    
    def get_ticker(self, symbol: str) -> Dict[str, float]:
        """Get ticker."""
        return {'price': 50000.0, 'volume': 1000.0}
    
    def create_order(self, symbol, side, order_type, amount, price=None, client_order_id=None):
        """Create order (mock)."""
        raise NotImplementedError("Mock live adapter does not support order creation")
    
    def cancel_order(self, order_id, symbol=None):
        """Cancel order (mock)."""
        return False
    
    def get_order(self, order_id, symbol=None):
        """Get order (mock)."""
        return None
    
    def health_check(self):
        """Health check."""
        return True


class TestPaperTrading(unittest.TestCase):
    """Test cases for PaperTradingAdapter."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = TradingConfig.default_for_mode(TradingMode.PAPER)
        self.market_data = MockMarketData()
        self.adapter = PaperTradingAdapter(self.config, self.market_data)
    
    def test_initial_balance(self):
        """Test initial balance is correct."""
        balances = self.adapter.get_balance()
        self.assertEqual(balances['USDT'].total, self.config.initial_capital)
        self.assertEqual(balances['USDT'].free, self.config.initial_capital)
    
    def test_buy_order(self):
        """Test buying with paper trading."""
        # Buy 0.1 BTC at ~$50,000
        order = self.adapter.create_order(
            'BTC/USDT',
            OrderSide.BUY,
            OrderType.MARKET,
            0.1
        )
        
        # Verify order was filled
        self.assertEqual(order.status, OrderStatus.FILLED)
        self.assertEqual(order.symbol, 'BTC/USDT')
        self.assertEqual(order.side, OrderSide.BUY)
        self.assertGreater(order.filled_amount, 0)
        
        # Verify balance updated
        balances = self.adapter.get_balance()
        self.assertIn('BTC', balances)
        self.assertGreater(balances['BTC'].free, 0)
        
        # Verify USDT decreased
        self.assertLess(balances['USDT'].free, self.config.initial_capital)
    
    def test_sell_order(self):
        """Test selling with paper trading."""
        # First buy some BTC
        self.adapter.create_order('BTC/USDT', OrderSide.BUY, OrderType.MARKET, 0.1)
        
        # Then sell it
        order = self.adapter.create_order(
            'BTC/USDT',
            OrderSide.SELL,
            OrderType.MARKET,
            0.1
        )
        
        self.assertEqual(order.status, OrderStatus.FILLED)
        
        # Verify we got USDT back (minus fees)
        balances = self.adapter.get_balance()
        self.assertGreater(balances['USDT'].free, 0)
    
    def test_insufficient_balance_buy(self):
        """Test insufficient balance for buy order."""
        # Try to buy more than we can afford
        with self.assertRaises(ValueError):
            self.adapter.create_order(
                'BTC/USDT',
                OrderSide.BUY,
                OrderType.MARKET,
                1000.0  # Way too much
            )
    
    def test_insufficient_balance_sell(self):
        """Test insufficient balance for sell order."""
        # Try to sell without owning the asset
        with self.assertRaises(ValueError):
            self.adapter.create_order(
                'BTC/USDT',
                OrderSide.SELL,
                OrderType.MARKET,
                1.0
            )
    
    def test_position_tracking(self):
        """Test position tracking."""
        # Buy BTC
        self.adapter.create_order('BTC/USDT', OrderSide.BUY, OrderType.MARKET, 0.1)
        
        positions = self.adapter.get_positions()
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].symbol, 'BTC/USDT')
        self.assertGreater(positions[0].size, 0)
    
    def test_performance_metrics(self):
        """Test performance metrics calculation."""
        # Make some trades
        self.adapter.create_order('BTC/USDT', OrderSide.BUY, OrderType.MARKET, 0.1)
        
        perf = self.adapter.get_performance()
        
        self.assertIn('initial_capital', perf)
        self.assertIn('current_equity', perf)
        self.assertIn('total_return', perf)
        self.assertIn('num_trades', perf)
        self.assertEqual(perf['num_trades'], 1)
    
    def test_slippage_calculation(self):
        """Test slippage is applied correctly."""
        # Get current price
        ticker = self.market_data.get_ticker('BTC/USDT')
        base_price = ticker['price']
        
        # Buy with slippage (market order)
        order = self.adapter.create_order(
            'BTC/USDT',
            OrderSide.BUY,
            OrderType.MARKET,
            0.1
        )
        
        # Execution price should be slightly higher than base price (slippage)
        self.assertGreater(order.price, base_price)
    
    def test_fee_calculation(self):
        """Test fee is calculated correctly."""
        initial_usdt = self.adapter.get_balance()['USDT'].free
        
        # Buy BTC
        order = self.adapter.create_order(
            'BTC/USDT',
            OrderSide.BUY,
            OrderType.MARKET,
            0.1
        )
        
        # Fee should be included in the cost
        self.assertIsNotNone(order.fee)
        self.assertGreater(order.fee['cost'], 0)
    
    def test_reset(self):
        """Test adapter reset."""
        # Make some trades
        self.adapter.create_order('BTC/USDT', OrderSide.BUY, OrderType.MARKET, 0.1)
        
        # Reset
        self.adapter.reset()
        
        # Verify back to initial state
        balances = self.adapter.get_balance()
        self.assertEqual(balances['USDT'].total, self.config.initial_capital)
        self.assertEqual(len(self.adapter.get_positions()), 0)


class TestShadowTrading(unittest.TestCase):
    """Test cases for ShadowTradingAdapter."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = TradingConfig.default_for_mode(TradingMode.SHADOW)
        self.market_data = MockMarketData()
        self.live_adapter = MockLiveAdapter()
        self.adapter = ShadowTradingAdapter(
            self.config,
            self.live_adapter,
            self.market_data
        )
    
    def test_initial_sync(self):
        """Test initial sync from live adapter."""
        balances = self.adapter.get_balance()
        
        # Should have synced from live
        self.assertIn('USDT', balances)
        self.assertIn('BTC', balances)
    
    def test_shadow_order_creation(self):
        """Test shadow order creation."""
        order = self.adapter.create_order(
            'BTC/USDT',
            OrderSide.BUY,
            OrderType.MARKET,
            0.1
        )
        
        # Verify it's marked as shadow
        self.assertTrue(order.id.startswith('shadow_'))
        self.assertEqual(order.status, OrderStatus.FILLED)
    
    def test_live_performance_comparison(self):
        """Test performance comparison between shadow and live."""
        # Create shadow order
        self.adapter.create_order('BTC/USDT', OrderSide.BUY, OrderType.MARKET, 0.1)
        
        # Compare performance
        comparison = self.adapter.compare_performance()
        
        self.assertIn('shadow', comparison)
        self.assertIn('live', comparison)
        self.assertIn('difference', comparison)
        self.assertIn('difference_percent', comparison)
    
    def test_divergence_analysis(self):
        """Test divergence analysis."""
        # Create some comparisons
        for _ in range(3):
            self.adapter.create_order('BTC/USDT', OrderSide.BUY, OrderType.MARKET, 0.01)
            self.adapter.compare_performance()
        
        analysis = self.adapter.analyze_divergence()
        
        self.assertIn('avg_difference_percent', analysis)
        self.assertIn('total_comparisons', analysis)
        self.assertEqual(analysis['total_comparisons'], 3)


class TestModeManager(unittest.TestCase):
    """Test cases for TradingModeManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = TradingModeManager()
        self.configs = ModeFactory.create_default_configs()
        self.market_data = MockMarketData()
        self.live_adapter = MockLiveAdapter()
        
        # Create adapters
        adapters = {}
        for mode in [TradingMode.PAPER, TradingMode.BACKTEST]:
            adapters[mode] = ModeFactory.create_adapter(
                mode,
                self.configs[mode],
                market_data_provider=self.market_data
            )
        
        adapters[TradingMode.LIVE] = self.live_adapter
        
        adapters[TradingMode.SHADOW] = ModeFactory.create_adapter(
            TradingMode.SHADOW,
            self.configs[TradingMode.SHADOW],
            live_adapter=self.live_adapter,
            market_data_provider=self.market_data
        )
        
        self.manager.initialize(TradingMode.PAPER, adapters)
    
    def test_initial_mode(self):
        """Test initial mode is PAPER."""
        self.assertEqual(self.manager.current_mode, TradingMode.PAPER)
    
    def test_switch_to_shadow(self):
        """Test switching to shadow mode."""
        result = self.manager.switch_mode(TradingMode.SHADOW)
        
        self.assertTrue(result['success'])
        self.assertEqual(self.manager.current_mode, TradingMode.SHADOW)
        self.assertEqual(result['old_mode'], 'paper')
        self.assertEqual(result['new_mode'], 'shadow')
    
    def test_live_mode_requires_confirmation(self):
        """Test that LIVE mode requires explicit confirmation."""
        # Without confirmation should fail
        with self.assertRaises(ModeTransitionError):
            self.manager.switch_mode(TradingMode.LIVE, confirm=False)
        
        # With confirmation should succeed
        result = self.manager.switch_mode(TradingMode.LIVE, confirm=True)
        self.assertTrue(result['success'])
        self.assertEqual(self.manager.current_mode, TradingMode.LIVE)
    
    def test_is_simulated(self):
        """Test is_simulated property."""
        self.assertTrue(self.manager.is_simulated())  # PAPER mode
        
        self.manager.switch_mode(TradingMode.SHADOW)
        self.assertTrue(self.manager.is_simulated())  # SHADOW mode
    
    def test_uses_real_capital(self):
        """Test uses_real_capital property."""
        self.assertFalse(self.manager.uses_real_capital())  # PAPER mode
        
        self.manager.switch_mode(TradingMode.LIVE, confirm=True)
        self.assertTrue(self.manager.uses_real_capital())  # LIVE mode
    
    def test_mode_history(self):
        """Test mode history tracking."""
        self.manager.switch_mode(TradingMode.SHADOW)
        self.manager.switch_mode(TradingMode.LIVE, confirm=True)
        
        history = self.manager.get_mode_history()
        self.assertGreater(len(history), 1)
    
    def test_validate_mode_safety(self):
        """Test mode safety validation."""
        safety = self.manager.validate_mode_safety()
        
        self.assertIn('current_mode', safety)
        self.assertIn('is_safe', safety)
        self.assertEqual(safety['current_mode'], 'paper')
        self.assertTrue(safety['is_safe'])  # Paper is safe
    
    def test_force_paper_mode(self):
        """Test force switch to paper mode."""
        # Switch to live
        self.manager.switch_mode(TradingMode.LIVE, confirm=True)
        self.assertEqual(self.manager.current_mode, TradingMode.LIVE)
        
        # Force back to paper
        self.manager.force_paper_mode()
        self.assertEqual(self.manager.current_mode, TradingMode.PAPER)


class TestModeFactory(unittest.TestCase):
    """Test cases for ModeFactory."""
    
    def test_create_default_configs(self):
        """Test creating default configurations."""
        configs = ModeFactory.create_default_configs()
        
        self.assertIn(TradingMode.BACKTEST, configs)
        self.assertIn(TradingMode.PAPER, configs)
        self.assertIn(TradingMode.SHADOW, configs)
        self.assertIn(TradingMode.LIVE, configs)
        
        # Verify PAPER config has virtual capital
        self.assertGreater(configs[TradingMode.PAPER].initial_capital, 0)
        
        # Verify LIVE requires confirmation
        self.assertTrue(configs[TradingMode.LIVE].requires_confirmation)
    
    def test_create_paper_adapter(self):
        """Test creating paper adapter."""
        config = TradingConfig.default_for_mode(TradingMode.PAPER)
        market_data = MockMarketData()
        
        adapter = ModeFactory.create_adapter(
            TradingMode.PAPER,
            config,
            market_data_provider=market_data
        )
        
        self.assertIsInstance(adapter, PaperTradingAdapter)
    
    def test_create_shadow_adapter(self):
        """Test creating shadow adapter."""
        config = TradingConfig.default_for_mode(TradingMode.SHADOW)
        market_data = MockMarketData()
        live_adapter = MockLiveAdapter()
        
        adapter = ModeFactory.create_adapter(
            TradingMode.SHADOW,
            config,
            live_adapter=live_adapter,
            market_data_provider=market_data
        )
        
        self.assertIsInstance(adapter, ShadowTradingAdapter)
    
    def test_shadow_requires_live_adapter(self):
        """Test that shadow mode requires live adapter."""
        config = TradingConfig.default_for_mode(TradingMode.SHADOW)
        
        with self.assertRaises(ValueError):
            ModeFactory.create_adapter(
                TradingMode.SHADOW,
                config,
                live_adapter=None
            )
    
    def test_get_mode_info(self):
        """Test getting mode information."""
        info = ModeFactory.get_mode_info(TradingMode.PAPER)
        
        self.assertEqual(info['mode'], 'paper')
        self.assertTrue(info['is_simulated'])
        self.assertFalse(info['uses_real_capital'])
        self.assertFalse(info['requires_confirmation'])
    
    def test_live_mode_info(self):
        """Test LIVE mode information."""
        info = ModeFactory.get_mode_info(TradingMode.LIVE)
        
        self.assertEqual(info['mode'], 'live')
        self.assertFalse(info['is_simulated'])
        self.assertTrue(info['uses_real_capital'])
        self.assertTrue(info['requires_confirmation'])


class TestTradingModes(unittest.TestCase):
    """Test cases for TradingMode enum and TradingConfig."""
    
    def test_trading_mode_properties(self):
        """Test TradingMode properties."""
        # BACKTEST
        self.assertTrue(TradingMode.BACKTEST.is_simulated)
        self.assertFalse(TradingMode.BACKTEST.uses_real_capital)
        self.assertTrue(TradingMode.BACKTEST.is_read_only)
        
        # PAPER
        self.assertTrue(TradingMode.PAPER.is_simulated)
        self.assertFalse(TradingMode.PAPER.uses_real_capital)
        self.assertTrue(TradingMode.PAPER.is_read_only)
        
        # SHADOW
        self.assertTrue(TradingMode.SHADOW.is_simulated)
        self.assertFalse(TradingMode.SHADOW.uses_real_capital)
        self.assertTrue(TradingMode.SHADOW.is_read_only)
        
        # LIVE
        self.assertFalse(TradingMode.LIVE.is_simulated)
        self.assertTrue(TradingMode.LIVE.uses_real_capital)
        self.assertFalse(TradingMode.LIVE.is_read_only)
    
    def test_config_validation(self):
        """Test configuration validation."""
        config = TradingConfig.default_for_mode(TradingMode.PAPER)
        self.assertTrue(config.validate())
    
    def test_invalid_config(self):
        """Test invalid configuration detection."""
        config = TradingConfig.default_for_mode(TradingMode.PAPER)
        config.initial_capital = -100  # Invalid
        
        with self.assertRaises(ValueError):
            config.validate()
    
    def test_config_log_configuration(self):
        """Test configuration logging."""
        config = TradingConfig.default_for_mode(TradingMode.PAPER)
        # Should not raise
        config.log_configuration()


if __name__ == '__main__':
    unittest.main()
