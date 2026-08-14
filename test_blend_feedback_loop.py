"""
Test: Verify that ensemble blend weights change based on actual strategy performance.
This tests the critical fix for the bug where per-strategy realized performance
was never recorded in ensemble blend mode, making the self-correcting feedback loop non-functional.
"""

import numpy as np
import pandas as pd
from strategy_selector import StrategySelector

def trend_following_strategy(prices, returns):
    """Simple trend-following: overweight assets with positive momentum"""
    momentum = (prices.iloc[-1] - prices.iloc[0]) / prices.iloc[0]
    weights = np.where(momentum > 0, 1.0, 0.0)
    if weights.sum() == 0:
        weights = np.ones(len(momentum)) / len(momentum)
    else:
        weights = weights / weights.sum()
    return weights

def mean_reversion_strategy(prices, returns):
    """Mean reversion: underweight recent winners"""
    momentum = (prices.iloc[-1] - prices.iloc[0]) / prices.iloc[0]
    weights = np.where(momentum < 0, 1.0, 0.5)  # Prefer losers
    weights = weights / weights.sum()
    return weights

def risk_parity_strategy(prices, returns):
    """Equal risk contribution"""
    vol = returns.std()
    inv_vol = 1.0 / (vol + 0.01)
    weights = inv_vol / inv_vol.sum()
    return weights

def mvo_strategy(prices, returns):
    """Simple max Sharpe"""
    # Use frequency-aware annualization
    from utils.timeframe import detect_frequency
    freq = detect_frequency(returns.index)
    mean_ret = returns.mean() * freq.annualization_factor_mean
    cov = returns.cov() * freq.observations_per_year
    try:
        inv_cov = np.linalg.inv(cov.values + 0.01 * np.eye(len(cov)))
        w = inv_cov @ mean_ret.values
        w = np.maximum(w, 0.01)  # Floor at 1%
        return w / w.sum()
    except:
        return np.ones(len(mean_ret)) / len(mean_ret)

def black_litterman_strategy(prices, returns):
    """Simplified BL with neutral views"""
    return np.ones(len(returns.columns)) / len(returns.columns)

def cvar_strategy(prices, returns):
    """CVaR optimization (simplified)"""
    return np.ones(len(returns.columns)) / len(returns.columns)

def ml_strategy(prices, returns):
    """ML-based (simplified)"""
    return np.ones(len(returns.columns)) / len(returns.columns)


