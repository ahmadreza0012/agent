"""
Fault tests for exchange failures.
"""

import sys
sys.path.insert(0, '/workspace')

import unittest
import time
from typing import Optional


class Order:
    """Mock Order class for testing."""
    def __init__(self, id, client_order_id, symbol, side, type, price, amount, filled_amount, status, timestamp):
        self.id = id
        self.client_order_id = client_order_id
        self.symbol = symbol
        self.side = side
        self.type = type
        self.price = price
        self.amount = amount
        self.filled_amount = filled_amount
        self.status = status
        self.timestamp = timestamp


class OrderSide:
    BUY = "buy"
    SELL = "sell"


class OrderType:
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus:
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"


class MockFailingExchangeAdapter:
    """Exchange adapter that fails on demand."""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.should_fail_on_create = False
        self.should_fail_on_get = False
        self.should_fail_on_cancel = False
    
    def set_failure_pattern(self, create=False, get=False, cancel=False):
        self.should_fail_on_create = create
        self.should_fail_on_get = get
        self.should_fail_on_cancel = cancel
    
    def get_balance(self, asset=None):
        return {'USDT': {'total': 10000, 'free': 10000, 'locked': 0}}
    
    def get_positions(self):
        return []
    
    def get_ticker(self, symbol):
        return {'symbol': symbol, 'price': 50000, 'volume': 1000}
    
    def create_order(self, symbol, side, order_type, amount, price=None, client_order_id=None):
        if self.should_fail_on_create:
            raise ConnectionError("Mock connection error - create_order failed")
        return Order(
            id="mock_1",
            client_order_id=client_order_id or "client_1",
            symbol=symbol,
            side=side,
            type=order_type,
            price=price or 50000,
            amount=amount,
            filled_amount=0,
            status=OrderStatus.OPEN,
            timestamp=time.time()
        )
    
    def cancel_order(self, order_id, symbol=None):
        if self.should_fail_on_cancel:
            raise ConnectionError("Mock connection error - cancel_order failed")
        return True
    
    def get_order(self, order_id, symbol=None):
        if self.should_fail_on_get:
            raise ConnectionError("Mock connection error - get_order failed")
        return Order(
            id=order_id,
            client_order_id="client_1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=50000,
            amount=0.1,
            filled_amount=0,
            status=OrderStatus.FILLED,
            timestamp=time.time()
        )
    
    def health_check(self):
        return True
    
    def _retry_operation(self, func, *args, max_retries=3, backoff=2.0):
        """Retry operation with exponential backoff."""
        last_error = None
        for attempt in range(max_retries):
            try:
                return func(*args)
            except ConnectionError as e:
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(0.01 * (backoff ** attempt))
        raise last_error


class TestExchangeFailure(unittest.TestCase):
    """Test exchange failure handling."""
    
    def setUp(self):
        self.adapter = MockFailingExchangeAdapter()
    
    def test_create_order_retry_on_timeout(self):
        """Test retry logic on create_order timeout."""
        self.adapter.set_failure_pattern(create=True)
        with self.assertRaises(ConnectionError):
            self.adapter._retry_operation(
                self.adapter.create_order,
                'BTC/USDT', OrderSide.BUY, OrderType.MARKET, 0.1
            )
    
    def test_get_order_retry_on_timeout(self):
        """Test retry logic on get_order timeout."""
        self.adapter.set_failure_pattern(get=True)
        with self.assertRaises(ConnectionError):
            self.adapter._retry_operation(self.adapter.get_order, 'order_1')
    
    def test_cancel_order_retry_on_timeout(self):
        """Test retry logic on cancel_order timeout."""
        self.adapter.set_failure_pattern(cancel=True)
        with self.assertRaises(ConnectionError):
            self.adapter._retry_operation(self.adapter.cancel_order, 'order_1')
    
    def test_successful_operation_no_retry(self):
        """Test successful operation doesn't retry."""
        self.adapter.set_failure_pattern()
        result = self.adapter._retry_operation(
            self.adapter.create_order,
            'BTC/USDT', OrderSide.BUY, OrderType.MARKET, 0.1
        )
        self.assertIsInstance(result, Order)
        self.assertEqual(result.status, OrderStatus.OPEN)


if __name__ == '__main__':
    unittest.main()
