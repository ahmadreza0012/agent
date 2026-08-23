#!/usr/bin/env python3
"""
Benchmark execution script for comparing trading system performance.

This script runs a comprehensive benchmark analysis comparing the trading
system against standard benchmarks including buy-and-hold, momentum, mean
reversion, risk parity, and market indices.

Usage:
    python scripts/run_benchmarks.py [--minimal] [--output-dir DIR]
"""

import sys
import argparse
import logging
from pathlib import Path

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from benchmarking.benchmark_system import BenchmarkSystem, BenchmarkType
from benchmarking.standard_benchmarks import (
    get_standard_benchmarks,
    get_minimal_benchmarks,
)
from benchmarking.report_generator import BenchmarkReportGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_sample_system_returns(price_data: pd.DataFrame, seed: int = 42) -> pd.Series:
    """
    Generate sample system returns for demonstration.
    
    In production, replace this with actual system returns from your strategy.
    
    Args:
        price_data: Price data DataFrame
        seed: Random seed for reproducibility
        
    Returns:
        Series of simulated system returns
    """
    np.random.seed(seed)
    
    # Get BTC returns as base
    if 'BTC/USDT' in price_data.columns:
        btc_returns = price_data['BTC/USDT'].pct_change().dropna()
    else:
        btc_returns = price_data.iloc[:, 0].pct_change().dropna()
    
    # Simulate a system with slight alpha over buy-and-hold
    # Add small positive bias and reduce volatility slightly
    alpha = 0.0002  # Small daily alpha
    noise = np.random.normal(0, 0.02, len(btc_returns))
    
    system_returns = btc_returns + alpha + noise * 0.5
    
    return system_returns


