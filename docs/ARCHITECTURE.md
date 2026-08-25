# Architecture

## System Overview

The Crypto Trading Agent is a production-ready quantitative trading system designed for cryptocurrency markets. It implements a multi-layer architecture with clear separation of concerns, enabling robust strategy development, risk management, and execution.

### Key Design Principles

1. **Modularity**: Each component has a single responsibility
2. **Defensive Programming**: Multiple safety layers prevent catastrophic losses
3. **Statefulness**: System maintains state across restarts
4. **Observability**: Comprehensive logging and monitoring
5. **Testability**: All components are unit-testable

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CRYPTO TRADING AGENT                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │   Data Layer │    │ Feature Layer│    │ Regime Layer │ │
│  │  Providers   │───▶│ Engineering  │───▶│  Detection   │ │
│  │              │    │              │    │              │ │
│  │ - CoinGecko  │    │ - Technical  │    │ - Volatility │ │
│  │ - ccxt       │    │ - Statistical│    │ - Trend      │ │
│  │ - News API   │    │ - ML Features│    │ - Sentiment  │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │   Strategy   │    │   Ensemble   │    │   Portfolio  │ │
│  │   Engines    │───▶│   Selector   │───▶│  Optimizer   │ │
│  │              │    │              │    │              │ │
│  │ - Momentum   │    │ - Regime     │    │ - MVO        │ │
│  │ - Mean Rev   │    │ - Adaptive   │    │ - Risk Parity│ │
│  │ - ML Signal  │    │ - Scoring    │    │ - CVaR       │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │  Risk Engine │    │  Execution   │    │  Persistence │ │
│  │  + Circuit   │───▶│    Engine    │───▶│   Layer      │ │
│  │  Breaker     │    │              │    │              │ │
│  │              │    │              │    │              │ │
│  │ - Exposure   │    │ - Order Mgmt │    │ - SQLite/    │ │
│  │ - Drawdown   │    │ - Position   │    │ - PostgreSQL │ │
│  │ - Limits     │    │ - Reconcile  │    │ - Stateful   │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │     API      │    │  Monitoring  │    │   Backtest   │ │
│  │  (FastAPI)   │◀──▶│   Logging    │◀──▶│   Engine     │ │
│  │              │    │              │    │              │ │
│  │ - Status     │    │ - Structured │    │ - Walk-forward││
│  │ - Control    │    │ - Metrics    │    │ - Attribution ││
│  │ - Metrics    │    │ - Alerts     │    │ - Monte Carlo ││
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Descriptions

### Data Layer

**Purpose**: Acquire, validate, and normalize market data.

**Components**:
- `data_fetcher.py`: Main data acquisition from CoinGecko and other providers
- `news_fetcher.py`: News and sentiment data collection
- `ai_sentiment.py`: AI-powered sentiment analysis using Groq LLM

**Features**:
- Multi-provider fallback
- Data caching (`.cache/data/`)
- Timestamp normalization
- Volume validation

### Feature Layer

**Purpose**: Transform raw data into predictive features.

**Components**:
- `ml/feature_engineering.py`: Causal feature engineering
- `utils/timeframe.py`: Timeframe detection and handling

**Feature Categories**:
- Technical indicators (RSI, MACD, Bollinger Bands)
- Statistical measures (volatility, correlation)
- Lag features (autoregressive terms)
- Cross-sectional features

### Regime Layer

**Purpose**: Detect market regime for adaptive strategy selection.

**Components**:
- `strategy_selector.py`: Contains `detect_regime()` function

**Regime Types**:
- `low_vol_bullish`: Low volatility, upward trend
- `high_vol_bullish`: High volatility, upward trend
- `low_vol_bearish`: Low volatility, downward trend
- `high_vol_bearish`: High volatility, downward trend

### Strategy Layer

**Purpose**: Generate trading signals and allocations.

**Strategies Implemented**:
1. **Equal Weight**: Naive diversification
2. **Momentum**: Return-based momentum
3. **Mean Reversion**: Statistical arbitrage
4. **Risk Parity**: Equal risk contribution
5. **MVO**: Mean-variance optimization
6. **CVaR**: Conditional Value-at-Risk optimization
7. **Black-Litterman**: View-based allocation
8. **Trend Following**: Moving average crossover
9. **ML Signal**: Machine learning predictions

### Ensemble Layer

**Purpose**: Combine strategies adaptively based on regime and performance.

**Components**:
- `strategy_selector.py`: `StrategySelector` class
- `ensemble/`: Ensemble combination logic

