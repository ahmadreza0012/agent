"""
Multi-Provider Data Fetcher

Aggregates data from multiple sources with automatic failover:
1. Binance/CCXT (primary for crypto) - up to 3 years
2. yfinance (fallback) - up to 3 years  
3. CoinGecko (fallback for daily) - up to 3 years

Ensures maximum data coverage by fetching from all available sources
and merging them intelligently.
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import logging
import time

from .base import DataProvider, OHLCVData
from .symbol_mapper import SymbolMapper

logger = logging.getLogger(__name__)


class MultiProviderDataFetcher(DataProvider):
    """
    Multi-source cryptocurrency data fetcher with automatic failover.
    
    Fetches up to 3 years of historical data by:
    1. Trying Binance/CCXT first (most reliable for crypto)
    2. Falling back to yfinance if Binance fails
    3. Using CoinGecko as final fallback for daily data
    
    Automatically paginates through exchange limits to get full history.
    """
    
    # Maximum candles per exchange request
    MAX_CANDLES_PER_REQUEST = 1000
    
    # Maximum days to fetch (3 years)
    MAX_DAYS = 365 * 3
    
    def __init__(
        self, 
        symbols: Optional[List[str]] = None,
        primary_exchange: str = 'binance'
    ):
        """
        Initialize multi-provider fetcher.
        
        Args:
            symbols: List of canonical symbols (default: major crypto pairs)
            primary_exchange: Primary exchange to try ('binance', 'bybit', etc.)
        """
        self.symbols = symbols or SymbolMapper().CANONICAL_SYMBOLS
        self.primary_exchange = primary_exchange
        self.mapper = SymbolMapper()
        self._ccxt_exchange = None
        
        logger.info(
            f"Initialized MultiProviderDataFetcher for {len(self.symbols)} symbols. "
            f"Primary exchange: {primary_exchange}"
        )
    
    def get_source_name(self) -> str:
        return f"Multi-Provider ({self.primary_exchange}/yfinance/CoinGecko)"
    
    def supports_timeframe(self, timeframe: str) -> bool:
        """Check if timeframe is supported."""
        return timeframe in ['1m', '5m', '15m', '1h', '4h', '1d']
    
    def _get_ccxt_exchange(self):
        """Get or create CCXT exchange instance."""
        if self._ccxt_exchange is None:
            try:
                import ccxt
                exchange_class = getattr(ccxt, self.primary_exchange, ccxt.binance)
                self._ccxt_exchange = exchange_class({
                    'enableRateLimit': True,
                    'timeout': 30000,
                    'options': {'defaultType': 'spot'}
                })
                logger.info(f"Connected to {self.primary_exchange} via CCXT")
            except Exception as e:
                logger.error(f"Failed to initialize CCXT exchange: {e}")
                self._ccxt_exchange = None
        return self._ccxt_exchange
    
    def fetch_ohlcv(self, symbol: str, timeframe: str, since_days: int) -> OHLCVData:
        """
        Fetch OHLCV data with automatic multi-source failover.
        
        Args:
            symbol: Canonical trading pair (e.g., 'BTC/USDT')
            timeframe: Candle timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            since_days: Number of days of historical data (max 3 years)
            
        Returns:
            OHLCVData with fetched data and metadata
        """
        # Cap at 3 years
        actual_days = min(since_days, self.MAX_DAYS)
        if since_days > self.MAX_DAYS:
            logger.warning(f"Capping historical data to {self.MAX_DAYS} days (3 years)")
        
        logger.info(f"Fetching {timeframe} data for {symbol} ({actual_days} days)")
        
        # Try providers in order
        providers = [
            ('CCXT', self._fetch_from_ccxt),
            ('yfinance', self._fetch_from_yfinance),
            ('CoinGecko', self._fetch_from_coingecko),
        ]
        
        for provider_name, provider_func in providers:
            try:
                logger.info(f"Trying {provider_name}...")
                df = provider_func(symbol, timeframe, actual_days)
                
                if df is not None and len(df) > 0:
                    volume_available = 'Volume' in df.columns and not df['Volume'].isna().all()
                    
                    logger.info(
                        f"✅ Successfully fetched {len(df)} candles from {provider_name} "
                        f"for {symbol} ({timeframe})"
                    )
                    
                    return OHLCVData(
                        df=df,
                        symbol=symbol,
                        timeframe=timeframe,
                        source=provider_name,
                        volume_available=volume_available
                    )
                else:
                    logger.warning(f"{provider_name} returned empty data")
                    
            except Exception as e:
                logger.warning(f"{provider_name} failed for {symbol}: {e}")
        
        # All providers failed
        raise ValueError(
            f"Failed to fetch data for {symbol} from any provider. "
            f"Tried: CCXT, yfinance, CoinGecko"
        )
    
    def _fetch_from_ccxt(
        self, 
        symbol: str, 
        timeframe: str, 
        since_days: int
    ) -> Optional[pd.DataFrame]:
        """
        Fetch from CCXT exchange with pagination to get full history.
        
        Implements proper pagination to fetch beyond single-request limits.
        """
        exchange = self._get_ccxt_exchange()
        if exchange is None:
            return None
        
        # Convert symbol to exchange format
        exchange_symbol = self.mapper.to_exchange_symbol(symbol, self.primary_exchange)
        if exchange_symbol is None:
            exchange_symbol = symbol  # Try as-is
        
        # Calculate start timestamp
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=since_days)
        since_ms = int(start_date.timestamp() * 1000)
        
        all_candles = []
        current_since = since_ms
        max_retries = 3
        retries = 0
        
        logger.info(
            f"Fetching from {self.primary_exchange}: {exchange_symbol}, "
            f"from {start_date.date()} to {end_date.date()}"
        )
        
        while current_since < int(end_date.timestamp() * 1000):
            try:
                # Respect rate limit
                time.sleep(0.2)
                
                candles = exchange.fetch_ohlcv(
                    symbol=exchange_symbol,
                    timeframe=timeframe,
                    since=current_since,
                    limit=self.MAX_CANDLES_PER_REQUEST
                )
                
                if not candles or len(candles) == 0:
                    logger.warning("No more candles available from exchange")
                    break
                
                all_candles.extend(candles)
                
                # Check if we've reached the end
                if len(candles) < self.MAX_CANDLES_PER_REQUEST:
                    logger.info("Reached end of available data")
                    break
                
                # Move to next batch
                last_timestamp = candles[-1][0]
                current_since = last_timestamp + 1
                
                # Safety check: prevent infinite loop
                if len(all_candles) > self.MAX_CANDLES_PER_REQUEST * 10:
                    logger.warning("Reached maximum candle limit, stopping pagination")
                    break
                    
            except Exception as e:
                error_str = str(e)
                if '451' in error_str or 'restricted' in error_str.lower():
                    logger.error(f"Exchange restricted from current location")
                    return None
                elif 'rate limit' in error_str.lower():
                    retries += 1
                    if retries < max_retries:
                        wait_time = 2 ** retries
                        logger.warning(f"Rate limit hit, waiting {wait_time}s")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error("Max retries exceeded for rate limit")
                        break
                else:
                    logger.error(f"CCXT fetch error: {e}")
                    break
        
        if not all_candles:
            return None
        
        # Convert to DataFrame
        df = pd.DataFrame(
            all_candles,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.set_index('timestamp', inplace=True)
        
        # Convert to float
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            df[col] = df[col].astype(float)
        
        # Remove duplicates and sort
        df = df[~df.index.duplicated(keep='first')]
        df.sort_index(inplace=True)
        
        # Trim to requested date range
        df = df[df.index >= start_date]
        
        logger.info(f"CCXT returned {len(df)} candles for {symbol}")
        return df
    
    def _fetch_from_yfinance(
        self, 
        symbol: str, 
        timeframe: str, 
        since_days: int
    ) -> Optional[pd.DataFrame]:
        """Fetch from yfinance with proper interval mapping."""
        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not installed")
            return None
        
        ticker_symbol = self.mapper.to_yfinance_ticker(symbol)
        if ticker_symbol is None:
            logger.warning(f"Symbol {symbol} not mapped to yfinance ticker")
            return None
        
        # Map timeframe to yfinance interval
        interval_map = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '1h': '1h',
            '4h': '1h',  # yfinance doesn't support 4h, will resample
            '1d': '1d'
        }
        
        interval = interval_map.get(timeframe, '1d')
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=since_days)
        
        logger.info(f"Fetching from yfinance: {ticker_symbol}, interval={interval}")
        
        try:
            ticker = yf.Ticker(ticker_symbol)
            df = ticker.history(start=start_date, end=end_date, interval=interval)
            
            if df.empty or len(df) < 10:
                logger.warning("yfinance returned insufficient data")
                return None
            
            # Standardize columns
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
            df.rename(columns={
                'Open': 'open', 'High': 'high', 'Low': 'low',
                'Close': 'close', 'Volume': 'volume'
            }, inplace=True)
            
            # Resample if 4h requested
            if timeframe == '4h':
                logger.info("Resampling 1h data to 4h")
                ohlc_dict = {
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }
                df = df.resample('4H').agg(ohlc_dict)
                df = df.dropna()
            
            logger.info(f"yfinance returned {len(df)} candles")
            return df
            
        except Exception as e:
            logger.error(f"yfinance fetch failed: {e}")
            return None
    
    def _fetch_from_coingecko(
        self, 
        symbol: str, 
        timeframe: str, 
        since_days: int
    ) -> Optional[pd.DataFrame]:
        """
        Fetch from CoinGecko (daily data only).
        
        Note: Free API has rate limits, no volume data.
        """
        if timeframe != '1d':
            logger.warning("CoinGecko only supports daily data")
            return None
        
        try:
            from pycoingecko import CoinGeckoAPI
        except ImportError:
            logger.warning("pycoingecko not installed")
            return None
        
        coin_id = self.mapper.to_coingecko_id(symbol)
        if coin_id is None:
            logger.warning(f"Symbol {symbol} not mapped to CoinGecko ID")
            return None
        
        api = CoinGeckoAPI()
        
        # Determine API days parameter (CoinGecko has specific options)
        if since_days > 365:
            api_days = 'max'
        elif since_days > 90:
            api_days = 365
        elif since_days > 30:
            api_days = 90
        elif since_days > 14:
            api_days = 30
        elif since_days > 1:
            api_days = 14
        else:
            api_days = 1
        
        logger.info(f"Fetching from CoinGecko: {coin_id}, days={api_days}")
        
        max_retries = 3
        retry_delay = 60
        
        for attempt in range(max_retries):
            try:
                ohlc_data = api.get_coin_ohlc_by_id(
                    coin_id, vs_currency='usd', days=api_days
                )
                
                if not ohlc_data or len(ohlc_data) < 10:
                    logger.warning("CoinGecko returned insufficient data")
                    return None
                
                # Convert to DataFrame
                df = pd.DataFrame(
                    ohlc_data, 
                    columns=['timestamp', 'open', 'high', 'low', 'close']
                )
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                df.rename(columns={
                    'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close'
                }, inplace=True)
                
                # Volume unavailable in free tier
                df['volume'] = np.nan
                
                logger.info(f"CoinGecko returned {len(df)} daily candles (no volume)")
                return df
                
            except Exception as e:
                error_str = str(e)
                if '429' in error_str or 'rate limit' in error_str.lower():
                    if attempt < max_retries - 1:
                        logger.warning(f"Rate limit hit, waiting {retry_delay}s")
                        time.sleep(retry_delay)
                        continue
                    else:
                        logger.error("CoinGecko max retries exceeded")
                        return None
                else:
                    logger.error(f"CoinGecko fetch failed: {e}")
                    return None
        
        return None
    
    def fetch_all_symbols(
        self, 
        symbols: List[str], 
        timeframe: str,
        since_days: int
    ) -> Dict[str, OHLCVData]:
        """Fetch data for multiple symbols."""
        data = {}
        for symbol in symbols:
            try:
                ohlcv = self.fetch_ohlcv(symbol, timeframe, since_days)
                data[symbol] = ohlcv
            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")
                data[symbol] = None
        
        return data
    
    def align_data(self, raw_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Align data from different symbols to common timestamps.
        
        CRITICAL: Only uses forward-fill to prevent lookahead bias.
        """
        if not raw_data:
            logger.warning("No data to align")
            return pd.DataFrame()
        
        # Get closing prices
        prices = pd.DataFrame()
        for symbol, ohlcv in raw_data.items():
            df = ohlcv.df if isinstance(ohlcv, OHLCVData) else ohlcv
            if df is not None and not df.empty:
                prices[symbol] = df['close']
        
        if prices.empty:
            logger.warning("All dataframes were empty or None")
            return pd.DataFrame()
        
        # CRITICAL: Only forward-fill to prevent lookahead bias
        prices = prices.ffill()
        
        # Log warning if NaN remains
        nan_count = prices.isna().sum().sum()
        if nan_count > 0:
            logger.warning(
                f"Data alignment resulted in {nan_count} NaN values after forward-fill. "
                f"These represent genuine missing data."
            )
        
        logger.info(f"Aligned data: {len(prices)} rows, {len(prices.columns)} columns")
        return prices
