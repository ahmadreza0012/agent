# Backtesting Framework

## Philosophy

The backtesting framework is designed for **realistic performance estimation** through:

1. **Walk-Forward Validation**: Multiple train/test splits over time
2. **Transaction Cost Modeling**: Realistic fee and slippage estimation
3. **Liquidity Constraints**: Position size limits based on volume
4. **Drawdown Circuit Breaker**: Automatic risk reduction during losses
5. **Performance Attribution**: Detailed P&L decomposition

---

## Walk-Forward Validation

### Concept

Instead of a single train/test split, walk-forward validation uses rolling windows:

```
Fold 1: [Train─────][Test]
Fold 2:      [Train─────][Test]
Fold 3:           [Train─────][Test]
Fold 4:                [Train─────][Test]
```

### Configuration

```yaml
backtest:
  train_window: 730    # days (2 years)
  test_window: 90      # days (3 months)
  n_folds: 4           # number of walk-forward folds
  gap: 10              # days between train and test (purge)
```

### Implementation

```python
# From backtester.py
class Backtester:
    def __init__(self, 
                 initial_capital: float = 100000,
                 transaction_cost: float = 0.001,
                 slippage: float = 0.0005,
                 max_drawdown_circuit_breaker: float = 0.12,
                 rebalance_frequency_weeks: int = 2):
        """
        Args:
            initial_capital: Starting capital in USD
            transaction_cost: Fee rate per trade
            slippage: Estimated slippage per trade
            max_drawdown_circuit_breaker: Drawdown threshold for auto-derisk
            rebalance_frequency_weeks: How often to rebalance portfolio
        """
```

---

## Data Requirements

### Minimum Data

| Requirement | Value |
|-------------|-------|
| History Length | ≥ 2 years recommended |
| Timeframe | 4h or daily minimum |
| Symbols | At least 3 uncorrelated assets |
| Quality | < 1% missing data points |

### Data Format

```python
# Expected DataFrame format
# Index: DatetimeIndex
# Columns: MultiIndex (symbol, metric)

df.columns = pd.MultiIndex.from_product([
    ['BTC/USDT', 'ETH/USDT'],  # symbols
    ['open', 'high', 'low', 'close', 'volume']  # metrics
])
```

---

## Execution Simulation

### Rebalancing Logic

```python
# Bi-weekly rebalancing (default)
rebalance_days = 14  # Every 2 weeks

# On rebalance day:
# 1. Calculate target weights from strategy
# 2. Check risk limits
# 3. Apply circuit breaker multiplier
# 4. Generate trades to reach target
# 5. Apply transaction costs
# 6. Update positions
```

### Transaction Costs

#### Fee Structure

```python
# Default transaction cost model
cost_model = {
    'fee_maker': 0.0004,    # 0.04% maker fee
    'fee_taker': 0.0010,    # 0.10% taker fee
    'default_spread': 0.0005,  # 0.05% bid-ask spread
    'base_slippage': 0.0005,   # 0.05% base slippage
}
```

#### Cost Calculation

```python
def calculate_transaction_cost(trade_value, adv):
    """Calculate total transaction cost."""
    
    # Base fees
    fee = trade_value * 0.001  # 0.1% taker fee
    
    # Spread cost
    spread = trade_value * 0.0005  # 0.05%
    
    # Market impact (for large orders)
    participation_rate = trade_value / adv
    market_impact = trade_value * 0.01 * participation_rate
    
    return fee + spread + market_impact
```

---

## Slippage Modeling

### Volume-Based Slippage

```python
def calculate_slippage(order_size, daily_volume):
    """Calculate slippage based on order size relative to volume."""
    
    # Participation rate
    participation = order_size / daily_volume
    
    # Slippage increases with participation
    if participation < 0.01:
        slippage_rate = 0.0005  # 0.05% for small orders
    elif participation < 0.05:
        slippage_rate = 0.0010  # 0.10% for medium orders
    else:
        slippage_rate = 0.0020  # 0.20% for large orders
    
    return order_size * slippage_rate
```

