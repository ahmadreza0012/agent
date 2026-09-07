"""
Performance Profiler for the Trading System.

This module provides comprehensive performance profiling capabilities
to identify bottlenecks and measure optimization improvements.
"""

import time
import functools
import logging
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from contextlib import contextmanager
import cProfile
import pstats
import io
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ProfileResult:
    """Result from profiling a function."""
    function_name: str
    total_time: float
    call_count: int
    min_time: float
    max_time: float
    avg_time: float
    children: List['ProfileResult'] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'function_name': self.function_name,
            'total_time': self.total_time,
            'call_count': self.call_count,
            'min_time': self.min_time,
            'max_time': self.max_time,
            'avg_time': self.avg_time,
        }


class PerformanceProfiler:
    """
    Performance profiler for the trading system.
    
    Features:
    - Function-level profiling with decorator
    - Context manager for code blocks
    - Statistical analysis (min, max, avg, total)
    - Hierarchical profiling with parent-child relationships
    - Report generation
    - Thread-safe operation
    
    Usage:
        # As a decorator
        @profiler.profile("my_function")
        def my_function():
            pass
        
        # As a context manager
        with profiler.measure("code_block"):
            # code here
        
        # Generate report
        print(profiler.report())
    """
    
    def __init__(self, enabled: bool = False):
        """
        Initialize the profiler.
        
        Args:
            enabled: Whether profiling is enabled (default False for production)
        """
        self.enabled = enabled
        self.results: Dict[str, List[float]] = {}
        self._profile_stack: List[str] = []
        self._lock = threading.RLock()
        self._cprofile = cProfile.Profile()
        self._cprofile_enabled = False
    
    def profile(self, name: Optional[str] = None):
        """
        Decorator to profile a function.
        
        Args:
            name: Optional custom name for the function
            
        Returns:
            Decorated function with profiling
            
        Example:
            @profiler.profile("expensive_calculation")
            def calculate():
                pass
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if not self.enabled:
                    return func(*args, **kwargs)
                
                func_name = name or func.__name__
                
                with self.measure(func_name):
                    result = func(*args, **kwargs)
                
                return result
            return wrapper
        return decorator
    
    def _record_time(self, name: str, elapsed: float):
        """Record a timing measurement."""
        with self._lock:
            if name not in self.results:
                self.results[name] = []
            self.results[name].append(elapsed)
    
    @contextmanager
    def measure(self, name: str):
        """
        Context manager for measuring blocks of code.
        
        Args:
            name: Name for this measurement block
            
        Example:
            with profiler.measure("data_loading"):
                data = load_data()
        """
        if not self.enabled:
            yield
            return
        
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self._record_time(name, elapsed)
    
    def enable_cprofile(self):
        """Enable cProfile for detailed function-level profiling."""
        self._cprofile_enabled = True
        self._cprofile.enable()
        logger.info("cProfile enabled")
    
    def disable_cprofile(self):
        """Disable cProfile."""
        if self._cprofile_enabled:
            self._cprofile.disable()
            self._cprofile_enabled = False
            logger.info("cProfile disabled")
    
    def get_cprofile_stats(self, top_n: int = 20) -> str:
        """
        Get cProfile statistics.
        
        Args:
            top_n: Number of top functions to show
            
        Returns:
            Formatted string of cProfile stats
        """
        if not self._cprofile_enabled:
            return "cProfile not enabled"
        
        stream = io.StringIO()
        stats = pstats.Stats(self._cprofile, stream=stream)
        stats.sort_stats('cumulative')
        stats.print_stats(top_n)
        return stream.getvalue()
    
    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Get statistics for all profiled functions.
        
        Returns:
            Dictionary mapping function names to statistics
        """
        stats = {}
        with self._lock:
            for name, times in self.results.items():
                if not times:
                    continue
                stats[name] = {
                    'total_time': sum(times),
                    'call_count': len(times),
                    'avg_time': sum(times) / len(times),
                    'min_time': min(times),
                    'max_time': max(times),
                }
        return stats
    
    def get_top_functions(self, n: int = 10, sort_by: str = 'total_time') -> List[tuple]:
        """
        Get top N functions by time.
        
        Args:
            n: Number of functions to return
            sort_by: Sort key ('total_time', 'avg_time', 'call_count')
            
        Returns:
            List of (name, stats) tuples
        """
        stats = self.get_stats()
        if not stats:
            return []
        
        sorted_stats = sorted(
            stats.items(),
            key=lambda x: x[1].get(sort_by, 0),
            reverse=True
        )
        return sorted_stats[:n]
    
    def report(self, top_n: int = 30) -> str:
        """
        Generate a performance report.
        
        Args:
            top_n: Number of top functions to show
            
        Returns:
            Formatted performance report string
        """
        stats = self.get_stats()
        if not stats:
            return "No profiling data collected."
        
        lines = ["=" * 100]
        lines.append("PERFORMANCE PROFILE REPORT")
        lines.append("=" * 100)
        lines.append("")
        lines.append(f"Total functions profiled: {len(stats)}")
        lines.append("")
        
        # Sort by total time descending
        sorted_stats = sorted(
            stats.items(),
            key=lambda x: x[1]['total_time'],
            reverse=True
        )[:top_n]
        
        lines.append(f"{'Function':<60} {'Total (s)':<12} {'Calls':<10} {'Avg (ms)':<12} {'Max (ms)':<12}")
        lines.append("-" * 100)
        
        for name, stat in sorted_stats:
            total = stat['total_time']
            calls = stat['call_count']
            avg_ms = stat['avg_time'] * 1000
            max_ms = stat['max_time'] * 1000
            lines.append(f"{name:<60} {total:<12.4f} {calls:<10} {avg_ms:<12.2f} {max_ms:<12.2f}")
        
        lines.append("")
        lines.append("=" * 100)
        
        # Add cProfile stats if available
        if self._cprofile_enabled:
            lines.append("")
            lines.append("CPROFILE DETAILED STATS:")
            lines.append("-" * 100)
            lines.append(self.get_cprofile_stats(top_n))
        
        return "\n".join(lines)
    
    def save_report(self, filename: str = 'performance_profile_report.txt', top_n: int = 30):
        """
        Save performance report to file.
        
        Args:
            filename: Output filename
            top_n: Number of top functions to include
        """
        report = self.report(top_n=top_n)
        Path(filename).write_text(report)
        logger.info(f"Performance report saved to {filename}")
        return filename
    
    def reset(self):
        """Reset all profiling data."""
        with self._lock:
            self.results.clear()
            self._profile_stack.clear()
        logger.debug("Profiler reset")
    
    def summary(self) -> str:
        """
        Get a brief summary of profiling results.
        
        Returns:
            Summary string with top 5 slowest functions
        """
        top = self.get_top_functions(5, 'total_time')
        if not top:
            return "No profiling data"
        
        lines = ["Performance Summary:", "-" * 40]
        for name, stats in top:
            lines.append(f"{name}: {stats['total_time']:.3f}s ({stats['call_count']} calls)")
        
        return "\n".join(lines)


