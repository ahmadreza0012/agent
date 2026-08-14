"""
Strategy Selector Module - Ensemble Blender Architecture with Regime-Driven Defensive Weighting
----------------------------------------------------------------------------------------------
STAGE 2 IMPROVEMENTS:
- Aggressive regime detection: high_vol and non-trending/bearish = defensive mode
- Forced 60-70% allocation to Trend-Following + CVaR + CASH in bad markets
- Trend-Following gets 80%+ CASH when no uptrends (strongest defense)
- Aggressive strategies (ML, pure MVO) get very low weight in high-vol regimes
- Sentiment impact: affects final weights of Trend-Following and Mean-Reversion (not just BL)

STAGE 3 IMPROVEMENTS:
- Negative Sharpe strategies reduce weight 2x faster (from 12 to 6 periods)
- Exponential transform for Sharpe scoring (better ranking)
- Floor/ceiling on strategy weights (5%-40%) maintains true diversification

STAGE 4 IMPROVEMENTS:
- Sentiment scores now multiply final weights of Trend-Following and Mean-Reversion
- Strongly negative sentiment = -50% weight reduction for trend strategies
"""

import logging
from collections import defaultdict, deque
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def detect_regime(returns: pd.DataFrame, window: int = 168, freq=None) -> str:
    """
    Aggressive regime classifier for crypto market conditions.
    
    STAGE 2 FIX: Enhanced thresholds for crypto volatility
    Returns one of: 'trending', 'mean_reverting', 'high_vol'
    
    PHASE 1 FIX: Accepts optional FrequencySpec for correct vol annualization.
    If freq is None, attempts to auto-detect from returns index.
    """
    if len(returns) < window:
        window = len(returns)
    if window < 5:
        return "mean_reverting"

    port = returns.tail(window).mean(axis=1)
    
    # PHASE 1 FIX: Use detected frequency for vol annualization
    if freq is None:
        # Auto-detect frequency from returns index
        try:
            from utils.timeframe import detect_frequency as detect_freq
            freq = detect_freq(returns)
        except Exception:
            # Fallback to hourly assumption with warning
            logger.warning("Could not detect frequency in detect_regime, assuming hourly")
            from utils.timeframe import FREQUENCY_SPECS
            freq = FREQUENCY_SPECS["1h"]
    
    vol = port.std() * freq.annualization_factor_vol
        
    autocorr = port.autocorr(lag=1) if len(port) > 2 else 0.0
    autocorr = 0.0 if pd.isna(autocorr) else autocorr
    
    recent_return = port.tail(window).sum()

    # STAGE 2 FIX: More aggressive high-vol detection
    if vol > 1.2:  # Lowered from 1.5 - more sensitive to risk
        logger.info(f"REGIME: high_vol (vol={vol:.2%})")
        return "high_vol"
    if autocorr > 0.1 or recent_return > 0.1:
        logger.info(f"REGIME: trending (autocorr={autocorr:.3f}, recent_ret={recent_return:.4f})") 
        return "trending"
    logger.info(f"REGIME: mean_reverting (autocorr={autocorr:.3f}, vol={vol:.2%})")
    return "mean_reverting"


# STAGE 5+ FIX: Even more balanced strategy biasing - further reduce defensive allocation
# In high_vol, target defensive weight around 45-50% instead of 50-55%
REGIME_PRIOR = {
    "trending": {
        "black_litterman": 1.3, "mvo": 1.2, "ml": 1.0,
        "risk_parity": 1.0, "cvar": 1.0,
        "trend_following": 1.8, "mean_reversion": 0.7
    },
    "mean_reverting": {
        "black_litterman": 0.9, "ml": 0.7, "mvo": 0.6,
        "risk_parity": 1.5, "cvar": 1.3,
        "trend_following": 0.5, "mean_reversion": 1.8
    },
    "high_vol": {
        # STAGE 5+ CRITICAL: Further reduction of defensive bias to improve returns
        # Allow ML and Black-Litterman even more weight (increased from 0.5/0.8 to 0.7/1.0)
        "risk_parity": 1.5, "cvar": 1.4, "black_litterman": 1.0,  # Reduced from 1.8/1.6/0.8
        "mvo": 0.7, "ml": 0.7,  # Increased from 0.5/0.5 - allow more aggressive strategies
        "trend_following": 1.0, "mean_reversion": 1.2  # Slightly reduced defensive bias
    },
}


