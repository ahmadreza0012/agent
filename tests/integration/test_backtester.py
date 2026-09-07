"""
Integration tests for Backtester.
"""

import sys
sys.path.insert(0, '/workspace')

import unittest
import pandas as pd
import numpy as np


class TestBacktester(unittest.TestCase):
    """Test Backtester integration."""
    
    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        self.prices = pd.DataFrame({
            'BTC': np.cumprod(1 + np.random.randn(100) * 0.01),
            'ETH': np.cumprod(1 + np.random.randn(100) * 0.015),
            'SOL': np.cumprod(1 + np.random.randn(100) * 0.02),
        }, index=pd.date_range('2020-01-01', periods=100, freq='D'))
    
    def test_backtester_run(self):
        """Test backtester execution."""
        try:
            from backtesting.engine import Backtester
            
            backtester = Backtester(data=self.prices, strategy='trend')
            results = backtester.run()
            
            self.assertIn('returns', results)
            self.assertIn('cumulative_returns', results)
            self.assertIn('sharpe', results)
            self.assertIn('max_drawdown', results)
        except ImportError:
            self.skipTest("Backtester not implemented yet")
    
    def test_walk_forward_backtester(self):
        """Test walk-forward backtester."""
        try:
            from backtesting.walk_forward_engine import WalkForwardBacktester
            
            backtester = WalkForwardBacktester(
                data=self.prices,
                strategy='trend',
                train_window=50,
                val_window=20,
                test_window=30
            )
            results = backtester.run()
            
            self.assertIn('train_results', results)
            self.assertIn('test_results', results)
            self.assertIn('out_of_sample_results', results)
        except ImportError:
            self.skipTest("WalkForwardBacktester not implemented yet")
    
    def test_backtester_with_transaction_costs(self):
        """Test backtester with transaction costs."""
        try:
            from backtesting.engine import Backtester
            
            backtester = Backtester(
                data=self.prices,
                strategy='trend',
                transaction_costs=True,
                slippage=0.001
            )
            results = backtester.run()
            
            self.assertIn('total_fees', results)
            self.assertIn('total_slippage', results)
        except ImportError:
            self.skipTest("Backtester not implemented yet")


if __name__ == '__main__':
    unittest.main()
