"""
Unit tests for timeframe/frequency detection module.

Tests:
1. Daily series annualizes with ~365
2. Hourly series annualizes with ~24*365
3. Mixed/wrong assumption fails gracefully
4. Frequency detection from index works correctly
"""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta

import sys
sys.path.insert(0, '/workspace')

from utils.timeframe import (
    detect_frequency, 
    FREQUENCY_SPECS, 
    DAILY_FREQ, 
    HOURLY_FREQ,
    annualize_returns,
    annualize_volatility,
    compute_annualized_stats,
)


class TestFrequencySpecs:
    """Test predefined frequency specifications."""
    
    def test_daily_freq_spec(self):
        """Daily frequency should have 365 obs/year."""
        freq = FREQUENCY_SPECS["1d"]
        assert freq.observations_per_day == 1.0
        assert freq.observations_per_year == 365.0
        assert freq.annualization_factor_mean == 365.0
        assert np.isclose(freq.annualization_factor_vol, np.sqrt(365.0))
    
    def test_hourly_freq_spec(self):
        """Hourly frequency should have 24*365 obs/year."""
        freq = FREQUENCY_SPECS["1h"]
        assert freq.observations_per_day == 24.0
        assert freq.observations_per_year == 24.0 * 365.0
        assert freq.annualization_factor_mean == 24.0 * 365.0
        assert np.isclose(freq.annualization_factor_vol, np.sqrt(24.0 * 365.0))


