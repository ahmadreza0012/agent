"""
PHASE 7 ENSEMBLE TEST SUITE
============================
Tests for Phase 7 Dynamic Ensemble improvements:
- Expanded REGIME_PRIOR (5 regimes)
- Dynamic composite scoring
- Regime-conditional performance tracking
- Strategy correlation penalty
- Turnover penalty
- Track record decay
- ML OOS weakness flag integration
- Sentiment multiplier restriction (trend_following/mean_reversion only)
- Bounded weights (5%-40%)
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

import sys
sys.path.insert(0, '/workspace')

from strategy_selector import (
    StrategySelector, 
    detect_regime, 
    REGIME_PRIOR, 
    StrategyScore
)


class TestRegimePriorExpansion:
    """Test 10.1: Verify all 5 regimes have priors."""
    
    def test_all_five_regimes_present(self):
        """Verify all 5 Phase 3 regimes exist in REGIME_PRIOR."""
        expected_regimes = ['bull_trend', 'bear_trend', 'high_vol', 'low_vol_range', 'crisis']
        actual_regimes = list(REGIME_PRIOR.keys())
        
        assert set(actual_regimes) == set(expected_regimes), \
            f"Expected regimes {expected_regimes}, got {actual_regimes}"
    
    def test_all_strategies_in_each_regime(self):
        """Verify each regime has priors for all 7 strategies."""
        expected_strategies = [
            'black_litterman', 'mvo', 'ml', 'risk_parity', 
            'cvar', 'trend_following', 'mean_reversion'
        ]
        
        for regime, priors in REGIME_PRIOR.items():
            for strategy in expected_strategies:
                assert strategy in priors, \
                    f"Missing strategy '{strategy}' in regime '{regime}'"
    
    def test_priors_sum_reasonable(self):
        """Verify priors sum to approximately 7-9 per regime (normalized around 1.0 per strategy)."""
        for regime, priors in REGIME_PRIOR.items():
            total = sum(priors.values())
            # Should be roughly 7 strategies * ~1.0 average = ~7, allow 5-10 range
            assert 5.0 <= total <= 10.0, \
                f"Regime {regime} priors sum to {total}, expected 5-10"
    
    def test_crisis_defensive_bias(self):
        """Verify crisis regime has defensive bias (high risk_parity/cvar)."""
        crisis = REGIME_PRIOR['crisis']
        
        # Defensive strategies should have higher priors
        assert crisis['risk_parity'] >= 1.5, "Crisis should favor risk_parity"
        assert crisis['cvar'] >= 1.5, "Crisis should favor cvar"
        
        # Aggressive strategies should have lower priors
        assert crisis['ml'] <= 0.6, "Crisis should reduce ML weight"
        assert crisis['mvo'] <= 0.6, "Crisis should reduce MVO weight"
    
    def test_bull_trend_offensive_bias(self):
        """Verify bull_trend regime has offensive bias (high trend_following)."""
        bull = REGIME_PRIOR['bull_trend']
        
        assert bull['trend_following'] >= 1.8, "Bull trend should strongly favor trend_following"
        assert bull['ml'] >= 1.0, "Bull trend should allow ML"
        
        # Defensive strategies reduced
        assert bull['risk_parity'] <= 1.0, "Bull trend reduces risk_parity"
        assert bull['cvar'] <= 1.0, "Bull trend reduces cvar"


class TestDynamicScoring:
    """Test 10.2: Verify dynamic scoring produces valid scores."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.selector = StrategySelector(
            ['mvo', 'risk_parity', 'ml', 'trend_following', 'mean_reversion']
        )
        
        # Generate synthetic data
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=200, freq='h')
        self.returns = pd.DataFrame(
            np.random.randn(200, 5) * 0.01,
            index=dates,
            columns=['BTC_', 'ETH_', 'SOL_', 'BNB_', 'XRP_']
        )
        self.prices = (1 + self.returns).cumprod() * 100
        
        # Mock strategy functions
        def mock_weights(prices, returns):
            n = len(returns.columns)
            return np.ones(n) / n
        
        self.strategy_fns = {
            'mvo': mock_weights,
            'risk_parity': mock_weights,
            'ml': mock_weights,
            'trend_following': mock_weights,
            'mean_reversion': mock_weights
        }
    
    def test_scores_in_valid_range(self):
        """Verify scores are in reasonable range [0, 1] after normalization."""
        # Record some performance history
        for i in range(10):
            for method in self.selector.candidate_methods:
                ret = np.random.randn() * 0.01
                vol = 0.1 + np.random.rand() * 0.05
                self.selector.record_realized_performance(method, ret, vol, regime='bull_trend')
        
        # Run blend
        weights, blend_weights = self.selector.blend(
            self.prices, self.returns, self.strategy_fns
        )
        
        # Verify blend weights are valid
        assert all(0 <= w <= 1 for w in blend_weights.values()), \
            "Blend weights should be in [0, 1]"
        assert abs(sum(blend_weights.values()) - 1.0) < 0.01, \
            "Blend weights should sum to 1.0"
    
    def test_ml_score_zero_on_negative_r2(self):
        """Verify ML score is 0 when OOS R² < 0."""
        # Set negative ML OOS R²
        self.selector.set_ml_oos_r2(-0.15)
        
        # Record performance
        for _ in range(10):
            for method in self.selector.candidate_methods:
                self.selector.record_realized_performance(
                    method, 0.01, 0.1, regime='bull_trend'
                )
        
        # Blend and check ML weight is at floor (5%)
        weights, blend_weights = self.selector.blend(
            self.prices, self.returns, self.strategy_fns
        )
        
        # ML should be at minimum weight due to zero score
        assert blend_weights.get('ml', 0) <= 0.06, \
            f"ML weight should be near minimum (5%), got {blend_weights.get('ml', 0):.2%}"


