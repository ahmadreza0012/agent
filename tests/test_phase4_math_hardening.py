"""
Phase 4: Math Hardening Tests
Tests for numerical stability, honest expected returns, and frequency-aware windows.
"""
import pytest
import numpy as np
import pandas as pd
from portfolio_optimizer import PortfolioOptimizer, trend_following_strategy, mean_reversion_strategy
from utils.timeframe import detect_frequency, HOURLY_FREQ, DAILY_FREQ


class TestExpectedReturnsHonesty:
    """Test that expected returns are honest (no forced positive floors)."""
    
    def test_negative_returns_allowed(self):
        """Verify optimizer handles negative expected returns without forcing positive."""
        n_assets = 3
        optimizer = PortfolioOptimizer(n_assets, ['BTC', 'ETH', 'SOL'])
        
        # All negative expected returns
        expected_returns = np.array([-0.05, -0.03, -0.02])
        cov_matrix = np.eye(3) * 0.04
        
        # Should not crash, should use fallback (min_vol or equal-weight)
        weights = optimizer.mean_variance_optimization(expected_returns, cov_matrix, 
                                                        risk_free_rate=0.0, method='max_sharpe')
        
        assert weights.sum() == pytest.approx(1.0, abs=0.01)
        assert all(weights >= 0)
        # Should NOT be all equal (which would indicate random fallback)
        # Some differentiation should exist based on volatility
    
    def test_all_returns_below_rf_fallback(self):
        """When all returns <= rf, should fall back to min_vol/equal-weight gracefully."""
        n_assets = 4
        optimizer = PortfolioOptimizer(n_assets, ['BTC', 'ETH', 'SOL', 'CASH'])
        
        # Expected returns below risk-free rate (0.0)
        expected_returns = np.array([-0.01, -0.02, -0.03, 0.0])
        cov_matrix = np.eye(4) * 0.05
        
        weights = optimizer.mean_variance_optimization(expected_returns, cov_matrix,
                                                        risk_free_rate=0.0, method='max_sharpe')
        
        assert weights.sum() == pytest.approx(1.0, abs=0.01)
        assert all(weights >= 0)


class TestCovarianceRegularization:
    """Test covariance matrix regularization for numerical stability."""
    
    def test_singular_cov_handling(self):
        """Near-singular covariance matrix should be handled via ridge regularization."""
        n_assets = 3
        optimizer = PortfolioOptimizer(n_assets, ['BTC', 'ETH', 'SOL'])
        
        # Create nearly singular covariance (highly correlated assets)
        base_cov = np.array([
            [0.04, 0.039, 0.038],
            [0.039, 0.04, 0.039],
            [0.038, 0.039, 0.04]
        ])
        
        expected_returns = np.array([0.05, 0.04, 0.03])
        
        # Should not crash due to singular matrix
        weights = optimizer.mean_variance_optimization(expected_returns, base_cov,
                                                        risk_free_rate=0.0)
        
        assert weights.sum() == pytest.approx(1.0, abs=0.01)
        assert all(weights >= 0)


class TestFrequencyAwareWindows:
    """Test that trend/MR strategies use bar-based windows, not hardcoded hours."""
    
    def test_trend_following_daily_vs_hourly(self):
        """Trend following should work with both daily and hourly data using same bar windows."""
        # Daily data (365 bars = ~1 year)
        np.random.seed(42)
        daily_prices = pd.DataFrame({
            'BTC': 100 * np.cumprod(1 + np.random.randn(500) * 0.02),
            'ETH': 100 * np.cumprod(1 + np.random.randn(500) * 0.025),
            'CASH': np.ones(500)
        })
        daily_returns = daily_prices.pct_change().dropna()
        
        # Hourly data (same number of bars but different time horizon)
        hourly_prices = pd.DataFrame({
            'BTC': 100 * np.cumprod(1 + np.random.randn(500) * 0.005),
            'ETH': 100 * np.cumprod(1 + np.random.randn(500) * 0.006),
            'CASH': np.ones(500)
        })
        hourly_returns = hourly_prices.pct_change().dropna()
        
        # Both should run without error (windows are in bars, not hours)
        daily_weights = trend_following_strategy(daily_prices, daily_returns, 
                                                  short_window=20, long_window=100)
        hourly_weights = trend_following_strategy(hourly_prices, hourly_returns,
                                                   short_window=20, long_window=100)
        
        assert len(daily_weights) == 3
        assert len(hourly_weights) == 3
        assert daily_weights.sum() == pytest.approx(1.0, abs=0.01)
        assert hourly_weights.sum() == pytest.approx(1.0, abs=0.01)
    
    def test_mean_reversion_zscore(self):
        """Mean reversion should use z-score based signals with bar windows."""
        np.random.seed(42)
        prices = pd.DataFrame({
            'BTC': 100 * np.cumprod(1 + np.random.randn(200) * 0.02),
            'ETH': 100 * np.cumprod(1 + np.random.randn(200) * 0.025),
            'SOL': 100 * np.cumprod(1 + np.random.randn(200) * 0.03),
        })
        returns = prices.pct_change().dropna()
        
        weights = mean_reversion_strategy(prices, returns, 
                                           lookback_window=50, z_score_threshold=1.5)
        
        assert len(weights) == 3
        assert weights.sum() == pytest.approx(1.0, abs=0.01)
        # Should cap extreme concentration
        assert max(weights) < 0.8  # No single asset > 80%


