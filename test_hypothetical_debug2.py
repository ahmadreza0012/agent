"""Debug test to verify hypothetical performance calculation for each strategy"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)

from backtester import Backtester
from strategy_selector import StrategySelector

np.random.seed(42)
n_hours = 500
n_assets = 6
asset_names = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA']

returns = np.random.randn(n_hours, n_assets) * 0.02 + 0.0001
prices_array = 100 * np.cumprod(1 + returns, axis=0)
cash_column = np.ones((n_hours, 1)) * (1 + 0.00001 * np.arange(n_hours)).reshape(-1, 1)
prices_with_cash = np.hstack([prices_array, cash_column])

dates = pd.date_range(start='2024-01-01', periods=n_hours, freq='h')
columns = asset_names + ['CASH']
df_prices = pd.DataFrame(prices_with_cash, index=dates, columns=columns)

def equal_weight(prices, returns):
    return np.ones(len(prices.columns)) / len(prices.columns)

def btc_bias(prices, returns):
    w = np.zeros(len(prices.columns))
    w[0] = 0.5
    w[1:] = 0.5 / (len(prices.columns) - 1)
    return w

def eth_bias(prices, returns):
    w = np.zeros(len(prices.columns))
    w[1] = 0.5
    w[:1] = 0.25
    w[2:] = 0.25 / (len(prices.columns) - 2)
    return w

def cash_heavy(prices, returns):
    w = np.zeros(len(prices.columns))
    w[-1] = 0.7
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
strategy_selector = StrategySelector(candidate_methods=candidate_methods)
backtester = Backtester(initial_capital=100000)

print("\nRunning single fold test with more rebalancing events...")

# Manually run a single fold with smaller train set to get more rebalances
test_start_idx = int(len(df_prices) * 0.5)
train_prices = df_prices.iloc[:test_start_idx]
test_prices = df_prices.iloc[test_start_idx:]

print(f"Train: {len(train_prices)} rows, Test: {len(test_prices)} rows")

result = backtester.run_single_fold(
    prices=train_prices,
    test_prices=test_prices,
    n_train=len(train_prices),
    weights_strategy=equal_weight,
    strategy_selector=strategy_selector,
    strategy_fns=strategy_fns,
    use_blend=True
)

print(f"\nRebalance events: {len(result['rebalance_events'])}")

if len(result['rebalance_events']) > 0:
    last_event = result['rebalance_events'][-1]
    if 'individual_weights' in last_event and last_event['individual_weights']:
        print(f"Individual strategies recorded: {list(last_event['individual_weights'].keys())}")

print(f"\nBacktester strategy_realized_performance:")
for name, perf in backtester.strategy_realized_performance.items():
    print(f"  {name}: return={perf['return']:.6f}, vol={perf['vol']:.6f}")

# Verify that hypothetical returns are different for each strategy
print("\nVerifying hypothetical returns are distinct and non-NaN:")
if backtester.strategy_realized_performance:
    returns_list = [(name, perf['return']) for name, perf in backtester.strategy_realized_performance.items()]
    print(f"Returns: {returns_list}")
    
    # Check for NaN
    has_nan = any(np.isnan(r[1]) for r in returns_list)
    print(f"Has NaN: {has_nan}")
    
    # Check for uniqueness (excluding ensemble_blend)
    individual_returns = [r[1] for r in returns_list if r[0] != 'ensemble_blend']
    unique_count = len(set(individual_returns))
    total_count = len(individual_returns)
    print(f"Unique individual returns: {unique_count}/{total_count}")
else:
    print("No performance data recorded!")

print("\n✅ Test completed!")
