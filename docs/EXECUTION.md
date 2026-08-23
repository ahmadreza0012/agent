# Execution Engine

## Overview

The execution engine manages the complete order lifecycle from creation to settlement, with support for multiple trading modes and exchanges.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  EXECUTION ENGINE                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │    Order     │    │   Position   │    │     Fill     │ │
│  │   Manager    │    │   Manager    │    │   Manager    │ │
│  │              │    │              │    │              │ │
│  │ - Create     │    │ - Track      │    │ - Process    │ │
│  │ - Submit     │    │ - Update     │    │ - Reconcile  │ │
│  │ - Cancel     │    │ - Value      │    │ - Adjust     │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│         │                   │                    │         │
│         └───────────────────┼────────────────────┘         │
│                             ▼                              │
│                  ┌──────────────────┐                      │
│                  │ Exchange Adapter │                      │
│                  │     (ccxt)       │                      │
│                  └──────────────────┘                      │
│                             │                              │
│                             ▼                              │
│                  ┌──────────────────┐                      │
│                  │    Exchange      │                      │
│                  │  (Binance, etc.) │                      │
│                  └──────────────────┘                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Components

| Component | File | Purpose |
|-----------|------|---------|
| Exchange Adapter | `execution/exchange_adapter.py` | ccxt wrapper |
| Order Manager | `execution/order_manager.py` | Order lifecycle |
| Position Manager | `execution/position_manager.py` | Position tracking |
| Fill Manager | `execution/fill_manager.py` | Fill processing |
| Reconciler | `execution/reconciler.py` | Position reconciliation |
| Trading Modes | `execution/trading_modes.py` | Mode definitions |

---

## Exchange Abstraction

### ccxt Integration

```python
# From execution/exchange_adapter.py
import ccxt

class ExchangeAdapter:
    def __init__(self, exchange_name='binance', sandbox=True):
        exchange_class = getattr(ccxt, exchange_name)
        self.exchange = exchange_class({
            'sandbox': sandbox,
            'apiKey': os.environ.get('EXCHANGE_API_KEY'),
            'secret': os.environ.get('EXCHANGE_SECRET_KEY'),
        })
    
    def fetch_balance(self):
        """Fetch account balance."""
        return self.exchange.fetch_balance()
    
    def create_order(self, symbol, type, side, amount, price=None):
        """Create an order."""
        return self.exchange.create_order(symbol, type, side, amount, price)
    
    def cancel_order(self, order_id, symbol):
        """Cancel an order."""
        return self.exchange.cancel_order(order_id, symbol)
```

### Supported Exchanges

| Exchange | Spot | Futures | Testnet |
|----------|------|---------|---------|
| Binance | ✅ | ✅ | ✅ |
| Coinbase | ✅ | ❌ | ✅ |
| Kraken | ✅ | ✅ | ❌ |

---

## Order Management

### Order Lifecycle

```
Created → Submitted → Open → Partially Filled → Filled
                       ↓
                    Cancelled
                       ↓
                    Rejected
                       ↓
                     Expired
```

### Order Types

| Type | Description | Use Case |
|------|-------------|----------|
| Market | Execute at best available price | Urgent execution |
| Limit | Execute at specified price or better | Price control |
| Stop-Loss | Trigger market order at stop price | Risk management |

### Order Creation

```python
# From execution/order_manager.py
@dataclass
class Order:
    id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    type: str  # 'market' or 'limit'
    amount: float
    price: Optional[float]
    status: str = 'created'
    filled: float = 0.0
    remaining: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
```

---

## Position Management

### Position Tracking

```python
# From execution/position_manager.py
@dataclass
class Position:
    symbol: str
    quantity: float
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    
    @property
    def cost_basis(self) -> float:
        return self.quantity * self.avg_entry_price
    
    @property
    def pnl_percent(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return self.unrealized_pnl / self.cost_basis
```

### Position Updates

```python
def update_position(position: Position, fill: Fill):
    """Update position based on fill."""
    
    if fill.side == 'buy':
        # Adding to position
        total_cost = position.cost_basis + fill.cost
        total_qty = position.quantity + fill.quantity
        position.avg_entry_price = total_cost / total_qty
        position.quantity = total_qty
    else:
        # Reducing position
        position.realized_pnl += (fill.price - position.avg_entry_price) * fill.quantity
        position.quantity -= fill.quantity
```

---

## Fill Management

### Fill Processing

```python
# From execution/fill_manager.py
@dataclass
class Fill:
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    cost: float
    fee: float
    fee_currency: str
    timestamp: datetime
```

### Fee Calculation

```python
def calculate_fee(fill_value: float, fee_rate: float = 0.001) -> float:
    """Calculate trading fee."""
    return fill_value * fee_rate
```

---

## Reconciliation

### Purpose

Ensure internal position records match exchange state.

### Process

```python
# From execution/reconciler.py
def reconcile_positions(internal_positions, exchange_positions):
    """Compare internal and exchange positions."""
    
    discrepancies = []
    
    for symbol in set(internal_positions.keys()) | set(exchange_positions.keys()):
        internal_qty = internal_positions.get(symbol, 0)
        exchange_qty = exchange_positions.get(symbol, 0)
        
        if abs(internal_qty - exchange_qty) > TOLERANCE:
            discrepancies.append({
                'symbol': symbol,
                'internal': internal_qty,
                'exchange': exchange_qty,
                'difference': internal_qty - exchange_qty
            })
    
    return discrepancies
```

