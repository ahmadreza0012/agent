"""
Timeframe / Frequency Detection Module
======================================
Centralized system for detecting data frequency and computing correct annualization factors.

CRITICAL: Replaces all hardcoded * 24 * 365 assumptions with dynamic frequency detection.

Conventions:
- Crypto markets trade 24/7, so we use 365 days/year (not 252 trading days)
- Frequency detected from median bar delta in the price index
- Falls back to daily assumption if detection fails

Usage:
    freq = detect_frequency(prices_df)
    ann_return = mean_return * freq.observations_per_year
    ann_vol = std_return * np.sqrt(freq.observations_per_year)
"""

import numpy as np
import pandas as pd
from typing import NamedTuple, Optional
import logging

logger = logging.getLogger(__name__)


class FrequencySpec(NamedTuple):
    """
    Specification for a given data frequency.
    
    Attributes:
        timeframe_id: Human-readable identifier (e.g., "1d", "1h")
        observations_per_day: Number of bars per day
        observations_per_year: Number of bars per year (for annualization)
        annualization_factor_mean: Factor to annualize mean returns (= obs_per_year)
        annualization_factor_vol: Factor to annualize volatility (= sqrt(obs_per_year))
    """
    timeframe_id: str
    observations_per_day: float
    observations_per_year: float
    annualization_factor_mean: float
    annualization_factor_vol: float
    
    @property
    def seconds_per_bar(self) -> float:
        """Seconds between bar closes."""
        return 86400.0 / self.observations_per_day


# Predefined frequency specifications
FREQUENCY_SPECS = {
    "1d": FrequencySpec(
        timeframe_id="1d",
        observations_per_day=1.0,
        observations_per_year=365.0,
        annualization_factor_mean=365.0,
        annualization_factor_vol=np.sqrt(365.0),
    ),
    "12h": FrequencySpec(
        timeframe_id="12h",
        observations_per_day=2.0,
        observations_per_year=2.0 * 365.0,
        annualization_factor_mean=2.0 * 365.0,
        annualization_factor_vol=np.sqrt(2.0 * 365.0),
    ),
    "6h": FrequencySpec(
        timeframe_id="6h",
        observations_per_day=4.0,
        observations_per_year=4.0 * 365.0,
        annualization_factor_mean=4.0 * 365.0,
        annualization_factor_vol=np.sqrt(4.0 * 365.0),
    ),
    "4h": FrequencySpec(
        timeframe_id="4h",
        observations_per_day=6.0,
        observations_per_year=6.0 * 365.0,
        annualization_factor_mean=6.0 * 365.0,
        annualization_factor_vol=np.sqrt(6.0 * 365.0),
    ),
    "1h": FrequencySpec(
        timeframe_id="1h",
        observations_per_day=24.0,
        observations_per_year=24.0 * 365.0,
        annualization_factor_mean=24.0 * 365.0,
        annualization_factor_vol=np.sqrt(24.0 * 365.0),
    ),
    "30m": FrequencySpec(
        timeframe_id="30m",
        observations_per_day=48.0,
        observations_per_year=48.0 * 365.0,
        annualization_factor_mean=48.0 * 365.0,
        annualization_factor_vol=np.sqrt(48.0 * 365.0),
    ),
    "15m": FrequencySpec(
        timeframe_id="15m",
        observations_per_day=96.0,
        observations_per_year=96.0 * 365.0,
        annualization_factor_mean=96.0 * 365.0,
        annualization_factor_vol=np.sqrt(96.0 * 365.0),
    ),
}


