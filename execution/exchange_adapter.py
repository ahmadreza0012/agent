"""
Exchange Adapter - Abstract interface for exchange integration.

This module provides the core abstraction layer for interacting with cryptocurrency exchanges.
It defines enums, dataclasses, and an abstract base class that concrete implementations must follow.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


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
    STOP_LIMIT = "stop_limit"


class OrderStatus(Enum):
    """Order status enumeration."""
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


@dataclass
class Balance:
    """Represents a balance for an asset."""
    asset: str
    total: float
    free: float
    locked: float
    
    def __post_init__(self):
        if self.total < 0:
            raise ValueError(f"Total balance cannot be negative: {self.total}")
        if self.free < 0:
            raise ValueError(f"Free balance cannot be negative: {self.free}")
        if self.locked < 0:
            raise ValueError(f"Locked balance cannot be negative: {self.locked}")
        if self.free + self.locked > self.total * 1.0001:  # Small tolerance for rounding
            logger.warning(f"Balance inconsistency: free + locked > total for {self.asset}")


@dataclass
class Position:
    """Represents a position in an asset."""
    symbol: str
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float = 0.0
    
    def __post_init__(self):
        self.unrealized_pnl = self.size * (self.current_price - self.entry_price)
    
    @property
    def market_value(self) -> float:
        """Calculate market value of the position."""
        return abs(self.size) * self.current_price
    
    @property
    def pnl_percentage(self) -> float:
        """Calculate PnL as a percentage of entry value."""
        if self.entry_price == 0 or self.size == 0:
            return 0.0
        return (self.unrealized_pnl / (abs(self.size) * self.entry_price)) * 100


@dataclass
class Order:
    """Represents an order."""
    id: str
    client_order_id: str
    symbol: str
    side: OrderSide
    type: OrderType
    price: Optional[float]
    amount: float
    filled_amount: float
    status: OrderStatus
    timestamp: datetime
    fee: Optional[Dict[str, Any]] = None
    average_price: Optional[float] = None
    remaining_amount: Optional[float] = None
    
    def __post_init__(self):
        if self.remaining_amount is None:
            self.remaining_amount = self.amount - self.filled_amount
    
    @property
    def is_complete(self) -> bool:
        """Check if order is complete (not open or partially filled)."""
        return self.status in (
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED
        )
    
    @property
    def fill_rate(self) -> float:
        """Calculate fill rate as a percentage."""
        if self.amount == 0:
            return 0.0
        return (self.filled_amount / self.amount) * 100


@dataclass
class Ticker:
    """Represents a ticker/price quote."""
    symbol: str
    bid: float
    ask: float
    last: float
    volume: float
    timestamp: datetime


class ExchangeAdapter(ABC):
    """
    Abstract base class for exchange adapters.
    
    This class defines the interface that all exchange adapters must implement.
    Concrete implementations should handle exchange-specific logic while
    maintaining this common interface.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the exchange adapter.
        
        Args:
            config: Configuration dictionary containing API keys, endpoints, etc.
                   Should never contain hardcoded credentials - use environment variables.
        """
        self.config = config or {}
        self._validate_config()
        logger.info(f"{self.__class__.__name__} initialized")
    
    def _validate_config(self) -> None:
        """Validate configuration. Override in subclasses for specific validation."""
        pass
    
    @abstractmethod
    def get_balance(self, asset: Optional[str] = None) -> Dict[str, Balance]:
        """
        Get balance(s) for asset(s).
        
        Args:
            asset: Optional asset symbol to filter by. If None, returns all balances.
        
        Returns:
            Dictionary mapping asset symbols to Balance objects.
        """
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """
        Get all open positions.
        
        Returns:
            List of Position objects.
        """
        pass
    
    @abstractmethod
    def get_ticker(self, symbol: str) -> Dict[str, float]:
        """
        Get current ticker/price for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT').
        
        Returns:
            Dictionary with price information.
        """
        pass
    
    @abstractmethod
    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        amount: float,
        price: Optional[float] = None,
        client_order_id: Optional[str] = None,
    ) -> Order:
        """
        Create a new order.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT').
            side: Order side (BUY or SELL).
            order_type: Order type (MARKET, LIMIT, etc.).
            amount: Amount to buy/sell.
            price: Price for limit orders (None for market orders).
            client_order_id: Unique client order ID for idempotency.
        
        Returns:
            Order object with order details.
        
        Raises:
            Exception: If order creation fails.
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """
        Cancel an existing order.
        
        Args:
            order_id: Exchange order ID.
            symbol: Trading pair symbol (optional for some exchanges).
        
        Returns:
            True if cancellation was successful.
        """
        pass
    
    @abstractmethod
    def get_order(self, order_id: str, symbol: Optional[str] = None) -> Optional[Order]:
        """
        Get order details and current status.
        
        Args:
            order_id: Exchange order ID.
            symbol: Trading pair symbol (optional for some exchanges).
        
        Returns:
            Order object or None if not found.
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if exchange connection is healthy.
        
        Returns:
            True if connection is healthy.
        """
        pass


