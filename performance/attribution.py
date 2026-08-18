"""
Phase 8: Performance Attribution System

This module provides comprehensive performance attribution for the crypto portfolio
optimization system, tracking each strategy's contribution to returns, costs, and
risk-adjusted metrics.

Key Features:
- Strategy-level attribution (gross/net returns, Sharpe, Sortino, Calmar)
- Asset-level attribution within each strategy
- Regime-conditional performance breakdown
- Cost and slippage attribution
- Turnover tracking per strategy
- Strategy ranking and recommendations
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from collections import defaultdict


@dataclass
class StrategyAttribution:
    """Attribution for a single strategy at a single point in time."""
    
    timestamp: datetime
    strategy_name: str
    regime: str
    asset_weights: Dict[str, float]  # asset -> weight in this strategy
    asset_returns: Dict[str, float]  # asset -> return for this period
    asset_contributions: Dict[str, float]  # asset -> contribution to strategy return
    strategy_return: float  # weighted return of this strategy
    portfolio_weight: float  # weight of this strategy in the ensemble
    portfolio_contribution: float  # strategy_return * portfolio_weight
    transaction_cost: float
    slippage: float
    net_contribution: float  # portfolio_contribution - cost - slippage
    
    def __post_init__(self):
        # Calculate asset contributions if not provided
        if not self.asset_contributions and self.asset_weights and self.asset_returns:
            self.asset_contributions = {
                asset: self.asset_weights.get(asset, 0.0) * self.asset_returns.get(asset, 0.0)
                for asset in set(self.asset_weights.keys()) | set(self.asset_returns.keys())
            }
        
        # Calculate strategy return if not provided
        if self.strategy_return == 0.0 and self.asset_contributions:
            self.strategy_return = sum(self.asset_contributions.values())
        
        # Calculate portfolio contribution if not provided
        if self.portfolio_contribution == 0.0:
            self.portfolio_contribution = self.strategy_return * self.portfolio_weight
        
        # Calculate net contribution if not provided
        if self.net_contribution == 0.0:
            self.net_contribution = self.portfolio_contribution - self.transaction_cost - self.slippage


@dataclass
class CumulativeAttribution:
    """Aggregated attribution over time."""
    
    strategy_name: str
    total_gross_return: float
    total_net_return: float
    total_cost: float
    total_turnover: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    hit_rate: float  # % of positive periods
    avg_positive_return: float
    avg_negative_return: float
    periods: int
    regime_breakdown: Dict[str, float]  # regime -> return in that regime
    
    # Additional metrics
    total_slippage: float = 0.0
    asset_contributions: Dict[str, float] = field(default_factory=dict)
    volatility: float = 0.0
    downside_deviation: float = 0.0
    peak_return: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for reporting."""
        return {
            'strategy_name': self.strategy_name,
            'total_gross_return': self.total_gross_return,
            'total_net_return': self.total_net_return,
            'total_cost': self.total_cost,
            'total_slippage': self.total_slippage,
            'total_turnover': self.total_turnover,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'calmar_ratio': self.calmar_ratio,
            'max_drawdown': self.max_drawdown,
            'hit_rate': self.hit_rate,
            'avg_positive_return': self.avg_positive_return,
            'avg_negative_return': self.avg_negative_return,
            'periods': self.periods,
            'volatility': self.volatility,
            'downside_deviation': self.downside_deviation,
            'regime_breakdown': self.regime_breakdown,
            'asset_contributions': self.asset_contributions,
        }


