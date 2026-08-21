"""
Strategy Selector Module - Phase 7 Dynamic Ensemble with Regime-Conditional Scoring
------------------------------------------------------------------------------------
PHASE 7 IMPROVEMENTS:
- Dynamic scoring replaces static exp(sharpe) with composite metrics
- Regime-conditional performance tracking (bull_trend, bear_trend, high_vol, low_vol_range, crisis)
- Strategy correlation penalty prevents over-concentration
- Turnover penalty reduces excessive rebalancing
- Track record decay gives more weight to recent performance
- ML OOS weakness flag integration
- Sentiment multiplier ONLY on trend_following and mean_reversion
- Bounded weights enforced (5%-40%)

BACKWARD COMPATIBILITY: Maintains Stage 2-6 functionality while adding Phase 7 enhancements.
"""

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class StrategyScore:
    """PHASE 7: Composite strategy scoring dataclass."""
    method: str
    raw_sharpe: float = 0.0
    sharpe_percentile: float = 0.0  # 0-1 across all strategies
    sortino: float = 0.0
    max_drawdown: float = 0.0
    consistency: float = 0.0  # 0-1 (positive months / total months)
    regime_score: float = 0.0  # performance in current regime
    recent_score: float = 0.0  # performance in last 6 periods
    sample_size: int = 0
    confidence: float = 0.0  # 0-1 based on sample size
    correlation_penalty: float = 0.0  # 0-1 (1 = high correlation with others)
    turnover_penalty: float = 0.0  # 0-0.20 based on turnover
    ml_weakness_flag: bool = False  # True if ML OOS R² < 0
    final_score: float = 0.0  # composite


def detect_regime(returns: pd.DataFrame, window: int = 168, freq=None) -> str:
    """
    PHASE 3/7 REGIME DETECTOR: Expanded to support all 5 regimes.
    
    Returns one of: 'bull_trend', 'bear_trend', 'high_vol', 'low_vol_range', 'crisis'
    
    PHASE 1 FIX: Uses FrequencySpec for correct vol annualization.
    PHASE 3 FIX: Distinguishes bull vs bear trends, adds crisis detection.
    NUMPY SAFEGUARD: Checks for NaN/Inf to prevent overflow errors.
    """
    if len(returns) < window:
        window = max(5, len(returns))
    if window < 5:
        return "low_vol_range"

    port = returns.tail(window).mean(axis=1)
    
    # NUMPY SAFEGUARD: Check for NaN/Inf in returns data
    if not np.all(np.isfinite(port.values)):
        logger.warning("REGIME: Non-finite values detected in returns, defaulting to low_vol_range")
        return "low_vol_range"
    
    # PHASE 1 FIX: Use detected frequency for vol annualization
    if freq is None:
        try:
            from utils.timeframe import detect_frequency as detect_freq
            freq = detect_freq(returns)
        except Exception:
            logger.warning("Could not detect frequency in detect_regime, assuming hourly")
            from utils.timeframe import FREQUENCY_SPECS
            freq = FREQUENCY_SPECS["1h"]
    
    vol = port.std() * freq.annualization_factor_vol
    
    # NUMPY SAFEGUARD: Ensure vol is finite
    if not np.isfinite(vol):
        logger.warning("REGIME: Non-finite volatility detected, defaulting to low_vol_range")
        return "low_vol_range"
    
    autocorr = port.autocorr(lag=1) if len(port) > 2 else 0.0
    autocorr = 0.0 if pd.isna(autocorr) else autocorr
    recent_return = port.tail(window).sum()
    
    # NUMPY SAFEGUARD: Ensure recent_return is finite
    if not np.isfinite(recent_return):
        recent_return = 0.0
    
    # Calculate drawdown for crisis detection
    cum_returns = (1 + port).cumprod()
    running_max = cum_returns.cummax()
    drawdown = (cum_returns - running_max) / running_max
    max_dd = drawdown.min() if len(drawdown) > 0 else 0.0
    
    # NUMPY SAFEGUARD: Ensure max_dd is finite
    if not np.isfinite(max_dd):
        max_dd = 0.0

    # PHASE 3: 5-regime classification
    # Crisis: extreme drawdown OR extreme volatility
    if max_dd < -0.15 or vol > 2.0:
        logger.info(f"REGIME: crisis (max_dd={max_dd:.2%}, vol={vol:.2%})")
        return "crisis"
    
    # High volatility: elevated but not crisis level
    if vol > 1.2:
        logger.info(f"REGIME: high_vol (vol={vol:.2%})")
        return "high_vol"
    
    # Bull trend: positive momentum with reasonable volatility
    if recent_return > 0.05 and vol < 1.2:
        logger.info(f"REGIME: bull_trend (recent_ret={recent_return:.2%}, vol={vol:.2%})")
        return "bull_trend"
    
    # Bear trend: negative momentum
    if recent_return < -0.05:
        logger.info(f"REGIME: bear_trend (recent_ret={recent_return:.2%})")
        return "bear_trend"
    
    # Low volatility range: calm markets
    logger.info(f"REGIME: low_vol_range (vol={vol:.2%}, recent_ret={recent_return:.2%})")
    return "low_vol_range"


