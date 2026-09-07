"""
Benchmarking module for trading system performance comparison.

This module provides comprehensive benchmark comparison capabilities
to evaluate whether the trading system adds value over simple alternatives.
"""

from .benchmark_system import (
    BenchmarkSystem,
    BenchmarkType,
    BenchmarkResult,
    ComprehensiveBenchmarkReport,
)
from .standard_benchmarks import get_standard_benchmarks
from .report_generator import BenchmarkReportGenerator

__all__ = [
    'BenchmarkSystem',
    'BenchmarkType',
    'BenchmarkResult',
    'ComprehensiveBenchmarkReport',
    'get_standard_benchmarks',
    'BenchmarkReportGenerator',
]
