"""
Standard benchmark definitions for crypto trading systems.

This module provides pre-configured benchmark strategies commonly used
for evaluating cryptocurrency trading performance.
"""

from typing import Dict, List
from .benchmark_system import BenchmarkType


def get_standard_benchmarks() -> List[Dict]:
    """
    Get standard benchmarks for crypto trading systems.
    
    These benchmarks cover:
    - Passive strategies (buy and hold)
    - Simple rule-based strategies (momentum, mean reversion, trend)
    - Risk parity allocation
    - Market index proxy
    - Cash/risk-free rate
    
    Returns:
        List of benchmark configurations that can be passed to BenchmarkSystem
    """
    return [
        # ===== PASSIVE BENCHMARKS =====
        {
            'name': 'Buy & Hold BTC',
            'type': BenchmarkType.PASSIVE,
            'symbol': 'BTC/USDT',
            'include_costs': True,
            'cost': 0.001,
            'description': 'Simple buy and hold strategy for Bitcoin',
        },
        {
            'name': 'Buy & Hold ETH',
            'type': BenchmarkType.PASSIVE,
            'symbol': 'ETH/USDT',
            'include_costs': True,
            'cost': 0.001,
            'description': 'Simple buy and hold strategy for Ethereum',
        },
        {
            'name': 'Equal Weight Portfolio',
            'type': BenchmarkType.PASSIVE,
            'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
            'include_costs': True,
            'cost': 0.001,
            'description': 'Equal-weighted portfolio of major cryptocurrencies',
        },
        
        # ===== SIMPLE STRATEGY BENCHMARKS =====
        {
            'name': 'Momentum Strategy (20d)',
            'type': BenchmarkType.SIMPLE,
            'strategy': 'momentum',
            'period': 20,
            'symbol': 'BTC/USDT',
            'include_costs': True,
            'cost': 0.001,
            'description': 'Go long when 20-day momentum is positive',
        },
        {
            'name': 'Mean Reversion (20d MA)',
            'type': BenchmarkType.SIMPLE,
            'strategy': 'mean_reversion',
            'period': 20,
            'symbol': 'BTC/USDT',
            'include_costs': True,
            'cost': 0.001,
            'description': 'Go long when price is below 20-day moving average',
        },
        {
            'name': 'Trend Following (200d MA)',
            'type': BenchmarkType.SIMPLE,
            'strategy': 'trend',
            'period': 200,
            'symbol': 'BTC/USDT',
            'include_costs': True,
            'cost': 0.001,
            'description': 'Go long when price is above 200-day moving average',
        },
        
        # ===== RISK PARITY BENCHMARK =====
        {
            'name': 'Risk Parity',
            'type': BenchmarkType.RISK_PARITY,
            'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
            'include_costs': True,
            'cost': 0.001,
            'description': 'Inverse volatility weighted portfolio',
        },
        
        # ===== MARKET INDEX =====
        {
            'name': 'Crypto Market Index (BTC)',
            'type': BenchmarkType.MARKET,
            'symbol': 'BTC/USDT',
            'description': 'Bitcoin as proxy for overall crypto market',
        },
        
        # ===== CASH / RISK-FREE =====
        {
            'name': 'Cash (Risk-Free)',
            'type': BenchmarkType.CASH,
            'rate': 0.0,  # Zero risk-free rate typical for crypto
            'description': 'Holding cash with zero risk-free rate',
        },
    ]


def get_minimal_benchmarks() -> List[Dict]:
    """
    Get a minimal set of essential benchmarks.
    
    Use this when you want a quick comparison without running all benchmarks.
    
    Returns:
        List of essential benchmark configurations
    """
    return [
        {
            'name': 'Buy & Hold BTC',
            'type': BenchmarkType.PASSIVE,
            'symbol': 'BTC/USDT',
            'include_costs': True,
        },
        {
            'name': 'Momentum Strategy',
            'type': BenchmarkType.SIMPLE,
            'strategy': 'momentum',
            'period': 20,
            'symbol': 'BTC/USDT',
            'include_costs': True,
        },
        {
            'name': 'Crypto Market Index',
            'type': BenchmarkType.MARKET,
            'symbol': 'BTC/USDT',
        },
    ]


def get_conservative_benchmarks() -> List[Dict]:
    """
    Get conservative benchmarks for risk-focused evaluation.
    
    Returns:
        List of conservative benchmark configurations
    """
    return [
        {
            'name': 'Cash (Risk-Free)',
            'type': BenchmarkType.CASH,
            'rate': 0.0,
        },
        {
            'name': 'Buy & Hold BTC',
            'type': BenchmarkType.PASSIVE,
            'symbol': 'BTC/USDT',
            'include_costs': True,
        },
        {
            'name': 'Risk Parity',
            'type': BenchmarkType.RISK_PARITY,
            'symbols': ['BTC/USDT', 'ETH/USDT'],
            'include_costs': True,
        },
        {
            'name': 'Trend Following (200d)',
            'type': BenchmarkType.SIMPLE,
            'strategy': 'trend',
            'period': 200,
            'symbol': 'BTC/USDT',
            'include_costs': True,
        },
    ]


def get_aggressive_benchmarks() -> List[Dict]:
    """
    Get aggressive benchmarks for alpha-focused evaluation.
    
    Returns:
        List of aggressive benchmark configurations
    """
    return [
        {
            'name': 'Momentum Strategy (20d)',
            'type': BenchmarkType.SIMPLE,
            'strategy': 'momentum',
            'period': 20,
            'symbol': 'BTC/USDT',
            'include_costs': True,
        },
        {
            'name': 'Mean Reversion (20d)',
            'type': BenchmarkType.SIMPLE,
            'strategy': 'mean_reversion',
            'period': 20,
            'symbol': 'BTC/USDT',
            'include_costs': True,
        },
        {
            'name': 'Equal Weight Portfolio',
            'type': BenchmarkType.PASSIVE,
            'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
            'include_costs': True,
        },
    ]
