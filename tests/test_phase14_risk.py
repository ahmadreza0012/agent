"""
Unit tests for Phase 14 Risk Engine.
"""

import sys
sys.path.insert(0, '/workspace')

import unittest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta


class TestRiskLimits(unittest.TestCase):
    """Test risk limits configuration."""
    
    def setUp(self):
        from risk.risk_limits import RiskLimits, DEFAULT_LIMITS
        self.limits = RiskLimits()
        self.default_limits = DEFAULT_LIMITS
    
    def test_default_limits(self):
        """Test default limit values."""
        self.assertEqual(self.limits.max_gross_exposure, 1.0)
        self.assertEqual(self.limits.max_single_position, 0.20)
        self.assertEqual(self.limits.max_drawdown, 0.12)
        self.assertEqual(self.limits.max_volatility, 0.50)
    
    def test_mode_limits(self):
        """Test mode-specific limits."""
        live_limits = self.default_limits['live']
        self.assertEqual(live_limits.max_drawdown, 0.10)
        self.assertEqual(live_limits.max_single_position, 0.20)
        
        research_limits = self.default_limits['research']
        self.assertEqual(research_limits.max_drawdown, 0.25)
        self.assertEqual(research_limits.max_single_position, 0.40)
    
    def test_update_limits(self):
        """Test updating limits."""
        self.limits.update(max_drawdown=0.15, max_single_position=0.25)
        self.assertEqual(self.limits.max_drawdown, 0.15)
        self.assertEqual(self.limits.max_single_position, 0.25)


class TestRiskMetrics(unittest.TestCase):
    """Test risk metrics calculation."""
    
    def setUp(self):
        from risk.risk_metrics import calculate_risk_metrics
        
        np.random.seed(42)
        dates = pd.date_range('2023-01-01', periods=252, freq='D')
        self.returns = pd.DataFrame({
            'BTC': np.random.randn(252) * 0.02,
            'ETH': np.random.randn(252) * 0.025,
            'SOL': np.random.randn(252) * 0.03,
        }, index=dates)
        
        self.prices = 100 + self.returns.cumsum()
        self.weights = {'BTC': 0.5, 'ETH': 0.3, 'SOL': 0.2}
    
    def test_calculate_metrics(self):
        """Test risk metrics calculation."""
        from risk.risk_metrics import calculate_risk_metrics
        
        metrics = calculate_risk_metrics(
            portfolio_weights=self.weights,
            asset_returns=self.returns,
            asset_prices=self.prices,
        )
        
        self.assertAlmostEqual(metrics.gross_exposure, 1.0)
        self.assertAlmostEqual(metrics.max_position, 0.5)
        self.assertEqual(metrics.max_position_asset, 'BTC')
        self.assertGreater(metrics.portfolio_volatility, 0)
        self.assertLessEqual(metrics.hhi, 1.0)
    
    def test_concentration_metrics(self):
        """Test concentration metrics."""
        from risk.risk_metrics import calculate_risk_metrics
        
        concentrated_weights = {'BTC': 0.8, 'ETH': 0.1, 'SOL': 0.1}
        metrics = calculate_risk_metrics(
            portfolio_weights=concentrated_weights,
            asset_returns=self.returns,
            asset_prices=self.prices,
        )
        
        self.assertGreater(metrics.hhi, 0.6)
        self.assertAlmostEqual(metrics.max_position, 0.8)
    
    def test_correlation_metrics(self):
        """Test correlation metrics."""
        from risk.risk_metrics import calculate_risk_metrics
        
        metrics = calculate_risk_metrics(
            portfolio_weights=self.weights,
            asset_returns=self.returns,
            asset_prices=self.prices,
        )
        
        self.assertIsNotNone(metrics.correlation_matrix)
        self.assertGreaterEqual(metrics.avg_correlation, -1)
        self.assertLessEqual(metrics.avg_correlation, 1)


