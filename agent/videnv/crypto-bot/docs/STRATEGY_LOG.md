# Strategy Experiment Log

## Experiment 1: 30-Day MA Backtest (Initial)
- **Data**: First 30 days of BTC/IRT hourly data
- **Strategy**: Moving Average Crossover (fast_ma=5, slow_ma=20)
- **Result**: Initial validation of backtester framework

## Experiment 2: 180-Day Data Collection
- **Data**: Extended to 180 days of BTC/IRT hourly data (data/btcirt_180d.csv)
- **Purpose**: Longer time horizon for more robust strategy testing

## Experiment 3: 180-Day MA Backtest
- **Strategy**: Moving Average Crossover (fast_ma=5, slow_ma=20)
- **Parameters**: commission_pct=0.0025, slippage_pct=0.001, position_size_pct=1.0, initial_capital=10_000_000
- **Result**: Validated backtester on longer dataset

## Experiment 4: Buggy Grid Search (MA Strategy)
- **Issue**: Initial grid search implementation had a mutation bug where input DataFrame was being modified between runs, causing state leakage across parameter combinations
- **Lesson**: Need isolated subprocesses for each parameter combination

## Experiment 5: Fixed Grid Search with Isolated Subprocesses (MA Strategy)
- **Fix**: Each parameter combination run in separate subprocess via `python -c "..."` invoked through Python's subprocess module
- **Result**: Clean, isolated runs with no shared state

---

## Experiment 6: RSI Grid Search (Isolated Subprocesses)

RSI Grid Search Results (all verified via isolated subprocesses AND independently confirmed by direct user execution):

| rsi_period | oversold | overbought | trades | return | win_rate | max_dd | sharpe |
|-----|-----|-----|-----|-----|-----|-----|-----|
| 14 | 20 | 80 | 3 | +0.83% | 66.67% | -27.76% | 0.038 |
| 21 | 30 | 70 | 6 | -14.23% | 66.67% | -30.81% | -0.099 |
| 14 | 25 | 75 | 6 | -17.69% | 66.67% | -33.07% | -0.134 |
| 14 | 30 | 70 | 13 | -26.00% | 61.54% | -35.66% | -0.212 |
| 14 | 35 | 65 | 23 | -33.42% | 52.17% | -38.44% | -0.286 |
| 9 | 30 | 70 | 29 | -37.47% | 48.28% | -43.77% | -0.334 |

**CRITICAL CAVEAT**: The (14,20,80) result is NOT statistically reliable. With only 3 trades, the entire +0.83% return is attributable to a single outlier trade (2026-03-07 to 2026-04-14, +13.47% return over 5 weeks). Removing that one trade would flip the strategy to a loss. This is documented as "not a reliable edge — an artifact of a small sample containing one large winning trade" — not as a validated profitable strategy.

**Sanity Check**: Baseline (14, 30, 70) matches expected 13 trades and -26.00% return exactly.

---

## Experiment 7: Bollinger Bands Strategy

Bollinger Bands Results (window=20, num_std=2.0, verified by direct user execution):
- 39 completed trades, -56.78% return, 33.3% win rate, -59.22% max drawdown — the worst performer of all 4 strategies tested.

---

## Overall Conclusion

Across 4 strategies (MA x2 parameter sets, RSI x6 parameter sets, Bollinger Bands x1) tested on 180 days of BTC/IRT hourly data, no combination showed a statistically reliable edge. 

Project moving into a longer-term research phase without a fixed deadline, focusing next on walk-forward analysis to test parameter robustness across different time periods, rather than single-period backtests which are prone to overfitting.
