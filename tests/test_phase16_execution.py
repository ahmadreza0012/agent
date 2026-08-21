"""
Unit tests for Phase 16 Execution Engine.

This module contains comprehensive tests for all execution engine components:
- Exchange Adapter (with mock implementation)
- Order Manager
- Position Manager
- Fill Manager
- Portfolio Reconciler
"""

import sys
sys.path.insert(0, '/workspace')

import unittest
from datetime import datetime
from typing import Dict, List, Optional

from execution import (
    ExchangeAdapter,
    OrderManager,
    PositionManager,
    FillManager,
    PortfolioReconciler,
    Order,
    OrderSide,
    OrderType,
    OrderStatus,
    Balance,
    Position,
    ReconciliationResult,
    PositionLimits,
)


class MockExchangeAdapter(ExchangeAdapter):
    """Mock exchange adapter for testing."""
    
    def __init__(self, config=None):
        super().__init__(config or {})
        self.balances = {
            'USDT': Balance('USDT', 10000.0, 10000.0, 0.0),
            'BTC': Balance('BTC', 1.0, 1.0, 0.0),
            'ETH': Balance('ETH', 10.0, 10.0, 0.0),
        }
        self.positions = []
        self.orders = {}
        self.order_counter = 0
        self._next_order_status = OrderStatus.FILLED
        self._should_fail = False
        self._fail_count = 0
    
    def set_next_order_status(self, status: OrderStatus):
        """Set the status for the next created order."""
        self._next_order_status = status
    
    def set_should_fail(self, fail: bool):
        """Configure whether operations should fail."""
        self._should_fail = fail
    
    def get_balance(self, asset=None):
        if self._should_fail:
            raise ConnectionError("Mock connection error")
        if asset:
            return {asset: self.balances.get(asset, Balance(asset, 0.0, 0.0, 0.0))}
        return self.balances
    
    def get_positions(self):
        if self._should_fail:
            raise ConnectionError("Mock connection error")
        return self.positions
    
    def get_ticker(self, symbol):
        if self._should_fail:
            raise ConnectionError("Mock connection error")
        return {'symbol': symbol, 'price': 50000.0, 'volume': 1000.0}
    
    def create_order(self, symbol, side, order_type, amount, price=None, client_order_id=None):
        if self._should_fail:
            self._fail_count += 1
            raise ConnectionError("Mock connection error")
        
        self.order_counter += 1
        filled_amount = amount if self._next_order_status == OrderStatus.FILLED else 0.0
        
        order = Order(
            id=f"mock_{self.order_counter}",
            client_order_id=client_order_id or f"client_{self.order_counter}",
            symbol=symbol,
            side=side,
            type=order_type,
            price=price or 50000.0,
            amount=amount,
            filled_amount=filled_amount,
            status=self._next_order_status,
            timestamp=datetime.now(),
        )
        self.orders[order.id] = order
        return order
    
    def cancel_order(self, order_id, symbol=None):
        if self._should_fail:
            raise ConnectionError("Mock connection error")
        if order_id in self.orders:
            self.orders[order_id].status = OrderStatus.CANCELLED
            return True
        return False
    
    def get_order(self, order_id, symbol=None):
        if self._should_fail:
            raise ConnectionError("Mock connection error")
        return self.orders.get(order_id)
    
    def health_check(self):
        return not self._should_fail


