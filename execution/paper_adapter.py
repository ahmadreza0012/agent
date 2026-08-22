"""
Paper Trading Adapter - Simulate trading with virtual capital using real market data.

This module provides a paper trading implementation that simulates realistic
execution (slippage, fees, latency) while using real-time market data.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from .exchange_adapter import (
    ExchangeAdapter, OrderSide, OrderType, OrderStatus,
    Balance, Position, Order
)
from .trading_modes import TradingConfig

logger = logging.getLogger(__name__)


class PaperTradingAdapter(ExchangeAdapter):
    """Simulate trading with virtual capital using real market data."""
    
    def __init__(self, config: TradingConfig, market_data_provider=None):
        """
        Initialize the paper trading adapter.
        
        Args:
            config: Trading configuration for paper mode
            market_data_provider: Optional provider for real-time market data
        """
        super().__init__(config={})
        self.config = config
        self.market_data = market_data_provider
        self._balances: Dict[str, Balance] = {
            'USDT': Balance('USDT', config.initial_capital, config.initial_capital, 0.0)
        }
        self._positions: Dict[str, Position] = {}
        self._orders: Dict[str, Order] = {}
        self._filled_orders: List[Order] = []
        self._order_counter = 0
        self._equity_history: List[Dict] = []
        self._initial_capital = config.initial_capital
        self._total_equity = config.initial_capital
        
        logger.info(f"[PAPER MODE] PaperTradingAdapter initialized with ${config.initial_capital:,.2f} virtual capital")
        logger.info(f"[PAPER MODE] Slippage model: {config.slippage_model}, Fee model: {config.fee_model}")
    
    def get_balance(self, asset: Optional[str] = None) -> Dict[str, Balance]:
        """Get balance(s) for asset(s)."""
        if asset:
            return {asset: self._balances.get(asset, Balance(asset, 0.0, 0.0, 0.0))}
        return self._balances.copy()
    
    def get_positions(self) -> List[Position]:
        """Get all open positions."""
        # Update position prices before returning
        for symbol, pos in self._positions.items():
            ticker = self.get_ticker(symbol)
            pos.current_price = ticker.get('price', pos.current_price)
            pos.unrealized_pnl = pos.size * (pos.current_price - pos.entry_price)
        return list(self._positions.values())
    
    def get_ticker(self, symbol: str) -> Dict[str, float]:
        """Get current ticker/price for a symbol."""
        if self.market_data:
            return self.market_data.get_ticker(symbol)
        # Fallback to last known price from positions or orders
        if symbol in self._positions:
            return {'price': self._positions[symbol].current_price, 'volume': 0.0}
        return {'price': 0.0, 'volume': 0.0}
    
    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        amount: float,
        price: Optional[float] = None,
        client_order_id: Optional[str] = None,
    ) -> Order:
        """Create a simulated order with realistic execution."""
        ticker = self.get_ticker(symbol)
        current_price = ticker.get('price', 0.0)
        
        if current_price == 0.0:
            raise ValueError(f"Unable to get price for {symbol}")
        
        # Calculate execution price with slippage
        execution_price = self._calculate_execution_price(
            symbol, side, order_type, amount, price, current_price
        )
        
        # Calculate fee
        fee = self._calculate_fee(execution_price, amount)
        total_cost = execution_price * amount + fee
        
        # Validate balance
        if side == OrderSide.BUY:
            if self._balances.get('USDT', Balance('USDT', 0, 0, 0)).free < total_cost:
                available = self._balances['USDT'].free
                raise ValueError(
                    f"Insufficient balance: ${available:,.2f} < ${total_cost:,.2f}"
                )
        else:
            base_asset = symbol.split('/')[0]
            if base_asset not in self._balances or \
               self._balances[base_asset].free < amount:
                available = self._balances.get(base_asset, Balance(base_asset, 0, 0, 0)).free
                raise ValueError(
                    f"Insufficient {base_asset} balance: {available} < {amount}"
                )
        
        # Create and execute order
        self._order_counter += 1
        order_id = f"paper_{self._order_counter}"
        client_oid = client_order_id or f"client_{self._order_counter}"
        
        order = Order(
            id=order_id,
            client_order_id=client_oid,
            symbol=symbol,
            side=side,
            type=order_type,
            price=execution_price,
            amount=amount,
            filled_amount=amount,
            status=OrderStatus.FILLED,
            timestamp=datetime.now(),
            fee={'cost': fee, 'currency': 'USDT'}
        )
        
        self._execute_order(order)
        self._orders[order.id] = order
        self._filled_orders.append(order)
        
        logger.info(
            f"[PAPER MODE] Order executed: {order.id} | {side.value.upper()} {amount} {symbol} "
            f"@ {execution_price:.2f} (fee: ${fee:.2f})"
        )
        
        return order
    
    def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """Cancel an existing order."""
        if order_id in self._orders and self._orders[order_id].status == OrderStatus.OPEN:
            self._orders[order_id].status = OrderStatus.CANCELLED
            logger.info(f"[PAPER MODE] Order cancelled: {order_id}")
            return True
        return False
    
    def get_order(self, order_id: str, symbol: Optional[str] = None) -> Optional[Order]:
        """Get order details and current status."""
        return self._orders.get(order_id)
    
    def health_check(self) -> bool:
        """Check if the adapter is healthy."""
        return True
    
    def _execute_order(self, order: Order) -> None:
        """Execute an order and update balances/positions."""
        symbol_parts = order.symbol.split('/')
        base_asset = symbol_parts[0]
        quote_asset = symbol_parts[1] if len(symbol_parts) > 1 else 'USDT'
        
        price = order.price
        amount = order.amount
        fee = order.fee.get('cost', 0) if order.fee else 0
        
        if order.side == OrderSide.BUY:
            # Deduct USDT
            cost = price * amount + fee
            self._balances['USDT'].total -= cost
            self._balances['USDT'].free -= cost
            
            # Add base asset
            if base_asset not in self._balances:
                self._balances[base_asset] = Balance(base_asset, 0.0, 0.0, 0.0)
            self._balances[base_asset].total += amount
            self._balances[base_asset].free += amount
            
            # Update position
            self._update_position(order.symbol, amount, price, OrderSide.BUY)
        else:
            # Deduct base asset
            self._balances[base_asset].total -= amount
            self._balances[base_asset].free -= amount
            
            # Add USDT proceeds
            proceeds = price * amount - fee
            self._balances['USDT'].total += proceeds
            self._balances['USDT'].free += proceeds
            
            # Update position
            self._update_position(order.symbol, amount, price, OrderSide.SELL)
        
        self._update_equity()
    
    def _update_position(self, symbol: str, amount: float, price: float, side: OrderSide) -> None:
        """Update position after an order execution."""
        if symbol not in self._positions:
            self._positions[symbol] = Position(
                symbol=symbol,
                size=0.0,
                entry_price=price,
                current_price=price,
                unrealized_pnl=0.0
            )
        
        pos = self._positions[symbol]
        
        if side == OrderSide.BUY:
            # Averaging in
            new_total = pos.size * pos.entry_price + amount * price
            pos.size += amount
            pos.entry_price = new_total / pos.size if pos.size > 0 else 0
        else:
            # Reducing position
            pos.size -= amount
            if pos.size <= 0:
                pos.size = 0
                pos.entry_price = 0.0
        
        pos.current_price = price
        pos.unrealized_pnl = pos.size * (pos.current_price - pos.entry_price)
    
    def _calculate_execution_price(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        amount: float,
        limit_price: Optional[float],
        current_price: float
    ) -> float:
        """Calculate execution price with slippage."""
        if order_type == OrderType.MARKET:
            slippage = self._calculate_slippage(symbol, amount)
            if side == OrderSide.BUY:
                return current_price * (1 + slippage)
            else:
                return current_price * (1 - slippage)
        else:
            # Limit order - use limit price or current price
            return limit_price if limit_price else current_price
    
    def _calculate_slippage(self, symbol: str, amount: float) -> float:
        """Calculate slippage based on order size and model."""
        if self.config.slippage_model == 'fixed':
            return 0.001  # Fixed 0.1% slippage
        elif self.config.slippage_model == 'dynamic':
            # Dynamic slippage based on order size
            base_slippage = 0.001  # 0.1% base
            size_factor = min(amount / 10.0, 0.01)  # Max 1% additional for large orders
            return base_slippage + size_factor
        else:  # 'real'
            # In paper mode, 'real' falls back to dynamic
            base_slippage = 0.001
            size_factor = min(amount / 10.0, 0.005)
            return base_slippage + size_factor
    
    def _calculate_fee(self, price: float, amount: float) -> float:
        """Calculate trading fee."""
        if self.config.fee_model == 'taker':
            return price * amount * 0.001  # 0.1% taker fee
        elif self.config.fee_model == 'maker':
            return price * amount * 0.0005  # 0.05% maker fee
        else:  # 'real'
            return price * amount * 0.001  # Default to taker fee
    
    def _update_equity(self) -> None:
        """Update total equity based on current positions."""
        total_value = self._balances['USDT'].total
        
        for symbol, pos in self._positions.items():
            ticker = self.get_ticker(symbol)
            total_value += pos.size * ticker.get('price', pos.current_price)
        
        self._total_equity = total_value
        
        self._equity_history.append({
            'timestamp': datetime.now(),
            'equity': total_value,
            'cash': self._balances['USDT'].total,
            'positions_value': total_value - self._balances['USDT'].total
        })
    
    def get_performance(self) -> Dict[str, Any]:
        """Get performance metrics."""
        if self._initial_capital == 0:
            return {
                'initial_capital': 0,
                'current_equity': 0,
                'cash': 0,
                'total_return': 0,
                'sharpe_ratio': 0,
                'num_trades': 0
            }
        
        total_return = (self._total_equity - self._initial_capital) / self._initial_capital
        
        # Calculate Sharpe ratio from equity history
        returns = []
        for i in range(1, len(self._equity_history)):
            prev_equity = self._equity_history[i-1]['equity']
            curr_equity = self._equity_history[i]['equity']
            if prev_equity > 0:
                ret = (curr_equity - prev_equity) / prev_equity
                returns.append(ret)
        
        if returns:
            avg_return = sum(returns) / len(returns)
            variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
            std_dev = variance ** 0.5
            sharpe = (avg_return / std_dev) if std_dev > 0 else 0
        else:
            sharpe = 0
        
        return {
            'initial_capital': self._initial_capital,
            'current_equity': self._total_equity,
            'cash': self._balances['USDT'].total,
            'total_return': total_return,
            'return_percent': total_return * 100,
            'sharpe_ratio': sharpe,
            'num_trades': len(self._filled_orders),
            'positions_count': len(self._positions)
        }
    
    def get_equity_history(self) -> List[Dict]:
        """Get equity history."""
        return self._equity_history.copy()
    
    def get_filled_orders(self) -> List[Order]:
        """Get all filled orders."""
        return self._filled_orders.copy()
    
    def reset(self) -> None:
        """Reset the adapter to initial state."""
        self._balances = {'USDT': Balance('USDT', self._initial_capital, self._initial_capital, 0.0)}
        self._positions = {}
        self._orders = {}
        self._filled_orders = []
        self._order_counter = 0
        self._equity_history = []
        self._total_equity = self._initial_capital
        logger.info("[PAPER MODE] Adapter reset to initial state")