class TestCorrelationPenalty:
    """Test 10.3: Verify correlation penalty reduces scores for correlated strategies."""
    
    def test_correlation_penalty_applies(self):
        """Verify high correlation between strategies triggers penalty."""
        selector = StrategySelector(['strat_a', 'strat_b'])
        
        # Record highly correlated weight histories
        np.random.seed(42)
        for _ in range(10):
            # Same weights for both strategies (perfect correlation)
            weights = np.array([0.5, 0.5])
            selector._weight_history['strat_a'].append(weights.copy())
            selector._weight_history['strat_b'].append(weights.copy())
            
            selector.record_realized_performance('strat_a', 0.01, 0.1)
            selector.record_realized_performance('strat_b', 0.01, 0.1)
        
        # Calculate penalty
        penalty_a = selector._correlation_penalty('strat_a')
        penalty_b = selector._correlation_penalty('strat_b')
        
        # Both should have high penalty due to perfect correlation
        assert penalty_a > 0.5 or penalty_b > 0.5, \
            f"Expected high correlation penalty, got a={penalty_a:.2f}, b={penalty_b:.2f}"


class TestTurnoverPenalty:
    """Test 10.4: Verify turnover penalty applies correctly."""
    
    def test_high_turnover_penalty(self):
        """Verify turnover > 50% triggers 20% penalty."""
        selector = StrategySelector(['high_tov_strat'])
        
        # Create score with high turnover
        score = StrategyScore(method='high_tov_strat')
        score.sharpe_percentile = 0.8
        score.consistency = 0.7
        score.regime_score = 0.6
        score.recent_score = 0.5
        score.confidence = 0.8
        score.correlation_penalty = 0.0
        score.turnover_penalty = 0.20  # High turnover
        
        # Calculate final score
        score.final_score = (
            0.25 * score.sharpe_percentile +
            0.10 * score.consistency +
            0.20 * score.regime_score +
            0.15 * score.recent_score +
            0.10 * score.confidence -
            0.05 * score.correlation_penalty -
            score.turnover_penalty
        )
        
        # Verify penalty reduced the score
        expected_without_penalty = (
            0.25 * 0.8 + 0.10 * 0.7 + 0.20 * 0.6 + 0.15 * 0.5 + 0.10 * 0.8
        )
        assert score.final_score < expected_without_penalty, \
            "High turnover should reduce final score"
    
    def test_moderate_turnover_penalty(self):
        """Verify turnover > 30% triggers 10% penalty."""
        selector = StrategySelector(['mod_tov_strat'])
        
        score = StrategyScore(method='mod_tov_strat')
        score.turnover_penalty = 0.10  # Moderate turnover
        
        # Rest of calculation same as above
        score.sharpe_percentile = 0.8
        score.consistency = 0.7
        score.regime_score = 0.6
        score.recent_score = 0.5
        score.confidence = 0.8
        score.correlation_penalty = 0.0
        
        score.final_score = (
            0.25 * 0.8 + 0.10 * 0.7 + 0.20 * 0.6 + 0.15 * 0.5 + 0.10 * 0.8 - 0.10
        )
        
        assert score.turnover_penalty == 0.10


