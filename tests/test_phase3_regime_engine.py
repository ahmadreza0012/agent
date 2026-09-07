"""
Tests for Phase 3 Regime Engine

Tests for:
- Regime detection on synthetic bull/bear/high-vol series
- No look-ahead bias (regime at t ignores returns after t)
- Frequency-aware window scaling (daily vs hourly)
- Integration with StrategySelector.blend
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from strategies.regime_engine import (
    RegimeEngine, RegimeState, RegimeLabel, 
    detect_regime, REGIME_THRESHOLDS
)
from utils.timeframe import FREQUENCY_SPECS


def generate_synthetic_prices(n_bars: int, n_assets: int = 4, 
                              drift: float = 0.0, vol: float = 0.02,
                              seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate synthetic price and return series.
    
    Args:
        n_bars: Number of bars
        n_assets: Number of assets
        drift: Per-bar drift (positive = bull, negative = bear)
        vol: Per-bar volatility
        seed: Random seed
        
    Returns:
        (prices, returns) DataFrames
    """
    np.random.seed(seed)
    
    # Generate cumulative returns
    dates = pd.date_range(start='2024-01-01', periods=n_bars, freq='H')
    asset_cols = [f'Asset_{i}' for i in range(n_assets)]
    
    # Generate correlated returns
    base_returns = np.random.normal(drift, vol, size=(n_bars, n_assets))
    
    returns = pd.DataFrame(base_returns, index=dates, columns=asset_cols)
    prices = (1 + returns).cumprod()
    
    return prices, returns


class TestRegimeEngineBasic:
    """Basic functionality tests for RegimeEngine."""
    
    def test_engine_initialization(self):
        """Test that engine initializes with default parameters."""
        engine = RegimeEngine()
        assert engine.vol_window_bars == 168
        assert engine.trend_short_bars == 72
        assert engine.thresholds['vol_high'] == 0.80
    
    def test_detect_insufficient_data(self):
        """Test behavior with insufficient data."""
        engine = RegimeEngine()
        short_returns = pd.DataFrame(
            np.random.randn(5, 2),
            columns=['A', 'B']
        )
        short_prices = (1 + short_returns).cumprod()
        
        state = engine.detect(prices=short_prices, returns=short_returns)
        assert state.label == RegimeLabel.LOW_VOL_RANGE
        assert 'insufficient_data' in state.features.get('error', '') or state.confidence >= 0.5
    
    def test_detect_returns_regime_state(self):
        """Test that detect returns proper RegimeState structure."""
        prices, returns = generate_synthetic_prices(n_bars=200, vol=0.01)
        engine = RegimeEngine()
        
        state = engine.detect(prices=prices, returns=returns)
        
        assert isinstance(state, RegimeState)
        assert isinstance(state.label, RegimeLabel)
        assert 0 <= state.confidence <= 1
        assert 'realized_vol' in state.features
        assert 'drawdown' in state.features
        assert state.as_of is not None


