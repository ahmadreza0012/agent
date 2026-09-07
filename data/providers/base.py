"""
Base Data Provider Interface

Abstract base class for all data providers.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass
import pandas as pd


@dataclass
class OHLCVData:
    """
    Container for OHLCV data with metadata.
    
    Attributes:
        df: DataFrame with columns [Open, High, Low, Close, Volume]
        symbol: Trading pair symbol (canonical format)
        timeframe: Candle timeframe (e.g., '1h', '1d')
        source: Data source identifier
        volume_available: Whether volume data is real or placeholder
        start_date: First timestamp in data
        end_date: Last timestamp in data
        row_count: Number of rows
    """
    df: pd.DataFrame
    symbol: str
    timeframe: str
    source: str
    volume_available: bool = True
    start_date: Optional[pd.Timestamp] = None
    end_date: Optional[pd.Timestamp] = None
    row_count: int = 0
    
    def __post_init__(self):
        if self.df is not None and not self.df.empty:
            self.start_date = self.df.index.min()
            self.end_date = self.df.index.max()
            self.row_count = len(self.df)
    
    def __repr__(self):
        return (f"OHLCVData(symbol={self.symbol}, timeframe={self.timeframe}, "
                f"rows={self.row_count}, volume_available={self.volume_available})")


class DataProvider(ABC):
    """
    Abstract base class for market data providers.
    
    All data providers must implement these methods.
    """
    
    @abstractmethod
    def fetch_ohlcv(self, symbol: str, timeframe: str, since_days: int) -> OHLCVData:
        """
        Fetch OHLCV data for a single symbol.
        
        Args:
            symbol: Trading pair in canonical format (e.g., 'BTC/USDT')
            timeframe: Candle timeframe ('1h', '1d', etc.)
            since_days: Number of days of historical data
            
        Returns:
            OHLCVData object with fetched data and metadata
            
        Raises:
            ValueError: If symbol is invalid or data unavailable
            ConnectionError: If data source is unreachable
        """
        pass
    
    @abstractmethod
    def fetch_all_symbols(self, symbols: List[str], timeframe: str, 
                          since_days: int) -> Dict[str, OHLCVData]:
        """
        Fetch OHLCV data for multiple symbols.
        
        Args:
            symbols: List of trading pairs in canonical format
            timeframe: Candle timeframe
            since_days: Number of days of historical data
            
        Returns:
            Dictionary mapping symbol to OHLCVData
        """
        pass
    
    @abstractmethod
    def supports_timeframe(self, timeframe: str) -> bool:
        """Check if provider supports given timeframe."""
        pass
    
    @abstractmethod
    def get_source_name(self) -> str:
        """Return human-readable source name."""
        pass
