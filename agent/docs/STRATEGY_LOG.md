# Strategy Experiment Log

## Experiment 1: 30-Day MA Backtest (Initial)
- **Data**: First 30 days of BTC/IRT hourly data
- **Strategy**: Moving Average Crossover (short_window=10, long_window=30)
- **Result**: 15 trades, total return -13.35%, win rate 20%, max drawdown -14.79%
- **Status**: ✅ Reliable (single clean run, later methodology confirmed correct)

## Experiment 2: 180-Day Data Collection
- **Data**: Extended to 180 days of BTC/IRT hourly data via paginated collector (data/btcirt_180d.csv), 4,320 hourly candles, 2026-01-13 to 2026-07-12

## Experiment 3: 180-Day MA Backtest
- **Strategy**: Moving Average Crossover (short_window=10, long_window=30)
- **Parameters**: commission_pct=0.0025, slippage_pct=0.001, position_size_pct=1.0, initial_capital=10,000,000
- **Result**: 84 trades, total return -34.46%, win rate 25.0%, max drawdown -42.11%, Sharpe -0.380
- **Status**: ✅ Confirmed independently by direct user execution (matched twice)

## Experiment 3b: 180-Day MA Backtest, alternate window (9, 21)
- **Result**: 116 trades, total return -45.13%, win rate 24.1%, max drawdown -50.81%, Sharpe -0.540
- **Status**: ✅ Confirmed independently by direct user execution

## Experiment 4: Buggy Grid Search (MA Strategy)
- **Issue**: Grid search loop shared a single mutable DataFrame across iterations; apply_moving_average_strategy lacked `df = df.copy()`, so signals from earlier iterations leaked into later ones, inflating trade counts (e.g. reported 137 trades for (9,21) instead of the correct 116).
- **Lesson**: Always copy input DataFrames inside strategy functions, and/or isolate each run in a separate subprocess.

## Experiment 5: Fixed Grid Search with Isolated Subprocesses
- **Fix**: Each parameter combination run in a separate subprocess via `python -c "..."` invoked through Python's subprocess module.
- **Result**: Clean, isolated runs with no shared state; results for MA matched direct standalone runs.

---

## Experiment 6: RSI Strategy

- **Baseline** (rsi_period=14, oversold=30, overbought=70): 13 trades, total return -26.00%, win rate 61.5%, max drawdown -35.66%, Sharpe -0.212
- **Status**: ✅ Confirmed independently by direct user execution

### RSI Grid Search Results (isolated subprocesses, sanity-checked against baseline)

| rsi_period | oversold | overbought | trades | return | win_rate | max_dd | sharpe |
|-----|-----|-----|-----|-----|-----|-----|-----|
| 14 | 20 | 80 | 3 | +0.83% | 66.67% | -27.76% | 0.038 |
| 21 | 30 | 70 | 6 | -14.23% | 66.67% | -30.81% | -0.099 |
| 14 | 25 | 75 | 6 | -17.69% | 66.67% | -33.07% | -0.134 |
| 14 | 30 | 70 | 13 | -26.00% | 61.54% | -35.66% | -0.212 |
| 14 | 35 | 65 | 23 | -33.42% | 52.17% | -38.44% | -0.286 |
| 9 | 30 | 70 | 29 | -37.47% | 48.28% | -43.77% | -0.334 |

**CRITICAL CAVEAT**: The (14,20,80) result is **NOT statistically reliable**. With only 3 trades, the entire +0.83% return is attributable to a single outlier trade (2026-03-07 to 2026-04-14, +13.47% return over 5 weeks). Removing that one trade would flip the strategy to a loss. This is documented as "not a reliable edge — an artifact of a small sample containing one large winning trade," not a validated profitable strategy.

**Sanity Check**: Baseline (14, 30, 70) matches the independently confirmed 13 trades and -26.00% return exactly.

---

## Experiment 7: Bollinger Bands Strategy

- **Parameters**: window=20, num_std=2.0
- **Result**: 39 trades, total return -56.78%, win rate 33.3%, max drawdown -59.22%, Sharpe -0.624
- **Status**: ✅ Confirmed by direct user execution
- Worst performer of all 4 strategies tested.

---

## Overall Conclusion (as of this log entry)

Across 4 strategies (MA with two parameter sets, RSI with six parameter sets, Bollinger Bands with one parameter set) tested on 180 days of BTC/IRT hourly data, **no combination showed a statistically reliable profitable edge**. The one nominally positive result (RSI 14/20/80, +0.83%) is not robust — it depends entirely on a single large trade in a 3-trade sample.

Project is moving into a longer-term research phase without a fixed deadline. Next planned step: walk-forward analysis, to test whether any parameter set that looks good on one time window continues to perform on a separate, later time window — this is a stronger test of robustness than a single full-period backtest, which is prone to overfitting.