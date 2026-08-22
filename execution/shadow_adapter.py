"""
Shadow Trading Adapter - Run alongside live trading without execution.

This module provides a shadow trading implementation that mirrors live trading
logic but uses simulated execution for comparison and validation.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from .exchange_adapter import (
    ExchangeAdapter, OrderSide, OrderType, OrderStatus,
    Balance, Position, Order
)
from .trading_modes import TradingConfig
from .paper_adapter import PaperTradingAdapter

logger = logging.getLogger(__name__)


class ShadowTradingAdapter(PaperTradingAdapter):
    """Run alongside live trading without actual execution."""
    
    def __init__(
        self,
        config: TradingConfig,
        live_adapter: ExchangeAdapter,
        market_data_provider=None
    ):
        """
        Initialize the shadow trading adapter.
        
        Args:
            config: Trading configuration for shadow mode
            live_adapter: The live trading adapter to mirror
            market_data_provider: Optional provider for real-time market data
        """
        super().__init__(config, market_data_provider)
        self.live_adapter = live_adapter
        self._shadow_orders: List[Order] = []
        self._comparison_data: List[Dict] = []
        self._sync_from_live()
        
        logger.info("[SHADOW MODE] ShadowTradingAdapter initialized")
        logger.info(f"[SHADOW MODE] Mirroring live adapter: {live_adapter.__class__.__name__}")
    
    def _sync_from_live(self) -> None:
        """Sync initial state from live adapter."""
        try:
            # Sync balances
            live_balances = self.live_adapter.get_balance()
            for asset, balance in live_balances.items():
                self._balances[asset] = Balance(
                    asset,
                    balance.total,
                    balance.free,
                    balance.locked
                )
            
            # Sync positions
            live_positions = self.live_adapter.get_positions()
            for pos in live_positions:
                self._positions[pos.symbol] = Position(
                    pos.symbol,
                    pos.size,
                    pos.entry_price,
                    pos.current_price,
                    pos.unrealized_pnl
                )
            
            # Update equity
            self._update_equity()
            
            logger.info("[SHADOW MODE] State synced from live adapter")
        except Exception as e:
            logger.error(f"[SHADOW MODE] Failed to sync from live: {e}")
    
    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        amount: float,
        price: Optional[float] = None,
        client_order_id: Optional[str] = None,
    ) -> Order:
        """Create a shadow order (simulated, not sent to exchange)."""
        # Create the order using paper trading logic
        order = super().create_order(
            symbol, side, order_type, amount, price, client_order_id
        )
        
        # Mark as shadow order
        order.id = f"shadow_{order.id}"
        self._shadow_orders.append(order)
        
        logger.info(
            f"[SHADOW MODE] Order executed: {order.id} | {side.value.upper()} {amount} {symbol} "
            f"@ {order.price:.2f} (SIMULATED)"
        )
        
        return order
    
    def get_live_performance(self) -> Dict[str, Any]:
        """Get current performance from live adapter."""
        try:
            live_balances = self.live_adapter.get_balance()
            live_positions = self.live_adapter.get_positions()
            
            # Calculate total equity
            total_value = sum(b.total for b in live_balances.values())
            
            # Get USDT balance
            usdt_balance = live_balances.get('USDT', Balance('USDT', 0, 0, 0))
            
            # Calculate positions value
            positions_value = sum(
                p.size * p.current_price for p in live_positions
            )
            
            return {
                'total_equity': total_value,
                'cash': usdt_balance.total,
                'positions_value': positions_value,
                'positions_count': len(live_positions),
                'timestamp': datetime.now()
            }
        except Exception as e:
            logger.error(f"[SHADOW MODE] Failed to get live performance: {e}")
            return {}
    
    def compare_performance(self) -> Dict[str, Any]:
        """Compare shadow vs live performance."""
        shadow_perf = self.get_performance()
        live_perf = self.get_live_performance()
        
        shadow_equity = shadow_perf.get('current_equity', 0)
        live_equity = live_perf.get('total_equity', 0)
        
        if live_equity > 0:
            difference = shadow_equity - live_equity
            difference_percent = (difference / live_equity) * 100
        else:
            difference = 0
            difference_percent = 0
        
        comparison = {
            'timestamp': datetime.now(),
            'shadow': shadow_perf,
            'live': live_perf,
            'difference': difference,
            'difference_percent': difference_percent,
            'shadow_better': shadow_equity > live_equity,
            'shadow_return': shadow_perf.get('total_return', 0),
            'shadow_trades': shadow_perf.get('num_trades', 0)
        }
        
        self._comparison_data.append(comparison)
        
        # Log comparison
        logger.info(
            f"[SHADOW MODE] Performance comparison: Shadow=${shadow_equity:,.2f} vs Live=${live_equity:,.2f} "
            f"(Diff: ${difference:+,.2f}, {difference_percent:+.2f}%)"
        )
        
        return comparison
    
    def get_comparison_history(self) -> List[Dict]:
        """Get history of performance comparisons."""
        return self._comparison_data.copy()
    
    def get_shadow_orders(self) -> List[Order]:
        """Get all shadow orders."""
        return self._shadow_orders.copy()
    
    def analyze_divergence(self) -> Dict[str, Any]:
        """Analyze divergence between shadow and live trading."""
        if not self._comparison_data:
            return {'error': 'No comparison data available'}
        
        differences = [c['difference_percent'] for c in self._comparison_data]
        shadow_better_count = sum(1 for c in self._comparison_data if c['shadow_better'])
        
        avg_diff = sum(differences) / len(differences) if differences else 0
        max_diff = max(differences) if differences else 0
        min_diff = min(differences) if differences else 0
        
        return {
            'avg_difference_percent': avg_diff,
            'max_difference_percent': max_diff,
            'min_difference_percent': min_diff,
            'shadow_better_ratio': shadow_better_count / len(self._comparison_data),
            'total_comparisons': len(self._comparison_data),
            'divergence_detected': abs(avg_diff) > 1.0  # More than 1% average divergence
        }
    
    def reset(self) -> None:
        """Reset shadow state and re-sync from live."""
        super().reset()
        self._shadow_orders = []
        self._comparison_data = []
        self._sync_from_live()
        logger.info("[SHADOW MODE] Shadow adapter reset and re-synced")
