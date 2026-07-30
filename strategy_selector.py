"""
Strategy Selector Module
-------------------------
Implements the "automatically pick the right strategy at the right time,
and self-correct over time" behavior requested.

Design choice (stated explicitly): this is a rolling-performance,
regime-adaptive selector, NOT a full reinforcement-learning agent. It is
transparent, auditable, and cheap to run at every rebalance, which matters
for a system meant to actually be trusted with money. A black-box RL agent
would be harder to justify at a 5%-monthly-return, real-capital target.

How it works:
1. At every rebalance, ALL candidate strategies are evaluated on the most
   recent lookback window (in-sample scoring), producing a Sharpe-like
   score for each.
2. The selector also keeps a rolling ledger of how each strategy actually
   performed the last time it was chosen (out-of-sample, realized) --
   this is the self-correction signal.
3. The next strategy is chosen by combining (a) current in-sample score
   and (b) each strategy's realized track record, so a strategy that
   "looked good" but then performed poorly gets penalized going forward.
4. A simple market-regime tag (trending vs. mean-reverting vs. high-vol)
   is computed and used to bias the choice, since some strategies are
   known to behave differently by regime (e.g. Risk Parity/CVaR tend to
   do better in high-vol regimes than max-Sharpe MVO).
"""

import logging
from collections import defaultdict, deque
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def detect_regime(returns: pd.DataFrame, window: int = 168) -> str:
    """
    Very simple, explainable regime classifier based on realized vol and
    autocorrelation of the (equal-weight) portfolio returns.

    Returns one of: 'trending', 'mean_reverting', 'high_vol'
    """
    if len(returns) < window:
        window = len(returns)
    if window < 5:
        return "mean_reverting"

    port = returns.tail(window).mean(axis=1)
    vol = port.std() * np.sqrt(24 * 365)
    autocorr = port.autocorr(lag=1) if len(port) > 2 else 0.0
    autocorr = 0.0 if pd.isna(autocorr) else autocorr
    
    # Calculate recent return trend
    recent_return = port.tail(window).sum()

    # FIX: Adjusted thresholds for crypto volatility
    if vol > 1.5:  # annualized vol > 150% -> crypto "high vol" regime
        return "high_vol"
    if autocorr > 0.1 or recent_return > 0.1:  # Strong trend or positive momentum
        return "trending"
    return "mean_reverting"


# Which strategies tend to be favored per regime (prior, not gospel --
# combined with the realized track record below).
# FIX: Stronger bias toward Risk Parity in high_vol regimes since it showed better resilience
# Also improved MVO preference in trending markets
REGIME_PRIOR = {
    "trending": {"black_litterman": 1.3, "mvo": 1.4, "ml": 1.1, "risk_parity": 0.9, "cvar": 1.0},
    "mean_reverting": {"black_litterman": 1.1, "ml": 1.0, "risk_parity": 1.2, "mvo": 0.9, "cvar": 1.0},
    "high_vol": {"risk_parity": 1.8, "cvar": 1.5, "black_litterman": 1.0, "mvo": 0.5, "ml": 0.7},
}


