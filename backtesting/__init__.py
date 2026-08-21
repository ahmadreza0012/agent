"""
Backtesting Module
------------------

Advanced backtesting and robustness analysis tools for crypto portfolio strategies.

Includes:
- Event-driven backtester with walk-forward evaluation
- Monte Carlo simulation framework
- Bootstrap resampling analysis
- Parameter perturbation studies
- Scenario analysis and stress testing
- Robustness metrics and confidence intervals
"""

from .robustness import RobustnessAnalyzer

__all__ = ['RobustnessAnalyzer']
