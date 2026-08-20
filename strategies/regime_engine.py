"""
Phase 3: Unified Regime Engine
================================
Single coherent regime detection system with multi-feature causal signals.

Design Principles:
1. Causal only: No look-ahead bias - regime at time t uses only data up to t
2. Frequency-aware: Window lengths scale with detected frequency (bars, not fixed hours)
3. Scorecard-based: Hierarchical rules avoid brittle single-threshold behavior
4. Configurable: All thresholds in one place
5. Logged: Features, confidence, and timestamp for analysis

Regime Labels:
- bull_trend: Strong positive trend with moderate volatility
- bear_trend: Strong negative trend (may coexist with high vol)
- high_vol: Elevated realized volatility (risk-off signal)
- low_vol_range: Low volatility, no clear trend (mean-reversion friendly)
- crisis: Deep drawdown AND extreme volatility (maximum defense)
"""

import logging
import numpy as np
import pandas as pd
from typing import NamedTuple, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from utils.timeframe import detect_frequency, FrequencySpec, FREQUENCY_SPECS

logger = logging.getLogger(__name__)


class RegimeLabel(str, Enum):
    """Valid regime labels."""
    BULL_TREND = "bull_trend"
    BEAR_TREND = "bear_trend"
    HIGH_VOL = "high_vol"
    LOW_VOL_RANGE = "low_vol_range"
    CRISIS = "crisis"


@dataclass
class RegimeState:
    """
    Output of regime detection at a point in time.
    
    Attributes:
        label: One of {bull_trend, bear_trend, high_vol, low_vol_range, crisis}
        confidence: 0..1 score indicating detection certainty
        features: Dict of feature values used for decision (for logging/analysis)
        as_of: Timestamp of the decision (decision time)
        timestamp: Unix timestamp or datetime for sequencing
    """
    label: RegimeLabel
    confidence: float
    features: Dict[str, float]
    as_of: Any  # datetime or timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'label': self.label.value,
            'confidence': self.confidence,
            'features': self.features,
            'as_of': str(self.as_of) if hasattr(self.as_of, '__str__') else self.as_of
        }


# =============================================================================
# CONFIGURABLE THRESHOLDS (all in one place)
# =============================================================================
# These can be tuned, but should NOT be grid-searched on test folds.
# Use economic justification or out-of-sample validation.

REGIME_THRESHOLDS = {
    # Volatility thresholds (annualized, decimal form)
    'vol_high': 0.80,       # Annualized vol > 80% → high_vol regime
    'vol_extreme': 1.50,    # Annualized vol > 150% → crisis candidate
    
    # Trend thresholds (cumulative return over window)
    'trend_strong_pos': 0.10,   # Cumulative return > 10% → bullish
    'trend_strong_neg': -0.10,  # Cumulative return < -10% → bearish
    
    # Drawdown thresholds (peak-to-trough, as positive number)
    'drawdown_moderate': 0.10,  # DD > 10% → defensive consideration
    'drawdown_severe': 0.25,    # DD > 25% → crisis candidate
    
    # Confidence calibration
    'confidence_floor': 0.5,    # Minimum confidence when regime detected
    'confidence_high': 0.8,     # High confidence threshold
}


