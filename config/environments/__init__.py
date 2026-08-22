"""
Environment configurations package.

This package contains environment-specific configuration files:
- development: Local development with paper trading
- testing: Automated test configuration
- paper: Paper trading with real market data
- shadow: Shadow trading (live data, simulated execution)
- production: Live trading with real capital
"""

from .development import get_config as get_development_config
from .testing import get_config as get_testing_config
from .paper import get_config as get_paper_config
from .shadow import get_config as get_shadow_config
from .production import get_config as get_production_config

__all__ = [
    'get_development_config',
    'get_testing_config',
    'get_paper_config',
    'get_shadow_config',
    'get_production_config',
]
