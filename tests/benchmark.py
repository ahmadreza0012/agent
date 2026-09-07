"""
Performance Benchmarking Framework.

This module provides tools for measuring and comparing performance
of different implementations.

Usage:
    from tests.benchmark import Benchmark, benchmark_function
    
    benchmark = Benchmark(iterations=20)
    benchmark.run("Function A", func_a, arg1, arg2)
    benchmark.run("Function B", func_b, arg1, arg2)
    
    print(benchmark.report())
    benchmark.save_report('benchmark_results.csv')
"""

import sys
sys.path.insert(0, '/workspace')

import time
import statistics
import logging
from typing import Callable, List, Dict, Any, Optional
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Result from a benchmark run."""
    name: str
    mean_time: float
    std_time: float
    min_time: float
    max_time: float
    median_time: float
    n_iterations: int
    total_time: float = field(init=False)
    speedup_vs_baseline: float = field(default=1.0)
    
    def __post_init__(self):
        self.total_time = self.mean_time * self.n_iterations
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'mean_ms': self.mean_time * 1000,
            'std_ms': self.std_time * 1000,
            'min_ms': self.min_time * 1000,
            'max_ms': self.max_time * 1000,
            'median_ms': self.median_time * 1000,
            'iterations': self.n_iterations,
            'speedup': self.speedup_vs_baseline,
        }


class Benchmark:
    """
    Performance benchmarking system.
    
    Features:
    - Multiple iterations with warmup
    - Statistical analysis (mean, std, min, max, median)
    - Comparison against baseline
    - CSV report generation
    - DataFrame export
    
    Usage:
        benchmark = Benchmark(iterations=20, warmup=3)
        
        # Run benchmarks
        benchmark.run("Old Implementation", old_func, data)
        benchmark.run("New Implementation", new_func, data)
        
        # Generate report
        print(benchmark.report())
        benchmark.save_report('results.csv')
    """
    
    def __init__(self, iterations: int = 10, warmup: int = 2, verbose: bool = True):
        """
        Initialize benchmark runner.
        
        Args:
            iterations: Number of measurement iterations
            warmup: Number of warmup iterations (not measured)
            verbose: Print progress during benchmarking
        """
        self.iterations = iterations
        self.warmup = warmup
        self.verbose = verbose
        self.results: List[BenchmarkResult] = []
        self._baseline: Optional[BenchmarkResult] = None
    
    def run(self, name: str, func: Callable, *args, 
            iterations: Optional[int] = None, 
            **kwargs) -> BenchmarkResult:
        """
        Run a benchmark for a function.
        
        Args:
            name: Name for this benchmark
            func: Function to benchmark
            *args: Positional arguments for the function
            iterations: Override default iterations
            **kwargs: Keyword arguments for the function
            
        Returns:
            BenchmarkResult with timing statistics
        """
        n_iter = iterations or self.iterations
        times = []
        
        if self.verbose:
            logger.info(f"Benchmarking '{name}'...")
        
        # Warmup
        for i in range(self.warmup):
            try:
                func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Warmup failed for {name}: {e}")
                raise
        
        # Measure
        for i in range(n_iter):
            start = time.perf_counter()
            try:
                func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                times.append(elapsed)
            except Exception as e:
                logger.error(f"Iteration {i+1} failed for {name}: {e}")
                raise
        
        # Calculate statistics
        result = BenchmarkResult(
            name=name,
            mean_time=statistics.mean(times),
            std_time=statistics.stdev(times) if len(times) > 1 else 0,
            min_time=min(times),
            max_time=max(times),
            median_time=statistics.median(times),
            n_iterations=n_iter
        )
        
        # Calculate speedup vs baseline
        if self._baseline is not None and self._baseline.name != name:
            result.speedup_vs_baseline = self._baseline.mean_time / result.mean_time
        
        self.results.append(result)
        
        if self.verbose:
            logger.info(f"  {name}: {result.mean_time*1000:.2f}ms ± {result.std_time*1000:.2f}ms")
        
        return result
    
    def set_baseline(self, name: str):
        """
        Set a benchmark result as the baseline for comparison.
        
        Args:
            name: Name of the benchmark to use as baseline
        """
        for result in self.results:
            if result.name == name:
                self._baseline = result
                logger.info(f"Set baseline: {name} ({result.mean_time*1000:.2f}ms)")
                return
        logger.warning(f"Baseline '{name}' not found")
    
    def compare(self, name1: str, name2: str) -> Dict[str, Any]:
        """
        Compare two benchmark results.
        
        Args:
            name1: First benchmark name
            name2: Second benchmark name
            
        Returns:
            Dictionary with comparison metrics
        """
        r1 = next((r for r in self.results if r.name == name1), None)
        r2 = next((r for r in self.results if r.name == name2), None)
        
        if not r1 or not r2:
            return {'error': 'Benchmark not found'}
        
        speedup = r1.mean_time / r2.mean_time
        improvement = (r1.mean_time - r2.mean_time) / r1.mean_time * 100
        
        return {
            'faster': name2 if speedup > 1 else name1,
            'speedup': max(speedup, 1/speedup),
            'improvement_percent': abs(improvement),
            'time_saved_ms': abs(r1.mean_time - r2.mean_time) * 1000,
        }
    
    def report(self, sort_by: str = 'mean_time') -> pd.DataFrame:
        """
        Generate a report of all benchmarks.
        
        Args:
            sort_by: Column to sort by ('mean_time', 'name', etc.)
            
        Returns:
            DataFrame with benchmark results
        """
        if not self.results:
            return pd.DataFrame()
        
        data = [{
            'Function': r.name,
            'Mean (ms)': r.mean_time * 1000,
            'Std (ms)': r.std_time * 1000,
            'Median (ms)': r.median_time * 1000,
            'Min (ms)': r.min_time * 1000,
            'Max (ms)': r.max_time * 1000,
            'Iterations': r.n_iterations,
            'Speedup': r.speedup_vs_baseline,
        } for r in self.results]
        
        df = pd.DataFrame(data)
        
        if sort_by in df.columns:
            df = df.sort_values(sort_by, ascending=(sort_by != 'Speedup'))
        
        return df.reset_index(drop=True)
    
    def save_report(self, filename: str = 'benchmark_report.csv'):
        """
        Save benchmark report to CSV.
        
        Args:
            filename: Output filename
        """
        df = self.report()
        df.to_csv(filename, index=False)
        logger.info(f"Benchmark report saved to {filename}")
        return filename
    
    def summary(self) -> str:
        """
        Get a text summary of benchmark results.
        
        Returns:
            Formatted summary string
        """
        if not self.results:
            return "No benchmark results"
        
        lines = ["=" * 80]
        lines.append("BENCHMARK SUMMARY")
        lines.append("=" * 80)
        lines.append("")
        
        # Sort by mean time
        sorted_results = sorted(self.results, key=lambda r: r.mean_time)
        
        for i, result in enumerate(sorted_results):
            rank = i + 1
            lines.append(f"{rank}. {result.name}")
            lines.append(f"   Mean: {result.mean_time*1000:.2f}ms ± {result.std_time*1000:.2f}ms")
            lines.append(f"   Range: [{result.min_time*1000:.2f}ms, {result.max_time*1000:.2f}ms]")
            if result.speedup_vs_baseline != 1.0:
                lines.append(f"   Speedup: {result.speedup_vs_baseline:.2f}x vs baseline")
            lines.append("")
        
        # Show comparisons
        if len(self.results) >= 2:
            lines.append("-" * 80)
            lines.append("COMPARISONS:")
            fastest = sorted_results[0]
            slowest = sorted_results[-1]
            
            if fastest != slowest:
                overall_speedup = slowest.mean_time / fastest.mean_time
                lines.append(f"Fastest: {fastest.name} ({fastest.mean_time*1000:.2f}ms)")
                lines.append(f"Slowest: {slowest.name} ({slowest.mean_time*1000:.2f}ms)")
                lines.append(f"Overall Speedup: {overall_speedup:.2f}x")
        
        lines.append("=" * 80)
        return "\n".join(lines)
    
    def reset(self):
        """Clear all benchmark results."""
        self.results.clear()
        self._baseline = None


def benchmark_function(func: Callable, *args, 
                       iterations: int = 10, 
                       warmup: int = 2,
                       **kwargs) -> Dict[str, float]:
    """
    Quick benchmark a function.
    
    Args:
        func: Function to benchmark
        *args: Positional arguments
        iterations: Number of iterations
        warmup: Number of warmup iterations
        **kwargs: Keyword arguments
        
    Returns:
        Dictionary with timing statistics
    """
    times = []
    
    # Warmup
    for _ in range(warmup):
        func(*args, **kwargs)
    
    # Measure
    for _ in range(iterations):
        start = time.perf_counter()
        func(*args, **kwargs)
        times.append(time.perf_counter() - start)
    
    return {
        'mean': sum(times) / len(times),
        'std': statistics.stdev(times) if len(times) > 1 else 0,
        'min': min(times),
        'max': max(times),
        'median': statistics.median(times),
        'total': sum(times),
    }


def compare_implementations(name_old: str, func_old: Callable,
                            name_new: str, func_new: Callable,
                            *args, iterations: int = 20, **kwargs) -> Dict[str, Any]:
    """
    Compare two implementations of the same functionality.
    
    Args:
        name_old: Name of old implementation
        func_old: Old implementation function
        name_new: Name of new implementation
        func_new: New implementation function
        *args: Arguments to pass to both functions
        iterations: Number of benchmark iterations
        **kwargs: Keyword arguments
        
    Returns:
        Dictionary with comparison results
    """
    benchmark = Benchmark(iterations=iterations, warmup=2, verbose=False)
    
    # Run benchmarks
    result_old = benchmark.run(name_old, func_old, *args, **kwargs)
    result_new = benchmark.run(name_new, func_new, *args, **kwargs)
    
    # Calculate improvement
    speedup = result_old.mean_time / result_new.mean_time
    improvement_pct = (result_old.mean_time - result_new.mean_time) / result_old.mean_time * 100
    
    return {
        'old_mean_ms': result_old.mean_time * 1000,
        'new_mean_ms': result_new.mean_time * 1000,
        'speedup': speedup,
        'improvement_percent': improvement_pct,
        'time_saved_per_call_ms': (result_old.mean_time - result_new.mean_time) * 1000,
        'full_report': benchmark.summary(),
    }


# Convenience function for quick comparisons
def quick_benchmark(func: Callable, *args, iterations: int = 10, **kwargs) -> float:
    """
    Quick single-number benchmark (returns mean time in ms).
    
    Args:
        func: Function to benchmark
        *args: Positional arguments
        iterations: Number of iterations
        **kwargs: Keyword arguments
        
    Returns:
        Mean execution time in milliseconds
    """
    result = benchmark_function(func, *args, iterations=iterations, **kwargs)
    return result['mean'] * 1000
