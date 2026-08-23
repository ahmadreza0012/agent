# PHASE 30: STRATEGY ROBUSTNESS - IMPLEMENTATION GUIDE

## Overview

Phase 30 introduces a comprehensive **Strategy Robustness Framework** to ensure all trading strategies in the system are:
- Economically sound with clear rationale
- Validated on out-of-sample data
- Robust across different market regimes
- Resilient to parameter changes
- Profitable after transaction costs
- Better than simple benchmarks

This phase completes the journey from having "working strategies" to having **validated, production-ready strategies**.

---

## Key Components

### 1. Strategy Validation Framework (`strategies/validation.py`)

The core validation system that tests strategies across 7 dimensions:

#### Validation Dimensions

| Dimension | Weight | Target | Description |
|-----------|--------|--------|-------------|
| OOS Sharpe | 25% | > 0.5 | Out-of-sample risk-adjusted returns |
| Regime Consistency | 20% | > 0.6 | Works across bull/bear/sideways markets |
| Parameter Robustness | 20% | > 0.6 | Stable under parameter variations |
| Cost-Adjusted Sharpe | 20% | > 0.3 | Profitable after transaction costs |
| Benchmark Comparison | 15% | > 0 | Beats buy-and-hold, momentum |

#### Validation Statuses

```python
class ValidationStatus(Enum):
    PASS = "pass"           # Meets all criteria
    FAIL = "fail"           # Below thresholds but not terrible
    INCONCLUSIVE = "inconclusive"  # Needs more data
    REJECTED = "rejected"   # Failed critical criteria
```

#### Usage Example

```python
from strategies.validation import (
    StrategyRobustnessValidator, 
    ValidationStatus, 
    StrategyHypothesis
)

# Define economic hypothesis
hypothesis = StrategyHypothesis(
    name="momentum",
    description="Momentum-based trend following",
    economic_rationale="Captures investor herding and delayed price discovery",
    expected_mechanism="Buy recent winners, sell recent losers",
    expected_regimes=["trending_up", "trending_down"],
    risk_factors=["range_bound_markets", "high_volatility"],
    dependencies=["price_data", "volume_data"],
    market_inefficiency="Behavioral bias toward extrapolation"
)

# Attach to strategy
strategy.hypothesis = hypothesis

# Validate
validator = StrategyRobustnessValidator()
result = validator.validate_strategy(
    strategy=strategy,
    data=in_sample_data,
    oos_data=out_of_sample_data,
    transaction_costs=0.001
)

print(f"Status: {result.status.value}")
print(f"Score: {result.score:.2f}")
print(f"OOS Sharpe: {result.metrics['oos_sharpe']:.2f}")
```

---

### 2. Strategy Registry (`strategies/registry.py`)

Centralized tracking of all strategies with their status and metadata.

#### Strategy Statuses

```python
class StrategyStatus(Enum):
    ACTIVE = "active"           # Passed validation, approved for production
    INACTIVE = "inactive"       # Temporarily disabled
    DEPRECATED = "deprecated"   # Being phased out
    EXPERIMENTAL = "experimental"  # Under testing
    REJECTED = "rejected"       # Failed validation
    PENDING_REVIEW = "pending_review"  # Awaiting validation
```

#### Usage Example

```python
from strategies.registry import StrategyRegistry, StrategyStatus

registry = StrategyRegistry()

# Register a strategy
registry.register(
    MomentumStrategy,
    name="momentum",
    description="12-month momentum with 1-month skip",
    status=StrategyStatus.EXPERIMENTAL,
    tags=["trend", "momentum", "long_short"],
    version="2.1.0",
    author="Quant Team",
    hypothesis=my_hypothesis
)

# Update status after validation
registry.set_validation_result("momentum", validation_result)

# Get active strategies for production
active_strategies = registry.get_active_strategies()

# Generate inventory report
report_df = registry.generate_inventory_report()
print(report_df)
```

---

### 3. Strategy Pruning Script (`scripts/prune_strategies.py`)

Automated script to identify and remove weak strategies.

#### Features
- Dry-run mode for safe testing
- Configurable minimum score threshold
- Detailed CSV reports
- Automatic status updates

#### Usage

```bash
# Dry run (no changes)
python scripts/prune_strategies.py --dry-run

# Apply changes
python scripts/prune_strategies.py --dry-run=false

# Custom threshold
python scripts/prune_strategies.py --min-score 0.5

# Save to custom location
python scripts/prune_strategies.py --output my_report.csv
```

---

## Strategy Review Guidelines

### Before Adding a Strategy

Every strategy must answer these questions:

#### 1. Economic Rationale
- **What market inefficiency does this exploit?**
  - Example: "Momentum captures investor herding behavior"
  
- **Why should this inefficiency exist?**
  - Example: "Behavioral biases cause delayed price discovery"
  
- **What is the expected mechanism?**
  - Example: "Buy recent winners, sell recent losers"

#### 2. Expected Behavior
- **Under what conditions should it work?**
  - Example: "Strong trends, low to moderate volatility"
  