# Global profiler instance
profiler = PerformanceProfiler(enabled=False)


class Timer:
    """Simple timer context manager for quick measurements."""
    
    def __init__(self, name: str = "Operation", log_level: int = logging.DEBUG):
        self.name = name
        self.log_level = log_level
        self.elapsed = 0.0
    
    def __enter__(self):
        self.start = time.perf_counter()
        return self
    
    def __exit__(self, *args):
        self.elapsed = time.perf_counter() - self.start
        logger.log(self.log_level, f"{self.name}: {self.elapsed:.4f}s")


def timed(func):
    """Decorator to log function execution time."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with Timer(func.__name__):
            return func(*args, **kwargs)
    return wrapper


def benchmark(func: Callable, *args, iterations: int = 10, **kwargs) -> Dict[str, float]:
    """
    Benchmark a function over multiple iterations.
    
    Args:
        func: Function to benchmark
        *args: Positional arguments for the function
        iterations: Number of iterations to run
        **kwargs: Keyword arguments for the function
        
    Returns:
        Dictionary with benchmark statistics
    """
    times = []
    
    # Warmup
    for _ in range(max(1, iterations // 5)):
        func(*args, **kwargs)
    
    # Measure
    for _ in range(iterations):
        start = time.perf_counter()
        func(*args, **kwargs)
        times.append(time.perf_counter() - start)
    
    return {
        'mean': sum(times) / len(times),
        'std': (sum((t - sum(times)/len(times))**2 for t in times) / len(times)) ** 0.5,
        'min': min(times),
        'max': max(times),
        'median': sorted(times)[len(times)//2],
        'total': sum(times),
    }
