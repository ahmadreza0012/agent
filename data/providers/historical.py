"""
Historical Data Provider

Fetches data from yfinance and CoinGecko for research purposes.
Properly handles volume availability flags.
"""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import time

from .base import DataProvider, OHLCVData
from .symbol_mapper import SymbolMapper

logger = logging.getLogger(__name__)


class HistoricalDataProvider(DataProvider):
    """
    Fetch historical OHLCV data from yfinance (primary) and CoinGecko (fallback).
    
    Priority:
    1. yfinance for hourly and daily data (reliable, includes volume)
    2. CoinGecko for daily data only (free API limitations, no volume)
    
    Volume Handling:
    - yfinance: Real volume data (volume_available=True)
    - CoinGecko: No volume in free tier (volume_available=False, column set to NaN)
    """
    
    def __init__(self, symbols: Optional[List[str]] = None):
        """
        Initialize historical data provider.
        
        Args:
            symbols: List of canonical symbols (default: major crypto pairs)
        """
        self.symbols = symbols or SymbolMapper().CANONICAL_SYMBOLS
        self.mapper = SymbolMapper()
        logger.info(f"Initialized HistoricalDataProvider for {len(self.symbols)} symbols")
    
    def get_source_name(self) -> str:
        return "yfinance/CoinGecko"
    
    def supports_timeframe(self, timeframe: str) -> bool:
        return timeframe in ['1h', '4h', '1d']
    
    def fetch_ohlcv(self, symbol: str, timeframe: str, since_days: int) -> OHLCVData:
        """
        Fetch OHLCV data for a single symbol.
        
        Args:
            symbol: Canonical trading pair (e.g., 'BTC/USDT')
            timeframe: Candle timeframe ('1h', '4h', '1d')
            since_days: Number of days of historical data
            
        Returns:
            OHLCVData with fetched data and metadata
        """
        logger.info(f"Fetching {timeframe} data for {symbol} ({since_days} days)")
        
        # Enforce limits based on timeframe
        if timeframe == '1h':
            max_days = 90
            if since_days > max_days:
                logger.warning(f"Hourly data limited to {max_days} days. Reducing from {since_days}.")
                since_days = max_days
        else:
            max_days = 365
            if since_days > max_days:
                logger.warning(f"Daily data limited to {max_days} days. Reducing from {since_days}.")
                since_days = max_days
        
        # Try yfinance first (preferred: has real volume)
        try:
            df = self._fetch_from_yfinance(symbol, timeframe, since_days)
            return OHLCVData(
                df=df,
                symbol=symbol,
                timeframe=timeframe,
                source='yfinance',
                volume_available=True
            )
        except Exception as e:
            logger.warning(f"yfinance fetch failed for {symbol}: {e}")
        
        # Fallback to CoinGecko (daily only, no volume)
        if timeframe != '1d':
            raise ValueError(f"CoinGecko fallback only supports daily data, not {timeframe}")
        
        try:
            df = self._fetch_from_coingecko(symbol, since_days)
            return OHLCVData(
                df=df,
                symbol=symbol,
                timeframe='1d',
                source='coingecko',
                volume_available=False  # CRITICAL: Mark volume as unavailable
            )
        except Exception as e:
            raise ValueError(f"No sufficient data retrieved for {symbol} from any source")
    
    def _fetch_from_yfinance(self, symbol: str, timeframe: str, 
                              since_days: int) -> pd.DataFrame:
        """Fetch from yfinance (includes real volume)."""
        import yfinance as yf
        
        ticker_symbol = self.mapper.to_yfinance_ticker(symbol)
        if ticker_symbol is None:
            raise ValueError(f"Symbol {symbol} not mapped to yfinance ticker")
        
        logger.debug(f"yfinance ticker: {ticker_symbol}")
        
        ticker = yf.Ticker(ticker_symbol)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=since_days)
        
        df = ticker.history(start=start_date, end=end_date, interval=timeframe)
        
        if df.empty or len(df) < 10:
            raise ValueError(f"No sufficient data from yfinance for {symbol}")
        
        # Standardize column names
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df.rename(columns={
            'Open': 'Open', 'High': 'High', 'Low': 'Low',
            'Close': 'Close', 'Volume': 'Volume'
        }, inplace=True)
        
        logger.info(f"✅ Retrieved {len(df)} candles from yfinance for {symbol}")
        return df
    
    def _fetch_from_coingecko(self, symbol: str, since_days: int) -> pd.DataFrame:
        """
        Fetch from CoinGecko (daily only, NO VOLUME in free tier).
        
        CRITICAL: Volume column is set to NaN (not 0) to indicate unavailability.
        Strategies requiring volume must handle this gracefully.
        """
        from pycoingecko import CoinGeckoAPI
        
        coin_id = self.mapper.to_coingecko_id(symbol)
        if coin_id is None:
            raise ValueError(f"Symbol {symbol} not mapped to CoinGecko ID")
        
        api = CoinGeckoAPI()
        
        # Determine API days parameter
        if since_days > 90:
            api_days = 365
        elif since_days > 30:
            api_days = 90
        elif since_days > 14:
            api_days = 30
        elif since_days > 1:
            api_days = 14
        else:
            api_days = 1
        
        max_retries = 3
        retry_delay = 60
        
        for attempt in range(max_retries):
            try:
                ohlc_data = api.get_coin_ohlc_by_id(
                    coin_id, vs_currency='usd', days=api_days
                )
                
                if ohlc_data and len(ohlc_data) >= 10:
                    break
                else:
                    logger.warning(f"CoinGecko returned insufficient data")
                    raise ValueError("Insufficient data from CoinGecko")
                    
            except Exception as e:
                error_str = str(e)
                if '429' in error_str or 'rate limit' in error_str.lower():
                    if attempt < max_retries - 1:
                        logger.warning(f"Rate limit hit, waiting {retry_delay}s")
                        time.sleep(retry_delay)
                    else:
                        raise
                elif attempt == max_retries - 1:
                    raise
                else:
                    time.sleep(1)
        
        # Convert to DataFrame
        df = pd.DataFrame(ohlc_data, columns=['timestamp', 'open', 'high', 'low', 'close'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df.rename(columns={
            'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'
        }, inplace=True)
        
        # CRITICAL: Set volume to NaN (not 0) to indicate unavailability
        # This prevents strategies from treating missing volume as "zero volume"
        df['Volume'] = np.nan
        
        logger.info(f"✅ Retrieved {len(df)} daily candles from CoinGecko for {symbol} "
                   f"(Volume: NaN/unavailable)")
        return df
    
    def fetch_all_symbols(self, symbols: List[str], timeframe: str,
                          since_days: int) -> Dict[str, OHLCVData]:
        """Fetch data for multiple symbols."""
        data = {}
        for symbol in symbols:
            try:
                ohlcv = self.fetch_ohlcv(symbol, timeframe, since_days)
                data[symbol] = ohlcv
            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")
        
        return data
