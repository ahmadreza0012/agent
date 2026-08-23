# System Architecture

## Overview

This document describes the architecture of the Crypto Trading Agent system after Phase 34 refactoring.

## Directory Structure

```
agent/
├── core/                              # Core domain & shared components
│   ├── domain/                        # Domain models and interfaces
│   │   ├── models.py                  # Order, Position, Balance, Trade, Signal
│   │   └── interfaces.py              # Abstract interfaces (DataProvider, Strategy, etc.)
│   └── config/                        # Configuration
│       └── settings.py                # Centralized settings
│
├── data/                              # Data layer
│   ├── providers/                     # Data providers (CoinGecko, Binance)
│   ├── validators/                    # Data validation
│   └── cache/                         # OHLCV caching
│
├── features/                          # Feature engineering
│   ├── technical/                     # Technical indicators
│   ├── market/                        # Market features
│   └── sentiment/                     # Sentiment analysis
│
├── regime/                            # Regime detection
│   └── regime_engine.py
│
├── strategies/                        # Strategy implementations
│   ├── base.py                        # Base Strategy class
│   ├── trend/                         # Trend following
│   ├── mean_reversion/                # Mean reversion
│   ├── ml/                            # ML-based strategies
│   └── [optimizers]/                  # MVO, Risk Parity, CVaR, Black-Litterman
│
├── ensemble/                          # Strategy ensemble
│   └── strategy_selector.py
│
├── portfolio/                         # Portfolio construction
│   └── portfolio_optimizer.py
│
├── risk/                              # Risk management
│   ├── risk_engine.py                 # Centralized risk engine
│   ├── circuit_breaker.py             # Stateful circuit breaker
│   ├── risk_limits.py                 # Risk limit definitions
│   ├── risk_metrics.py                # Risk metric calculations
│   └── capital_preservation.py        # Capital preservation system
│
├── execution/                         # Execution engine
│   ├── exchange_adapter.py            # Exchange abstraction
│   ├── order_manager.py               # Order lifecycle
│   ├── position_manager.py            # Position tracking
│   ├── reconciler.py                  # Position reconciliation
│   └── kill_switch.py                 # Emergency kill switch
│
├── backtesting/                       # Backtesting framework
│   ├── engine.py                      # Main backtesting engine
│   ├── walk_forward.py                # Walk-forward validation
│   ├── attribution.py                 # Performance attribution
│   ├── costs.py                       # Transaction cost modeling
│   ├── robustness.py                  # Monte Carlo analysis
│   └── stress.py                      # Stress testing
│
├── ml/                                # Machine learning
│   ├── pipeline.py                    # ML pipeline
│   ├── validation.py                  # Purged walk-forward validation
│   ├── model_registry.py              # Model version tracking
│   └── feature_engineering.py         # ML feature engineering
│
├── persistence/                       # Persistence layer
│   ├── repositories/                  # Data repositories
│   └── db_manager.py                  # Database management
│
├── api/                               # FastAPI application
│   ├── routes/                        # API routes
│   │   ├── health.py
│   │   ├── status.py
│   │   ├── portfolio.py
│   │   ├── orders.py
│   │   ├── performance.py
│   │   ├── risk.py
│   │   └── admin.py
│   └── app.py                         # FastAPI application
│
├── monitoring/                        # Observability
│   ├── logging.py                     # Structured logging
│   └── metrics.py                     # Metrics collection
│
├── tests/                             # Test suite
│   ├── unit/                          # Unit tests
│   ├── integration/                   # Integration tests
│   ├── security/                      # Security tests
│   ├── time_series/                   # Time-series tests
│   └── fault/                         # Fault injection tests
│
├── docs/                              # Documentation
├── scripts/                           # Utility scripts
├── main.py                            # Main entry point
└── requirements.txt                   # Dependencies
```

## Core Components

### Domain Layer (`core/domain/`)

The domain layer contains the fundamental entities and interfaces:

**Models:**
- `Order` - Represents a trading order with side, type, status
- `Position` - Represents an open position with PnL tracking
- `Balance` - Represents asset balances
- `Trade` - Represents an executed trade (fill)
- `Signal` - Represents a trading signal

**Interfaces:**
- `DataProvider` - Abstract interface for market data
- `Strategy` - Abstract interface for trading strategies
- `RiskEngine` - Abstract interface for risk management
- `ExchangeAdapter` - Abstract interface for exchange integration
- `PortfolioOptimizer` - Abstract interface for portfolio optimization
- `RegimeDetector` - Abstract interface for regime detection

### Configuration (`core/config/`)

Centralized configuration management with:
- Risk parameters
- Transaction cost assumptions
- Liquidity constraints
- ML/ensemble settings
- Backtester defaults
- Helper functions for mode detection

### Risk Management (`risk/`)

Multi-layered risk management system:
1. **Risk Engine** - Centralized risk evaluation
2. **Circuit Breaker** - Stateful trading halt mechanism
3. **Risk Limits** - Position size, drawdown, and exposure limits
4. **Capital Preservation** - Drawdown-based risk reduction

### Execution (`execution/`)

Trading execution subsystem:
- Exchange abstraction layer
- Order lifecycle management
- Position tracking and reconciliation
- Kill switch for emergency halts

### Backtesting (`backtesting/`)

Comprehensive backtesting framework:
- Walk-forward validation
- Performance attribution
- Transaction cost modeling
- Monte Carlo robustness analysis
- Stress testing scenarios

## Data Flow

```
Data Providers → Feature Engineering → Regime Detection
                                              ↓
Strategy Ensemble ←────────────────────── ML Pipeline
         ↓
Portfolio Optimizer
         ↓
Risk Engine → Circuit Breaker → Execution Engine → Exchange
         ↓                              ↓
    Monitoring                    Persistence
```

## Key Design Principles

1. **Domain-Driven Design** - Clear separation between domain logic and infrastructure
2. **Dependency Injection** - Components depend on abstractions, not concrete implementations
3. **Single Responsibility** - Each module has one well-defined purpose
4. **Open/Closed Principle** - Open for extension, closed for modification
5. **Fail-Safe Defaults** - Conservative defaults that protect capital

## Trading Modes

The system supports four trading modes:

| Mode | Purpose | Risk Limits |
|------|---------|-------------|
| BACKTEST | Historical simulation | Research thresholds |
| PAPER | Live simulation | Live thresholds (no real money) |
| SHADOW | Parallel live tracking | Live thresholds |
| LIVE | Real trading | Strict live thresholds |

## Extension Points

### Adding a New Strategy

1. Create a new file in `strategies/[category]/`
2. Inherit from `Strategy` interface
3. Implement `generate_signal()`, `get_parameters()`, `set_parameters()`
4. Register in strategy selector

### Adding a New Data Provider

1. Create a new file in `data/providers/`
2. Inherit from `DataProvider` interface
3. Implement `get_ohlcv()`, `get_ticker()`, `get_balance()`
4. Register in data layer

### Adding a New Risk Metric

1. Add calculation to `risk/risk_metrics.py`
2. Update `risk/risk_engine.py` to use the metric
3. Add to risk evaluation logic

## Deployment Considerations

- Environment variables for sensitive configuration
- Health check endpoints for monitoring
- Structured logging for observability
- Rate limiting for API protection
- CORS configuration for web access

## Version History

- **v1.0.0** (Phase 34) - Final architecture refactoring
- Previous versions - See individual phase summaries