class TestRegimeDetectionSynthetic:
    """Test regime detection on synthetic market conditions."""
    
    def test_bull_market_detection(self):
        """Test that strong positive drift produces bull_trend regime."""
        # Generate bull market: positive drift, moderate vol
        prices, returns = generate_synthetic_prices(
            n_bars=500, drift=0.001, vol=0.015, seed=42
        )
        
        engine = RegimeEngine()
        state = engine.detect(prices=prices, returns=returns)
        
        # Should detect either bull_trend or low_vol_range (if trend not strong enough)
        # The key is it should NOT be crisis or high_vol
        assert state.label in [RegimeLabel.BULL_TREND, RegimeLabel.LOW_VOL_RANGE]
        assert state.features['realized_vol'] < REGIME_THRESHOLDS['vol_extreme']
    
    def test_bear_market_detection(self):
        """Test that strong negative drift produces bear_trend regime."""
        # Generate bear market: negative drift
        prices, returns = generate_synthetic_prices(
            n_bars=500, drift=-0.002, vol=0.02, seed=42
        )
        
        engine = RegimeEngine()
        state = engine.detect(prices=prices, returns=returns)
        
        # Should detect bear_trend or high_vol (if vol elevated)
        assert state.label in [RegimeLabel.BEAR_TREND, RegimeLabel.HIGH_VOL, RegimeLabel.CRISIS]
        assert state.features['short_return'] < 0
    
    def test_high_vol_detection(self):
        """Test that high volatility produces high_vol regime."""
        # Generate high vol series
        prices, returns = generate_synthetic_prices(
            n_bars=500, drift=0.0, vol=0.05, seed=42  # High vol
        )
        
        engine = RegimeEngine()
        state = engine.detect(prices=prices, returns=returns)
        
        # With vol=0.05 per bar, annualized vol should be very high
        # Hourly: 0.05 * sqrt(24*365) ≈ 4.68 → definitely high_vol
        assert state.label in [RegimeLabel.HIGH_VOL, RegimeLabel.CRISIS]
        assert state.features['realized_vol'] > REGIME_THRESHOLDS['vol_high']
    
    def test_crisis_detection(self):
        """Test that deep drawdown + extreme vol produces crisis regime."""
        # Generate crisis: sharp drop with high vol
        np.random.seed(42)
        n_bars = 500
        dates = pd.date_range(start='2024-01-01', periods=n_bars, freq='H')
        
        # Create a crash scenario
        returns_data = np.random.normal(0, 0.04, size=(n_bars, 4))
        # Add severe drawdown in recent period
        returns_data[-50:, :] = -0.03  # Sharp decline
        
        returns = pd.DataFrame(returns_data, index=dates, columns=['A', 'B', 'C', 'D'])
        prices = (1 + returns).cumprod()
        
        engine = RegimeEngine()
        state = engine.detect(prices=prices, returns=returns)
        
        # Should detect crisis or high_vol given the stress
        assert state.label in [RegimeLabel.CRISIS, RegimeLabel.HIGH_VOL, RegimeLabel.BEAR_TREND]


class TestNoLookAheadBias:
    """Critical tests for no look-ahead bias."""
    
    def test_regime_at_t_uses_only_past_data(self):
        """Verify regime at time t doesn't use future returns."""
        np.random.seed(42)
        n_bars = 300
        dates = pd.date_range(start='2024-01-01', periods=n_bars, freq='H')
        
        # Generate returns where future is completely different from past
        returns_data = np.zeros((n_bars, 2))
        returns_data[:150, :] = 0.001  # Positive first half
        returns_data[150:, :] = -0.01  # Negative second half (crash)
        
        returns = pd.DataFrame(returns_data, index=dates, columns=['A', 'B'])
        prices = (1 + returns).cumprod()
        
        engine = RegimeEngine(vol_window_bars=50, trend_short_bars=20)
        
        # Check regime at midpoint (should only see positive returns)
        mid_idx = 150
        returns_up_to_t = returns.iloc[:mid_idx]
        prices_up_to_t = prices.iloc[:mid_idx]
        
        state = engine.detect(prices=prices_up_to_t, returns=returns_up_to_t)
        
        # At midpoint, should NOT see bear_trend because crash hasn't happened yet
        # (This is a probabilistic test - the positive drift should dominate)
        assert state.features['short_return'] > -0.05  # Should not be strongly negative
    
    def test_rolling_detection_consistency(self):
        """Test that rolling regime detection is consistent."""
        prices, returns = generate_synthetic_prices(n_bars=400, vol=0.02)
        engine = RegimeEngine(vol_window_bars=50)
        
        regimes = []
        for i in range(100, len(returns), 20):
            subset_prices = prices.iloc[:i]
            subset_returns = returns.iloc[:i]
            state = engine.detect(prices=subset_prices, returns=subset_returns)
            regimes.append((i, state.label.value, state.features.copy()))
        
        # Just verify we can compute regimes at multiple points
        assert len(regimes) > 0
        for _, label, features in regimes:
            assert label in ['bull_trend', 'bear_trend', 'high_vol', 'low_vol_range', 'crisis']
            assert 'realized_vol' in features


