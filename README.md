# Crypto Trading Agent

A production-ready, research-grade quantitative trading system for cryptocurrency markets.

## Features

- **Multi-Strategy Ensemble**: MVO, Risk Parity, CVaR, Black-Litterman, and Trend Following
- **ML-Powered Forecasting**: Random Forest with purged walk-forward validation
- **Regime Detection**: Adaptive strategy selection based on market conditions
- **Comprehensive Risk Management**: Centralized risk engine with circuit breaker
- **Four Trading Modes**: Backtest, Paper, Shadow, and Live trading
- **Production-Grade Execution**: Exchange abstraction with order management
- **Full Backtesting**: Walk-forward validation with transaction cost modeling
- **Performance Attribution**: Detailed P&L decomposition and analysis
- **REST API**: FastAPI endpoints for monitoring and control
- **Persistence Layer**: Stateful operation across restarts

## Quick Start

```bash
# Clone the repository
git clone https://github.com/ahmadreza0012/agent
cd agent

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings (API keys, database, etc.)

# Run in paper trading mode
python main.py --mode paper

# Run backtests
python run_backtest.py

# Start API server
python app.py
```

## System Requirements

- Python 3.10+
- PostgreSQL (production) or SQLite (development)
- Minimum 4GB RAM
- Network access to cryptocurrency exchanges

## Documentation

See the [docs/](docs/) directory for comprehensive documentation:

| Document | Description |
|----------|-------------|
| [Architecture](docs/ARCHITECTURE.md) | System overview and component design |
| [Trading Modes](docs/TRADING_MODES.md) | Backtest, Paper, Shadow, Live modes |
| [Risk Management](docs/RISK_MANAGEMENT.md) | Risk engine and circuit breaker |
| [Backtesting](docs/BACKTESTING.md) | Walk-forward backtesting framework |
| [ML Validation](docs/ML_VALIDATION.md) | Machine learning pipeline |
| [Data Sources](docs/DATA_SOURCES.md) | Data providers and management |
| [Execution](docs/EXECUTION.md) | Order execution and management |
| [Deployment](docs/DEPLOYMENT.md) | Deployment guide |
| [Security](docs/SECURITY.md) | Security practices |
| [Testing](docs/TESTING.md) | Test suite documentation |

## Trading Modes

| Mode | Capital | Execution | Use Case |
|------|---------|-----------|----------|
| `backtest` | Virtual | Simulated | Strategy development |
| `paper` | Virtual | Simulated | System validation |
| `shadow` | Real (read-only) | Simulated | Performance comparison |
| `live` | Real | Real | Production trading |

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     CRYPTO TRADING AGENT                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │   Data Layer │    │ Feature Layer│    │ Regime Layer │ │
│  │  Providers   │───▶│ Engineering  │───▶│  Detection   │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │   Strategy   │    │   Ensemble   │    │   Portfolio  │ │
│  │   Engines    │───▶│   Selector   │───▶│  Optimizer   │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │  Risk Engine │    │  Execution   │    │  Persistence │ │
│  │  + Circuit   │───▶│    Engine    │───▶│   Layer      │ │
│  │  Breaker     │    │              │    │              │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │     API      │    │  Monitoring  │    │   Backtest   │ │
│  │  (FastAPI)   │───▶│   Logging    │    │   Engine     │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

Key environment variables (see `.env.example` for full list):

```bash
# Trading mode: backtest, paper, shadow, live
TRADING_MODE=paper

# Exchange configuration
TRADING_EXCHANGE__NAME=binance
TRADING_EXCHANGE__SANDBOX=true

# Database
TRADING_DATABASE__TYPE=sqlite
TRADING_DATABASE__PATH=data/trading.db

# Safety limits
TRADING_LIMITS__MAX_DAILY_LOSS=0.05
TRADING_LIMITS__MAX_TOTAL_DRAWDOWN=0.15
TRADING_LIMITS__MAX_POSITION_SIZE=0.20
```

## Project Structure

```
.
├── api/              # FastAPI REST endpoints
├── backtesting/      # Backtest engines
├── config/           # Configuration modules
├── data/             # Data storage
├── database/         # Database layer
├── docs/             # Documentation
├── ensemble/         # Strategy ensemble
├── execution/        # Execution engine
├── ml/               # ML pipeline
├── models/           # Data models
├── observability/    # Logging & monitoring
├── performance/      # Performance attribution
├── persistence/      # State persistence
├── risk/             # Risk management
├── strategies/       # Trading strategies
├── tests/            # Test suite
├── utils/            # Utilities
├── main.py           # Main orchestrator
├── app.py            # FastAPI application
└── requirements.txt  # Dependencies
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run unit tests
pytest tests/unit/ -v

# Run with coverage
pytest --cov=. tests/
```

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

---

**Version**: 5.0  
**Last Updated**: 2024  
**Python**: 3.10+
