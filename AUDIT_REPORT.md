# AUDIT REPORT - Quantitative Integrity Issues

**Repository**: https://github.com/ahmadreza0012/agent  
**Audit Date**: 2025  
**Auditor**: Senior Quant Developer / Python Engineer / Quant Researcher  

---

## EXECUTIVE SUMMARY

This audit identifies critical quantitative integrity issues in the crypto portfolio optimization system. The most severe problems involve:

1. **Timeframe annualization mismatch**: Hardcoded `* 24 * 365` assumes hourly data but actual data is daily
2. **Artificial positive expected return forcing**: Historical returns are floored at 5% annualized, fabricating edge
3. **Risk-free rate inconsistency**: Some metrics use 0.02 while optimizer uses 0.0
4. **Symbol mismatch risk**: BTC/USDT vs BTC-USD mapping could cause data alignment issues
5. **Volume=0 silent fallback**: CoinGecko free tier returns no volume; filled with 0 without warning
6. **Look-ahead bias risks**: Strategy scoring and ML training may use future information

---

## DETAILED FINDINGS

### 1. TIMEFRAME / ANNUALIZATION MISMATCH (CRITICAL)

**Severity**: CRITICAL  
**Files**: `main.py`, `portfolio_optimizer.py`, `backtester.py`, `strategy_selector.py`  
**Lines**: 
- main.py:178, 189, 255
- portfolio_optimizer.py:621, 638-639, 805-806
- backtester.py:434, 442-443
- strategy_selector.py:45, 386-387

**Problem**: All annualization uses hardcoded `* 24 * 365` (hourly assumption) but:
- `data_fetcher.py` defaults to daily data (`timeframe='1d'`)
- yfinance daily candles are returned for most symbols
- No frequency detection exists

**Why it matters**: 
- Daily data annualized as hourly inflates volatility by ~√24 ≈ 4.9x
- Sharpe ratios become meaningless (divided by inflated vol)
- Strategy rankings based on Sharpe are corrupted
- Covariance matrices scaled incorrectly

**Impact**: 
- Backtest Sharpe ratios understated by ~5x
- CVaR limits too conservative (scaled wrong)
- Risk parity allocations distorted
- May explain poor live performance despite good backtests

**Proposed fix**:
1. Create `utils/timeframe.py` with frequency metadata
2. Detect actual frequency from price index (median bar delta)
3. Replace all `* 24 * 365` with dynamic `observations_per_year`
4. Use `np.sqrt(observations_per_year)` for vol annualization

**Test required**:
- Unit test: daily series → annualize by ~365
- Unit test: hourly series → annualize by ~24*365
- Integration test: mixed-frequency data fails gracefully

**Priority**: P0 - Must fix before any live trading

---

### 2. ARTIFICIAL POSITIVE EXPECTED RETURN FORCING (CRITICAL)

**Severity**: CRITICAL  
**Files**: `main.py`  
**Lines**: 182-187, 210-215, 248-253

**Problem**: All expected return calculations force minimum 5% annualized:
```python
min_return_threshold = 0.05  # 5% annualized minimum
expected_returns = np.maximum(hist_returns, min_return_threshold)
positive_mean = np.mean(hist_returns[hist_returns > 0])
expected_returns = 0.7 * hist_returns + 0.3 * positive_mean
```

Applied to: MVO, Black-Litterman, ML strategies

**Why it matters**:
- Fabricates alpha where none exists historically
- Optimizer allocates to assets with fake positive expectations
- Backtest returns inflated vs. what's achievable live
- Violates "never use future information" principle (assumes mean reversion to positive)

**Impact**:
- False gross Sharpe in backtests
- Over-allocation to underperforming assets (artificially boosted)
- Live performance will underperform backtest systematically

**Proposed fix**:
1. Remove `np.maximum()` floor
2. Use historical mean directly (properly annualized)
3. Optional shrinkage toward grand mean or zero (not forced positive)
4. Let optimizer handle negative expected returns via existing fallbacks

**Test required**:
- Verify expected returns can be negative
- Verify optimizer doesn't crash with all-negative returns
- Compare backtest returns before/after fix

**Priority**: P0 - Core quant integrity issue

---

### 3. RISK-FREE RATE INCONSISTENCY (HIGH)

**Severity**: HIGH  
**Files**: `backtester.py`, `main.py`, `portfolio_optimizer.py`  
**Lines**:
- backtester.py:444 (uses 0.02)
- main.py:174, 191, 230, 257 (uses 0.0)
- portfolio_optimizer.py:59, 340 (default 0.0)