class StrategySelector:
    """
    Risk-weighted ensemble blender with regime-driven defensive bias.
    
    STAGE 2-4 IMPROVEMENTS:
    - Enforces 60-70% allocation to defensive strategies (Trend-Following + CVaR + CASH) in bad markets
    - Sentiment multiplier on Trend-Following and Mean-Reversion weights
    - Faster learning from negative Sharpe strategies (6 vs 12 periods)
    - Floor/ceiling constraints maintain true diversification
    """

    def __init__(self, candidate_methods: List[str], track_record_len: int = 6,
                 min_strategy_weight: float = 0.05, max_strategy_weight: float = 0.40):
        """
        Args:
            track_record_len: STAGE 3 FIX - Reduced from 12 to 6 for faster learning
            min_strategy_weight: Floor for strategy weights (prevents elimination)
            max_strategy_weight: Ceiling for strategy weights (prevents dominance)
        """
        self.candidate_methods = candidate_methods
        self.track_record_len = track_record_len
        self.min_strategy_weight = min_strategy_weight
        self.max_strategy_weight = max_strategy_weight
        
        self._track_record: Dict[str, deque] = {m: deque(maxlen=track_record_len) for m in candidate_methods}
        self.history: List[Dict] = []
        self.sentiment_score = 0.0  # STAGE 4: Store latest sentiment score
        
        logger.info(f"StrategySelector initialized with {len(candidate_methods)} strategies, "
                   f"track_record_len={track_record_len}, "
                   f"min_weight={min_strategy_weight:.0%}, max_weight={max_strategy_weight:.0%}")

    def record_realized_performance(self, method: str, realized_return: float, realized_vol: float):
        """Call after a rebalance period ends. STAGE 3: Faster penalization of losing strategies."""
        score = realized_return / realized_vol if realized_vol > 0 else 0.0
        self._track_record.setdefault(method, deque(maxlen=self.track_record_len)).append(score)
        
        if score < -0.5:
            logger.warning(f"[STAGE 3] {method} had severely negative Sharpe {score:.3f} - will reduce weight rapidly")

    def _track_record_score(self, method: str) -> float:
        rec = self._track_record[method]
        if not rec:
            return 0.0
        return float(np.mean(rec))

    def set_sentiment_score(self, sentiment: float):
        """
        STAGE 4: Set the current market sentiment score (-1.0 to 1.0).
        This will be applied as a multiplier to trend-following and mean-reversion weights.
        """
        self.sentiment_score = np.clip(sentiment, -1.0, 1.0)
        logger.info(f"[STAGE 4] Sentiment score updated: {self.sentiment_score:.3f}")

    def select(self, prices: pd.DataFrame, returns: pd.DataFrame,
                in_sample_scores: Dict[str, float], realized_perf: Optional[Dict] = None,
                current_drawdown: float = 0.0) -> str:
        """
        LEGACY METHOD: Pick the single best strategy (kept for backward compatibility).
        For new code, use blend() instead for ensemble approach.
        """
        regime = detect_regime(returns)
        prior = REGIME_PRIOR.get(regime, {m: 1.0 for m in self.candidate_methods})

        has_hybrid = any('hybrid' in m for m in self.candidate_methods)
        if has_hybrid and (regime == 'high_vol' or current_drawdown > 0.05):
            if 'hybrid_risk_parity_arb' in self.candidate_methods:
                logger.info(f"[STAGE 2] Forcing hybrid_risk_parity_arb due to regime={regime}, drawdown={current_drawdown:.2%}")
                return 'hybrid_risk_parity_arb'
            elif 'hybrid_mvo_arb' in self.candidate_methods:
                logger.info(f"[STAGE 2] Forcing hybrid_mvo_arb due to regime={regime}, drawdown={current_drawdown:.2%}")
                return 'hybrid_mvo_arb'

        combined = {}
        for m in self.candidate_methods:
            in_sample = in_sample_scores.get(m, 0.0)
            track = self._track_record_score(m)
            regime_mult = prior.get(m, 1.0)
            
            if realized_perf and m in realized_perf:
                ret = realized_perf[m].get('return', -999)
                vol = realized_perf[m].get('vol', 1.0)
                realized_score = ret / (vol + 0.01) if vol > 0 else -999
                
                if ret < 0:
                    realized_score *= 10.0
                
                combined[m] = (0.2 * in_sample + 0.8 * realized_score) * regime_mult
                logger.info(f"  {m}: in_sample={in_sample:.3f}, realized_ret={ret:.4f}, realized_score={realized_score:.3f}, combined={combined[m]:.3f}")
            else:
                combined[m] = (0.4 * in_sample + 0.6 * track) * regime_mult

        chosen = max(combined, key=combined.get)
        
        if all(v < 0 for v in combined.values()):
            if 'risk_parity' in combined:
                chosen = 'risk_parity'
                logger.warning(f"[STAGE 2] All strategies negative! Forcing risk_parity for safety")
            elif 'cvar' in combined:
                chosen = 'cvar'
                logger.warning(f"[STAGE 2] All strategies negative! Forcing cvar for safety")
        
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
        ENSEMBLE BLEND with STAGE 2-4 improvements:
        - Regime-driven defensive weighting (60-70% to defensive strategies in bad markets)
        - Sentiment multiplier on trend-following and mean-reversion
        - Faster learning from negative Sharpe strategies (6 vs 12 periods)
        - Floor/ceiling constraints (5%-40%) maintain true diversification
        """
        # Step 1: Get weights from each strategy
        all_weights = {}
        failed_strategies = []
        
        for name, fn in strategy_fns.items():
            try:
                w = fn(prices, returns)
                w_array = np.array(w)
                
                if len(w_array) != len(returns.columns):
                    logger.error(f"Strategy {name} returned {len(w_array)} weights but expected {len(returns.columns)}")
                    failed_strategies.append(name)
                    continue
                    
                if w_array.sum() > 0:
                    w_array = w_array / w_array.sum()
                
                all_weights[name] = w_array
                logger.debug(f"Strategy {name} produced valid weights: {w_array}")
            except Exception as e:
                logger.warning(f"Strategy {name} failed during blend: {e}")
                failed_strategies.append(name)
        
        if not all_weights:
            n_assets = len(returns.columns)
            logger.warning("All strategies failed! Using equal-weight fallback")
            return np.ones(n_assets) / n_assets, {}
        
        # Step 2: Calculate long-term realized Sharpe for each strategy
        strategy_sharpes = {}
        for name in all_weights.keys():
            rec = self._track_record.setdefault(name, deque(maxlen=self.track_record_len))
            if len(rec) >= 2:  # STAGE 3 FIX: Need only 2 observations (was 3)
                sharpe = float(np.mean(rec))
            else:
                sharpe = 0.0
            strategy_sharpes[name] = sharpe
        
        # Step 3: Convert Sharpes to blend weights with regime bias
        raw_scores = {}
        regime = detect_regime(returns)
        prior = REGIME_PRIOR.get(regime, {m: 1.0 for m in all_weights.keys()})
        
        for name in all_weights.keys():
            sharpe = strategy_sharpes[name]
            regime_bias = prior.get(name, 1.0)
            
            # STAGE 3 FIX: Exponential transform better ranks strategies during drawdowns
            clipped_sharpe = np.clip(sharpe, -5, 5)
            score = float(np.exp(clipped_sharpe)) * regime_bias
            raw_scores[name] = score
        
        # Normalize to sum to 1.0
        total_score = sum(raw_scores.values())
        if total_score == 0:
            blend_weights = {name: 1.0 / len(all_weights) for name in all_weights.keys()}
        else:
            blend_weights = {name: score / total_score for name, score in raw_scores.items()}
        
        # Apply floor and ceiling constraints
        blend_weights = self._apply_weight_constraints(blend_weights)
        
        # STAGE 5+ FIX: Softer defensive allocation - target 45-50% instead of 50-55%
        if regime in ['high_vol', 'mean_reverting']:
            logger.info(f"[STAGE 5+] Regime {regime} detected - enforcing softer defensive allocation (45-50%)")
            defensive_strategies = ['trend_following', 'cvar', 'risk_parity']
            defensive_weight = sum(blend_weights.get(s, 0) for s in defensive_strategies)
            
            if defensive_weight < 0.45:
                logger.info(f"[STAGE 5+] Current defensive weight {defensive_weight:.0%} < 45% target. "
                           f"Rebalancing to enforce 48% minimum...")
                # Reduce aggressive strategies less aggressively (only 25% cut vs 30% before)
                aggressive_strategies = ['ml', 'mvo', 'black_litterman']
                aggressive_weight = sum(blend_weights.get(s, 0) for s in aggressive_strategies)
                
                if aggressive_weight > 0:
                    # Cut aggressive strategies by only 25% (was 30%)
                    reduction = aggressive_weight * 0.25
                    for s in aggressive_strategies:
                        if s in blend_weights:
                            blend_weights[s] *= 0.75  # Keep 75% instead of 70%
                    
                    # Reallocate to defensive (preference: trend_following > cvar > risk_parity)
                    boost_distribution = [0.4, 0.35, 0.25]
                    for s, boost in zip(defensive_strategies, boost_distribution):
                        if s in blend_weights:
                            blend_weights[s] += reduction * boost
                
                # Re-apply constraints
                blend_weights = self._apply_weight_constraints(blend_weights)
                new_defensive = sum(blend_weights.get(s, 0) for s in defensive_strategies)
                logger.info(f"[STAGE 5+] Defensive allocation after rebalance: {new_defensive:.0%}")
        
        # STAGE 4 FIX: Apply sentiment multiplier to trend-following and mean-reversion
        if self.sentiment_score != 0.0:
            sentiment_multiplier = 1.0 + (self.sentiment_score * 0.5)  # -1 → 0.5x, +1 → 1.5x
            
            for s in ['trend_following', 'mean_reversion']:
                if s in blend_weights:
                    old_weight = blend_weights[s]
                    blend_weights[s] *= sentiment_multiplier
                    logger.info(f"[STAGE 4] {s}: sentiment={self.sentiment_score:.2f}, "
                               f"multiplier={sentiment_multiplier:.2f}, "
                               f"weight {old_weight:.2%} → {blend_weights[s]:.2%}")
            
            # Re-normalize
            total = sum(blend_weights.values())
            if total > 0:
                blend_weights = {k: v / total for k, v in blend_weights.items()}
            
            # Re-apply constraints (sentiment may have violated them)
            blend_weights = self._apply_weight_constraints(blend_weights)
        
        # Step 4: Combine asset weights using strategy blend weights
        combined_asset_weights = np.zeros(len(returns.columns))
        for name, w in all_weights.items():
            combined_asset_weights += blend_weights[name] * w
        
        if combined_asset_weights.sum() > 0:
            combined_asset_weights = combined_asset_weights / combined_asset_weights.sum()
        
        # Log blend composition
        blend_log = ", ".join([f"{k}={v*100:.1f}%" for k, v in sorted(blend_weights.items(), key=lambda x: -x[1])])
        logger.info(f"[Regime={regime}] Blend weights: {blend_log}")
        logger.info(f"Combined asset weights: {combined_asset_weights}")
        
        return combined_asset_weights, blend_weights
    
    def _apply_weight_constraints(self, weights: Dict[str, float]) -> Dict[str, float]:
        """
        STAGE 2-3: Apply floor/ceiling constraints while maintaining sum=1.
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
        
        # Iterative projection (max 10 iterations)
        for iteration in range(10):
            # Apply floor
            weights = {k: max(min_w, v) for k, v in weights.items()}
            # Apply ceiling
            weights = {k: min(max_w, v) for k, v in weights.items()}
            # Normalize
            total = sum(weights.values())
            if total > 0:
                weights = {k: v / total for k, v in weights.items()}
            else:
                weights = {k: 1.0 / n for k in weights.keys()}
                break
        
        return weights


