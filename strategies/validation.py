"""
Strategy Validation Framework for Phase 30: Strategy Robustness

This module provides comprehensive validation of trading strategies to ensure
they are robust, economically sound, and generalize well out-of-sample.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple
from enum import Enum
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    """Status of strategy validation."""
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
    REJECTED = "rejected"


@dataclass
class StrategyHypothesis:
    """
    Define the hypothesis for a strategy.
    
    Every strategy must have a clear economic rationale before validation.
    """
    name: str
    description: str
    economic_rationale: str  # Why should this work?
    expected_mechanism: str  # How does it capture returns?
    expected_regimes: List[str]  # When should it work?
    risk_factors: List[str]  # What can go wrong?
    dependencies: List[str]  # What does it depend on?
    market_inefficiency: str = ""  # What inefficiency does it exploit?
    expected_turnover: str = ""  # Expected turnover characteristics


@dataclass
class ValidationResult:
    """Results of strategy validation."""
    strategy_name: str
    status: ValidationStatus
    score: float  # Overall robustness score (0-1)
    metrics: Dict[str, float]
    reasons: List[str]
    recommendations: List[str]
    timestamp: str
    validation_details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'strategy_name': self.strategy_name,
            'status': self.status.value,
            'score': self.score,
            'metrics': self.metrics,
            'reasons': self.reasons,
            'recommendations': self.recommendations,
            'timestamp': self.timestamp,
            'validation_details': self.validation_details,
        }


class StrategyRobustnessValidator:
    """
    Validate strategy robustness across multiple dimensions.
    
    This validator tests strategies across:
    1. Economic rationale
    2. In-sample performance
    3. Out-of-sample performance
    4. Regime-specific performance
    5. Parameter sensitivity
    6. Transaction cost impact
    7. Benchmark comparison
    
    A strategy must pass all critical tests to be approved for production.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the validator with configuration.
        
        Args:
            config: Configuration dictionary with thresholds
        """
        self.config = config or {}
        
        # Minimum requirements
        self.min_oos_years = self.config.get('min_oos_years', 1.0)
        self.min_sharpe_threshold = self.config.get('min_sharpe', 0.5)
        self.max_drawdown_threshold = self.config.get('max_drawdown', 0.25)
        self.min_cost_adjusted_sharpe = self.config.get('min_cost_adjusted_sharpe', 0.3)
        self.min_regime_consistency = self.config.get('min_regime_consistency', 0.6)
        self.min_param_robustness = self.config.get('min_param_robustness', 0.6)
        
        # Parameter testing range
        self.param_variation_pct = self.config.get('param_variation_pct', 0.2)
        self.n_param_variations = self.config.get('n_param_variations', 5)
        
        logger.info(f"StrategyRobustnessValidator initialized with thresholds:")
        logger.info(f"  Min OOS Sharpe: {self.min_sharpe_threshold}")
        logger.info(f"  Max Drawdown: {self.max_drawdown_threshold}")
        logger.info(f"  Min Cost-Adjusted Sharpe: {self.min_cost_adjusted_sharpe}")
    
    def validate_strategy(
        self,
        strategy: Any,
        data: pd.DataFrame,
        oos_data: pd.DataFrame,
        transaction_costs: float = 0.001,
        benchmark_data: Optional[pd.DataFrame] = None,
    ) -> ValidationResult:
        """
        Validate a strategy across multiple dimensions.
        
        Args:
            strategy: Strategy instance to validate (must have generate_signals method)
            data: Training/in-sample data
            oos_data: Out-of-sample data (completely separate from training data)
            transaction_costs: Estimated transaction costs (default 0.1%)
            benchmark_data: Optional benchmark data for comparison
            
        Returns:
            ValidationResult with status, score, and detailed metrics
        """
        reasons = []
        recommendations = []
        validation_details = {}
        
        # 1. Economic rationale check (CRITICAL - must pass)
        logger.info(f"Validating strategy: {strategy.name}")
        has_rationale, rationale_reason = self._check_economic_rationale(strategy)
        if not has_rationale:
            return ValidationResult(
                strategy_name=strategy.name,
                status=ValidationStatus.REJECTED,
                score=0.0,
                metrics={},
                reasons=["No economic rationale provided"],
                recommendations=["Define clear economic rationale with StrategyHypothesis before validation"],
                timestamp=datetime.now().isoformat(),
                validation_details={'rationale_check': False}
            )
        
        validation_details['rationale_check'] = True
        
        # 2. In-sample performance (baseline)
        logger.info("Calculating in-sample metrics...")
        is_metrics = self._calculate_metrics(strategy, data, "in_sample")
        validation_details['in_sample'] = is_metrics
        
        # 3. Out-of-sample performance (CRITICAL)
        logger.info("Calculating out-of-sample metrics...")
        oos_metrics = self._calculate_metrics(strategy, oos_data, "out_of_sample")
        validation_details['out_of_sample'] = oos_metrics
        
        # 4. Regime-specific performance
        logger.info("Testing regime consistency...")
        regime_metrics = self._evaluate_by_regime(strategy, oos_data)
        validation_details['regime_performance'] = regime_metrics
        
        # 5. Parameter sensitivity
        logger.info("Testing parameter sensitivity...")
        param_sensitivity = self._test_parameter_sensitivity(strategy, oos_data)
        validation_details['parameter_sensitivity'] = param_sensitivity
        
        # 6. Transaction cost impact
        logger.info("Testing transaction cost impact...")
        cost_impact = self._test_transaction_costs(strategy, oos_data, transaction_costs)
        validation_details['cost_impact'] = cost_impact
        
        # 7. Benchmark comparison
        logger.info("Comparing to benchmarks...")
        benchmark_comparison = self._compare_to_benchmarks(
            strategy, 
            oos_data, 
            benchmark_data
        )
        validation_details['benchmark_comparison'] = benchmark_comparison
        
        # Calculate overall robustness score
        score = self._calculate_robustness_score(
            oos_metrics,
            regime_metrics,
            param_sensitivity,
            cost_impact,
            benchmark_comparison
        )
        
        # Determine validation status
        status = self._determine_status(
            oos_metrics,
            regime_metrics,
            param_sensitivity,
            cost_impact,
            reasons,
            recommendations
        )
        
        # Build final metrics dictionary
        metrics = {
            'is_sharpe': is_metrics['sharpe'],
            'oos_sharpe': oos_metrics['sharpe'],
            'oos_sortino': oos_metrics['sortino'],
            'oos_max_drawdown': oos_metrics['max_drawdown'],
            'oos_win_rate': oos_metrics['win_rate'],
            'cost_adjusted_sharpe': cost_impact['cost_adjusted_sharpe'],
            'turnover': cost_impact['turnover'],
            'regime_consistency': regime_metrics['consistency'],
            'param_robustness': param_sensitivity['robustness'],
            'vs_buy_hold': benchmark_comparison.get('buy_hold', 0.0),
        }
        
        return ValidationResult(
            strategy_name=strategy.name,
            status=status,
            score=score,
            metrics=metrics,
            reasons=reasons,
            recommendations=recommendations,
            timestamp=datetime.now().isoformat(),
            validation_details=validation_details
        )
    
    def _check_economic_rationale(self, strategy: Any) -> Tuple[bool, str]:
        """Check if strategy has a documented economic rationale."""
        if not hasattr(strategy, 'hypothesis'):
            return False, "Strategy lacks 'hypothesis' attribute"
        
        hypothesis = strategy.hypothesis
        if not isinstance(hypothesis, StrategyHypothesis):
            return False, "Hypothesis must be StrategyHypothesis instance"
        
        required_fields = ['economic_rationale', 'expected_mechanism']
        missing = [f for f in required_fields if not getattr(hypothesis, f, '')]
        
        if missing:
            return False, f"Missing required fields: {missing}"
        
        # Check that rationale is substantive (not empty or generic)
        if len(hypothesis.economic_rationale) < 20:
            return False, "Economic rationale too brief"
        
        return True, "Economic rationale validated"
    
    def _calculate_metrics(self, strategy: Any, data: pd.DataFrame, label: str) -> Dict[str, float]:
        """Calculate performance metrics for a dataset."""
        try:
            # Generate signals/returns from strategy
            if hasattr(strategy, 'generate_signals'):
                returns = strategy.generate_signals(data)
            elif hasattr(strategy, 'backtest'):
                results = strategy.backtest(data)
                returns = results.get('returns', pd.Series())
            else:
                logger.warning(f"Strategy {strategy.name} has no generate_signals or backtest method")
                return self._empty_metrics()
            
            if returns is None or len(returns) == 0:
                logger.warning(f"No returns generated for {label}")
                return self._empty_metrics()
            
            # Ensure returns is a Series
            if isinstance(returns, pd.DataFrame):
                returns = returns.iloc[:, 0]
            
            returns = returns.dropna()
            
            if len(returns) < 10:
                logger.warning(f"Too few returns for {label}: {len(returns)}")
                return self._empty_metrics()
            
            # Calculate metrics
            sharpe = self._calculate_sharpe(returns)
            sortino = self._calculate_sortino(returns)
            max_dd = self._calculate_max_drawdown(returns)
            win_rate = (returns > 0).mean()
            
            positive_returns = returns[returns > 0]
            negative_returns = returns[returns < 0]
            
            avg_win = positive_returns.mean() if len(positive_returns) > 0 else 0.0
            avg_loss = abs(negative_returns.mean()) if len(negative_returns) > 0 else 0.0
            
            # Profit factor
            gross_profit = positive_returns.sum() if len(positive_returns) > 0 else 0.0
            gross_loss = abs(negative_returns.sum()) if len(negative_returns) > 0 else 0.0
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.nan
            
            return {
                'sharpe': sharpe,
                'sortino': sortino,
                'max_drawdown': max_dd,
                'win_rate': win_rate,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'total_return': (1 + returns).prod() - 1,
                'annualized_return': returns.mean() * 252,
                'annualized_vol': returns.std() * np.sqrt(252),
                'n_periods': len(returns),
            }
            
        except Exception as e:
            logger.error(f"Error calculating metrics for {label}: {e}")
            return self._empty_metrics()
    
    def _empty_metrics(self) -> Dict[str, float]:
        """Return empty metrics dictionary."""
        return {
            'sharpe': 0.0,
            'sortino': 0.0,
            'max_drawdown': 1.0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': np.nan,
            'total_return': 0.0,
            'annualized_return': 0.0,
            'annualized_vol': 0.0,
            'n_periods': 0,
        }
    
    def _evaluate_by_regime(self, strategy: Any, data: pd.DataFrame) -> Dict[str, Any]:
        """Evaluate strategy performance across different market regimes."""
        try:
            # Use existing regime detection if available
            regimes = self._detect_regimes(data)
            
            if not regimes or len(regimes) == 0:
                return {'regime_returns': {}, 'consistency': 0.5}
            
            regime_returns = {}
            regime_sharpes = {}
            
            for regime_name, mask in regimes.items():
                if mask.sum() < 20:  # Need minimum data points
                    continue
                    
                regime_data = data[mask]
                returns = self._get_strategy_returns(strategy, regime_data)
                
                if len(returns) > 0:
                    sharpe = self._calculate_sharpe(returns)
                    regime_returns[regime_name] = returns.mean()
                    regime_sharpes[regime_name] = sharpe
            
            # Calculate consistency across regimes
            if len(regime_sharpes) > 1:
                sharpes = list(regime_sharpes.values())
                mean_sharpe = np.mean(sharpes)
                std_sharpe = np.std(sharpes)
                # Consistency = 1 - coefficient of variation (normalized)
                cv = std_sharpe / (abs(mean_sharpe) + 1e-8)
                consistency = max(0, min(1, 1 - cv))
            else:
                consistency = 0.5  # Not enough regimes to test
            
            return {
                'regime_returns': regime_returns,
                'regime_sharpes': regime_sharpes,
                'consistency': consistency,
                'n_regimes_tested': len(regime_sharpes),
            }
            
        except Exception as e:
            logger.error(f"Error evaluating by regime: {e}")
            return {'regime_returns': {}, 'consistency': 0.5}
    
    def _detect_regimes(self, data: pd.DataFrame) -> Dict[str, pd.Series]:
        """Detect market regimes from data."""
        try:
            # Try to use existing regime engine
            from strategies.regime_engine import RegimeEngine
            engine = RegimeEngine()
            
            if hasattr(engine, 'detect_regimes'):
                regimes = engine.detect_regimes(data)
                if isinstance(regimes, dict):
                    return regimes
            
            # Fallback: simple volatility-based regimes
            returns = data['close'].pct_change().dropna()
            rolling_vol = returns.rolling(20).std()
            
            vol_median = rolling_vol.median()
            
            regimes = {
                'low_vol': rolling_vol < vol_median * 0.8,
                'normal_vol': (rolling_vol >= vol_median * 0.8) & (rolling_vol <= vol_median * 1.2),
                'high_vol': rolling_vol > vol_median * 1.2,
            }
            return regimes
            
        except Exception as e:
            logger.warning(f"Could not detect regimes: {e}")
            return {}
    
    def _test_parameter_sensitivity(self, strategy: Any, data: pd.DataFrame) -> Dict[str, Any]:
        """Test how sensitive strategy is to parameter changes."""
        try:
            # Get base parameters
            if not hasattr(strategy, 'get_params'):
                return {'robustness': 0.5, 'mean_sharpe': 0.0, 'std_sharpe': 0.0, 'n_variations': 0}
            
            base_params = strategy.get_params()
            if not base_params:
                return {'robustness': 0.5, 'mean_sharpe': 0.0, 'std_sharpe': 0.0, 'n_variations': 0}
            
            # Generate parameter variations
            param_variations = self._generate_param_variations(base_params)
            
            sharpe_values = []
            for variation in param_variations:
                try:
                    # Set new parameters
                    strategy.set_params(variation)
                    
                    # Get returns and calculate Sharpe
                    returns = self._get_strategy_returns(strategy, data)
                    sharpe = self._calculate_sharpe(returns)
                    sharpe_values.append(sharpe)
                    
                except Exception as e:
                    logger.warning(f"Parameter variation failed: {e}")
                    continue
            
            # Restore original parameters
            strategy.set_params(base_params)
            
            if len(sharpe_values) < 2:
                return {'robustness': 0.5, 'mean_sharpe': 0.0, 'std_sharpe': 0.0, 'n_variations': len(sharpe_values)}
            
            # Calculate robustness as inverse of coefficient of variation
            mean_sharpe = np.mean(sharpe_values)
            std_sharpe = np.std(sharpe_values)
            
            if mean_sharpe > 0:
                cv = std_sharpe / mean_sharpe
                robustness = max(0, min(1, 1 - cv))
            else:
                robustness = 0.0
            
            return {
                'robustness': robustness,
                'mean_sharpe': mean_sharpe,
                'std_sharpe': std_sharpe,
                'n_variations': len(sharpe_values),
                'sharpe_values': sharpe_values,
            }
            
        except Exception as e:
            logger.error(f"Error testing parameter sensitivity: {e}")
            return {'robustness': 0.5, 'mean_sharpe': 0.0, 'std_sharpe': 0.0, 'n_variations': 0}
    
    def _test_transaction_costs(self, strategy: Any, data: pd.DataFrame, cost: float) -> Dict[str, Any]:
        """Test strategy performance after transaction costs."""
        try:
            returns = self._get_strategy_returns(strategy, data)
            
            if len(returns) == 0:
                return {'turnover': 0.0, 'cost_adjusted_sharpe': 0.0, 'cost_impact': 0.0}
            
            # Estimate turnover
            turnover = self._calculate_turnover(returns)
            
            # Apply transaction costs
            cost_adjusted_returns = returns - (turnover * cost)
            cost_adjusted_sharpe = self._calculate_sharpe(cost_adjusted_returns)
            
            # Calculate cost impact
            raw_sharpe = self._calculate_sharpe(returns)
            cost_impact = raw_sharpe - cost_adjusted_sharpe
            
            return {
                'turnover': turnover,
                'cost_adjusted_sharpe': cost_adjusted_sharpe,
                'cost_impact': cost_impact,
                'raw_sharpe': raw_sharpe,
            }
            
        except Exception as e:
            logger.error(f"Error testing transaction costs: {e}")
            return {'turnover': 0.0, 'cost_adjusted_sharpe': 0.0, 'cost_impact': 0.0}
    
    def _compare_to_benchmarks(
        self, 
        strategy: Any, 
        data: pd.DataFrame, 
        benchmark_data: Optional[pd.DataFrame] = None
    ) -> Dict[str, float]:
        """Compare strategy to benchmarks."""
        try:
            strategy_returns = self._get_strategy_returns(strategy, data)
            
            if len(strategy_returns) == 0:
                return {'buy_hold': 0.0, 'momentum': 0.0}
            
            comparison = {}
            
            # Buy and hold benchmark
            if 'close' in data.columns:
                buy_hold_returns = data['close'].pct_change().dropna()
                # Align lengths
                min_len = min(len(strategy_returns), len(buy_hold_returns))
                excess_vs_bh = strategy_returns.iloc[:min_len] - buy_hold_returns.iloc[:min_len]
                comparison['buy_hold'] = self._calculate_sharpe(excess_vs_bh)
            
            # Momentum benchmark (if applicable)
            if 'close' in data.columns and len(data) > 20:
                momentum_returns = data['close'].pct_change(periods=20).dropna()
                min_len = min(len(strategy_returns), len(momentum_returns))
                excess_vs_mom = strategy_returns.iloc[:min_len] - momentum_returns.iloc[:min_len]
                comparison['momentum'] = self._calculate_sharpe(excess_vs_mom)
            
            # Custom benchmark if provided
            if benchmark_data is not None:
                bench_returns = benchmark_data['close'].pct_change().dropna()
                min_len = min(len(strategy_returns), len(bench_returns))
                excess_vs_custom = strategy_returns.iloc[:min_len] - bench_returns.iloc[:min_len]
                comparison['custom'] = self._calculate_sharpe(excess_vs_custom)
            
            return comparison
            
        except Exception as e:
            logger.error(f"Error comparing to benchmarks: {e}")
            return {'buy_hold': 0.0, 'momentum': 0.0}
    
    def _calculate_robustness_score(
        self,
        oos_metrics: Dict[str, float],
        regime_metrics: Dict[str, Any],
        param_sens: Dict[str, Any],
        cost_impact: Dict[str, Any],
        benchmark_comp: Dict[str, float]
    ) -> float:
        """
        Calculate overall robustness score (0-1).
        
        Weights:
        - OOS Sharpe: 25%
        - Regime consistency: 20%
        - Parameter robustness: 20%
        - Cost-adjusted Sharpe: 20%
        - Benchmark comparison: 15%
        """
        scores = []
        weights = []
        
        # OOS Sharpe (normalized to 0-1, target Sharpe=2.0)
        sharpe_score = min(1.0, max(0.0, oos_metrics['sharpe'] / 2.0))
        scores.append(sharpe_score)
        weights.append(0.25)
        
        # Regime consistency
        regime_score = regime_metrics.get('consistency', 0.5)
        scores.append(regime_score)
        weights.append(0.20)
        
        # Parameter robustness
        param_score = param_sens.get('robustness', 0.5)
        scores.append(param_score)
        weights.append(0.20)
        
        # Cost-adjusted Sharpe (normalized to 0-1, target Sharpe=1.5)
        cost_score = min(1.0, max(0.0, cost_impact['cost_adjusted_sharpe'] / 1.5))
        scores.append(cost_score)
        weights.append(0.20)
        
        # Benchmark comparison (average excess Sharpe)
        if benchmark_comp:
            benchmark_scores = [min(1.0, max(0.0, s + 0.5)) for s in benchmark_comp.values()]
            bench_score = np.mean(benchmark_scores)
        else:
            bench_score = 0.5
        scores.append(bench_score)
        weights.append(0.15)
        
        # Weighted average
        total_score = sum(s * w for s, w in zip(scores, weights))
        return round(total_score, 4)
    
    def _determine_status(
        self,
        oos_metrics: Dict[str, float],
        regime_metrics: Dict[str, Any],
        param_sens: Dict[str, Any],
        cost_impact: Dict[str, Any],
        reasons: List[str],
        recommendations: List[str]
    ) -> ValidationStatus:
        """Determine validation status based on metrics."""
        
        # Check for automatic rejection
        if oos_metrics['sharpe'] < 0.1:
            reasons.append(f"OOS Sharpe ({oos_metrics['sharpe']:.2f}) below minimum threshold (0.1)")
            recommendations.append("Strategy does not generate sufficient risk-adjusted returns")
            return ValidationStatus.REJECTED
        
        if regime_metrics.get('consistency', 0) < 0.3:
            reasons.append(f"Regime consistency ({regime_metrics.get('consistency', 0):.2f}) too low")
            recommendations.append("Strategy only works in specific market conditions")
            return ValidationStatus.REJECTED
        
        if param_sens.get('robustness', 0) < 0.3:
            reasons.append(f"Parameter robustness ({param_sens.get('robustness', 0):.2f}) too low")
            recommendations.append("Strategy is overly sensitive to parameter choices")
            return ValidationStatus.REJECTED
        
        if cost_impact.get('cost_adjusted_sharpe', 0) < 0.1:
            reasons.append(f"Cost-adjusted Sharpe ({cost_impact.get('cost_adjusted_sharpe', 0):.2f}) below minimum")
            recommendations.append("Transaction costs eliminate strategy edge")
            return ValidationStatus.REJECTED
        
        # Check for PASS criteria
        passes_all = True
        
        if oos_metrics['sharpe'] < self.min_sharpe_threshold:
            passes_all = False
            reasons.append(f"OOS Sharpe ({oos_metrics['sharpe']:.2f}) below target ({self.min_sharpe_threshold})")
        
        if oos_metrics['max_drawdown'] > self.max_drawdown_threshold:
            passes_all = False
            reasons.append(f"OOS drawdown ({oos_metrics['max_drawdown']:.2%}) exceeds limit ({self.max_drawdown_threshold:.2%})")
            recommendations.append("Add risk controls or reduce position sizing")
        
        if regime_metrics.get('consistency', 0) < self.min_regime_consistency:
            passes_all = False
            reasons.append(f"Regime consistency ({regime_metrics.get('consistency', 0):.2f}) below target ({self.min_regime_consistency})")
        
        if param_sens.get('robustness', 0) < self.min_param_robustness:
            passes_all = False
            reasons.append(f"Parameter robustness ({param_sens.get('robustness', 0):.2f}) below target ({self.min_param_robustness})")
        
        if cost_impact.get('cost_adjusted_sharpe', 0) < self.min_cost_adjusted_sharpe:
            passes_all = False
            reasons.append(f"Cost-adjusted Sharpe ({cost_impact.get('cost_adjusted_sharpe', 0):.2f}) below target ({self.min_cost_adjusted_sharpe})")
            recommendations.append("Reduce turnover or optimize execution")
        
        if passes_all:
            return ValidationStatus.PASS
        elif oos_metrics['sharpe'] > 0.3:
            return ValidationStatus.INCONCLUSIVE
        else:
            return ValidationStatus.FAIL
    
    # Helper methods
    def _calculate_sharpe(self, returns: pd.Series, risk_free: float = 0.0) -> float:
        """Calculate annualized Sharpe ratio."""
        if len(returns) < 10 or returns.std() == 0:
            return 0.0
        excess_returns = returns - risk_free
        return (excess_returns.mean() / (returns.std() + 1e-8)) * np.sqrt(252)
    
    def _calculate_sortino(self, returns: pd.Series, risk_free: float = 0.0) -> float:
        """Calculate annualized Sortino ratio."""
        downside = returns[returns < 0]
        if len(downside) < 5 or downside.std() == 0:
            return 0.0
        excess_returns = returns - risk_free
        return (excess_returns.mean() / (downside.std() + 1e-8)) * np.sqrt(252)
    
    def _calculate_max_drawdown(self, returns: pd.Series) -> float:
        """Calculate maximum drawdown."""
        if len(returns) == 0:
            return 0.0
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        return abs(drawdown.min())
    
    def _calculate_turnover(self, returns: pd.Series) -> float:
        """Estimate turnover from returns."""
        positions = np.sign(returns).fillna(0)
        changes = positions.diff().abs()
        return changes.mean() / 2
    
    def _get_strategy_returns(self, strategy: Any, data: pd.DataFrame) -> pd.Series:
        """Get returns from strategy."""
        if hasattr(strategy, 'generate_signals'):
            returns = strategy.generate_signals(data)
        elif hasattr(strategy, 'backtest'):
            results = strategy.backtest(data)
            returns = results.get('returns', pd.Series())
        else:
            return pd.Series()
        
        if isinstance(returns, pd.DataFrame):
            returns = returns.iloc[:, 0]
        
        return returns.dropna()
    
    def _generate_param_variations(self, base_params: Dict) -> List[Dict]:
        """Generate parameter variations for sensitivity testing."""
        variations = [base_params.copy()]  # Base case
        
        for param_name, param_value in base_params.items():
            if isinstance(param_value, (int, float)):
                # Generate variations around the parameter
                for i in range(1, self.n_param_variations):
                    variation = base_params.copy()
                    # Vary by ±variation_pct
                    direction = 1 if i % 2 == 0 else -1
                    variation_amount = (i // 2 + 1) * self.param_variation_pct
                    new_value = param_value * (1 + direction * variation_amount)
                    
                    if isinstance(param_value, int):
                        new_value = int(round(new_value))
                        if new_value <= 0:
                            new_value = 1
                    
                    variation[param_name] = new_value
                    variations.append(variation)
        
        return variations
