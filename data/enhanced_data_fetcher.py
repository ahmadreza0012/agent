"""
Enhanced Data Fetcher with Multi-Exchange Support
Fetches from Binance, Nobitex (Iran), and other exchanges
"""
import ccxt
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MultiExchangeDataFetcher:
    """
    Fetch data from multiple crypto exchanges
    """
    
    def __init__(self, symbols: List[str], exchange: str = 'binance'):
        self.symbols = symbols
        self.exchange_name = exchange
        
        try:
            # Initialize exchange
            if exchange == 'binance':
                self.exchange = ccxt.binance({'enableRateLimit': True})
            elif exchange == 'nobitex':
                self.exchange = ccxt.nobitex({'enableRateLimit': True})
            else:
                self.exchange = getattr(ccxt, exchange)({'enableRateLimit': True})
            
            logger.info(f"Connected to {exchange}")
        except Exception as e:
            logger.error(f"Failed to connect to {exchange}: {e}")
            self.exchange = None
    
    def fetch_all_symbols(self, timeframe: str = '1h', since_days: int = 365,
                         use_cache: bool = True) -> Dict[str, pd.DataFrame]:
        """
        Fetch OHLCV data for all symbols
        
        Args:
            timeframe: Candlestick timeframe (1h, 4h, 1d, etc.)
            since_days: How many days back to fetch
            use_cache: Use cached data if available
            
        Returns:
            Dictionary of symbol -> OHLCV DataFrame
        """
        if self.exchange is None:
            logger.error("Exchange not initialized")
            return {}
        
        data = {}
        since = int((datetime.now() - timedelta(days=since_days)).timestamp() * 1000)
        
        for symbol in self.symbols:
            try:
                logger.info(f"Fetching {symbol}...")
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since)
                
                df = pd.DataFrame(
                    ohlcv,
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                
                data[symbol] = df
                logger.info(f"Fetched {len(df)} candles for {symbol}")
                
            except Exception as e:
                logger.error(f"Error fetching {symbol}: {e}")
        
        return data
    
    def align_data(self, raw_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Align data from different sources to common timestamps
        """
        if not raw_data:
            return pd.DataFrame()
        
        # Get closing prices
        prices = pd.DataFrame()
        for symbol, df in raw_data.items():
            prices[symbol] = df['close']
        
        # Forward fill for missing values
        prices = prices.fillna(method='ffill').fillna(method='bfill')
        
        logger.info(f"Aligned data: {len(prices)} rows, {len(prices.columns)} columns")
        return prices
    
    def calculate_returns(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate log returns
        """
        returns = np.log(prices / prices.shift(1)).fillna(0)
        return returns


def load_cached_data(cache_path: str, symbol: str) -> Optional[pd.DataFrame]:
    """
    Load cached data from file
    """
    try:
        df = pd.read_csv(f"{cache_path}{symbol}.csv", index_col=0, parse_dates=True)
        logger.info(f"Loaded cached data for {symbol}")
        return df
    except:
        return None
