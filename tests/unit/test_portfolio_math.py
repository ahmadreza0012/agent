"""
Unit tests for portfolio math functions.
"""

import sys
sys.path.insert(0, '/workspace')

import unittest
import numpy as np
import pandas as np


class TestMVO(unittest.TestCase):
    """Test Mean-Variance Optimization."""
    
    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        self.returns = pd.DataFrame({
            'Asset1': np.random.randn(100) * 0.01,
            'Asset2': np.random.randn(100) * 0.015,
            'Asset3': np.random.randn(100) * 0.02,
        })
        # Add some correlation
        self.returns['Asset2'] += self.returns['Asset1'] * 0.3
        self.returns['Asset3'] += self.returns['Asset1'] * 0.1 + self.returns['Asset2'] * 0.2
        from utils.timeframe import detect_frequency
        self.freq = detect_frequency(self.returns)
    
    def test_mvo_weights_sum_to_one(self):
        """Test MVO weights sum to 1."""
        try:
            from portfolio.optimizer import MVO
            optimizer = MVO(returns=self.returns, freq=self.freq)
            weights = optimizer.optimize()
            self.assertAlmostEqual(weights.sum(), 1.0, places=6)
        except ImportError:
            self.skipTest("MVO not implemented yet")
    
    def test_mvo_weights_non_negative(self):
        """Test MVO weights are non-negative."""
        try:
            from portfolio.optimizer import MVO
            optimizer = MVO(returns=self.returns, freq=self.freq)
            weights = optimizer.optimize()
            self.assertTrue((weights >= 0).all())
        except ImportError:
            self.skipTest("MVO not implemented yet")


class TestRiskParity(unittest.TestCase):
    """Test Risk Parity optimization."""
    
    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        self.returns = pd.DataFrame({
            'Asset1': np.random.randn(100) * 0.01,
            'Asset2': np.random.randn(100) * 0.015,
            'Asset3': np.random.randn(100) * 0.02,
        })
        from utils.timeframe import detect_frequency
        self.freq = detect_frequency(self.returns)
    
    def test_risk_parity_weights_sum_to_one(self):
        """Test Risk Parity weights sum to 1."""
        try:
            from portfolio.optimizer import RiskParity
            optimizer = RiskParity(returns=self.returns, freq=self.freq)
            weights = optimizer.optimize()
            self.assertAlmostEqual(weights.sum(), 1.0, places=6)
        except ImportError:
            self.skipTest("RiskParity not implemented yet")


class TestCVaR(unittest.TestCase):
    """Test Conditional Value at Risk optimization."""
    
    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        self.returns = pd.DataFrame({
            'Asset1': np.random.randn(100) * 0.01,
            'Asset2': np.random.randn(100) * 0.015,
            'Asset3': np.random.randn(100) * 0.02,
        })
        from utils.timeframe import detect_frequency
        self.freq = detect_frequency(self.returns)
    
    def test_cvar_weights_sum_to_one(self):
        """Test CVaR weights sum to 1."""
        try:
            from portfolio.optimizer import CVaR
            optimizer = CVaR(returns=self.returns, freq=self.freq, confidence_level=0.95)
            weights = optimizer.optimize()
            self.assertAlmostEqual(weights.sum(), 1.0, places=6)
        except ImportError:
            self.skipTest("CVaR not implemented yet")


if __name__ == '__main__':
    unittest.main()