class TestOrderManager(unittest.TestCase):
    """Tests for OrderManager."""
    
    def setUp(self):
        self.adapter = MockExchangeAdapter()
        self.manager = OrderManager(self.adapter)
    
    def test_create_market_order(self):
        """Test creating a market order."""
        order = self.manager.create_order('BTC/USDT', OrderSide.BUY, OrderType.MARKET, 0.1)
        self.assertEqual(order.status, OrderStatus.FILLED)
        self.assertEqual(order.amount, 0.1)
        self.assertIsNotNone(order.client_order_id)
    
    def test_create_limit_order(self):
        """Test creating a limit order."""
        self.adapter.set_next_order_status(OrderStatus.OPEN)
        order = self.manager.create_order('BTC/USDT', OrderSide.BUY, OrderType.LIMIT, 0.1, 49000.0)
        self.assertEqual(order.status, OrderStatus.OPEN)
        self.assertEqual(order.price, 49000.0)
    
    def test_idempotency(self):
        """Test that duplicate client_order_id returns existing order."""
        client_id = "test_client_123"
        order1 = self.manager.create_order(
            'BTC/USDT', OrderSide.BUY, OrderType.MARKET, 0.1, client_order_id=client_id
        )
        order2 = self.manager.create_order(
            'BTC/USDT', OrderSide.BUY, OrderType.MARKET, 0.1, client_order_id=client_id
        )
        self.assertEqual(order1.id, order2.id)
    
    def test_cancel_order(self):
        """Test cancelling an order."""
        self.adapter.set_next_order_status(OrderStatus.OPEN)
        order = self.manager.create_order(
            'BTC/USDT', OrderSide.BUY, OrderType.LIMIT, 0.1, 49000.0
        )
        result = self.manager.cancel_order(order.id)
        self.assertTrue(result)
        updated = self.manager.get_order(order.id)
        self.assertEqual(updated.status, OrderStatus.CANCELLED)
    
    def test_get_open_orders(self):
        """Test getting open orders."""
        self.adapter.set_next_order_status(OrderStatus.OPEN)
        order1 = self.manager.create_order(
            'BTC/USDT', OrderSide.BUY, OrderType.LIMIT, 0.1, 49000.0
        )
        order2 = self.manager.create_order(
            'ETH/USDT', OrderSide.BUY, OrderType.LIMIT, 1.0, 2000.0
        )
        open_orders = self.manager.get_open_orders()
        self.assertEqual(len(open_orders), 2)
    
    def test_is_order_complete(self):
        """Test checking if order is complete."""
        # Filled order should be complete
        order1 = self.manager.create_order(
            'BTC/USDT', OrderSide.BUY, OrderType.MARKET, 0.1
        )
        self.assertTrue(self.manager.is_order_complete(order1.id))
        
        # Open order should not be complete
        self.adapter.set_next_order_status(OrderStatus.OPEN)
        order2 = self.manager.create_order(
            'BTC/USDT', OrderSide.BUY, OrderType.LIMIT, 0.1, 49000.0
        )
        self.assertFalse(self.manager.is_order_complete(order2.id))


class TestPositionManager(unittest.TestCase):
    """Tests for PositionManager."""
    
    def setUp(self):
        self.manager = PositionManager()
    
    def test_create_position(self):
        """Test creating a new position."""
        self.manager.update_position('BTC/USDT', 50000.0, 0.1, OrderSide.BUY)
        pos = self.manager.get_position('BTC/USDT')
        self.assertEqual(pos.size, 0.1)
        self.assertEqual(pos.entry_price, 50000.0)
    
    def test_increase_position(self):
        """Test increasing a position."""
        self.manager.update_position('BTC/USDT', 50000.0, 0.1, OrderSide.BUY)
        self.manager.update_position('BTC/USDT', 51000.0, 0.1, OrderSide.BUY)
        pos = self.manager.get_position('BTC/USDT')
        self.assertEqual(pos.size, 0.2)
        self.assertEqual(pos.entry_price, 50500.0)  # Weighted average
    
    def test_decrease_position(self):
        """Test decreasing a position."""
        self.manager.update_position('BTC/USDT', 50000.0, 0.1, OrderSide.BUY)
        self.manager.update_position('BTC/USDT', 51000.0, 0.05, OrderSide.SELL)
        pos = self.manager.get_position('BTC/USDT')
        self.assertEqual(pos.size, 0.05)
        self.assertEqual(pos.entry_price, 50000.0)  # Remains unchanged for sells
    
    def test_close_position(self):
        """Test closing a position."""
        self.manager.update_position('BTC/USDT', 50000.0, 0.1, OrderSide.BUY)
        realized_pnl = self.manager.close_position('BTC/USDT')
        pos = self.manager.get_position('BTC/USDT')
        self.assertEqual(pos.size, 0.0)
        self.assertIsNotNone(realized_pnl)
    
    def test_unrealized_pnl(self):
        """Test unrealized PnL calculation."""
        self.manager.update_position('BTC/USDT', 50000.0, 0.1, OrderSide.BUY)
        pnl = self.manager.calculate_unrealized_pnl('BTC/USDT', 52000.0)
        self.assertEqual(pnl, 200.0)  # 0.1 * (52000 - 50000)
    
    def test_position_limits(self):
        """Test position limits enforcement."""
        limits = PositionLimits(max_position_size=0.5)
        manager = PositionManager(limits=limits)
        
        # This should succeed
        manager.update_position('BTC/USDT', 50000.0, 0.3, OrderSide.BUY)
        
        # This should fail (exceeds limit)
        with self.assertRaises(ValueError):
            manager.update_position('BTC/USDT', 50000.0, 0.3, OrderSide.BUY)


