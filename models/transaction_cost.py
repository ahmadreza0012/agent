import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

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
    
    def calculate_cost(self, symbol: str, order_size: float, price: float, volume: float, volatility: float, side: str = 'buy', is_maker: bool = True) -> CostComponents:
        fee_rate = self.config['fee_maker'] if is_maker else self.config['fee_taker']
        fees = order_size * fee_rate
        spread = self._estimate_spread(symbol, price, volatility, volume)
        spread_cost = order_size * spread
        slippage = self._estimate_slippage(order_size, volume, volatility)
        slippage_cost = order_size * slippage
        impact = self._estimate_market_impact(order_size, volume)
        impact_cost = order_size * impact
        return CostComponents(fees=fees, spread=spread_cost, slippage=slippage_cost, market_impact=impact_cost)
    
    def _estimate_spread(self, symbol: str, price: float, volatility: float, volume: float) -> float:
        base = self.config['default_spread']
        vol_adj = 1.0 + volatility * 10.0
        liq_ratio = max(0.1, min(1.0, volume / self.config['min_liquidity']))
        liq_adj = 1.0 + (1.0 - liq_ratio) * 2.0
        return base * vol_adj * liq_adj
    
    def _estimate_slippage(self, order_size: float, volume: float, volatility: float) -> float:
        if volume <= 0:
            return self.config['base_slippage'] * 2.0
        vol_frac = order_size / volume
        return min(self.config['base_slippage'] + vol_frac * 5.0 + volatility * 2.0, 0.05)
    
    def _estimate_market_impact(self, order_size: float, volume: float) -> float:
        if volume <= 0:
            return self.config['market_impact_factor'] * 0.01
        return min(self.config['market_impact_factor'] * (order_size / volume) ** 0.5, 0.02)

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
