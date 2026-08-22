# Phase 21: Live Trading Safety

## Overview

Live Trading Safety is the **final safety layer** before real capital is deployed. This phase implements all safeguards that protect against catastrophic losses, system failures, and market anomalies in live trading.

## Core Principles

1. **FAIL CLOSED** - If critical data is unavailable, do not guess. Stop trading.
2. **HARD AND SOFT BOUNDARIES** - Every safety limit has both a warning (soft) and stop (hard) boundary.
3. **IMPOSSIBLE TO EXCEED** - Hard limits must be programmatically impossible to exceed.
4. **PRE-TRADE VALIDATION** - All safety checks run BEFORE every trade decision.
5. **CONTINUOUS MONITORING** - Exchange health checked continuously in live mode.
6. **EXPLICIT RECOVERY** - Recovery from safety halt requires explicit manual action.

## Components

### 1. Live Safety Configuration (`execution/live_safety_config.py`)

Defines all safety limits and state tracking:

```python
from execution.live_safety_config import LiveSafetyLimits, LiveSafetyState

limits = LiveSafetyLimits()
limits.log_configuration()  # Log all configured limits

state = LiveSafetyState()
state.update_equity(10000.0)
state.record_trade(pnl=100.0, turnover=5000.0, symbol='BTC/USDT', side='BUY')
```

**Key Limits:**
| Category | Soft Limit | Hard Limit |
|----------|-----------|------------|
| Daily Loss | 2% | 5% |
| Total Drawdown | 10% | 15% |
| Position Size | - | 20% of portfolio |
| Total Exposure | - | 60% of portfolio |
| Max Order Value | - | $100,000 |
| Max Slippage | - | 0.5% |
| Max Data Age | 10s | 60s |
| API Failures | - | 3 consecutive |

### 2. Safety Checker (`execution/safety_checker.py`)

Validates all conditions before allowing a trade:

```python
from execution.safety_checker import SafetyChecker

checker = SafetyChecker(limits, state, exchange, position_manager, market_data)

# Run all checks
result = checker.check_all(order_request)
if not result.is_safe:
    logger.error(f"Trade blocked: {result.reason}")
```

**Checks Performed:**
1. Exchange Health (CRITICAL)
2. Data Quality (CRITICAL)
3. Loss Limits (CRITICAL)
4. Position Limits
5. Exposure Limits
6. Gradual Exposure Ramp
7. Order-Specific Limits

### 3. Live Safety Engine (`execution/live_safety_engine.py`)

Central orchestrator for live trading safety:

```python
from execution.live_safety_engine import LiveSafetyEngine
from execution.kill_switch import KillSwitch

engine = LiveSafetyEngine(
    limits=limits,
    kill_switch=kill_switch,
    exchange_adapter=exchange,
    position_manager=position_manager,
    market_data_provider=market_data
)

# Pre-trade check
result = engine.pre_trade_check(order_request)
if not result.is_safe:
    # Trade blocked - DO NOT EXECUTE
    return

# Post-trade update
engine.post_trade_update({
    'pnl': realized_pnl,
    'turnover': order_value,
    'symbol': 'BTC/USDT',
    'side': 'BUY',
    'amount': 0.1,
    'price': 50000.0
})

# Start continuous monitoring
engine.start_monitoring()
```

### 4. Live Safety Integration (`execution/live_safety_integration.py`)

Wraps all trading operations with safety checks:

```python
from execution.live_safety_integration import LiveSafetyIntegration

integration = LiveSafetyIntegration(
    safety_engine=safety_engine,
    order_manager=order_manager,
    position_manager=position_manager,
    risk_engine=risk_engine
)

# Execute order safely (PRIMARY ENTRY POINT)
result = integration.execute_order_safely(order_request)
if not result['success']:
    logger.error(f"Trade blocked: {result['error']}")
```

## Gradual Exposure Ramp

New live trading systems start with reduced exposure and increase gradually:

```python
# Initialize ramp at 10% initial exposure
engine.initialize_exposure_ramp()

# Attempt to increase exposure after positive performance
result = engine.attempt_exposure_increase()
if result.is_safe:
    logger.info(f"Exposure increased: {result.details}")
```

**Ramp Rules:**
- Start at 10% of target exposure
- Increase every 7 days (configurable)
- Maximum 10% increase per step
- Requires 5 consecutive positive days
- Stops at max_total_exposure (60%)

## Emergency Procedures

### Force Halt

```python
# Immediate trading halt
engine.force_halt("Critical system failure detected")
```

### Reset Daily Limits

```python
# Call at start of each trading day
engine.reset_daily_limits()
```

### Check Status

```python
status = engine.get_status()
print(f"Can trade: {status['can_trade']}")
print(f"Daily P&L: ${status['daily_pnl']:,.2f}")
print(f"Drawdown: {status['current_drawdown']*100:.2f}%")
```

## Integration Checklist

- [ ] LiveSafetyEngine integrates with KillSwitch
- [ ] Pre-trade checks run before every order
- [ ] Daily limits reset at configurable time
- [ ] Health checks run continuously (every 10 seconds)
- [ ] Data quality validated before trading
- [ ] Gradual exposure ramp configured
- [ ] Emergency halt procedures documented
- [ ] Alert callbacks configured for critical events

## Testing

Run all Phase 21 tests:

```bash
python -m unittest tests.test_phase21_live_safety -v
```

Expected output: 34 tests passing

## Files Created

1. `execution/live_safety_config.py` - Safety limits and state
2. `execution/safety_checker.py` - Pre-trade validation
3. `execution/live_safety_engine.py` - Safety orchestration
4. `execution/live_safety_integration.py` - Trading system integration
5. `tests/test_phase21_live_safety.py` - Unit tests
6. `docs/LIVE_SAFETY.md` - This documentation

## Next Steps

After completing Phase 21:
- **Phase 22:** Persistence
- **Phase 23:** Database  
- **Phase 24:** API