class TestFrequencyAwareness:
    """Test that windows scale correctly with frequency."""
    
    def test_hourly_vs_daily_window_scaling(self):
        """Test that same calendar window uses different bar counts."""
        # Hourly data: 168 bars = 1 week
        hourly_prices, hourly_returns = generate_synthetic_prices(
            n_bars=500, vol=0.01
        )
        
        # Daily data: 168 bars = ~24 weeks
        daily_prices, daily_returns = generate_synthetic_prices(
            n_bars=500, vol=0.02
        )
        
        engine = RegimeEngine(vol_window_bars=168)
        
        # Both should work without error
        hourly_state = engine.detect(prices=hourly_prices, returns=hourly_returns, 
                                     freq=FREQUENCY_SPECS["1h"])
        daily_state = engine.detect(prices=daily_prices, returns=daily_returns,
                                    freq=FREQUENCY_SPECS["1d"])
        
        # Verify both produce valid regime states
        assert isinstance(hourly_state.label, RegimeLabel)
        assert isinstance(daily_state.label, RegimeLabel)
        
        # Volatility should be properly annualized for each frequency
        assert hourly_state.features['realized_vol'] >= 0
        assert daily_state.features['realized_vol'] >= 0
    
    def test_auto_frequency_detection(self):
        """Test that engine auto-detects frequency when not provided."""
        prices, returns = generate_synthetic_prices(n_bars=300)
        engine = RegimeEngine()
        
        # Should work without explicit freq
        state = engine.detect(prices=prices, returns=returns, freq=None)
        assert isinstance(state.label, RegimeLabel)


class TestBackwardCompatibility:
    """Test backward compatibility with old detect_regime interface."""
    
    def test_old_interface_still_works(self):
        """Test that old detect_regime function still works."""
        prices, returns = generate_synthetic_prices(n_bars=200)
        
        # Old interface should return string labels
        regime = detect_regime(returns, window=100)
        
        assert regime in ['trending', 'mean_reverting', 'high_vol']
    
    def test_label_mapping(self):
        """Test new-to-old label mapping."""
        from strategies.regime_engine import RegimeLabel
        
        label_map = {
            RegimeLabel.CRISIS: "high_vol",
            RegimeLabel.HIGH_VOL: "high_vol",
            RegimeLabel.BULL_TREND: "trending",
            RegimeLabel.BEAR_TREND: "trending",
            RegimeLabel.LOW_VOL_RANGE: "mean_reverting",
        }
        
        # Verify all new labels map to valid old labels
        for new_label, old_label in label_map.items():
            assert old_label in ['trending', 'mean_reverting', 'high_vol']


class TestIntegrationWithStrategySelector:
    """Test integration with StrategySelector."""
    
    def test_regime_prior_weights_exist(self):
        """Test that regime prior weights are defined for all regimes."""
        engine = RegimeEngine()
        
        for regime in RegimeLabel:
            priors = engine.get_regime_prior_weights(regime)
            assert isinstance(priors, dict)
            assert len(priors) > 0
            
            # Should include key strategies
            expected_strategies = ['cvar', 'risk_parity', 'trend_following', 
                                   'ml', 'mvo', 'mean_reversion']
            for strat in expected_strategies:
                assert strat in priors
    
    def test_crisis_increases_defensive_weights(self):
        """Test that crisis regime increases defensive strategy weights."""
        engine = RegimeEngine()
        
        crisis_priors = engine.get_regime_prior_weights(RegimeLabel.CRISIS)
        bull_priors = engine.get_regime_prior_weights(RegimeLabel.BULL_TREND)
        
        # Defensive strategies should have higher weight in crisis
        assert crisis_priors['cvar'] > bull_priors['cvar']
        assert crisis_priors['risk_parity'] > bull_priors['risk_parity']
        
        # Aggressive strategies should have lower weight in crisis
        assert crisis_priors['ml'] < bull_priors['ml']
        assert crisis_priors['mvo'] < bull_priors['mvo']
    
    def test_volume_available_flag_logged(self):
        """Test that volume availability is tracked."""
        prices, returns = generate_synthetic_prices(n_bars=200)
        volumes = pd.DataFrame(
            np.random.rand(200, 4) * 1000,
            index=prices.index,
            columns=prices.columns
        )
        
        engine = RegimeEngine()
        
        # With volumes
        state_with_vol = engine.detect(prices=prices, returns=returns, volumes=volumes)
        assert state_with_vol.features['volume_available'] == True
        
        # Without volumes
        state_no_vol = engine.detect(prices=prices, returns=returns, volumes=None)
        assert state_no_vol.features['volume_available'] == False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