class TestFillManager(unittest.TestCase):
    """Tests for FillManager."""
    
    def setUp(self):
        self.adapter = MockExchangeAdapter()
        self.order_manager = OrderManager(self.adapter)
        self.position_manager = PositionManager()
        self.fill_manager = FillManager(self.position_manager, self.order_manager)
    
    def test_process_full_fill(self):
        """Test processing a full fill."""
        order = self.order_manager.create_order(
            'BTC/USDT', OrderSide.BUY, OrderType.MARKET, 0.1
        )
        fill = {'price': 50000.0, 'amount': 0.1, 'fee': {'cost': 0.01, 'currency': 'USDT'}}
        self.fill_manager.process_fill(order, fill)
        pos = self.position_manager.get_position('BTC/USDT')
        self.assertEqual(pos.size, 0.1)
    
    def test_process_partial_fill(self):
        """Test processing a partial fill."""
        self.adapter.set_next_order_status(OrderStatus.PARTIALLY_FILLED)
        order = self.order_manager.create_order(
            'BTC/USDT', OrderSide.BUY, OrderType.LIMIT, 0.1, 50000.0
        )
        fill = {'price': 50000.0, 'amount': 0.04, 'fee': {'cost': 0.004, 'currency': 'USDT'}}
        self.fill_manager.process_fill(order, fill)
        pos = self.position_manager.get_position('BTC/USDT')
        self.assertEqual(pos.size, 0.04)
    
    def test_is_order_fully_filled(self):
        """Test checking if order is fully filled."""
        order = self.order_manager.create_order(
            'BTC/USDT', OrderSide.BUY, OrderType.MARKET, 0.1
        )
        self.assertTrue(self.fill_manager.is_order_fully_filled(order))
    
    def test_get_total_fees(self):
        """Test calculating total fees."""
        order = self.order_manager.create_order(
            'BTC/USDT', OrderSide.BUY, OrderType.MARKET, 0.1
        )
        fill = {'price': 50000.0, 'amount': 0.1, 'fee': {'cost': 5.0, 'currency': 'USDT'}}
        self.fill_manager.process_fill(order, fill)
        total_fees = self.fill_manager.get_total_fees(order.id)
        self.assertEqual(total_fees, 5.0)


class TestReconciler(unittest.TestCase):
    """Tests for PortfolioReconciler."""
    
    def setUp(self):
        self.adapter = MockExchangeAdapter()
        self.position_manager = PositionManager()
        self.reconciler = PortfolioReconciler(self.adapter, self.position_manager)
    
    def test_reconcile_consistent(self):
        """Test reconciliation when states match."""
        # Set up matching state (both empty)
        result = self.reconciler.reconcile()
        self.assertTrue(result.is_consistent)
    
    def test_detect_mismatch(self):
        """Test mismatch detection."""
        # Add local position but exchange has none
        self.position_manager.update_position('BTC/USDT', 50000.0, 0.1, OrderSide.BUY)
        result = self.reconciler.reconcile()
        self.assertFalse(result.is_consistent)
        self.assertGreater(len(result.position_mismatches), 0)
    
    def test_get_reconciliation_status(self):
        """Test getting reconciliation status."""
        status = self.reconciler.get_reconciliation_status()
        self.assertEqual(status['status'], 'never_reconciled')
        
        # Perform reconciliation
        self.reconciler.reconcile()
        status = self.reconciler.get_reconciliation_status()
        self.assertEqual(status['status'], 'reconciled')


class TestExecutionFlow(unittest.TestCase):
    """Integration tests for full execution flow."""
    
    def setUp(self):
        self.adapter = MockExchangeAdapter()
        self.order_manager = OrderManager(self.adapter)
        self.position_manager = PositionManager()
        self.fill_manager = FillManager(self.position_manager, self.order_manager)
        self.reconciler = PortfolioReconciler(self.adapter, self.position_manager)
    
    def test_full_execution_flow(self):
        """Test complete execution flow from order to reconciliation."""
        # Create order
        order = self.order_manager.create_order(
            'BTC/USDT', OrderSide.BUY, OrderType.MARKET, 0.1
        )
        
        # Process fill
        fill_data = {'price': 50000.0, 'amount': 0.1, 'fee': {'cost': 5.0, 'currency': 'USDT'}}
        self.fill_manager.process_fill(order, fill_data)
        
        # Verify position was updated
        pos = self.position_manager.get_position('BTC/USDT')
        self.assertEqual(pos.size, 0.1)
        
        # Verify order is complete
        self.assertTrue(self.order_manager.is_order_complete(order.id))
    
    def test_duplicate_order_prevention(self):
        """Test that duplicate orders are prevented."""
        client_id = "unique_client_id_123"
        
        # Create first order
        order1 = self.order_manager.create_order(
            'BTC/USDT', OrderSide.BUY, OrderType.MARKET, 0.1, client_order_id=client_id
        )
        
        # Try to create duplicate
        order2 = self.order_manager.create_order(
            'BTC/USDT', OrderSide.BUY, OrderType.MARKET, 0.1, client_order_id=client_id
        )
        
        # Should return same order
        self.assertEqual(order1.id, order2.id)


if __name__ == '__main__':
    unittest.main(verbosity=2)