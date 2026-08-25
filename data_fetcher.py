"""
Data Fetcher Module for Cryptocurrency Algorithmic Trading
Uses CCXT library with Binance exchange for clean, reliable OHLCV data.
"""

import ccxt
import pandas as pd
from datetime import datetime, timezone
from typing import List, Optional, Dict
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CryptoDataFetcher:
    """
    Robust cryptocurrency data fetcher using CCXT and Binance exchange.
    Handles rate limits gracefully and returns clean DataFrames with DatetimeIndex.
    """
    
    def __init__(self, exchange_id: str = 'binance', rate_limit_delay: float = 0.2):
        """
        Initialize the data fetcher with specified exchange.
        
        Args:
            exchange_id: Exchange identifier (default: 'binance')
            rate_limit_delay: Delay between API calls in seconds to respect rate limits
        """
        self.exchange_id = exchange_id
        self.rate_limit_delay = rate_limit_delay
        self.exchange = self._initialize_exchange(exchange_id)
        self._last_request_time = 0
        
    def _initialize_exchange(self, exchange_id: str) -> ccxt.Exchange:
        """Initialize CCXT exchange with proper configuration."""
        try:
            exchange_class = getattr(ccxt, exchange_id)
            exchange = exchange_class({
                'enableRateLimit': True,
                'timeout': 30000,
                'options': {
                    'defaultType': 'spot',
                }
            })
            logger.info(f"Successfully initialized {exchange_id} exchange")
            return exchange
        except AttributeError:
            raise ValueError(f"Exchange '{exchange_id}' not supported by CCXT")
        except Exception as e:
            raise ConnectionError(f"Failed to initialize exchange: {e}")
    
    def _respect_rate_limit(self):
        """Ensure we don't exceed rate limits by adding delays between requests."""
        current_time = time.time()
        elapsed = current_time - self._last_request_time
        if elapsed < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - elapsed
            time.sleep(sleep_time)
        self._last_request_time = time.time()
    
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = '1d',
        since: Optional[datetime] = None,
        limit: int = 500,
        max_retries: int = 3
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from the exchange and return as a clean DataFrame.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT', 'ETH/USDT')
            timeframe: Candle timeframe (e.g., '1m', '5m', '1h', '1d')
            since: Start datetime for fetching data
            limit: Maximum number of candles to fetch per request
            max_retries: Maximum retry attempts on failure
            
        Returns:
            pd.DataFrame with DatetimeIndex and columns: open, high, low, close, volume
        """
        # Normalize symbol format for CCXT
        if '/' not in symbol:
            # Assume format like 'BTCUSDT' -> convert to 'BTC/USDT'
            if symbol.endswith('USDT'):
                symbol = f"{symbol[:-4]}/{symbol[-4:]}"
            elif symbol.endswith('USD'):
                symbol = f"{symbol[:-3]}/{symbol[-3:]}"
            else:
                symbol = f"{symbol}/USDT"
        
        symbol = symbol.upper()
        
        # Convert since to milliseconds timestamp if provided
        since_ms = None
        if since is not None:
            if isinstance(since, datetime):
                since_ms = int(since.timestamp() * 1000)
            else:
                since_ms = int(since)
        
        all_ohlcv = []
        retries = 0
        
        while retries < max_retries:
            try:
                self._respect_rate_limit()
                
                ohlcv_data = self.exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=since_ms,
                    limit=limit
                )
                
                if not ohlcv_data:
                    logger.warning(f"No data returned for {symbol}")
                    break
                
                all_ohlcv.extend(ohlcv_data)
                
                # If we got less than limit, we've reached the end
                if len(ohlcv_data) < limit:
                    break
                    
                # For pagination, update since to last candle + 1ms
                last_timestamp = ohlcv_data[-1][0]
                since_ms = last_timestamp + 1
                
                # Add small delay for pagination
                time.sleep(0.1)
                
                break  # Success, exit retry loop
                
            except ccxt.RateLimitExceeded:
                retries += 1
                wait_time = 2 ** retries  # Exponential backoff
                logger.warning(f"Rate limit exceeded for {symbol}. Waiting {wait_time}s...")
                time.sleep(wait_time)
                
            except ccxt.NetworkError as e:
                retries += 1
                wait_time = 2 ** retries
                logger.warning(f"Network error for {symbol}: {e}. Retrying ({retries}/{max_retries})...")
                time.sleep(wait_time)
                
            except ccxt.ExchangeError as e:
                retries += 1
                logger.warning(f"Exchange error for {symbol}: {e}. Retrying ({retries}/{max_retries})...")
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Unexpected error fetching {symbol}: {e}")
                raise
        
        if not all_ohlcv:
            raise ValueError(f"Failed to fetch data for {symbol} after {max_retries} retries")
        
        return self._parse_ohlcv(all_ohlcv, symbol)
    
    def _parse_ohlcv(self, ohlcv_data: List[List], symbol: str) -> pd.DataFrame:
        """
        Parse raw OHLCV data into a clean DataFrame with DatetimeIndex.
        
        Args:
            ohlcv_data: Raw OHLCV data from CCXT
            symbol: Trading pair symbol
            
        Returns:
            Clean DataFrame with DatetimeIndex
        """
        df = pd.DataFrame(
            ohlcv_data,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        
        # Convert timestamp to datetime and set as index
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.set_index('timestamp', inplace=True)
        
        # Convert numeric columns to float
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            df[col] = df[col].astype(float)
        
        # Remove any duplicate indices
        df = df[~df.index.duplicated(keep='first')]
        
        # Sort by timestamp
        df.sort_index(inplace=True)
        
        # Validate data quality - check for extreme values
        self._validate_data_quality(df, symbol)
        
        logger.info(f"Parsed {len(df)} candles for {symbol} from {df.index[0]} to {df.index[-1]}")
        
        return df
    
    def _validate_data_quality(self, df: pd.DataFrame, symbol: str):
        """
        Validate data quality and log warnings for suspicious values.
        
        Args:
            df: DataFrame to validate
            symbol: Trading pair symbol
        """
        # Check for zero or negative prices
        if (df['close'] <= 0).any():
            logger.warning(f"{symbol}: Found non-positive close prices")
        
        # Check for extreme price jumps (>50% in single candle)
        returns = df['close'].pct_change().abs()
        extreme_jumps = returns[returns > 0.5]
        if len(extreme_jumps) > 0:
            logger.warning(f"{symbol}: Found {len(extreme_jumps)} extreme price jumps (>50%)")
        
        # Check for volume spikes
        if 'volume' in df.columns:
            volume_std = df['volume'].std()
            if volume_std > 0:
                volume_zscore = (df['volume'] - df['volume'].mean()) / volume_std
                extreme_volume = volume_zscore[volume_zscore.abs() > 10]
                if len(extreme_volume) > 0:
                    logger.info(f"{symbol}: Found {len(extreme_volume)} extreme volume spikes")
    
    def fetch_multiple_pairs(
        self,
        symbols: List[str],
        timeframe: str = '1d',
        since: Optional[datetime] = None,
        limit: int = 500
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch OHLCV data for multiple trading pairs.
        
        Args:
            symbols: List of trading pair symbols
            timeframe: Candle timeframe
            since: Start datetime for fetching data
            limit: Maximum number of candles to fetch per request
            
        Returns:
            Dictionary mapping symbol to DataFrame
        """
        result = {}
        for symbol in symbols:
            try:
                df = self.fetch_ohlcv(symbol, timeframe, since, limit)
                result[symbol] = df
                logger.info(f"Successfully fetched data for {symbol}")
            except Exception as e:
                logger.error(f"Failed to fetch data for {symbol}: {e}")
                result[symbol] = None
        
        return result
    
    def get_available_symbols(self, quote_currency: str = 'USDT') -> List[str]:
        """
        Get list of available trading pairs for a quote currency.
        
        Args:
            quote_currency: Quote currency to filter by (default: 'USDT')
            
        Returns:
            List of available symbol strings
        """
        try:
            markets = self.exchange.load_markets()
            symbols = [
                symbol for symbol, info in markets.items()
                if info.get('quote') == quote_currency and info.get('active', True)
            ]
            return symbols
        except Exception as e:
            logger.error(f"Failed to load markets: {e}")
            return []
    
    def close(self):
        """Close the exchange connection."""
        if self.exchange:
            self.exchange.close()
            logger.info("Exchange connection closed")


