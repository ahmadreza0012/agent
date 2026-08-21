"""
Robustness Analyzer - Monte Carlo and Statistical Robustness Framework
======================================================================

Provides comprehensive robustness analysis for portfolio strategies including:
- Bootstrap resampling of returns (block bootstrap to preserve autocorrelation)
- Parameter perturbation analysis
- Scenario analysis (stress testing)
- Probability distributions of key metrics
- Confidence intervals
- Ruin probability calculations
- Recovery time analysis

Author: Quantitative Development Team
Phase: 12 - Monte Carlo / Robustness
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass
import logging
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class SimulationResult:
    """Container for a single simulation result."""
    sharpe_ratio: float
    total_return: float
    max_drawdown: float
    cvar_95: float
    win_rate: float
    calmar_ratio: float
    sortino_ratio: float
    parameters_used: Dict
    scenario_name: str


@dataclass
class DistributionSummary:
    """Summary statistics for a metric distribution."""
    mean: float
    median: float
    std: float
    percentile_5: float
    percentile_25: float
    percentile_50: float
    percentile_75: float
    percentile_95: float
    min_value: float
    max_value: float
    probability_positive: float
    skewness: float
    kurtosis: float


# Predefined stress test scenarios
SCENARIOS = {
    'baseline': {
        'volatility_multiplier': 1.0,
        'correlation_spike': 0.0,
        'liquidity_reduction': 0.0,
        'impact_multiplier': 1.0,
        'description': 'No perturbation - baseline scenario'
    },
    'high_vol': {
        'volatility_multiplier': 2.0,
        'correlation_spike': 0.0,
        'liquidity_reduction': 0.0,
        'impact_multiplier': 1.0,
        'description': '2x volatility regime'
    },
    'crisis': {
        'volatility_multiplier': 3.0,
        'correlation_spike': 0.3,
        'liquidity_reduction': 0.0,
        'impact_multiplier': 1.5,
        'description': '3x volatility + correlation spike + higher impact'
    },
    'low_liquidity': {
        'volatility_multiplier': 1.0,
        'correlation_spike': 0.0,
        'liquidity_reduction': 0.5,
        'impact_multiplier': 2.0,
        'description': '50% volume reduction + 2x market impact'
    },
    'spike_impact': {
        'volatility_multiplier': 1.0,
        'correlation_spike': 0.0,
        'liquidity_reduction': 0.0,
        'impact_multiplier': 3.0,
        'description': '3x market impact costs'
    },
    'mild_downturn': {
        'volatility_multiplier': 1.5,
        'correlation_spike': 0.15,
        'liquidity_reduction': 0.2,
        'impact_multiplier': 1.2,
        'description': 'Mild market downturn with elevated volatility'
    }
}


class RobustnessAnalyzer:
    """
    Monte Carlo and robustness analysis for portfolio strategies.
    
    This class provides comprehensive statistical analysis of strategy 
    performance through multiple simulation techniques:
    
    1. **Bootstrap Resampling**: Block bootstrap preserves autocorrelation
       structure in returns while generating alternative return paths.
    
    2. **Parameter Perturbation**: Tests sensitivity to changes in key
       parameters (transaction costs, liquidity limits, etc.).
    
    3. **Scenario Analysis**: Stress tests under predefined market regimes
       (crisis, high vol, low liquidity, etc.).
    
    4. **Probability Distributions**: Calculates full distributions and
       confidence intervals for all key metrics.
    
    5. **Ruin Analysis**: Estimates probability of capital falling below
       critical thresholds and expected recovery times.
    
    Attributes:
        backtester: Backtester instance to analyze
        n_simulations: Number of Monte Carlo simulations (default 1000)
        block_size: Block size for block bootstrap (default 20 days)
        results: Dictionary storing all simulation results
    
    Example:
        >>> analyzer = RobustnessAnalyzer(backtester, n_simulations=1000)
        >>> results = analyzer.run_bootstrap_analysis(returns_df)
        >>> report = analyzer.generate_report()
        >>> print(report['summary'])
    """
    
    def __init__(self, backtester, n_simulations: int = 1000, block_size: int = 20):
        """
        Initialize the RobustnessAnalyzer.
        
        Args:
            backtester: Backtester instance to analyze
            n_simulations: Number of Monte Carlo simulations (default 1000)
            block_size: Block size for block bootstrap in days (default 20)
                       Should be large enough to capture autocorrelation
        """
        self.backtester = backtester
        self.n_simulations = n_simulations
        self.block_size = block_size
        self.results: Dict[str, List[SimulationResult]] = {}
        self.distributions: Dict[str, DistributionSummary] = {}
        self.scenario_results: Dict[str, List[SimulationResult]] = {}
        
        logger.info(f"Initialized RobustnessAnalyzer with {n_simulations} simulations, "
                   f"block_size={block_size} days")
    
    def bootstrap_returns(self, returns: pd.DataFrame, 
                          n_simulations: Optional[int] = None,
                          block_size: Optional[int] = None) -> np.ndarray:
        """
        Generate bootstrap samples of returns using block bootstrap.
        
        Block bootstrap preserves the autocorrelation structure in returns
        by sampling contiguous blocks rather than individual observations.
        This is critical for financial time series which exhibit serial
        correlation in volatility and returns.
        
        Args:
            returns: DataFrame of asset returns (shape: n_periods x n_assets)
            n_simulations: Number of bootstrap samples (overrides default if provided)
            block_size: Block size in days (overrides default if provided)
        
        Returns:
            Array of shape (n_simulations, n_periods, n_assets) containing
            bootstrap-sampled return paths
        
        Notes:
            - Uses overlapping blocks (stationary bootstrap approach)
            - Block count is calculated to cover the full sample period
            - Random starting points ensure proper sampling distribution
        
        References:
            Künsch, H.R. (1989). The Jackknife and the Bootstrap for General
            Stationary Observations. Annals of Statistics, 17(3), 1217-1241.
        """
        n_sim = n_simulations or self.n_simulations
        b_size = block_size or self.block_size
        
        returns_array = returns.values
        n_periods, n_assets = returns_array.shape
        
        # Calculate number of blocks needed
        n_blocks = int(np.ceil(n_periods / b_size))
        
        # Maximum starting index for blocks
        max_start = n_periods - b_size
        
        bootstrap_samples = np.zeros((n_sim, n_periods, n_assets))
        
        for sim_idx in range(n_sim):
            # Generate random block starts
            block_starts = np.random.randint(0, max_start + 1, size=n_blocks)
            
            # Concatenate blocks
            sampled_returns = []
            for start in block_starts:
                end = min(start + b_size, n_periods)
                sampled_returns.append(returns_array[start:end])
            
            # Concatenate and trim to original length
            concatenated = np.vstack(sampled_returns)
            bootstrap_samples[sim_idx] = concatenated[:n_periods]
        
        logger.info(f"Generated {n_sim} bootstrap samples with block_size={b_size}")
        return bootstrap_samples
    
    def run_bootstrap_analysis(self, returns: pd.DataFrame,
                               weights: Optional[np.ndarray] = None,
                               n_simulations: Optional[int] = None) -> Dict[str, List[float]]:
        """
        Run full bootstrap analysis and compute metric distributions.
        
        For each bootstrap sample:
        1. Apply portfolio weights (or use equal weights if not provided)
        2. Calculate portfolio returns
        3. Compute performance metrics (Sharpe, drawdown, etc.)
        4. Store results for distribution analysis
        
        Args:
            returns: DataFrame of asset returns
            weights: Optional array of portfolio weights (default: equal weight)
            n_simulations: Number of simulations (optional override)
        
        Returns:
            Dictionary mapping metric names to lists of simulated values:
            {
                'sharpe_ratio': [...],
                'total_return': [...],
                'max_drawdown': [...],
                ...
            }
        """
        n_sim = n_simulations or self.n_simulations
        
        if weights is None:
            # Equal weight portfolio
            n_assets = returns.shape[1]
            weights = np.ones(n_assets) / n_assets
        
        # Generate bootstrap samples
        bootstrap_samples = self.bootstrap_returns(returns, n_simulations=n_sim)
        
        # Storage for metrics
        metrics = {
            'sharpe_ratio': [],
            'total_return': [],
            'max_drawdown': [],
            'cvar_95': [],
            'win_rate': [],
            'calmar_ratio': [],
            'sortino_ratio': []
        }
        
        for sim_idx in range(n_sim):
            sim_returns = bootstrap_samples[sim_idx]
            
            # Portfolio returns
            port_returns = sim_returns @ weights
            
            # Calculate metrics
            metrics['sharpe_ratio'].append(self._calculate_sharpe(port_returns))
            metrics['total_return'].append(self._calculate_total_return(port_returns))
            metrics['max_drawdown'].append(self._calculate_max_drawdown(port_returns))
            metrics['cvar_95'].append(self._calculate_cvar(port_returns))
            metrics['win_rate'].append(self._calculate_win_rate(port_returns))
            
            dd = self._calculate_max_drawdown(port_returns)
            metrics['calmar_ratio'].append(
                self._calculate_annualized_return(port_returns) / max(dd, 0.01)
            )
            metrics['sortino_ratio'].append(self._calculate_sortino(port_returns))
        
        self.results['bootstrap'] = [
            SimulationResult(
                sharpe_ratio=metrics['sharpe_ratio'][i],
                total_return=metrics['total_return'][i],
                max_drawdown=metrics['max_drawdown'][i],
                cvar_95=metrics['cvar_95'][i],
                win_rate=metrics['win_rate'][i],
                calmar_ratio=metrics['calmar_ratio'][i],
                sortino_ratio=metrics['sortino_ratio'][i],
                parameters_used={},
                scenario_name='bootstrap'
            )
            for i in range(n_sim)
        ]
        
        logger.info(f"Completed bootstrap analysis with {n_sim} simulations")
        return metrics
    
    def perturb_parameters(self, base_params: Dict,
                           perturbation_scale: float = 0.10) -> Dict:
        """
        Perturb parameters by random factors for sensitivity analysis.
        
        Each parameter is multiplied by a random factor drawn from a
        log-normal distribution centered at 1.0 with specified scale.
        This ensures parameters stay positive and allows asymmetric perturbations.
        
        Parameters perturbed:
        - transaction_cost
        - slippage
        - rebalance_frequency (discrete)
        - lookback_hours
        - max_position_pct_of_adv
        - max_volume_participation
        
        Args:
            base_params: Dictionary of base parameter values
            perturbation_scale: Standard deviation of log-normal perturbation
                              (default 0.10 = 10% typical deviation)
        
        Returns:
            Dictionary of perturbed parameter values
        
        Notes:
            - Uses log-normal distribution to ensure positive values
            - Discrete parameters (like rebalance_frequency) are rounded
            - Scale of 0.10 means ~68% of perturbations are within ±10%
        """
        perturbed = {}
        
        for param, value in base_params.items():
            if isinstance(value, bool):
                # Don't perturb booleans
                perturbed[param] = value
            elif isinstance(value, int):
                # Integer parameters: perturb then round
                if 'frequency' in param.lower() or 'hours' in param.lower():
                    # Time-based integers: use multiplicative perturbation
                    factor = np.exp(np.random.normal(0, perturbation_scale))
                    perturbed[param] = max(1, int(round(value * factor)))
                else:
                    perturbed[param] = value
            elif isinstance(value, float):
                # Float parameters: log-normal perturbation
                factor = np.exp(np.random.normal(0, perturbation_scale))
                perturbed[param] = max(0.0001, value * factor)  # Ensure positive
            else:
                perturbed[param] = value
        
        return perturbed
    
    def run_parameter_perturbation(self, base_params: Dict,
                                   returns: pd.DataFrame,
                                   weights: Optional[np.ndarray] = None,
                                   n_simulations: Optional[int] = None,
                                   perturbation_scale: float = 0.10) -> Dict[str, List[float]]:
        """
        Run analysis with perturbed parameters to test sensitivity.
        
        For each simulation:
        1. Perturb all parameters randomly
        2. Adjust returns based on parameter changes (e.g., higher costs)
        3. Calculate performance metrics
        4. Record how metrics vary with parameter changes
        
        Args:
            base_params: Base parameter dictionary
            returns: Asset returns DataFrame
            weights: Portfolio weights (optional, default equal weight)
            n_simulations: Number of simulations
            perturbation_scale: Scale of parameter perturbations
        
        Returns:
            Dictionary of metric distributions under parameter uncertainty
        """
        n_sim = n_simulations or self.n_simulations
        
        if weights is None:
            n_assets = returns.shape[1]
            weights = np.ones(n_assets) / n_assets
        
        metrics = {
            'sharpe_ratio': [],
            'total_return': [],
            'max_drawdown': [],
            'cvar_95': [],
            'win_rate': []
        }
        
        for sim_idx in range(n_sim):
            # Perturb parameters
            perturbed_params = self.perturb_parameters(base_params, perturbation_scale)
            
            # Adjust returns for changed costs
            adjusted_returns = self._adjust_returns_for_costs(
                returns.values,
                base_params,
                perturbed_params
            )
            
            # Portfolio returns
            port_returns = adjusted_returns @ weights
            
            # Calculate metrics
            metrics['sharpe_ratio'].append(self._calculate_sharpe(port_returns))
            metrics['total_return'].append(self._calculate_total_return(port_returns))
            metrics['max_drawdown'].append(self._calculate_max_drawdown(port_returns))
            metrics['cvar_95'].append(self._calculate_cvar(port_returns))
            metrics['win_rate'].append(self._calculate_win_rate(port_returns))
        
        self.results['parameter_perturbation'] = [
            SimulationResult(
                sharpe_ratio=metrics['sharpe_ratio'][i],
                total_return=metrics['total_return'][i],
                max_drawdown=metrics['max_drawdown'][i],
                cvar_95=metrics['cvar_95'][i],
                win_rate=metrics['win_rate'][i],
                calmar_ratio=0.0,  # Not calculated for efficiency
                sortino_ratio=0.0,
                parameters_used=self.perturb_parameters(base_params, perturbation_scale),
                scenario_name='parameter_perturbation'
            )
            for i in range(n_sim)
        ]
        
        logger.info(f"Completed parameter perturbation analysis with {n_sim} simulations")
        return metrics
    
    def _adjust_returns_for_costs(self, returns: np.ndarray,
                                   base_params: Dict,
                                   perturbed_params: Dict) -> np.ndarray:
        """
        Adjust returns based on changes in cost parameters.
        
        Higher transaction costs and slippage reduce net returns.
        This method applies those adjustments to the return series.
        
        Args:
            returns: Raw returns array (n_periods x n_assets)
            base_params: Original parameter values
            perturbed_params: Perturbed parameter values
        
        Returns:
            Adjusted returns array
        """
        # Get cost parameters
        base_cost = base_params.get('transaction_cost', 0.001)
        perturbed_cost = perturbed_params.get('transaction_cost', 0.001)
        
        base_slippage = base_params.get('slippage', 0.0005)
        perturbed_slippage = perturbed_params.get('slippage', 0.0005)
        
        # Assume average turnover of 20% per period
        avg_turnover = 0.20
        
        # Cost difference per period
        cost_diff = (perturbed_cost - base_cost + perturbed_slippage - base_slippage) * avg_turnover
        
        # Adjust returns (costs reduce returns)
        adjusted = returns.copy()
        adjusted -= cost_diff
        
        return adjusted
    
    def apply_scenario(self, returns: pd.DataFrame,
                       scenario_name: str) -> np.ndarray:
        """
        Apply stress scenario to returns.
        
        Scenarios modify returns based on predefined stress factors:
        - Volatility multiplier: scales return magnitude
        - Correlation spike: increases cross-asset correlation
        - Liquidity reduction: reduces effective returns via higher costs
        - Impact multiplier: increases market impact costs
        
        Args:
            returns: DataFrame of asset returns
            scenario_name: Name of scenario from SCENARIOS dict
        
        Returns:
            Stressed returns array
        
        Raises:
            ValueError: If scenario_name not found in SCENARIOS
        """
        if scenario_name not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario_name}. "
                           f"Available: {list(SCENARIOS.keys())}")
        
        scenario = SCENARIOS[scenario_name]
        returns_array = returns.values.copy()
        
        # Apply volatility multiplier
        vol_mult = scenario['volatility_multiplier']
        if vol_mult != 1.0:
            returns_array *= vol_mult
        
        # Apply correlation spike (simplified: add common shock)
        corr_spike = scenario['correlation_spike']
        if corr_spike > 0:
            n_periods, n_assets = returns_array.shape
            # Add correlated component
            common_shock = np.random.normal(0, corr_spike, n_periods).reshape(-1, 1)
            returns_array += common_shock * np.ones((n_periods, n_assets)) * 0.1
        
        # Apply liquidity/impact effects (reduce returns)
        liq_reduction = scenario['liquidity_reduction']
        impact_mult = scenario['impact_multiplier']
        
        if liq_reduction > 0 or impact_mult > 1.0:
            # Estimate additional cost from reduced liquidity and higher impact
            base_cost = 0.001  # Base transaction cost
            additional_cost = base_cost * (liq_reduction + (impact_mult - 1.0))
            returns_array -= additional_cost
        
        logger.info(f"Applied scenario '{scenario_name}': {scenario['description']}")
        return returns_array
    
    def run_scenario_analysis(self, returns: pd.DataFrame,
                              weights: Optional[np.ndarray] = None,
                              scenarios: Optional[List[str]] = None,
                              n_simulations_per_scenario: int = 100) -> Dict[str, Dict[str, List[float]]]:
        """
        Run scenario analysis across multiple stress scenarios.
        
        For each scenario:
        1. Apply stress factors to historical returns
        2. Run Monte Carlo simulations on stressed returns
        3. Calculate metric distributions
        4. Compare to baseline
        
        Args:
            returns: Historical asset returns
            weights: Portfolio weights (optional)
            scenarios: List of scenario names to test (default: all)
            n_simulations_per_scenario: Simulations per scenario
        
        Returns:
            Nested dictionary: {scenario_name: {metric_name: [values]}}
        """
        if scenarios is None:
            scenarios = list(SCENARIOS.keys())
        
        if weights is None:
            n_assets = returns.shape[1]
            weights = np.ones(n_assets) / n_assets
        
        all_results = {}
        
        for scenario_name in scenarios:
            logger.info(f"Running scenario: {scenario_name}")
            
            # Apply scenario stress
            stressed_returns = self.apply_scenario(returns, scenario_name)
            
            # Run Monte Carlo on stressed returns
            metrics = {
                'sharpe_ratio': [],
                'total_return': [],
                'max_drawdown': [],
                'cvar_95': [],
                'win_rate': []
            }
            
            for _ in range(n_simulations_per_scenario):
                # Add noise to simulate path uncertainty
                noise = np.random.normal(0, 0.01, stressed_returns.shape)
                noisy_returns = stressed_returns + noise
                
                port_returns = noisy_returns @ weights
                
                metrics['sharpe_ratio'].append(self._calculate_sharpe(port_returns))
                metrics['total_return'].append(self._calculate_total_return(port_returns))
                metrics['max_drawdown'].append(self._calculate_max_drawdown(port_returns))
                metrics['cvar_95'].append(self._calculate_cvar(port_returns))
                metrics['win_rate'].append(self._calculate_win_rate(port_returns))
            
            all_results[scenario_name] = metrics
            
            # Store for later analysis
            self.scenario_results[scenario_name] = [
                SimulationResult(
                    sharpe_ratio=metrics['sharpe_ratio'][i],
                    total_return=metrics['total_return'][i],
                    max_drawdown=metrics['max_drawdown'][i],
                    cvar_95=metrics['cvar_95'][i],
                    win_rate=metrics['win_rate'][i],
                    calmar_ratio=0.0,
                    sortino_ratio=0.0,
                    parameters_used={},
                    scenario_name=scenario_name
                )
                for i in range(n_simulations_per_scenario)
            ]
        
        return all_results
    
    def calculate_distributions(self, metrics: Dict[str, List[float]]) -> Dict[str, DistributionSummary]:
        """
        Calculate comprehensive distribution statistics for metrics.
        
        For each metric, calculates:
        - Mean, median, standard deviation
        - Percentiles: 5th, 25th, 50th, 75th, 95th
        - Min, max values
        - Probability of positive value
        - Skewness and kurtosis
        
        Args:
            metrics: Dictionary mapping metric names to value lists
        
        Returns:
            Dictionary mapping metric names to DistributionSummary objects
        """
        distributions = {}
        
        for metric_name, values in metrics.items():
            values_arr = np.array(values)
            
            distributions[metric_name] = DistributionSummary(
                mean=float(np.mean(values_arr)),
                median=float(np.median(values_arr)),
                std=float(np.std(values_arr)),
                percentile_5=float(np.percentile(values_arr, 5)),
                percentile_25=float(np.percentile(values_arr, 25)),
                percentile_50=float(np.percentile(values_arr, 50)),
                percentile_75=float(np.percentile(values_arr, 75)),
                percentile_95=float(np.percentile(values_arr, 95)),
                min_value=float(np.min(values_arr)),
                max_value=float(np.max(values_arr)),
                probability_positive=float(np.mean(values_arr > 0)),
                skewness=float(stats.skew(values_arr)),
                kurtosis=float(stats.kurtosis(values_arr))
            )
        
        self.distributions.update(distributions)
        return distributions
    
    def calculate_ruin_probability(self, returns: np.ndarray,
                                    initial_capital: float = 100000,
                                    ruin_threshold: float = 0.50,
                                    n_simulations: Optional[int] = None) -> Dict:
        """
        Calculate probability of ruin and recovery statistics.
        
        Ruin is defined as cumulative capital falling below a threshold
        (e.g., 50% of initial capital). This method estimates:
        
        1. Probability of ruin occurring
        2. Expected time to ruin (if it occurs)
        3. Distribution of maximum drawdowns
        4. Recovery time statistics
        
        Args:
            returns: Array of portfolio returns
            initial_capital: Starting capital amount
            ruin_threshold: Fraction of initial capital considered "ruin"
                           (default 0.50 = 50% loss)
            n_simulations: Number of bootstrap simulations
        
        Returns:
            Dictionary containing:
            - ruin_probability: P(capital < threshold)
            - expected_time_to_ruin: Expected periods until ruin
            - recovery_time_mean: Average time to recover from ruin
            - recovery_time_median: Median recovery time
            - max_drawdown_distribution: Stats on worst drawdowns
        """
        n_sim = n_simulations or self.n_simulations
        n_periods = len(returns)
        
        ruin_level = initial_capital * ruin_threshold
        
        ruin_count = 0
        times_to_ruin = []
        recovery_times = []
        max_drawdowns = []
        
        for _ in range(n_sim):
            # Bootstrap sample
            indices = np.random.choice(n_periods, n_periods, replace=True)
            sampled_returns = returns[indices]
            
            # Calculate cumulative capital path
            cum_returns = np.cumprod(1 + sampled_returns)
            capital_path = initial_capital * cum_returns
            
            # Check for ruin
            if np.any(capital_path < ruin_level):
                ruin_count += 1
                # Time to first ruin
                ruin_time = np.argmax(capital_path < ruin_level)
                times_to_ruin.append(ruin_time)
                
                # Recovery time (if recovers)
                post_ruin = capital_path[ruin_time:]
                if np.any(post_ruin > initial_capital):
                    recovery_time = np.argmax(post_ruin > initial_capital)
                    recovery_times.append(recovery_time)
            
            # Max drawdown
            running_max = np.maximum.accumulate(capital_path)
            drawdowns = (running_max - capital_path) / running_max
            max_drawdowns.append(np.max(drawdowns))
        
        ruin_prob = ruin_count / n_sim
        
        result = {
            'ruin_probability': ruin_prob,
            'expected_time_to_ruin': float(np.mean(times_to_ruin)) if times_to_ruin else None,
            'recovery_time_mean': float(np.mean(recovery_times)) if recovery_times else None,
            'recovery_time_median': float(np.median(recovery_times)) if recovery_times else None,
            'max_drawdown_mean': float(np.mean(max_drawdowns)),
            'max_drawdown_median': float(np.median(max_drawdowns)),
            'max_drawdown_95th': float(np.percentile(max_drawdowns, 95)),
            'n_simulations': n_sim,
            'ruin_level_usd': ruin_level,
            'ruin_threshold_pct': ruin_threshold
        }
        
        logger.info(f"Ruin probability: {ruin_prob:.2%} "
                   f"(threshold: {ruin_threshold:.0%} of ${initial_capital:,})")
        return result
    
    def generate_report(self) -> Dict:
        """
        Generate comprehensive robustness report.
        
        Compiles all analysis results into a structured report including:
        - Summary statistics
        - Confidence intervals for all metrics
        - Scenario comparison
        - Ruin probabilities
        - Recommendations based on robustness
        
        Returns:
            Dictionary containing:
            {
                'summary': Key findings and metrics,
                'distributions': Full distribution summaries,
                'confidence_intervals': 90% CI for key metrics,
                'scenarios': Scenario analysis results,
                'ruin_analysis': Ruin probability and recovery stats,
                'recommendation': Actionable recommendation string
            }
        
        Example:
            >>> report = analyzer.generate_report()
            >>> print(f"90% CI for Sharpe: [{report['confidence_intervals']['sharpe_90_ci'][0]:.2f}, "
            ...       f"{report['confidence_intervals']['sharpe_90_ci'][1]:.2f}]")
        """
        report = {
            'summary': {},
            'distributions': {},
            'confidence_intervals': {},
            'scenarios': {},
            'ruin_analysis': {},
            'recommendation': ''
        }
        
        # Process bootstrap results
        if 'bootstrap' in self.results and self.results['bootstrap']:
            bootstrap_results = self.results['bootstrap']
            
            # Extract metrics
            metrics_dict = {
                'sharpe_ratio': [r.sharpe_ratio for r in bootstrap_results],
                'total_return': [r.total_return for r in bootstrap_results],
                'max_drawdown': [r.max_drawdown for r in bootstrap_results],
                'cvar_95': [r.cvar_95 for r in bootstrap_results],
                'win_rate': [r.win_rate for r in bootstrap_results]
            }
            
            # Calculate distributions
            dists = self.calculate_distributions(metrics_dict)
            
            # Summary
            report['summary'] = {
                'n_simulations': len(bootstrap_results),
                'sharpe_mean': dists['sharpe_ratio'].mean,
                'sharpe_median': dists['sharpe_ratio'].median,
                'sharpe_std': dists['sharpe_ratio'].std,
                'return_mean': dists['total_return'].mean,
                'max_drawdown_median': dists['max_drawdown'].median,
                'probability_positive_return': dists['total_return'].probability_positive,
                'probability_profitable_strategy': dists['sharpe_ratio'].probability_positive
            }
            
            # Confidence intervals (90%)
            report['confidence_intervals'] = {
                'sharpe_90_ci': (dists['sharpe_ratio'].percentile_5, 
                                dists['sharpe_ratio'].percentile_95),
                'return_90_ci': (dists['total_return'].percentile_5,
                               dists['total_return'].percentile_95),
                'drawdown_90_ci': (dists['max_drawdown'].percentile_5,
                                 dists['max_drawdown'].percentile_95)
            }
            
            # Convert distributions to dicts for JSON serialization
            report['distributions'] = {
                name: {
                    'mean': d.mean,
                    'median': d.median,
                    'std': d.std,
                    'p5': d.percentile_5,
                    'p25': d.percentile_25,
                    'p50': d.percentile_50,
                    'p75': d.percentile_75,
                    'p95': d.percentile_95,
                    'prob_positive': d.probability_positive
                }
                for name, d in dists.items()
            }
        
        # Scenario results
        if self.scenario_results:
            report['scenarios'] = {}
            for scenario_name, results in self.scenario_results.items():
                if results:
                    sharpe_values = [r.sharpe_ratio for r in results]
                    return_values = [r.total_return for r in results]
                    
                    report['scenarios'][scenario_name] = {
                        'description': SCENARIOS.get(scenario_name, {}).get('description', ''),
                        'sharpe_mean': float(np.mean(sharpe_values)),
                        'sharpe_median': float(np.median(sharpe_values)),
                        'return_mean': float(np.mean(return_values)),
                        'return_median': float(np.median(return_values)),
                        'n_simulations': len(results)
                    }
        
        # Recommendation logic
        if report['summary']:
            sharpe_median = report['summary'].get('sharpe_median', 0)
            ruin_prob = report.get('ruin_analysis', {}).get('ruin_probability', 0)
            
            if sharpe_median > 1.0 and ruin_prob < 0.10:
                report['recommendation'] = (
                    "STRATEGY APPEARS ROBUST: High median Sharpe ratio with low ruin probability. "
                    "Confidence intervals suggest consistent performance across simulations."
                )
            elif sharpe_median > 0.5 and ruin_prob < 0.25:
                report['recommendation'] = (
                    "MODERATE CONFIDENCE: Strategy shows positive expectancy but monitor drawdowns. "
                    "Consider position sizing adjustments to reduce tail risk."
                )
            elif sharpe_median < 0:
                report['recommendation'] = (
                    "WARNING: Negative median Sharpe ratio suggests strategy may not be profitable. "
                    "Review strategy logic and parameter choices before deployment."
                )
            else:
                report['recommendation'] = (
                    "CAUTION ADVISED: Elevated ruin probability or wide confidence intervals. "
                    "Reduce position sizes and implement strict risk controls."
                )
        
        return report
    
    # =========================================================================
    # Helper Methods - Metric Calculations
    # =========================================================================
    
    def _calculate_sharpe(self, returns: np.ndarray, annualization: int = 252) -> float:
        """Calculate annualized Sharpe ratio (assuming RF=0)."""
        if len(returns) < 2 or np.std(returns) == 0:
            return 0.0
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        if std_return == 0:
            return 0.0
        return (mean_return / std_return) * np.sqrt(annualization)
    
    def _calculate_total_return(self, returns: np.ndarray) -> float:
        """Calculate cumulative total return."""
        return float(np.prod(1 + returns) - 1)
    
    def _calculate_annualized_return(self, returns: np.ndarray, 
                                     annualization: int = 252) -> float:
        """Calculate annualized return."""
        total_return = self._calculate_total_return(returns)
        n_periods = len(returns)
        if n_periods == 0:
            return 0.0
        return ((1 + total_return) ** (annualization / n_periods)) - 1
    
    def _calculate_max_drawdown(self, returns: np.ndarray) -> float:
        """Calculate maximum drawdown from return series."""
        if len(returns) == 0:
            return 0.0
        
        cum_returns = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cum_returns)
        drawdowns = (running_max - cum_returns) / running_max
        return float(np.max(drawdowns))
    
    def _calculate_cvar(self, returns: np.ndarray, confidence: float = 0.95) -> float:
        """Calculate Conditional Value at Risk (Expected Shortfall)."""
        if len(returns) == 0:
            return 0.0
        
        var_threshold = np.percentile(returns, (1 - confidence) * 100)
        tail_returns = returns[returns <= var_threshold]
        
        if len(tail_returns) == 0:
            return -var_threshold
        
        return float(-np.mean(tail_returns))
    
    def _calculate_win_rate(self, returns: np.ndarray) -> float:
        """Calculate win rate (percentage of positive returns)."""
        if len(returns) == 0:
            return 0.0
        return float(np.mean(returns > 0))
    
    def _calculate_sortino(self, returns: np.ndarray, annualization: int = 252) -> float:
        """Calculate Sortino ratio (downside deviation)."""
        if len(returns) < 2:
            return 0.0
        
        mean_return = np.mean(returns)
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0:
            return float('inf') if mean_return > 0 else 0.0
        
        downside_std = np.std(downside_returns)
        if downside_std == 0:
            return 0.0
        
        return (mean_return / downside_std) * np.sqrt(annualization)