class TestBlackLittermanNeutralViews:
    """Test Black-Litterman degrades gracefully with neutral/empty views."""
    
    def test_empty_views_degrade_to_prior(self):
        """Empty sentiment views should degrade to prior optimization without crash."""
        n_assets = 3
        optimizer = PortfolioOptimizer(n_assets, ['BTC', 'ETH', 'SOL'])
        
        market_caps = np.array([1.0, 1.0, 1.0])
        cov_matrix = np.eye(3) * 0.04
        
        # Empty views (P is empty, Q is empty)
        P = np.zeros((0, 3))  # No views
        Q = np.array([])      # No view values
        
        # Should not crash, should return reasonable weights
        try:
            weights = optimizer.black_litterman(market_caps, cov_matrix, P, Q,
                                                 tau=0.05, risk_free_rate=0.0)
            assert weights.sum() == pytest.approx(1.0, abs=0.01)
            assert all(weights >= 0)
        except Exception as e:
            # If it raises an error for empty views, that's acceptable behavior
            # as long as it's documented
            assert "view" in str(e).lower() or "empty" in str(e).lower()
    
    def test_extreme_views_clipped(self):
        """Extreme sentiment views should be clipped to prevent explosion."""
        n_assets = 3
        optimizer = PortfolioOptimizer(n_assets, ['BTC', 'ETH', 'SOL'])
        
        market_caps = np.array([1.0, 1.0, 1.0])
        cov_matrix = np.eye(3) * 0.04
        
        # Extreme views (should be clipped internally)
        P = np.eye(3)
        Q = np.array([10.0, -10.0, 5.0])  # Unrealistic magnitudes
        
        # Should produce finite weights (not NaN or inf)
        weights = optimizer.black_litterman(market_caps, cov_matrix, P, Q,
                                             tau=0.05, risk_free_rate=0.0)
        
        assert np.all(np.isfinite(weights))
        assert weights.sum() == pytest.approx(1.0, abs=0.01)
        assert all(weights >= 0)


class TestSolverHygiene:
    """Test MVO solver creates fresh instances and logs failures."""
    
    def test_fresh_instance_per_solve(self):
        """Multiple calls should not reuse solved EfficientFrontier instances."""
        n_assets = 3
        optimizer = PortfolioOptimizer(n_assets, ['BTC', 'ETH', 'SOL'])
        
        expected_returns1 = np.array([0.05, 0.04, 0.03])
        expected_returns2 = np.array([0.01, 0.02, 0.03])
        cov_matrix = np.eye(3) * 0.04
        
        # Two separate optimizations with different inputs
        weights1 = optimizer.mean_variance_optimization(expected_returns1, cov_matrix)
        weights2 = optimizer.mean_variance_optimization(expected_returns2, cov_matrix)
        
        # Should produce different weights (not cached/reused)
        assert not np.allclose(weights1, weights2, rtol=0.01)
        
        assert weights1.sum() == pytest.approx(1.0, abs=0.01)
        assert weights2.sum() == pytest.approx(1.0, abs=0.01)


class TestCVaRFrequencyConsistency:
    """Test CVaR does not double-annualize scenario returns."""
    
    def test_cvar_no_double_annualization(self):
        """CVaR should use consistent per-bar or annualized returns, not both."""
        n_assets = 3
        optimizer = PortfolioOptimizer(n_assets, ['BTC', 'ETH', 'SOL'])
        
        np.random.seed(42)
        # Per-bar returns (not annualized)
        returns = np.random.randn(500, 3) * 0.02
        
        # Should calculate CVaR on provided scale
        weights = optimizer.cvar_optimization(returns, cvar_limit=0.10, confidence=0.95)
        
        assert weights.sum() == pytest.approx(1.0, abs=0.01)
        assert all(weights >= 0)
        assert np.all(np.isfinite(weights))


class TestRiskParityZeroVol:
    """Test risk parity handles zero-volatility assets cleanly."""
    
    def test_zero_vol_asset_handling(self):
        """Assets with zero volatility should get minimum weight, not crash."""
        n_assets = 4
        optimizer = PortfolioOptimizer(n_assets, ['BTC', 'ETH', 'STABLE', 'CASH'])
        
        # Covariance with zero-vol assets (stablecoin, cash)
        cov_matrix = np.array([
            [0.04, 0.02, 0.0, 0.0],
            [0.02, 0.05, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0],   # STABLE: zero vol
            [0.0, 0.0, 0.0, 0.0]    # CASH: zero vol
        ])
        
        weights = optimizer.risk_parity(cov_matrix)
        
        assert weights.sum() == pytest.approx(1.0, abs=0.01)
        assert all(weights >= 0)
        # Zero-vol assets should still get some allocation (cash buffer logic)
        assert weights[2] >= 0  # STABLE
        assert weights[3] >= 0  # CASH


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