---

## Performance Metrics

### Return Metrics

| Metric | Formula | Target |
|--------|---------|--------|
| Total Return | (Final - Initial) / Initial | > 0% |
| Annualized Return | (1 + Total)^(1/Y) - 1 | > 10% |
| Monthly Return (Avg) | Mean of monthly returns | > 0.8% |
| Best Month | Maximum monthly return | - |
| Worst Month | Minimum monthly return | > -10% |

### Risk Metrics

| Metric | Formula | Target |
|--------|---------|--------|
| Volatility | Std(returns) × √252 | < 20% |
| Max Drawdown | Min(cumulative peak - trough) | < 15% |
| Daily VaR (95%) | 5th percentile of daily returns | < 3% |
| CVaR (90%) | Mean of worst 10% days | < 5% |

### Risk-Adjusted Metrics

| Metric | Formula | Target |
|--------|---------|--------|
| Sharpe Ratio | (Return - Rf) / Volatility | > 1.0 |
| Sortino Ratio | (Return - Rf) / Downside Dev | > 1.5 |
| Calmar Ratio | Annual Return / Max DD | > 1.0 |
| Win Rate | Winning days / Total days | > 50% |

---

## Attribution Analysis

### Components

```python
# From performance/attribution.py
class AttributionEngine:
    def decompose_returns(self, weights, returns):
        """Decompose portfolio returns into components."""
        
        # Asset selection effect
        selection = sum(w * r for w, r in zip(weights, returns))
        
        # Allocation effect (vs benchmark)
        allocation = sum((w - w_bench) * r for w, w_bench, r in ...)
        
        # Interaction effect
        interaction = sum((w - w_bench) * (r - r_bench) for ...)
        
        return {
            'selection': selection,
            'allocation': allocation,
            'interaction': interaction,
            'total': selection + allocation + interaction
        }
```

### Output

```
Performance Attribution Report
==============================

Period: 2023-01-01 to 2023-12-31

Portfolio Return:        +15.3%
Benchmark Return:        +8.2%
Active Return:           +7.1%

Attribution:
├── Asset Selection:     +5.2%
├── Allocation Effect:   +1.5%
└── Interaction:         +0.4%

Strategy Contribution:
├── Momentum:           +3.1%
├── Mean Reversion:     +1.8%
├── Risk Parity:        +1.2%
└── ML Signal:          +1.0%
```

---

## Monte Carlo Robustness

### Purpose

Assess whether results are due to skill or luck by simulating alternative paths.

### Method

```python
def monte_carlo_backtest(returns, n_simulations=1000):
    """Run Monte Carlo analysis on backtest results."""
    
    simulated_results = []
    for _ in range(n_simulations):
        # Sample returns randomly with replacement
        sampled = np.random.choice(returns, len(returns), replace=True)
        
        # Calculate metrics
        cum_return = np.cumprod(1 + sampled)[-1] - 1
        max_dd = calculate_max_drawdown(sampled)
        sharpe = sampled.mean() / sampled.std() * np.sqrt(252)
        
        simulated_results.append({
            'return': cum_return,
            'max_drawdown': max_dd,
            'sharpe': sharpe
        })
    
    # Analyze distribution
    return {
        'expected_return': np.mean([r['return'] for r in simulated_results]),
        'probability_positive': np.mean([r['return'] > 0 for r in simulated_results]),
        'probability_target': np.mean([r['return'] > 0.10 for r in simulated_results]),
        'var_95': np.percentile([r['return'] for r in simulated_results], 5)
    }
```

---

## Stress Testing Scenarios

### Built-in Scenarios