class TestDetectFrequency:
    """Test frequency detection from price data."""
    
    def test_detect_daily_index(self):
        """Should detect daily frequency from daily-spaced index."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        prices = pd.DataFrame({'BTC': np.random.randn(100).cumsum() + 100}, index=dates)
        
        freq = detect_frequency(prices)
        
        assert freq.timeframe_id == "1d"
        assert freq.observations_per_year == 365.0
    
    def test_detect_hourly_index(self):
        """Should detect hourly frequency from hourly-spaced index."""
        dates = pd.date_range('2024-01-01', periods=1000, freq='h')
        prices = pd.DataFrame({'BTC': np.random.randn(1000).cumsum() + 100}, index=dates)
        
        freq = detect_frequency(prices)
        
        assert freq.timeframe_id == "1h"
        assert freq.observations_per_year == 24.0 * 365.0
    
    def test_detect_empty_dataframe(self):
        """Should handle empty DataFrame gracefully."""
        prices = pd.DataFrame()
        
        with pytest.raises(ValueError, match="empty"):
            detect_frequency(prices)
    
    def test_detect_single_row(self):
        """Should fall back to daily for single-row DataFrame."""
        prices = pd.DataFrame({'BTC': [100.0]}, index=[datetime(2024, 1, 1)])
        
        freq = detect_frequency(prices)
        
        assert freq.timeframe_id == "1d"
    
    def test_detect_non_datetime_index(self):
        """Should fall back to daily for non-datetime index."""
        prices = pd.DataFrame({'BTC': np.random.randn(100)}, index=range(100))
        
        freq = detect_frequency(prices)
        
        assert freq.timeframe_id == "1d"


class TestAnnualization:
    """Test annualization functions."""
    
    def test_annualize_daily_returns(self):
        """Daily returns should annualize by ~365."""
        # Simulate daily mean return of 0.001 (0.1% per day)
        daily_mean = np.array([0.001])
        
        ann_return = annualize_returns(daily_mean, DAILY_FREQ)
        
        # Should be approximately 0.001 * 365 = 0.365 (36.5% annual)
        expected = 0.001 * 365.0
        assert np.isclose(ann_return[0], expected)
    
    def test_annualize_hourly_returns(self):
        """Hourly returns should annualize by ~24*365."""
        # Simulate hourly mean return of 0.0001 (0.01% per hour)
        hourly_mean = np.array([0.0001])
        
        ann_return = annualize_returns(hourly_mean, HOURLY_FREQ)
        
        # Should be approximately 0.0001 * 24 * 365 = 0.876 (87.6% annual)
        expected = 0.0001 * 24.0 * 365.0
        assert np.isclose(ann_return[0], expected)
    
    def test_annualize_daily_volatility(self):
        """Daily vol should annualize by sqrt(365)."""
        daily_std = np.array([0.02])  # 2% daily vol
        
        ann_vol = annualize_volatility(daily_std, DAILY_FREQ)
        
        expected = 0.02 * np.sqrt(365.0)
        assert np.isclose(ann_vol[0], expected)
    
    def test_annualize_hourly_volatility(self):
        """Hourly vol should annualize by sqrt(24*365)."""
        hourly_std = np.array([0.005])  # 0.5% hourly vol
        
        ann_vol = annualize_volatility(hourly_std, HOURLY_FREQ)
        
        expected = 0.005 * np.sqrt(24.0 * 365.0)
        assert np.isclose(ann_vol[0], expected)
    
    def test_compute_annualized_stats_daily(self):
        """Test full stats computation on daily data."""
        # Generate synthetic daily returns
        np.random.seed(42)
        n_days = 365
        returns = pd.DataFrame({
            'BTC': np.random.randn(n_days) * 0.02 + 0.0005,
            'ETH': np.random.randn(n_days) * 0.025 + 0.0006,
        })
        
        stats = compute_annualized_stats(returns)
        
        # Check frequency detected as daily
        assert stats['freq'].timeframe_id == "1d"
        
        # Annualized mean should be daily_mean * 365
        expected_ann_mean_btc = returns['BTC'].mean() * 365.0
        assert np.isclose(stats['ann_mean'][0], expected_ann_mean_btc, rtol=1e-5)
        
        # Annualized vol should be daily_std * sqrt(365)
        expected_ann_vol_btc = returns['BTC'].std() * np.sqrt(365.0)
        assert np.isclose(stats['ann_vol'][0], expected_ann_vol_btc, rtol=1e-5)
    
    def test_compute_annualized_stats_hourly(self):
        """Test full stats computation on hourly data."""
        # Generate synthetic hourly returns
        np.random.seed(42)
        n_hours = 24 * 30  # 30 days of hourly data
        dates = pd.date_range('2024-01-01', periods=n_hours, freq='h')
        returns = pd.DataFrame({
            'BTC': np.random.randn(n_hours) * 0.002 + 0.00005,
            'ETH': np.random.randn(n_hours) * 0.0025 + 0.00006,
        }, index=dates)
        
        stats = compute_annualized_stats(returns)
        
        # Check frequency detected as hourly
        assert stats['freq'].timeframe_id == "1h"
        
        # Annualized mean should be hourly_mean * 24 * 365
        expected_ann_mean_btc = returns['BTC'].mean() * 24.0 * 365.0
        assert np.isclose(stats['ann_mean'][0], expected_ann_mean_btc, rtol=1e-5)
        
        # Annualized vol should be hourly_std * sqrt(24*365)
        expected_ann_vol_btc = returns['BTC'].std() * np.sqrt(24.0 * 365.0)
        assert np.isclose(stats['ann_vol'][0], expected_ann_vol_btc, rtol=1e-5)


class TestWrongAssumptionFails:
    """Test that wrong frequency assumptions are caught."""
    
    def test_daily_data_with_hourly_assumption(self):
        """Using hourly annualization on daily data should give very different results."""
        np.random.seed(42)
        n_days = 100
        returns = pd.DataFrame({
            'BTC': np.random.randn(n_days) * 0.02,
        })
        
        # Correct: daily annualization
        daily_stats = compute_annualized_stats(returns, DAILY_FREQ)
        
        # Wrong: hourly annualization (would be a bug)
        hourly_stats = compute_annualized_stats(returns, HOURLY_FREQ)
        
        # Vol should be very different (sqrt(24) ≈ 4.9x difference)
        vol_ratio = hourly_stats['ann_vol'][0] / daily_stats['ann_vol'][0]
        
        # The ratio should be close to sqrt(24) ≈ 4.899
        assert np.isclose(vol_ratio, np.sqrt(24.0), rtol=0.1), \
            f"Expected vol ratio ~{np.sqrt(24.0):.2f}, got {vol_ratio:.2f}"
        
        # This demonstrates why frequency detection matters!
        print(f"\nWARNING: Using wrong frequency assumption changes vol by {vol_ratio:.2f}x")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
