import sys
import os
import subprocess
import pandas as pd
import numpy as np

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

def worker(filter_type):
    from strategy.rsi_strategy import apply_rsi_strategy
    from backtest.backtester import run_backtest
    
    # Path to the trusted dataset
    data_path = os.path.join(BASE_DIR, 'data', 'btcirt_180d.csv')
    df = pd.read_csv(data_path, parse_dates=['timestamp'])
    
    # Apply RSI (14, 30, 70) baseline
    df = apply_rsi_strategy(df, rsi_period=14, oversold=30, overbought=70)
    
    # Apply 50-period MA for trend filter
    df['ma50'] = df['close'].rolling(window=50).mean()
    df['ma50_prev'] = df['ma50'].shift(1)
    df['ma_sloping_up'] = df['ma50'] > df['ma50_prev']
    df['price_above_ma50'] = df['close'] > df['ma50']
    
    # Create filtered signals based on filter type
    if filter_type == 'baseline':
        # No filter - just use original RSI signals
        df['position_filtered'] = df['position']
        filter_name = "RSI Baseline (no filter)"
    elif filter_type == 'price_above_ma50':
        # Only allow long signals when price is above MA50
        df['position_filtered'] = df.apply(lambda row: 
            row['position'] if (row['position'] == 1 and row['price_above_ma50']) or row['position'] != 1 else 0, axis=1)
        filter_name = "RSI + Price Above MA50"
    elif filter_type == 'ma_sloping_up':
        # Only allow long signals when MA50 is sloping up
        df['position_filtered'] = df.apply(lambda row:
            row['position'] if (row['position'] == 1 and row['ma_sloping_up']) or row['position'] != 1 else 0, axis=1)
        filter_name = "RSI + MA50 Sloping Up"
    elif filter_type == 'both':
        # Only allow long signals when BOTH conditions are true
        df['position_filtered'] = df.apply(lambda row:
            row['position'] if (row['position'] == 1 and row['price_above_ma50'] and row['ma_sloping_up']) or row['position'] != 1 else 0, axis=1)
        filter_name = "RSI + Price Above MA50 + MA Sloping Up"
    else:
        raise ValueError(f"Unknown filter type: {filter_type}")
    
    # Rename position_filtered to position for backtester
    df['position'] = df['position_filtered']
    
    # Run backtest without SL/TP, pure signal exits
    results = run_backtest(
        df,
        initial_capital=10_000_000,
        position_size_pct=1.0,
        stop_loss_pct=None,
        take_profit_pct=None
    )
    
    # Handle case where no trades occurred
    if 'num_trades' not in results:
        print(f"=== {filter_name} ===")
        print(f"Error: No trades executed")
        print(f"Details: {results}")
        print("-" * 50)
        return
    
    # Extract and print exactly what we need
    print(f"=== {filter_name} ===")
    print(f"num_trades: {results['num_trades']}")
    print(f"total_return_pct: {results['total_return_pct']:.2f}%")
    print(f"win_rate_pct: {results['win_rate_pct']:.1f}%")
    print(f"max_drawdown_pct: {results['max_drawdown_pct']:.2f}%")
    print(f"final_capital: {results['final_capital']:.2f}")
    print("-" * 50)

if __name__ == "__main__":
    # If called with 'worker' argument, run for a specific filter type
    if len(sys.argv) > 2 and sys.argv[1] == 'worker':
        worker(sys.argv[2])
    else:
        # Main process: run all filter types using isolated subprocesses
        filters = ['baseline', 'price_above_ma50', 'ma_sloping_up', 'both']
        print("Starting Trend-Filtered RSI Grid Search (Isolated Subprocesses)...")
        print("=" * 50)
        
        for f in filters:
            # Execute this script in a new Python process
            proc = subprocess.run(
                [sys.executable, __file__, 'worker', f],
                capture_output=True,
                text=True,
                cwd=BASE_DIR
            )
            print(proc.stdout)
            if proc.returncode != 0:
                print(f"ERROR in subprocess for filter {f}:")
                print(proc.stderr)