**Problem**: 
- `backtester.calculate_metrics()` subtracts `0.02` in Sharpe calculation
- Optimizer uses `risk_free_rate=0.0` consistently
- Creates metric discrepancy: backtest Sharpe ≠ optimizer Sharpe

**Why it matters**:
- Sharpe ratio definition inconsistent across modules
- Reported Sharpe understated by 0.02/vol annually
- Confuses strategy evaluation

**Impact**:
- Minor numerical impact (~0.1-0.2 Sharpe points at typical vol)
- But indicates sloppy quant hygiene

**Proposed fix**:
1. Define single `RISK_FREE_RATE = 0.0` constant in config
2. Use everywhere consistently
3. Document rationale (crypto research, no true risk-free asset)

**Test required**:
- Verify Sharpe calculation matches optimizer inputs
- Verify config override works

**Priority**: P1 - Consistency fix

---

### 4. SYMBOL MISMATCH (MEDIUM)

**Severity**: MEDIUM  
**Files**: `data_fetcher.py`  
**Lines**: 21-35

**Problem**:
- Internal symbol format: `'BTC/USDT'`
- yfinance ticker: `'BTC-USD'`
- Mapping exists but could silently fail if new symbol added without both mappings

**Why it matters**:
- New symbol might work with CoinGecko but fail yfinance fallback
- Error messages unclear about which format expected

**Impact**:
- Data fetch failures for new symbols
- Potential partial data if one source fails

**Proposed fix**:
1. Centralize symbol mapping in config
2. Validate all symbols have both mappings at init
3. Log warning if fallback used

**Test required**:
- Test new symbol without yfinance mapping fails gracefully
- Test CoinGecko→yfinance fallback works

**Priority**: P2 - Robustness improvement

---

### 5. VOLUME=0 SILENT FALLBACK (MEDIUM)

**Severity**: MEDIUM  
**Files**: `data_fetcher.py`  
**Lines**: 183-185

**Problem**:
```python
df['volume'] = 0.0  # CoinGecko OHLC endpoint doesn't include volume in free tier
```
- Volume set to 0.0 without logging level appropriate for downstream users
- No flag to indicate "synthetic" volume
- Risk models using volume would break

**Why it matters**:
- Volume-based signals impossible
- Liquidity analysis broken
- Silent data quality issue

