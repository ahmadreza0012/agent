# Crypto Portfolio Optimization System - Documentation

## Step 1: Theoretical Foundation

### 1.1 Modern Portfolio Theory (MPT) in Crypto Context

**Markowitz Mean-Variance Optimization:**
```
minimize: w^T Σ w
subject to: w^T μ = μ_target, Σw = 1, w ≥ 0
```

Where:
- `w`: Portfolio weights vector
- `Σ`: Covariance matrix of asset returns
- `μ`: Expected returns vector

For crypto assets, the high volatility and correlation regime shifts make traditional MVO unstable. We address this with:

### 1.2 Black-Litterman Model

Overcomes MVO's sensitivity to input assumptions by combining:
1. **Equilibrium returns** (implied from market caps)
2. **Investor views** (from AI sentiment analysis)

```
E[R_BL] = [(τΣ)^-1 + P^T Ω^-1 P]^-1 [(τΣ)^-1 Π + P^T Ω^-1 Q]
```

Where:
- `Π`: Implied equilibrium returns
- `P`: View matrix
- `Q`: View returns
- `Ω`: View uncertainty
- `τ`: Scaling factor (typically 0.05)

### 1.3 Risk Parity

Equalizes risk contribution from each asset:
```
RC_i = w_i × (Σw)_i / √(w^T Σ w)
Target: RC_i = 1/n for all i
```

Particularly useful for crypto where volatilities differ significantly.

### 1.4 CVaR Optimization

Conditional Value at Risk (Expected Shortfall):
```
CVaR_α = E[L | L ≥ VaR_α]
```

Rockafellar-Uryasev formulation enables convex optimization.

### 1.5 Why 5% Monthly is Challenging

Mathematical reality check:
- 5% monthly = 79.6% annualized ((1.05)^12 - 1)
- Crypto Sharpe ratios typically range 0.3-0.8 in live trading
- To achieve 80% annual return with Sharpe 0.5 requires 160% volatility
- Maximum reasonable crypto portfolio volatility: 40-60%
- **Implies realistic monthly target: 1-3% with 10-20% drawdowns**

---

## Step 2: System Architecture

```
+------------------+     +-------------------+     +---------------------+
|   Data Layer     |     |    AI Layer       |     |   ML Layer          |
|                  |     |                   |     |                     |
| Binance API ---> |---->| News/Sentiment -> |     | Feature Engineering |
| OHLCV Fetch      |     | LLM (Groq)        |---> | XGBoost Forecasts   |
| Price Alignment  |     | Mock Fallback     |     | Return Prediction   |
+------------------+     +-------------------+     +---------------------+
         |                        |                         |
         v                        v                         v
+------------------------------------------------------------------------+
|                      Optimization Layer                                |
|                                                                        |
|  +-------------+  +------------------+  +------------+  +------------+ |
|  | MVO         |  | Black-Litterman  |  | Risk Parity|  | CVaR       | |
|  | Max Sharpe  |  | AI Views         |  | Equal Risk |  | Constraint | |
|  +------+------+  +--------+---------+  +-----+------+  +------+-----+ |
|         |                |                 |                |          |
|         +----------------+-----------------+----------------+          |
|                              |                                         |
|                              v                                         |
|                    +------------------+                                |
|                    | Weight Output    |                                |
|                    +--------+---------+                                |
+-------------------------------------|----------------------------------+
                                      |
                                      v
+------------------------------------------------------------------------+
|                      Backtesting Layer                                 |
|                                                                        |
|  Weekly Rebalancing --> Transaction Costs --> Portfolio Evolution      |
|         |                                          |                   |
|         v                                          v                   |
|  Performance Metrics <-- Drawdown Monitoring <-- VaR/CVaR Calc         |
+------------------------------------------------------------------------+
```

### Module Interactions:

1. **data_fetcher.py**: Fetches 1-year hourly OHLCV from Binance
2. **ai_sentiment.py**: Generates views from sentiment (mock fallback for backtesting)
3. **portfolio_optimizer.py**: Implements MVO, BL, Risk Parity, CVaR
4. **backtester.py**: Event-driven weekly rebalancing with costs
5. **main.py**: Orchestrates full pipeline

---

## Step 3: Code Implementation

Files created in `/workspace`:
- `requirements.txt` - Dependencies
- `data_fetcher.py` - Binance data fetching via ccxt
- `ai_sentiment.py` - AI sentiment with mock fallback
- `portfolio_optimizer.py` - Optimization algorithms
- `backtester.py` - Weekly rebalancing backtester
- `main.py` - Full pipeline orchestrator

---

## Step 4: Execution & Raw Output

### Backtest Configuration:
- **Data**: 1 year hourly (8760 observations)
- **Train/Test Split**: 75%/25% (9 months train, 3 months test)
- **Test Period**: 2026-04-17 to 2026-07-17 (~3 months out-of-sample)
- **Rebalancing**: Weekly (13 rebalances)
- **Transaction Costs**: 0.1% taker + 0.05% slippage
- **Initial Capital**: $100,000

