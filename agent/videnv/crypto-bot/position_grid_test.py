import sys
import os
import subprocess
import pandas as pd

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

def worker(position_size):
    from strategy.rsi_strategy import apply_rsi_strategy
    from backtest.backtester import run_backtest
    
    # Path to the trusted dataset
    data_path = os.path.join(BASE_DIR, 'data', 'btcirt_180d.csv')
    df = pd.read_csv(data_path, parse_dates=['timestamp'])
    
    # Apply RSI (14, 30, 70) baseline
    df = apply_rsi_strategy(df, rsi_period=14, oversold=30, overbought=70)
    
    # Run backtest without SL/TP, pure signal exits
    results = run_backtest(
        df,
        initial_capital=10_000_000,
        position_size_pct=position_size,
        stop_loss_pct=None,
        take_profit_pct=None
    )
    
    # Extract and print exactly what we need
    print(f"=== Position Size: {position_size * 100:.0f}% ===")
    print(f"num_trades: {results['num_trades']}")
    print(f"total_return_pct: {results['total_return_pct']:.2f}%")
    print(f"win_rate_pct: {results['win_rate_pct']:.1f}%")
    print(f"max_drawdown_pct: {results['max_drawdown_pct']:.2f}%")
    print(f"final_capital: {results['final_capital']:.2f}")
    print("-" * 40)

if __name__ == "__main__":
    # If called with 'worker' argument, run for a specific position size
    if len(sys.argv) > 2 and sys.argv[1] == 'worker':
        worker(float(sys.argv[2]))
    else:
        # Main process: grid search using isolated subprocesses
        sizes = [1.0, 0.5, 0.25, 0.1, 0.05]
        print("Starting Position Sizing Grid Search (Isolated Subprocesses)...")
        print("=" * 40)
        
        for s in sizes:
            # Execute this script in a new Python process
            proc = subprocess.run(
                [sys.executable, __file__, 'worker', str(s)],
                capture_output=True,
                text=True,
                cwd=BASE_DIR
            )
            print(proc.stdout)
            if proc.returncode != 0:
                print(f"ERROR in subprocess for size {s}:")
                print(proc.stderr)