| Scenario | Period | Description |
|----------|--------|-------------|
| Crypto Winter | 2022 | Extended bear market |
| COVID Crash | Feb-Apr 2020 | Sharp crash and recovery |
| Bull Run | 2021 | Sustained uptrend |
| High Volatility | Various | Elevated volatility periods |

### Configuration

```yaml
stress_testing:
  enabled: true
  scenarios:
    - name: "crypto_winter"
      start: "2022-01-01"
      end: "2022-12-31"
    - name: "covid_crash"
      start: "2020-02-01"
      end: "2020-04-30"
  
  custom_scenarios:
    - name: "30_percent_drop"
      type: "shock"
      magnitude: -0.30
```

---

## Backtest Configuration

### Example Configuration File

```yaml
# backtest_config.yaml
backtest:
  start_date: "2020-01-01"
  end_date: "2023-12-31"
  
  symbols:
    - BTC/USDT
    - ETH/USDT
    - SOL/USDT
  
  timeframe: "4h"
  
  walk_forward:
    train_days: 730
    test_days: 90
    n_folds: 4
    purge_days: 10
  
  costs:
    maker_fee: 0.0004
    taker_fee: 0.0010
    slippage_model: "volume_based"
  
  constraints:
    max_position: 0.20
    max_exposure: 0.60
    min_liquidity_usd: 1000000
  
  risk:
    max_drawdown: 0.15
    circuit_breaker: true
    derisk_factor: 0.4
  
  rebalance:
    frequency: "biweekly"
    time: "00:00"
```

### Running Backtests

```bash
# Run with default configuration
python run_backtest.py

# Run with custom configuration
python run_backtest.py --config backtest_config.yaml

# Run specific date range
python run_backtest.py --start 2022-01-01 --end 2022-12-31

# Run with specific symbols
python run_backtest.py --symbols BTC/USDT,ETH/USDT
```

---

## Interpreting Results

### Red Flags

⚠️ **Overfitting Indicators**:
- In-sample Sharpe >> Out-of-sample Sharpe
- Performance degrades significantly in later folds
- Strategy works only on specific assets

⚠️ **Data Snooping**:
- Too many strategies tested, only best reported
- Parameters optimized on full dataset
- Look-ahead bias in features

⚠️ **Unrealistic Assumptions**:
- Zero transaction costs
- Perfect execution at close
- No liquidity constraints

### Green Flags

✅ **Robust Performance**:
- Consistent results across folds
- Similar performance on different assets
- Reasonable turnover and costs

✅ **Realistic Modeling**:
- Conservative cost assumptions
- Liquidity constraints applied
- Slippage modeled appropriately

---

## Troubleshooting

### Backtest Shows Extreme Returns

**Problem**: Returns seem too good to be true.

**Checklist**:
1. Verify transaction costs are applied
2. Check for look-ahead bias
3. Ensure no survivorship bias
4. Validate data quality

### Walk-Forward Folds Show Degradation

**Problem**: Later folds perform worse than early folds.

**Possible Causes**:
- Market regime change
- Strategy decay
- Overfitting to early period

**Resolution**:
1. Analyze each fold separately
2. Check for regime适应性
3. Consider adaptive strategies

### High Turnover Warning

**Problem**: Excessive trading causing high costs.

**Solutions**:
1. Increase rebalance frequency (trade less often)
2. Add turnover constraint to optimizer
3. Implement threshold-based rebalancing

---

## Best Practices

1. **Always use walk-forward validation** - Single split is unreliable
2. **Include realistic costs** - Fees + slippage + spread
3. **Test multiple market regimes** - Bull, bear, sideways
4. **Validate on out-of-sample data** - Never optimize on test set
5. **Run Monte Carlo analysis** - Assess statistical significance
6. **Check attribution** - Understand sources of returns
7. **Document all assumptions** - For reproducibility

---

## Version Information

- **Document Version**: 1.0
- **Last Updated**: 2024
- **Phase**: 35 (Documentation)

---

*This document reflects the actual implementation as of Phase 35.*
