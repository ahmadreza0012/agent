# Migration Guide - Phase 34 Architecture Refactoring

## Overview

This guide documents the migration from the legacy module structure to the new domain-driven architecture.

## What Changed

### New Modules Created

| New Location | Purpose |
|--------------|---------|
| `core/domain/models.py` | Centralized domain models (Order, Position, Balance, etc.) |
| `core/domain/interfaces.py` | Abstract interfaces for key components |
| `core/config/settings.py` | Centralized configuration |
| `features/technical/` | Technical indicators |
| `features/market/` | Market features |
| `features/sentiment/` | Sentiment analysis |
| `strategies/trend/` | Trend following strategies |
| `strategies/mean_reversion/` | Mean reversion strategies |
| `strategies/ml/` | ML-based strategies |
| `persistence/repositories/` | Data repositories |

### Files Moved

| Old Location | New Location |
|--------------|-------------|
| `config.py` | `core/config/settings.py` (copy) |
| `regime_engine.py` (in strategies/) | `regime/regime_engine.py` |
| Various execution files | `execution/` (consolidated) |
| API routes | `api/routes/` (already organized) |

## Import Changes

### Before (Legacy)

```python
from config import RISK_FREE_RATE, DEFAULT_TRADING_MODE
from risk_policy import RiskPolicy
from data_fetcher import DataFetcher
```

### After (New Architecture)

```python
from core.config.settings import RISK_FREE_RATE, DEFAULT_TRADING_MODE
from risk.risk_limits import RiskPolicy
from data.providers.coingecko import DataFetcher
```

### Domain Models

```python
# New recommended imports
from core.domain.models import Order, Position, Balance, Trade, Signal
from core.domain.interfaces import DataProvider, Strategy, RiskEngine

# Also available via root core import (with deprecation warning)
from core import Order, Position, Balance
```

## Backward Compatibility

The system maintains backward compatibility through:

1. **Original files preserved** - Legacy files remain in place
2. **Deprecation warnings** - Old import paths trigger warnings
3. **Gradual migration path** - Update imports incrementally

## Migration Steps

### Step 1: Verify New Imports Work

```bash
cd /workspace
python -c "from core.domain.models import Order; print('OK')"
python -c "from core.config.settings import RISK_FREE_RATE; print('OK')"
```

### Step 2: Update Your Code

Replace old imports with new ones:

```python
# OLD
from config import RISK_FREE_RATE

# NEW
from core.config.settings import RISK_FREE_RATE
```

### Step 3: Test Functionality

Run your existing tests to ensure nothing breaks:

```bash
python main.py --mode backtest
```

### Step 4: Remove Deprecated Imports

Once all code is updated, you can remove legacy imports.

## Key Concepts

### Domain-Driven Design

The new architecture organizes code by business domain:
- **Domain layer** (`core/domain/`) - Core business entities
- **Infrastructure layer** (`data/`, `execution/`, `persistence/`) - Technical implementations
- **Application layer** (`api/`, `main.py`) - Application logic

### Clear Boundaries

Each module has a single responsibility:
- `core/` - Shared domain models and configuration
- `data/` - Data acquisition and validation
- `features/` - Feature engineering
- `strategies/` - Trading strategy implementations
- `risk/` - Risk management
- `execution/` - Order execution
- `backtesting/` - Historical simulation

## Troubleshooting

### Import Errors

If you get `ModuleNotFoundError`:
1. Check that the new directory structure exists
2. Verify `__init__.py` files are present
3. Use the new import paths

### Circular Dependencies

If you encounter circular imports:
1. Move shared types to `core/domain/`
2. Use abstract interfaces in `core/domain/interfaces.py`
3. Import at the function level if necessary

## Getting Help

- Review `docs/ARCHITECTURE.md` for the full architecture
- Check individual module docstrings for usage examples
- See existing code for import patterns
