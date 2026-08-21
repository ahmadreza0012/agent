"""
Phase 10: Transaction Cost Model Test Suite
--------------------------------------------

Comprehensive tests for the TransactionCostModel integration including:
- TransactionCostModel initialization and defaults
- Cost calculation (maker/taker, spread, impact)
- Liquidity constraints
- Market impact calculation
- Spread cost calculation
- Integration with backtester
- Integration with attribution
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging

from models.transaction_cost import (
    TransactionCostModel, 
    CostBreakdown,
    calculate_transaction_cost
)
from performance.attribution import AttributionEngine, StrategyAttribution


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestTransactionCostModelInitialization:
    """Test TransactionCostModel initialization and defaults."""
    
    def test_default_initialization(self):
        """Test default parameter values."""
        model = TransactionCostModel()
        
        assert model.maker_fee == 0.0004, "Default maker fee should be 0.04%"
        assert model.taker_fee == 0.0010, "Default taker fee should be 0.10%"
        assert model.spread == 0.0005, "Default spread should be 0.05%"
        assert model.alpha == 0.01, "Default alpha should be 0.01"
        assert model.min_liquidity_usd == 1_000_000, "Default min liquidity should be $1M"
        assert model.max_position_pct_of_adv == 0.10, "Default max position should be 10% of ADV"
        assert model.max_volume_participation == 0.20, "Default max participation should be 20%"
    
    def test_custom_initialization(self):
        """Test custom parameter values."""
        model = TransactionCostModel(
            maker_fee=0.0002,
            taker_fee=0.0005,
            spread=0.001,
            alpha=0.02,
            min_liquidity_usd=500_000,
            max_position_pct_of_adv=0.05,
            max_volume_participation=0.15
        )
        
        assert model.maker_fee == 0.0002
        assert model.taker_fee == 0.0005
        assert model.spread == 0.001
        assert model.alpha == 0.02
        assert model.min_liquidity_usd == 500_000
        assert model.max_position_pct_of_adv == 0.05
        assert model.max_volume_participation == 0.15


class TestCostCalculation:
    """Test cost calculation methods."""
    
    def test_maker_vs_taker_fees(self):
        """Test difference between maker and taker fees."""
        model = TransactionCostModel(maker_fee=0.0004, taker_fee=0.0010)
        order_value = 100_000
        
        maker_cost = model.calculate_cost_scalar(order_value, order_type='maker')
        taker_cost = model.calculate_cost_scalar(order_value, order_type='taker')
        
        # Taker should be more expensive
        assert taker_cost > maker_cost
        # Fee difference should be (0.0010 - 0.0004) * 100_000 = $60
        fee_diff = taker_cost - maker_cost
        assert abs(fee_diff - 60.0) < 1.0, f"Fee difference should be ~$60, got ${fee_diff}"
    
    def test_cost_breakdown(self):
        """Test that cost breakdown returns all components."""
        model = TransactionCostModel()
        order_value = 50_000
        
        breakdown = model.calculate_cost(order_value, volatility=0.02, avg_daily_volume=1e6)
        
        assert isinstance(breakdown, CostBreakdown)
        assert breakdown.fee_cost >= 0
        assert breakdown.spread_cost >= 0
        assert breakdown.impact_cost >= 0
        assert breakdown.total_cost == breakdown.fee_cost + breakdown.spread_cost + breakdown.impact_cost
    
    def test_cost_scales_with_order_size(self):
        """Test that costs scale linearly with order size (except impact)."""
        model = TransactionCostModel()
        
        small_order = 10_000
        large_order = 100_000
        
        small_cost = model.calculate_cost_scalar(small_order, volatility=0.01, avg_daily_volume=1e7)
        large_cost = model.calculate_cost_scalar(large_order, volatility=0.01, avg_daily_volume=1e7)
        
        # Large order should cost more
        assert large_cost > small_cost
        # Should scale roughly linearly (within 20% due to impact non-linearity)
        ratio = large_cost / small_cost
        assert 8 < ratio < 12, f"Cost ratio should be close to 10x, got {ratio:.2f}x"


class TestMarketImpact:
    """Test market impact calculations."""
    
    def test_market_impact_square_root_model(self):
        """Test square-root market impact model."""
        model = TransactionCostModel(alpha=0.01)
        
        # Small order relative to volume
        small_impact = model.calculate_market_impact(
            order_value=10_000,
            avg_daily_volume=10_000_000,
            volatility=0.02
        )
        
        # Large order relative to volume
        large_impact = model.calculate_market_impact(
            order_value=1_000_000,
            avg_daily_volume=10_000_000,
            volatility=0.02
        )
        
        # Large order should have disproportionately higher impact (square root law)
        assert large_impact > small_impact * 10  # 100x order should have >10x impact
        
    def test_market_impact_increases_with_volatility(self):
        """Test that market impact increases with volatility."""
        model = TransactionCostModel()
        
        low_vol_impact = model.calculate_market_impact(
            order_value=100_000,
            avg_daily_volume=1_000_000,
            volatility=0.01
        )
        
        high_vol_impact = model.calculate_market_impact(
            order_value=100_000,
            avg_daily_volume=1_000_000,
            volatility=0.05
        )
        
        assert high_vol_impact > low_vol_impact
        # Should scale linearly with volatility
        assert abs(high_vol_impact / low_vol_impact - 5.0) < 0.1
    
    def test_market_impact_participation_rate_clamped(self):
        """Test that participation rate is clamped to [0, 1]."""
        model = TransactionCostModel()
        
        # Order larger than ADV should not cause infinite impact
        huge_order_impact = model.calculate_market_impact(
            order_value=100_000_000,
            avg_daily_volume=1_000_000,
            volatility=0.02
        )
        
        # Impact should be finite and reasonable
        assert np.isfinite(huge_order_impact)
        assert huge_order_impact > 0


class TestSpreadCost:
    """Test spread-based execution costs."""
    
    def test_spread_cost_half_spread(self):
        """Test that spread cost uses half-spread for one-way execution."""
        model = TransactionCostModel(spread=0.001)  # 0.1% spread
        order_value = 100_000
        
        spread_cost = model.calculate_spread_cost(order_value)
        
        # Half spread: 0.1% / 2 = 0.05% = $50 on $100k
        expected_cost = order_value * 0.001 / 2
        assert abs(spread_cost - expected_cost) < 0.01
    
    def test_spread_cost_custom_spread(self):
        """Test spread cost with custom spread value."""
        model = TransactionCostModel()
        
        custom_spread = 0.002  # 0.2%
        order_value = 50_000
        
        spread_cost = model.calculate_spread_cost(order_value, spread=custom_spread)
        
        expected_cost = order_value * custom_spread / 2
        assert abs(spread_cost - expected_cost) < 0.01


class TestLiquidityConstraints:
    """Test liquidity constraint checking."""
    
    def test_liquidity_check_passes(self):
        """Test that reasonable orders pass liquidity check."""
        model = TransactionCostModel()
        
        can_execute, reason = model.check_liquidity(
            order_value=100_000,
            avg_daily_volume=10_000_000
        )
        
        assert can_execute, f"Order should pass: {reason}"
        assert reason == "Liquidity OK"
    
    def test_liquidity_too_low(self):
        """Test rejection when liquidity is too low."""
        model = TransactionCostModel(min_liquidity_usd=1_000_000)
        
        can_execute, reason = model.check_liquidity(
            order_value=10_000,
            avg_daily_volume=500_000  # Below $1M minimum
        )
        
        assert not can_execute
        assert "Liquidity too low" in reason
    
    def test_position_exceeds_adv_limit(self):
        """Test rejection when position exceeds ADV limit."""
        model = TransactionCostModel(max_position_pct_of_adv=0.10)
        
        can_execute, reason = model.check_liquidity(
            order_value=2_000_000,  # 20% of $10M ADV
            avg_daily_volume=10_000_000
        )
        
        assert not can_execute
        assert "Position exceeds" in reason
    
    def test_exceeds_volume_participation(self):
        """Test rejection when order exceeds volume participation limit."""
        model = TransactionCostModel(
            max_position_pct_of_adv=0.10,
            max_volume_participation=0.20
        )
        
        # Position limit allows it (10% of $10M = $1M)
        # But participation limit doesn't (20% of $10M = $2M)
        # Order of $3M should fail on participation
        can_execute, reason = model.check_liquidity(
            order_value=3_000_000,
            avg_daily_volume=10_000_000
        )
        
        assert not can_execute
        assert "volume participation" in reason
    
    def test_get_max_order_size(self):
        """Test maximum order size calculation."""
        model = TransactionCostModel(
            max_position_pct_of_adv=0.10,
            max_volume_participation=0.20
        )
        
        max_order = model.get_max_order_size(avg_daily_volume=10_000_000)
        
        # Should be limited by position (10% = $1M), not participation (20% = $2M)
        assert max_order == 1_000_000
    
    def test_zero_order_for_illiquid_asset(self):
        """Test that illiquid assets return zero max order size."""
        model = TransactionCostModel(min_liquidity_usd=1_000_000)
        
        max_order = model.get_max_order_size(avg_daily_volume=500_000)
        
        assert max_order == 0.0


class TestConvenienceFunction:
    """Test the convenience function for simple use cases."""
    
    def test_calculate_transaction_cost(self):
        """Test the standalone convenience function."""
        cost = calculate_transaction_cost(
            order_value=50_000,
            volatility=0.02,
            avg_daily_volume=1_000_000,
            order_type='taker'
        )
        
        assert isinstance(cost, float)
        assert cost > 0
        # Rough estimate: 0.1% fee + 0.025% spread + small impact ≈ 0.15% = $75
        assert 50 < cost < 150, f"Expected cost around $75, got ${cost}"


class TestAttributionIntegration:
    """Test integration with Performance Attribution system."""
    
    def test_strategy_attribution_with_costs(self):
        """Test that StrategyAttribution includes transaction costs."""
        attribution = StrategyAttribution(
            timestamp=datetime.now(),
            strategy_name="test_strategy",
            regime="low_vol_range",
            asset_weights={"BTC": 0.5, "ETH": 0.5},
            asset_returns={"BTC": 0.01, "ETH": 0.02},
            asset_contributions={},  # Will be calculated
            strategy_return=0.0,     # Will be calculated
            portfolio_weight=0.2,
            portfolio_contribution=0.0,
            transaction_cost=0.001,
            slippage=0.0005,
            net_contribution=0.0,
        )
        
        # Asset contributions should be calculated
        assert "BTC" in attribution.asset_contributions
        assert "ETH" in attribution.asset_contributions
        
        # Strategy return should be sum of contributions
        assert attribution.strategy_return > 0
        
        # Net contribution should subtract costs
        expected_net = attribution.portfolio_contribution - attribution.transaction_cost - attribution.slippage
        assert abs(attribution.net_contribution - expected_net) < 1e-10
    
    def test_attribution_engine_records_costs(self):
        """Test that AttributionEngine properly records and aggregates costs."""
        engine = AttributionEngine(risk_free_rate=0.0)
        
        # Record multiple rebalances
        for i in range(5):
            engine.record_rebalance(
                timestamp=datetime.now() + timedelta(days=i),
                strategy_weights={
                    "momentum": {"BTC": 0.6, "ETH": 0.4},
                    "mean_reversion": {"BTC": 0.4, "ETH": 0.6}
                },
                asset_returns={"BTC": 0.01, "ETH": 0.02},
                costs={"momentum": 0.001, "mean_reversion": 0.0015},
                slippage={"momentum": 0.0005, "mean_reversion": 0.0005},
                regime="low_vol_range",
                portfolio_strategy_weights={"momentum": 0.5, "mean_reversion": 0.5}
            )
        
        cumulative = engine.calculate_cumulative_attribution()
        
        assert "momentum" in cumulative
        assert "mean_reversion" in cumulative
        
        # Check that costs are tracked
        assert cumulative["momentum"].total_cost > 0
        assert cumulative["mean_reversion"].total_cost > 0
        
        # Net return should be less than gross return
        assert cumulative["momentum"].total_net_return < cumulative["momentum"].total_gross_return


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""
    
    def test_cost_model_scalar_method(self):
        """Test that calculate_cost_scalar returns float for backward compatibility."""
        model = TransactionCostModel()
        
        result = model.calculate_cost_scalar(
            order_value=10_000,
            volatility=0.01,
            avg_daily_volume=1e6
        )
        
        assert isinstance(result, float)
        assert result > 0
    
    def test_turnover_cost_returns_breakdown(self):
        """Test that turnover cost returns CostBreakdown."""
        model = TransactionCostModel()
        
        old_weights = np.array([0.5, 0.5])
        new_weights = np.array([0.6, 0.4])
        capital = 100_000
        
        breakdown = model.calculate_turnover_cost(
            old_weights=old_weights,
            new_weights=new_weights,
            capital=capital
        )
        
        assert isinstance(breakdown, CostBreakdown)
        assert breakdown.total_cost > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
