"""
Unit tests for return calculations.
"""

import sys
sys.path.insert(0, '/workspace')

import unittest
import pandas as pd
import numpy as np


class TestReturns(unittest.TestCase):
    """Test return calculation functions."""
    
    def setUp(self):
        """Create test price data."""
        np.random.seed(42)
        self.prices = pd.Series(
            np.cumprod(1 + np.random.randn(100) * 0.01),
            index=pd.date_range('2020-01-01', periods=100, freq='D')
        )
        self.weights = pd.Series([0.5, 0.3, 0.2], index=['BTC', 'ETH', 'SOL'])
        self.asset_prices = pd.DataFrame({
            'BTC': np.cumprod(1 + np.random.randn(100) * 0.01),
            'ETH': np.cumprod(1 + np.random.randn(100) * 0.015),
            'SOL': np.cumprod(1 + np.random.randn(100) * 0.02),
        }, index=pd.date_range('2020-01-01', periods=100, freq='D'))
    
    def test_simple_returns(self):
        """Test simple return calculation."""
        from utils.returns import simple_returns
        returns = simple_returns(self.prices)
        self.assertEqual(len(returns), len(self.prices) - 1)
        self.assertTrue((returns >= -1).all())
    
    def test_log_returns(self):
        """Test log return calculation."""
        from utils.returns import log_returns
        returns = log_returns(self.prices)
        self.assertEqual(len(returns), len(self.prices) - 1)
        # Log returns should be approximately equal to simple returns for small changes
        simple = simple_returns(self.prices)
        np.testing.assert_almost_equal(returns, np.log(1 + simple), decimal=6)
    
    def test_cumulative_returns(self):
        """Test cumulative return calculation."""
        from utils.returns import simple_returns, cumulative_returns
        returns = simple_returns(self.prices)
        cum = cumulative_returns(returns)
        self.assertEqual(len(cum), len(returns))
        self.assertAlmostEqual(
            cum.iloc[-1],
            self.prices.iloc[-1] / self.prices.iloc[0] - 1,
            places=6
        )
    
    def test_portfolio_returns(self):
        """Test portfolio return calculation."""
        from utils.returns import simple_returns, portfolio_returns
        returns = simple_returns(self.asset_prices)
        portfolio = portfolio_returns(returns, self.weights)
        self.assertEqual(len(portfolio), len(returns))
        # Portfolio return should be weighted sum of asset returns
        expected = returns.dot(self.weights)
        pd.testing.assert_series_equal(portfolio, expected)
    
    def test_annualized_returns(self):
        """Test annualized return calculation."""
        from utils.returns import simple_returns, annualized_returns
        from utils.timeframe import detect_frequency
        freq = detect_frequency(self.prices)
        returns = simple_returns(self.prices)
        ann_ret = annualized_returns(returns, freq)
        self.assertIsInstance(ann_ret, float)
    
    def test_sharpe_ratio(self):
        """Test Sharpe ratio calculation."""
        from utils.returns import simple_returns, sharpe_ratio
        from utils.timeframe import detect_frequency
        freq = detect_frequency(self.prices)
        returns = simple_returns(self.prices)
        sharpe = sharpe_ratio(returns, freq, risk_free_rate=0.0)
        self.assertIsInstance(sharpe, float)
        # Sharpe ratio should be reasonable
        self.assertGreater(sharpe, -10)
        self.assertLess(sharpe, 10)
    
    def test_sortino_ratio(self):
        """Test Sortino ratio calculation."""
        from utils.returns import simple_returns, sortino_ratio
        from utils.timeframe import detect_frequency
        freq = detect_frequency(self.prices)
        returns = simple_returns(self.prices)
        sortino = sortino_ratio(returns, freq, risk_free_rate=0.0)
        self.assertIsInstance(sortino, float)


if __name__ == '__main__':
    unittest.main()
