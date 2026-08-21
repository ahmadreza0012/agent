import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging
logger = logging.getLogger(__name__)

@dataclass
class RobustnessMetrics:
    probability_loss: float; probability_dd_10: float; probability_dd_20: float
    var_95: float; var_99: float; cvar_95: float; median_cagr: float
    worst_percentile: float; best_percentile: float; probability_ruin: float

class RobustnessAnalyzer:
    def __init__(self, n_simulations: int = 1000, random_seed: int = 42):
        self.n_simulations = n_simulations; self.random_seed = random_seed
        np.random.seed(random_seed)
    
    def simulate(self, returns: np.ndarray, strategy_func: callable, perturb_params: Optional[Dict] = None, block_size: int = 20) -> Dict[str, np.ndarray]:
        n = len(returns); results = {'total_return': [], 'max_drawdown': [], 'sharpe': [], 'cagr': []}
        for _ in range(self.n_simulations):
            boot = self._block_bootstrap(returns, block_size)
            if perturb_params: boot = self._apply_perturbations(boot, perturb_params)
            metrics = self._calculate_metrics(boot)
            for k, v in metrics.items(): results[k].append(v)
        return {k: np.array(v) for k, v in results.items()}
    
    def _block_bootstrap(self, data: np.ndarray, block_size: int) -> np.ndarray:
        n = len(data); n_blocks = int(np.ceil(n / block_size))
        idx = np.random.randint(0, n - block_size + 1, n_blocks)
        result = []
        for i in idx: result.extend(data[i:i+block_size])
        return np.array(result[:n])
    
    def _apply_perturbations(self, returns: np.ndarray, params: Dict) -> np.ndarray:
        perturbed = returns.copy()
        if 'slippage' in params: perturbed *= 1.0 + np.random.randn() * params['slippage']
        if 'cost' in params: perturbed -= (1.0 + np.random.randn() * params['cost']) * 0.001
        return perturbed
    
    def _calculate_metrics(self, returns: np.ndarray) -> Dict[str, float]:
        cum = np.cumsum(returns); total = cum[-1]
        peak = np.maximum.accumulate(cum); dd = np.max(peak - cum)
        mean_ret, std_ret = np.mean(returns), np.std(returns)
        sharpe = (mean_ret / std_ret) * np.sqrt(252) if std_ret > 0 else 0
        n_years = len(returns) / 252
        cagr = (1 + total) ** (1 / n_years) - 1 if n_years > 0 else 0
        return {'total_return': total, 'max_drawdown': dd, 'sharpe': sharpe, 'cagr': cagr}
    
    def calculate_robustness_metrics(self, results: Dict) -> RobustnessMetrics:
        tr = results['total_return']; dd = results['max_drawdown']
        return RobustnessMetrics(probability_loss=np.mean(tr < 0), probability_dd_10=np.mean(dd > 0.10), probability_dd_20=np.mean(dd > 0.20), var_95=np.percentile(tr, 5), var_99=np.percentile(tr, 1), cvar_95=np.mean(tr[tr <= np.percentile(tr, 5)]), median_cagr=np.percentile(results['cagr'], 50), worst_percentile=np.percentile(tr, 5), best_percentile=np.percentile(tr, 95), probability_ruin=np.mean(tr < -0.50))
