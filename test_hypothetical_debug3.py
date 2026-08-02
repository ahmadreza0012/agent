"""Debug test to see why hypothetical returns aren't being recorded for individual strategies"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.DEBUG)

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

print("\nRunning single fold test with DEBUG logging...")

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
        print(f"\nIndividual weights recorded:")
        for name, w in last_event['individual_weights'].items():
            print(f"  {name}: shape={w.shape}, sum={w.sum():.4f}")

# Manually compute what the hypothetical returns should be
print("\n\nManual verification of hypothetical calculation:")
test_asset_returns = test_prices.pct_change().dropna()
daily_returns = result['daily_returns']
returns_series = pd.Series(daily_returns)

print(f"test_asset_returns shape: {test_asset_returns.shape}")
print(f"daily_returns length: {len(daily_returns)}")
print(f"returns_series index: {returns_series.index[:3]}...")
print(f"test_asset_returns index: {test_asset_returns.index[:3]}...")

common_index = test_asset_returns.index.intersection(returns_series.index)
aligned_asset_returns = test_asset_returns.loc[common_index]
print(f"\nAligned asset returns shape: {aligned_asset_returns.shape}")

for name, ind_weights in last_event['individual_weights'].items():
    hypothetical_daily_returns = aligned_asset_returns.values @ ind_weights
    hyp_returns_series = pd.Series(hypothetical_daily_returns, index=common_index)
    hypothetical_realized_return = hyp_returns_series.mean() * len(hyp_returns_series)
    hypothetical_realized_vol = hyp_returns_series.std() * np.sqrt(len(hyp_returns_series))
    print(f"{name}: return={hypothetical_realized_return:.6f}, vol={hypothetical_realized_vol:.6f}")

print("\n✅ Test completed!")
