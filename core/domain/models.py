"""
Core domain models for the trading system.

These models represent the fundamental entities used throughout the system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List, Any


class OrderSide(Enum):
    """Order side enumeration."""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Order type enumeration."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderStatus(Enum):
    """Order status enumeration."""
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class TradingMode(Enum):
    """Trading mode enumeration."""
    BACKTEST = "backtest"
    PAPER = "paper"
    SHADOW = "shadow"
    LIVE = "live"


@dataclass
class Order:
    """
    Represents a trading order.
    
    Attributes:
        id: Unique order identifier
        client_order_id: Client-provided order ID for idempotency
        symbol: Trading pair symbol (e.g., 'BTC/USDT')
        side: Buy or sell
        type: Market, limit, stop_loss, or take_profit
        price: Order price (for limit orders)
        amount: Order quantity
        filled_amount: Amount filled so far
        status: Current order status
        timestamp: Order creation time
        fee: Fee information
        metadata: Additional order metadata
    """
    id: str
    client_order_id: Optional[str]
    symbol: str
    side: OrderSide
    type: OrderType
    price: float
    amount: float
    filled_amount: float = 0.0
    status: OrderStatus = OrderStatus.OPEN
    timestamp: datetime = field(default_factory=datetime.now)
    fee: Optional[Dict[str, float]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert order to dictionary."""
        return {
            'id': self.id,
            'client_order_id': self.client_order_id,
            'symbol': self.symbol,
            'side': self.side.value,
            'type': self.type.value,
            'price': self.price,
            'amount': self.amount,
            'filled_amount': self.filled_amount,
            'status': self.status.value,
            'timestamp': self.timestamp.isoformat(),
            'fee': self.fee,
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Order':
        """Create order from dictionary."""
        return cls(
            id=data['id'],
            client_order_id=data.get('client_order_id'),
            symbol=data['symbol'],
            side=OrderSide(data['side']),
            type=OrderType(data['type']),
            price=data['price'],
            amount=data['amount'],
            filled_amount=data.get('filled_amount', 0.0),
            status=OrderStatus(data.get('status', 'open')),
            timestamp=datetime.fromisoformat(data['timestamp']) if isinstance(data.get('timestamp'), str) else data.get('timestamp', datetime.now()),
            fee=data.get('fee'),
            metadata=data.get('metadata'),
        )


@dataclass
class Position:
    """
    Represents a trading position.
    
    Attributes:
        symbol: Trading pair symbol
        size: Position size (positive for long, negative for short)
        entry_price: Average entry price
        current_price: Current market price
        unrealized_pnl: Unrealized profit/loss
        realized_pnl: Realized profit/loss from closed positions
        last_update: Last update timestamp
    """
    symbol: str
    size: float  # Positive for long, negative for short
    entry_price: float
    current_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)
    
    @property
    def notional_value(self) -> float:
        """Calculate notional value of position."""
        return abs(self.size * self.current_price)
    
    @property
    def pnl_percentage(self) -> float:
        """Calculate PnL as percentage of entry value."""
        if self.entry_price == 0:
            return 0.0
        return (self.current_price - self.entry_price) / self.entry_price
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary."""
        return {
            'symbol': self.symbol,
            'size': self.size,
            'entry_price': self.entry_price,
            'current_price': self.current_price,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'last_update': self.last_update.isoformat(),
            'notional_value': self.notional_value,
            'pnl_percentage': self.pnl_percentage,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Position':
        """Create position from dictionary."""
        return cls(
            symbol=data['symbol'],
            size=data['size'],
            entry_price=data['entry_price'],
            current_price=data['current_price'],
            unrealized_pnl=data.get('unrealized_pnl', 0.0),
            realized_pnl=data.get('realized_pnl', 0.0),
            last_update=datetime.fromisoformat(data['last_update']) if isinstance(data.get('last_update'), str) else data.get('last_update', datetime.now()),
        )


@dataclass
class Balance:
    """
    Represents an asset balance.
    
    Attributes:
        asset: Asset symbol (e.g., 'BTC', 'USDT')
        total: Total balance
        free: Available balance (not locked in orders)
        locked: Balance locked in open orders
        timestamp: Last update timestamp
    """
    asset: str
    total: float
    free: float
    locked: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def available(self) -> float:
        """Get available balance (alias for free)."""
        return self.free
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert balance to dictionary."""
        return {
            'asset': self.asset,
            'total': self.total,
            'free': self.free,
            'locked': self.locked,
            'timestamp': self.timestamp.isoformat(),
            'available': self.available,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Balance':
        """Create balance from dictionary."""
        return cls(
            asset=data['asset'],
            total=data['total'],
            free=data['free'],
            locked=data.get('locked', 0.0),
            timestamp=datetime.fromisoformat(data['timestamp']) if isinstance(data.get('timestamp'), str) else data.get('timestamp', datetime.now()),
        )


@dataclass
class Trade:
    """
    Represents an executed trade (fill).
    
    Attributes:
        id: Unique trade identifier
        order_id: ID of the parent order
        symbol: Trading pair symbol
        side: Buy or sell
        price: Execution price
        amount: Executed amount
        fee: Trade fee
        timestamp: Execution time
    """
    id: str
    order_id: str
    symbol: str
    side: OrderSide
    price: float
    amount: float
    fee: Optional[Dict[str, float]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def notional_value(self) -> float:
        """Calculate notional value of trade."""
        return self.price * self.amount
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trade to dictionary."""
        return {
            'id': self.id,
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side.value,
            'price': self.price,
            'amount': self.amount,
            'fee': self.fee,
            'timestamp': self.timestamp.isoformat(),
            'notional_value': self.notional_value,
        }


@dataclass
class Signal:
    """
    Represents a trading signal.
    
    Attributes:
        symbol: Trading pair symbol
        direction: Long or short signal
        strength: Signal strength (0.0 to 1.0)
        strategy: Strategy that generated the signal
        timestamp: Signal generation time
        metadata: Additional signal information
    """
    symbol: str
    direction: int  # 1 for long, -1 for short, 0 for neutral
    strength: float
    strategy: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert signal to dictionary."""
        return {
            'symbol': self.symbol,
            'direction': self.direction,
            'strength': self.strength,
            'strategy': self.strategy,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
        }
