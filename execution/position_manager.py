"""
Position Manager - Tracks and manages positions.

This module maintains accurate position state, updates positions based on fills,
calculates unrealized PnL, and enforces position limits.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

from .exchange_adapter import Position, Order, OrderSide, OrderStatus

logger = logging.getLogger(__name__)


@dataclass
class PositionLimits:
    """Configuration for position limits."""
    max_position_size: float = 100.0  # Maximum position size in base currency
    max_notional_value: float = 1000000.0  # Maximum notional value in quote currency
    max_leverage: float = 1.0  # Maximum leverage allowed


class PositionManager:
    """Tracks positions and updates them based on order fills."""
    
    def __init__(self, limits: Optional[PositionLimits] = None):
        """
        Initialize the Position Manager.
        
        Args:
            limits: Optional position limits configuration.
        """
        self.positions: Dict[str, Position] = {}  # symbol -> Position
        self.limits = limits or PositionLimits()
        logger.info("PositionManager initialized")
    
    def _check_position_limits(self, symbol: str, new_size: float, price: float) -> bool:
        """
        Check if a position update would violate limits.
        
        Args:
            symbol: Trading pair symbol.
            new_size: New position size after update.
            price: Current price.
        
        Returns:
            True if within limits, False if limits would be violated.
        """
        # Check max position size
        if abs(new_size) > self.limits.max_position_size:
            logger.warning(
                f"Position limit exceeded for {symbol}: "
                f"size={abs(new_size)} > max={self.limits.max_position_size}"
            )
            return False
        
        # Check max notional value
        notional_value = abs(new_size) * price
        if notional_value > self.limits.max_notional_value:
            logger.warning(
                f"Notional value limit exceeded for {symbol}: "
                f"value={notional_value} > max={self.limits.max_notional_value}"
            )
            return False
        
        return True
    
    def update_position(
        self,
        symbol: str,
        fill_price: float,
        fill_amount: float,
        side: OrderSide,
        current_price: Optional[float] = None,
    ) -> None:
        """
        Update a position based on a fill.
        
        Args:
            symbol: Asset symbol (e.g., 'BTC/USDT').
            fill_price: Execution price of the fill.
            fill_amount: Amount filled.
            side: BUY or SELL.
            current_price: Current market price (for PnL calculation).
        """
        if current_price is None:
            current_price = fill_price
        
        # Calculate new position size
        current_pos = self.positions.get(symbol)
        current_size = current_pos.size if current_pos else 0.0
        new_size = current_size + (fill_amount if side == OrderSide.BUY else -fill_amount)
        
        # Check position limits
        if not self._check_position_limits(symbol, new_size, fill_price):
            logger.error(f"Position update rejected due to limit violation: {symbol}")
            raise ValueError(f"Position limit violation for {symbol}")
        
        if current_pos is None:
            # Create new position
            self.positions[symbol] = Position(
                symbol=symbol,
                size=new_size,
                entry_price=fill_price,
                current_price=current_price,
                unrealized_pnl=0.0,
            )
            logger.info(f"New position created: {symbol} | size={new_size} @ {fill_price}")
            return
        
        # Update existing position
        pos = current_pos
        
        if side == OrderSide.BUY:
            # Buying - calculate weighted average entry price
            if new_size != 0:
                total_cost = (pos.size * pos.entry_price) + (fill_amount * fill_price)
                pos.entry_price = total_cost / new_size
            pos.size = new_size
        else:  # SELL
            # Selling - reduce position
            # Entry price remains unchanged when reducing
            pos.size = new_size
            
            # If we crossed from long to short or vice versa, recalculate entry
            if current_size * new_size < 0:
                # Position flipped direction
                pos.entry_price = fill_price
        
        # Update current price and PnL
        pos.current_price = current_price
        pos.unrealized_pnl = pos.size * (pos.current_price - pos.entry_price)
        
        if pos.size == 0:
            logger.info(f"Position closed: {symbol} | PnL={pos.unrealized_pnl:.2f}")
        else:
            logger.info(
                f"Position updated: {symbol} | size={pos.size:.6f} @ {pos.entry_price:.2f} | "
                f"PnL={pos.unrealized_pnl:.2f}"
            )
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position for a symbol.
        
        Args:
            symbol: Trading pair symbol.
        
        Returns:
            Position object or None if no position exists.
        """
        return self.positions.get(symbol)
    
    def get_all_positions(self) -> List[Position]:
        """
        Get all positions (including zero-size positions).
        
        Returns:
            List of all Position objects.
        """
        return list(self.positions.values())
    
    def get_open_positions(self) -> List[Position]:
        """
        Get positions with non-zero size.
        
        Returns:
            List of Position objects with non-zero size.
        """
        return [pos for pos in self.positions.values() if abs(pos.size) > 0.000001]
    
    def close_position(self, symbol: str) -> Optional[float]:
        """
        Close a position (set size to zero).
        
        Args:
            symbol: Trading pair symbol.
        
        Returns:
            Realized PnL from closing the position, or None if no position existed.
        """
        if symbol not in self.positions:
            logger.warning(f"No position to close for {symbol}")
            return None
        
        pos = self.positions[symbol]
        realized_pnl = pos.unrealized_pnl
        
        # Store final PnL before closing
        pos.size = 0.0
        pos.unrealized_pnl = 0.0
        
        logger.info(f"Position closed manually: {symbol} | Realized PnL={realized_pnl:.2f}")
        return realized_pnl
    
    def calculate_unrealized_pnl(self, symbol: str, current_price: float) -> float:
        """
        Calculate unrealized PnL for a position at a given price.
        
        Args:
            symbol: Trading pair symbol.
            current_price: Current market price.
        
        Returns:
            Unrealized PnL value.
        """
        pos = self.positions.get(symbol)
        if not pos or pos.size == 0:
            return 0.0
        return pos.size * (current_price - pos.entry_price)
    
    def update_prices(self, prices: Dict[str, float]) -> None:
        """
        Update current prices for all positions.
        
        Args:
            prices: Dictionary mapping symbols to current prices.
        """
        for symbol, price in prices.items():
            if symbol in self.positions:
                pos = self.positions[symbol]
                pos.current_price = price
                pos.unrealized_pnl = pos.size * (price - pos.entry_price)
    
    def get_total_unrealized_pnl(self, prices: Optional[Dict[str, float]] = None) -> float:
        """
        Calculate total unrealized PnL across all positions.
        
        Args:
            prices: Optional dictionary of current prices. If None, uses stored prices.
        
        Returns:
            Total unrealized PnL.
        """
        if prices:
            self.update_prices(prices)
        
        return sum(pos.unrealized_pnl for pos in self.get_open_positions())
    
    def get_position_summary(self) -> Dict[str, any]:
        """
        Get a summary of all positions.
        
        Returns:
            Dictionary with position statistics.
        """
        open_positions = self.get_open_positions()
        total_value = sum(abs(pos.size) * pos.current_price for pos in open_positions)
        total_pnl = sum(pos.unrealized_pnl for pos in open_positions)
        
        return {
            'total_positions': len(open_positions),
            'total_value': total_value,
            'total_unrealized_pnl': total_pnl,
            'long_positions': sum(1 for pos in open_positions if pos.size > 0),
            'short_positions': sum(1 for pos in open_positions if pos.size < 0),
        }