### Tolerance Levels

| Asset Type | Tolerance |
|------------|-----------|
| BTC | 0.00001 |
| ETH | 0.0001 |
| Altcoins | 0.01 |

---

## Idempotency

### Order ID Generation

```python
def generate_order_id(symbol: str, side: str, timestamp: datetime) -> str:
    """Generate idempotent order ID."""
    
    base = f"{symbol}_{side}_{timestamp.strftime('%Y%m%d%H%M%S')}"
    hash_id = hashlib.sha256(base.encode()).hexdigest()[:16]
    
    return f"cta_{hash_id}"
```

### Duplicate Prevention

```python
class OrderRegistry:
    def __init__(self):
        self.submitted_orders = set()
    
    def is_duplicate(self, order_id: str) -> bool:
        """Check if order was already submitted."""
        return order_id in self.submitted_orders
    
    def register(self, order_id: str):
        """Register order as submitted."""
        self.submitted_orders.add(order_id)
```

---

## Retry Logic

### Configuration

```python
RETRY_CONFIG = {
    'max_retries': 3,
    'initial_delay': 1.0,  # seconds
    'max_delay': 60.0,
    'backoff_multiplier': 2.0,
    'retryable_errors': [
        'TIMEOUT',
        'NETWORK_ERROR',
        'RATE_LIMITED',
    ]
}
```

### Implementation

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=60),
    reraise=True
)
def submit_order_with_retry(order):
    """Submit order with automatic retry."""
    
    try:
        result = exchange.create_order(...)
        return result
    except Exception as e:
        if type(e).__name__ in RETRY_CONFIG['retryable_errors']:
            raise  # Will be retried
        else:
            logger.error(f"Non-retryable error: {e}")
            raise
```

---

## Error Handling

### Error Categories

| Category | Examples | Action |
|----------|----------|--------|
| Network | Timeout, ConnectionError | Retry with backoff |
| Rate Limit | 429 Too Many Requests | Wait and retry |
| Validation | Invalid symbol, Bad price | Fix and resubmit |
| Authorization | Invalid API key | Alert and halt |
| Balance | Insufficient funds | Reduce size or halt |

### Error Handler

```python
def handle_error(error: Exception, context: Dict) -> ErrorAction:
    """Determine action based on error type."""
    
    if isinstance(error, ccxt.NetworkError):
        return ErrorAction.RETRY
    
    elif isinstance(error, ccxt.RateLimitExceeded):
        return ErrorAction.WAIT_AND_RETRY
    
    elif isinstance(error, ccxt.AuthenticationError):
        return ErrorAction.HALT_AND_ALERT
    
    elif isinstance(error, ccxt.InsufficientFunds):
        return ErrorAction.REDUCE_SIZE
    
    else:
        return ErrorAction.LOG_AND_CONTINUE
```

---

## Partial Fills

### Handling

```python
def handle_partial_fill(order: Order, fill: Fill):
    """Process partial fill."""
    
    order.filled += fill.quantity
    order.remaining = order.amount - order.filled
    order.status = 'partially_filled' if order.remaining > 0 else 'filled'
    
    # Update position for filled portion
    position_manager.update(order.symbol, fill)
    
    if order.remaining > 0:
        # Keep order active for remaining quantity
        logger.info(f"Partial fill: {order.filled}/{order.amount}")
    else:
        logger.info(f"Order complete: {order.id}")
```

---

## Performance Considerations

### Latency Optimization

1. **Connection Pooling**: Reuse HTTP connections
2. **Async Operations**: Non-blocking order submission
3. **Local Caching**: Cache frequently accessed data
4. **Batch Operations**: Group related requests

### Throughput Limits

| Operation | Max Rate |
|-----------|----------|
| Order Submit | 10/sec |
| Order Cancel | 20/sec |
| Balance Fetch | 1/sec |
| Price Fetch | 5/sec |

---

## Troubleshooting

### Order Not Filling

**Symptoms**: Order stays in "open" state.

**Causes**:
- Limit price too far from market
- Low liquidity
- Order size too large

**Resolution**:
```python
# Check order status
order = order_manager.get_order(order_id)
print(f"Status: {order.status}, Filled: {order.filled}/{order.amount}")

# If stuck, consider canceling and repricing
if order.age_minutes > 30 and order.filled == 0:
    order_manager.cancel(order_id)
```

### Position Mismatch

**Symptoms**: Internal position doesn't match exchange.

**Resolution**:
```bash
# Run reconciliation
python scripts/reconcile.py --symbols BTC/USDT

# Force sync from exchange
python scripts/sync_positions.py --force
```

### API Errors

**Symptoms**: Repeated API failures.

**Diagnosis**:
```python
# Check API connectivity
adapter = ExchangeAdapter()
try:
    balance = adapter.fetch_balance()
    print("API OK")
except Exception as e:
    print(f"API Error: {e}")
```

---

## Best Practices

1. **Always use idempotent order IDs** - Prevent duplicates
2. **Implement retry logic** - Handle transient errors
3. **Reconcile regularly** - Catch discrepancies early
4. **Log all operations** - For debugging and audit
5. **Test in paper mode first** - Validate before live
6. **Monitor fill rates** - Detect execution issues
7. **Handle partial fills** - Don't assume full fills

---

## Version Information

- **Document Version**: 1.0
- **Last Updated**: 2024
- **Phase**: 35 (Documentation)

---

*This document reflects the actual implementation as of Phase 35.*
