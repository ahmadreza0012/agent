"""
Tests for Bollinger Bands Strategy

This module tests the bollinger_strategy.py implementation.
"""

import pandas as pd
import numpy as np
import pytest
from strategy.bollinger_strategy import apply_bollinger_strategy


def test_no_mutation_of_input():
    """
    Test that apply_bollinger_strategy does not mutate the input DataFrame.
    
    This is a regression test for a bug that occurred multiple times in this project,
    where the strategy function would modify the original input DataFrame instead of
    working on a copy.
    """
    # Create original DataFrame
    original_df = pd.DataFrame({
        'close': [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0,
                  110.0, 111.0, 112.0, 113.0, 114.0, 115.0, 116.0, 117.0, 118.0, 119.0,
                  120.0, 121.0, 122.0, 123.0, 124.0, 125.0, 126.0, 127.0, 128.0, 129.0]
    })
    
    # Store a copy for comparison
    original_copy = original_df.copy()
    
    # Apply strategy (should not mutate original_df)
    result_df = apply_bollinger_strategy(original_df, window=20, num_std=2.0)
    
    # Assert original DataFrame is unchanged
    pd.testing.assert_frame_equal(original_df, original_copy)
    
    # Assert result has additional columns
    assert 'middle_band' in result_df.columns
    assert 'upper_band' in result_df.columns
    assert 'lower_band' in result_df.columns
    assert 'position' in result_df.columns


def test_band_calculation_on_constant_prices():
    """
    Test that with a constant price series, rolling_std is 0, so all bands equal the price.
    
    When prices are constant:
    - mean = constant value
    - std = 0
    - upper_band = middle_band + (num_std * 0) = middle_band
    - lower_band = middle_band - (num_std * 0) = middle_band
    """
    constant_price = 100.0
    
    # Create DataFrame with constant prices (need at least 'window' rows for bands to be calculated)
    df = pd.DataFrame({
        'close': [constant_price] * 30  # 30 rows of constant price
    })
    
    result = apply_bollinger_strategy(df, window=20, num_std=2.0)
    
    # Drop NaN rows (first window-1 rows will have NaN for bands)
    result_valid = result.dropna()
    
    # All bands should equal the constant price
    assert len(result_valid) > 0, "No valid rows after dropping NaN"
    
    for idx in result_valid.index:
        assert result_valid.loc[idx, 'middle_band'] == constant_price, \
            f"middle_band at {idx} should be {constant_price}"
        assert result_valid.loc[idx, 'upper_band'] == constant_price, \
            f"upper_band at {idx} should be {constant_price}"
        assert result_valid.loc[idx, 'lower_band'] == constant_price, \
            f"lower_band at {idx} should be {constant_price}"


def test_signal_generation_on_synthetic_dip_and_recovery():
    """
    Test that a buy signal is generated when price dips below lower band and recovers.
    
    We craft a price series where:
    1. First, prices are stable to establish the bands
    2. Then, price sharply drops below the lower band
    3. Finally, price recovers back above the lower band
    
    This should trigger a buy signal (position=1) at the recovery point.
    """
    # Create a synthetic price series
    # Start with stable prices around 100
    prices = [100.0] * 20  # Establish baseline for 20 periods
    
    # Sharp dip: prices drop significantly
    prices.extend([80.0, 75.0, 70.0])  # Dip below where lower band would be
    
    # Recovery: price goes back up
    prices.extend([85.0, 90.0, 95.0, 100.0])
    
    df = pd.DataFrame({'close': prices})
    
    # Use a smaller window to ensure we get valid bands quickly
    result = apply_bollinger_strategy(df, window=10, num_std=2.0)
    
    # Check that at least one buy signal (position=1) was generated
    buy_signals = result[result['position'] == 1]
    
    assert len(buy_signals) > 0, \
        "Expected at least one buy signal (position=1) during price recovery from dip"
    
    # Find the first buy signal and verify it occurs after the dip
    first_buy_idx = buy_signals.index[0]
    assert first_buy_idx >= 20, \
        f"Buy signal at index {first_buy_idx} should occur after the initial stable period"
