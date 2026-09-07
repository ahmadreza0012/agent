"""
Data Provider Abstractions

This module provides a clean interface for fetching market data from various sources.
"""

import logging

from .base import DataProvider, OHLCVData
from .historical import HistoricalDataProvider
from .cached import CachedDataProvider
from .symbol_mapper import SymbolMapper
from .quality_validator import DataQualityValidator

__all__ = [
    'DataProvider',
    'OHLCVData',
    'HistoricalDataProvider',
    'CachedDataProvider',
    'SymbolMapper',
    'DataQualityValidator',
]


def create_data_provider(source: str = 'historical', symbols=None):
    """
    Factory function to create appropriate data provider based on source.
    
    Args:
        source: Data source ('historical', 'cached', 'binance')
        symbols: List of symbols to fetch
        
    Returns:
        DataProvider instance
    """
    if source == 'historical':
        return HistoricalDataProvider(symbols=symbols)
    elif source == 'cached':
        return CachedDataProvider(symbols=symbols)
    else:
        # Default to historical as fallback (avoids Binance restrictions)
        logger = logging.getLogger(__name__)
        logger.warning(f"Unknown source '{source}', falling back to historical data provider")
        return HistoricalDataProvider(symbols=symbols)