def compute_in_sample_scores(candidate_methods: List[str], strategy_fns: Dict[str, Callable],
                               prices: pd.DataFrame, returns: pd.DataFrame, freq=None) -> Dict[str, float]:
    """
    Score each candidate strategy on the lookback window.
    STAGE 2-3: Better error handling for structural bugs.
    
    PHASE 1 FIX: Accepts optional FrequencySpec for correct annualization.
    If freq is None, auto-detects from returns index.
    """
    scores = {}
    n_expected_assets = len(returns.columns)
    
    # PHASE 1 FIX: Determine annualization factors
    if freq is None:
        # Auto-detect frequency from returns index
        try:
            from utils.timeframe import detect_frequency as detect_freq
            freq = detect_freq(returns)
        except Exception:
            # Fallback to hourly assumption with warning
            logger.warning("Could not detect frequency in compute_in_sample_scores, assuming hourly")
            from utils.timeframe import FREQUENCY_SPECS
            freq = FREQUENCY_SPECS["1h"]
    
    ann_mean_factor = freq.annualization_factor_mean
    ann_vol_factor = freq.annualization_factor_vol
    
    for method in candidate_methods:
        try:
            weights = strategy_fns[method](prices, returns)
            weights_array = np.array(weights)
            
            if len(weights_array) != n_expected_assets:
                logger.error(f"CRITICAL MISMATCH for {method}: expected {n_expected_assets} weights, got {len(weights_array)}")
                scores[method] = -999.0
                continue
            
            port_ret = returns.values @ weights_array
            mean_r = port_ret.mean() * ann_mean_factor
            vol_r = port_ret.std() * ann_vol_factor
            scores[method] = (mean_r - 0.0) / vol_r if vol_r > 0 else 0.0  # STAGE 1: rf_rate = 0.0
        except Exception as e:
            logger.warning(f"In-sample scoring failed for {method}: {e}")
            scores[method] = -999.0
    return scores


def main():
    """Offline self-test with synthetic data."""
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

    selector.record_realized_performance(chosen, realized_return=-0.05, realized_vol=0.2)
    chosen2 = selector.select(prices, returns, fake_in_sample)
    print("Chosen strategy after bad outcome:", chosen2)


if __name__ == "__main__":
    main()
