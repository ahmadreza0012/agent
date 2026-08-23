"""
Technical Indicators Module
===========================
Causal technical indicators for feature engineering.

All indicators are designed to be causal - they only use past and current data,
never future data. This prevents look-ahead bias in backtesting and live trading.
"""

import numpy as np
import pandas as pd
from typing import Tuple, Union


def EMA(prices: Union[pd.Series, pd.DataFrame], period: int = 20) -> pd.Series:
    """
    Exponential Moving Average.
    
    Args:
        prices: Price series
        period: EMA period (default 20)
    
    Returns:
        EMA series with same index as input
    
    Raises:
        ValueError: If input is empty or has insufficient data
    """
    if isinstance(prices, pd.DataFrame):
        prices = prices['close'] if 'close' in prices.columns else prices.iloc[:, 0]
    
    if len(prices) == 0:
        raise ValueError("Input series cannot be empty")
    
    if len(prices) < period:
        raise ValueError(f"Input series must have at least {period} data points for EMA")
    
    ema = prices.ewm(span=period, adjust=False).mean()
    return ema


def SMA(prices: Union[pd.Series, pd.DataFrame], period: int = 20) -> pd.Series:
    """
    Simple Moving Average.
    
    Args:
        prices: Price series
        period: SMA period (default 20)
    
    Returns:
        SMA series with same index as input
    """
    if isinstance(prices, pd.DataFrame):
        prices = prices['close'] if 'close' in prices.columns else prices.iloc[:, 0]
    
    sma = prices.rolling(window=period).mean()
    return sma


def RSI(prices: Union[pd.Series, pd.DataFrame], period: int = 14) -> pd.Series:
    """
    Relative Strength Index.
    
    Args:
        prices: Price series
        period: RSI period (default 14)
    
    Returns:
        RSI series (0-100) with same index as input
    """
    if isinstance(prices, pd.DataFrame):
        prices = prices['close'] if 'close' in prices.columns else prices.iloc[:, 0]
    
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(50)  # Neutral RSI for undefined cases
    
    return rsi


def MACD(prices: Union[pd.Series, pd.DataFrame], 
         fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Moving Average Convergence Divergence.
    
    Args:
        prices: Price series
        fast: Fast EMA period (default 12)
        slow: Slow EMA period (default 26)
        signal: Signal line EMA period (default 9)
    
    Returns:
        Tuple of (MACD line, Signal line, Histogram)
    """
    if isinstance(prices, pd.DataFrame):
        prices = prices['close'] if 'close' in prices.columns else prices.iloc[:, 0]
    
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram


def ATR(ohlc: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average True Range.
    
    Args:
        ohlc: DataFrame with columns: open, high, low, close
        period: ATR period (default 14)
    
    Returns:
        ATR series with same index as input
    """
    high = ohlc['high']
    low = ohlc['low']
    close = ohlc['close']
    
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.ewm(span=period, adjust=False).mean()
    
    return atr


def ADX(ohlc: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average Directional Index.
    
    Args:
        ohlc: DataFrame with columns: open, high, low, close
        period: ADX period (default 14)
    
    Returns:
        ADX series (0-100) with same index as input
    """
    high = ohlc['high']
    low = ohlc['low']
    close = ohlc['close']
    
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)
    
    # Directional Movement
    plus_dm = high - prev_high
    minus_dm = prev_low - low
    
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    
    # True Range
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Smoothed values
    atr = true_range.ewm(span=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)
    
    # DX and ADX
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(span=period, adjust=False).mean()
    adx = adx.fillna(0)
    
    return adx


def bollinger_bands(prices: Union[pd.Series, pd.DataFrame], 
                     period: int = 20, 
                     std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Bollinger Bands.
    
    Args:
        prices: Price series
        period: Moving average period (default 20)
        std_dev: Standard deviation multiplier (default 2.0)
    
    Returns:
        Tuple of (upper band, middle band, lower band)
    """
    if isinstance(prices, pd.DataFrame):
        prices = prices['close'] if 'close' in prices.columns else prices.iloc[:, 0]
    
    middle = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    
    return upper, middle, lower


def stochastic(ohlc: pd.DataFrame, 
                k_period: int = 14, 
                d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
    """
    Stochastic Oscillator.
    
    Args:
        ohlc: DataFrame with columns: open, high, low, close
        k_period: %K period (default 14)
        d_period: %D smoothing period (default 3)
    
    Returns:
        Tuple of (%K, %D)
    """
    high = ohlc['high']
    low = ohlc['low']
    close = ohlc['close']
    
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    
    k_percent = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    k_percent = k_percent.fillna(50)
    
    d_percent = k_percent.rolling(window=d_period).mean()
    
    return k_percent, d_percent


def supertrend(ohlc: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series]:
    """
    Supertrend indicator.
    
    Args:
        ohlc: DataFrame with columns: open, high, low, close
        period: ATR period (default 10)
        multiplier: ATR multiplier (default 3.0)
    
    Returns:
        Tuple of (supertrend values, direction: 1=up, -1=down)
    """
    high = ohlc['high']
    low = ohlc['low']
    close = ohlc['close']
    
    atr = ATR(ohlc, period)
    
    hl2 = (high + low) / 2
    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)
    
    supertrend = pd.Series(index=ohlc.index)
    direction = pd.Series(index=ohlc.index)
    
    supertrend.iloc[0] = upper_band.iloc[0]
    direction.iloc[0] = 1
    
    for i in range(1, len(ohlc)):
        if close.iloc[i] > supertrend.iloc[i-1]:
            supertrend.iloc[i] = lower_band.iloc[i]
            direction.iloc[i] = 1
        else:
            supertrend.iloc[i] = upper_band.iloc[i]
            direction.iloc[i] = -1
    
    return supertrend, direction


# Export all indicators
__all__ = [
    'EMA',
    'SMA', 
    'RSI',
    'MACD',
    'ATR',
    'ADX',
    'Bollinger Bands',
    'Stochastic',
    'Supertrend'
]
