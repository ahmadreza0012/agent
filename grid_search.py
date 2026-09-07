#!/usr/bin/env python3
"""
Run RSI strategy grid search with isolated subprocesses for each parameter combination.
"""

import subprocess
import sys
import json

# Parameter combinations to test
PARAM_COMBOS = [
    (14, 30, 70),  # baseline
    (14, 20, 80),  # more conservative thresholds
    (14, 25, 75),
    (21, 30, 70),  # longer period
    (9, 30, 70),   # shorter period
    (14, 35, 65),  # less conservative thresholds
]

# Fixed parameters
COMMISSION_PCT = 0.0025
SLIPPAGE_PCT = 0.001
POSITION_SIZE_PCT = 1.0
INITIAL_CAPITAL = 10_000_000

DATA_FILE = "data/btcirt_180d.csv"
WORKING_DIR = "/workspace/agent/videnv/crypto-bot"

def run_isolated_backtest(rsi_period, oversold, overbought):
    """Run a single backtest in an isolated subprocess."""
    
    code = f'''
import pandas as pd
import sys
import json

sys.path.insert(0, "{WORKING_DIR}")

from strategy.rsi_strategy import apply_rsi_strategy
from backtest.backtester import run_backtest

df = pd.read_csv("{WORKING_DIR}/{DATA_FILE}", parse_dates=["timestamp"])
df = apply_rsi_strategy(df, rsi_period={rsi_period}, oversold={oversold}, overbought={overbought})
results = run_backtest(
    df, 
    initial_capital={INITIAL_CAPITAL}, 
    commission_pct={COMMISSION_PCT}, 
    slippage_pct={SLIPPAGE_PCT}, 
    position_size_pct={POSITION_SIZE_PCT}
)

output = {{
    "num_trades": results["num_trades"],
    "total_return_pct": results["total_return_pct"],
    "win_rate_pct": results["win_rate_pct"],
    "max_drawdown_pct": results["max_drawdown_pct"],
    "sharpe_ratio": results["sharpe_ratio"]
}}
print(json.dumps(output))
'''.strip()

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=WORKING_DIR,
        capture_output=True,
        text=True
    )
    
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    }

def main():
    results = []
    
    print("=" * 80)
    print("RSI STRATEGY GRID SEARCH - ISOLATED SUBPROCESSES")
    print("=" * 80)
    print(f"Data file: {DATA_FILE}")
    print(f"Commission: {COMMISSION_PCT*100:.2f}%, Slippage: {SLIPPAGE_PCT*100:.2f}%, Position Size: {POSITION_SIZE_PCT*100:.0f}%")
    print(f"Initial Capital: {INITIAL_CAPITAL:,}")
    print("=" * 80)
    
    for rsi_period, oversold, overbought in PARAM_COMBOS:
        print(f"\n--- Running: rsi_period={rsi_period}, oversold={oversold}, overbought={overbought} ---\n")
        
        proc_result = run_isolated_backtest(rsi_period, oversold, overbought)
        
        print("STDOUT:")
        print(proc_result["stdout"])
        if proc_result["stderr"]:
            print("STDERR:")
            print(proc_result["stderr"])
        print(f"Return code: {proc_result['returncode']}")
        print("-" * 80)
        
        if proc_result["returncode"] == 0:
            try:
                metrics = json.loads(proc_result["stdout"].strip())
                results.append({
                    "rsi_period": rsi_period,
                    "oversold": oversold,
                    "overbought": overbought,
                    **metrics
                })
            except json.JSONDecodeError as e:
                print(f"ERROR: Could not parse JSON output: {e}")
        else:
            print(f"ERROR: Subprocess failed with return code {proc_result['returncode']}")
    
    # Sort by total_return_pct descending
    results.sort(key=lambda x: x["total_return_pct"], reverse=True)
    
    print("\n" + "=" * 80)
    print("FINAL RESULTS TABLE (sorted by total_return_pct descending)")
    print("=" * 80)
    print(f"{'rsi_period':<12} {'oversold':<10} {'overbought':<12} {'num_trades':<12} {'total_return_pct':<18} {'win_rate_pct':<14} {'max_drawdown_pct':<18} {'sharpe_ratio':<12}")
    print("-" * 108)
    
    for r in results:
        print(f"{r['rsi_period']:<12} {r['oversold']:<10} {r['overbought']:<12} {r['num_trades']:<12} {r['total_return_pct']:>16.2f}% {r['win_rate_pct']:>12.2f}% {r['max_drawdown_pct']:>16.2f}% {r['sharpe_ratio']:>12.3f}")
    
    print("=" * 80)
    
    # Sanity check for baseline
    baseline = next((r for r in results if r["rsi_period"] == 14 and r["oversold"] == 30 and r["overbought"] == 70), None)
    if baseline:
        print(f"\nSANITY CHECK: Baseline (14, 30, 70) -> num_trades={baseline['num_trades']}, total_return_pct={baseline['total_return_pct']:.2f}%")
        if baseline["num_trades"] == 13 and abs(baseline["total_return_pct"] - (-26.00)) < 0.01:
            print("✓ Baseline matches expected values (13 trades, -26.00% return)")
        else:
            print("✗ WARNING: Baseline does NOT match expected values!")

if __name__ == "__main__":
    main()
