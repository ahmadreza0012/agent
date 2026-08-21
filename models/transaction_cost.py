"""
Transaction Cost Model
---------------------
Realistic transaction costs with maker/taker fees, spread, and market impact.

This model provides comprehensive transaction cost estimation including:
- Maker/taker fees based on exchange fee schedules
- Bid-ask spread costs
- Market impact using square-root model
- Liquidity constraints checking

Fee Structure (defaults based on major crypto exchanges):
- Maker fee: 0.04% (limit orders provide liquidity)
- Taker fee: 0.10% (market orders take liquidity)
- Spread: 0.05% (typical bid-ask spread for liquid pairs)
- Market impact coefficient (alpha): 0.01

Market Impact Model:
The model uses the square-root law of market impact:
    impact = alpha * sqrt(participation_rate) * volatility * order_value

where participation_rate = order_value / avg_daily_volume

Liquidity Constraints:
- Maximum position: 10% of Average Daily Volume (ADV)
- Maximum volume participation: 20% of daily volume
- Minimum liquidity threshold: $1M daily volume
"""

import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CostBreakdown:
    """Detailed breakdown of transaction costs."""
    fee_cost: float
    spread_cost: float
    impact_cost: float
    total_cost: float
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for logging/reporting."""
        return {
            'fee_cost': self.fee_cost,
            'spread_cost': self.spread_cost,
            'impact_cost': self.impact_cost,
            'total_cost': self.total_cost
        }


class TransactionCostModel:
    """
    Realistic transaction cost model for crypto trading.
    
    Costs:
    - Maker fee: limit orders (0.04%)
    - Taker fee: market orders (0.10%)
    - Spread: bid-ask spread (0.05%)
    - Market impact: price impact of large orders (square-root model)
    
    The model is designed to be conservative and realistic, avoiding
    look-ahead bias by using only information available at trade time.
    """
    
    # Liquidity constraint defaults
    DEFAULT_MIN_LIQUIDITY_USD = 1_000_000  # $1M minimum daily volume
    DEFAULT_MAX_POSITION_PCT_OF_ADV = 0.10  # 10% of ADV
    DEFAULT_MAX_VOLUME_PARTICIPATION = 0.20  # 20% of daily volume
    
    def __init__(self, 
                 maker_fee: float = 0.0004, 
                 taker_fee: float = 0.0010,
                 spread: float = 0.0005, 
                 alpha: float = 0.01,
                 min_liquidity_usd: float = None,
                 max_position_pct_of_adv: float = None,
                 max_volume_participation: float = None):
        """
        Initialize the Transaction Cost Model.
        
        Args:
            maker_fee: Fee for limit orders (default 0.04% = 0.0004)
            taker_fee: Fee for market orders (default 0.10% = 0.0010)
            spread: Bid-ask spread (default 0.05% = 0.0005)
            alpha: Market impact coefficient (default 0.01)
            min_liquidity_usd: Minimum acceptable daily volume (default $1M)
            max_position_pct_of_adv: Max position as % of ADV (default 10%)
            max_volume_participation: Max order as % of daily volume (default 20%)
        """
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.spread = spread
        self.alpha = alpha
        
        # Liquidity constraints
        self.min_liquidity_usd = min_liquidity_usd or self.DEFAULT_MIN_LIQUIDITY_USD
        self.max_position_pct_of_adv = max_position_pct_of_adv or self.DEFAULT_MAX_POSITION_PCT_OF_ADV
        self.max_volume_participation = max_volume_participation or self.DEFAULT_MAX_VOLUME_PARTICIPATION
        
        logger.info(f"TransactionCostModel initialized: maker={maker_fee:.4f}, "
                   f"taker={taker_fee:.4f}, spread={spread:.4f}, alpha={alpha:.4f}")
    
    def calculate_cost(self, order_value: float, volatility: float = 0.01,
                       avg_daily_volume: float = 1e6, order_type: str = 'taker') -> CostBreakdown:
        """
        Calculate total transaction cost with detailed breakdown.
        
        Cost = fee + spread + market_impact
        
        Args:
            order_value: Notional value of the order in USD
            volatility: Daily volatility (default 1%)
            avg_daily_volume: Average daily volume in USD
            order_type: 'maker' or 'taker'
            
        Returns:
            CostBreakdown object with detailed cost components
            
        Note:
            All inputs must be known at trade time to avoid look-ahead bias.
            Volatility should be calculated from historical data up to trade time.
            Volume should be trailing average, not future volume.
        """
        fee = self.maker_fee if order_type == 'maker' else self.taker_fee
        
        # Fee cost
        fee_cost = order_value * fee
        
        # Spread cost (half spread for mid-price execution)
        spread_cost = self.calculate_spread_cost(order_value, self.spread)
        
        # Market impact (square root model)
        impact_cost = self.calculate_market_impact(order_value, avg_daily_volume, volatility)
        
        total = fee_cost + spread_cost + impact_cost
        
        logger.debug(f"Cost breakdown: fee=${fee_cost:.2f}, spread=${spread_cost:.2f}, "
                    f"impact=${impact_cost:.2f}, total=${total:.2f}")
        
        return CostBreakdown(
            fee_cost=fee_cost,
            spread_cost=spread_cost,
            impact_cost=impact_cost,
            total_cost=total
        )
    
    def calculate_cost_scalar(self, order_value: float, volatility: float = 0.01,
                              avg_daily_volume: float = 1e6, order_type: str = 'taker') -> float:
        """
        Calculate total transaction cost as a scalar value.
        
        This is a convenience method for backward compatibility.
        
        Args:
            order_value: Notional value of the order in USD
            volatility: Daily volatility (default 1%)
            avg_daily_volume: Average daily volume in USD
            order_type: 'maker' or 'taker'
            
        Returns:
            Total cost in USD
        """
        breakdown = self.calculate_cost(order_value, volatility, avg_daily_volume, order_type)
        return breakdown.total_cost
    
    def calculate_market_impact(self, order_value: float, avg_daily_volume: float, 
                                volatility: float) -> float:
        """
        Calculate market impact using the square-root model.
        
        The square-root law of market impact states that price impact scales
        with the square root of the participation rate (order size relative to
        market volume).
        
        Formula:
            impact = alpha * sqrt(participation_rate) * volatility * order_value
        
        where:
            participation_rate = order_value / avg_daily_volume
            
        Args:
            order_value: Order size in USD
            avg_daily_volume: Average daily volume in USD (ADV)
            volatility: Daily volatility (as decimal, e.g., 0.01 for 1%)
            
        Returns:
            Market impact cost in USD
            
        Reference:
            Almgren, R., & Chriss, N. (2000). Optimal execution of portfolio 
            transactions. Journal of Risk, 3, 5-39.
        """
        # Clamp participation rate to [0, 1] to avoid unrealistic scenarios
        participation_rate = min(order_value / max(avg_daily_volume, 1e-6), 1.0)
        participation_rate = max(participation_rate, 0.0)
        
        # Square-root impact model
        impact = self.alpha * np.sqrt(participation_rate) * volatility * order_value
        
        logger.debug(f"Market impact: participation={participation_rate:.4f}, "
                    f"volatility={volatility:.4f}, impact=${impact:.2f}")
        
        return impact
    
    def calculate_spread_cost(self, order_value: float, spread: float = None) -> float:
        """
        Calculate cost from bid-ask spread.
        
        Assumes execution at mid-price + half spread for buys,
        and mid-price - half spread for sells. For round-trip costs,
        use the full spread.
        
        Args:
            order_value: Order size in USD
            spread: Bid-ask spread as decimal (default: self.spread)
                   If None, uses instance default
            
        Returns:
            Spread cost in USD (half-spread for one-way execution)
        """
        if spread is None:
            spread = self.spread
        
        # Half spread for one-way execution
        spread_cost = order_value * (spread / 2)
        
        return spread_cost
    
    def check_liquidity(self, order_value: float, avg_daily_volume: float) -> Tuple[bool, str]:
        """
        Check if an order can be executed given liquidity constraints.
        
        Constraints checked:
        1. Minimum liquidity threshold: ADV must exceed min_liquidity_usd
        2. Position limit: Order must not exceed max_position_pct_of_adv * ADV
        3. Participation limit: Order must not exceed max_volume_participation * ADV
        
        Args:
            order_value: Order size in USD
            avg_daily_volume: Average daily volume in USD (ADV)
            
        Returns:
            Tuple of (can_execute: bool, reason: str)
            If can_execute is False, reason explains which constraint was violated
        """
        # Check minimum liquidity
        if avg_daily_volume < self.min_liquidity_usd:
            return False, f"Liquidity too low: ${avg_daily_volume:,.0f} < ${self.min_liquidity_usd:,.0f} minimum"
        
        # Check position limit (10% of ADV)
        max_position = avg_daily_volume * self.max_position_pct_of_adv
        if order_value > max_position:
            return False, f"Position exceeds {self.max_position_pct_of_adv:.0%} of ADV: " \
                         f"${order_value:,.0f} > ${max_position:,.0f}"
        
        # Check volume participation limit (20% of daily volume)
        max_participation = avg_daily_volume * self.max_volume_participation
        if order_value > max_participation:
            return False, f"Order exceeds {self.max_volume_participation:.0%} volume participation: " \
                         f"${order_value:,.0f} > ${max_participation:,.0f}"
        
        return True, "Liquidity OK"
    
    def get_max_order_size(self, avg_daily_volume: float) -> float:
        """
        Calculate maximum allowable order size given liquidity constraints.
        
        Args:
            avg_daily_volume: Average daily volume in USD (ADV)
            
        Returns:
            Maximum order size in USD that satisfies all constraints
        """
        # Position limit
        max_by_position = avg_daily_volume * self.max_position_pct_of_adv
        
        # Participation limit
        max_by_participation = avg_daily_volume * self.max_volume_participation
        
        # Take the more restrictive limit
        max_order = min(max_by_position, max_by_participation)
        
        # Also respect minimum liquidity requirement
        if avg_daily_volume < self.min_liquidity_usd:
            return 0.0  # Cannot trade this asset
        
        return max_order
    
    def check_spread_threshold(self, spread: float, 
                               max_spread_bps: float = 50) -> Tuple[bool, str]:
        """
        Check if spread is acceptable for trading.
        
        High spreads indicate illiquid markets and can significantly impact
        execution costs. This check prevents trading in excessively wide
        spread conditions.
        
        Args:
            spread: Current spread as decimal (e.g., 0.001 for 10 bps)
            max_spread_bps: Maximum acceptable spread in basis points (default 50 bps = 0.005)
        
        Returns:
            Tuple of (can_trade: bool, reason: str)
            If can_trade is False, reason explains why spread is unacceptable
        """
        spread_bps = spread * 10000  # Convert to basis points
        
        if spread_bps > max_spread_bps:
            return False, f"Spread too high: {spread_bps:.1f} bps > {max_spread_bps} bps threshold"
        
        return True, f"Spread acceptable: {spread_bps:.1f} bps"
    
    def calculate_liquidity_adjusted_weights(self, raw_weights: np.ndarray,
                                              symbols: list[str],
                                              avg_daily_volumes: Dict[str, float],
                                              capital: float) -> np.ndarray:
        """
        Adjust portfolio weights based on liquidity constraints.
        
        This method enforces that no position exceeds liquidity limits and
        redistributes excess weight proportionally to other assets.
        
        Algorithm:
        1. Calculate max position value for each asset based on ADV
        2. Cap weights that exceed max position
        3. Redistribute excess proportionally to uncapped assets
        4. Iterate until convergence or max iterations
        5. Ensure sum(weights) = 1
        
        Args:
            raw_weights: Original portfolio weights (should sum to 1)
            symbols: Asset symbols corresponding to weights
            avg_daily_volumes: Dictionary mapping symbol to ADV in USD
            capital: Total portfolio value in USD
            
        Returns:
            Adjusted weights that satisfy all liquidity constraints
            
        Note:
            - Assets with ADV below min_liquidity_usd are excluded (weight = 0)
            - If all assets are illiquid, returns equal-weight cash position
        """
        weights = raw_weights.copy().astype(float)
        n_assets = len(weights)
        
        if n_assets == 0:
            return weights
        
        # Calculate max position for each asset
        max_positions = np.zeros(n_assets)
        liquid_mask = np.zeros(n_assets, dtype=bool)
        
        for i, symbol in enumerate(symbols):
            adv = avg_daily_volumes.get(symbol, 0.0)
            
            # Check minimum liquidity
            if adv >= self.min_liquidity_usd:
                liquid_mask[i] = True
                # Max position is the more restrictive of position/participation limits
                max_by_position = adv * self.max_position_pct_of_adv
                max_by_participation = adv * self.max_volume_participation
                max_positions[i] = min(max_by_position, max_by_participation) / capital
            else:
                # Illiquid asset - force weight to zero
                weights[i] = 0.0
                logger.warning(f"Asset {symbol} excluded: ADV ${adv:,.0f} < ${self.min_liquidity_usd:,.0f} minimum")
        
        # Check if any liquid assets remain
        if not liquid_mask.any():
            logger.warning("No liquid assets available - returning zero weights")
            return np.zeros(n_assets)
        
        # Iteratively cap and redistribute
        max_iterations = 10
        for iteration in range(max_iterations):
            # Find assets exceeding limits
            excess_mask = (weights > max_positions) & liquid_mask
            
            if not excess_mask.any():
                break  # All constraints satisfied
            
            # Calculate excess weight
            excess = np.sum(weights[excess_mask] - max_positions[excess_mask])
            
            # Cap exceeded positions
            weights[excess_mask] = max_positions[excess_mask]
            
            # Redistribute excess to uncapped liquid assets
            uncapped_mask = ~excess_mask & liquid_mask
            uncapped_total = np.sum(weights[uncapped_mask])
            
            if uncapped_total > 0:
                # Proportional redistribution
                for i in range(n_assets):
                    if uncapped_mask[i]:
                        weights[i] += excess * (weights[i] / uncapped_total)
            else:
                # No uncapped assets - distribute equally among liquid assets
                liquid_count = liquid_mask.sum()
                if liquid_count > 0:
                    remaining_weight = 1.0 - np.sum(weights[liquid_mask])
                    weights[liquid_mask] += remaining_weight / liquid_count
        
        # Final normalization to ensure sum = 1 (for liquid assets only)
        liquid_total = np.sum(weights[liquid_mask])
        if liquid_total > 0:
            weights[liquid_mask] /= liquid_total
        
        # Ensure no negative weights
        weights = np.maximum(weights, 0.0)
        
        # Final normalization
        total = np.sum(weights)
        if total > 0:
            weights /= total
        
        logger.info(f"Liquidity adjustment: {liquid_mask.sum()}/{n_assets} assets liquid, "
                   f"final weights sum: {np.sum(weights):.4f}")
        
        return weights
    
    def calculate_turnover_cost(self, old_weights: np.ndarray, new_weights: np.ndarray,
                                capital: float, volatility: float = 0.01,
                                avg_daily_volume: float = 1e6) -> CostBreakdown:
        """
        Calculate cost of rebalancing from old to new weights.
        
        Args:
            old_weights: Previous portfolio weights
            new_weights: New target portfolio weights
            capital: Total portfolio value in USD
            volatility: Daily volatility (default 1%)
            avg_daily_volume: Average daily volume in USD
            
        Returns:
            CostBreakdown object with detailed cost components
        """
        turnover = np.abs(new_weights - old_weights).sum() / 2
        order_value = capital * turnover
        return self.calculate_cost(order_value, volatility, avg_daily_volume)


# Convenience function for backward compatibility
def calculate_transaction_cost(order_value: float, volatility: float = 0.01,
                               avg_daily_volume: float = 1e6, 
                               order_type: str = 'taker') -> float:
    """
    Calculate transaction cost using default model parameters.
    
    This is a convenience function for simple use cases.
    
    Args:
        order_value: Order size in USD
        volatility: Daily volatility (default 1%)
        avg_daily_volume: Average daily volume in USD
        order_type: 'maker' or 'taker'
        
    Returns:
        Total cost in USD
    """
    model = TransactionCostModel()
    return model.calculate_cost_scalar(order_value, volatility, avg_daily_volume, order_type)