**Features**:
- Track record tracking (6-period rolling window)
- Exponential Sharpe transformation
- Regime-aware weighting
- Defensive allocation in high volatility

### Portfolio Optimizer

**Purpose**: Convert strategy signals into portfolio weights.

**Components**:
- `portfolio_optimizer.py`: Main optimization engine

**Optimization Methods**:
- Mean-Variance Optimization (MVO)
- Risk Parity
- CVaR (Conditional Value-at-Risk)
- Black-Litterman
- Hierarchical Risk Parity (HRP)

### Risk Engine

**Purpose**: Independent risk evaluation that can override strategy decisions.

**Components**:
- `risk/risk_engine.py`: Centralized risk evaluation
- `risk/circuit_breaker.py`: Stateful circuit breaker
- `risk/risk_limits.py`: Configurable risk limits
- `risk/risk_metrics.py`: Risk metric calculations

**Risk Checks**:
- Gross exposure limits
- Position size limits
- Daily loss limits
- Drawdown limits
- Volatility constraints
- Liquidity requirements

### Circuit Breaker

**Purpose**: Automatic risk reduction during adverse conditions.

**State Machine**:
```
NORMAL → WARNING → DERISK → HALT → RECOVERY → NORMAL
```

**State Transitions**:

| From | To | Trigger |
|------|-----|---------|
| NORMAL | WARNING | Drawdown > 5% or daily loss > 1.5% |
| WARNING | DERISK | Drawdown > 8% or daily loss > 2.0% |
| DERISK | HALT | Drawdown > 12% or daily loss > 3.0% |
| HALT | RECOVERY | Drawdown recovers below 10% |
| RECOVERY | NORMAL | Drawdown recovers below 2% |

**Position Multipliers**:
- NORMAL: 100%
- WARNING: 70%
- DERISK: 40%
- HALT: 0%
- RECOVERY: 50%

### Execution Engine

**Purpose**: Manage order lifecycle and position tracking.

**Components**:
- `execution/exchange_adapter.py`: Exchange abstraction (ccxt)
- `execution/order_manager.py`: Order creation and tracking
- `execution/position_manager.py`: Position tracking
- `execution/fill_manager.py`: Fill processing
- `execution/reconciler.py`: Position reconciliation
- `execution/mode_factory.py`: Trading mode factory
- `execution/trading_modes.py`: Mode definitions

**Order Lifecycle**:
```
Created → Submitted → Open → Partially Filled → Filled
                       ↓
                    Cancelled
                       ↓
                    Rejected
                       ↓
                     Expired
```

### Persistence Layer

**Purpose**: Maintain state across system restarts.

**Components**:
- `db_manager.py`: Database operations
- `persistence/`: State persistence modules

**Persisted Data**:
- Strategy track records
- Circuit breaker state
- Order history
- Position snapshots
- Performance metrics

### API Layer

**Purpose**: External interface for monitoring and control.

**Components**:
- `app.py`: FastAPI application
- `api/`: API endpoint modules

**Endpoints**:
- `GET /status`: System status
- `GET /metrics`: Performance metrics
- `GET /positions`: Current positions
- `POST /control`: System control commands

### Monitoring & Observability

**Purpose**: System health tracking and alerting.

**Components**:
- `auto_logger.py`: Automated logging
- `logging_config.py`: Logging configuration
- `observability/`: Monitoring modules

**Logged Events**:
- Trade executions
- Risk limit breaches
- State transitions
- API requests
- Errors and exceptions

### Backtesting Engine

**Purpose**: Historical simulation with realistic modeling.

**Components**:
- `backtester.py`: Event-driven backtester
- `backtesting/`: Backtest utilities
- `performance/attribution.py`: Performance attribution

**Features**:
- Walk-forward validation
- Transaction cost modeling
- Slippage modeling
- Liquidity constraints
- Drawdown circuit breaker
- Performance attribution

---

## Data Flow

### Live Trading Flow

```
1. Data Fetch → 2. Feature Engineering → 3. Regime Detection
                                              ↓
4. Strategy Selection ← 5. Ensemble Scoring
         ↓
6. Portfolio Optimization → 7. Risk Check → 8. Circuit Breaker
                                                    ↓
9. Order Creation → 10. Order Submission → 11. Fill Processing
                                                   ↓
12. Position Update → 13. Persistence → 14. Logging
```

### Backtest Flow