# PHASE 7: EXPANDED REGIME_PRIOR - All 5 Phase 3 regimes supported
# Economic rationale documented for each regime
REGIME_PRIOR = {
    # BULL TREND: Favor growth-oriented strategies
    "bull_trend": {
        "black_litterman": 1.4,  # BL benefits from clear views
        "mvo": 1.3,              # MVO works well in stable uptrends
        "ml": 1.2,               # ML can capture momentum patterns
        "risk_parity": 0.9,      # Less need for risk balancing
        "cvar": 0.8,             # Tail risk less concerning
        "trend_following": 2.0,  # Maximum allocation to trend
        "mean_reversion": 0.6    # Mean reversion underperforms in trends
    },
    
    # BEAR TREND: Defensive with some opportunistic positioning
    "bear_trend": {
        "black_litterman": 1.1,  # Conservative views
        "mvo": 0.7,              # Reduce MVO exposure
        "ml": 0.8,               # ML may find short opportunities
        "risk_parity": 1.4,      # Risk balancing important
        "cvar": 1.5,             # Tail risk protection
        "trend_following": 1.2,  # Can follow downward trends
        "mean_reversion": 1.3    # Bounce plays possible
    },
    
    # HIGH VOL: Moderate defense without panic
    "high_vol": {
        "black_litterman": 1.0,  # Steady approach
        "mvo": 0.7,              # Reduce optimization risk
        "ml": 0.7,               # ML uncertain in chaos
        "risk_parity": 1.5,      # Risk balancing critical
        "cvar": 1.4,             # Tail risk focus
        "trend_following": 1.0,  # Neutral to trends
        "mean_reversion": 1.2    # Some mean reversion opportunities
    },
    
    # LOW VOL RANGE: Balanced approach, favor efficiency
    "low_vol_range": {
        "black_litterman": 1.2,  # Good environment for views
        "mvo": 1.3,              # Optimization works well
        "ml": 1.1,               # ML can find patterns
        "risk_parity": 1.0,      # Standard allocation
        "cvar": 0.9,             # Less tail concern
        "trend_following": 1.1,  # Mild trend following
        "mean_reversion": 1.4    # Mean reversion works in calm markets
    },
    
    # CRISIS: Maximum defense, survival mode
    "crisis": {
        "black_litterman": 0.8,  # Conservative
        "mvo": 0.5,              # Minimize optimization risk
        "ml": 0.4,               # ML unreliable in crises
        "risk_parity": 1.8,      # Maximum risk balancing
        "cvar": 1.8,             # Maximum tail protection
        "trend_following": 1.3,  # Follow crash trends
        "mean_reversion": 1.0    # Caution on reversal bets
    },
}


