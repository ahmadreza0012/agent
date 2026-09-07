"""
System Profiling Script for the Trading System.

This script profiles the complete trading pipeline to identify bottlenecks
and measure performance characteristics.

Usage:
    python scripts/profile_system.py
"""

import sys
sys.path.insert(0, '/workspace')

import time
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

from utils.profiler import profiler, PerformanceProfiler, Timer, benchmark
from utils.cache import cache, SmartCache

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_sample_data(n_rows: int = 1000, n_symbols: int = 5) -> dict:
    """Create sample OHLCV data for profiling."""
    np.random.seed(42)
    
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ADA/USDT', 'DOT/USDT'][:n_symbols]
    data = {}
    
    for symbol in symbols:
        dates = pd.date_range('2023-01-01', periods=n_rows, freq='D')
        df = pd.DataFrame({
            'open': np.random.randn(n_rows).cumsum() + 100,
            'high': np.random.randn(n_rows).cumsum() + 100 + abs(np.random.randn(n_rows)),
            'low': np.random.randn(n_rows).cumsum() + 100 - abs(np.random.randn(n_rows)),
            'close': np.random.randn(n_rows).cumsum() + 100,
            'volume': np.random.randint(1000, 100000, n_rows),
        }, index=dates)
        data[symbol] = df
    
    return data


def profile_data_operations():
    """Profile common data operations."""
    print("\n" + "=" * 80)
    print("PROFILING DATA OPERATIONS")
    print("=" * 80)
    
    data = create_sample_data(n_rows=5000, n_symbols=3)
    df = data['BTC/USDT']
    
    # Profile return calculations
    with profiler.measure("returns_calculation"):
        returns = df['close'].pct_change()
    
    # Profile rolling volatility
    with profiler.measure("rolling_volatility"):
        rolling_vol = returns.rolling(20).std()
    
    # Profile multiple lag features
    with profiler.measure("lag_features"):
        for lag in [1, 2, 3, 5, 10]:
            df[f'close_lag{lag}'] = df['close'].shift(lag)
    
    # Profile EMA calculations
    with profiler.measure("ema_calculation"):
        ema_20 = df['close'].ewm(span=20).mean()
        ema_50 = df['close'].ewm(span=50).mean()
    
    # Profile correlation matrix
    with profiler.measure("correlation_matrix"):
        corr_matrix = df[['open', 'high', 'low', 'close', 'volume']].corr()
    
    print(f"Returns calculation: {returns.sum():.4f}")
    print(f"Rolling volatility: {rolling_vol.iloc[-1]:.4f}")
    print(f"EMA 20: {ema_20.iloc[-1]:.4f}")


def profile_covariance_operations():
    """Profile covariance matrix calculations."""
    print("\n" + "=" * 80)
    print("PROFILING COVARIANCE OPERATIONS")
    print("=" * 80)
    
    data = create_sample_data(n_rows=500, n_symbols=10)
    
    # Calculate returns for all symbols
    returns_dict = {}
    for symbol, df in data.items():
        returns_dict[symbol] = df['close'].pct_change().dropna()
    
    returns_df = pd.DataFrame(returns_dict)
    
    # Profile standard covariance
    with profiler.measure("covariance_standard"):
        cov_std = returns_df.cov()
    
    # Profile correlation
    with profiler.measure("correlation"):
        corr = returns_df.corr()
    
    # Profile eigenvalue decomposition
    with profiler.measure("eigenvalue_decomposition"):
        eigenvals, eigenvecs = np.linalg.eigh(cov_std.values)
    
    print(f"Covariance shape: {cov_std.shape}")
    print(f"Largest eigenvalue: {eigenvals.max():.6f}")


def profile_portfolio_operations():
    """Profile portfolio optimization operations."""
    print("\n" + "=" * 80)
    print("PROFILING PORTFOLIO OPERATIONS")
    print("=" * 80)
    
    n_assets = 10
    np.random.seed(42)
    
    # Generate random returns
    returns = np.random.randn(500, n_assets) * 0.01
    
    # Profile covariance calculation
    with profiler.measure("portfolio_covariance"):
        cov_matrix = np.cov(returns, rowvar=False)
    
    # Profile mean returns
    with profiler.measure("mean_returns"):
        mean_returns = returns.mean(axis=0)
    
    # Profile inverse covariance (for Markowitz)
    with profiler.measure("inverse_covariance"):
        try:
            cov_inv = np.linalg.inv(cov_matrix)
        except np.linalg.LinAlgError:
            cov_inv = np.linalg.pinv(cov_matrix)
    
    # Profile portfolio variance calculation
    weights = np.ones(n_assets) / n_assets
    with profiler.measure("portfolio_variance"):
        port_var = weights.T @ cov_matrix @ weights
    
    print(f"Portfolio variance: {port_var:.6f}")
    print(f"Mean returns: {mean_returns.mean():.6f}")