- **Under what conditions should it fail?**
  - Example: "Range-bound markets, high volatility reversals"

#### 3. Risk Factors
Identify how the strategy can fail:
- **Technical**: Data issues, execution problems
- **Market**: Regime changes, liquidity drops
- **Behavioral**: Changing investor behavior
- **Structural**: Regulatory changes, market structure changes

---

## Decision Criteria

### PASS Criteria
A strategy passes validation when ALL of the following are true:

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| OOS Sharpe | > 0.5 | Meaningful risk-adjusted returns |
| Cost-Adjusted Sharpe | > 0.3 | Survives transaction costs |
| Max Drawdown | < 25% | Acceptable risk level |
| Regime Consistency | > 0.6 | Works in multiple regimes |
| Parameter Robustness | > 0.6 | Not overfit to specific params |

### REJECT Criteria
A strategy is rejected if ANY of the following are true:

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| OOS Sharpe | < 0.1 | No meaningful edge |
| Cost-Adjusted Sharpe | < 0.1 | Costs eliminate all profit |
| Regime Consistency | < 0.3 | Only works in one regime |
| Parameter Robustness | < 0.3 | Overfit to specific parameters |
| Economic Rationale | Missing | No reason to believe it will work |

### INCONCLUSIVE
Use when:
- OOS Sharpe between 0.1 and 0.5
- Limited data available
- Some regime inconsistency
- Needs more testing

---

## Implementation Checklist

### For Each New Strategy

- [ ] **Define Hypothesis**
  - [ ] Economic rationale documented
  - [ ] Expected mechanism explained
  - [ ] Market inefficiency identified
  - [ ] Risk factors listed
  - [ ] Expected regimes specified

- [ ] **Implement Strategy**
  - [ ] No look-ahead bias
  - [ ] No data leakage
  - [ ] Correct mathematics
  - [ ] Handles missing data
  - [ ] Has `generate_signals()` method
  - [ ] Has `get_params()` and `set_params()` methods

- [ ] **Run Validation**
  - [ ] In-sample performance calculated
  - [ ] Out-of-sample performance calculated
  - [ ] Regime consistency tested
  - [ ] Parameter sensitivity tested
  - [ ] Transaction cost impact tested
  - [ ] Benchmark comparison done

- [ ] **Review Results**
  - [ ] OOS Sharpe > 0.5
  - [ ] Cost-adjusted Sharpe > 0.3
  - [ ] Regime consistency > 0.6
  - [ ] Parameter robustness > 0.6
  - [ ] Clear economic rationale

- [ ] **Register Strategy**
  - [ ] Added to registry with metadata
  - [ ] Validation result stored
  - [ ] Status updated based on results
  - [ ] Tags added for categorization

---

## Example: Validating a Momentum Strategy

```python
import pandas as pd
import numpy as np
from strategies.validation import (
    StrategyRobustnessValidator,
    ValidationStatus,
    StrategyHypothesis
)
from strategies.registry import StrategyRegistry, StrategyStatus

# 1. Define the hypothesis
momentum_hypothesis = StrategyHypothesis(
    name="cross_sectional_momentum",
    description="Long-short portfolio based on 12-month momentum",
    economic_rationale=(
        "Momentum profits from investor herding behavior and "
        "delayed price discovery. Investors underreact to news "
        "initially, then overreact as prices move significantly."
    ),
    expected_mechanism=(
        "Buy top decile performers from past 12 months (skipping most recent month), "
        "sell bottom decile performers. Rebalance monthly."
    ),
    expected_regimes=["trending_up", "trending_down"],
    risk_factors=[
        "Market reversals cause simultaneous losses on both legs",
        "High turnover increases transaction costs",
        "Small-cap stocks may have liquidity issues",
    ],
    dependencies=["price_data", "market_cap_data"],
    market_inefficiency="Behavioral bias toward extrapolation of recent trends",
    expected_turnover="~50% monthly due to rank changes"
)

# 2. Create and configure strategy
class MomentumStrategy:
    name = "cross_sectional_momentum"
    hypothesis = momentum_hypothesis
    
    def __init__(self, lookback=252, skip=21):
        self.lookback = lookback
        self.skip = skip
    
    def get_params(self):
        return {'lookback': self.lookback, 'skip': self.skip}
    
    def set_params(self, params):
        self.lookback = params.get('lookback', self.lookback)
        self.skip = params.get('skip', self.skip)
    
    def generate_signals(self, data):
        # Implementation here
        returns = data['close'].pct_change(self.lookback).shift(self.skip)
        return returns

strategy = MomentumStrategy(lookback=252, skip=21)

# 3. Prepare data
# In-sample: 2020-2022
# Out-of-sample: 2023-2024
in_sample_data = load_data('2020-01-01', '2022-12-31')
oos_data = load_data('2023-01-01', '2024-12-31')

# 4. Run validation
validator = StrategyRobustnessValidator(config={
    'min_sharpe': 0.5,
    'max_drawdown': 0.25,
    'min_cost_adjusted_sharpe': 0.3,
})

result = validator.validate_strategy(
    strategy=strategy,
    data=in_sample_data,
    oos_data=oos_data,
    transaction_costs=0.001  # 0.1% per trade
)

# 5. Review results
print(f"Validation Status: {result.status.value}")
print(f"Robustness Score: {result.score:.2f}")
print(f"\nKey Metrics:")
print(f"  OOS Sharpe: {result.metrics['oos_sharpe']:.2f}")
print(f"  Cost-Adjusted Sharpe: {result.metrics['cost_adjusted_sharpe']:.2f}")
print(f"  Regime Consistency: {result.metrics['regime_consistency']:.2f}")
print(f"  Parameter Robustness: {result.metrics['param_robustness']:.2f}")

if result.reasons:
    print(f"\nIssues Found:")
    for reason in result.reasons:
        print(f"  - {reason}")

if result.recommendations:
    print(f"\nRecommendations:")
    for rec in result.recommendations:
        print(f"  - {rec}")

# 6. Register strategy
registry = StrategyRegistry()
registry.register(
    MomentumStrategy,
    name="cross_sectional_momentum",
    description="12-month momentum with 1-month skip",
    status=StrategyStatus.EXPERIMENTAL,
    tags=["momentum", "long_short", "equity"],
    version="1.0.0",
    author="Quant Team",
    hypothesis=momentum_hypothesis
)

# 7. Store validation result
registry.set_validation_result("cross_sectional_momentum", result)

# 8. Check if strategy is approved for production
if result.status == ValidationStatus.PASS:
    print("\n✓ Strategy approved for production use")
else:
    print(f"\n✗ Strategy not approved: {result.status.value}")
```

