"""
Transaction Cost Model
---------------------
Realistic transaction costs with maker/taker fees, spread, and market impact.
"""

import numpy as np
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class TransactionCostModel:
    """
    Realistic transaction cost model for crypto trading.
    
    Costs:
    - Maker fee: limit orders (0.04%)
    - Taker fee: market orders (0.10%)
    - Spread: bid-ask spread (0.05%)
    - Market impact: price impact of large orders
    """
    
    def __init__(self, maker_fee: float = 0.0004, taker_fee: float = 0.0010,
                 spread: float = 0.0005, alpha: float = 0.01):
        """
        Args:
            maker_fee: Fee for limit orders (0.04%)
            taker_fee: Fee for market orders (0.10%)
            spread: Bid-ask spread (0.05%)
            alpha: Market impact coefficient
        """
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.spread = spread
        self.alpha = alpha
    
    def calculate_cost(self, order_value: float, volatility: float = 0.01,
                       avg_daily_volume: float = 1e6, order_type: str = 'taker') -> float:
        """
        Calculate total transaction cost.
        
        Cost = fee + spread + market_impact
        
        Args:
            order_value: Notional value of the order
            volatility: Daily volatility (default 1%)
            avg_daily_volume: Average daily volume in USD
            order_type: 'maker' or 'taker'
        """
        fee = self.maker_fee if order_type == 'maker' else self.taker_fee
        
        # Fee cost
        fee_cost = order_value * fee
        
        # Spread cost (half spread for mid-price execution)
        spread_cost = order_value * (self.spread / 2)
        
        # Market impact (square root model)
        # impact = alpha * sqrt(volume / ADV) * volatility
        participation = min(order_value / max(avg_daily_volume, 1e6), 1.0)
        impact_cost = order_value * self.alpha * np.sqrt(participation) * volatility
        
        total = fee_cost + spread_cost + impact_cost
        
        logger.debug(f"Cost breakdown: fee=${fee_cost:.2f}, spread=${spread_cost:.2f}, "
                    f"impact=${impact_cost:.2f}, total=${total:.2f}")
        
        return total
    
    def calculate_turnover_cost(self, old_weights: np.ndarray, new_weights: np.ndarray,
                                capital: float, volatility: float = 0.01,
                                avg_daily_volume: float = 1e6) -> float:
        """
        Calculate cost of rebalancing from old to new weights.
        """
        turnover = np.abs(new_weights - old_weights).sum() / 2
        order_value = capital * turnover
        return self.calculate_cost(order_value, volatility, avg_daily_volume)