def profile_caching():
    """Profile caching performance."""
    print("\n" + "=" * 80)
    print("PROFILING CACHING PERFORMANCE")
    print("=" * 80)
    
    test_cache = SmartCache(cache_dir='data/cache/test_cache', ttl_hours=1)
    test_cache.clear()
    
    def expensive_operation(x):
        """Simulate expensive computation."""
        time.sleep(0.01)  # 10ms delay
        return x ** 2
    
    # Profile without caching
    n_iterations = 10
    start = time.time()
    for i in range(n_iterations):
        expensive_operation(i)
    no_cache_time = time.time() - start
    
    # Profile with caching
    @test_cache.cached(ttl_hours=1)
    def cached_operation(x):
        return expensive_operation(x)
    
    start = time.time()
    for i in range(n_iterations):
        cached_operation(i)
    with_cache_time = time.time() - start
    
    print(f"Without caching: {no_cache_time:.3f}s ({n_iterations} calls)")
    print(f"With caching: {with_cache_time:.3f}s ({n_iterations} calls)")
    print(f"Speedup: {no_cache_time / with_cache_time:.2f}x")
    
    # Show cache stats
    print(f"Cache stats: {test_cache.stats()}")


def profile_full_pipeline():
    """Run the complete pipeline with profiling."""
    print("\n" + "=" * 80)
    print("PROFILING FULL PIPELINE")
    print("=" * 80)
    
    # Enable profiling
    profiler.enabled = True
    profiler.reset()
    
    # 1. Load/generate data
    print("Loading data...")
    with profiler.measure("data_loading"):
        data = create_sample_data(n_rows=1000, n_symbols=5)
    
    # 2. Data preprocessing
    print("Preprocessing data...")
    with profiler.measure("data_preprocessing"):
        for symbol, df in data.items():
            df['returns'] = df['close'].pct_change()
            df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
            
            # Technical indicators
            df['sma_20'] = df['close'].rolling(20).mean()
            df['sma_50'] = df['close'].rolling(50).mean()
            df['volatility'] = df['returns'].rolling(20).std()
    
    # 3. Feature engineering
    print("Engineering features...")
    with profiler.measure("feature_engineering"):
        for symbol, df in data.items():
            # Lag features
            for lag in [1, 2, 3, 5]:
                df[f'returns_lag{lag}'] = df['returns'].shift(lag)
            
            # Rolling features
            df['momentum'] = df['close'] / df['close'].shift(5) - 1
            df['mean_reversion'] = df['close'] - df['sma_20']
    
    # 4. Covariance calculation
    print("Calculating covariance...")
    with profiler.measure("covariance_calculation"):
        returns_dict = {s: df['returns'].dropna() for s, df in data.items()}
        returns_df = pd.DataFrame(returns_dict)
        cov_matrix = returns_df.cov()
    
    # 5. Risk metrics
    print("Calculating risk metrics...")
    with profiler.measure("risk_metrics"):
        for symbol, df in data.items():
            df['sharpe'] = (df['returns'].mean() / df['returns'].std()) * np.sqrt(252)
            df['max_drawdown'] = df['close'].cummax() - df['close']
    
    # 6. Portfolio optimization simulation
    print("Optimizing portfolio...")
    with profiler.measure("portfolio_optimization"):
        n_assets = len(data)
        weights = np.ones(n_assets) / n_assets
        port_return = sum(weights[i] * data[list(data.keys())[i]]['returns'].mean() 
                         for i in range(n_assets))
        port_risk = np.sqrt(weights.T @ cov_matrix.values @ weights)
    
    # Print results
    print(f"\nPortfolio expected return: {port_return * 252:.2%}")
    print(f"Portfolio annualized risk: {port_risk * np.sqrt(252):.2%}")
    
    # Generate report
    print("\n" + profiler.report())
    
    # Save report
    report_path = Path('performance_profile_report.txt')
    profiler.save_report(str(report_path))
    print(f"\nReport saved to {report_path}")
    
    return profiler.get_stats()


def run_benchmarks():
    """Run detailed benchmarks."""
    print("\n" + "=" * 80)
    print("RUNNING BENCHMARKS")
    print("=" * 80)
    
    from utils.profiler import benchmark
    
    # Benchmark different array sizes
    sizes = [100, 500, 1000, 5000]
    
    print("\nBenchmarking rolling mean:")
    for size in sizes:
        data = np.random.randn(size)
        result = benchmark(lambda x: pd.Series(x).rolling(20).mean(), data, iterations=20)
        print(f"  Size {size}: mean={result['mean']*1000:.2f}ms, std={result['std']*1000:.2f}ms")
    
    print("\nBenchmarking covariance:")
    for n in [5, 10, 20, 50]:
        returns = np.random.randn(500, n)
        result = benchmark(lambda x: np.cov(x, rowvar=False), returns, iterations=20)
        print(f"  Assets {n}: mean={result['mean']*1000:.2f}ms, std={result['std']*1000:.2f}ms")


def main():
    """Main profiling function."""
    print("=" * 80)
    print("TRADING SYSTEM PERFORMANCE PROFILER")
    print("=" * 80)
    print(f"Started at: {datetime.now().isoformat()}")
    
    start_time = time.time()
    
    try:
        # Run individual component profiles
        profile_data_operations()
        profile_covariance_operations()
        profile_portfolio_operations()
        profile_caching()
        
        # Run full pipeline profile
        stats = profile_full_pipeline()
        
        # Run benchmarks
        run_benchmarks()
        
    except Exception as e:
        logger.error(f"Profiling error: {e}", exc_info=True)
        raise
    
    total_time = time.time() - start_time
    print(f"\n{'=' * 80}")
    print(f"Total profiling time: {total_time:.2f}s")
    print(f"Completed at: {datetime.now().isoformat()}")
    print("=" * 80)
    
    # Summary
    print("\nPERFORMANCE SUMMARY")
    print("-" * 40)
    print(profiler.summary())


if __name__ == '__main__':
    main()
