"""
Test for StrategySelector KeyError bug fix.

This test verifies that StrategySelector.blend() does not raise KeyError
when strategy_fns contains strategies that were not in the original
candidate_methods list passed to __init__.

Bug scenario:
- StrategySelector was constructed with incomplete candidate_methods (e.g., 5 strategies)
- strategy_fns had additional strategies (trend_following, mean_reversion = 7 total)
- blend() tried to access self._track_record['trend_following'] which didn't exist
- Result: KeyError crashed every rebalance in production

Fix:
- Use .setdefault() to auto-create deque for missing strategies
- Also ensure main.py constructs StrategySelector AFTER strategy_fns is complete
"""

import numpy as np
import pandas as pd
import pytest
from strategy_selector import StrategySelector


def create_mock_data(n_periods=100, n_assets=3):
    """Create mock price and return data for testing."""
    dates = pd.date_range('2024-01-01', periods=n_periods, freq='D')
    prices = pd.DataFrame(
        np.random.rand(n_periods, n_assets) * 100 + 100,
        columns=[f'Asset{i}' for i in range(n_assets)],
        index=dates
    )
    returns = prices.pct_change().dropna()
    return prices, returns


def create_strategy_functions():
    """Create mock strategy functions."""
    def mvo_fn(p, r): return np.array([0.4, 0.3, 0.3])
    def risk_parity_fn(p, r): return np.array([0.33, 0.33, 0.34])
    def cvar_fn(p, r): return np.array([0.5, 0.25, 0.25])
    def trend_following_fn(p, r): return np.array([0.6, 0.2, 0.2])
    def mean_reversion_fn(p, r): return np.array([0.2, 0.5, 0.3])
    
    return {
        'mvo': mvo_fn,
        'risk_parity': risk_parity_fn,
        'cvar': cvar_fn,
        'trend_following': trend_following_fn,
        'mean_reversion': mean_reversion_fn
    }


def test_blend_with_incomplete_candidate_methods():
    """
    Test that blend() handles strategies not in original candidate_methods.
    
    This reproduces the exact bug scenario from production where:
    - StrategySelector was created with ['mvo', 'risk_parity', 'cvar']
    - strategy_fns had 5 strategies including 'trend_following', 'mean_reversion'
    - blend() crashed with KeyError: 'trend_following'
    """
    # Create selector with INCOMPLETE candidate list (simulating old buggy main.py)
    incomplete_candidates = ['mvo', 'risk_parity', 'cvar']
    selector = StrategySelector(candidate_methods=incomplete_candidates)
    
    prices, returns = create_mock_data()
    strategy_fns = create_strategy_functions()
    
    # This should NOT raise KeyError anymore
    result = selector.blend(prices, returns, strategy_fns)
    
    # Verify results
    assert result is not None
    assert len(result) == 2
    combined_weights, blend_weights = result
    
    # Combined weights should be valid numpy array
    assert isinstance(combined_weights, np.ndarray)
    assert len(combined_weights) == 3  # 3 assets
    assert np.isclose(combined_weights.sum(), 1.0, atol=1e-6)
    
    # Blend weights should include ALL strategies from strategy_fns
    assert 'trend_following' in blend_weights
    assert 'mean_reversion' in blend_weights
    assert len(blend_weights) == 5  # All 5 strategies
    
    print("✓ Test passed: blend() handles missing strategies correctly")


def test_blend_with_complete_candidate_methods():
    """
    Test that blend() works correctly when candidate_methods matches strategy_fns.
    
    This is the ideal scenario after fixing main.py to construct StrategySelector
    AFTER strategy_fns is complete.
    """
    # Create selector with COMPLETE candidate list (fixed main.py approach)
    strategy_fns = create_strategy_functions()
    complete_candidates = list(strategy_fns.keys())
    selector = StrategySelector(candidate_methods=complete_candidates)
    
    prices, returns = create_mock_data()
    
    result = selector.blend(prices, returns, strategy_fns)
    
    assert result is not None
    combined_weights, blend_weights = result
    
    assert isinstance(combined_weights, np.ndarray)
    assert len(combined_weights) == 3
    assert np.isclose(combined_weights.sum(), 1.0, atol=1e-6)
    assert len(blend_weights) == 5
    
    print("✓ Test passed: blend() works with complete candidate_methods")


def test_track_record_auto_creation():
    """
    Test that _track_record entries are auto-created for new strategies.
    """
    selector = StrategySelector(candidate_methods=['mvo'])
    
    # Access a strategy not in candidate_methods via setdefault pattern
    # (this is what blend() does internally now)
    from collections import deque
    rec = selector._track_record.setdefault('new_strategy', deque(maxlen=selector.track_record_len))
    
    assert isinstance(rec, deque)
    assert len(rec) == 0
    assert 'new_strategy' in selector._track_record
    
    print("✓ Test passed: _track_record auto-creates missing entries")


def test_multiple_rebalance_cycles():
    """
    Test that multiple consecutive blend() calls work without errors.
    
    This simulates multiple rebalance cycles in production.
    """
    strategy_fns = create_strategy_functions()
    complete_candidates = list(strategy_fns.keys())
    selector = StrategySelector(candidate_methods=complete_candidates)
    
    prices, returns = create_mock_data()
    
    # Simulate 5 consecutive rebalance cycles
    for i in range(5):
        result = selector.blend(prices, returns, strategy_fns)
        assert result is not None
        
        # Record some fake performance to build track record
        selector.record_realized_performance('mvo', 0.02, 0.1)
        selector.record_realized_performance('trend_following', 0.03, 0.15)
    
    print("✓ Test passed: Multiple rebalance cycles work correctly")


if __name__ == '__main__':
    test_blend_with_incomplete_candidate_methods()
    test_blend_with_complete_candidate_methods()
    test_track_record_auto_creation()
    test_multiple_rebalance_cycles()
    print("\n✅ All tests passed!")