def run_benchmarks(
    price_data: pd.DataFrame,
    system_returns: pd.Series,
    use_minimal: bool = False,
    output_dir: str = None
) -> dict:
    """
    Run complete benchmark comparison.
    
    Args:
        price_data: Price data for benchmarks (columns are symbols)
        system_returns: System returns series
        use_minimal: Use minimal set of benchmarks
        output_dir: Directory to save reports
        
    Returns:
        Dictionary with report and generated files
    """
    logger.info("Starting benchmark analysis...")
    
    # Initialize benchmark system
    config = {
        'risk_free_rate': 0.0,  # Zero risk-free rate for crypto
        'significance_level': 0.05,
    }
    benchmark_system = BenchmarkSystem(config=config)
    
    # Select benchmarks
    if use_minimal:
        benchmarks = get_minimal_benchmarks()
        logger.info(f"Using minimal benchmark set ({len(benchmarks)} benchmarks)")
    else:
        benchmarks = get_standard_benchmarks()
        logger.info(f"Using full benchmark set ({len(benchmarks)} benchmarks)")
    
    # Run comparison
    logger.info("Running benchmark comparisons...")
    try:
        report = benchmark_system.compare_to_benchmarks(
            system_returns=system_returns,
            price_data=price_data,
            benchmark_configs=benchmarks
        )
        logger.info("Benchmark comparison completed successfully")
    except Exception as e:
        logger.error(f"Benchmark comparison failed: {e}")
        raise
    
    # Initialize report generator
    if output_dir:
        report_config = {'output_dir': output_dir}
    else:
        report_config = {}
    
    report_generator = BenchmarkReportGenerator(config=report_config)
    
    # Generate text report
    logger.info("Generating text report...")
    text_report = report_generator.generate_text_report(report)
    print("\n" + text_report)
    
    # Save text report
    text_file = 'benchmark_report.txt'
    if output_dir:
        text_path = Path(output_dir) / text_file
    else:
        text_path = Path(text_file)
    
    with open(text_path, 'w') as f:
        f.write(text_report)
    logger.info(f"Text report saved to {text_path}")
    
    # Generate benchmark returns dict for visualization
    logger.info("Preparing visualization data...")
    benchmark_returns = {}
    for config in benchmarks:
        name = config.get('name', 'unknown')
        bench_type = config.get('type')
        if isinstance(bench_type, str):
            bench_type = BenchmarkType(bench_type)
        
        try:
            if bench_type == BenchmarkType.PASSIVE:
                returns = benchmark_system._passive_benchmark(price_data, config)
            elif bench_type == BenchmarkType.SIMPLE:
                returns = benchmark_system._simple_strategy(price_data, config)
            elif bench_type == BenchmarkType.RISK_PARITY:
                returns = benchmark_system._risk_parity_benchmark(price_data, config)
            elif bench_type == BenchmarkType.MARKET:
                returns = benchmark_system._market_benchmark(price_data, config)
            elif bench_type == BenchmarkType.CASH:
                returns = benchmark_system._cash_benchmark(config)
            else:
                continue
            
            # Align with system returns
            common_idx = system_returns.index.intersection(returns.index)
            if len(common_idx) > 10:
                benchmark_returns[name] = returns.loc[common_idx]
                
        except Exception as e:
            logger.warning(f"Could not generate benchmark {name}: {e}")
    
    # Generate visual report
    logger.info("Generating visual report...")
    try:
        fig = report_generator.generate_visual_report(
            report,
            system_returns,
            benchmark_returns,
            filename='benchmark_report.png'
        )
        logger.info("Visual report generated successfully")
    except Exception as e:
        logger.warning(f"Could not generate visual report: {e}")
        fig = None
    
    # Generate CSV report
    logger.info("Generating CSV report...")
    csv_path = report_generator.generate_csv_report(report, filename='benchmark_comparison.csv')
    logger.info(f"CSV report saved to {csv_path}")
    
    # Generate metrics summary
    metrics_data = {
        'metric': [
            'Total Return',
            'Annualized Return',
            'Annualized Volatility',
            'Sharpe Ratio',
            'Sortino Ratio',
            'Calmar Ratio',
            'Max Drawdown',
            'Win Rate',
            'Profit Factor',
            'Turnover',
        ],
        'value': [
            report.total_return,
            report.annualized_return,
            report.annualized_volatility,
            report.sharpe_ratio,
            report.sortino_ratio,
            report.calmar_ratio,
            report.max_drawdown,
            report.win_rate,
            report.profit_factor,
            report.turnover,
        ]
    }
    metrics_df = pd.DataFrame(metrics_data)
    metrics_file = 'benchmark_metrics.csv'
    if output_dir:
        metrics_path = Path(output_dir) / metrics_file
    else:
        metrics_path = Path(metrics_file)
    
    metrics_df.to_csv(metrics_path, index=False)
    logger.info(f"Metrics saved to {metrics_path}")
    
    return {
        'report': report,
        'text_file': str(text_path),
        'csv_file': csv_path,
        'metrics_file': str(metrics_path),
        'visual_file': str(Path(output_dir or '.') / 'benchmark_report.png') if fig else None,
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Run benchmark analysis for trading system'
    )
    parser.add_argument(
        '--minimal',
        action='store_true',
        help='Use minimal set of benchmarks'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='benchmark_reports',
        help='Directory to save reports'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        default='2020-01-01',
        help='Start date for data'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        default='2024-01-01',
        help='End date for data'
    )
    
    args = parser.parse_args()
    
    # Create output directory
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Load price data
    logger.info(f"Loading price data from {args.start_date} to {args.end_date}...")
    
    try:
        from data.providers.historical import HistoricalDataProvider
        provider = HistoricalDataProvider()
        
        price_data = provider.get_historical_data(
            symbols=['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
            start=args.start_date,
            end=args.end_date,
            timeframe='1d'
        )
        
        if isinstance(price_data, dict):
            # Convert dict to DataFrame if needed
            price_data = pd.DataFrame(price_data)
            
    except Exception as e:
        logger.warning(f"Could not load historical data: {e}")
        logger.info("Generating sample data for demonstration...")
        
        # Generate sample data
        dates = pd.date_range(start=args.start_date, end=args.end_date, freq='D')
        np.random.seed(42)
        
        # Simulate price data
        btc_prices = 10000 * np.cumprod(1 + np.random.normal(0.0005, 0.03, len(dates)))
        eth_prices = 500 * np.cumprod(1 + np.random.normal(0.0006, 0.04, len(dates)))
        sol_prices = 20 * np.cumprod(1 + np.random.normal(0.0008, 0.05, len(dates)))
        
        price_data = pd.DataFrame({
            'BTC/USDT': btc_prices,
            'ETH/USDT': eth_prices,
            'SOL/USDT': sol_prices,
        }, index=dates)
    
    logger.info(f"Loaded price data with {len(price_data)} rows and {len(price_data.columns)} columns")
    
    # Generate or load system returns
    logger.info("Getting system returns...")
    
    try:
        # Try to get actual system returns
        from backtesting.attribution import PerformanceAttribution
        attribution = PerformanceAttribution()
        system_returns = attribution.get_system_returns()
        
        if system_returns is None or len(system_returns) == 0:
            raise ValueError("No system returns available")
            
    except Exception as e:
        logger.warning(f"Could not load system returns: {e}")
        logger.info("Generating sample system returns for demonstration...")
        system_returns = generate_sample_system_returns(price_data)
    
    logger.info(f"System returns: {len(system_returns)} observations")
    logger.info(f"  Mean: {system_returns.mean():.6f}")
    logger.info(f"  Std: {system_returns.std():.6f}")
    logger.info(f"  Sharpe: {system_returns.mean() / (system_returns.std() + 1e-8) * np.sqrt(252):.2f}")
    
    # Run benchmarks
    results = run_benchmarks(
        price_data=price_data,
        system_returns=system_returns,
        use_minimal=args.minimal,
        output_dir=str(output_path)
    )
    
    # Print summary
    print("\n" + "=" * 80)
    print("BENCHMARK ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"\nReports saved to: {output_path}")
    print(f"  - Text Report: {results['text_file']}")
    print(f"  - CSV Data: {results['csv_file']}")
    print(f"  - Metrics: {results['metrics_file']}")
    if results['visual_file']:
        print(f"  - Visual Report: {results['visual_file']}")
    
    # Return exit code based on performance
    report = results['report']
    outperform_count = sum(1 for v in report.outperformance_summary.values() if v)
    total_count = len(report.outperformance_summary)
    
    if outperform_count > total_count / 2:
        print(f"\n✅ System outperforms {outperform_count}/{total_count} benchmarks")
        return 0
    else:
        print(f"\n⚠️  System underperforms {total_count - outperform_count}/{total_count} benchmarks")
        return 1


if __name__ == '__main__':
    sys.exit(main())
