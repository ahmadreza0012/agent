import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

@dataclass
class CostBreakdown:
    """Detailed breakdown of transaction costs."""
    fees: float = 0.0
    spread: float = 0.0
    slippage: float = 0.0
    market_impact: float = 0.0
    total: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        return {
            'fees': self.fees,
            'spread': self.spread,
            'slippage': self.slippage,
            'market_impact': self.market_impact,
            'total': self.total,
        }

@dataclass
class CostComponents:
    fees: float = 0.0
    spread: float = 0.0
    slippage: float = 0.0
    market_impact: float = 0.0
    
    @property
    def total(self) -> float:
        return self.fees + self.spread + self.slippage + self.market_impact

class TransactionCostModel:
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {'fee_maker': 0.0005, 'fee_taker': 0.0010, 'default_spread': 0.0005, 'base_slippage': 0.0005, 'market_impact_factor': 0.1, 'min_liquidity': 10000}
    
    def calculate_cost(self, order_value: float, volatility: float, avg_daily_volume: float, 
                       order_type: str = 'taker') -> CostBreakdown:
        """
        Calculate transaction cost for a given order value.
        
        Args:
            order_value: Dollar value of the order
            volatility: Current volatility
            avg_daily_volume: Average daily volume
            order_type: 'maker' or 'taker'
            
        Returns:
            CostBreakdown with detailed cost components
        """
        fee_rate = self.config['fee_maker'] if order_type == 'maker' else self.config['fee_taker']
        fees = order_value * fee_rate
        
        # Spread cost estimation
        spread_rate = self.config['default_spread'] * (1.0 + volatility * 10.0)
        spread_cost = order_value * spread_rate
        
        # Slippage estimation
        if avg_daily_volume > 0:
            vol_frac = order_value / avg_daily_volume
            slippage_rate = min(self.config['base_slippage'] + vol_frac * 5.0 + volatility * 2.0, 0.05)
        else:
            slippage_rate = self.config['base_slippage'] * 2.0
        slippage_cost = order_value * slippage_rate
        
        # Market impact estimation
        if avg_daily_volume > 0:
            impact_rate = min(self.config['market_impact_factor'] * (order_value / avg_daily_volume) ** 0.5, 0.02)
        else:
            impact_rate = self.config['market_impact_factor'] * 0.01
        impact_cost = order_value * impact_rate
        
        total = fees + spread_cost + slippage_cost + impact_cost
        
        return CostBreakdown(
            fees=fees,
            spread=spread_cost,
            slippage=slippage_cost,
            market_impact=impact_cost,
            total=total
        )
    
    def calculate_cost_scalar(self, order_value: float, volatility: float, 
                              avg_daily_volume: float, order_type: str = 'taker') -> float:
        """Calculate total cost as a scalar value."""
        breakdown = self.calculate_cost(order_value, volatility, avg_daily_volume, order_type)
        return breakdown.total

class LiquidityConstraints:
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {'max_position_adv': 0.01, 'volume_participation': 0.10, 'min_liquidity': 10000, 'spread_threshold': 0.01, 'max_order_size': 100000}
    
    def check_constraints(self, order_size: float, volume: float, price: float, spread: float) -> Tuple[bool, str]:
        if volume < self.config['min_liquidity']:
            return False, f"Insufficient liquidity: volume={volume:.0f}"
        if order_size > self.config['max_order_size']:
            return False, f"Order size {order_size:.0f} exceeds max"
        if order_size / volume > self.config['volume_participation']:
            return False, f"Participation {order_size/volume:.1%} exceeds limit"
        if spread > self.config['spread_threshold']:
            return False, f"Spread {spread:.2%} exceeds threshold"
        return True, "OK"
