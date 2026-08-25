# Trading Modes

## Overview

The Crypto Trading Agent supports four distinct trading modes, each designed for specific stages of development, testing, and production deployment.

### Mode Comparison

| Mode | Capital | Execution | Real Money | Use Case |
|------|---------|-----------|------------|----------|
| `backtest` | Virtual | Simulated on historical data | No | Strategy development |
| `paper` | Virtual | Simulated with live data | No | System validation |
| `shadow` | Real (read-only) | Simulated in parallel | No | Performance comparison |
| `live` | Real | Actual exchange orders | Yes | Production trading |

---

## Mode Descriptions

### Backtest Mode

**Purpose**: Historical simulation for strategy development and validation.

**Characteristics**:
- Uses historical price data only
- No connection to exchanges required
- Fastest execution mode
- Supports walk-forward validation
- Full performance attribution available

**Configuration**:
```bash
TRADING_MODE=backtest
```

**Usage**:
```python
# Via command line
python main.py --mode backtest

# Or via run_backtest.py
python run_backtest.py
```

**When to Use**:
- Initial strategy development
- Parameter optimization
- Walk-forward validation
- Monte Carlo analysis

**Limitations**:
- Cannot predict future performance
- May not capture all market dynamics
- Slippage and costs are modeled, not real

---

### Paper Mode

**Purpose**: Simulated trading with live market data.

**Characteristics**:
- Virtual capital (configurable initial amount)
- Simulated order execution
- Real-time market data
- Full system functionality without risk
- Track record persisted to database

**Configuration**:
```bash
TRADING_MODE=paper
PAPER_INITIAL_CAPITAL=100000
```

**Usage**:
```bash
python main.py --mode paper
```

**When to Use**:
- System integration testing
- API validation
- Latency measurement
- Operational readiness verification

**Behavior**:
- Orders created but not sent to exchange
- Positions tracked virtually
- P&L calculated on virtual positions
- All safety checks active

---

### Shadow Mode

**Purpose**: Parallel execution tracking without affecting real positions.

**Characteristics**:
- Reads real exchange positions (read-only)
- Calculates what trades *would* be made
- Tracks hypothetical performance
- No actual order submission
- Useful for comparing strategy vs. reality

**Configuration**:
```bash
TRADING_MODE=shadow
SHADOW_PRIMARY_MODE=paper  # Optional: track against paper mode
```

**Usage**:
```bash
python main.py --mode shadow
```

**When to Use**:
- Comparing strategy signals to actual positions
- Validating execution logic
- Performance benchmarking
- Pre-live validation

**Behavior**:
- Fetches current positions from exchange
- Calculates target portfolio
- Logs intended trades (not executed)
- Tracks hypothetical P&L

---

### Live Mode

**Purpose**: Real money trading with actual exchange execution.

**Characteristics**:
- Real capital at risk
- Actual orders sent to exchange
- Full position reconciliation
- All safety mechanisms active
- Requires exchange API keys

**Configuration**:
```bash
TRADING_MODE=live
TRADING_EXCHANGE__API_KEY=your_api_key
TRADING_EXCHANGE__API_SECRET=your_secret
TRADING_EXCHANGE__SANDBOX=false  # Must be false for live trading
```

**Usage**:
```bash
python main.py --mode live
```

**When to Use**:
- Production trading only
- After thorough testing in other modes
- When all safety checks pass

**Safety Requirements**:
- ✅ Exchange API keys configured
- ✅ Database initialized
- ✅ Risk limits set appropriately
- ✅ Kill switch tested
- ✅ At least 2 weeks successful paper trading

---

## Mode Transitions

### Recommended Progression

```
backtest → paper → shadow → live
```

### Transition Checklist

#### Backtest → Paper
- [ ] Strategies show positive expected return
- [ ] Walk-forward validation complete
- [ ] Transaction costs modeled realistically
- [ ] Drawdown within acceptable limits

#### Paper → Shadow
- [ ] System runs stable for 1+ week
- [ ] No critical errors in logs
- [ ] API rate limits respected
- [ ] Position tracking accurate

