"""Tests for the Bollinger Bands strategy."""
import pandas as pd
import numpy as np
from strategy.bollinger_strategy import apply_bollinger_strategy


def test_no_mutation_of_input():
    """Regression test: input DataFrame must not be mutated.
    
    This was a bug in earlier versions where the strategy modified
    the input DataFrame in place, causing state leakage between runs.
    """
    # Create a simple price series
    dates = pd.date_range("2025-01-01", periods=50, freq="h")
    prices = np.linspace(100, 110, 50)
    df = pd.DataFrame({"close": prices}, index=dates)
    
    # Keep a copy to compare
    df_original = df.copy()
    
    # Run the strategy (apply_bollinger_strategy only takes df, window, num_std)
    result = apply_bollinger_strategy(
        df,
        window=20,
        num_std=2.0,
    )
    
    # Assert input was not mutated
    pd.testing.assert_frame_equal(df, df_original)
    
    # Assert result has expected columns
    assert "middle_band" in result.columns
    assert "upper_band" in result.columns
    assert "lower_band" in result.columns
    assert "position" in result.columns


def test_band_calculation_on_constant_prices():
    """With constant prices, rolling std is 0, so all bands equal the price."""
    # Create constant price series
    dates = pd.date_range("2025-01-01", periods=50, freq="h")
    constant_price = 100.0
    prices = np.full(50, constant_price)
    df = pd.DataFrame({"close": prices}, index=dates)
    
    # Run the strategy
    result = apply_bollinger_strategy(
        df,
        window=20,
        num_std=2.0,
    )
    
    # After warmup period (window), bands should all equal the constant price
    # Check from index window-1 onwards (where rolling calculations are valid)
    warmup_start = 19  # window - 1
    middle_band = result.iloc[warmup_start:].loc[:, "middle_band"]
    upper_band = result.iloc[warmup_start:].loc[:, "upper_band"]
    lower_band = result.iloc[warmup_start:].loc[:, "lower_band"]
    
    # All bands should equal the constant price
    assert np.allclose(middle_band.values, constant_price), f"Middle band {middle_band.values} != {constant_price}"
    assert np.allclose(upper_band.values, constant_price), f"Upper band {upper_band.values} != {constant_price}"
    assert np.allclose(lower_band.values, constant_price), f"Lower band {lower_band.values} != {constant_price}"


def test_signal_generation_on_synthetic_dip_and_recovery():
    """Craft a price series with a dip below lower band, then recovery.
    
    Assert that a buy signal is generated when price recovers back above
    the lower band (mean reversion logic).
    """
    # Create a price series with an obvious dip and recovery
    # Start at 100, dip to 80, recover to 100
    dates = pd.date_range("2025-01-01", periods=100, freq="h")
    
    # Build prices: stable at 100, then sharp dip, then recovery
    prices = []
    for i in range(100):
        if i < 40:
            prices.append(100.0)  # Stable period to establish bands
        elif i < 50:
            prices.append(100.0 - (i - 40) * 3)  # Dip down to 70
        else:
            prices.append(70.0 + (i - 50) * 3)  # Recover back up
    
    df = pd.DataFrame({"close": prices}, index=dates)
    
    # Run the strategy
    result = apply_bollinger_strategy(
        df,
        window=20,
        num_std=2.0,
    )
    
    # Check that we have signals
    assert "position" in result.columns
    
    # The strategy should generate a buy signal (position = 1) at some point
    # during or after the recovery phase when price crosses back above lower band
    positions = result["position"].values
    
    # There should be at least one buy signal (position == 1)
    # given the mean-reversion nature of Bollinger Bands
    buy_signals = positions[positions == 1]
    assert len(buy_signals) > 0, "Expected at least one buy signal during dip/recovery"