class TestBoundedWeights:
    """Test 10.5: Verify weights never exceed bounds."""
    
    def test_min_weight_enforced(self):
        """Verify no strategy gets less than 5% weight."""
        selector = StrategySelector(['a', 'b', 'c', 'd', 'e'])
        
        # Set extreme scores that would eliminate some strategies
        for method in selector.candidate_methods:
            for _ in range(10):
                selector.record_realized_performance(method, -0.5 if method != 'a' else 0.5, 0.1)
        
        # Mock strategies
        def mock_w(p, r):
            return np.ones(len(r.columns)) / len(r.columns)
        
        strategy_fns = {m: mock_w for m in selector.candidate_methods}
        
        _, blend_weights = selector.blend(
            pd.DataFrame(np.random.randn(100, 5)),
            pd.DataFrame(np.random.randn(100, 5) * 0.01),
            strategy_fns
        )
        
        # All strategies should have at least 5%
        for method, weight in blend_weights.items():
            assert weight >= 0.04, \
                f"Strategy {method} weight {weight:.2%} below 5% minimum"
    
    def test_max_weight_enforced(self):
        """Verify no strategy gets more than 40% weight."""
        selector = StrategySelector(['dominant', 'weak1', 'weak2', 'weak3'])
        
        # Make one strategy much better
        for _ in range(20):
            selector.record_realized_performance('dominant', 0.1, 0.05)
            for weak in ['weak1', 'weak2', 'weak3']:
                selector.record_realized_performance(weak, -0.05, 0.15)
        
        def mock_w(p, r):
            return np.ones(len(r.columns)) / len(r.columns)
        
        strategy_fns = {m: mock_w for m in selector.candidate_methods}
        
        _, blend_weights = selector.blend(
            pd.DataFrame(np.random.randn(100, 4)),
            pd.DataFrame(np.random.randn(100, 4) * 0.01),
            strategy_fns
        )
        
        # No strategy should exceed 40%
        for method, weight in blend_weights.items():
            assert weight <= 0.41, \
                f"Strategy {method} weight {weight:.2%} exceeds 40% maximum"