class StrategySelector:
    """Tracks realized performance per strategy and picks the best one going forward."""

    def __init__(self, candidate_methods: List[str], track_record_len: int = 12):
        self.candidate_methods = candidate_methods
        self.track_record_len = track_record_len
        # method -> deque of realized Sharpe-like scores from periods it was actually used
        self._track_record: Dict[str, deque] = {m: deque(maxlen=track_record_len) for m in candidate_methods}
        self.history: List[Dict] = []  # audit log of every decision made

    def record_realized_performance(self, method: str, realized_return: float, realized_vol: float):
        """Call this after a rebalance period ends, with what actually happened."""
        score = realized_return / realized_vol if realized_vol > 0 else 0.0
        self._track_record[method].append(score)

    def _track_record_score(self, method: str) -> float:
        rec = self._track_record[method]
        if not rec:
            return 0.0  # neutral prior, no track record yet
        return float(np.mean(rec))

    def select(self, prices: pd.DataFrame, returns: pd.DataFrame,
               in_sample_scores: Dict[str, float], realized_perf: Optional[Dict] = None) -> str:
        """
        Pick the strategy to use for the NEXT period.
        IMPROVED: Now considers realized performance heavily to avoid losing strategies.

        Args:
            prices, returns: recent lookback data (for regime detection)
            in_sample_scores: {method_name: sharpe_like_score} computed on
                the lookback window for each candidate method (higher=better)
            realized_perf: {method: {'return': float, 'vol': float}} from last period

        Returns:
            chosen method name
        """
        regime = detect_regime(returns)
        prior = REGIME_PRIOR.get(regime, {m: 1.0 for m in self.candidate_methods})

        combined = {}
        for m in self.candidate_methods:
            in_sample = in_sample_scores.get(m, 0.0)
            track = self._track_record_score(m)
            regime_mult = prior.get(m, 1.0)
            
            # NEW: If we have realized performance, use it as primary signal
            if realized_perf and m in realized_perf:
                ret = realized_perf[m].get('return', -999)
                vol = realized_perf[m].get('vol', 1.0)
                # Realized Sharpe-like metric (penalize losses heavily)
                realized_score = ret / (vol + 0.01) if vol > 0 else -999
                
                # If strategy lost money, apply VERY heavy penalty (10x)
                if ret < 0:
                    realized_score *= 10.0  # Amplify negative signal strongly
                
                # Weight: 20% in-sample, 80% realized (realized dominates when available)
                combined[m] = (0.2 * in_sample + 0.8 * realized_score) * regime_mult
                logger.info(f"  {m}: in_sample={in_sample:.3f}, realized_ret={ret:.4f}, realized_score={realized_score:.3f}, combined={combined[m]:.3f}")
            else:
                # No realized data yet: use default weighting
                combined[m] = (0.4 * in_sample + 0.6 * track) * regime_mult

        chosen = max(combined, key=combined.get)
        
        # SAFETY: If all scores are negative, force Risk Parity (safest option)
        if all(v < 0 for v in combined.values()):
            if 'risk_parity' in combined:
                chosen = 'risk_parity'
                logger.warning(f"All strategies negative! Forcing risk_parity for safety")
            elif 'cvar' in combined:
                # Second safest option
                chosen = 'cvar'
                logger.warning(f"All strategies negative! Forcing cvar for safety")
        
        self.history.append({
            "regime": regime,
            "scores": combined,
            "chosen": chosen,
        })
        logger.info(f"Regime={regime} | scores={ {k: round(v, 3) for k, v in combined.items()} } | chosen={chosen}")
        return chosen


def compute_in_sample_scores(candidate_methods: List[str], strategy_fns: Dict[str, Callable],
                              prices: pd.DataFrame, returns: pd.DataFrame) -> Dict[str, float]:
    """
    Score each candidate strategy on the lookback window by computing the
    Sharpe ratio the resulting weights WOULD have achieved on that same
    window (in-sample). This is only used as one signal among several in
    StrategySelector.select, precisely because in-sample scores overstate
    quality -- the realized track record term corrects for that over time.
    """
    scores = {}
    for method in candidate_methods:
        try:
            weights = strategy_fns[method](prices, returns)
            port_ret = returns.values @ np.array(weights)
            mean_r = port_ret.mean() * 24 * 365
            vol_r = port_ret.std() * np.sqrt(24 * 365)
            scores[method] = (mean_r - 0.02) / vol_r if vol_r > 0 else 0.0
        except Exception as e:
            logger.warning(f"In-sample scoring failed for {method}: {e}")
            scores[method] = -999.0
    return scores


def main():
    """Offline self-test with synthetic data (no network needed)."""
    np.random.seed(0)
    dates = pd.date_range("2024-01-01", periods=500, freq="h")
    returns = pd.DataFrame(np.random.randn(500, 4) * 0.01, index=dates,
                            columns=["BTC", "ETH", "SOL", "BNB"])
    prices = (1 + returns).cumprod() * 100

    methods = ["mvo", "risk_parity", "cvar", "black_litterman"]
    selector = StrategySelector(methods)

    regime = detect_regime(returns)
    print("Detected regime:", regime)

    fake_in_sample = {"mvo": 0.5, "risk_parity": 0.3, "cvar": 0.4, "black_litterman": 0.6}
    chosen = selector.select(prices, returns, fake_in_sample)
    print("Chosen strategy:", chosen)

    # simulate a bad realized outcome for the chosen strategy -> should be
    # penalized next time even if in-sample score stays high
    selector.record_realized_performance(chosen, realized_return=-0.05, realized_vol=0.2)
    chosen2 = selector.select(prices, returns, fake_in_sample)
    print("Chosen strategy after a bad realized outcome:", chosen2)


if __name__ == "__main__":
    main()
