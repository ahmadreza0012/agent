"""
Phase 11: Liquidity / Market Impact Test Suite
-----------------------------------------------

Comprehensive tests for liquidity constraints, market impact modeling,
and position sizing based on liquidity.

Tests cover:
- Liquidity constraint enforcement in portfolio construction
- Volume participation limits
- Minimum liquidity filtering
- Position sizing based on liquidity
- Spread threshold checks
- Integration with backtester
- Edge cases (all illiquid, zero capital, etc.)
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch
import sys
import os

# Add workspace to path
sys.path.insert(0, '/workspace')

from models.transaction_cost import TransactionCostModel, CostBreakdown


class TestLiquidityConstraintEnforcement:
    """Test liquidity constraint enforcement in portfolio construction."""
    
    def test_enforce_liquidity_constraints_basic(self):
        """Test basic liquidity constraint enforcement."""
        cost_model = TransactionCostModel()
        
        # Raw weights that exceed liquidity limits
        raw_weights = np.array([0.5, 0.3, 0.2])  # 50%, 30%, 20%
        symbols = ['BTC', 'ETH', 'SOL']
        
        # Low ADV - should cap positions
        avg_daily_volumes = {
            'BTC': 500_000,  # $500k ADV
            'ETH': 300_000,  # $300k ADV
            'SOL': 200_000,  # $200k ADV
        }
        
        capital = 1_000_000  # $1M portfolio
        
        adjusted_weights = cost_model.calculate_liquidity_adjusted_weights(
            raw_weights=raw_weights,
            symbols=symbols,
            avg_daily_volumes=avg_daily_volumes,
            capital=capital
        )
        
        # Check weights sum to 1
        assert np.isclose(np.sum(adjusted_weights), 1.0, atol=0.01)
        
        # Check no weight exceeds its liquidity limit (10% of ADV / capital)
        for i, symbol in enumerate(symbols):
            max_weight = (avg_daily_volumes[symbol] * 0.10) / capital
            assert adjusted_weights[i] <= max_weight + 0.01  # Small tolerance
    
    def test_enforce_liquidity_with_illiquid_asset(self):
        """Test that illiquid assets are excluded."""
        cost_model = TransactionCostModel(min_liquidity_usd=1_000_000)
        
        raw_weights = np.array([0.4, 0.4, 0.2])
        symbols = ['BTC', 'ETH', 'LOW_LIQ']
        
        avg_daily_volumes = {
            'BTC': 5_000_000,  # Liquid
            'ETH': 3_000_000,  # Liquid
            'LOW_LIQ': 500_000,  # Illiquid (< $1M)
        }
        
        capital = 1_000_000
        
        adjusted_weights = cost_model.calculate_liquidity_adjusted_weights(
            raw_weights=raw_weights,
            symbols=symbols,
            avg_daily_volumes=avg_daily_volumes,
            capital=capital
        )
        
        # Illiquid asset should have zero weight
        low_liq_idx = symbols.index('LOW_LIQ')
        assert adjusted_weights[low_liq_idx] == 0.0
        
        # Remaining weights should sum to 1
        remaining_sum = np.sum(adjusted_weights) - adjusted_weights[low_liq_idx]
        assert np.isclose(remaining_sum, 1.0, atol=0.01)
    
    def test_all_assets_illiquid(self):
        """Test behavior when all assets are illiquid."""
        cost_model = TransactionCostModel(min_liquidity_usd=1_000_000)
        
        raw_weights = np.array([0.33, 0.33, 0.34])
        symbols = ['A', 'B', 'C']
        
        avg_daily_volumes = {
            'A': 500_000,
            'B': 400_000,
            'C': 300_000,
        }
        
        capital = 1_000_000
        
        adjusted_weights = cost_model.calculate_liquidity_adjusted_weights(
            raw_weights=raw_weights,
            symbols=symbols,
            avg_daily_volumes=avg_daily_volumes,
            capital=capital
        )
        
        # All weights should be zero (no liquid assets)
        assert np.all(adjusted_weights == 0.0)


class TestVolumeParticipationLimits:
    """Test volume participation limits."""
    
    def test_participation_limit_calculation(self):
        """Test volume participation limit calculation."""
        cost_model = TransactionCostModel(max_volume_participation=0.20)
        
        adv = 1_000_000
        max_order = cost_model.get_max_order_size(adv)
        
        # Max order should be 20% of ADV (more restrictive than 10% position limit)
        expected = adv * 0.10  # Position limit is more restrictive
        assert max_order == expected
    
    def test_position_vs_participation_limit(self):
        """Test that more restrictive limit is applied."""
        # Test with 10% position, 20% participation
        cost_model1 = TransactionCostModel(
            max_position_pct_of_adv=0.10,
            max_volume_participation=0.20
        )
        
        adv = 1_000_000
        max_order1 = cost_model1.get_max_order_size(adv)
        assert max_order1 == adv * 0.10  # Position limit wins
        
        # Test with 20% position, 5% participation
        cost_model2 = TransactionCostModel(
            max_position_pct_of_adv=0.20,
            max_volume_participation=0.05
        )
        
        max_order2 = cost_model2.get_max_order_size(adv)
        assert max_order2 == adv * 0.05  # Participation limit wins


class TestMinimumLiquidityFiltering:
    """Test minimum liquidity filtering."""
    
    def test_filter_by_liquidity(self):
        """Test filtering assets by liquidity."""
        from portfolio_optimizer import PortfolioOptimizer
        
        optimizer = PortfolioOptimizer(n_assets=4, asset_names=['BTC', 'ETH', 'SOL', 'LOW'])
        
        avg_daily_volumes = {
            'BTC': 5_000_000,
            'ETH': 3_000_000,
            'SOL': 1_500_000,
            'LOW': 500_000,  # Below $1M threshold
        }
        
        symbols = ['BTC', 'ETH', 'SOL', 'LOW']
        liquid_symbols = optimizer.filter_by_liquidity(
            symbols=symbols,
            avg_daily_volumes=avg_daily_volumes,
            min_liquidity_usd=1_000_000
        )
        
        assert 'LOW' not in liquid_symbols
        assert len(liquid_symbols) == 3
        assert set(liquid_symbols) == {'BTC', 'ETH', 'SOL'}
    
    def test_check_liquidity_below_threshold(self):
        """Test liquidity check fails below threshold."""
        cost_model = TransactionCostModel(min_liquidity_usd=1_000_000)
        
        can_execute, reason = cost_model.check_liquidity(
            order_value=10_000,
            avg_daily_volume=500_000  # Below threshold
        )
        
        assert can_execute is False
        assert "Liquidity too low" in reason


class TestPositionSizingBasedOnLiquidity:
    """Test position sizing based on liquidity."""
    
    def test_calculate_max_position_from_liquidity(self):
        """Test max position calculation from liquidity."""
        from portfolio_optimizer import PortfolioOptimizer
        
        optimizer = PortfolioOptimizer(n_assets=1, asset_names=['BTC'])
        
        # High liquidity asset
        max_weight = optimizer.calculate_max_position_from_liquidity(
            symbol='BTC',
            avg_daily_volume=10_000_000,
            capital=1_000_000
        )
        
        # Should be 10% of ADV / capital = $1M / $1M = 1.0 (capped at 100%)
        assert max_weight == 1.0
        
        # Low liquidity asset
        max_weight_low = optimizer.calculate_max_position_from_liquidity(
            symbol='LOW',
            avg_daily_volume=500_000,
            capital=1_000_000
        )
        
        # Below minimum liquidity -> 0
        assert max_weight_low == 0.0
    
    def test_realistic_position_sizing(self):
        """Test realistic position sizing scenario."""
        cost_model = TransactionCostModel()
        
        # Realistic scenario: $100k portfolio, $2M ADV asset
        raw_weights = np.array([0.5])
        symbols = ['BTC']
        avg_daily_volumes = {'BTC': 2_000_000}
        capital = 100_000
        
        adjusted = cost_model.calculate_liquidity_adjusted_weights(
            raw_weights=raw_weights,
            symbols=symbols,
            avg_daily_volumes=avg_daily_volumes,
            capital=capital
        )
        
        # Max position = $2M * 10% = $200k, but portfolio is only $100k
        # So weight should be capped at 1.0 (100%)
        assert adjusted[0] == 1.0


class TestSpreadThreshold:
    """Test spread threshold checks."""
    
    def test_spread_threshold_acceptable(self):
        """Test acceptable spread passes threshold."""
        cost_model = TransactionCostModel()
        
        # 10 bps spread (0.001) - well below 50 bps threshold
        can_trade, reason = cost_model.check_spread_threshold(
            spread=0.001,
            max_spread_bps=50
        )
        
        assert can_trade is True
        assert "acceptable" in reason.lower()
    
    def test_spread_threshold_exceeded(self):
        """Test excessive spread fails threshold."""
        cost_model = TransactionCostModel()
        
        # 100 bps spread (0.01) - exceeds 50 bps threshold
        can_trade, reason = cost_model.check_spread_threshold(
            spread=0.01,
            max_spread_bps=50
        )
        
        assert can_trade is False
        assert "too high" in reason.lower()
    
    def test_spread_threshold_boundary(self):
        """Test spread at exact threshold."""
        cost_model = TransactionCostModel()
        
        # Exactly 50 bps
        can_trade, reason = cost_model.check_spread_threshold(
            spread=0.005,  # 50 bps
            max_spread_bps=50
        )
        
        # At boundary should pass
        assert can_trade is True


class TestBacktesterIntegration:
    """Test integration with backtester."""
    
    def test_backtester_has_liquidity_params(self):
        """Test backtester accepts liquidity parameters."""
        from backtester import Backtester
        
        bt = Backtester(
            initial_capital=100_000,
            min_liquidity_usd=500_000,
            max_position_pct_of_adv=0.05,
            max_volume_participation=0.15
        )
        
        assert bt.min_liquidity_usd == 500_000
        assert bt.max_position_pct_of_adv == 0.05
        assert bt.max_volume_participation == 0.15
    
    def test_backtester_cost_model_initialized(self):
        """Test backtester initializes cost model with liquidity params."""
        from backtester import Backtester
        
        bt = Backtester(
            initial_capital=100_000,
            min_liquidity_usd=2_000_000,
            max_position_pct_of_adv=0.08
        )
        
        assert bt.cost_model.min_liquidity_usd == 2_000_000
        assert bt.cost_model.max_position_pct_of_adv == 0.08


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_zero_capital(self):
        """Test behavior with zero capital."""
        cost_model = TransactionCostModel()
        
        raw_weights = np.array([0.5, 0.5])
        symbols = ['BTC', 'ETH']
        avg_daily_volumes = {'BTC': 1_000_000, 'ETH': 1_000_000}
        capital = 0
        
        # Should handle gracefully (avoid division by zero)
        adjusted = cost_model.calculate_liquidity_adjusted_weights(
            raw_weights=raw_weights,
            symbols=symbols,
            avg_daily_volumes=avg_daily_volumes,
            capital=capital
        )
        
        # Should return valid weights (implementation-dependent)
        assert len(adjusted) == 2
        assert np.all(adjusted >= 0)
    
    def test_empty_symbols(self):
        """Test behavior with empty symbol list."""
        cost_model = TransactionCostModel()
        
        raw_weights = np.array([])
        symbols = []
        avg_daily_volumes = {}
        capital = 100_000
        
        adjusted = cost_model.calculate_liquidity_adjusted_weights(
            raw_weights=raw_weights,
            symbols=symbols,
            avg_daily_volumes=avg_daily_volumes,
            capital=capital
        )
        
        assert len(adjusted) == 0
    
    def test_missing_volume_data(self):
        """Test behavior with missing volume data."""
        cost_model = TransactionCostModel()
        
        raw_weights = np.array([0.5, 0.5])
        symbols = ['BTC', 'ETH']
        avg_daily_volumes = {'BTC': 1_000_000}  # ETH missing
        capital = 100_000
        
        adjusted = cost_model.calculate_liquidity_adjusted_weights(
            raw_weights=raw_weights,
            symbols=symbols,
            avg_daily_volumes=avg_daily_volumes,
            capital=capital
        )
        
        # ETH should be treated as illiquid (weight = 0)
        eth_idx = symbols.index('ETH')
        assert adjusted[eth_idx] == 0.0
    
    def test_extreme_volatility(self):
        """Test cost calculation with extreme volatility."""
        cost_model = TransactionCostModel()
        
        # 100% daily volatility
        cost = cost_model.calculate_cost_scalar(
            order_value=100_000,
            volatility=1.0,
            avg_daily_volume=1_000_000
        )
        
        # Should be finite and positive
        assert np.isfinite(cost)
        assert cost > 0


class TestMarketImpactCalculation:
    """Test market impact calculation specifics."""
    
    def test_square_root_impact(self):
        """Test square-root market impact model."""
        cost_model = TransactionCostModel(alpha=0.01)
        
        # Small order relative to ADV
        impact_small = cost_model.calculate_market_impact(
            order_value=10_000,
            avg_daily_volume=1_000_000,
            volatility=0.02
        )
        
        # Large order relative to ADV
        impact_large = cost_model.calculate_market_impact(
            order_value=100_000,
            avg_daily_volume=1_000_000,
            volatility=0.02
        )
        
        # Impact should scale with sqrt(participation_rate)
        # sqrt(0.1) / sqrt(0.01) = sqrt(10) ≈ 3.16
        ratio = impact_large / impact_small
        assert 2.5 < ratio < 4.0  # Allow some tolerance
    
    def test_impact_zero_for_tiny_orders(self):
        """Test negligible impact for tiny orders."""
        cost_model = TransactionCostModel()
        
        impact = cost_model.calculate_market_impact(
            order_value=100,  # Very small
            avg_daily_volume=10_000_000,
            volatility=0.01
        )
        
        # Should be very small but positive
        assert impact >= 0
        assert impact < 1.0  # Less than $1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
