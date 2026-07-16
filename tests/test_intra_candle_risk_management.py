"""
Tests for intra-candle stop-loss / take-profit functionality in backtester.
"""

import pandas as pd
import numpy as np
import sys
sys.path.insert(0, '/workspace/agent/videnv/crypto-bot')

from backtest.backtester import run_backtest


def test_intra_candle_stop_loss_triggers_mid_candle():
    """
    Test that stop-loss triggers within a candle when low price hits the stop level,
    even if the close price doesn't reflect it.
    
    Scenario:
    - Entry at price 100 (with slippage/commission, actual entry ~100.35)
    - Stop loss at 5% below entry = ~95.33
    - Candle has: open=100, high=102, low=94, close=99
    - The low (94) is below stop_loss_level (~95.33), so stop should trigger
    - Exit price should be max(open, stop_loss_level) = max(100, 95.33) = 100
      But wait, we need to think about this more carefully:
      - If low <= stop_loss_level during the candle, it means price touched stop_loss
      - The exit happens at max(open, stop_loss_level) because:
        - If open > stop_loss: price started at open, dropped to stop_loss, we exit at stop_loss
        - If open < stop_loss: price gapped down below stop, we exit at open (first available price)
    """
    # Create synthetic data with known behavior
    # Row 0: setup candle (no signal)
    # Row 1: buy signal (position=1) -> enters at row 2's open
    # Row 2: position is now open, check SL/TP first -> no trigger yet (low=98)
    # Row 3: candle where stop-loss triggers mid-candle
    #        open=100, high=102, low=94, close=99
    #        Entry price will be ~100 * 1.001 * 1.0025 = ~100.35
    #        Stop loss level = 100.35 * 0.95 = ~95.33
    #        Since low (94) < 95.33, stop triggers
    #        Exit price = max(open=100, stop_loss=95.33) = 100
    #        After slippage/commission: 100 * 0.999 * 0.9975 = ~99.65
    
    data = {
        'timestamp': pd.date_range('2024-01-01', periods=5, freq='h'),
        'open': [98, 99, 100, 100, 98],
        'high': [99, 101, 102, 102, 99],
        'low': [97, 98, 98, 94, 97],   # Row 3 has low=94 which triggers stop
        'close': [98, 100, 101, 99, 98],
        'position': [0, 1, 0, 0, 0],  # Buy signal at row 1
    }
    df = pd.DataFrame(data)
    
    # Run backtest with 5% stop loss
    results = run_backtest(
        df,
        initial_capital=10_000_000,
        commission_pct=0.0025,
        slippage_pct=0.001,
        position_size_pct=1.0,
        stop_loss_pct=0.05,
        take_profit_pct=None,
    )
    
    assert "error" not in results, f"Backtest returned error: {results.get('error')}"
    assert results["num_trades"] == 1, f"Expected 1 trade, got {results['num_trades']}"
    
    trade = results["trade_log"].iloc[0]
    assert trade["exit_reason"] == "stop_loss", \
        f"Expected exit_reason='stop_loss', got '{trade['exit_reason']}'"
    
    # Verify exit happened at row 3 (the candle where low triggered stop)
    expected_exit_timestamp = df.loc[3, 'timestamp']
    assert trade["exit_timestamp"] == expected_exit_timestamp, \
        f"Expected exit at {expected_exit_timestamp}, got {trade['exit_timestamp']}"
    
    # Calculate expected values
    entry_open = df.loc[2, 'open']  # 100 (entry happens at row 2's open due to row 1's signal)
    expected_entry_price = entry_open * (1 + 0.001) * (1 + 0.0025)  # ~100.35
    
    # Stop loss level
    stop_loss_level = expected_entry_price * (1 - 0.05)  # ~95.33
    
    # Since low (94) <= stop_loss_level (95.33), stop triggers
    # Exit price before slippage = max(open=100, stop_loss_level=95.33) = 100
    expected_exit_price_before_fees = max(entry_open, stop_loss_level)
    expected_exit_price = expected_exit_price_before_fees * (1 - 0.001) * (1 - 0.0025)  # ~99.65
    
    assert abs(trade["entry_price"] - expected_entry_price) < 0.01, \
        f"Entry price mismatch: expected {expected_entry_price}, got {trade['entry_price']}"
    assert abs(trade["exit_price"] - expected_exit_price) < 0.01, \
        f"Exit price mismatch: expected {expected_exit_price}, got {trade['exit_price']}"
    
    print(f"✓ Intra-candle stop-loss test PASSED")
    print(f"  Entry price: {trade['entry_price']:.2f}")
    print(f"  Exit price: {trade['exit_price']:.2f}")
    print(f"  Exit reason: {trade['exit_reason']}")
    print(f"  PnL: {trade['pnl']:.2f}")


