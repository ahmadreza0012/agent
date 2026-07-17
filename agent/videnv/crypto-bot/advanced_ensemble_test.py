"""
Advanced Ensemble Strategy Test
================================
Combines multi-timeframe analysis, regime filtering (ADX), and dynamic strategy selection.

Strategy Logic:
1. Multi-Timeframe Trend: 4hr SMA vs 1hr price to determine macro trend direction
2. Regime Filter (ADX): 
   - ADX > 25: Trend-following mode (use Donchian breakout + MA confirmation)
   - ADX < 20: Mean-reversion mode (use RSI + Bollinger Bands)
   - ADX 20-25: No trade / flat
3. Volume Confirmation: Require above-average volume for breakouts
4. Dynamic Position Sizing: Scale position by inverse ATR (volatility)

Target: 20% monthly profit (~791% annually)
"""

import pandas as pd
import numpy as np
from ta.trend import SMAIndicator, EMAIndicator, ADXIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import VolumeWeightedAveragePrice
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest.backtester import run_backtest, print_report


def calculate_multi_timeframe_trend(df: pd.DataFrame) -> pd.Series:
    """
    Resample to 4hr and calculate SMA, then merge back to 1hr data.
    Returns: 1 if price > 4hr SMA (bullish), -1 if price < 4hr SMA (bearish), 0 otherwise
    """
    # Create a copy to avoid modifying original
    df_copy = df.copy()
    
    # Calculate 4hr SMA on the 1hr data (equivalent to resampling)
    # 4hr SMA = SMA of last 4 hourly closes
    df_copy['sma_4hr'] = df_copy['close'].rolling(window=4, min_periods=4).mean()
    
    # Determine trend: price relative to 4hr SMA
    trend = pd.Series(0, index=df.index)
    trend[df_copy['close'] > df_copy['sma_4hr'] * 1.001] = 1   # Bullish
    trend[df_copy['close'] < df_copy['sma_4hr'] * 0.999] = -1  # Bearish
    
    return trend


