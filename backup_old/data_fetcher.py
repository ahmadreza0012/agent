"""
Data Fetcher Module
Fetches historical OHLCV data from Binance using ccxt
"""
import ccxt
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataFetcher:
    """Fetch and process cryptocurrency OHLCV data from Binance"""
    
    def __init__(self, symbols: List[str] = None):
        """
        Initialize data fetcher
        
        Args:
            symbols: List of trading pairs (e.g., ['BTC/USDT', 'ETH/USDT'])
        """
        self.symbols = symbols or [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'
        ]
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        logger.info(f"Initialized DataFetcher for {len(self.symbols)} symbols")
    
    def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', 
                    since_days: int = 365) -> pd.DataFrame:
        """
        Fetch OHLCV data for a single symbol
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Candle timeframe (default: '1h')
            since_days: Number of days of historical data
            
        Returns:
            DataFrame with OHLCV data
        """
        logger.info(f"Fetching {timeframe} data for {symbol} ({since_days} days)")
        
        # Calculate since timestamp
        since = self.exchange.milliseconds() - (since_days * 24 * 60 * 60 * 1000)
        
        all_candles = []
        current_since = since
        
        while True:
            try:
                candles = self.exchange.fetch_ohlcv(
                    symbol, timeframe, since=current_since, limit=1000
                )
                
                if not candles:
                    break
                    
                all_candles.extend(candles)
                
                if len(candles) < 1000:
                    break
                    
                # Move to next batch
                current_since = candles[-1][0] + 1
                
                # Rate limit handling
                time.sleep(0.1)
                
            except Exception as e:
                logger.warning(f"Error fetching {symbol}: {e}")
                time.sleep(1)
                break
        
        if not all_candles:
            raise ValueError(f"No data retrieved for {symbol}")
        
        # Convert to DataFrame
        df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 
                          'close': 'Close', 'volume': 'Volume'}, inplace=True)
        
        logger.info(f"Retrieved {len(df)} candles for {symbol}")
        return df
    
    def fetch_all_symbols(self, timeframe: str = '1h', 
                         since_days: int = 365) -> Dict[str, pd.DataFrame]:
        """
        Fetch OHLCV data for all symbols
        
        Returns:
            Dictionary mapping symbol to DataFrame
        """
        data = {}
        for symbol in self.symbols:
            try:
                df = self.fetch_ohlcv(symbol, timeframe, since_days)
                data[symbol] = df
            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")
        
        return data
    
    def align_data(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Align all symbols to common timestamps (inner join)
        
        Args:
            data: Dictionary of symbol -> DataFrame
            
        Returns:
            DataFrame with Close prices for all symbols aligned
        """
        close_prices = {}
        for symbol, df in data.items():
            clean_symbol = symbol.replace('/', '_').replace('USDT', '')
            close_prices[clean_symbol] = df['Close']
        
        # Inner join to align timestamps
        aligned = pd.DataFrame(close_prices).dropna()
        logger.info(f"Aligned data shape: {aligned.shape}")
        logger.info(f"Date range: {aligned.index.min()} to {aligned.index.max()}")
        
        return aligned
    
    def calculate_returns(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate log returns from price data
        
        Args:
            prices: DataFrame of aligned prices
            
        Returns:
            DataFrame of log returns
        """
        returns = np.log(prices / prices.shift(1)).dropna()
        logger.info(f"Returns calculated: {returns.shape}")
        return returns


def main():
    """Test data fetching"""
    fetcher = DataFetcher()
    
    # Fetch 1 year of hourly data
    data = fetcher.fetch_all_symbols(timeframe='1h', since_days=365)
    
    # Align data
    prices = fetcher.align_data(data)
    
    # Calculate returns
    returns = fetcher.calculate_returns(prices)
    
    print("\n=== Data Summary ===")
    print(f"Symbols: {list(prices.columns)}")
    print(f"Date range: {prices.index.min()} to {prices.index.max()}")
    print(f"Total observations: {len(prices)}")
    print(f"\nPrice statistics:")
    print(prices.describe())
    print(f"\nReturn statistics:")
    print(returns.describe())
    
    return prices, returns


if __name__ == "__main__":
    prices, returns = main()