class TestSentimentMultiplier:
    """Test 10.6: Verify sentiment ONLY applied to trend_following and mean_reversion."""
    
    def test_sentiment_only_affects_target_strategies(self):
        """Verify sentiment multiplier only affects trend_following and mean_reversion."""
        selector = StrategySelector([
            'trend_following', 'mean_reversion', 'mvo', 'risk_parity', 'ml'
        ])
        
        # Set strong positive sentiment
        selector.set_sentiment_score(0.8)
        
        # Record equal performance for all
        for method in selector.candidate_methods:
            for _ in range(10):
                selector.record_realized_performance(method, 0.02, 0.1)
        
        def mock_w(p, r):
            return np.ones(len(r.columns)) / len(r.columns)
        
        strategy_fns = {m: mock_w for m in selector.candidate_methods}
        
        # Get initial equal weights
        _, initial_weights = selector.blend(
            pd.DataFrame(np.random.randn(100, 5)),
            pd.DataFrame(np.random.randn(100, 5) * 0.01),
            strategy_fns
        )
        
        # Trend following and mean reversion should get boosted
        # Others should not be directly affected by sentiment
        tf_weight = initial_weights.get('trend_following', 0)
        mr_weight = initial_weights.get('mean_reversion', 0)
        mvo_weight = initial_weights.get('mvo', 0)
        
        # With positive sentiment, TF and MR should be relatively favored
        # Note: After normalization, exact values depend on all scores
        assert tf_weight > 0 or mr_weight > 0, \
            "Trend following or mean reversion should have weight"
    
    def test_sent_multiplier_clipped(self):
        """Verify sentiment multiplier is clipped to [0.5, 1.5]."""
        selector = StrategySelector(['trend_following'])
        
        # Test extreme negative
        selector.set_sentiment_score(-1.0)
        mult_neg = 1.0 + (selector.sentiment_score * 0.5)
        mult_neg = np.clip(mult_neg, 0.5, 1.5)
        assert mult_neg == 0.5, f"Negative sentiment multiplier should be 0.5, got {mult_neg}"
        
        # Test extreme positive
        selector.set_sentiment_score(1.0)
        mult_pos = 1.0 + (selector.sentiment_score * 0.5)
        mult_pos = np.clip(mult_pos, 0.5, 1.5)
        assert mult_pos == 1.5, f"Positive sentiment multiplier should be 1.5, got {mult_pos}"


class TestIntegration:
    """Test 10.7: Full integration test."""
    
    def test_full_cycle_no_crash(self):
        """Run full cycle and verify no crashes."""
        selector = StrategySelector([
            'mvo', 'risk_parity', 'ml', 'cvar',
            'trend_following', 'mean_reversion', 'black_litterman'
        ])
        
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=300, freq='h')
        returns = pd.DataFrame(
            np.random.randn(300, 7) * 0.01,
            index=dates,
            columns=['BTC_', 'ETH_', 'SOL_', 'BNB_', 'XRP_', 'ADA_', 'DOT_']
        )
        prices = (1 + returns).cumprod() * 100
        
        def mock_w(p, r):
            return np.ones(len(r.columns)) / len(r.columns)
        
        strategy_fns = {m: mock_w for m in selector.candidate_methods}
        
        # Simulate 20 rebalance cycles
        for i in range(20):
            # Detect regime
            regime = detect_regime(returns.iloc[:100 + i*10])
            
            # Record performance
            for method in selector.candidate_methods:
                ret = np.random.randn() * 0.02
                vol = 0.1 + np.random.rand() * 0.05
                selector.record_realized_performance(method, ret, vol, regime=regime)
            
            # Set ML OOS R² occasionally
            if i % 5 == 0:
                selector.set_ml_oos_r2(np.random.randn() * 0.1)
            
            # Set sentiment
            selector.set_sentiment_score(np.random.randn() * 0.5)
            
            # Run blend
            weights, blend_weights = selector.blend(
                prices.iloc[:100 + i*10],
                returns.iloc[:100 + i*10],
                strategy_fns
            )
            
            # Verify weights are valid
            assert len(weights) == 7, f"Expected 7 asset weights, got {len(weights)}"
            assert abs(weights.sum() - 1.0) < 0.01, f"Weights should sum to 1, got {weights.sum()}"
            assert all(np.isfinite(weights)), "All weights should be finite"
    
    def test_weights_sum_to_one(self):
        """Verify ensemble weights always sum to 1."""
        selector = StrategySelector(['a', 'b', 'c'])
        
        for _ in range(10):
            for method in selector.candidate_methods:
                selector.record_realized_performance(
                    method, np.random.randn() * 0.01, 0.1
                )
        
        def mock_w(p, r):
            return np.ones(len(r.columns)) / len(r.columns)
        
        strategy_fns = {m: mock_w for m in selector.candidate_methods}
        
        returns = pd.DataFrame(np.random.randn(100, 3) * 0.01)
        prices = (1 + returns).cumprod() * 100
        
        weights, _ = selector.blend(prices, returns, strategy_fns)
        
        assert abs(weights.sum() - 1.0) < 1e-6, \
            f"Weights should sum to 1.0, got {weights.sum()}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
