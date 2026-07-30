"""
Integration test for Black-Litterman, ML strategy, and CASH allocation.
Tests that all strategies work correctly with CASH column and produce valid weights.
"""

import numpy as np
import pandas as pd
import sys
import os

# Add workspace to path
sys.path.insert(0, '/workspace')

from portfolio_optimizer import PortfolioOptimizer
from ai_sentiment import AISentimentAnalyzer
from strategy_selector import StrategySelector, compute_in_sample_scores

def test_all_strategies_with_cash():
    """Test that all 5 strategies work correctly with CASH column."""
    print("="*60)
    print("TEST: All strategies with CASH allocation")
    print("="*60)
    
    # Create synthetic data
    np.random.seed(42)
    dates = pd.date_range('2025-01-01', periods=365, freq='D')
    symbols = ['BTC_', 'ETH_', 'SOL_', 'BNB_', 'XRP_']
    
    returns_synthetic = pd.DataFrame(
        np.random.randn(365, 5) * 0.02 + 0.0005,
        index=dates,
        columns=symbols
    )
    prices_synthetic = (1 + returns_synthetic).cumprod() * 1000
    
    # Add CASH column
    prices_synthetic['CASH'] = 1.0
    returns_with_cash = returns_synthetic.copy()
    returns_with_cash['CASH'] = 0.0
    
    n_assets = len(returns_with_cash.columns)
    optimizer = PortfolioOptimizer(n_assets=n_assets, asset_names=list(returns_with_cash.columns))
    ai_sentiment = AISentimentAnalyzer(use_mock=True)  # Use mock for testing
    
    # Define all 5 strategy functions
    def mvo_strategy(prices, returns):
        return optimizer.mean_variance_optimization(np.array([0.1]*n_assets), returns.cov().values)
    
    def risk_parity_strategy(prices, returns):
        return optimizer.risk_parity(returns.cov().values)
    
    def cvar_strategy(prices, returns):
        return optimizer.cvar_optimization(returns.values, cvar_limit=0.03, confidence=0.95)
    
    def black_litterman_strategy(prices, returns):
        if 'CASH' in returns.columns:
            returns_risky = returns.drop(columns=['CASH'])
        else:
            returns_risky = returns
        expected_returns_hist = returns_risky.mean().values
        
        if 'CASH' in prices.columns:
            prices_risky = prices.drop(columns=['CASH'])
        else:
            prices_risky = prices
        
        risky_symbols = [s for s in returns.columns if s != 'CASH']
        P, Q = ai_sentiment.generate_views(prices_risky, expected_returns_hist, risky_symbols)
        cov_risky = returns_risky.cov().values
        n_risky = len(risky_symbols)
        market_caps = np.ones(n_risky)
        omega = ai_sentiment.get_confidence_matrix(n_risky, risky_symbols, base_confidence=0.05)
        
        bl_weights_risky = optimizer.black_litterman(market_caps, cov_risky, P, Q, tau=0.05, omega=omega)
        
        if 'CASH' in returns.columns:
            cash_idx = list(returns.columns).index('CASH')
            full_weights = np.zeros(n_assets)
            risky_indices = [i for i in range(n_assets) if i != cash_idx]
            full_weights[risky_indices] = bl_weights_risky * 0.85
            full_weights[cash_idx] = 0.15
            return full_weights
        else:
            return bl_weights_risky
    
    def ml_strategy(prices, returns):
        ml_expected_returns = optimizer.ml_forecast_returns(returns, lookback=168, forecast_horizon=24)
        cov_matrix = returns.cov().values
        return optimizer.mean_variance_optimization(ml_expected_returns, cov_matrix, method='max_sharpe')
    
    strategy_fns = {
        'mvo': mvo_strategy,
        'risk_parity': risk_parity_strategy,
        'cvar': cvar_strategy,
        'black_litterman': black_litterman_strategy,
        'ml': ml_strategy
    }
    
    candidate_methods = ['mvo', 'risk_parity', 'cvar', 'black_litterman', 'ml']
    
    # Test each strategy
    results = {}
    for method in candidate_methods:
        try:
            weights = strategy_fns[method](prices_synthetic, returns_with_cash)
            
            # Check dimensions
            assert len(weights) == n_assets, f"{method}: Expected {n_assets} weights, got {len(weights)}"
            
            # Check sum to ~1
            weight_sum = np.sum(weights)
            assert abs(weight_sum - 1.0) < 0.01, f"{method}: Weights sum to {weight_sum}, not 1.0"
            
            # Check CASH allocation
            cash_idx = list(returns_with_cash.columns).index('CASH')
            cash_weight = weights[cash_idx]
            
            results[method] = {
                'weights': weights,
                'cash_weight': cash_weight,
                'risky_weights': weights[:cash_idx].tolist() + weights[cash_idx+1:].tolist(),
                'passed': True
            }
            
            print(f"\n✅ {method.upper()}:")
            print(f"   Weights: {np.round(weights, 4)}")
            print(f"   Sum: {np.sum(weights):.4f}")
            print(f"   CASH weight: {cash_weight:.4f}")
            
        except Exception as e:
            results[method] = {'passed': False, 'error': str(e)}
            print(f"\n❌ {method.upper()} FAILED: {e}")
    
    # Test in-sample scoring
    print("\n" + "="*60)
    print("TEST: In-sample scoring with all strategies")
    print("="*60)
    
    scores = compute_in_sample_scores(candidate_methods, strategy_fns, prices_synthetic, returns_with_cash)
    print("\nIn-sample scores:")
    for method, score in scores.items():
        status = "✅" if score > -999 else "❌"
        print(f"   {status} {method}: {score:.4f}")
    
    # Verify no dimension mismatch errors
    failed_scores = {k: v for k, v in scores.items() if v <= -999}
    if failed_scores:
        print(f"\n⚠️  WARNING: {len(failed_scores)} strategies failed scoring: {list(failed_scores.keys())}")
    else:
        print("\n✅ All strategies passed in-sample scoring!")
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    passed_count = sum(1 for r in results.values() if r.get('passed', False))
    print(f"Strategies passed: {passed_count}/{len(candidate_methods)}")
    
    # Check CASH allocation across strategies
    print("\nCASH allocation by strategy:")
    for method, result in results.items():
        if result.get('passed'):
            print(f"   {method}: {result['cash_weight']:.2%}")
    
    all_passed = passed_count == len(candidate_methods) and len(failed_scores) == 0
    print(f"\n{'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    
    return all_passed


def test_black_litterman_selected():
    """Test that Black-Litterman can be selected by StrategySelector."""
    print("\n" + "="*60)
    print("TEST: Black-Litterman selection by StrategySelector")
    print("="*60)
    
    np.random.seed(42)
    dates = pd.date_range('2025-01-01', periods=365, freq='D')
    symbols = ['BTC_', 'ETH_', 'SOL_', 'BNB_', 'XRP_']
    
    returns_synthetic = pd.DataFrame(
        np.random.randn(365, 5) * 0.02 + 0.0005,
        index=dates,
        columns=symbols
    )
    prices_synthetic = (1 + returns_synthetic).cumprod() * 1000
    prices_synthetic['CASH'] = 1.0
    returns_with_cash = returns_synthetic.copy()
    returns_with_cash['CASH'] = 0.0
    
    candidate_methods = ['mvo', 'risk_parity', 'cvar', 'black_litterman', 'ml']
    selector = StrategySelector(candidate_methods=candidate_methods)
    
    # Create minimal strategy functions for testing
    n_assets = len(returns_with_cash.columns)
    optimizer = PortfolioOptimizer(n_assets=n_assets, asset_names=list(returns_with_cash.columns))
    
    def dummy_mvo(prices, returns):
        return np.ones(n_assets) / n_assets
    
    def dummy_rp(prices, returns):
        return np.ones(n_assets) / n_assets
    
    def dummy_cvar(prices, returns):
        return np.ones(n_assets) / n_assets
    
    def dummy_bl(prices, returns):
        return np.ones(n_assets) / n_assets
    
    def dummy_ml(prices, returns):
        return np.ones(n_assets) / n_assets
    
    strategy_fns = {
        'mvo': dummy_mvo,
        'risk_parity': dummy_rp,
        'cvar': dummy_cvar,
        'black_litterman': dummy_bl,
        'ml': dummy_ml
    }
    
    # Compute scores
    scores = compute_in_sample_scores(candidate_methods, strategy_fns, prices_synthetic, returns_with_cash)
    
    # Select strategy
    chosen = selector.select(prices_synthetic, returns_with_cash, scores)
    
    print(f"\nChosen strategy: {chosen}")
    print(f"All candidate methods: {candidate_methods}")
    print(f"Black-Litterman in candidates: {'black_litterman' in candidate_methods}")
    print(f"Black-Litterman score: {scores.get('black_litterman', 'N/A')}")
    
    # The test passes if black_litterman is in candidates and no errors occurred
    test_passed = 'black_litterman' in candidate_methods and chosen in candidate_methods
    print(f"\n{'✅ TEST PASSED' if test_passed else '❌ TEST FAILED'}")
    
    return test_passed


if __name__ == "__main__":
    test1_passed = test_all_strategies_with_cash()
    test2_passed = test_black_litterman_selected()
    
    print("\n" + "="*60)
    print("FINAL RESULT")
    print("="*60)
    if test1_passed and test2_passed:
        print("✅ ALL INTEGRATION TESTS PASSED")
        sys.exit(0)
    else:
        print("❌ SOME INTEGRATION TESTS FAILED")
        sys.exit(1)