class TestRiskEngine(unittest.TestCase):
    """Test Risk Engine functionality."""
    
    def setUp(self):
        from risk.risk_engine import RiskEngine
        from risk.risk_limits import RiskLimits
        
        self.engine = RiskEngine(mode='research')
        
        np.random.seed(42)
        dates = pd.date_range('2023-01-01', periods=252, freq='D')
        self.returns = pd.DataFrame({
            'BTC': np.random.randn(252) * 0.02,
            'ETH': np.random.randn(252) * 0.025,
            'SOL': np.random.randn(252) * 0.03,
        }, index=dates)
        self.prices = 100 + self.returns.cumsum()
        # Use more diversified weights within research mode limits (HHI < 0.25)
        # HHI = 0.33^2 + 0.33^2 + 0.34^2 = 0.333, still > 0.25
        # Need more equal: 0.33 each gives HHI = 0.33
        # For HHI < 0.25 with 3 assets, need roughly equal: 1/3 each = 0.333 -> HHI = 0.333
        # Actually need more assets or lower concentration. Let's use 4 assets.
        self.weights = {'BTC': 0.25, 'ETH': 0.25, 'SOL': 0.25, 'ADA': 0.25}
        
        # Add ADA to returns and prices
        self.returns['ADA'] = np.random.randn(252) * 0.028
        self.prices['ADA'] = 100 + self.returns['ADA'].cumsum()
        
        self.market_data = {
            'BTC': {'volume': 100000, 'spread': 0.001},
            'ETH': {'volume': 100000, 'spread': 0.001},
            'SOL': {'volume': 100000, 'spread': 0.001},
            'ADA': {'volume': 100000, 'spread': 0.001},
        }
    
    def test_normal_evaluation(self):
        """Test normal risk evaluation."""
        decision = self.engine.evaluate(
            portfolio_weights=self.weights,
            asset_returns=self.returns,
            asset_prices=self.prices,
            market_data=self.market_data,
        )
        
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.risk_multiplier, 1.0)
        self.assertEqual(decision.reason, "OK")
    
    def test_high_exposure_evaluation(self):
        """Test evaluation with high exposure."""
        high_exposure_weights = {'BTC': 0.8, 'ETH': 0.7, 'SOL': 0.6}
        
        decision = self.engine.evaluate(
            portfolio_weights=high_exposure_weights,
            asset_returns=self.returns,
            asset_prices=self.prices,
        )
        
        # Should be reduced due to high exposure
        self.assertTrue(decision.allowed)  # Not halted
        self.assertLess(decision.risk_multiplier, 1.0)
        self.assertIn("REDUCE", decision.reason)
    
    def test_extreme_weights_evaluation(self):
        """Test evaluation with extreme weights."""
        extreme_weights = {'BTC': 0.95, 'ETH': 0.05, 'SOL': 0.0}
        
        decision = self.engine.evaluate(
            portfolio_weights=extreme_weights,
            asset_returns=self.returns,
            asset_prices=self.prices,
        )
        
        # Should be reduced due to position concentration
        self.assertTrue(decision.allowed)
        self.assertLess(decision.risk_multiplier, 1.0)
    
    def test_state_tracking(self):
        """Test state tracking."""
        self.engine.evaluate(
            portfolio_weights=self.weights,
            asset_returns=self.returns,
            asset_prices=self.prices,
        )
        
        state = self.engine.get_state()
        self.assertIsNotNone(state['current_metrics'])
        self.assertIsNotNone(state['last_decision'])
        self.assertEqual(state['decision_count'], 1)
    
    def test_risk_report(self):
        """Test risk report generation."""
        # Run multiple evaluations
        for _ in range(5):
            self.engine.evaluate(
                portfolio_weights=self.weights,
                asset_returns=self.returns,
                asset_prices=self.prices,
            )
        
        report = self.engine.get_risk_report()
        self.assertEqual(report['total_evaluations'], 5)
        self.assertIn('halt_rate', report)
        self.assertIn('avg_risk_multiplier', report)
    
    def test_mode_switching(self):
        """Test mode switching."""
        from risk.risk_limits import DEFAULT_LIMITS
        
        # Switch to live mode
        self.engine.set_mode('live')
        self.assertEqual(self.engine.mode, 'live')
        self.assertEqual(self.engine.limits.max_drawdown, DEFAULT_LIMITS['live'].max_drawdown)
        
        # Switch to research mode
        self.engine.set_mode('research')
        self.assertEqual(self.engine.mode, 'research')
        self.assertEqual(self.engine.limits.max_drawdown, DEFAULT_LIMITS['research'].max_drawdown)
    
    def test_reset(self):
        """Test engine reset."""
        self.engine.evaluate(
            portfolio_weights=self.weights,
            asset_returns=self.returns,
            asset_prices=self.prices,
        )
        
        self.assertIsNotNone(self.engine._last_decision)
        self.assertEqual(len(self.engine._history), 1)
        
        self.engine.reset()
        
        self.assertIsNone(self.engine._last_decision)
        self.assertEqual(len(self.engine._history), 0)


if __name__ == '__main__':
    unittest.main()