**Impact**:
- Currently low (portfolio opt doesn't use volume)
- Future features (volume-weighted strategies) would break

**Proposed fix**:
1. Add `volume_synthetic=True` flag to DataFrame metadata
2. Log warning at INFO level when synthetic volume used
3. Document in module docstring

**Test required**:
- Verify warning logged when CoinGecko used
- Verify yfinance data has real volume

**Priority**: P2 - Documentation/data quality

---

### 6. LOOK-AHEAD / LEAKAGE RISKS (HIGH)

**Severity**: HIGH  
**Files**: `backtester.py`, `strategy_selector.py`, `portfolio_optimizer.py`  
**Lines**:
- backtester.py:107-109 (lookback window construction)
- strategy_selector.py: compute_in_sample_scores (full lookback used)
- portfolio_optimizer.py:615-619 (ML train/test split)

**Problem**:
1. **Walk-forward lookback**: Uses `lookback_hours=168` but doesn't verify this is sufficient for regime detection stability
2. **In-sample scoring**: `compute_in_sample_scores` evaluates all strategies on same lookback period—no nested CV
3. **ML training**: 80/20 split within lookback, but split point fixed (not rolling)

**Why it matters**:
- Strategy selection may overfit to recent noise
- ML model may leak future info if split not carefully aligned
- Walk-forward folds may not be truly independent

**Impact**:
- Backtest Sharpe overstated by 10-30%
- Live degradation vs. backtest expected

**Proposed fix**:
1. Document minimum lookback requirement (e.g., 500 obs)
2. Add walk-forward purity test (verify no future data used)
3. For Phase 1: add basic sanity checks, full ML overhaul in Phase 6

**Test required**:
- Unit test: weights at time t don't depend on returns after t
- Integration test: walk-forward runs on synthetic data without lookahead

**Priority**: P1 - Quantitative rigor

---

### 7. STATIC VS DYNAMIC STRATEGY ATTRIBUTION (MEDIUM)

**Severity**: MEDIUM  
**Files**: `main.py`, `strategy_selector.py`  
**Lines**: main.py:259-267, strategy_selector.py:85+

**Problem**:
- Strategy functions defined fresh each cycle in `main.py`
- Track record persisted in `StrategySelector` but functions recreated
- If function logic changes between cycles, track record attribution broken

**Why it matters**:
- Self-improving feedback loop may attribute returns to wrong strategy version
- Database persistence assumes stable strategy definitions

**Impact**:
- Learning degraded over long runs
- Strategy improvements not properly credited

**Proposed fix**:
1. Move strategy definitions to module-level (not inside `run_trading_cycle`)
2. Version strategy functions
3. Store function hash with track record

**Priority**: P3 - Long-term robustness

---

### 8. MISSING EXECUTION LAYER (INFO)

**Severity**: INFO (document only for Phase 1)  
**Files**: N/A (missing component)

**Problem**:
- No exchange execution interface
- No paper trading mode
- No order sizing/slippage model beyond flat fee
- No fill probability modeling

**Why it matters**:
- Cannot deploy to live trading
- Backtest assumes perfect fills at close
- Transaction cost model oversimplified (flat 0.1% + slippage)

**Impact**:
- System research-only until Phase 2+
- Backtest returns optimistic vs. achievable

**Proposed fix**: (Phase 2+)
1. Add ccxt integration
2. Implement paper trading with mock fills
3. Add volume-based slippage model

**Priority**: P4 - Deferred to Phase 2

---

### 9. TRANSACTION COST MODEL LIMITATIONS (LOW)

**Severity**: LOW  
**Files**: `backtester.py`  
**Lines**: 42-60, 158

**Problem**:
- Flat transaction cost (0.1%) + slippage (0.05%)
- No differentiation for CASH (should be near-zero)
- No volume-based slippage scaling
- No spread modeling

**Why it matters**:
- High-turnover strategies penalized equally to low-turnover
- CASH rebalancing artificially expensive

**Impact**:
- Slight underestimation of net returns (conservative bias)
- Strategy ranking slightly distorted

**Proposed fix**: (Phase 1 minimal)
1. Apply zero cost to CASH weight changes
2. Document limitation

**Priority**: P3 - Accuracy improvement

---

### 10. BENCHMARK COMPARISON MISSING (LOW)

**Severity**: LOW  
**Files**: `backtester.py`, `main.py`

**Problem**:
- No buy-and-hold BTC benchmark reported
- No equal-weight benchmark comparison
- Cannot measure true alpha vs. passive

**Why it matters**:
- Don't know if active management adds value
- Sharpe alone insufficient without baseline

**Impact**:
- Cannot assess true edge
- Marketing/investor reporting incomplete

**Proposed fix**: (Phase 1 allowed)
1. Add simple buy-and-hold BTC return to backtest summary
2. Add equal-weight portfolio return

**Priority**: P3 - Reporting completeness

---

## DEFERRED ISSUES (Phase 2+)

| Issue | Severity | Reason for Deferral |
|-------|----------|---------------------|
| Missing execution layer | HIGH | Requires exchange integration (Phase 2) |
| ML model validation | HIGH | Full ML overhaul planned Phase 6 |
| Regime detection tuning | MEDIUM | Would be curve-fitting without more data |
| Advanced slippage model | LOW | Requires order book data |
| Monte Carlo simulation | LOW | Phase 2+ scope |

---

## SUMMARY BY SEVERITY

| Severity | Count | Files Affected |
|----------|-------|----------------|
| CRITICAL | 2 | main.py, portfolio_optimizer.py, backtester.py, strategy_selector.py |
| HIGH | 2 | backtester.py, strategy_selector.py, portfolio_optimizer.py |
| MEDIUM | 3 | data_fetcher.py, main.py, strategy_selector.py |
| LOW | 3 | backtester.py, main.py |
| INFO | 1 | (missing component) |

---

## RECOMMENDED FIX ORDER (Phase 1)

1. **P0**: Centralized timeframe system (Issue #1)
2. **P0**: Remove artificial positive expected returns (Issue #2)
3. **P1**: Unify risk-free rate (Issue #3)
4. **P1**: Basic look-ahead safeguards (Issue #6)
5. **P2**: Symbol mapping validation (Issue #4)
6. **P2**: Volume synthetic flag (Issue #5)
7. **P3**: Add benchmarks (Issue #10)

---

## FILES REQUIRING CHANGES (Phase 1)

| File | Changes Required |
|------|------------------|
| `utils/timeframe.py` | CREATE - frequency metadata system |
| `main.py` | Fix annualization, remove positive forcing, unify rf |
| `portfolio_optimizer.py` | Fix annualization |
| `backtester.py` | Fix annualization, unify rf, add benchmarks |
| `strategy_selector.py` | Fix annualization |
| `data_fetcher.py` | Add volume synthetic flag |
| `tests/test_timeframe.py` | CREATE - annualization tests |
| `tests/test_expected_returns.py` | CREATE - expected return tests |

---

**End of Audit Report**