# Convenience function for quick data fetching
def get_crypto_data(
    symbol: str,
    timeframe: str = '1d',
    since: Optional[datetime] = None,
    limit: int = 500,
    exchange: str = 'binance'
) -> pd.DataFrame:
    """
    Convenience function to fetch crypto OHLCV data.
    
    Args:
        symbol: Trading pair symbol (e.g., 'BTC/USDT')
        timeframe: Candle timeframe
        since: Start datetime
        limit: Maximum candles to fetch
        exchange: Exchange to use
        
    Returns:
        DataFrame with OHLCV data
    """
    fetcher = CryptoDataFetcher(exchange_id=exchange)
    try:
        return fetcher.fetch_ohlcv(symbol, timeframe, since, limit)
    finally:
        fetcher.close()


# Alias for backward compatibility with main.py
DataFetcher = CryptoDataFetcher


if __name__ == "__main__":
    # Example usage
    fetcher = CryptoDataFetcher()
    
    try:
        # Fetch BTC/USDT daily data
        btc_data = fetcher.fetch_ohlcv('BTC/USDT', timeframe='1d', limit=100)
        print(f"\nBTC/USDT Data Shape: {btc_data.shape}")
        print(btc_data.tail())
        
        # Fetch multiple pairs
        symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
        multi_data = fetcher.fetch_multiple_pairs(symbols)
        
        for sym, df in multi_data.items():
            if df is not None:
                print(f"\n{sym}: {len(df)} candles, Range: {df.index[0]} to {df.index[-1]}")
    finally:
        fetcher.close()
