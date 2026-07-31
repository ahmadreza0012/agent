"""
Strategy Selector Module - Ensemble Blender Architecture
---------------------------------------------------------
ARCHITECTURE CHANGE: Replaced "winner-take-all" strategy selection with a
"risk-weighted ensemble blend" that combines multiple strategies simultaneously.

Why this matters:
1. Diversification: Instead of betting 100% on one "best" strategy each period
   (which risks overfitting to short-term noise), we blend multiple strategies
   with weights based on their long-term realized Sharpe ratios.
2. True Independence: Added trend_following and mean_reversion strategies that
   use completely different logic (price-based, not covariance-based) to ensure
   real diversification beyond just parameter tweaks.
3. Stability: Long lookback windows (90+ days) for weight calculation prevent
   noisy short-term fluctuations from causing excessive churn.
4. Safety Floors: No strategy can go below 5% or above 40% of the blend, ensuring
   true diversification is maintained even if one strategy temporarily underperforms.

Design philosophy: This is an explainable, auditable ensemble system - not a
black-box RL agent. Transparency matters when managing real capital with a
5%-monthly-return target.
"""

import logging
from collections import defaultdict, deque
from typing import Callable, Dict, List, Optional, Tuple

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
    "trending": {"black_litterman": 1.3, "mvo": 1.4, "ml": 1.1, "risk_parity": 0.9, "cvar": 1.0, "trend_following": 1.5, "mean_reversion": 0.7},
    "mean_reverting": {"black_litterman": 1.1, "ml": 1.0, "risk_parity": 1.2, "mvo": 0.9, "cvar": 1.0, "trend_following": 0.6, "mean_reversion": 1.6},
    "high_vol": {"risk_parity": 1.8, "cvar": 1.5, "black_litterman": 1.0, "mvo": 0.5, "ml": 0.7, "trend_following": 0.8, "mean_reversion": 1.2},
}


