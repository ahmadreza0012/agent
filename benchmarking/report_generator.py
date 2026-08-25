"""
Benchmark report generator for creating text and visual reports.

This module provides functionality to generate comprehensive reports
comparing trading system performance against benchmarks.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Optional
import logging
from pathlib import Path
from datetime import datetime

from .benchmark_system import ComprehensiveBenchmarkReport, BenchmarkResult

logger = logging.getLogger(__name__)


class BenchmarkReportGenerator:
    """
    Generate visual and text reports from benchmark results.
    
    This class creates both human-readable text reports and visual
    charts to help analyze trading system performance relative to benchmarks.
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize the report generator.
        
        Args:
            config: Configuration dictionary with optional parameters:
                - output_dir: Directory to save reports (default: 'benchmark_reports')
        """
        self.config = config or {}
        self.output_dir = Path(self.config.get('output_dir', 'benchmark_reports'))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def generate_text_report(self, report: ComprehensiveBenchmarkReport) -> str:
        """
        Generate a comprehensive text-based benchmark report.
        
        Args:
            report: ComprehensiveBenchmarkReport object
            
        Returns:
            Formatted text report as string
        """
        lines = [
            "=" * 80,
            f"BENCHMARK REPORT: {report.system_name}",
            "=" * 80,
            "",
            f"Report Generated: {report.timestamp}",
            f"Analysis Period: {report.period_start} to {report.period_end}",
            "",
            "=" * 80,
            "SYSTEM PERFORMANCE SUMMARY",
            "=" * 80,
            "",
            "RETURNS",
            "-" * 40,
            f"Total Return:        {report.total_return:>12.2%}",
            f"Annualized Return:   {report.annualized_return:>12.2%}",
            f"Annualized Volatility: {report.annualized_volatility:>12.2%}",
            "",
            "RISK-ADJUSTED METRICS",
            "-" * 40,
            f"Sharpe Ratio:        {report.sharpe_ratio:>12.2f}",
            f"Sortino Ratio:       {report.sortino_ratio:>12.2f}",
            f"Calmar Ratio:        {report.calmar_ratio:>12.2f}",
            "",
            "DRAWDOWN ANALYSIS",
            "-" * 40,
            f"Max Drawdown:        {report.max_drawdown:>12.2%}",
            f"Average Drawdown:    {report.avg_drawdown:>12.2%}",
            f"Recovery Time:       {report.recovery_time:>12d} days",
            "",
            "TRADING STATISTICS",
            "-" * 40,
            f"Win Rate:            {report.win_rate:>12.2%}",
            f"Profit Factor:       {report.profit_factor:>12.2f}",
            f"Turnover (annual):   {report.turnover:>12.2%}",
            f"Total Fees:          {report.total_fees:>12.2%}",
            f"Total Slippage:      {report.total_slippage:>12.2%}",
            "",
            "=" * 80,
            "BENCHMARK COMPARISONS",
            "=" * 80,
            "",
        ]
        
        # Table header
        lines.append(f"{'Benchmark':<35} {'Sys Sharpe':<12} {'Bench Sharpe':<12} {'Excess':<10} {'Significant':<12}")
        lines.append("-" * 80)
        
        for result in report.benchmark_comparisons:
            status = "✅ Yes" if result.is_significant else "⚠️ No" if result.excess_metric > 0 else "❌ No"
            lines.append(
                f"{result.benchmark_name:<35} "
                f"{result.system_metric:<12.2f} "
                f"{result.benchmark_metric:<12.2f} "
                f"{result.excess_metric:<+10.2f} "
                f"{status:<12}"
            )
        
        lines.extend([
            "",
            "=" * 80,
            "OUTPERFORMANCE SUMMARY",
            "=" * 80,
            "",
        ])
        
        outperform_count = sum(1 for v in report.outperformance_summary.values() if v)
        total_count = len(report.outperformance_summary)
        
        lines.append(f"Outperforms {outperform_count} of {total_count} benchmarks")
        lines.append("")
        
        for name, outperforms in report.outperformance_summary.items():
            status = "✅" if outperforms else "❌"
            lines.append(f"{status} {name}: {'Outperforms' if outperforms else 'Underperforms'}")
        
        lines.extend([
            "",
            "=" * 80,
            "RECOMMENDATIONS",
            "=" * 80,
            "",
        ])
        
        for i, rec in enumerate(report.recommendations, 1):
            lines.append(f"{i}. {rec}")
        
        lines.extend([
            "",
            "=" * 80,
            "END OF REPORT",
            "=" * 80,
        ])
        
        return "\n".join(lines)
    
    def generate_visual_report(
        self,
        report: ComprehensiveBenchmarkReport,
        system_returns: pd.Series,
        benchmark_returns_dict: Dict[str, pd.Series],
        filename: Optional[str] = None
    ) -> plt.Figure:
        """
        Generate a comprehensive visual benchmark report.
        
        Args:
            report: ComprehensiveBenchmarkReport object
            system_returns: System returns series
            benchmark_returns_dict: Dictionary mapping benchmark names to returns
            filename: Optional filename to save the figure
            
        Returns:
            Matplotlib Figure object
        """
        # Set style
        plt.style.use('seaborn-v0_8-whitegrid')
        
        fig, axes = plt.subplots(3, 2, figsize=(16, 14))
        fig.suptitle(f'Benchmark Report: {report.system_name}', fontsize=16, fontweight='bold')
        
        # 1. Cumulative returns comparison
        ax = axes[0, 0]
        cumulative_system = (1 + system_returns).cumprod()
        cumulative_system.plot(ax=ax, label='System', color='darkblue', linewidth=2)
        
        colors = plt.cm.tab10(np.linspace(0, 1, len(benchmark_returns_dict)))
        for idx, (name, returns) in enumerate(benchmark_returns_dict.items()):
            cumulative = (1 + returns).cumprod()
            cumulative.plot(ax=ax, label=name, color=colors[idx], alpha=0.7, linewidth=1.5)
        
        ax.set_title('Cumulative Returns Comparison', fontsize=12, fontweight='bold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Cumulative Return')
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # 2. Rolling Sharpe ratio (60-day window)
        ax = axes[0, 1]
        rolling_sharpe = system_returns.rolling(60).apply(
            lambda x: x.mean() / (x.std() + 1e-8) * np.sqrt(252), raw=False
        )
        rolling_sharpe.plot(ax=ax, color='darkblue', label='System', linewidth=2)
        
        ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        ax.axhline(y=0.5, color='orange', linestyle='--', alpha=0.7, label='Good (0.5)')
        ax.axhline(y=1.0, color='green', linestyle='--', alpha=0.7, label='Excellent (1.0)')
        
        ax.set_title('Rolling 60-Day Sharpe Ratio', fontsize=12, fontweight='bold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Sharpe Ratio')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
        
        # 3. Drawdown comparison
        ax = axes[1, 0]
        drawdown_system = cumulative_system / cumulative_system.expanding().max() - 1
        drawdown_system.plot(ax=ax, label='System', color='darkblue', linewidth=2)
        
        for idx, (name, returns) in enumerate(benchmark_returns_dict.items()):
            cumulative = (1 + returns).cumprod()
            drawdown = cumulative / cumulative.expanding().max() - 1
            drawdown.plot(ax=ax, label=name, color=colors[idx], alpha=0.7, linewidth=1.5)
        
        ax.set_title('Drawdown Comparison', fontsize=12, fontweight='bold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Drawdown')
        ax.legend(loc='lower left', fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.fill_between(ax.get_xlim(), 0, -0.2, alpha=0.1, color='red', label='Danger Zone (-20%)')
        
        # 4. Monthly return heatmap
        ax = axes[1, 1]
        monthly_returns = system_returns.resample('ME').apply(lambda x: (1 + x).prod() - 1)
        
        if len(monthly_returns) > 0:
            # Create pivot table for heatmap
            years = monthly_returns.index.year
            months = monthly_returns.index.month
            monthly_pivot = monthly_returns.groupby([years, months]).first()
            
            if len(monthly_pivot) > 0:
                try:
                    monthly_pivot = monthly_pivot.unstack(level=1)
                    monthly_pivot.columns = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                                            'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                    
                    sns.heatmap(
                        monthly_pivot,
                        ax=ax,
                        cmap='RdYlGn',
                        center=0,
                        annot=True,
                        fmt='.1%',
                        cbar_kws={'label': 'Monthly Return'},
                        vmin=-0.2,
                        vmax=0.2
                    )
                    ax.set_title('Monthly Return Heatmap', fontsize=12, fontweight='bold')
                    ax.set_xlabel('Month')
                    ax.set_ylabel('Year')
                except Exception as e:
                    ax.text(0.5, 0.5, f'Insufficient data for heatmap\n{str(e)}', 
                           transform=ax.transAxes, ha='center', va='center')
        else:
            ax.text(0.5, 0.5, 'No data available for heatmap', 
                   transform=ax.transAxes, ha='center', va='center')
        
        # 5. Performance metrics bar chart
        ax = axes[2, 0]
        metrics = ['Sharpe', 'Sortino', 'Calmar']
        system_metrics = [report.sharpe_ratio, report.sortino_ratio, report.calmar_ratio]
        
        # Calculate benchmark metrics for comparison
        benchmark_avg_metrics = []
        for metric_idx, metric_name in enumerate(metrics):
            bench_values = []
            for name, returns in benchmark_returns_dict.items():
                if metric_name == 'Sharpe':
                    value = self._calculate_sharpe(returns)
                elif metric_name == 'Sortino':
                    value = self._calculate_sortino(returns)
                else:  # Calmar
                    value = self._calculate_calmar(returns)
                bench_values.append(value)
            benchmark_avg_metrics.append(np.mean(bench_values) if bench_values else 0)
        
        x = np.arange(len(metrics))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, system_metrics, width, label='System', color='darkblue')
        bars2 = ax.bar(x + width/2, benchmark_avg_metrics, width, label='Avg Benchmark', color='lightgray')
        
        ax.set_title('Performance Metrics Comparison', fontsize=12, fontweight='bold')
        ax.set_xlabel('Metric')
        ax.set_ylabel('Value')
        ax.set_xticks(x)
        ax.set_xticklabels(metrics)
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        
        # Add value labels on bars
        for bar in bars1:
            height = bar.get_height()
            ax.annotate(f'{height:.2f}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom', fontsize=9)
        
        # 6. Benchmark outperformance summary
        ax = axes[2, 1]
        outperformance_data = list(report.outperformance_summary.values())
        benchmark_names = list(report.outperformance_summary.keys())
        
        # Truncate long names
        benchmark_names = [name[:20] + '...' if len(name) > 23 else name for name in benchmark_names]
        
        colors_outperf = ['green' if v else 'red' for v in outperformance_data]
        y_pos = np.arange(len(benchmark_names))
        
        bars = ax.barh(y_pos, [1 if v else -1 for v in outperformance_data], 
                      color=colors_outperf, alpha=0.7)
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(benchmark_names, fontsize=8)
        ax.set_xlabel('Performance vs Benchmark', fontsize=10)
        ax.set_title('Benchmark Outperformance Summary', fontsize=12, fontweight='bold')
        ax.axvline(x=0, color='black', linewidth=1)
        ax.set_xlim(-1.2, 1.2)
        
        # Add text labels
        for i, (name, v) in enumerate(zip(benchmark_names, outperformance_data)):
            label = '✓' if v else '✗'
            ax.text(0.9 if v else -0.9, i, label, 
                   ha='right' if v else 'left', va='center', fontsize=10)
        
        plt.tight_layout()
        
        if filename:
            save_path = self.output_dir / filename
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Visual report saved to {save_path}")
        else:
            plt.show()
        
        return fig
    
    def generate_csv_report(self, report: ComprehensiveBenchmarkReport, filename: str = None) -> str:
        """
        Generate CSV report with benchmark comparison data.
        
        Args:
            report: ComprehensiveBenchmarkReport object
            filename: Optional filename to save CSV
            
        Returns:
            Path to saved CSV file
        """
        # Create DataFrame with benchmark comparisons
        data = []
        for result in report.benchmark_comparisons:
            data.append({
                'benchmark_name': result.benchmark_name,
                'benchmark_type': result.benchmark_type.value,
                'system_sharpe': result.system_metric,
                'benchmark_sharpe': result.benchmark_metric,
                'excess_sharpe': result.excess_metric,
                'excess_percentage': result.excess_percentage,
                'p_value': result.p_value,
                'is_significant': result.is_significant,
                'outperforms': result.excess_metric > 0,
            })
        
        df = pd.DataFrame(data)
        
        if filename:
            save_path = self.output_dir / filename
            df.to_csv(save_path, index=False)
            logger.info(f"CSV report saved to {save_path}")
            return str(save_path)
        
        return df.to_csv(index=False)
    
    def _calculate_sharpe(self, returns: pd.Series) -> float:
        """Calculate annualized Sharpe ratio."""
        if len(returns) < 2 or returns.std() == 0:
            return 0.0
        return returns.mean() / (returns.std() + 1e-8) * np.sqrt(252)
    
    def _calculate_sortino(self, returns: pd.Series) -> float:
        """Calculate annualized Sortino ratio."""
        downside = returns[returns < 0]
        if len(downside) < 2 or downside.std() == 0:
            return 0.0
        return returns.mean() / (downside.std() + 1e-8) * np.sqrt(252)
    
    def _calculate_calmar(self, returns: pd.Series) -> float:
        """Calculate Calmar ratio."""
        cumulative = (1 + returns).cumprod()
        total_return = cumulative.iloc[-1] - 1
        n_years = len(returns) / 252
        annualized = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else 0
        drawdown = cumulative / cumulative.expanding().max() - 1
        max_dd = abs(drawdown.min())
        return annualized / max_dd if max_dd > 0 else 0