class StrategySelector:
    """
    PHASE 7 DYNAMIC ENSEMBLE with regime-conditional scoring.
    
    PHASE 7 IMPROVEMENTS:
    - Dynamic composite scoring replaces static exp(sharpe)
    - Regime-conditional performance tracking (5 regimes)
    - Strategy correlation penalty prevents over-concentration
    - Turnover penalty reduces excessive rebalancing
    - Track record decay (10% per period)
    - ML OOS weakness flag integration
    - Sentiment multiplier ONLY on trend_following/mean_reversion
    - Bounded weights enforced (5%-40%)
    
    BACKWARD COMPATIBILITY: Maintains Stage 2-6 functionality.
    """

    def __init__(self, candidate_methods: List[str], track_record_len: int = 6,
                 min_strategy_weight: float = 0.05, max_strategy_weight: float = 0.40,
                 decay_rate: float = 0.1):
        """
        Args:
            track_record_len: Number of periods for track record (default 6)
            min_strategy_weight: Floor for strategy weights (5%)
            max_strategy_weight: Ceiling for strategy weights (40%)
            decay_rate: Exponential decay rate for track record (10% per period)
        """
        self.candidate_methods = candidate_methods
        self.track_record_len = track_record_len
        self.min_strategy_weight = min_strategy_weight
        self.max_strategy_weight = max_strategy_weight
        self.decay_rate = decay_rate
        
        # Track records: deque of (period_index, score, regime) tuples
        self._track_record: Dict[str, deque] = {m: deque(maxlen=track_record_len) for m in candidate_methods}
        
        # PHASE 7: Regime-conditional performance tracking
        self._regime_performance: Dict[str, Dict[str, deque]] = {
            regime: {m: deque(maxlen=50) for m in candidate_methods}
            for regime in REGIME_PRIOR.keys()
        }
        
        # Strategy weight history for correlation calculation
        self._weight_history: Dict[str, deque] = {m: deque(maxlen=30) for m in candidate_methods}
        
        # ML OOS R² tracking
        self._ml_oos_r2: Optional[float] = None
        
        self.history: List[Dict] = []
        self.sentiment_score = 0.0
        self._period_counter = 0
        
        logger.info(f"StrategySelector (PHASE 7) initialized with {len(candidate_methods)} strategies, "
                   f"track_record_len={track_record_len}, decay_rate={decay_rate}, "
                   f"min_weight={min_strategy_weight:.0%}, max_weight={max_strategy_weight:.0%}")

    def record_realized_performance(self, method: str, realized_return: float, realized_vol: float,
                                    regime: Optional[str] = None):
        """
        Record performance for a strategy. PHASE 7: Also tracks regime-conditional performance.
        
        Args:
            method: Strategy name
            realized_return: Period return
            realized_vol: Period volatility
            regime: Current regime (optional, auto-detected if None)
        """
        score = realized_return / realized_vol if realized_vol > 0 else 0.0
        self._period_counter += 1
        
        # Standard track record with decay weighting
        self._track_record.setdefault(method, deque(maxlen=self.track_record_len)).append(
            (self._period_counter, score, regime)
        )
        
        # Regime-conditional tracking
        if regime and regime in self._regime_performance:
            self._regime_performance[regime][method].append((self._period_counter, score))
        
        if score < -0.5:
            logger.warning(f"[PHASE 7] {method} had severely negative Sharpe {score:.3f}")

    def set_ml_oos_r2(self, r2: float):
        """PHASE 7: Set ML OOS R² for weakness flag integration."""
        self._ml_oos_r2 = r2
        if r2 < 0:
            logger.warning(f"[PHASE 7] ML OOS R²={r2:.3f} < 0 - ML strategy will be heavily penalized")
        elif r2 < 0.05:
            logger.info(f"[PHASE 7] ML OOS R²={r2:.3f} < 0.05 - ML strategy score reduced by 50%")

    def _track_record_score(self, method: str) -> float:
        """Calculate exponentially decayed track record score."""
        rec = self._track_record.get(method, deque())
        if not rec:
            return 0.0
        
        # Exponential decay: older observations weighted less
        now = self._period_counter
        weighted_sum = 0.0
        weight_total = 0.0
        
        for period_idx, score, regime in rec:
            age = now - period_idx
            weight = np.exp(-self.decay_rate * age)
            weighted_sum += weight * score
            weight_total += weight
        
        return weighted_sum / weight_total if weight_total > 0 else 0.0

    def _regime_score(self, method: str, current_regime: str) -> float:
        """PHASE 7: Calculate strategy performance in current regime."""
        regime_rec = self._regime_performance.get(current_regime, {}).get(method, deque())
        if not regime_rec:
            return 0.5  # Neutral prior when no data
        
        scores = [score for _, score in regime_rec]
        return float(np.mean(scores))

    def _recent_score(self, method: str, periods: int = 6) -> float:
        """PHASE 7: Calculate recent performance (last N periods)."""
        rec = self._track_record.get(method, deque())
        if len(rec) < 2:
            return 0.0
        
        # Get last N periods
        recent = list(rec)[-periods:]
        scores = [score for _, score, _ in recent]
        return float(np.mean(scores))

    def _consistency_score(self, method: str) -> float:
        """PHASE 7: Calculate consistency (fraction of positive periods)."""
        rec = self._track_record.get(method, deque())
        if len(rec) < 2:
            return 0.5
        
        scores = [score for _, score, _ in rec]
        positive_count = sum(1 for s in scores if s > 0)
        return positive_count / len(scores)

    def _confidence_score(self, method: str) -> float:
        """PHASE 7: Calculate confidence based on sample size."""
        rec = self._track_record.get(method, deque())
        n = len(rec)
        if n == 0:
            return 0.0
        # Confidence increases with sample size, saturating at ~20 observations
        return min(1.0, n / 20.0)

    def _correlation_penalty(self, method: str) -> float:
        """PHASE 7: Calculate correlation penalty with other strategies."""
        if len(self._weight_history.get(method, [])) < 5:
            return 0.0
        
        method_weights = list(self._weight_history[method])
        penalties = []
        
        for other_method in self.candidate_methods:
            if other_method == method:
                continue
            other_weights = list(self._weight_history.get(other_method, []))
            if len(other_weights) < 5:
                continue
            
            # Calculate correlation
            min_len = min(len(method_weights), len(other_weights))
            corr = np.corrcoef(method_weights[-min_len:], other_weights[-min_len:])[0, 1]
            
            if not np.isnan(corr) and corr > 0.7:
                penalties.append((corr - 0.7) / 0.3)  # Scale 0.7-1.0 to 0-1
        
        return np.mean(penalties) if penalties else 0.0

    def set_sentiment_score(self, sentiment: float):
        """PHASE 7: Set sentiment score (applied ONLY to trend_following/mean_reversion)."""
        self.sentiment_score = np.clip(sentiment, -1.0, 1.0)
        logger.info(f"[PHASE 7] Sentiment score: {self.sentiment_score:.3f}")

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
              strategy_fns: Dict[str, Callable], lookback_window_days: int = 90,
              turnover: Optional[Dict[str, float]] = None) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        PHASE 7 DYNAMIC ENSEMBLE BLEND:
        - Dynamic composite scoring replaces static exp(sharpe)
        - Regime-conditional performance tracking (5 regimes)
        - Strategy correlation penalty prevents over-concentration
        - Turnover penalty reduces excessive rebalancing
        - Track record decay (10% per period)
        - ML OOS weakness flag integration
        - Sentiment multiplier ONLY on trend_following/mean_reversion
        - Bounded weights enforced (5%-40%)
        
        Args:
            turnover: Optional dict of strategy turnover values for penalty calculation
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
                # Record weight history for correlation calculation
                self._weight_history.setdefault(name, deque(maxlen=30)).append(w_array.copy())
                logger.debug(f"Strategy {name} produced valid weights")
            except Exception as e:
                logger.warning(f"Strategy {name} failed during blend: {e}")
                failed_strategies.append(name)
        
        if not all_weights:
            n_assets = len(returns.columns)
            logger.warning("All strategies failed! Using equal-weight fallback")
            return np.ones(n_assets) / n_assets, {}
        
        # PHASE 7: Dynamic composite scoring
        regime = detect_regime(returns)
        scores_dict: Dict[str, StrategyScore] = {}
        
        # Calculate raw sharpes for percentile ranking
        raw_sharpes = {}
        for name in all_weights.keys():
            rec = self._track_record.get(name, deque())
            if len(rec) >= 2:
                # Use tuple format (period_idx, score, regime)
                scores = [s for _, s, _ in rec]
                raw_sharpes[name] = float(np.mean(scores))
            else:
                raw_sharpes[name] = 0.0
        
        # Calculate sharpe percentiles
        if raw_sharpes:
            sorted_sharpes = sorted(raw_sharpes.values())
            for name in all_weights.keys():
                rank = sorted_sharpes.index(raw_sharpes[name])
                raw_sharpes[name] = rank / max(1, len(sorted_sharpes) - 1) if len(sorted_sharpes) > 1 else 0.5
        
        # Build composite scores for each strategy
        for name in all_weights.keys():
            score = StrategyScore(method=name)
            score.raw_sharpe = raw_sharpes.get(name, 0.0)
            score.sharpe_percentile = raw_sharpes.get(name, 0.0)
            score.regime_score = self._regime_score(name, regime)
            score.recent_score = self._recent_score(name)
            score.consistency = self._consistency_score(name)
            score.confidence = self._confidence_score(name)
            score.correlation_penalty = self._correlation_penalty(name)
            
            # Turnover penalty
            if turnover and name in turnover:
                tov = turnover[name]
                if tov > 0.50:
                    score.turnover_penalty = 0.20
                elif tov > 0.30:
                    score.turnover_penalty = 0.10
                else:
                    score.turnover_penalty = 0.0
            
            # ML weakness flag
            if name == 'ml' and self._ml_oos_r2 is not None:
                if self._ml_oos_r2 < 0:
                    score.ml_weakness_flag = True
                elif self._ml_oos_r2 < 0.05:
                    score.ml_weakness_flag = True  # Will reduce score by 50%
            
            # PHASE 7 COMPOSITE SCORING FORMULA:
            # final = 0.25*sharpe_pct + 0.15*sortino + 0.10*consistency + 0.20*regime + 0.15*recent + 0.10*confidence - 0.05*corr_penalty - turnover_penalty
            # Simplified: using sharpe_percentile as proxy for sortino
            score.final_score = (
                0.25 * score.sharpe_percentile +
                0.10 * score.consistency +
                0.20 * score.regime_score +
                0.15 * score.recent_score +
                0.10 * score.confidence -
                0.05 * score.correlation_penalty -
                score.turnover_penalty
            )
            
            # Apply ML weakness penalty
            if score.ml_weakness_flag:
                if self._ml_oos_r2 is not None and self._ml_oos_r2 < 0:
                    score.final_score = 0.0  # ML OOS R² < 0 → zero score
                    logger.warning(f"[PHASE 7] ML strategy score set to 0 due to OOS R²={self._ml_oos_r2:.3f}")
                else:
                    score.final_score *= 0.5  # ML OOS R² < 0.05 → 50% score
                    logger.info(f"[PHASE 7] ML strategy score reduced by 50% due to weak OOS R²")
            
            # Apply regime prior as multiplier
            regime_bias = REGIME_PRIOR.get(regime, {}).get(name, 1.0)
            score.final_score *= regime_bias
            
            scores_dict[name] = score
            logger.debug(f"[PHASE 7] {name}: final_score={score.final_score:.3f} (sharpe={score.sharpe_percentile:.2f}, regime={score.regime_score:.2f}, recent={score.recent_score:.2f})")
        
        # Convert scores to blend weights
        total_score = sum(s.final_score for s in scores_dict.values())
        if total_score <= 0:
            # Fallback to equal weights if all scores are negative/zero
            blend_weights = {name: 1.0 / len(all_weights) for name in all_weights.keys()}
            logger.warning("All strategy scores <= 0, using equal-weight fallback")
        else:
            blend_weights = {name: max(0.0, s.final_score) / total_score for name, s in scores_dict.items()}
        
        # Apply floor and ceiling constraints (5%-40%)
        blend_weights = self._apply_weight_constraints(blend_weights)
        
        # PHASE 7: Sentiment multiplier ONLY on trend_following and mean_reversion
        if self.sentiment_score != 0.0:
            sentiment_multiplier = 1.0 + (self.sentiment_score * 0.5)  # Range: [0.5, 1.5]
            sentiment_multiplier = np.clip(sentiment_multiplier, 0.5, 1.5)
            
            for s in ['trend_following', 'mean_reversion']:
                if s in blend_weights:
                    old_weight = blend_weights[s]
                    blend_weights[s] *= sentiment_multiplier
                    logger.info(f"[PHASE 7] {s}: sentiment={self.sentiment_score:.2f}, "
                               f"multiplier={sentiment_multiplier:.2f}, weight {old_weight:.2%} → {blend_weights[s]:.2%}")
            
            # Re-normalize
            total = sum(blend_weights.values())
            if total > 0:
                blend_weights = {k: v / total for k, v in blend_weights.items()}
            
            # Re-apply constraints
            blend_weights = self._apply_weight_constraints(blend_weights)
        
        # Log blend composition
        blend_log = ", ".join([f"{k}={v*100:.1f}%" for k, v in sorted(blend_weights.items(), key=lambda x: -x[1])])
        logger.info(f"[PHASE 7 | Regime={regime}] Blend weights: {blend_log}")
        
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
        
        # Return all_weights to avoid recomputing strategies in backtester
        return combined_asset_weights, blend_weights, all_weights
    
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