class CCXTExchangeAdapter(ExchangeAdapter):
    """
    Concrete implementation using ccxt library.
    
    This adapter wraps ccxt to provide a clean interface while handling
    retry logic, rate limiting, and error handling.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the CCXT exchange adapter.
        
        Args:
            config: Configuration with exchange name, API keys, etc.
                   Example: {'exchange': 'binance', 'apiKey': '...', 'secret': '...'}
        """
        import ccxt
        
        self.ccxt = ccxt
        super().__init__(config)
        
        exchange_id = self.config.get('exchange', 'binance')
        exchange_class = getattr(ccxt, exchange_id, None)
        
        if not exchange_class:
            raise ValueError(f"Unsupported exchange: {exchange_id}")
        
        # Initialize ccxt exchange instance
        exchange_config = {
            'timeout': self.config.get('timeout', 30000),
            'enableRateLimit': self.config.get('enable_rate_limit', True),
        }
        
        # Add API credentials if provided
        api_key = self.config.get('api_key')
        api_secret = self.config.get('api_secret')
        if api_key and api_secret:
            exchange_config['apiKey'] = api_key
            exchange_config['secret'] = api_secret
        
        # Add optional parameters
        if 'sandbox' in self.config:
            exchange_config['sandbox'] = self.config['sandbox']
        
        self.exchange = exchange_class(exchange_config)
        self._max_retries = self.config.get('max_retries', 3)
        self._retry_delay = self.config.get('retry_delay', 1.0)
        
        logger.info(f"CCXTExchangeAdapter initialized for {exchange_id}")
    
    def _with_retry(self, func, *args, **kwargs):
        """Execute function with exponential backoff retry logic."""
        import time
        
        last_exception = None
        for attempt in range(self._max_retries):
            try:
                return func(*args, **kwargs)
            except (self.ccxt.NetworkError, self.ccxt.ExchangeError) as e:
                last_exception = e
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2 ** attempt)
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"All {self._max_retries} attempts failed. Last error: {e}")
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                raise
        
        raise last_exception
    
    def get_balance(self, asset: Optional[str] = None) -> Dict[str, Balance]:
        """Get balance(s) from exchange."""
        def _fetch():
            balance = self.exchange.fetch_balance()
            result = {}
            
            for currency, amounts in balance.items():
                if isinstance(amounts, dict) and 'total' in amounts:
                    result[currency] = Balance(
                        asset=currency,
                        total=amounts.get('total', 0.0) or 0.0,
                        free=amounts.get('free', 0.0) or 0.0,
                        locked=amounts.get('used', 0.0) or 0.0,
                    )
            
            return result
        
        balances = self._with_retry(_fetch)
        
        if asset:
            return {asset: balances.get(asset, Balance(asset, 0.0, 0.0, 0.0))}
        return balances
    
    def get_positions(self) -> List[Position]:
        """Get positions from exchange."""
        def _fetch():
            positions = self.exchange.fetch_positions()
            result = []
            
            for pos in positions:
                if pos.get('contracts', 0) != 0:  # Only non-zero positions
                    result.append(Position(
                        symbol=pos.get('symbol', ''),
                        size=pos.get('contracts', 0),
                        entry_price=pos.get('entryPrice', 0.0),
                        current_price=pos.get('markPrice', pos.get('lastPrice', 0.0)),
                        unrealized_pnl=pos.get('unrealizedPnl', 0.0),
                    ))
            
            return result
        
        return self._with_retry(_fetch)
    
    def get_ticker(self, symbol: str) -> Dict[str, float]:
        """Get ticker from exchange."""
        def _fetch():
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                'symbol': ticker.get('symbol', symbol),
                'bid': ticker.get('bid', 0.0),
                'ask': ticker.get('ask', 0.0),
                'last': ticker.get('last', ticker.get('close', 0.0)),
                'volume': ticker.get('baseVolume', 0.0),
                'timestamp': ticker.get('timestamp', datetime.now().timestamp()),
            }
        
        return self._with_retry(_fetch)
    
    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        amount: float,
        price: Optional[float] = None,
        client_order_id: Optional[str] = None,
    ) -> Order:
        """Create order on exchange."""
        def _create():
            params = {}
            if client_order_id:
                params['clientOrderId'] = client_order_id
            
            ccxt_order = self.exchange.create_order(
                symbol=symbol,
                type=order_type.value,
                side=side.value,
                amount=amount,
                price=price,
                params=params,
            )
            
            # Convert ccxt order to our Order format
            status_map = {
                'open': OrderStatus.OPEN,
                'closed': OrderStatus.FILLED,
                'canceled': OrderStatus.CANCELLED,
                'cancelled': OrderStatus.CANCELLED,
                'rejected': OrderStatus.REJECTED,
                'expired': OrderStatus.EXPIRED,
            }
            
            filled = ccxt_order.get('filled', 0) or 0
            amount_val = ccxt_order.get('amount', 0) or 0
            
            return Order(
                id=ccxt_order.get('id', ''),
                client_order_id=ccxt_order.get('clientOrderId', client_order_id or ''),
                symbol=ccxt_order.get('symbol', symbol),
                side=OrderSide(ccxt_order.get('side', 'buy')),
                type=OrderType(ccxt_order.get('type', 'market')),
                price=ccxt_order.get('price'),
                amount=amount_val,
                filled_amount=filled,
                status=status_map.get(ccxt_order.get('status', 'unknown'), OrderStatus.UNKNOWN),
                timestamp=datetime.fromtimestamp(ccxt_order.get('timestamp', datetime.now().timestamp()) / 1000),
                fee=ccxt_order.get('fee'),
                average_price=ccxt_order.get('average'),
            )
        
        return self._with_retry(_create)
    
    def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """Cancel order on exchange."""
        def _cancel():
            try:
                self.exchange.cancel_order(order_id, symbol)
                return True
            except Exception as e:
                logger.error(f"Failed to cancel order {order_id}: {e}")
                return False
        
        return self._with_retry(_cancel)
    
    def get_order(self, order_id: str, symbol: Optional[str] = None) -> Optional[Order]:
        """Get order from exchange."""
        def _fetch():
            try:
                ccxt_order = self.exchange.fetch_order(order_id, symbol)
                
                status_map = {
                    'open': OrderStatus.OPEN,
                    'closed': OrderStatus.FILLED,
                    'canceled': OrderStatus.CANCELLED,
                    'cancelled': OrderStatus.CANCELLED,
                    'rejected': OrderStatus.REJECTED,
                    'expired': OrderStatus.EXPIRED,
                }
                
                filled = ccxt_order.get('filled', 0) or 0
                amount_val = ccxt_order.get('amount', 0) or 0
                
                return Order(
                    id=ccxt_order.get('id', ''),
                    client_order_id=ccxt_order.get('clientOrderId', ''),
                    symbol=ccxt_order.get('symbol', ''),
                    side=OrderSide(ccxt_order.get('side', 'buy')),
                    type=OrderType(ccxt_order.get('type', 'market')),
                    price=ccxt_order.get('price'),
                    amount=amount_val,
                    filled_amount=filled,
                    status=status_map.get(ccxt_order.get('status', 'unknown'), OrderStatus.UNKNOWN),
                    timestamp=datetime.fromtimestamp(ccxt_order.get('timestamp', datetime.now().timestamp()) / 1000),
                    fee=ccxt_order.get('fee'),
                    average_price=ccxt_order.get('average'),
                )
            except Exception as e:
                logger.error(f"Failed to fetch order {order_id}: {e}")
                return None
        
        return self._with_retry(_fetch)
    
    def health_check(self) -> bool:
        """Check exchange health."""
        try:
            self.exchange.fetch_status()
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False