class AttributionEngine:
    """
    Engine for calculating and tracking performance attribution.
    
    This engine records rebalancing events, calculates attribution metrics,
    and provides rankings and recommendations for strategy selection.
    """
    
    def __init__(self, risk_free_rate: float = 0.0):
        """
        Initialize the AttributionEngine.
        
        Args:
            risk_free_rate: Annual risk-free rate for Sharpe/Sortino calculations
        """
        self.risk_free_rate = risk_free_rate
        
        # Store all attribution records
        self._records: List[StrategyAttribution] = []
        
        # Store period returns per strategy for risk metrics
        self._strategy_returns: Dict[str, List[float]] = defaultdict(list)
        
        # Store regime performance
        self._regime_performance: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
        
        # Store asset contributions per strategy
        self._asset_contributions: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
        
        # Store turnover per strategy
        self._strategy_turnover: Dict[str, List[float]] = defaultdict(list)
        
        # Store costs per strategy
        self._strategy_costs: Dict[str, List[float]] = defaultdict(list)
        
        # Previous weights for turnover calculation
        self._prev_weights: Dict[str, Dict[str, float]] = {}
        
        # Current regime
        self._current_regime: str = "low_vol_range"
    
    def record_rebalance(
        self,
        timestamp: datetime,
        strategy_weights: Dict[str, Dict[str, float]],  # strategy -> {asset -> weight}
        asset_returns: Dict[str, float],
        costs: Dict[str, float],  # strategy -> cost
        slippage: Dict[str, float],  # strategy -> slippage
        regime: str,
        portfolio_strategy_weights: Optional[Dict[str, float]] = None,  # strategy -> portfolio weight
    ) -> None:
        """
        Record a rebalancing event for attribution.
        
        Args:
            timestamp: Time of rebalance
            strategy_weights: Dictionary mapping strategy names to their asset weights
            asset_returns: Dictionary mapping assets to their returns for this period
            costs: Transaction costs per strategy
            slippage: Slippage per strategy
            regime: Current market regime
            portfolio_strategy_weights: Weight of each strategy in the portfolio
        """
        self._current_regime = regime
        
        if portfolio_strategy_weights is None:
            # Equal weight if not provided
            n_strategies = len(strategy_weights)
            portfolio_strategy_weights = {s: 1.0 / n_strategies for s in strategy_weights}
        
        for strategy_name, asset_weights in strategy_weights.items():
            # Calculate asset contributions
            asset_contributions = {
                asset: asset_weights.get(asset, 0.0) * asset_returns.get(asset, 0.0)
                for asset in asset_weights.keys()
            }
            
            # Calculate strategy return
            strategy_return = sum(asset_contributions.values())
            
            # Get portfolio weight for this strategy
            portfolio_weight = portfolio_strategy_weights.get(strategy_name, 0.0)
            
            # Calculate portfolio contribution
            portfolio_contribution = strategy_return * portfolio_weight
            
            # Get costs
            transaction_cost = costs.get(strategy_name, 0.0)
            slip = slippage.get(strategy_name, 0.0)
            
            # Calculate net contribution
            net_contribution = portfolio_contribution - transaction_cost - slip
            
            # Create attribution record
            attribution = StrategyAttribution(
                timestamp=timestamp,
                strategy_name=strategy_name,
                regime=regime,
                asset_weights=asset_weights.copy(),
                asset_returns=asset_returns.copy(),
                asset_contributions=asset_contributions,
                strategy_return=strategy_return,
                portfolio_weight=portfolio_weight,
                portfolio_contribution=portfolio_contribution,
                transaction_cost=transaction_cost,
                slippage=slip,
                net_contribution=net_contribution,
            )
            
            self._records.append(attribution)
            
            # Store for cumulative calculations
            self._strategy_returns[strategy_name].append(strategy_return)
            self._regime_performance[regime][strategy_name].append(strategy_return)
            
            # Store asset contributions
            for asset, contrib in asset_contributions.items():
                self._asset_contributions[strategy_name][asset].append(contrib)
            
            # Store costs
            self._strategy_costs[strategy_name].append(transaction_cost + slip)
            
            # Calculate turnover
            if strategy_name in self._prev_weights:
                prev_weights = self._prev_weights[strategy_name]
                turnover = sum(abs(asset_weights.get(a, 0.0) - prev_weights.get(a, 0.0)) for a in set(asset_weights.keys()) | set(prev_weights.keys())) / 2
                self._strategy_turnover[strategy_name].append(turnover)
            
            # Update previous weights
            self._prev_weights[strategy_name] = asset_weights.copy()
    
    def calculate_cumulative_attribution(self) -> Dict[str, CumulativeAttribution]:
        """
        Calculate cumulative attribution metrics for all strategies.
        
        Returns:
            Dictionary mapping strategy names to CumulativeAttribution objects
        """
        results = {}
        
        for strategy_name in self._strategy_returns.keys():
            returns = self._strategy_returns[strategy_name]
            
            if len(returns) == 0:
                continue
            
            # Basic metrics
            total_gross_return = sum(returns)
            total_cost = sum(self._strategy_costs[strategy_name])
            total_slippage = sum(self._strategy_costs[strategy_name]) * 0.5  # Approximate split
            total_turnover = sum(self._strategy_turnover.get(strategy_name, [0.0] * len(returns)))
            
            # Risk metrics
            returns_array = np.array(returns)
            volatility = np.std(returns_array) if len(returns) > 1 else 0.0
            
            # Annualize (assuming daily returns)
            annualization_factor = 365
            annualized_return = total_gross_return * annualization_factor / len(returns)
            annualized_vol = volatility * np.sqrt(annualization_factor)
            
            # Sharpe ratio
            if annualized_vol > 0:
                sharpe_ratio = (annualized_return - self.risk_free_rate) / annualized_vol
            else:
                sharpe_ratio = 0.0
            
            # Sortino ratio (downside deviation)
            negative_returns = returns_array[returns_array < 0]
            if len(negative_returns) > 0:
                downside_deviation = np.std(negative_returns) * np.sqrt(annualization_factor)
                if downside_deviation > 0:
                    sortino_ratio = (annualized_return - self.risk_free_rate) / downside_deviation
                else:
                    sortino_ratio = sharpe_ratio  # Fallback
            else:
                downside_deviation = 0.0
                sortino_ratio = sharpe_ratio
            
            # Maximum drawdown
            cumulative_returns = np.cumsum(returns)
            peak = np.maximum.accumulate(cumulative_returns)
            drawdown = peak - cumulative_returns
            max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0.0
            
            # Calmar ratio
            if max_drawdown > 0:
                calmar_ratio = annualized_return / max_drawdown
            else:
                calmar_ratio = annualized_return if annualized_return > 0 else 0.0
            
            # Hit rate
            positive_periods = sum(1 for r in returns if r > 0)
            hit_rate = positive_periods / len(returns) if len(returns) > 0 else 0.0
            
            # Average positive/negative returns
            positive_returns = [r for r in returns if r > 0]
            negative_returns_list = [r for r in returns if r < 0]
            avg_positive_return = np.mean(positive_returns) if positive_returns else 0.0
            avg_negative_return = np.mean(negative_returns_list) if negative_returns_list else 0.0
            
            # Regime breakdown
            regime_breakdown = {}
            for regime, regime_returns in self._regime_performance.items():
                if strategy_name in regime_returns:
                    strat_regime_returns = regime_returns[strategy_name]
                    if strat_regime_returns:
                        regime_breakdown[regime] = sum(strat_regime_returns)
            
            # Asset contributions
            asset_contrib_totals = {}
            for asset, contribs in self._asset_contributions[strategy_name].items():
                asset_contrib_totals[asset] = sum(contribs)
            
            # Total net return
            total_net_return = total_gross_return - total_cost
            
            results[strategy_name] = CumulativeAttribution(
                strategy_name=strategy_name,
                total_gross_return=total_gross_return,
                total_net_return=total_net_return,
                total_cost=total_cost,
                total_slippage=total_slippage,
                total_turnover=total_turnover,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                calmar_ratio=calmar_ratio,
                max_drawdown=max_drawdown,
                hit_rate=hit_rate,
                avg_positive_return=avg_positive_return,
                avg_negative_return=avg_negative_return,
                periods=len(returns),
                regime_breakdown=regime_breakdown,
                asset_contributions=asset_contrib_totals,
                volatility=volatility,
                downside_deviation=downside_deviation,
                peak_return=np.max(cumulative_returns) if len(cumulative_returns) > 0 else 0.0,
            )
        
        return results
    
    def get_strategy_ranking(self, metric: str = 'sharpe') -> List[Tuple[str, float]]:
        """
        Rank strategies by a specified metric.
        
        Args:
            metric: Metric to rank by ('sharpe', 'sortino', 'calmar', 'return', 'hit_rate')
        
        Returns:
            List of (strategy_name, score) tuples sorted descending
        """
        attribution = self.calculate_cumulative_attribution()
        
        metric_map = {
            'sharpe': lambda x: x.sharpe_ratio,
            'sortino': lambda x: x.sortino_ratio,
            'calmar': lambda x: x.calmar_ratio,
            'return': lambda x: x.total_net_return,
            'hit_rate': lambda x: x.hit_rate,
            'volatility': lambda x: -x.volatility,  # Lower is better
        }
        
        getter = metric_map.get(metric, metric_map['sharpe'])
        
        ranked = sorted(
            [(name, getter(attr)) for name, attr in attribution.items()],
            key=lambda x: x[1],
            reverse=True
        )
        
        return ranked
    
    def get_regime_breakdown(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Get performance breakdown by regime for each strategy.
        
        Returns:
            Nested dict: regime -> strategy -> {return, sharpe, periods}
        """
        results = {}
        
        for regime, strategy_returns in self._regime_performance.items():
            results[regime] = {}
            for strategy_name, returns in strategy_returns.items():
                if returns:
                    returns_array = np.array(returns)
                    volatility = np.std(returns_array) if len(returns) > 1 else 0.0
                    
                    if volatility > 0:
                        sharpe = np.mean(returns_array) / volatility * np.sqrt(365)
                    else:
                        sharpe = 0.0 if np.mean(returns_array) == 0 else float('inf')
                    
                    results[regime][strategy_name] = {
                        'return': sum(returns),
                        'sharpe': sharpe,
                        'periods': len(returns),
                    }
        
        return results
    
    def get_asset_attribution(self, strategy_name: str) -> Dict[str, float]:
        """
        Get asset-level attribution for a specific strategy.
        
        Args:
            strategy_name: Name of the strategy
        
        Returns:
            Dictionary mapping assets to their total contribution
        """
        if strategy_name not in self._asset_contributions:
            return {}
        
        return {
            asset: sum(contribs)
            for asset, contribs in self._asset_contributions[strategy_name].items()
        }
    
    def get_cost_attribution(self) -> Dict[str, Dict[str, float]]:
        """
        Get cost attribution per strategy.
        
        Returns:
            Dictionary with cost breakdown per strategy
        """
        results = {}
        
        for strategy_name in self._strategy_costs.keys():
            costs = self._strategy_costs[strategy_name]
            turnovers = self._strategy_turnover.get(strategy_name, [0.0] * len(costs))
            
            results[strategy_name] = {
                'total_cost': sum(costs),
                'avg_cost_per_period': np.mean(costs) if costs else 0.0,
                'total_turnover': sum(turnovers),
                'cost_drag': sum(costs) / sum(self._strategy_returns[strategy_name]) if sum(self._strategy_returns[strategy_name]) != 0 else 0.0,
            }
        
        return results
    
    def get_strategy_recommendations(self) -> List[Dict[str, Any]]:
        """
        Generate strategy recommendations based on attribution results.
        
        Returns:
            List of recommendation dictionaries
        """
        attribution = self.calculate_cumulative_attribution()
        recommendations = []
        
        for strategy_name, attr in attribution.items():
            # Determine recommendation based on Sharpe ratio
            if attr.sharpe_ratio > 0.5:
                action = "KEEP"
                rationale = f"Strong risk-adjusted returns (Sharpe={attr.sharpe_ratio:.2f})"
            elif attr.sharpe_ratio >= 0.0:
                action = "REDUCE"
                rationale = f"Moderate performance (Sharpe={attr.sharpe_ratio:.2f}), consider reducing weight by 50%"
            else:
                action = "REVIEW"
                rationale = f"Negative risk-adjusted returns (Sharpe={attr.sharpe_ratio:.2f}), consider removal"
            
            # Check regime-specific performance
            regime_notes = []
            for regime, regime_return in attr.regime_breakdown.items():
                if regime_return > 0.1:  # Strong in this regime
                    regime_notes.append(f"performs well in {regime}")
                elif regime_return < -0.1:  # Poor in this regime
                    regime_notes.append(f"underperforms in {regime}")
            
            if regime_notes:
                rationale += f" ({'; '.join(regime_notes)})"
            
            recommendations.append({
                'strategy': strategy_name,
                'action': action,
                'rationale': rationale,
                'metrics': attr.to_dict(),
            })
        
        # Sort by action priority (KEEP first, then REDUCE, then REVIEW)
        action_priority = {'KEEP': 0, 'REDUCE': 1, 'REVIEW': 2}
        recommendations.sort(key=lambda x: (action_priority[x['action']], -x['metrics']['sharpe_ratio']))
        
        return recommendations
    
    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert attribution data to a pandas DataFrame for visualization.
        
        Returns:
            DataFrame with columns: timestamp, strategy, asset, return, contribution, cost, regime
        """
        rows = []
        
        for record in self._records:
            for asset, contribution in record.asset_contributions.items():
                rows.append({
                    'timestamp': record.timestamp,
                    'strategy': record.strategy_name,
                    'asset': asset,
                    'asset_weight': record.asset_weights.get(asset, 0.0),
                    'asset_return': record.asset_returns.get(asset, 0.0),
                    'contribution': contribution,
                    'strategy_return': record.strategy_return,
                    'portfolio_weight': record.portfolio_weight,
                    'portfolio_contribution': record.portfolio_contribution,
                    'transaction_cost': record.transaction_cost,
                    'slippage': record.slippage,
                    'net_contribution': record.net_contribution,
                    'regime': record.regime,
                })
        
        return pd.DataFrame(rows)
    
    def get_summary_table(self) -> pd.DataFrame:
        """
        Generate a summary table of all strategies.
        
        Returns:
            DataFrame with strategies as rows and metrics as columns
        """
        attribution = self.calculate_cumulative_attribution()
        cost_attr = self.get_cost_attribution()
        
        rows = []
        for strategy_name, attr in attribution.items():
            cost_info = cost_attr.get(strategy_name, {})
            rows.append({
                'Strategy': strategy_name,
                'Gross Ret': attr.total_gross_return,
                'Net Ret': attr.total_net_return,
                'Sharpe': attr.sharpe_ratio,
                'Sortino': attr.sortino_ratio,
                'Calmar': attr.calmar_ratio,
                'Max DD': attr.max_drawdown,
                'Turnover': attr.total_turnover,
                'Cost Drag': cost_info.get('cost_drag', 0.0),
                'Hit Rate': attr.hit_rate,
                'Periods': attr.periods,
            })
        
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values('Sharpe', ascending=False)
        
        return df
    
    def clear(self) -> None:
        """Clear all recorded data."""
        self._records.clear()
        self._strategy_returns.clear()
        self._regime_performance.clear()
        self._asset_contributions.clear()
        self._strategy_turnover.clear()
        self._strategy_costs.clear()
        self._prev_weights.clear()