```
1. Load Historical Data → 2. Walk-Forward Split
                                    ↓
3. For Each Fold:
   - Train on Train Set
   - Validate on Test Set
   - Simulate Trades
   - Calculate Metrics
                                    ↓
4. Aggregate Results → 5. Attribution Analysis
```

---

## Module Dependencies

```
main.py
├── data_fetcher.py
├── ai_sentiment.py
├── backtester.py
├── portfolio_optimizer.py
├── strategy_selector.py
├── db_manager.py
├── auto_logger.py
└── funding_rate_arb.py

backtester.py
├── strategy_selector.py
├── portfolio_optimizer.py
├── performance/attribution.py
└── models/transaction_cost.py

strategy_selector.py
├── regime detection logic
└── strategy scoring

portfolio_optimizer.py
├── PyPortfolioOpt (MVO, Risk Parity, CVaR)
└── custom optimizations

risk/risk_engine.py
├── risk/risk_limits.py
├── risk/risk_metrics.py
└── risk/circuit_breaker.py

execution/
├── exchange_adapter.py (ccxt)
├── order_manager.py
├── position_manager.py
└── reconciler.py
```

---

## Technology Stack

### Core Technologies

| Component | Technology | Version |
|-----------|------------|---------|
| Language | Python | 3.10+ |
| Database | SQLite/PostgreSQL | Latest |
| API | FastAPI | 0.115+ |
| Exchange | ccxt | 4.3+ |

### Key Libraries

| Library | Purpose | Version |
|---------|---------|---------|
| numpy | Numerical computing | 1.26+ |
| pandas | Data manipulation | 2.2+ |
| scikit-learn | Machine learning | 1.5+ |
| PyPortfolioOpt | Portfolio optimization | 1.5+ |
| scipy | Scientific computing | 1.14+ |
| matplotlib | Visualization | 3.9+ |
| pytest | Testing | 8.3+ |

### External Services

| Service | Purpose |
|---------|---------|
| CoinGecko | Price data |
| Binance (or other) | Exchange access |
| Groq | AI sentiment analysis |

---

## Deployment Architecture

### Development

```
┌─────────────┐
│   Local     │
│  Developer  │
│   Machine   │
├─────────────┤
│  main.py    │
│  app.py     │
│  SQLite DB  │
└─────────────┘
```

### Production

```
┌─────────────────────────────────────────┐
│           Cloud Platform                │
│         (Railway, AWS, etc.)            │
├─────────────────────────────────────────┤
│                                         │
│  ┌───────────┐    ┌───────────┐        │
│  │   Web     │    │  Worker   │        │
│  │  Process  │    │  Process  │        │
│  │           │    │           │        │
│  │ - API     │    │ - Trading │        │
│  │ - UI      │    │ - Loop    │        │
│  └───────────┘    └───────────┘        │
│                                         │
│  ┌───────────────────────────┐         │
│  │      PostgreSQL DB        │         │
│  └───────────────────────────┘         │
│                                         │
│  ┌───────────────────────────┐         │
│  │       Redis Cache         │         │
│  └───────────────────────────┘         │
│                                         │
└─────────────────────────────────────────┘
```

---

## Scalability Considerations

### Horizontal Scaling

- **API Layer**: Stateless, can be load-balanced
- **Worker Processes**: Multiple instances with partitioned symbols
- **Database**: Read replicas for reporting

### Vertical Scaling

- **Memory**: Scale with universe size
- **CPU**: Parallel backtesting and ML training
- **Storage**: Historical data grows over time

### Bottlenecks

1. **Data Fetching**: Rate-limited by providers
2. **ML Training**: CPU-intensive
3. **Optimization**: Quadratic programming complexity

---

## Security Architecture

### Defense in Depth

```
┌─────────────────────────────────────┐
│         Network Layer               │
│    - Firewall rules                 │
│    - Rate limiting                  │
├─────────────────────────────────────┤
│       Application Layer             │
│    - API key authentication         │
│    - Input validation               │
│    - Trading mode checks            │
├─────────────────────────────────────┤
│         Data Layer                  │
│    - Encrypted secrets              │
│    - Parameterized queries          │
│    - Access control                 │
└─────────────────────────────────────┘
```

### Key Security Features

- Environment variable-based secrets
- API key encryption at rest
- Trading mode isolation
- Kill switch for emergency halt
- Audit logging

---

## Version Information

- **Architecture Version**: 5.0
- **Last Updated**: 2024
- **Phase**: 35 (Documentation)

---

*This document reflects the actual implementation as of Phase 35.*
