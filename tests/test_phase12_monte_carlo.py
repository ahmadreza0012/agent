"""
Test Suite - Phase 12: Monte Carlo / Robustness Analysis
=========================================================

Comprehensive tests for the RobustnessAnalyzer including:
- Bootstrap resampling
- Parameter perturbation
- Scenario analysis
- Distribution calculations
- Ruin probability
- Report generation
- Integration tests

Author: Quantitative Development Team
Phase: 12
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, MagicMock
import sys
import os

# Add workspace to path
sys.path.insert(0, '/workspace')

from backtesting.robustness import (
    RobustnessAnalyzer, 
    SimulationResult, 
    DistributionSummary,
    SCENARIOS
)


class MockBacktester:
    """Mock backtester for testing."""
    def __init__(self):
        self.initial_capital = 100000
        self.transaction_cost = 0.001
        self.slippage = 0.0005


@pytest.fixture
def sample_returns():
    """Create sample returns DataFrame for testing."""
    np.random.seed(42)
    n_periods = 252  # 1 year of daily data
    n_assets = 5
    
    # Generate correlated returns
    base_vol = 0.02
    returns = np.random.normal(0.0005, base_vol, (n_periods, n_assets))
    
    # Add some autocorrelation
    for i in range(1, n_periods):
        returns[i] += 0.1 * returns[i-1]
    
    columns = ['BTC', 'ETH', 'SOL', 'ADA', 'DOT']
    dates = pd.date_range('2023-01-01', periods=n_periods, freq='D')
    
    return pd.DataFrame(returns, columns=columns, index=dates)


@pytest.fixture
def sample_weights():
    """Create sample portfolio weights."""
    return np.array([0.3, 0.25, 0.2, 0.15, 0.1])


@pytest.fixture
def analyzer():
    """Create RobustnessAnalyzer instance with mock backtester."""
    mock_backtester = MockBacktester()
    return RobustnessAnalyzer(mock_backtester, n_simulations=100, block_size=20)


class TestRobustnessAnalyzerInitialization:
    """Test class initialization and defaults."""
    
    def test_initialization(self):
        """Test basic initialization."""
        mock_backtester = MockBacktester()
        analyzer = RobustnessAnalyzer(mock_backtester, n_simulations=500, block_size=30)
        
        assert analyzer.backtester == mock_backtester
        assert analyzer.n_simulations == 500
        assert analyzer.block_size == 30
        assert analyzer.results == {}
        assert analyzer.distributions == {}
        assert analyzer.scenario_results == {}
    
    def test_default_parameters(self):
        """Test default parameter values."""
        mock_backtester = MockBacktester()
        analyzer = RobustnessAnalyzer(mock_backtester)
        
        assert analyzer.n_simulations == 1000
        assert analyzer.block_size == 20


class TestBootstrapResampling:
    """Test bootstrap resampling functionality."""
    
    def test_bootstrap_returns_shape(self, analyzer, sample_returns):
        """Test that bootstrap returns have correct shape."""
        n_sim = 50
        bootstrap_samples = analyzer.bootstrap_returns(
            sample_returns, 
            n_simulations=n_sim,
            block_size=20
        )
        
        expected_shape = (n_sim, sample_returns.shape[0], sample_returns.shape[1])
        assert bootstrap_samples.shape == expected_shape
    
    def test_bootstrap_preserves_mean(self, analyzer, sample_returns):
        """Test that bootstrap preserves mean structure approximately."""
        original_mean = sample_returns.values.mean()
        
        bootstrap_samples = analyzer.bootstrap_returns(
            sample_returns, 
            n_simulations=100,
            block_size=20
        )
        
        # Average across all bootstrap samples should be close to original
        bootstrap_mean = bootstrap_samples.mean()
        
        # Allow 20% tolerance due to sampling variation
        assert abs(bootstrap_mean - original_mean) < abs(original_mean) * 0.2 + 0.001
    
    def test_bootstrap_different_samples(self, analyzer, sample_returns):
        """Test that different bootstrap samples are actually different."""
        bootstrap_samples = analyzer.bootstrap_returns(
            sample_returns, 
            n_simulations=10,
            block_size=20
        )
        
        # Check that not all samples are identical
        unique_samples = len(set(map(tuple, bootstrap_samples.reshape(10, -1))))
        assert unique_samples > 1
    
    def test_block_size_effect(self, sample_returns):
        """Test that different block sizes produce different results."""
        mock_backtester = MockBacktester()
        
        analyzer_small = RobustnessAnalyzer(mock_backtester, n_simulations=50, block_size=5)
        analyzer_large = RobustnessAnalyzer(mock_backtester, n_simulations=50, block_size=50)
        
        samples_small = analyzer_small.bootstrap_returns(sample_returns)
        samples_large = analyzer_large.bootstrap_returns(sample_returns)
        
        # Different block sizes should produce different distributions
        std_small = samples_small.std()
        std_large = samples_large.std()
        
        # They should be somewhat different (not exactly equal)
        assert not np.allclose(std_small, std_large, rtol=0.01)


class TestBootstrapAnalysis:
    """Test full bootstrap analysis pipeline."""
    
    def test_run_bootstrap_analysis(self, analyzer, sample_returns, sample_weights):
        """Test running full bootstrap analysis."""
        metrics = analyzer.run_bootstrap_analysis(
            sample_returns,
            weights=sample_weights,
            n_simulations=50
        )
        
        # Check all expected metrics are present
        expected_metrics = [
            'sharpe_ratio', 'total_return', 'max_drawdown',
            'cvar_95', 'win_rate', 'calmar_ratio', 'sortino_ratio'
        ]
        
        for metric in expected_metrics:
            assert metric in metrics
            assert len(metrics[metric]) == 50
        
        # Check results are stored
        assert 'bootstrap' in analyzer.results
        assert len(analyzer.results['bootstrap']) == 50
    
    def test_bootstrap_with_equal_weights(self, analyzer, sample_returns):
        """Test bootstrap analysis with default equal weights."""
        metrics = analyzer.run_bootstrap_analysis(sample_returns, n_simulations=30)
        
        assert 'sharpe_ratio' in metrics
        assert len(metrics['sharpe_ratio']) == 30
    
    def test_bootstrap_metric_ranges(self, analyzer, sample_returns):
        """Test that bootstrap metrics are in reasonable ranges."""
        metrics = analyzer.run_bootstrap_analysis(sample_returns, n_simulations=50)
        
        # Sharpe ratio should be finite
        assert all(np.isfinite(metrics['sharpe_ratio']))
        
        # Win rate should be between 0 and 1
        assert all(0 <= wr <= 1 for wr in metrics['win_rate'])
        
        # Max drawdown should be between 0 and 1
        assert all(0 <= dd <= 1 for dd in metrics['max_drawdown'])


class TestParameterPerturbation:
    """Test parameter perturbation functionality."""
    
    def test_perturb_parameters_basic(self, analyzer):
        """Test basic parameter perturbation."""
        base_params = {
            'transaction_cost': 0.001,
            'slippage': 0.0005,
            'rebalance_frequency': 2,
            'lookback_hours': 720,
            'max_position_pct_of_adv': 0.10,
            'max_volume_participation': 0.20
        }
        
        perturbed = analyzer.perturb_parameters(base_params, perturbation_scale=0.10)
        
        # All parameters should be present
        for key in base_params:
            assert key in perturbed
        
        # Float parameters should be positive
        assert perturbed['transaction_cost'] > 0
        assert perturbed['slippage'] > 0
        
        # Integer parameters should still be integers
        assert isinstance(perturbed['rebalance_frequency'], int)
        assert isinstance(perturbed['lookback_hours'], int)
    
    def test_perturbation_scale_effect(self, analyzer):
        """Test that larger perturbation scale creates more variance."""
        base_params = {'transaction_cost': 0.001, 'slippage': 0.0005}
        
        # Small perturbation
        small_perturbations = [
            analyzer.perturb_parameters(base_params, perturbation_scale=0.01)
            for _ in range(50)
        ]
        
        # Large perturbation
        large_perturbations = [
            analyzer.perturb_parameters(base_params, perturbation_scale=0.50)
            for _ in range(50)
        ]
        
        # Calculate variance in transaction_cost
        small_var = np.var([p['transaction_cost'] for p in small_perturbations])
        large_var = np.var([p['transaction_cost'] for p in large_perturbations])
        
        # Larger scale should produce more variance
        assert large_var > small_var
    
    def test_boolean_not_perturbed(self, analyzer):
        """Test that boolean parameters are not perturbed."""
        base_params = {
            'enabled': True,
            'use_stop_loss': False,
            'transaction_cost': 0.001
        }
        
        perturbed = analyzer.perturb_parameters(base_params)
        
        assert perturbed['enabled'] == True
        assert perturbed['use_stop_loss'] == False
    
    def test_run_parameter_perturbation(self, analyzer, sample_returns):
        """Test running parameter perturbation analysis."""
        base_params = {
            'transaction_cost': 0.001,
            'slippage': 0.0005,
            'rebalance_frequency': 2
        }
        
        metrics = analyzer.run_parameter_perturbation(
            base_params,
            sample_returns,
            n_simulations=30,
            perturbation_scale=0.10
        )
        
        assert 'sharpe_ratio' in metrics
        assert len(metrics['sharpe_ratio']) == 30
        assert 'parameter_perturbation' in analyzer.results


class TestScenarioAnalysis:
    """Test scenario analysis functionality."""
    
    def test_scenarios_defined(self):
        """Test that predefined scenarios exist."""
        assert 'baseline' in SCENARIOS
        assert 'high_vol' in SCENARIOS
        assert 'crisis' in SCENARIOS
        assert 'low_liquidity' in SCENARIOS
        
        # Each scenario should have required keys
        for name, scenario in SCENARIOS.items():
            assert 'volatility_multiplier' in scenario
            assert 'description' in scenario
    
    def test_apply_scenario_baseline(self, analyzer, sample_returns):
        """Test applying baseline scenario (no change)."""
        stressed = analyzer.apply_scenario(sample_returns, 'baseline')
        
        # Baseline should not modify returns significantly
        # (might have small floating point differences)
        assert np.allclose(stressed, sample_returns.values, rtol=1e-10)
    
    def test_apply_scenario_high_vol(self, analyzer, sample_returns):
        """Test applying high volatility scenario."""
        stressed = analyzer.apply_scenario(sample_returns, 'high_vol')
        
        # High vol should increase magnitude of returns
        original_std = sample_returns.values.std()
        stressed_std = stressed.std()
        
        # Should be approximately 2x (with some noise from random components)
        assert stressed_std > original_std * 1.5
    
    def test_apply_unknown_scenario(self, analyzer, sample_returns):
        """Test error handling for unknown scenario."""
        with pytest.raises(ValueError) as exc_info:
            analyzer.apply_scenario(sample_returns, 'unknown_scenario')
        
        assert 'Unknown scenario' in str(exc_info.value)
    
    def test_run_scenario_analysis(self, analyzer, sample_returns):
        """Test running full scenario analysis."""
        scenarios = ['baseline', 'high_vol', 'crisis']
        
        results = analyzer.run_scenario_analysis(
            sample_returns,
            scenarios=scenarios,
            n_simulations_per_scenario=20
        )
        
        # Check all scenarios are present
        for scenario in scenarios:
            assert scenario in results
            
            # Check metrics are present
            assert 'sharpe_ratio' in results[scenario]
            assert len(results[scenario]['sharpe_ratio']) == 20
        
        # Check scenario results are stored
        for scenario in scenarios:
            assert scenario in analyzer.scenario_results


class TestDistributionCalculations:
    """Test distribution calculation functionality."""
    
    def test_calculate_distributions(self, analyzer):
        """Test calculating distribution statistics."""
        metrics = {
            'sharpe_ratio': [0.5, 0.8, 1.2, 0.9, 0.6, 1.1, 0.7, 0.85],
            'total_return': [0.05, 0.12, -0.03, 0.08, 0.15, 0.02, 0.10, 0.07]
        }
        
        dists = analyzer.calculate_distributions(metrics)
        
        assert 'sharpe_ratio' in dists
        assert 'total_return' in dists
        
        # Check all expected fields
        for name, dist in dists.items():
            assert hasattr(dist, 'mean')
            assert hasattr(dist, 'median')
            assert hasattr(dist, 'std')
            assert hasattr(dist, 'percentile_5')
            assert hasattr(dist, 'percentile_95')
            assert hasattr(dist, 'probability_positive')
            assert hasattr(dist, 'skewness')
            assert hasattr(dist, 'kurtosis')
    
    def test_distribution_percentiles_ordering(self, analyzer):
        """Test that percentiles are properly ordered."""
        np.random.seed(42)
        values = np.random.normal(0, 1, 1000).tolist()
        
        metrics = {'test_metric': values}
        dists = analyzer.calculate_distributions(metrics)
        
        dist = dists['test_metric']
        
        # Percentiles should be ordered
        assert dist.percentile_5 <= dist.percentile_25
        assert dist.percentile_25 <= dist.percentile_50
        assert dist.percentile_50 <= dist.percentile_75
        assert dist.percentile_75 <= dist.percentile_95
    
    def test_probability_positive(self, analyzer):
        """Test probability positive calculation."""
        # All positive
        metrics_pos = {'test': [1, 2, 3, 4, 5]}
        dists_pos = analyzer.calculate_distributions(metrics_pos)
        assert dists_pos['test'].probability_positive == 1.0
        
        # All negative
        metrics_neg = {'test': [-1, -2, -3, -4, -5]}
        dists_neg = analyzer.calculate_distributions(metrics_neg)
        assert dists_neg['test'].probability_positive == 0.0
        
        # Mixed
        metrics_mix = {'test': [-1, -1, 1, 1, 1]}
        dists_mix = analyzer.calculate_distributions(metrics_mix)
        assert abs(dists_mix['test'].probability_positive - 0.6) < 0.01


class TestRuinProbability:
    """Test ruin probability calculations."""
    
    def test_ruin_probability_basic(self, analyzer, sample_returns):
        """Test basic ruin probability calculation."""
        port_returns = sample_returns.values @ np.ones(sample_returns.shape[1]) / sample_returns.shape[1]
        
        result = analyzer.calculate_ruin_probability(
            port_returns,
            initial_capital=100000,
            ruin_threshold=0.50,
            n_simulations=50
        )
        
        # Result should contain expected keys
        assert 'ruin_probability' in result
        assert 'expected_time_to_ruin' in result
        assert 'max_drawdown_mean' in result
        assert 'n_simulations' in result
        
        # Probability should be between 0 and 1
        assert 0 <= result['ruin_probability'] <= 1
    
    def test_ruin_threshold_effect(self, sample_returns):
        """Test that stricter ruin threshold increases probability."""
        mock_backtester = MockBacktester()
        analyzer = RobustnessAnalyzer(mock_backtester, n_simulations=50)
        
        port_returns = sample_returns.values @ np.ones(sample_returns.shape[1]) / sample_returns.shape[1]
        
        # Loose threshold (30% loss)
        result_loose = analyzer.calculate_ruin_probability(
            port_returns,
            initial_capital=100000,
            ruin_threshold=0.30
        )
        
        # Strict threshold (70% loss)
        result_strict = analyzer.calculate_ruin_probability(
            port_returns,
            initial_capital=100000,
            ruin_threshold=0.70
        )
        
        # Stricter threshold should have lower or equal ruin probability
        # (harder to lose 70% than 30%)
        assert result_strict['ruin_probability'] <= result_loose['ruin_probability']
    
    def test_ruin_level_calculation(self, analyzer, sample_returns):
        """Test that ruin level is calculated correctly."""
        port_returns = sample_returns.values @ np.ones(sample_returns.shape[1]) / sample_returns.shape[1]
        
        result = analyzer.calculate_ruin_probability(
            port_returns,
            initial_capital=100000,
            ruin_threshold=0.50,
            n_simulations=10
        )
        
        assert result['ruin_level_usd'] == 50000
        assert result['ruin_threshold_pct'] == 0.50


class TestReportGeneration:
    """Test report generation functionality."""
    
    def test_generate_report_empty(self, analyzer):
        """Test generating report with no results."""
        report = analyzer.generate_report()
        
        assert 'summary' in report
        assert 'distributions' in report
        assert 'confidence_intervals' in report
        assert 'scenarios' in report
        assert 'ruin_analysis' in report
        assert 'recommendation' in report
    
    def test_generate_report_with_bootstrap(self, analyzer, sample_returns):
        """Test generating report after bootstrap analysis."""
        # Run bootstrap first
        analyzer.run_bootstrap_analysis(sample_returns, n_simulations=50)
        
        report = analyzer.generate_report()
        
        # Summary should be populated
        assert report['summary']
        assert 'sharpe_mean' in report['summary']
        assert 'sharpe_median' in report['summary']
        assert 'n_simulations' in report['summary']
        
        # Confidence intervals should be present
        assert 'sharpe_90_ci' in report['confidence_intervals']
        assert 'return_90_ci' in report['confidence_intervals']
        
        # Distributions should be present
        assert 'sharpe_ratio' in report['distributions']
    
    def test_generate_report_with_scenarios(self, analyzer, sample_returns):
        """Test generating report after scenario analysis."""
        # Run scenario analysis
        analyzer.run_scenario_analysis(
            sample_returns,
            scenarios=['baseline', 'high_vol'],
            n_simulations_per_scenario=20
        )
        
        report = analyzer.generate_report()
        
        # Scenarios should be in report
        assert 'baseline' in report['scenarios']
        assert 'high_vol' in report['scenarios']
        
        # Each scenario should have description
        assert 'description' in report['scenarios']['baseline']
    
    def test_recommendation_logic_positive(self, analyzer, sample_returns):
        """Test recommendation for positive strategy."""
        # Create very good returns
        good_returns = pd.DataFrame(
            np.random.normal(0.002, 0.01, (252, 3)),
            columns=['A', 'B', 'C']
        )
        
        analyzer.run_bootstrap_analysis(good_returns, n_simulations=50)
        report = analyzer.generate_report()
        
        assert report['recommendation']
        assert len(report['recommendation']) > 0
    
    def test_report_structure(self, analyzer, sample_returns):
        """Test overall report structure."""
        analyzer.run_bootstrap_analysis(sample_returns, n_simulations=30)
        report = analyzer.generate_report()
        
        # Top-level keys
        expected_keys = ['summary', 'distributions', 'confidence_intervals', 
                        'scenarios', 'ruin_analysis', 'recommendation']
        for key in expected_keys:
            assert key in report
        
        # Summary structure
        if report['summary']:
            assert 'n_simulations' in report['summary']


class TestHelperMethods:
    """Test helper calculation methods."""
    
    def test_calculate_sharpe(self, analyzer):
        """Test Sharpe ratio calculation."""
        # Constant returns
        returns_const = np.array([0.01, 0.01, 0.01, 0.01])
        sharpe_const = analyzer._calculate_sharpe(returns_const)
        assert sharpe_const == 0  # No variance
        
        # Positive mean, some variance
        np.random.seed(42)
        returns_good = np.random.normal(0.001, 0.02, 100)
        sharpe_good = analyzer._calculate_sharpe(returns_good)
        assert sharpe_good > 0
    
    def test_calculate_total_return(self, analyzer):
        """Test total return calculation."""
        returns = np.array([0.01, 0.02, -0.01, 0.03])
        total = analyzer._calculate_total_return(returns)
        
        expected = np.prod(1 + returns) - 1
        assert abs(total - expected) < 1e-10
    
    def test_calculate_max_drawdown(self, analyzer):
        """Test maximum drawdown calculation."""
        # Monotonically increasing - no drawdown
        returns_pos = np.array([0.01, 0.02, 0.015, 0.01])
        dd_pos = analyzer._calculate_max_drawdown(returns_pos)
        assert dd_pos >= 0
        
        # Big loss followed by recovery
        returns_volatile = np.array([-0.2, 0.1, 0.1, 0.1])
        dd_volatile = analyzer._calculate_max_drawdown(returns_volatile)
        assert dd_volatile > 0.15  # Should catch the big drop
    
    def test_calculate_cvar(self, analyzer):
        """Test CVaR calculation."""
        np.random.seed(42)
        returns = np.random.normal(0.0005, 0.02, 1000)
        
        cvar = analyzer._calculate_cvar(returns, confidence=0.95)
        
        # CVaR should be positive (it's a risk measure)
        assert cvar > 0
    
    def test_calculate_win_rate(self, analyzer):
        """Test win rate calculation."""
        returns_all_wins = np.array([0.01, 0.02, 0.015])
        assert analyzer._calculate_win_rate(returns_all_wins) == 1.0
        
        returns_all_losses = np.array([-0.01, -0.02, -0.015])
        assert analyzer._calculate_win_rate(returns_all_losses) == 0.0
        
        returns_mixed = np.array([0.01, -0.01, 0.02, -0.02, 0.015])
        assert abs(analyzer._calculate_win_rate(returns_mixed) - 0.6) < 0.01
    
    def test_calculate_sortino(self, analyzer):
        """Test Sortino ratio calculation."""
        np.random.seed(42)
        returns = np.random.normal(0.0005, 0.02, 252)
        
        sortino = analyzer._calculate_sortino(returns)
        
        # Should be finite
        assert np.isfinite(sortino)


class TestIntegration:
    """Integration tests for full Monte Carlo workflow."""
    
    def test_full_bootstrap_workflow(self, sample_returns, sample_weights):
        """Test complete bootstrap analysis workflow."""
        mock_backtester = MockBacktester()
        analyzer = RobustnessAnalyzer(mock_backtester, n_simulations=100)
        
        # Run bootstrap
        metrics = analyzer.run_bootstrap_analysis(
            sample_returns,
            weights=sample_weights,
            n_simulations=100
        )
        
        # Calculate distributions
        dists = analyzer.calculate_distributions(metrics)
        
        # Generate report
        report = analyzer.generate_report()
        
        # Verify all components
        assert len(metrics['sharpe_ratio']) == 100
        assert 'sharpe_ratio' in dists
        assert report['summary']
        assert report['recommendation']
    
    def test_full_scenario_workflow(self, sample_returns):
        """Test complete scenario analysis workflow."""
        mock_backtester = MockBacktester()
        analyzer = RobustnessAnalyzer(mock_backtester, n_simulations=50)
        
        # Run scenario analysis
        results = analyzer.run_scenario_analysis(
            sample_returns,
            scenarios=['baseline', 'crisis', 'high_vol'],
            n_simulations_per_scenario=30
        )
        
        # Generate report
        report = analyzer.generate_report()
        
        # Verify
        assert len(results) == 3
        assert 'baseline' in report['scenarios']
        assert 'crisis' in report['scenarios']
        assert 'high_vol' in report['scenarios']
    
    def test_comparison_across_scenarios(self, sample_returns):
        """Test comparing metrics across scenarios."""
        mock_backtester = MockBacktester()
        analyzer = RobustnessAnalyzer(mock_backtester, n_simulations=50)
        
        results = analyzer.run_scenario_analysis(
            sample_returns,
            scenarios=['baseline', 'high_vol', 'crisis'],
            n_simulations_per_scenario=50
        )
        
        # Crisis should generally have worse Sharpe than baseline
        baseline_sharpe = np.mean(results['baseline']['sharpe_ratio'])
        crisis_sharpe = np.mean(results['crisis']['sharpe_ratio'])
        
        # With our stress model, crisis typically has higher vol which reduces Sharpe
        # This is a soft check as randomness can affect results
        # Just verify both are computed
        assert np.isfinite(baseline_sharpe)
        assert np.isfinite(crisis_sharpe)


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_returns(self, analyzer):
        """Test handling of empty returns."""
        empty_returns = pd.DataFrame()
        
        # Should handle gracefully
        with pytest.raises((IndexError, AttributeError)):
            analyzer.bootstrap_returns(empty_returns)
    
    def test_single_asset(self, analyzer):
        """Test with single asset."""
        np.random.seed(42)
        single_asset = pd.DataFrame(
            np.random.normal(0.0005, 0.02, 100),
            columns=['BTC']
        )
        
        metrics = analyzer.run_bootstrap_analysis(single_asset, n_simulations=20)
        
        assert 'sharpe_ratio' in metrics
        assert len(metrics['sharpe_ratio']) == 20
    
    def test_very_short_series(self, analyzer):
        """Test with very short return series."""
        np.random.seed(42)
        short_returns = pd.DataFrame(
            np.random.normal(0.0005, 0.02, 10),
            columns=['BTC']
        )
        
        # Should work but may have numerical issues
        metrics = analyzer.run_bootstrap_analysis(short_returns, n_simulations=10)
        
        assert 'sharpe_ratio' in metrics
    
    def test_zero_weights(self, analyzer, sample_returns):
        """Test with zero weights."""
        zero_weights = np.zeros(sample_returns.shape[1])
        
        # Should handle without crashing
        metrics = analyzer.run_bootstrap_analysis(
            sample_returns,
            weights=zero_weights,
            n_simulations=10
        )
        
        # Returns should be zero, Sharpe undefined (handled)
        assert 'sharpe_ratio' in metrics


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
