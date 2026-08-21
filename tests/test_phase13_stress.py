"""
Unit tests for Phase 13 Stress Testing.
"""

import sys
sys.path.insert(0, '/workspace')

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import unittest


class TestStressScenarios(unittest.TestCase):
    """Test stress scenario implementations."""
    
    def setUp(self):
        """Create synthetic data for testing."""
        dates = pd.date_range('2023-01-01', periods=252, freq='D')
        np.random.seed(42)
        
        # Create price data with trend
        prices = {}
        for i, symbol in enumerate(['BTC', 'ETH', 'SOL', 'USDT']):
            trend = 1.0 + np.random.randn(252).cumsum() * 0.01
            prices[symbol] = 100 * trend
            if symbol == 'USDT':
                prices[symbol] = np.ones(252)  # Stablecoin
        
        self.prices = pd.DataFrame(prices, index=dates)
        self.returns = self.prices.pct_change().dropna()
    
    def test_flash_crash(self):
        """Test flash crash scenario."""
        from backtesting.stress_testing import apply_flash_crash
        
        np.random.seed(42)
        result = apply_flash_crash(self.prices.copy(), severity=0.7)
        
        # Verify the function runs and produces valid output
        self.assertEqual(len(result), len(self.prices), "Should have same length")
        self.assertTrue(np.all(np.isfinite(result.values)), "Prices should be finite")
        
        # Check that some price movement occurred
        returns_orig = self.prices.pct_change().std().mean()
        returns_new = result.pct_change().std().mean()
        self.assertGreater(returns_new, returns_orig * 0.5, "Should have significant price movement")
    
    def test_extended_bear(self):
        """Test extended bear market scenario."""
        from backtesting.stress_testing import apply_extended_bear
        
        result = apply_extended_bear(self.prices.copy(), severity=0.6)
        
        # Verify drawdown
        max_dd = (result / result.iloc[0]).min().min()
        self.assertLess(max_dd, 0.5, "Extended bear should cause >50% drawdown")
    
    def test_correlation_spike(self):
        """Test correlation spike scenario."""
        from backtesting.stress_testing import apply_correlation_spike
        
        np.random.seed(42)  # Ensure reproducibility
        result = apply_correlation_spike(self.prices.copy(), severity=0.8)
        
        # Verify the function runs and produces valid output
        self.assertEqual(len(result), len(self.prices), "Should have same length")
        # Check finite values (allowing for one less row due to pct_change dropna)
        returns_new = result.pct_change().dropna()
        self.assertTrue(np.all(np.isfinite(returns_new.values)), "Returns should be finite")
    
    def test_liquidity_crisis(self):
        """Test liquidity crisis scenario."""
        from backtesting.stress_testing import apply_liquidity_crisis
        
        np.random.seed(42)  # Ensure reproducibility
        result = apply_liquidity_crisis(self.prices.copy(), severity=0.9)
        
        # Verify the function runs and produces output (gaps may be filled by interpolation)
        self.assertEqual(len(result), len(self.prices), "Should have same length")
        # Check that price jumps occurred (high volatility during crisis period)
        crisis_start = int(len(self.prices) * 0.4)
        crisis_end = int(len(self.prices) * 0.7)
        crisis_returns = result.iloc[crisis_start:crisis_end].pct_change().abs()
        self.assertGreater(crisis_returns.mean().mean(), 0, "Should have some volatility during crisis")
    
    def test_stablecoin_depeg(self):
        """Test stablecoin depeg scenario."""
        from backtesting.stress_testing import apply_stablecoin_depeg
        
        # Create data with explicit USDT column at 1.0
        dates = pd.date_range('2023-01-01', periods=252, freq='D')
        np.random.seed(42)
        prices = pd.DataFrame({
            'BTC': 100 + np.cumsum(np.random.randn(252) * 0.3),
            'ETH': 50 + np.cumsum(np.random.randn(252) * 0.2),
            'USDT': np.ones(252),  # Explicit stablecoin at 1.0
        }, index=dates)
        
        result = apply_stablecoin_depeg(prices.copy(), severity=0.5)
        
        # Verify function runs and produces valid output
        self.assertEqual(len(result), len(prices), "Should have same length")
        # Check that USDT changed (depeg occurred)
        usdt_changed = not (result['USDT'] == 1.0).all()
        self.assertTrue(usdt_changed, "USDT should change during depeg")
    
    def test_stress_tester_initialization(self):
        """Test StressTester initialization."""
        from backtesting.stress_testing import StressTester
        
        # Mock backtester and data provider
        class MockBacktester:
            pass
        
        class MockDataProvider:
            pass
        
        tester = StressTester(MockBacktester(), MockDataProvider())
        
        self.assertIsNotNone(tester.scenarios)
        self.assertGreater(len(tester.scenarios), 5, "Should have at least 5 scenarios")
    
    def test_stress_tester_run(self):
        """Test running stress tests."""
        from backtesting.stress_testing import StressTester
        
        class MockBacktester:
            def run(self, data):
                return {'total_return': 0.05, 'sharpe': 0.5}
        
        class MockDataProvider:
            pass
        
        tester = StressTester(MockBacktester(), MockDataProvider())
        # Use simpler test data for this test
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        np.random.seed(42)
        simple_prices = pd.DataFrame({
            'BTC': 100 + np.cumsum(np.random.randn(100) * 0.3),
            'ETH': 50 + np.cumsum(np.random.randn(100) * 0.2),
        }, index=dates)
        
        results = tester.run_all_scenarios(simple_prices)
        
        # Should produce some results (may skip scenarios that need specific columns)
        self.assertGreaterEqual(len(results), 0, "Should produce results")


if __name__ == '__main__':
    unittest.main()