def detect_frequency(prices: pd.DataFrame, 
                     assume_daily_threshold_hours: float = 12.0) -> FrequencySpec:
    """
    Detect the frequency of price data from the index.
    
    Algorithm:
    1. Compute median time delta between consecutive index entries
    2. Match to nearest predefined frequency spec
    3. Fall back to daily ("1d") if detection fails or index not datetime
    
    Args:
        prices: DataFrame with DatetimeIndex (or convertible)
        assume_daily_threshold_hours: If median delta > this, assume daily
        
    Returns:
        FrequencySpec for the detected frequency
        
    Raises:
        ValueError: If prices empty or index cannot be converted to datetime
    """
    if prices.empty:
        raise ValueError("Cannot detect frequency from empty DataFrame")
    
    # Try to ensure datetime index
    index = prices.index
    if not isinstance(index, pd.DatetimeIndex):
        try:
            index = pd.to_datetime(index)
        except Exception as e:
            logger.warning(f"Cannot convert index to datetime: {e}. Assuming daily frequency.")
            return FREQUENCY_SPECS["1d"]
    
    if len(index) < 2:
        logger.warning("Index has < 2 entries, assuming daily frequency.")
        return FREQUENCY_SPECS["1d"]
    
    # Compute median time delta
    deltas = index.to_series().diff().dropna()
    median_delta = deltas.median()
    
    # Convert to hours
    try:
        median_hours = median_delta.total_seconds() / 3600.0
    except AttributeError:
        # Already a timedelta
        median_hours = median_delta / np.timedelta64(1, 'h')
    
    logger.info(f"Detected median bar delta: {median_hours:.2f} hours")
    
    # Match to nearest frequency
    if median_hours > assume_daily_threshold_hours:
        # Likely daily data
        return FREQUENCY_SPECS["1d"]
    
    # Find closest predefined frequency
    best_match = None
    best_diff = float('inf')
    
    for freq_id, spec in FREQUENCY_SPECS.items():
        hours_per_bar = 24.0 / spec.observations_per_day
        diff = abs(median_hours - hours_per_bar)
        if diff < best_diff:
            best_diff = diff
            best_match = spec
    
    # Sanity check: if best match is very far, fall back to daily
    if best_match is None or best_diff > 6.0:  # More than 6 hours off
        logger.warning(f"Frequency detection uncertain (median={median_hours:.2f}h). Assuming daily.")
        return FREQUENCY_SPECS["1d"]
    
    logger.info(f"Using frequency spec: {best_match.timeframe_id} "
                f"(annualization: mean={best_match.annualization_factor_mean:.1f}, "
                f"vol={best_match.annualization_factor_vol:.2f})")
    
    return best_match


def annualize_returns(mean_returns: np.ndarray, freq: FrequencySpec) -> np.ndarray:
    """
    Annualize mean returns using the correct factor for the data frequency.
    
    Args:
        mean_returns: Array of per-bar mean returns (not yet annualized)
        freq: FrequencySpec for the data
        
    Returns:
        Annualized returns
    """
    return mean_returns * freq.annualization_factor_mean


def annualize_volatility(std_returns: np.ndarray, freq: FrequencySpec) -> np.ndarray:
    """
    Annualize volatility using the square-root-of-time rule.
    
    Args:
        std_returns: Array of per-bar standard deviations (not yet annualized)
        freq: FrequencySpec for the data
        
    Returns:
        Annualized volatility
    """
    return std_returns * freq.annualization_factor_vol


def compute_annualized_stats(returns: pd.DataFrame, 
                             freq: Optional[FrequencySpec] = None) -> dict:
    """
    Compute annualized return and volatility statistics for a returns DataFrame.
    
    Args:
        returns: DataFrame of per-bar returns (each column an asset)
        freq: FrequencySpec (auto-detected if None)
        
    Returns:
        Dict with keys: 'ann_mean', 'ann_vol', 'ann_sharpe' (assuming rf=0)
    """
    if freq is None:
        # Auto-detect from the returns index
        freq = detect_frequency(returns)
    
    mean_ret = returns.mean().values
    std_ret = returns.std().values
    
    ann_mean = annualize_returns(mean_ret, freq)
    ann_vol = annualize_volatility(std_ret, freq)
    ann_sharpe = ann_mean / ann_vol
    
    return {
        'ann_mean': ann_mean,
        'ann_vol': ann_vol,
        'ann_sharpe': ann_sharpe,
        'freq': freq,
    }


# Convenience constants for direct use (but prefer detection!)
DAILY_FREQ = FREQUENCY_SPECS["1d"]
HOURLY_FREQ = FREQUENCY_SPECS["1h"]

# Legacy constants (DEPRECATED - use detect_frequency instead)
OBSERVATIONS_PER_DAY = 1.0  # Assume daily by default
OBSERVATIONS_PER_YEAR = 365.0
ANNUALIZATION_FACTOR_MEAN = 365.0
ANNUALIZATION_FACTOR_VOL = np.sqrt(365.0)