class RegimeEngine:
    """
    Unified regime detection engine using multi-feature hierarchical rules.
    
    Features (all causal, computed at time t using only data up to t):
    1. Realized volatility (annualized)
    2. Short vs medium trend (return over N bars vs M bars)
    3. Drawdown from recent peak
    4. Average cross-asset correlation (optional, if multiple assets)
    5. Volume availability flag (skip volume features if NaN)
    
    Decision hierarchy:
    1. CRISIS: If drawdown severe AND vol extreme
    2. HIGH_VOL: If vol > high threshold
    3. BULL_TREND: If trend strong positive AND vol not extreme
    4. BEAR_TREND: If trend strong negative
    5. LOW_VOL_RANGE: Default (low vol, no clear trend)
    """
    
    def __init__(self, 
                 vol_window_bars: int = 168,      # ~1 week hourly, ~24 weeks daily
                 trend_short_bars: int = 72,       # Short trend window
                 trend_medium_bars: int = 336,     # Medium trend window
                 drawdown_window_bars: int = 720,  # ~30 days hourly, ~30 days daily
                 thresholds: Optional[Dict[str, float]] = None):
        """
        Initialize RegimeEngine with configurable windows and thresholds.
        
        Args:
            vol_window_bars: Number of bars for volatility calculation
            trend_short_bars: Bars for short-term trend
            trend_medium_bars: Bars for medium-term trend
            drawdown_window_bars: Bars for drawdown calculation
            thresholds: Override default REGIME_THRESHOLDS (rarely needed)
        """
        self.vol_window_bars = vol_window_bars
        self.trend_short_bars = trend_short_bars
        self.trend_medium_bars = trend_medium_bars
        self.drawdown_window_bars = drawdown_window_bars
        self.thresholds = thresholds or REGIME_THRESHOLDS.copy()
        
        logger.info(f"RegimeEngine initialized: vol_window={vol_window_bars}b, "
                   f"trend_short={trend_short_bars}b, trend_medium={trend_medium_bars}b")
    
    def _compute_realized_vol(self, returns: pd.DataFrame, freq: FrequencySpec) -> float:
        """
        Compute annualized realized volatility over the lookback window.
        
        Uses portfolio-level returns (mean across assets) for regime detection.
        Correctly annualizes using the detected frequency.
        """
        # Clip returns to prevent overflow
        returns_clipped = np.clip(returns, -0.5, 0.5)
        
        window = min(self.vol_window_bars, len(returns_clipped))
        if window < 10:
            return 0.0
        
        port_returns = returns_clipped.tail(window).mean(axis=1)
        vol = port_returns.std() * freq.annualization_factor_vol
        # Cap vol at reasonable maximum (e.g., 500%)
        if np.isnan(vol) or np.isinf(vol) or vol > 5.0:
            return 0.5  # Default to 50% if calculation fails
        return vol
    
    def _compute_trend_signal(self, returns: pd.DataFrame) -> Tuple[float, float]:
        """
        Compute trend signal: short-term vs medium-term cumulative returns.
        
        Returns:
            (short_return, medium_return): Cumulative returns over each window
        """
        port_returns = returns.mean(axis=1)
        
        # Short trend
        short_window = min(self.trend_short_bars, len(port_returns))
        short_ret = port_returns.tail(short_window).sum() if short_window >= 5 else 0.0
        
        # Medium trend
        medium_window = min(self.trend_medium_bars, len(port_returns))
        medium_ret = port_returns.tail(medium_window).sum() if medium_window >= 10 else 0.0
        
        return short_ret, medium_ret
    
    def _compute_drawdown(self, prices: pd.DataFrame) -> float:
        """Compute maximum drawdown safely without overflow."""
        if prices is None or len(prices) < 2:
            return 0.0
        
        # Get price series
        if isinstance(prices, pd.DataFrame):
            prices_series = prices.iloc[:, 0] if prices.shape[1] > 0 else prices
        else:
            prices_series = prices
        
        # Remove NaN/Inf and clip extreme values
        prices_series = prices_series.replace([np.inf, -np.inf], np.nan).dropna()
        if len(prices_series) < 2:
            return 0.0
        
        # Clip to prevent overflow
        prices_series = np.clip(prices_series, 1e-6, 1e12)
        
        # Calculate running maximum
        running_max = prices_series.cummax()
        safe_running_max = np.maximum(running_max, 1e-6)
        
        # Calculate drawdown
        drawdown = (prices_series - safe_running_max) / safe_running_max
        drawdown = np.clip(drawdown, -1.0, 0.0)
        
        max_dd = drawdown.min()
        
        # Safety check
        if np.isnan(max_dd) or np.isinf(max_dd) or max_dd < -1.0 or max_dd > 0.0:
            return 0.0
        
        return float(max_dd)
    
    def _compute_correlation_signal(self, returns: pd.DataFrame) -> float:
        """
        Compute average pairwise correlation across assets.
        
        High correlation during stress = reduced diversification benefit.
        Returns mean correlation (excluding diagonal).
        """
        if len(returns.columns) < 2 or len(returns) < 10:
            return 0.0
        
        try:
            corr_matrix = returns.tail(self.vol_window_bars).corr()
            # Get upper triangle (excluding diagonal)
            n = len(corr_matrix)
            mask = np.triu(np.ones((n, n)), k=1).astype(bool)
            avg_corr = corr_matrix.values[mask].mean()
            return avg_corr if not np.isnan(avg_corr) else 0.0
        except Exception:
            return 0.0
    
    def _check_volume_available(self, volumes: Optional[pd.DataFrame]) -> bool:
        """Check if volume data is available (not all NaN)."""
        if volumes is None:
            return False
        try:
            # Check if any volume data is non-NaN
            return not volumes.isna().all().all()
        except Exception:
            return False
    
    def detect(self, 
               prices: pd.DataFrame, 
               returns: pd.DataFrame,
               volumes: Optional[pd.DataFrame] = None,
               freq: Optional[FrequencySpec] = None) -> RegimeState:
        """
        Detect market regime at the current point in time.
        
        CRITICAL: This method uses ONLY data available at decision time.
        No future data, no look-ahead bias.
        
        Args:
            prices: DataFrame of prices (index = timestamps, columns = assets)
            returns: DataFrame of returns (same structure)
            volumes: Optional DataFrame of volumes (for volume-based features)
            freq: Optional FrequencySpec (auto-detected if None)
            
        Returns:
            RegimeState with label, confidence, features, and timestamp
        """
        # Safety: ensure returns are finite
        returns = returns.replace([np.inf, -np.inf], np.nan).dropna()
        if returns.empty or len(returns) < 5:
            return RegimeState(
                label=RegimeLabel.LOW_VOL_RANGE,
                confidence=0.5,
                features={'error': 'returns_empty_or_insufficient'},
                as_of=None
            )
        
        # Clip returns to prevent overflow
        returns = np.clip(returns, -0.5, 0.5)
        
        if len(returns) < 10:
            logger.warning("Insufficient data for regime detection, returning low_vol_range")
            return RegimeState(
                label=RegimeLabel.LOW_VOL_RANGE,
                confidence=self.thresholds['confidence_floor'],
                features={'error': 'insufficient_data'},
                as_of=returns.index[-1] if len(returns) > 0 else None
            )
        
        # Auto-detect frequency if not provided
        if freq is None:
            try:
                freq = detect_frequency(prices)
            except Exception as e:
                logger.warning(f"Frequency detection failed: {e}, using daily fallback")
                freq = FREQUENCY_SPECS["1d"]
        
        # Compute features (all causal)
        vol = self._compute_realized_vol(returns, freq)
        short_ret, medium_ret = self._compute_trend_signal(returns)
        drawdown = self._compute_drawdown(prices)
        avg_corr = self._compute_correlation_signal(returns)
        volume_ok = self._check_volume_available(volumes)
        
        features = {
            'realized_vol': vol,
            'short_return': short_ret,
            'medium_return': medium_ret,
            'drawdown': drawdown,
            'avg_correlation': avg_corr,
            'volume_available': volume_ok,
        }
        
        # Hierarchical regime detection
        label, confidence = self._classify_regime(features)
        
        regime_state = RegimeState(
            label=label,
            confidence=confidence,
            features=features,
            as_of=returns.index[-1]
        )
        
        logger.info(f"[PHASE 3] Regime={label.value}, confidence={confidence:.2f}, "
                   f"vol={vol:.2%}, dd={drawdown:.2%}, trend_short={short_ret:.4f}")
        
        return regime_state
    
    def _classify_regime(self, features: Dict[str, float]) -> Tuple[RegimeLabel, float]:
        """
        Hierarchical regime classification based on feature scores.
        
        Priority order:
        1. CRISIS: Deep drawdown + extreme vol
        2. HIGH_VOL: Elevated volatility
        3. BULL_TREND: Strong positive trend
        4. BEAR_TREND: Strong negative trend  
        5. LOW_VOL_RANGE: Default (low vol, no clear trend)
        """
        vol = features['realized_vol']
        short_ret = features['short_return']
        drawdown = features['drawdown']
        
        # Level 1: Crisis detection (most severe)
        if (drawdown >= self.thresholds['drawdown_severe'] and 
            vol >= self.thresholds['vol_extreme']):
            confidence = min(1.0, 0.7 + (drawdown - self.thresholds['drawdown_severe']) * 0.5)
            return RegimeLabel.CRISIS, confidence
        
        # Level 2: High volatility
        if vol >= self.thresholds['vol_high']:
            # Confidence increases with vol
            confidence = min(1.0, 0.6 + (vol - self.thresholds['vol_high']) * 0.3)
            return RegimeLabel.HIGH_VOL, confidence
        
        # Level 3: Bull trend (positive momentum)
        if short_ret >= self.thresholds['trend_strong_pos']:
            confidence = min(1.0, 0.6 + (short_ret - self.thresholds['trend_strong_pos']) * 0.5)
            return RegimeLabel.BULL_TREND, confidence
        
        # Level 4: Bear trend (negative momentum)
        if short_ret <= self.thresholds['trend_strong_neg']:
            confidence = min(1.0, 0.6 + abs(short_ret - self.thresholds['trend_strong_neg']) * 0.5)
            return RegimeLabel.BEAR_TREND, confidence
        
        # Level 5: Low volatility range (default)
        # Confidence is higher when vol is truly low
        vol_midpoint = self.thresholds['vol_high'] / 2
        if vol < vol_midpoint:
            confidence = self.thresholds['confidence_high']
        else:
            confidence = self.thresholds['confidence_floor']
        
        return RegimeLabel.LOW_VOL_RANGE, confidence
    
    def get_regime_prior_weights(self, regime: RegimeLabel) -> Dict[str, float]:
        """
        Map regime to prior weights for strategy blending.
        
        This replaces the hardcoded REGIME_PRIOR in strategy_selector.py
        with a more explicit, documented mapping.
        
        Returns dict of strategy_name -> weight multiplier
        """
        priors = {
            RegimeLabel.CRISIS: {
                # Maximum defense: cash, CVaR, risk parity
                'cvar': 2.0,
                'risk_parity': 1.8,
                'trend_following': 1.5,  # Defensive trend-following
                'black_litterman': 1.2,  # BL with shrinkage
                'mean_reversion': 0.3,   # Avoid mean-reversion in crashes
                'ml': 0.3,               # Reduce ML exposure
                'mvo': 0.2,              # Avoid pure MVO
            },
            RegimeLabel.HIGH_VOL: {
                # High defense but allow some risk-taking
                'cvar': 1.6,
                'risk_parity': 1.5,
                'trend_following': 1.2,
                'black_litterman': 1.0,
                'mean_reversion': 0.8,
                'ml': 0.6,
                'mvo': 0.5,
            },
            RegimeLabel.BEAR_TREND: {
                # Defensive with trend-following bias
                'trend_following': 1.8,
                'cvar': 1.4,
                'risk_parity': 1.2,
                'black_litterman': 0.9,
                'mean_reversion': 0.5,
                'ml': 0.5,
                'mvo': 0.4,
            },
            RegimeLabel.BULL_TREND: {
                # Risk-on: allow ML, MVO, trend-following
                'ml': 1.3,
                'mvo': 1.2,
                'trend_following': 1.5,
                'black_litterman': 1.2,
                'risk_parity': 0.8,
                'cvar': 0.7,
                'mean_reversion': 0.6,
            },
            RegimeLabel.LOW_VOL_RANGE: {
                # Mean-reversion friendly environment
                'mean_reversion': 1.8,
                'risk_parity': 1.3,
                'black_litterman': 1.1,
                'ml': 0.9,
                'mvo': 0.8,
                'trend_following': 0.7,
                'cvar': 0.8,
            },
        }
        return priors.get(regime, priors[RegimeLabel.LOW_VOL_RANGE])


# =============================================================================
# BACKWARD COMPATIBILITY: Wrap old detect_regime interface
# =============================================================================

def detect_regime(returns: pd.DataFrame, window: int = 168, freq=None) -> str:
    """
    Backward-compatible wrapper for existing code.
    
    Maps new RegimeEngine output to old regime labels:
    - crisis/high_vol → "high_vol"
    - bull_trend/bear_trend → "trending"
    - low_vol_range → "mean_reverting"
    
    For new code, use RegimeEngine.detect() directly.
    """
    engine = RegimeEngine(vol_window_bars=window)
    
    # Create minimal prices DataFrame from returns (cumulative)
    prices = (1 + returns).cumprod()
    
    state = engine.detect(prices=prices, returns=returns, freq=freq)
    
    # Map new labels to old labels for backward compatibility
    label_map = {
        RegimeLabel.CRISIS: "high_vol",
        RegimeLabel.HIGH_VOL: "high_vol",
        RegimeLabel.BULL_TREND: "trending",
        RegimeLabel.BEAR_TREND: "trending",
        RegimeLabel.LOW_VOL_RANGE: "mean_reverting",
    }
    
    return label_map[state.label]