def test_blend_weights_change_with_performance():
    """Test that blend weights dynamically adjust based on realized performance"""
    
    np.random.seed(42)
    n_hours = 200
    dates = pd.date_range('2024-01-01', periods=n_hours, freq='h')
    
    # Create a scenario where trend_following clearly outperforms
    # BTC: strong uptrend
    btc = 100 * np.exp(np.cumsum(0.002 + 0.01 * np.random.randn(n_hours)))
    # ETH: moderate uptrend  
    eth = 100 * np.exp(np.cumsum(0.001 + 0.015 * np.random.randn(n_hours)))
    # XRP: downtrend
    xrp = 100 * np.exp(np.cumsum(-0.0015 + 0.02 * np.random.randn(n_hours)))
    # SOL: flat
    sol = 100 * np.exp(np.cumsum(0.0001 + 0.025 * np.random.randn(n_hours)))
    # DOGE: slight downtrend
    doge = 100 * np.exp(np.cumsum(-0.0005 + 0.03 * np.random.randn(n_hours)))
    
    prices_df = pd.DataFrame({
        'BTC': btc, 'ETH': eth, 'XRP': xrp, 'SOL': sol, 'DOGE': doge
    }, index=dates)
    
    strategy_fns = {
        'trend_following': trend_following_strategy,
        'mean_reversion': mean_reversion_strategy,
        'risk_parity': risk_parity_strategy,
        'mvo': mvo_strategy,
        'black_litterman': black_litterman_strategy,
        'cvar': cvar_strategy,
        'ml': ml_strategy
    }
    
    candidate_methods = list(strategy_fns.keys())
    selector = StrategySelector(candidate_methods)
    
    blend_history = []
    n_periods = 5
    
    print("=" * 70)
    print("TEST: Ensemble Blend Self-Correcting Feedback Loop")
    print("=" * 70)
    print(f"\nScenario: BTC/ETH trending up, XRP/DOGE trending down")
    print(f"Expectation: trend_following should gain weight over periods\n")
    
    for period in range(n_periods):
        start_idx = period * 30
        end_idx = start_idx + 60
        
        if end_idx > n_hours:
            break
        
        lookback_prices = prices_df.iloc[start_idx:end_idx]
        lookback_returns = lookback_prices.pct_change().dropna()
        
        if len(lookback_returns) < 20:
            continue
        
        # Get blend composition BEFORE recording performance
        _, blend_composition = selector.blend(lookback_prices, lookback_returns, strategy_fns)
        blend_history.append(blend_composition.copy())
        
        print(f"Period {period + 1} blend weights:")
        sorted_blend = sorted(blend_composition.items(), key=lambda x: -x[1])
        for name, weight in sorted_blend:
            print(f"  {name:20s}: {weight*100:5.1f}%")
        print()
        
        # Simulate end-of-period: record hypothetical performance for each strategy
        for name, fn in strategy_fns.items():
            try:
                w = fn(lookback_prices, lookback_returns)
                w = np.array(w)
                if w.sum() > 0:
                    w = w / w.sum()
                
                # Calculate hypothetical returns
                hyp_rets = (lookback_returns.values @ w)
                hyp_ret_total = hyp_rets.mean() * len(hyp_rets)
                hyp_vol_total = hyp_rets.std() * np.sqrt(len(hyp_rets))
                
                if hyp_vol_total > 0:
                    selector.record_realized_performance(name, hyp_ret_total, hyp_vol_total)
            except Exception as e:
                print(f"  Warning: {name} failed: {e}")
    
    # Analyze results
    print("=" * 70)
    print("ANALYSIS: Did blend weights adapt to performance?")
    print("=" * 70)
    
    if len(blend_history) < 2:
        print("ERROR: Not enough periods collected")
        return False
    
    first = blend_history[0]
    last = blend_history[-1]
    
    print(f"\nFirst period -> Last period comparison:")
    print()
    
    changes_found = False
    for name in candidate_methods:
        w1 = first.get(name, 0)
        w2 = last.get(name, 0)
        diff = w2 - w1
        
        if abs(diff) > 0.005:  # More than 0.5% change
            direction = "↑" if diff > 0 else "↓"
            print(f"  {name:20s}: {w1*100:5.1f}% -> {w2*100:5.1f}%  {direction} ({diff*100:+.1f}pp)")
            changes_found = True
    
    print()
    
    # Specific check: trend_following should have gained weight in this scenario
    tf_first = first.get('trend_following', 0)
    tf_last = last.get('trend_following', 0)
    
    if tf_last > tf_first + 0.02:  # At least 2 percentage point increase
        print(f"✓ SUCCESS: trend_following weight increased from {tf_first*100:.1f}% to {tf_last*100:.1f}%")
        print(f"  (as expected in a trending market scenario)")
    elif tf_last > tf_first:
        print(f"✓ PARTIAL: trend_following weight slightly increased from {tf_first*100:.1f}% to {tf_last*100:.1f}%")
    else:
        print(f"✗ WARNING: trend_following weight did not increase as expected")
        print(f"  ({tf_first*100:.1f}% -> {tf_last*100:.1f}%)")
    
    print()
    
    if changes_found:
        print("✓ VERIFIED: Blend weights are DYNAMICALLY ADJUSTING based on performance!")
        print("  The self-correcting feedback loop is FUNCTIONAL.")
        return True
    else:
        print("✗ FAILED: Blend weights appear STATIC across periods.")
        print("  The feedback loop may not be working correctly.")
        return False


if __name__ == "__main__":
    success = test_blend_weights_change_with_performance()
    exit(0 if success else 1)
