"""
Data Fetcher Module
Fetches historical OHLCV data from CoinGecko using pycoingecko
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time
from pycoingecko import CoinGeckoAPI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Mapping from trading pair symbols to CoinGecko coin IDs
SYMBOL_TO_COINGECKO_ID = {
    'BTC/USDT': 'bitcoin',
    'ETH/USDT': 'ethereum',
    'SOL/USDT': 'solana',
    'BNB/USDT': 'binancecoin',
    'XRP/USDT': 'ripple',
}


class DataFetcher:
    """Fetch and process cryptocurrency OHLCV data from CoinGecko"""

    def __init__(self, symbols: List[str] = None):
        """
        Initialize data fetcher

        Args:
            symbols: List of trading pairs (e.g., ['BTC/USDT', 'ETH/USDT'])
        """
        self.symbols = symbols or [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'
        ]
        self.api = CoinGeckoAPI()
        logger.info(f"Initialized DataFetcher for {len(self.symbols)} symbols using CoinGecko API")

    def fetch_ohlcv(self, symbol: str, timeframe: str = '1h',
                     since_days: int = 90) -> pd.DataFrame:
        """
        Fetch OHLCV data for a single symbol from CoinGecko

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Candle timeframe (default: '1h', only '1h' supported by CoinGecko API)
            since_days: Number of days of historical data (max 90 for free API, or use 'max')

        Returns:
            DataFrame with OHLCV data ['open', 'high', 'low', 'close', 'volume']
        """
        logger.info(f"Fetching {timeframe} data for {symbol} ({since_days} days)")

        # Map symbol to CoinGecko coin ID
        coin_id = SYMBOL_TO_COINGECKO_ID.get(symbol)
        if coin_id is None:
            raise ValueError(f"Symbol {symbol} not mapped to CoinGecko ID. "
                             f"Available mappings: {list(SYMBOL_TO_COINGECKO_ID.keys())}")

        # CoinGecko's get_coin_ohlc returns hourly candles
        # Free API supports: 1, 14, 30, 90, or 'max' days
        # We'll use 'max' for full history, but cap at 90 if user requests <= 90
        max_retries = 3
        retry_delay = 60  # seconds to wait on rate limit (429)
        
        ohlc_data = None
        for attempt in range(max_retries):
            try:
                # Determine the 'days' parameter for CoinGecko API
                if since_days >= 365 or since_days == 'max':
                    api_days = 'max'
                elif since_days > 90:
                    # For values between 91-364, use 'max' to get all available data
                    api_days = 'max'
                elif since_days > 30:
                    api_days = 90
                elif since_days > 14:
                    api_days = 30
                elif since_days > 1:
                    api_days = 14
                else:
                    api_days = 1
                
                logger.debug(f"Using CoinGecko days parameter: {api_days}")
                
                # get_coin_ohlc_by_id(coin_id, vs_currency, days) returns [timestamp, open, high, low, close]
                ohlc_data = self.api.get_coin_ohlc_by_id(coin_id, vs_currency='usd', days=api_days)
                break  # Success, exit retry loop
                
            except Exception as e:
                error_str = str(e)
                # Check for rate limit or time range errors
                if '429' in error_str or 'rate limit' in error_str.lower():
                    logger.warning(f"Rate limit hit for {symbol}, waiting {retry_delay}s before retry {attempt+1}/{max_retries}")
                    time.sleep(retry_delay)
                elif '10012' in error_str or 'time range' in error_str.lower():
                    # Time range error - switch to 'max' and retry
                    logger.warning(f"Time range error for {symbol}, switching to 'max' days")
                    try:
                        ohlc_data = self.api.get_coin_ohlc_by_id(coin_id, vs_currency='usd', days='max')
                        break
                    except Exception as e2:
                        logger.warning(f"Error with 'max' days: {e2}")
                        if attempt == max_retries - 1:
                            raise ValueError(f"Failed to fetch data for {symbol}: {e2}")
                        time.sleep(5)
                else:
                    logger.warning(f"Error fetching {symbol}: {e}")
                    if attempt == max_retries - 1:
                        raise ValueError(f"Failed to fetch data for {symbol} after {max_retries} attempts: {e}")
                    time.sleep(1)
        
        if not ohlc_data:
            raise ValueError(f"No data retrieved for {symbol}")

        # Convert to DataFrame
        # CoinGecko returns: [timestamp(ms), open, high, low, close]
        df = pd.DataFrame(ohlc_data, columns=['timestamp', 'open', 'high', 'low', 'close'])
        
        # Add volume column (CoinGecko OHLC doesn't include volume, set to 0 or estimate)
        # For portfolio optimization, volume is less critical, so we set it to a placeholder
        df['volume'] = 0.0
        
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