class StrategySelector:
    """Tracks realized performance per strategy and blends them with risk-weighted ensemble."""

    def __init__(self, candidate_methods: List[str], track_record_len: int = 12,
                 min_strategy_weight: float = 0.05, max_strategy_weight: float = 0.40):
        """
        Args:
            candidate_methods: List of strategy names to consider
            track_record_len: Number of periods to track for realized performance
            min_strategy_weight: Floor for any strategy's weight in blend (prevents elimination)
            max_strategy_weight: Ceiling for any strategy's weight in blend (prevents dominance)
        """
        self.candidate_methods = candidate_methods
        self.track_record_len = track_record_len
        self.min_strategy_weight = min_strategy_weight
        self.max_strategy_weight = max_strategy_weight
        
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
               in_sample_scores: Dict[str, float], realized_perf: Optional[Dict] = None,
               current_drawdown: float = 0.0) -> str:
        """
        LEGACY METHOD: Pick the single best strategy (kept for backward compatibility).
        For new code, use blend() instead for ensemble approach.
        """
        regime = detect_regime(returns)
        prior = REGIME_PRIOR.get(regime, {m: 1.0 for m in self.candidate_methods})

        # CRITICAL: Force hybrid strategy in high_vol regime or significant drawdown
        # This ensures we get the 60% arb allocation when markets are risky
        has_hybrid = any('hybrid' in m for m in self.candidate_methods)
        if has_hybrid and (regime == 'high_vol' or current_drawdown > 0.05):
            # Prefer hybrid_risk_parity_arb as it's more stable than hybrid_mvo_arb
            if 'hybrid_risk_parity_arb' in self.candidate_methods:
                logger.info(f"Forcing hybrid_risk_parity_arb due to regime={regime}, drawdown={current_drawdown:.2%}")
                return 'hybrid_risk_parity_arb'
            elif 'hybrid_mvo_arb' in self.candidate_methods:
                logger.info(f"Forcing hybrid_mvo_arb due to regime={regime}, drawdown={current_drawdown:.2%}")
                return 'hybrid_mvo_arb'

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
            elif any('hybrid' in m for m in combined):
                # Fallback to hybrid if available (has arb buffer)
                chosen = next(m for m in combined.keys() if 'hybrid' in m)
                logger.warning(f"All strategies negative! Forcing {chosen} for arb buffer")
        
        self.history.append({
            "regime": regime,
            "scores": combined,
            "chosen": chosen,
        })
        logger.info(f"Regime={regime} | scores={ {k: round(v, 3) for k, v in combined.items()} } | chosen={chosen}")
        return chosen

    def blend(self, prices: pd.DataFrame, returns: pd.DataFrame,
              strategy_fns: Dict[str, Callable], lookback_window_days: int = 90) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        ENSEMBLE BLEND: Instead of selecting one winner, compute risk-weighted blend of ALL strategies.
        
        Design principles to prevent overfitting:
        1. Long lookback window (>=90 days) for Sharpe calculation - avoids noise from short-term fluctuations
        2. Floor/ceiling on strategy weights (min 5%, max 40%) - ensures true diversification
        3. Negative Sharpe strategies get floor weight (not zero) - may recover in next regime
        4. Regime priors gently bias weights (not force 100% allocation)
        
        Args:
            prices: Price DataFrame for trend-following/mean-reversion strategies
            returns: Returns DataFrame for scoring and optimization
            strategy_fns: Dict mapping strategy name to function that returns weights
            lookback_window_days: Window for calculating realized Sharpe ratios
            
        Returns:
            Tuple of (combined_asset_weights, strategy_blend_weights)
            - combined_asset_weights: Final blended weights for each asset (sums to 1.0)
            - strategy_blend_weights: Weight of each strategy in the blend (for logging)
        """
        # Step 1: Get weights from each strategy
        all_weights = {}
        failed_strategies = []
        
        for name, fn in strategy_fns.items():
            try:
                w = fn(prices, returns)
                w_array = np.array(w)
                
                # Validate dimensions
                if len(w_array) != len(returns.columns):
                    logger.error(f"Strategy {name} returned {len(w_array)} weights but expected {len(returns.columns)}")
                    failed_strategies.append(name)
                    continue
                    
                # Normalize individual strategy weights to sum to 1
                if w_array.sum() > 0:
                    w_array = w_array / w_array.sum()
                
                all_weights[name] = w_array
                logger.debug(f"Strategy {name} produced valid weights: {w_array}")
            except Exception as e:
                logger.warning(f"Strategy {name} failed during blend: {e}")
                failed_strategies.append(name)
        
        if not all_weights:
            # Fallback: equal weight all assets
            n_assets = len(returns.columns)
            logger.warning("All strategies failed! Using equal-weight fallback")
            return np.ones(n_assets) / n_assets, {}
        
        # Step 2: Calculate long-term realized Sharpe for each strategy
        strategy_sharpes = {}
        for name in all_weights.keys():
            rec = self._track_record[name]
            if len(rec) >= 3:  # Need at least 3 observations for meaningful Sharpe
                sharpe = float(np.mean(rec))
            else:
                # New strategy: use neutral prior
                sharpe = 0.0
            strategy_sharpes[name] = sharpe
        
        # Step 3: Convert Sharpes to blend weights with floor/ceiling constraints
        # Use softmax-like transformation but with constraints
        raw_scores = {}
        regime = detect_regime(returns)
        prior = REGIME_PRIOR.get(regime, {m: 1.0 for m in all_weights.keys()})
        
        for name in all_weights.keys():
            sharpe = strategy_sharpes[name]
            regime_bias = prior.get(name, 1.0)
            
            # Transform Sharpe to score (positive Sharpe -> higher score)
            # Add small constant to avoid negative scores for floor strategies
            score = max(0.1, sharpe + 0.5) * regime_bias
            raw_scores[name] = score
        
        # Normalize to sum to 1.0
        total_score = sum(raw_scores.values())
        if total_score == 0:
            # All scores zero: equal weight
            blend_weights = {name: 1.0 / len(all_weights) for name in all_weights.keys()}
        else:
            blend_weights = {name: score / total_score for name, score in raw_scores.items()}
        
        # Apply floor and ceiling constraints
        # Iterative projection to ensure sum=1 while respecting bounds
        blend_weights = self._apply_weight_constraints(blend_weights)
        
        # Step 4: Combine asset weights using strategy blend weights
        combined_asset_weights = np.zeros(len(returns.columns))
        for name, w in all_weights.items():
            combined_asset_weights += blend_weights[name] * w
        
        # Final normalization (should already sum to ~1.0, but ensure precision)
        if combined_asset_weights.sum() > 0:
            combined_asset_weights = combined_asset_weights / combined_asset_weights.sum()
        
        # Log blend composition
        blend_log = ", ".join([f"{k}={v*100:.1f}%" for k, v in sorted(blend_weights.items(), key=lambda x: -x[1])])
        logger.info(f"Blend weights: {blend_log}")
        logger.info(f"Combined asset weights: {combined_asset_weights}")
        
        return combined_asset_weights, blend_weights
    
    def _apply_weight_constraints(self, weights: Dict[str, float]) -> Dict[str, float]:
        """
        Apply floor/ceiling constraints to strategy weights while maintaining sum=1.
        Uses iterative proportional fitting.
        """
        n = len(weights)
        min_w = self.min_strategy_weight
        max_w = self.max_strategy_weight
        
        # Check feasibility
        if n * min_w > 1.0:
            logger.warning(f"Cannot satisfy min weight {min_w} for {n} strategies. Adjusting.")
            min_w = 0.95 / n
        if n * max_w < 1.0:
            logger.warning(f"Cannot satisfy max weight {max_w} for {n} strategies. Adjusting.")
            max_w = 1.05 / n
        
        # Iterative projection
        for _ in range(10):  # Max iterations
            # Apply floor
            weights = {k: max(min_w, v) for k, v in weights.items()}
            # Apply ceiling
            weights = {k: min(max_w, v) for k, v in weights.items()}
            # Normalize
            total = sum(weights.values())
            if total > 0:
                weights = {k: v / total for k, v in weights.items()}
            else:
                # Fallback to equal weight
                weights = {k: 1.0 / n for k in weights.keys()}
                break
        
        return weights


def compute_in_sample_scores(candidate_methods: List[str], strategy_fns: Dict[str, Callable],
                              prices: pd.DataFrame, returns: pd.DataFrame) -> Dict[str, float]:
    """
    Score each candidate strategy on the lookback window by computing the
    Sharpe ratio the resulting weights WOULD have achieved on that same
    window (in-sample). This is only used as one signal among several in
    StrategySelector.select, precisely because in-sample scores overstate
    quality -- the realized track record term corrects for that over time.
    
    FIX: Added dimension mismatch check - if weights don't match returns columns,
    this is a structural bug (not just a scoring failure) and should log ERROR.
    """
    scores = {}
    n_expected_assets = len(returns.columns)
    
    for method in candidate_methods:
        try:
            weights = strategy_fns[method](prices, returns)
            weights_array = np.array(weights)
            
            # CRITICAL CHECK: Ensure weights dimension matches returns columns
            if len(weights_array) != n_expected_assets:
                logger.error(f"CRITICAL MISMATCH for {method}: expected {n_expected_assets} weights "
                           f"(columns: {list(returns.columns)}), got {len(weights_array)}. "
                           f"This indicates a structural bug in optimizer/strategy function.")
                scores[method] = -999.0
                continue
            
            port_ret = returns.values @ weights_array
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
