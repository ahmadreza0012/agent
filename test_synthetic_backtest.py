"""
Synthetic backtest to verify the hypothetical performance calculation fix.
Uses synthetic data with 200 hours, 7 strategies (6 assets + CASH), use_blend=True
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from backtester import Backtester
from strategy_selector import StrategySelector

# Create synthetic price data for 6 assets + CASH
np.random.seed(42)
n_hours = 200
n_assets = 6  # BTC, ETH, SOL, BNB, XRP, and one more
asset_names = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA']

# Generate random walks for prices
returns = np.random.randn(n_hours, n_assets) * 0.02 + 0.0001
prices_array = 100 * np.cumprod(1 + returns, axis=0)

# Add CASH column (constant = 1, or slowly growing)
cash_column = np.ones((n_hours, 1)) * (1 + 0.00001 * np.arange(n_hours)).reshape(-1, 1)
prices_with_cash = np.hstack([prices_array, cash_column])

print(f"prices_with_cash shape: {prices_with_cash.shape}")

# Create DataFrame
dates = pd.date_range(start='2024-01-01', periods=n_hours, freq='h')
columns = asset_names + ['CASH']
df_prices = pd.DataFrame(prices_with_cash, index=dates, columns=columns)

print("=" * 70)
print("SYNTHETIC BACKTEST - Verifying Hypothetical Performance Fix")
print("=" * 70)
print(f"Data shape: {df_prices.shape}")
print(f"Date range: {df_prices.index.min()} to {df_prices.index.max()}")
print(f"Assets: {list(df_prices.columns)}")

# Define 7 simple strategies
def equal_weight(prices, returns):
    n = len(prices.columns)
    return np.ones(n) / n

def btc_bias(prices, returns):
    w = np.zeros(len(prices.columns))
    w[0] = 0.5  # BTC
    w[1:] = 0.5 / (len(prices.columns) - 1)
    return w

def eth_bias(prices, returns):
    w = np.zeros(len(prices.columns))
    w[1] = 0.5  # ETH
    w[:1] = 0.25
    w[2:] = 0.25 / (len(prices.columns) - 2)
    return w

def cash_heavy(prices, returns):
    w = np.zeros(len(prices.columns))
    w[-1] = 0.7  # CASH (last column)
    w[:-1] = 0.3 / (len(prices.columns) - 1)
    return w

def momentum(prices, returns):
    if len(returns) < 10:
        return equal_weight(prices, returns)
    mean_ret = returns.mean()
    w = np.maximum(mean_ret.values, 0) + 0.1
    if w.sum() > 0:
        w = w / w.sum()
    return w

def min_vol(prices, returns):
    if len(returns) < 10:
        return equal_weight(prices, returns)
    cov = returns.cov().values
    try:
        inv_cov = np.linalg.inv(cov + 0.01 * np.eye(len(cov)))
        w = inv_cov @ np.ones(len(cov))
        if w.sum() > 0:
            w = w / w.sum()
        return w
    except:
        return equal_weight(prices, returns)

def risk_parity(prices, returns):
    if len(returns) < 10:
        return equal_weight(prices, returns)
    vol = returns.std().values + 1e-6
    w = 1 / vol
    if w.sum() > 0:
        w = w / w.sum()
    return w

strategy_fns = {
    'equal_weight': equal_weight,
    'btc_bias': btc_bias,
    'eth_bias': eth_bias,
    'cash_heavy': cash_heavy,
    'momentum': momentum,
    'min_vol': min_vol,
    'risk_parity': risk_parity
}

candidate_methods = list(strategy_fns.keys())
print(f"\nStrategies: {candidate_methods}")

strategy_selector = StrategySelector(candidate_methods=candidate_methods)
backtester = Backtester(initial_capital=100000)

print("\nRunning walk-forward backtest with use_blend=True...")
try:
    results = backtester.run_walk_forward(
        prices=df_prices,
        n_folds=2,
        strategy_selector=strategy_selector,
        strategy_fns=strategy_fns,
        use_blend=True
    )
    print("\n✅ SUCCESS! No ValueError or shape mismatch occurred.")
    
    # Check aggregated metrics
    if 'aggregated' in results:
        agg = results['aggregated']
        print(f"\nAggregated Metrics:")
        print(f"  Mean Monthly Return: {agg.get('mean_monthly_return', 'N/A')}")
        print(f"  Worst Max Drawdown: {agg.get('worst_max_drawdown', 'N/A')}")
        print(f"  Mean Sharpe: {agg.get('mean_sharpe', 'N/A')}")
    
    # Check fold results
    if 'folds' in results:
        print(f"\nFold Results ({len(results['folds'])} folds):")
        for i, fold in enumerate(results['folds']):
            if 'metrics' in fold:
                m = fold['metrics']
                print(f"  Fold {i+1}: Return={m.get('total_return', 'N/A'):.4f}, "
                      f"Sharpe={m.get('sharpe_ratio', 'N/A'):.4f}")
    
    # Check strategy realized performance
    print(f"\nStrategy Realized Performance (from backtester):")
    for name, perf in backtester.strategy_realized_performance.items():
        print(f"  {name}: return={perf['return']:.6f}, vol={perf['vol']:.6f}")
    
except Exception as e:
    print(f"\n❌ FAILED with error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