---

## Performance Targets

| Component | Target | Measurement |
|-----------|--------|-------------|
| Validation runtime | < 5 seconds | Per strategy |
| Parameter variations | 5+ | Tested automatically |
| Regime tests | 3+ | Low/normal/high vol |
| Minimum OOS period | 1 year | Separate from training |
| Transaction cost test | 0.1% default | Configurable |

---

## Files Created/Modified

| File | Purpose | Lines |
|------|---------|-------|
| `strategies/validation.py` | Core validation framework | ~720 |
| `strategies/registry.py` | Strategy tracking system | ~465 |
| `scripts/prune_strategies.py` | Automated pruning script | ~270 |
| `docs/STRATEGY_ROBUSTNESS.md` | This documentation | - |

---

## Integration with Existing Systems

### Ensemble Strategy Selector
```python
# Only use ACTIVE strategies in ensemble
active_strategies = registry.get_active_strategies()
strategies_to_use = [
    registry.get_strategy(name)() 
    for name in active_strategies
]
```

### Risk Engine
```python
# Reject strategies with excessive drawdown
validation = registry.get_validation_result(strategy_name)
if validation.metrics['oos_max_drawdown'] > 0.25:
    risk_engine.block_strategy(strategy_name)
```

### Backtesting Pipeline
```python
# Use validated parameters
metadata = registry.get_metadata(strategy_name)
params = metadata.parameters  # Validated parameters
```

---

## Best Practices

### DO
✅ Define clear economic rationale before implementing
✅ Test on truly out-of-sample data
✅ Include realistic transaction costs
✅ Test across multiple market regimes
✅ Document all assumptions and risks
✅ Keep only strategies that add diversification
✅ Re-validate periodically as new data arrives

### DON'T
❌ Add strategies without economic rationale
❌ Optimize parameters on test data
❌ Ignore transaction costs
❌ Keep strategies that only work in one regime
❌ Use data-snooped parameters
❌ Add redundant strategies (same exposure)
❌ Skip validation for "obvious" strategies

---

## Troubleshooting

### "No economic rationale provided"
**Solution:** Define `StrategyHypothesis` with all required fields and attach to strategy.

### "OOS Sharpe below threshold"
**Solution:** Either improve the strategy or accept it has no real edge. Don't curve-fit.

### "Parameter robustness too low"
**Solution:** Strategy may be overfit. Try simpler parameters or regularization.

### "Regime consistency too low"
**Solution:** Add regime filters or reduce position sizing in unfavorable regimes.

### "Cost-adjusted Sharpe too low"
**Solution:** Reduce turnover, optimize execution, or accept smaller position sizes.

---

## Next Steps

After completing Phase 30:

1. **Validate all existing strategies** - Run validation on current strategies
2. **Prune weak strategies** - Remove those that fail validation
3. **Document active strategies** - Ensure all have complete documentation
4. **Set up periodic re-validation** - Schedule regular validation runs
5. **Integrate with CI/CD** - Require validation for new strategies

---

## Summary

Phase 30 transforms the strategy development process from "does it make money in backtest?" to "is this a robust, economically-sound strategy that will work in production?"

Key achievements:
- ✅ Systematic validation framework
- ✅ Centralized strategy registry
- ✅ Automated pruning of weak strategies
- ✅ Clear decision criteria
- ✅ Economic rationale requirement
- ✅ Out-of-sample testing mandate
- ✅ Transaction cost awareness
- ✅ Regime robustness testing

**Quality over quantity.** A few robust strategies beat many fragile ones.
