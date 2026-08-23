# Crypto Trading Agent - Documentation

Comprehensive documentation for the Crypto Trading Agent quantitative trading system.

## Documentation Index

### Core Documentation

| Document | Description |
|----------|-------------|
| [Architecture](ARCHITECTURE.md) | System architecture, components, and data flow |
| [Trading Modes](TRADING_MODES.md) | Backtest, Paper, Shadow, and Live modes |
| [Risk Management](RISK_MANAGEMENT.md) | Risk engine, circuit breaker, and safety controls |
| [Backtesting](BACKTESTING.md) | Walk-forward backtesting framework |
| [ML Validation](ML_VALIDATION.md) | Machine learning pipeline and validation |
| [Data Sources](DATA_SOURCES.md) | Data providers and management |
| [Execution](EXECUTION.md) | Order execution and position management |
| [Deployment](DEPLOYMENT.md) | Deployment guide and configuration |
| [Security](SECURITY.md) | Security practices and key management |
| [Testing](TESTING.md) | Test suite and quality assurance |

### Additional Documentation

| Document | Description |
|----------|-------------|
| [Configuration](CONFIGURATION.md) | Environment variables and settings |
| [Live Safety](LIVE_SAFETY.md) | Live trading safety checks |
| [Performance Optimization](PERFORMANCE_OPTIMIZATION.md) | Performance tuning guide |
| [Static Quality](STATIC_QUALITY.md) | Code quality standards |
| [Strategy Robustness](STRATEGY_ROBUSTNESS.md) | Strategy validation framework |

## Quick Reference

### Running the System

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run in paper trading mode
python main.py --mode paper

# Run backtests
python run_backtest.py

# Start API server
python app.py
```

### Key Directories

```
/workspace
├── api/              # FastAPI endpoints
├── backtesting/      # Backtest engines
├── config/           # Configuration modules
├── data/             # Data storage
├── database/         # Database layer
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
└── utils/            # Utilities
```

### Trading Modes Summary

| Mode | Capital | Execution | Use Case |
|------|---------|-----------|----------|
| `backtest` | Virtual | Simulated | Strategy development |
| `paper` | Virtual | Simulated | System validation |
| `shadow` | Real (read-only) | Simulated | Performance comparison |
| `live` | Real | Real | Production trading |

### Risk States

```
NORMAL → WARNING → DERISK → HALT → RECOVERY → NORMAL
```

- **NORMAL**: Full trading allowed (100% positions)
- **WARNING**: Caution advised (70% positions)
- **DERISK**: Reduced exposure (40% positions)
- **HALT**: Trading stopped (0% positions)
- **RECOVERY**: Gradual return (50% positions)

## Version Information

- **System Version**: 5.0
- **Documentation Version**: 1.0
- **Last Updated**: 2024
- **Python Version**: 3.10+

## Support

For issues and questions:
- Check existing documentation
- Review test cases for usage examples
- Examine log output for debugging

---

*This documentation reflects the actual implementation as of Phase 35.*
