"""
Comprehensive benchmark comparison system.

This module provides the core functionality for comparing trading system
performance against various benchmarks including passive strategies,
simple strategies, risk parity, and market indices.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from enum import Enum
import logging
from datetime import datetime
from scipy import stats

logger = logging.getLogger(__name__)


class BenchmarkType(Enum):
    """Types of benchmarks."""
    PASSIVE = "passive"          # Buy and hold, equal weight
    SIMPLE = "simple"            # Simple strategies (momentum, etc.)
    RISK_PARITY = "risk_parity"  # Risk parity
    MARKET = "market"            # Market indices
    CASH = "cash"                # Risk-free rate
    CUSTOM = "custom"            # User-defined


@dataclass
class BenchmarkResult:
    """Results from a benchmark comparison."""
    benchmark_name: str
    benchmark_type: BenchmarkType
    system_metric: float
    benchmark_metric: float
    excess_metric: float
    excess_percentage: float
    p_value: Optional[float] = None
    is_significant: bool = False
    details: Dict = field(default_factory=dict)


@dataclass
class ComprehensiveBenchmarkReport:
    """Complete benchmark comparison report."""
    system_name: str
    period_start: str
    period_end: str
    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    avg_drawdown: float
    recovery_time: float
    turnover: float
    total_fees: float
    total_slippage: float
    win_rate: float
    profit_factor: float
    benchmark_comparisons: List[BenchmarkResult]
    outperformance_summary: Dict[str, bool]
    recommendations: List[str]
    timestamp: str = field(default_factory=lambda: str(datetime.now()))


class BenchmarkSystem:
    """
    Comprehensive benchmark comparison system.
    
    This class provides methods to compare trading system performance
    against various benchmarks with statistical significance testing.
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize the benchmark system.
        
        Args:
            config: Configuration dictionary with optional parameters:
                - risk_free_rate: Annual risk-free rate (default: 0.0)
                - significance_level: P-value threshold for significance (default: 0.05)
        """
        self.config = config or {}
        self.risk_free_rate = self.config.get('risk_free_rate', 0.0)
        self.significance_level = self.config.get('significance_level', 0.05)
        
    def compare_to_benchmarks(
        self,
        system_returns: pd.Series,
        price_data: pd.DataFrame,
        benchmark_configs: List[Dict]
    ) -> ComprehensiveBenchmarkReport:
        """
        Compare system performance against multiple benchmarks.
        
        Args:
            system_returns: System's returns series
            price_data: Price data for benchmarks (columns are symbols)
            benchmark_configs: List of benchmark configurations
        
        Returns:
            ComprehensiveBenchmarkReport with all comparison results
        """
        results = []
        
        for config in benchmark_configs:
            benchmark_type = config.get('type', BenchmarkType.PASSIVE)
            if isinstance(benchmark_type, str):
                benchmark_type = BenchmarkType(benchmark_type)
                
            benchmark_name = config.get('name', f"Benchmark_{len(results)}")
            
            try:
                # Generate benchmark returns based on type
                if benchmark_type == BenchmarkType.PASSIVE:
                    benchmark_returns = self._passive_benchmark(price_data, config)
                elif benchmark_type == BenchmarkType.SIMPLE:
                    benchmark_returns = self._simple_strategy(price_data, config)
                elif benchmark_type == BenchmarkType.RISK_PARITY:
                    benchmark_returns = self._risk_parity_benchmark(price_data, config)
                elif benchmark_type == BenchmarkType.MARKET:
                    benchmark_returns = self._market_benchmark(price_data, config)
                elif benchmark_type == BenchmarkType.CASH:
                    benchmark_returns = self._cash_benchmark(config)
                else:
                    benchmark_returns = self._custom_benchmark(price_data, config)
                
                # Align returns
                aligned = self._align_returns(system_returns, benchmark_returns)
                if aligned is None:
                    logger.warning(f"Skipping {benchmark_name}: insufficient overlap")
                    continue
                
                # Calculate comparison metrics
                result = self._compare_returns(
                    aligned['system'],
                    aligned['benchmark'],
                    benchmark_name,
                    benchmark_type
                )
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error processing benchmark {benchmark_name}: {e}")
                continue
        
        if not results:
            raise ValueError("No valid benchmarks could be computed")
        
        # Generate comprehensive report
        report = self._generate_report(system_returns, results)
        return report
    
    def _passive_benchmark(self, price_data: pd.DataFrame, config: Dict) -> pd.Series:
        """Generate passive benchmark returns (buy and hold)."""
        symbol = config.get('symbol')
        symbols = config.get('symbols')
        
        if symbol:
            # Single asset buy and hold
            if symbol not in price_data.columns:
                # Try to find similar symbol
                available = [c for c in price_data.columns if symbol.split('/')[0] in c]
                if available:
                    symbol = available[0]
                else:
                    raise ValueError(f"Symbol {symbol} not found in price data")
            prices = price_data[symbol]
            returns = prices.pct_change()
            
        elif symbols:
            # Equal weight portfolio
            available_symbols = [s for s in symbols if s in price_data.columns]
            if not available_symbols:
                raise ValueError("No valid symbols found for equal weight benchmark")
            prices = price_data[available_symbols].mean(axis=1)
            returns = prices.pct_change()
        else:
            # Use first available column
            prices = price_data.iloc[:, 0]
            returns = prices.pct_change()
        
        # Apply transaction costs if specified
        if config.get('include_costs', True):
            cost = config.get('cost', 0.001)
            # Buy and hold has minimal turnover (~10% annual rebalance)
            returns = returns - (cost * 0.1 / 252)  # Daily cost
        
        return returns
    
    def _simple_strategy(self, price_data: pd.DataFrame, config: Dict) -> pd.Series:
        """Generate simple strategy benchmark returns."""
        strategy_type = config.get('strategy', 'momentum')
        symbol = config.get('symbol', 'BTC/USDT')
        
        if symbol not in price_data.columns:
            available = [c for c in price_data.columns if symbol.split('/')[0] in c]
            if available:
                symbol = available[0]
            else:
                raise ValueError(f"Symbol {symbol} not found in price data")
        
        prices = price_data[symbol]
        
        if strategy_type == 'momentum':
            # Simple momentum: long if N-day return > 0
            period = config.get('period', 20)
            mom = prices.pct_change(period)
            position = (mom > 0).astype(int)
            returns = position.shift(1) * prices.pct_change()
            
        elif strategy_type == 'mean_reversion':
            # Simple mean reversion: buy when price below N-day MA
            period = config.get('period', 20)
            ma = prices.rolling(period).mean()
            position = (prices < ma).astype(int)
            returns = position.shift(1) * prices.pct_change()
            
        elif strategy_type == 'trend':
            # Simple trend following: long when price > N-day MA
            period = config.get('period', 200)
            ma = prices.rolling(period).mean()
            position = (prices > ma).astype(int)
            returns = position.shift(1) * prices.pct_change()
        else:
            returns = prices.pct_change()
        
        # Apply transaction costs
        if config.get('include_costs', True):
            cost = config.get('cost', 0.001)
            turnover = (position.diff().abs() / 2).mean()
            daily_cost = turnover * cost
            returns = returns - daily_cost
        
        return returns.fillna(0)
    
    def _risk_parity_benchmark(self, price_data: pd.DataFrame, config: Dict) -> pd.Series:
        """Generate risk parity benchmark returns."""
        symbols = config.get('symbols', ['BTC/USDT', 'ETH/USDT'])
        available_symbols = [s for s in symbols if s in price_data.columns]
        
        if len(available_symbols) < 2:
            # Fall back to single asset if not enough symbols
            logger.warning("Not enough symbols for risk parity, falling back to passive")
            return self._passive_benchmark(price_data, {'symbol': available_symbols[0] if available_symbols else symbols[0]})
        
        # Calculate returns and volatility
        returns = price_data[available_symbols].pct_change().dropna()
        vol = returns.rolling(20).std()
        
        # Inverse volatility weights (normalized)
        inv_vol = 1 / (vol + 1e-8)
        weights = inv_vol.div(inv_vol.sum(axis=1), axis=0)
        
        # Apply weights to get portfolio returns
        weighted_returns = returns * weights.shift(1)
        portfolio_returns = weighted_returns.sum(axis=1)
        
        # Apply transaction costs
        if config.get('include_costs', True):
            cost = config.get('cost', 0.001)
            # Estimate turnover from weight changes
            weight_changes = weights.diff().abs().sum(axis=1).mean()
            daily_cost = weight_changes * cost / 2
            portfolio_returns = portfolio_returns - daily_cost
        
        return portfolio_returns
    
    def _market_benchmark(self, price_data: pd.DataFrame, config: Dict) -> pd.Series:
        """Generate market index benchmark (BTC as market proxy)."""
        symbol = config.get('symbol', 'BTC/USDT')
        if symbol in price_data.columns:
            return price_data[symbol].pct_change()
        
        # Try to find BTC
        btc_symbols = [c for c in price_data.columns if 'BTC' in c]
        if btc_symbols:
            return price_data[btc_symbols[0]].pct_change()
        
        # Use first column as fallback
        return price_data.iloc[:, 0].pct_change()
    
    def _cash_benchmark(self, config: Dict) -> pd.Series:
        """Generate cash/risk-free benchmark returns."""
        rate = config.get('rate', self.risk_free_rate)
        # Annual rate to daily
        daily_rate = (1 + rate) ** (1/365) - 1
        return pd.Series(daily_rate)
    
    def _custom_benchmark(self, price_data: pd.DataFrame, config: Dict) -> pd.Series:
        """Generate custom benchmark from user function."""
        func = config.get('func')
        if func and callable(func):
            return func(price_data, config)
        raise ValueError("Custom benchmark requires a callable 'func' parameter")
    
    def _align_returns(self, system_returns: pd.Series, benchmark_returns: pd.Series) -> Optional[Dict]:
        """Align system and benchmark returns by common index."""
        # Ensure both are Series
        if not isinstance(system_returns, pd.Series):
            system_returns = pd.Series(system_returns)
        if not isinstance(benchmark_returns, pd.Series):
            benchmark_returns = pd.Series(benchmark_returns)
        
        # Find common index
        common_index = system_returns.index.intersection(benchmark_returns.index)
        
        if len(common_index) < 10:
            return None
        
        return {
            'system': system_returns.loc[common_index].fillna(0),
            'benchmark': benchmark_returns.loc[common_index].fillna(0)
        }
    
    def _compare_returns(
        self,
        system_returns: pd.Series,
        benchmark_returns: pd.Series,
        benchmark_name: str,
        benchmark_type: BenchmarkType
    ) -> BenchmarkResult:
        """Compare system returns against benchmark returns."""
        # Calculate Sharpe ratios
        system_sharpe = self._calculate_sharpe(system_returns)
        benchmark_sharpe = self._calculate_sharpe(benchmark_returns)
        excess_sharpe = system_sharpe - benchmark_sharpe
        
        # Calculate excess percentage relative to benchmark
        excess_percentage = excess_sharpe / (abs(benchmark_sharpe) + 1e-8)
        
        # Calculate t-test for statistical significance
        excess_returns = system_returns - benchmark_returns
        p_value = self._t_test(excess_returns)
        is_significant = p_value < self.significance_level
        
        return BenchmarkResult(
            benchmark_name=benchmark_name,
            benchmark_type=benchmark_type,
            system_metric=system_sharpe,
            benchmark_metric=benchmark_sharpe,
            excess_metric=excess_sharpe,
            excess_percentage=excess_percentage,
            p_value=p_value,
            is_significant=is_significant,
            details={
                'system_mean': system_returns.mean(),
                'system_std': system_returns.std(),
                'benchmark_mean': benchmark_returns.mean(),
                'benchmark_std': benchmark_returns.std(),
                'correlation': system_returns.corr(benchmark_returns),
            }
        )
    
    def _generate_report(
        self,
        system_returns: pd.Series,
        benchmark_results: List[BenchmarkResult]
    ) -> ComprehensiveBenchmarkReport:
        """Generate comprehensive benchmark report."""
        # Calculate cumulative returns
        cumulative = (1 + system_returns).cumprod()
        total_return = cumulative.iloc[-1] - 1
        
        # Annualize metrics
        n_years = len(system_returns) / 252
        if n_years > 0:
            annualized_return = (1 + total_return) ** (1 / n_years) - 1
        else:
            annualized_return = 0.0
        
        annualized_vol = system_returns.std() * np.sqrt(252)
        sharpe = self._calculate_sharpe(system_returns)
        sortino = self._calculate_sortino(system_returns)
        
        # Calculate drawdown metrics
        drawdown = self._calculate_drawdown(cumulative)
        max_dd = abs(drawdown.min())
        avg_dd = abs(drawdown[drawdown < 0].mean()) if (drawdown < 0).any() else 0
        recovery_time = self._calculate_recovery_time(drawdown)
        
        # Calmar ratio
        calmar = annualized_return / max_dd if max_dd > 0 else 0
        
        # Calculate turnover estimate
        turnover = self._calculate_turnover(system_returns)
        
        # Fee and slippage estimates
        total_fees = turnover * len(system_returns) * 0.0005  # 0.05% per trade
        total_slippage = turnover * len(system_returns) * 0.0005
        
        # Win rate and profit factor
        wins = system_returns[system_returns > 0]
        losses = system_returns[system_returns < 0]
        win_rate = len(wins) / len(system_returns) if len(system_returns) > 0 else 0
        
        if losses.sum() != 0:
            profit_factor = abs(wins.sum() / losses.sum())
        else:
            profit_factor = float('inf') if wins.sum() > 0 else 0.0
        
        # Determine outperformance summary
        outperformance_summary = {}
        for result in benchmark_results:
            outperformance_summary[result.benchmark_name] = result.excess_metric > 0
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            sharpe, max_dd, benchmark_results, turnover
        )
        
        return ComprehensiveBenchmarkReport(
            system_name="Trading System",
            period_start=str(system_returns.index[0]) if len(system_returns) > 0 else "N/A",
            period_end=str(system_returns.index[-1]) if len(system_returns) > 0 else "N/A",
            total_return=total_return,
            annualized_return=annualized_return,
            annualized_volatility=annualized_vol,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown=max_dd,
            avg_drawdown=avg_dd,
            recovery_time=recovery_time,
            turnover=turnover,
            total_fees=total_fees,
            total_slippage=total_slippage,
            win_rate=win_rate,
            profit_factor=profit_factor,
            benchmark_comparisons=benchmark_results,
            outperformance_summary=outperformance_summary,
            recommendations=recommendations
        )
    
    def _generate_recommendations(
        self,
        sharpe: float,
        max_dd: float,
        benchmark_results: List[BenchmarkResult],
        turnover: float
    ) -> List[str]:
        """Generate recommendations based on performance analysis."""
        recommendations = []
        
        if sharpe < 0.5:
            recommendations.append("Sharpe ratio below 0.5 - consider improving risk-adjusted returns")
        
        if max_dd > 0.3:
            recommendations.append("Max drawdown exceeds 30% - strengthen risk controls")
        
        underperform_count = sum(1 for r in benchmark_results if r.excess_metric < 0)
        if underperform_count > 0:
            recommendations.append(f"Underperforms {underperform_count} benchmark(s) - investigate underperformance causes")
        
        if turnover > 2.0:  # More than 200% annual turnover
            recommendations.append("High turnover detected - consider reducing trading frequency to lower costs")
        
        if not recommendations:
            recommendations.append("System performs reasonably well against benchmarks - continue monitoring")
        
        return recommendations
    
    # Helper methods
    def _calculate_sharpe(self, returns: pd.Series, risk_free: float = None) -> float:
        """Calculate annualized Sharpe ratio."""
        if len(returns) < 2 or returns.std() == 0:
            return 0.0
        
        if risk_free is None:
            risk_free = self.risk_free_rate
        
        daily_rf = risk_free / 252
        excess_returns = returns - daily_rf
        sharpe = excess_returns.mean() / (excess_returns.std() + 1e-8) * np.sqrt(252)
        return sharpe
    
    def _calculate_sortino(self, returns: pd.Series, risk_free: float = None) -> float:
        """Calculate annualized Sortino ratio."""
        if len(returns) < 2:
            return 0.0
        
        if risk_free is None:
            risk_free = self.risk_free_rate
        
        daily_rf = risk_free / 252
        downside = returns[returns < daily_rf]
        
        if len(downside) < 2 or downside.std() == 0:
            return 0.0
        
        excess = returns.mean() - daily_rf
        sortino = excess / (downside.std() + 1e-8) * np.sqrt(252)
        return sortino
    
    def _calculate_drawdown(self, cumulative: pd.Series) -> pd.Series:
        """Calculate drawdown series from cumulative returns."""
        running_max = cumulative.expanding().max()
        return (cumulative - running_max) / running_max
    
    def _calculate_recovery_time(self, drawdown: pd.Series) -> int:
        """Calculate average recovery time from drawdowns."""
        if not (drawdown < -0.01).any():
            return 0
        
        recovery_days = []
        in_drawdown = False
        start_day = 0
        
        for i, dd in enumerate(drawdown):
            if dd < -0.01 and not in_drawdown:
                in_drawdown = True
                start_day = i
            elif dd >= 0 and in_drawdown:
                recovery_days.append(i - start_day)
                in_drawdown = False
        
        return int(np.mean(recovery_days)) if recovery_days else 0
    
    def _calculate_turnover(self, returns: pd.Series) -> float:
        """Estimate annual turnover from returns."""
        positions = np.sign(returns).fillna(0)
        changes = positions.diff().abs()
        # Average daily turnover, annualized
        return changes.mean() / 2 * 252
    
    def _t_test(self, returns: pd.Series) -> float:
        """Perform t-test for significance of excess returns."""
        if len(returns) < 10:
            return 1.0
        
        try:
            t_stat, p_value = stats.ttest_1samp(returns, 0)
            return p_value
        except Exception:
            return 1.0
