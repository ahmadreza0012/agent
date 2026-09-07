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
from .multi_provider import MultiProviderDataFetcher

__all__ = [
    'DataProvider',
    'OHLCVData',
    'HistoricalDataProvider',
    'CachedDataProvider',
    'SymbolMapper',
    'DataQualityValidator',
    'MultiProviderDataFetcher',
]


def create_data_provider(source: str = 'multi', symbols=None, primary_exchange: str = 'binance'):
    """
    Factory function to create appropriate data provider based on source.
    
    Args:
        source: Data source ('multi', 'historical', 'cached', 'binance')
            - 'multi': Multi-provider with automatic failover (RECOMMENDED)
            - 'historical': yfinance/CoinGecko fallback
            - 'cached': Local cached data
        symbols: List of symbols to fetch
        primary_exchange: Primary exchange for multi-provider ('binance', 'bybit', etc.)
        
    Returns:
        DataProvider instance
    """
    if source == 'multi':
        return MultiProviderDataFetcher(symbols=symbols, primary_exchange=primary_exchange)
    elif source == 'historical':
        return HistoricalDataProvider(symbols=symbols)
    elif source == 'cached':
        return CachedDataProvider(symbols=symbols)
    else:
        # Default to multi-provider for maximum data coverage
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Unknown source '{source}', falling back to multi-provider data fetcher"
        )
        return MultiProviderDataFetcher(symbols=symbols, primary_exchange=primary_exchange)
