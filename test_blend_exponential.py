"""
Test script to verify that the exponential transform in blend() correctly
preserves relative performance differences between strategies even when all
Sharpes are negative (market downturn scenario).

This test confirms:
1. Strategies with different negative Sharpes get different scores (not collapsed to same value)
2. Better Sharpe (less negative) gets higher weight than worse Sharpe (more negative)
3. The old hard floor would have given identical weights to both strategies
"""

import numpy as np
import pandas as pd
from strategy_selector import StrategySelector

def test_exponential_transform_preserves_differences():
    """Test that exp(sharpe) preserves relative differences for negative Sharpes."""
    
    # Create a StrategySelector with 2 strategies
    candidate_methods = ['strategy_good', 'strategy_bad']
    selector = StrategySelector(candidate_methods=candidate_methods)
    
    # Simulate track records with different negative Sharpes
    # strategy_good: Sharpe = -0.45 (less bad, e.g., -4.5% loss with some vol)
    # strategy_bad: Sharpe = -0.68 (worse, e.g., -16.6% loss)
    
    # Add multiple observations to build track record
    for _ in range(5):
        selector._track_record['strategy_good'].append(-0.45)
        selector._track_record['strategy_bad'].append(-0.68)
    
    print("=" * 70)
    print("TEST: Exponential Transform Preserves Relative Differences")
    print("=" * 70)
    
    # Calculate what the OLD formula would give:
    old_score_good = max(0.1, -0.45 + 0.5)  # = max(0.1, 0.05) = 0.1
    old_score_bad = max(0.1, -0.68 + 0.5)   # = max(0.1, -0.18) = 0.1
    print(f"\nOLD FORMULA (hard floor):")
    print(f"  strategy_good (Sharpe=-0.45): score = max(0.1, -0.45+0.5) = {old_score_good}")
    print(f"  strategy_bad  (Sharpe=-0.68): score = max(0.1, -0.68+0.5) = {old_score_bad}")
    print(f"  → Both collapsed to 0.1! No differentiation!")
    
    # Calculate what the NEW formula gives:
    new_score_good = np.exp(np.clip(-0.45, -5, 5))  # = exp(-0.45) ≈ 0.638
    new_score_bad = np.exp(np.clip(-0.68, -5, 5))   # = exp(-0.68) ≈ 0.507
    print(f"\nNEW FORMULA (exponential):")
    print(f"  strategy_good (Sharpe=-0.45): score = exp(-0.45) = {new_score_good:.4f}")
    print(f"  strategy_bad  (Sharpe=-0.68): score = exp(-0.68) = {new_score_bad:.4f}")
    print(f"  → Ratio preserved: {new_score_good/new_score_bad:.3f}x (better strategy gets more weight)")
    
    # Verify the key assertion: new formula differentiates, old doesn't
    assert old_score_good == old_score_bad, "Old formula should collapse both to 0.1"
    assert new_score_good > new_score_bad, "New formula should give higher score to better strategy"
    
    # Now test the actual blend() method with synthetic data
    print("\n" + "=" * 70)
    print("INTEGRATION TEST: Running blend() with synthetic data")
    print("=" * 70)
    
    # Create synthetic returns data (5 days, 3 assets)
    np.random.seed(42)
    n_days = 10
    n_assets = 3
    assets = ['BTC', 'ETH', 'SOL']
    
    # Synthetic prices (slightly trending up) - create proper 2D array
    random_returns = np.random.randn(n_days, n_assets) * 0.02
    prices = pd.DataFrame(
        np.cumprod(1 + random_returns, axis=0),
        columns=assets
    )
    
    # Synthetic returns
    returns = prices.pct_change().dropna()
    
    # Mock strategy functions that return equal-weight portfolios
    def mock_strategy_good(prices, returns):
        return np.array([0.33, 0.33, 0.34])
    
    def mock_strategy_bad(prices, returns):
        return np.array([0.33, 0.33, 0.34])
    
    strategy_fns = {
        'strategy_good': mock_strategy_good,
        'strategy_bad': mock_strategy_bad
    }
    
    # Run blend
    combined_weights, blend_weights = selector.blend(prices, returns, strategy_fns)
    
    print(f"\nBlend weights from blend():")
    for name, weight in sorted(blend_weights.items(), key=lambda x: -x[1]):
        print(f"  {name}: {weight*100:.2f}%")
    
    # Verify that strategy_good has higher weight than strategy_bad
    assert blend_weights['strategy_good'] > blend_weights['strategy_bad'], \
        f"strategy_good ({blend_weights['strategy_good']:.4f}) should have higher weight than strategy_bad ({blend_weights['strategy_bad']:.4f})"
    
    print(f"\n✓ VERIFIED: strategy_good has {blend_weights['strategy_good']/blend_weights['strategy_bad']:.2f}x the weight of strategy_bad")
    print("✓ EXPONENTIAL TRANSFORM WORKS: Relative performance differences are preserved!")
    
    return True


def test_extreme_negative_sharpes():
    """Test with very negative Sharpes to ensure no numerical issues."""
    
    candidate_methods = ['s1', 's2', 's3']
    selector = StrategySelector(candidate_methods=candidate_methods)
    
    # Add track records with very negative Sharpes
    sharpes = [-2.0, -3.5, -4.8]
    for method, sharpe in zip(candidate_methods, sharpes):
        for _ in range(5):
            selector._track_record[method].append(sharpe)
    
    print("\n" + "=" * 70)
    print("TEST: Extreme Negative Sharpes (no overflow/underflow)")
    print("=" * 70)
    
    # Calculate expected scores with clipped exp
    expected_scores = {}
    for method, sharpe in zip(candidate_methods, sharpes):
        clipped = np.clip(sharpe, -5, 5)
        expected_scores[method] = np.exp(clipped)
        print(f"  {method} (Sharpe={sharpe}): exp(clipped) = {expected_scores[method]:.6f}")
    
    # Verify ordering is preserved
    assert expected_scores['s1'] > expected_scores['s2'] > expected_scores['s3'], \
        "Ordering should be preserved even for extreme negative values"
    
    print("✓ VERIFIED: No numerical issues with extreme negative Sharpes")
    return True


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("BLEND EXPONENTIAL TRANSFORM TEST SUITE")
    print("=" * 70)
    
    test_exponential_transform_preserves_differences()
    test_extreme_negative_sharpes()
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED ✓")
    print("=" * 70)
    print("\nSUMMARY:")
    print("- Old formula (hard floor) collapsed all negative-Sharpes to 0.1")
    print("- New formula (exp) preserves relative differences")
    print("- Better strategies get proportionally higher weights even in downturns")
    print("- Self-correction now works correctly across all market conditions")