def test_intra_candle_take_profit_triggers_mid_candle():
    """
    Test that take-profit triggers within a candle when high price hits the target level,
    even if the close price doesn't reflect it.
    
    Scenario:
    - Entry at price 100
    - Take profit at 10% above entry = ~110
    - Candle has: open=100, high=112, low=98, close=105
    - The high (112) is above take_profit_level, so take-profit should trigger
    """
    data = {
        'timestamp': pd.date_range('2024-01-01', periods=5, freq='h'),
        'open': [98, 99, 100, 100, 105],
        'high': [99, 101, 102, 112, 106],  # Row 3 has high=112 which triggers TP
        'low': [97, 98, 98, 98, 104],
        'close': [98, 100, 101, 105, 105],
        'position': [0, 1, 0, 0, 0],  # Buy signal at row 1
    }
    df = pd.DataFrame(data)
    
    # Run backtest with 10% take profit
    results = run_backtest(
        df,
        initial_capital=10_000_000,
        commission_pct=0.0025,
        slippage_pct=0.001,
        position_size_pct=1.0,
        stop_loss_pct=None,
        take_profit_pct=0.10,
    )
    
    assert "error" not in results, f"Backtest returned error: {results.get('error')}"
    assert results["num_trades"] == 1, f"Expected 1 trade, got {results['num_trades']}"
    
    trade = results["trade_log"].iloc[0]
    assert trade["exit_reason"] == "take_profit", \
        f"Expected exit_reason='take_profit', got '{trade['exit_reason']}'"
    
    # Verify exit happened at row 3 (the candle where high triggered TP)
    expected_exit_timestamp = df.loc[3, 'timestamp']
    assert trade["exit_timestamp"] == expected_exit_timestamp, \
        f"Expected exit at {expected_exit_timestamp}, got {trade['exit_timestamp']}"
    
    print(f"✓ Intra-candle take-profit test PASSED")
    print(f"  Entry price: {trade['entry_price']:.2f}")
    print(f"  Exit price: {trade['exit_price']:.2f}")
    print(f"  Exit reason: {trade['exit_reason']}")
    print(f"  PnL: {trade['pnl']:.2f}")


def test_stop_loss_and_take_profit_disabled_by_default():
    """
    Test that when stop_loss_pct and take_profit_pct are None (default),
    the backtest behaves exactly as before (only signal-based exits).
    
    Note: Signal execution happens at the NEXT candle's open after the signal.
    So a sell signal at row N will execute at row N+1's open.
    """
    data = {
        'timestamp': pd.date_range('2024-01-01', periods=7, freq='h'),
        'open': [98, 99, 100, 95, 98, 110, 108],
        'high': [99, 101, 102, 96, 99, 111, 109],
        'low': [97, 98, 90, 94, 97, 109, 107],   # Row 2 has very low low, but SL disabled
        'close': [98, 100, 95, 98, 110, 110, 108],
        'position': [0, 1, 0, 0, 0, -1, 0],  # Buy at row 1, sell signal at row 5
    }
    df = pd.DataFrame(data)
    
    # Run backtest WITHOUT stop loss / take profit (default behavior)
    results = run_backtest(
        df,
        initial_capital=10_000_000,
        commission_pct=0.0025,
        slippage_pct=0.001,
        position_size_pct=1.0,
        stop_loss_pct=None,
        take_profit_pct=None,
    )
    
    assert "error" not in results, f"Backtest returned error: {results.get('error')}"
    assert results["num_trades"] == 1, f"Expected 1 trade, got {results['num_trades']}"
    
    trade = results["trade_log"].iloc[0]
    assert trade["exit_reason"] == "signal", \
        f"Expected exit_reason='signal', got '{trade['exit_reason']}'"
    
    # Exit should happen at row 6 (where sell signal executes), not row 2 (where low was)
    expected_exit_timestamp = df.loc[6, 'timestamp']
    assert trade["exit_timestamp"] == expected_exit_timestamp, \
        f"Expected exit at {expected_exit_timestamp}, got {trade['exit_timestamp']}"
    
    print(f"✓ Disabled risk management test PASSED")
    print(f"  Exit reason: {trade['exit_reason']}")
    print(f"  Exit timestamp: {trade['exit_timestamp']}")


if __name__ == "__main__":
    print("=" * 60)
    print("Running intra-candle stop-loss/take-profit unit tests")
    print("=" * 60)
    
    print("\n--- Test 1: Intra-candle stop-loss ---")
    test_intra_candle_stop_loss_triggers_mid_candle()
    
    print("\n--- Test 2: Intra-candle take-profit ---")
    test_intra_candle_take_profit_triggers_mid_candle()
    
    print("\n--- Test 3: Risk management disabled by default ---")
    test_stop_loss_and_take_profit_disabled_by_default()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