#### Shadow → Live
- [ ] Shadow performance matches expectations
- [ ] All reconciliation checks pass
- [ ] Risk engine functioning correctly
- [ ] Kill switch tested and working
- [ ] Start with minimal capital

---

## Configuration

### Environment Variables

```bash
# Core mode setting
TRADING_MODE=paper  # backtest, paper, shadow, or live

# Paper mode settings
PAPER_INITIAL_CAPITAL=100000

# Shadow mode settings
SHADOW_PRIMARY_MODE=paper

# Exchange settings (required for shadow and live)
TRADING_EXCHANGE__NAME=binance
TRADING_EXCHANGE__SANDBOX=true   # false for live
TRADING_EXCHANGE__API_KEY=
TRADING_EXCHANGE__API_SECRET=
```

### Programmatic Mode Selection

```python
from execution.trading_modes import TradingMode

# Check current mode
current_mode = TradingMode.PAPER

# Mode properties
current_mode.is_simulated      # True for backtest, paper, shadow
current_mode.uses_real_capital # True only for live
current_mode.is_read_only      # True for backtest, paper, shadow
```

---

## Safety Guards by Mode

### Backtest
- No external dependencies
- No risk of capital loss
- Historical data only

### Paper
- Virtual capital only
- All risk checks active
- Circuit breaker functional
- Position limits enforced

### Shadow
- Read-only exchange access
- No order submission
- Reconciliation passive
- Risk monitoring active

### Live
- Full risk management stack
- Circuit breaker can halt trading
- Position reconciliation mandatory
- Kill switch available
- Daily loss limits enforced

---

## Mode Detection in Code

```python
import os

def get_trading_mode() -> str:
    """Get current trading mode from environment."""
    return os.environ.get('TRADING_MODE', 'paper')

def is_live_mode() -> bool:
    """Check if running in live mode."""
    return get_trading_mode() == 'live'

def is_simulated_mode() -> bool:
    """Check if running in simulated mode."""
    return get_trading_mode() in ['backtest', 'paper', 'shadow']
```

---

## Validation Requirements

### Before Any Mode

- [ ] Environment variables configured
- [ ] Database accessible
- [ ] Logging functional
- [ ] No syntax errors

### Before Live Mode (Additional)

- [ ] Exchange connectivity verified
- [ ] API permissions correct (spot trading enabled)
- [ ] Balance sufficient for minimum trades
- [ ] Risk limits appropriate for account size
- [ ] Emergency contacts documented
- [ ] Monitoring configured

---

## Troubleshooting

### Mode Not Changing

**Problem**: System continues running in old mode after change.

**Solution**:
```bash
# Ensure .env file is updated
cat .env | grep TRADING_MODE

# Restart the application
pkill -f "python main.py"
python main.py --mode paper
```

### Paper Mode Shows Zero Capital

**Problem**: Paper trading starts with $0.

**Solution**:
```bash
# Set initial capital
echo "PAPER_INITIAL_CAPITAL=100000" >> .env
```

### Live Mode Won't Start

**Problem**: Error when switching to live mode.

**Checklist**:
1. Verify API keys are set
2. Check `TRADING_EXCHANGE__SANDBOX=false`
3. Ensure minimum balance exists
4. Review logs for specific error

### Shadow Mode Shows No Positions

**Problem**: Shadow mode reports no existing positions.

**Possible Causes**:
- API keys lack read permissions
- Exchange sandbox mode still enabled
- No positions exist on exchange

---

## Best Practices

1. **Always start in backtest mode** when developing new strategies
2. **Run paper mode for at least 2 weeks** before considering live
3. **Use shadow mode to validate** your understanding of exchange state
4. **Start live mode with minimal capital** for first month
5. **Monitor all modes** with same rigor as live trading
6. **Keep detailed logs** for post-trade analysis
7. **Test kill switch** in paper mode regularly

---

## Version Information

- **Document Version**: 1.0
- **Last Updated**: 2024
- **Phase**: 35 (Documentation)

---

*This document reflects the actual implementation as of Phase 35.*