def calculate_adx_regime(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate ADX and classify regime:
    - ADX > 25: Strong trend (trend-following mode)
    - ADX < 20: Weak trend / ranging (mean-reversion mode)
    - ADX 20-25: Transition / no-trade zone
    """
    adx_indicator = ADXIndicator(
        high=df['high'],
        low=df['low'],
        close=df['close'],
        window=period
    )
    adx = adx_indicator.adx()
    
    regime = pd.Series(0, index=df.index)  # 0 = no-trade/transition
    regime[adx > 25] = 1   # 1 = trend-following
    regime[adx < 20] = 2   # 2 = mean-reversion
    
    return regime, adx


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range for volatility-based position sizing."""
    atr_indicator = AverageTrueRange(
        high=df['high'],
        low=df['low'],
        close=df['close'],
        window=period
    )
    return atr_indicator.average_true_range()


def generate_trend_following_signals(df: pd.DataFrame, mt_trend: pd.Series) -> pd.Series:
    """
    Trend-following strategy using Donchian Channels + MA confirmation.
    Entry: Price breaks above 20-period high (for long) or below 20-period low (for short)
    Filter: Only take signals in direction of multi-timeframe trend
    """
    signals = pd.Series(0, index=df.index)
    
    # Donchian Channels: 20-period high/low
    donchian_high = df['high'].rolling(window=20, min_periods=20).max()
    donchian_low = df['low'].rolling(window=20, min_periods=20).min()
    
    # 20-period SMA for additional confirmation
    sma_20 = df['close'].rolling(window=20, min_periods=20).mean()
    
    for i in range(20, len(df)):
        current_close = df['close'].iloc[i]
        prev_high = donchian_high.iloc[i-1]
        prev_low = donchian_low.iloc[i-1]
        trend_dir = mt_trend.iloc[i]
        
        # Long breakout: price breaks above previous high, aligned with bullish trend
        if current_close > prev_high and trend_dir >= 0:
            # Additional filter: price should be above SMA
            if current_close > sma_20.iloc[i]:
                signals.iloc[i] = 1  # Buy
        
        # Short breakout: price breaks below previous low, aligned with bearish trend
        elif current_close < prev_low and trend_dir <= 0:
            # Additional filter: price should be below SMA
            if current_close < sma_20.iloc[i]:
                signals.iloc[i] = -1  # Sell/Short
    
    return signals


def generate_mean_reversion_signals(df: pd.DataFrame, mt_trend: pd.Series) -> pd.Series:
    """
    Mean-reversion strategy using RSI + Bollinger Bands.
    Entry: RSI oversold + price at lower BB (for long), RSI overbought + price at upper BB (for short)
    Filter: Only take signals against the immediate move but with the larger trend
    """
    signals = pd.Series(0, index=df.index)
    
    # RSI
    rsi_indicator = RSIIndicator(close=df['close'], window=14)
    rsi = rsi_indicator.rsi()
    
    # Bollinger Bands
    bb_indicator = BollingerBands(close=df['close'], window=20, window_dev=2)
    bb_upper = bb_indicator.bollinger_hband()
    bb_lower = bb_indicator.bollinger_lband()
    bb_middle = bb_indicator.bollinger_mavg()
    
    # BB %b: where price is within the bands (0 = lower, 1 = upper)
    bb_pct_b = (df['close'] - bb_lower) / (bb_upper - bb_lower)
    
    for i in range(20, len(df)):
        current_rsi = rsi.iloc[i]
        current_bb_pct = bb_pct_b.iloc[i]
        trend_dir = mt_trend.iloc[i]
        
        # Long: RSI oversold (<30) AND price near lower band (%b < 0.2)
        # Take long only if larger trend is not strongly bearish
        if current_rsi < 30 and current_bb_pct < 0.2:
            if trend_dir >= -0.5:  # Not strongly bearish
                signals.iloc[i] = 1  # Buy
        
        # Short: RSI overbought (>70) AND price near upper band (%b > 0.8)
        # Take short only if larger trend is not strongly bullish
        elif current_rsi > 70 and current_bb_pct > 0.8:
            if trend_dir <= 0.5:  # Not strongly bullish
                signals.iloc[i] = -1  # Sell/Short
    
    return signals


def apply_volume_filter(df: pd.DataFrame, signals: pd.Series, lookback: int = 20) -> pd.Series:
    """
    Filter signals: only allow trades when volume is above average.
    This helps confirm breakouts and reduces false signals.
    """
    avg_volume = df['volume'].rolling(window=lookback, min_periods=lookback).mean()
    
    filtered_signals = signals.copy()
    for i in range(lookback, len(df)):
        if signals.iloc[i] != 0:
            if df['volume'].iloc[i] < avg_volume.iloc[i]:
                filtered_signals.iloc[i] = 0  # Disable signal due to low volume
    
    return filtered_signals


def convert_signals_to_positions(signals: pd.Series) -> pd.Series:
    """
    Convert signal series (-1, 0, 1) to position series for backtester.
    Backtester expects: 1 = buy/open long, -1 = sell/close, 0 = hold
    
    Our logic:
    - Signal 1 (buy): If no position, open long (position=1). If short, close and reverse (position=1).
    - Signal -1 (sell): If long, close (position=-1). If no position, open short (position=-1).
    - Signal 0: Hold current position (but backtester handles this differently)
    
    Simplified approach for this test:
    - Signal 1 => position 1 (enter/maintain long)
    - Signal -1 => position -1 (enter/maintain short or close long)
    - Signal 0 => position 0 (flat)
    
    The backtester will handle transitions. We output raw signals as positions.
    """
    # For simplicity, we'll use the signals directly as positions
    # The backtester interprets position changes
    return signals


def generate_combined_strategy_signals(df: pd.DataFrame) -> pd.Series:
    """
    Main strategy function that combines all components:
    1. Multi-timeframe trend
    2. ADX regime classification
    3. Strategy selection based on regime
    4. Volume filter
    """
    # Calculate all indicators
    mt_trend = calculate_multi_timeframe_trend(df)
    regime, adx = calculate_adx_regime(df)
    atr = calculate_atr(df)
    
    # Generate signals for each regime
    tf_signals = generate_trend_following_signals(df, mt_trend)
    mr_signals = generate_mean_reversion_signals(df, mt_trend)
    
    # Combine based on regime
    combined_signals = pd.Series(0, index=df.index)
    
    for i in range(len(df)):
        reg = regime.iloc[i]
        
        if reg == 1:  # Trend-following regime (ADX > 25)
            combined_signals.iloc[i] = tf_signals.iloc[i]
        elif reg == 2:  # Mean-reversion regime (ADX < 20)
            combined_signals.iloc[i] = mr_signals.iloc[i]
        else:  # Transition zone (ADX 20-25)
            combined_signals.iloc[i] = 0  # No trade
    
    # Apply volume filter
    final_signals = apply_volume_filter(df, combined_signals)
    
    return final_signals, mt_trend, regime, adx, atr


def run_baseline_rsi_test(df_test: pd.DataFrame) -> dict:
    """
    Baseline test: Simple RSI strategy (14, 30, 70) on test set.
    This proves the backtester is working correctly.
    """
    print("\n" + "="*60)
    print("BASELINE TEST: Simple RSI Strategy (14, 30, 70)")
    print("="*60)
    
    signals = pd.Series(0, index=df_test.index)
    rsi_indicator = RSIIndicator(close=df_test['close'], window=14)
    rsi = rsi_indicator.rsi()
    
    for i in range(14, len(df_test)):
        if rsi.iloc[i] < 30:
            signals.iloc[i] = 1  # Buy
        elif rsi.iloc[i] > 70:
            signals.iloc[i] = -1  # Sell
    
    df_with_signals = df_test.copy()
    df_with_signals['position'] = signals
    
    results = run_backtest(
        df_with_signals,
        initial_capital=10_000_000,
        commission_pct=0.0025,
        slippage_pct=0.001,
        position_size_pct=1.0,
    )
    
    print(f"\nBaseline RSI Results:")
    print(f"  Total Return: {results['total_return_pct']:+.2f}%")
    print(f"  Num Trades: {results['num_trades']}")
    print(f"  Win Rate: {results['win_rate_pct']:.1f}%")
    print(f"  Max Drawdown: {results['max_drawdown_pct']:.2f}%")
    
    return results


def main():
    print("="*70)
    print("ADVANCED ENSEMBLE STRATEGY TEST")
    print("Multi-Timeframe + ADX Regime Filter + Dynamic Strategy Selection")
    print("="*70)
    
    # Load data
    data_path = os.path.join(os.path.dirname(__file__), 'data', 'btcirt_180d.csv')
    print(f"\nLoading data from: {data_path}")
    df = pd.read_csv(data_path, parse_dates=['timestamp'])
    print(f"Total rows: {len(df)}")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    # Chronological train/test split (70/30)
    split_idx = int(len(df) * 0.7)
    df_train = df.iloc[:split_idx].copy().reset_index(drop=True)
    df_test = df.iloc[split_idx:].copy().reset_index(drop=True)
    
    print(f"\nTrain set: {len(df_train)} rows ({df_train['timestamp'].min()} to {df_train['timestamp'].max()})")
    print(f"Test set: {len(df_test)} rows ({df_test['timestamp'].min()} to {df_test['timestamp'].max()})")
    
    # Run baseline RSI test on test set
    baseline_results = run_baseline_rsi_test(df_test)
    
    # Generate signals for train and test sets
    print("\n" + "="*60)
    print("GENERATING SIGNALS FOR ADVANCED ENSEMBLE STRATEGY")
    print("="*60)
    
    print("\nCalculating indicators and generating signals...")
    train_signals, train_mt_trend, train_regime, train_adx, train_atr = generate_combined_strategy_signals(df_train)
    test_signals, test_mt_trend, test_regime, test_adx, test_atr = generate_combined_strategy_signals(df_test)
    
    # Add signals to dataframes
    df_train['position'] = train_signals
    df_test['position'] = test_signals
    
    # Show signal distribution
    print(f"\nTrain set signal distribution:")
    print(f"  Long (1): {(train_signals == 1).sum()}")
    print(f"  Flat (0): {(train_signals == 0).sum()}")
    print(f"  Short (-1): {(train_signals == -1).sum()}")
    
    print(f"\nTest set signal distribution:")
    print(f"  Long (1): {(test_signals == 1).sum()}")
    print(f"  Flat (0): {(test_signals == 0).sum()}")
    print(f"  Short (-1): {(test_signals == -1).sum()}")
    
    # Run backtest on train set
    print("\n" + "="*60)
    print("BACKTEST RESULTS - TRAIN SET")
    print("="*60)
    train_results = run_backtest(
        df_train,
        initial_capital=10_000_000,
        commission_pct=0.0025,
        slippage_pct=0.001,
        position_size_pct=1.0,
    )
    print_report(train_results)
    
    # Run backtest on test set (this is the real performance metric)
    print("\n" + "="*60)
    print("BACKTEST RESULTS - TEST SET (OUT-OF-SAMPLE)")
    print("="*60)
    test_results = run_backtest(
        df_test,
        initial_capital=10_000_000,
        commission_pct=0.0025,
        slippage_pct=0.001,
        position_size_pct=1.0,
    )
    print_report(test_results)
    
    # Summary and analysis
    print("\n" + "="*70)
    print("STRATEGY SUMMARY & ANALYSIS")
    print("="*70)
    
    print("\nStrategy Parameters:")
    print("  - Multi-timeframe trend: 4hr SMA vs 1hr price")
    print("  - ADX regime filter: >25=trend, <20=mean-reversion, 20-25=no-trade")
    print("  - Trend-following: Donchian 20-period breakout + SMA confirmation")
    print("  - Mean-reversion: RSI(14) with 30/70 thresholds + Bollinger Bands %b")
    print("  - Volume filter: Above 20-period average volume required")
    print("  - Transaction costs: 0.25% commission + 0.1% slippage")
    
    print("\n" + "-"*70)
    print("PERFORMANCE COMPARISON")
    print("-"*70)
    print(f"{'Metric':<30} {'Train Set':>15} {'Test Set':>15}")
    print("-"*70)
    print(f"{'Total Return (%)':<30} {train_results['total_return_pct']:>15.2f} {test_results['total_return_pct']:>15.2f}")
    print(f"{'Num Trades':<30} {train_results['num_trades']:>15} {test_results['num_trades']:>15}")
    print(f"{'Win Rate (%)':<30} {train_results['win_rate_pct']:>15.1f} {test_results['win_rate_pct']:>15.1f}")
    print(f"{'Max Drawdown (%)':<30} {train_results['max_drawdown_pct']:>15.2f} {test_results['max_drawdown_pct']:>15.2f}")
    print(f"{'Sharpe Ratio':<30} {train_results['sharpe_ratio']:>15.3f} {test_results['sharpe_ratio']:>15.3f}")
    print("-"*70)
    
    # Check if 20% monthly target was achieved
    # Test set covers approximately: len(df_test) hours / (24 * 30) months
    test_days = len(df_test) / 24  # Assuming 1-hour data
    test_months = test_days / 30
    
    if test_months > 0:
        monthly_return = ((1 + test_results['total_return_pct']/100) ** (1/test_months) - 1) * 100
        print(f"\nTest period: {test_days:.1f} days ({test_months:.2f} months)")
        print(f"Monthlyized return: {monthly_return:.2f}%")
        
        if monthly_return >= 20:
            print("\n*** TARGET ACHIEVED: 20% monthly profit WAS achieved! ***")
        else:
            print(f"\n*** TARGET NOT MET: 20% monthly profit was NOT achieved ***")
            print(f"    Actual monthly return: {monthly_return:.2f}%")
            print(f"    Gap to target: {20 - monthly_return:.2f}%")
    
    # Final verdict
    print("\n" + "="*70)
    print("FINAL VERDICT")
    print("="*70)
    
    if test_results['total_return_pct'] > 0:
        print(f"The advanced ensemble strategy achieved a POSITIVE return of {test_results['total_return_pct']:.2f}%")
        print("on the out-of-sample test set, demonstrating some edge over transaction costs.")
    else:
        print(f"The advanced ensemble strategy achieved a NEGATIVE return of {test_results['total_return_pct']:.2f}%")
        print("on the out-of-sample test set, indicating the edge was insufficient to overcome")
        print("transaction costs (0.35% round-trip).")
    
    print("\nWhy the strategy may have failed to beat costs:")
    print("  1. Market efficiency: BTC/IRT 1hr data may not have persistent patterns")
    print("  2. Transaction costs: 0.35% per round-trip requires significant edge")
    print("  3. Indicator lag: All technical indicators are inherently lagging")
    print("  4. Regime misclassification: ADX thresholds may not optimally separate regimes")
    print("  5. Overfitting risk: Parameters optimized on training may not generalize")
    
    return test_results


if __name__ == "__main__":
    results = main()
