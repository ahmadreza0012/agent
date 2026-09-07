import numpy as np
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging
logger = logging.getLogger(__name__)

@dataclass
class StrategyScore:
    method: str
    sharpe_percentile: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    consistency: float = 0.0
    regime_score: float = 0.0
    recent_score: float = 0.0
    confidence: float = 0.0
    correlation_penalty: float = 0.0
    turnover_penalty: float = 0.0
    final_score: float = 0.0
    
    @property
    def is_valid(self) -> bool:
        return np.all(np.isfinite([self.sharpe_percentile, self.sortino_ratio, self.max_drawdown, self.consistency, self.regime_score, self.recent_score, self.confidence, self.correlation_penalty, self.turnover_penalty]))

class StrategyScorer:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {'weights': {'sharpe_percentile': 0.25, 'sortino_ratio': 0.15, 'max_drawdown': 0.15, 'consistency': 0.15, 'regime_score': 0.15, 'recent_score': 0.10}, 'bounds': {'min_weight': 0.05, 'max_weight': 0.40, 'min_observations': 50, 'correlation_threshold': 0.70}}
        self.weights = self.config['weights']
        self.bounds = self.config['bounds']
    
    def calculate_score(self, method: str, historical_returns: List[float], sharpe: float, sortino: float, max_drawdown: float, current_regime: str, regime_performance: Dict[str, float], recent_returns: Optional[List[float]] = None, turnover: float = 0.0) -> StrategyScore:
        n_obs = len(historical_returns)
        score = StrategyScore(method=method)
        score.sharpe_percentile = np.clip((sharpe + 1.0) / 4.0, 0, 1)
        score.sortino_ratio = np.clip((sortino + 0.5) / 3.0, 0, 1)
        score.max_drawdown = np.clip(1.0 - abs(min(max_drawdown, 0.0)) * 2.0, 0, 1)
        score.consistency = self._consistency(historical_returns)
        score.regime_score = self._regime_score(regime_performance.get(current_regime, 0.0), current_regime)
        recent = recent_returns or historical_returns[-min(20, n_obs):]
        score.recent_score = self._recent_score(recent)
        score.confidence = self._confidence(n_obs)
        score.turnover_penalty = 0.20 if turnover > 0.50 else (0.10 if turnover > 0.30 else (0.05 if turnover > 0.15 else 0.0))
        score.final_score = self._final(score)
        return score
    
    def _consistency(self, returns: List[float]) -> float:
        if len(returns) < 10:
            return 0.5
        rolling = []
        for i in range(0, len(returns)-10, 5):
            w = returns[i:i+10]
            if np.std(w) > 0:
                rolling.append(np.mean(w) / np.std(w))
        if not rolling:
            return 0.5
        return np.clip(1.0 - min(1.0, np.std(rolling) / (abs(np.mean(rolling)) + 0.001)), 0, 1)
    
    def _regime_score(self, regime_return: float, regime: str) -> float:
        if regime in ['bull_trend', 'low_vol_range']:
            n = (regime_return + 0.05) / 0.10
        elif regime == 'bear_trend':
            n = (regime_return + 0.10) / 0.10
        elif regime == 'crisis':
            n = (regime_return + 0.15) / 0.10
        else:
            n = 1.0 - abs(regime_return) * 10.0
        return np.clip(n, 0, 1)
    
    def _recent_score(self, recent: List[float]) -> float:
        if not recent:
            return 0.5
        weights = np.exp(np.linspace(0, -1, len(recent)))
        weights /= weights.sum()
        wr = sum(w * r for w, r in zip(weights, recent))
        return np.clip((wr + 0.02) / 0.04, 0, 1)
    
    def _confidence(self, n: int) -> float:
        min_obs = self.bounds.get('min_observations', 50)
        return np.clip(min(1.0, n / min_obs * 0.5 if n < min_obs else 0.5 + (n - min_obs) / 150 * 0.5), 0, 1)
    
    def _final(self, score: StrategyScore) -> float:
        ws = sum(self.weights.get(k, 0) * getattr(score, k) for k in ['sharpe_percentile', 'sortino_ratio', 'max_drawdown', 'consistency', 'regime_score', 'recent_score'])
        penalty = (1.0 - score.confidence) * 0.25 + score.turnover_penalty * 0.5 + score.correlation_penalty * 0.3
        return np.clip(ws - penalty * ws, 0, 1)
    
    def calculate_correlation_penalty(self, histories: Dict[str, List[np.ndarray]]) -> Dict[str, float]:
        penalties = {}
        names = list(histories.keys())
        if len(names) < 2:
            return {n: 0.0 for n in names}
        mats = {}
        for n, h in histories.items():
            if h:
                flat = []
                for arr in h:
                    flat.extend(arr.flatten())
                mats[n] = np.array(flat)
        corrs = {}
        for i, n1 in enumerate(names):
            if n1 not in mats:
                continue
            for n2 in names[i+1:]:
                if n2 not in mats:
                    continue
                v1, v2 = mats[n1], mats[n2]
                if len(v1) == len(v2) and len(v1) > 0:
                    c = np.corrcoef(v1, v2)[0,1]
                    if not np.isnan(c):
                        corrs[(n1,n2)] = abs(c)
        thresh = self.bounds.get('correlation_threshold', 0.70)
        for n in names:
            total, cnt = 0.0, 0
            for (n1,n2), c in corrs.items():
                if n1 == n or n2 == n:
                    if c > thresh:
                        total += (c - thresh) * 2.0
                        cnt += 1
            penalties[n] = min(0.50, total / max(1, cnt)) if cnt > 0 else 0.0
        return penalties
    
    def apply_bounded_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        min_w = self.bounds.get('min_weight', 0.05)
        max_w = self.bounds.get('max_weight', 0.40)
        bounded = {n: np.clip(w, min_w, max_w) for n, w in weights.items()}
        total = sum(bounded.values())
        return {n: w / total for n, w in bounded.items()} if total > 0 else {n: 1.0/len(bounded) for n in bounded}