### Raw Results (from console output):

#### Black-Litterman Strategy:
```
Final Value: $80,686.15
Total Return: -19.31%
Monthly Return: -6.81%
Sharpe Ratio: -1.68
Max Drawdown: -29.53%
Transaction Costs: $0.00 (optimizer fell back to equal weight)
```

#### MVO (Mean-Variance) Strategy:
```
Final Value: $94,398.11
Total Return: -5.60%
Monthly Return: -1.88%
Sharpe Ratio: -0.12
Max Drawdown: -27.38%
Transaction Costs: $1,037.20
```

#### Risk Parity Strategy:
```
Final Value: $79,170.42
Total Return: -20.83%
Monthly Return: -7.39%
Sharpe Ratio: -1.82
Max Drawdown: -30.45%
Transaction Costs: $83.06
```

#### CVaR Strategy:
```
Final Value: $80,692.09
Total Return: -19.31%
Monthly Return: -6.81%
Sharpe Ratio: -1.68
Max Drawdown: -29.53%
(Optimizer fell back to equal weight due to numerical issues)
```

---

## Step 5: Final Assessment

### Verdict: ❌ TARGETS NOT ACHIEVED

| Metric | Target | Best Achieved | Status |
|--------|--------|---------------|--------|
| Monthly Return | +5.00% | -1.88% (MVO) | ✗ FAILED |
| Max Drawdown | <15% | 27.38% (MVO) | ✗ FAILED |
| Sharpe Ratio | >1.0 | -0.12 (MVO) | ✗ FAILED |

### Mathematical Explanation for Failure:

1. **Market Regime**: The out-of-sample period (April-July 2026) was a bear/correction phase. All crypto assets showed negative momentum. Long-only portfolios cannot profit in sustained downtrends.

2. **No Short Selling**: Long-only constraints prevent profiting from downtrends. All strategies were forced to hold depreciating assets.

3. **High Correlation**: During stress periods, crypto correlations approach 1, eliminating diversification benefits. When BTC drops 30%, altcoins typically drop 50%+.

4. **Transaction Costs**: MVO incurred $1,037 in costs from high turnover (frequent 100% weight changes). This eroded already-negative returns.

5. **Estimation Error**: Expected returns are notoriously difficult to estimate. Mean-variance optimization amplifies estimation errors, leading to extreme concentrated positions.

6. **Target Unrealistic**: 
   - 5% monthly = 79.6% annualized
   - Even top quant funds (Renaissance, Two Sigma) target 15-30% annually
   - Crypto hedge funds typically target 20-50% annually with 2-3x leverage
   - **Realistic unlevered target: 1-3% monthly with 15-25% drawdowns**

### Why Single-Asset Strategies Also Failed:

The original problem statement noted RSI/MA/XGBoost directional strategies failed due to:
- Transaction costs eroding small edges
- Regime shifts invalidating patterns  
- Market efficiency at hourly frequency

**Portfolio optimization doesn't solve these issues**—it only manages risk across assets. If all assets trend down together, no allocation helps without shorting.

### Concrete Next Steps:

1. **Add Short-Selling Capability**: Enable negative weights to profit from downtrends (requires futures/perpetual swaps).

2. **Regime Detection**: Use HMM or ML to identify bull/bear/sideways regimes:
   - Bull: Risk-on, concentrated positions
   - Bear: Market-neutral, short-biased, or cash
   - Sideways: Mean-reversion strategies

3. **Alternative Alpha Sources**:
   - **Funding Rate Arbitrage**: Capture perp swap funding differentials (market-neutral)
   - **Basis Trading**: Spot-futures basis convergence
   - **Market Making**: Bid-ask spread capture (requires low latency)
   - **Liquidation Hunting**: Front-run predictable liquidation cascades

4. **Leverage Management**: Use modest leverage (2-3x) during favorable conditions to amplify returns.

5. **Tail Risk Hedging**: Buy OTM puts or use options strategies to limit drawdowns.

6. **Reinforcement Learning**: Train RL agent to dynamically allocate based on market state.

7. **Higher Frequency**: Move to 5-15 minute bars for more rebalancing opportunities.

8. **Cross-Exchange Arbitrage**: Price discrepancies between exchanges.

### Realistic Expectations for Production:

| Metric | Conservative | Aggressive |
|--------|--------------|------------|
| Monthly Return | 1-2% | 3-5% |
| Max Drawdown | 10-15% | 20-30% |
| Sharpe Ratio | 0.5-0.8 | 0.8-1.2 |
| Leverage | 1x | 2-3x |

**Recommendation**: Start with Risk Parity + regime detection, add market-neutral arbitrage strategies, then layer on directional alpha with strict risk limits.
