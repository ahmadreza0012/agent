# Phase 16: Execution Engine

## Overview

The Execution Engine is the critical bridge between the strategy layer and the real world. It provides a **safe, reliable, and production-grade** interface to cryptocurrency exchanges.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       EXECUTION ENGINE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │ ExchangeAdapter │    │  OrderManager   │                    │
│  │ (ccxt wrapper)  │    │  (order state)  │                    │
│  └────────┬────────┘    └────────┬────────┘                    │
│           │                      │                              │
│           ▼                      ▼                              │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │ PositionManager │    │   FillManager   │                    │
│  │ (position state)│    │  (fill processing)│                   │
│  └────────┬────────┘    └────────┬────────┘                    │
│           │                      │                              │
│           └──────────┬───────────┘                              │
│                      ▼                                          │
│          ┌─────────────────────┐                                │
│          │ PortfolioReconciler │                                │
│          │ (state comparison)  │                                │
│          └─────────────────────┘                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Exchange Adapter (`execution/exchange_adapter.py`)

Abstract interface for exchange integration using ccxt library.

**Key Classes:**
- `ExchangeAdapter` - Abstract base class
- `CCXTExchangeAdapter` - Concrete implementation using ccxt
- `Order`, `Position`, `Balance`, `Ticker` - Data classes
- `OrderSide`, `OrderType`, `OrderStatus` - Enums

**Methods:**
- `get_balance(asset)` - Get account balances
- `get_positions()` - Get open positions
- `get_ticker(symbol)` - Get current price
- `create_order(...)` - Create new order
- `cancel_order(order_id, symbol)` - Cancel order
- `get_order(order_id, symbol)` - Get order status
- `health_check()` - Check connection health

### 2. Order Manager (`execution/order_manager.py`)

Manages order lifecycle with idempotency guarantees.

**Key Features:**
- Unique `client_order_id` generation
- Duplicate order detection
- Order status tracking
- Timeout handling

**Methods:**
- `create_order(...)` - Create and track order
- `cancel_order(order_id)` - Cancel order
- `update_order_status(order_id)` - Refresh from exchange
- `get_open_orders()` - Get active orders
- `is_order_complete(order_id)` - Check completion status

### 3. Position Manager (`execution/position_manager.py`)

Maintains accurate position state.

**Key Features:**
- Position tracking by symbol
- Weighted average entry price calculation
- Unrealized PnL calculation
- Position limit enforcement

**Methods:**
- `update_position(symbol, fill_price, fill_amount, side)` - Update after fill
- `get_position(symbol)` - Get position
- `get_all_positions()` - Get all positions
- `close_position(symbol)` - Close position
- `calculate_unrealized_pnl(symbol, current_price)` - Calculate PnL

### 4. Fill Manager (`execution/fill_manager.py`)

Processes and reconciles order fills.

**Key Features:**
- Fill event processing
- Partial fill detection
- Fee calculation
- Position updates on fills

**Methods:**
- `process_fill(order, fill_data)` - Process fill event
- `get_fills(order_id)` - Get fills for order
- `is_order_fully_filled(order)` - Check fill status
- `calculate_fee(order, fill_data)` - Calculate fee

### 5. Portfolio Reconciler (`execution/reconciler.py`)

Ensures local state matches exchange state.

**Key Features:**
- Position reconciliation
- Balance reconciliation
- Mismatch detection
- Critical mismatch flagging

**Methods:**
- `reconcile()` - Full reconciliation
- `reconcile_positions()` - Position-only check
- `reconcile_balances()` - Balance-only check
- `detect_mismatch()` - Quick mismatch check

## Usage Example

```python
from execution import (
    CCXTExchangeAdapter,
    OrderManager,
    PositionManager,
    FillManager,
    PortfolioReconciler,
    OrderSide,
    OrderType,
)

# Initialize components
adapter = CCXTExchangeAdapter({
    'exchange': 'binance',
    'api_key': 'YOUR_API_KEY',
    'api_secret': 'YOUR_SECRET',
    'sandbox': True,
})

order_manager = OrderManager(adapter)
position_manager = PositionManager()
fill_manager = FillManager(position_manager, order_manager)
reconciler = PortfolioReconciler(adapter, position_manager)

# Create order with idempotency
order = order_manager.create_order(
    symbol='BTC/USDT',
    side=OrderSide.BUY,
    order_type=OrderType.MARKET,
    amount=0.1,
)

# Process fill when confirmed
fill_data = {
    'price': 50000.0,
    'amount': 0.1,
    'fee': {'cost': 5.0, 'currency': 'USDT'},
}
fill_manager.process_fill(order, fill_data)

# Periodic reconciliation
result = reconciler.reconcile()
if not result.is_consistent:
    print(f"Mismatch detected: {result.position_mismatches}")
```

## Critical Rules

1. **Never assume an order was filled** because `create_order()` returned successfully.
2. **Always verify order status** via `get_order()` or webhooks.
3. **Handle partial fills explicitly.**
4. **Implement retry logic** with exponential backoff for network errors.
5. **Never hard-code exchange credentials** - use environment variables.
6. **Every order must have a unique `client_order_id`** for idempotency.
7. **Never reconcile blindly** - if local and exchange state differ, enter RECONCILIATION_REQUIRED state.
8. **Log every order, fill, and error** with structured logging.

## Testing

Run tests:
```bash
python tests/test_phase16_execution.py
```

Test coverage includes:
- Unit tests for all components
- Integration tests for full execution flow
- Idempotency tests
- Mismatch detection tests
- Position limit tests

## Error Handling

All components implement:
- Retry logic with exponential backoff
- Structured error logging
- Graceful degradation on failures
- Clear error messages

## Security

- API keys loaded from environment variables only
- No credentials stored in code or logs
- Sandbox mode supported for testing
- Health checks before operations

## Next Steps

After Phase 16, continue with:
- **Phase 17:** Idempotency hardening & order recovery
- **Phase 18:** Position Reconciliation improvements
- **Phase 19:** Kill Switch implementation
- **Phase 20:** Paper/Shadow Trading modes
- **Phase 21:** Live Trading Safety
