"""
Data Fetcher Module
Fetches historical OHLCV data from CoinGecko using pycoingecko
with fallback to yfinance
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

# Mapping from trading pair symbols to yfinance ticker symbols
SYMBOL_TO_YFINANCE_TICKER = {
    'BTC/USDT': 'BTC-USD',
    'ETH/USDT': 'ETH-USD',
    'SOL/USDT': 'SOL-USD',
    'BNB/USDT': 'BNB-USD',
    'XRP/USDT': 'XRP-USD',
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

    def fetch_ohlcv(self, symbol: str, timeframe: str = '1d',
                     since_days: int = 90) -> pd.DataFrame:
        """
        Fetch OHLCV data for a single symbol.
        Priority: yfinance for hourly data (reliable), CoinGecko for daily fallback.

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Candle timeframe ('1h' for hourly, '1d' for daily)
            since_days: Number of days of historical data.
                        For hourly data: max 90 days
                        For daily data: max 365 days

        Returns:
            DataFrame with OHLCV data ['Open', 'High', 'Low', 'Close', 'Volume']
        """
        logger.info(f"Fetching {timeframe} data for {symbol} ({since_days} days)")

        # Enforce maximum limits based on timeframe
        if timeframe == '1h':
            max_days = 90
            if since_days > max_days:
                logger.warning(f"Hourly data limited to {max_days} days. "
                              f"Reducing from {since_days} to {max_days} days.")
                since_days = max_days
        else:  # daily
            max_days = 365
            if since_days > max_days:
                logger.warning(f"Daily data limited to {max_days} days. "
                              f"Reducing from {since_days} to {max_days} days.")
                since_days = max_days
        
        # For hourly data, use yfinance directly (CoinGecko free API doesn't support hourly for long periods)
        if timeframe == '1h':
            logger.info(f"Using yfinance for hourly data ({since_days} days)")
            try:
                return self._fetch_from_yfinance(symbol, timeframe, since_days)
            except Exception as e:
                logger.error(f"yfinance hourly fetch failed: {e}")
                raise
        
        # For daily data, prefer yfinance for reliability (CoinGecko free API has limitations)
        # Try yfinance first, fallback to CoinGecko only if yfinance fails
        logger.info(f"Using yfinance for daily data ({since_days} days)")
        try:
            return self._fetch_from_yfinance(symbol, timeframe, since_days)
        except Exception as e:
            logger.warning(f"yfinance daily fetch failed ({e}), falling back to CoinGecko...")
            # Fall through to CoinGecko code below
            pass
        
        # CoinGecko fallback for daily data
        coin_id = SYMBOL_TO_COINGECKO_ID.get(symbol)
        if coin_id is None:
            raise ValueError(f"Symbol {symbol} not mapped to CoinGecko ID.")
        
        max_retries = 3
        retry_delay = 60
        ohlc_data = None
        use_yfinance_fallback = False
        
        for attempt in range(max_retries):
            try:
                # Determine the 'days' parameter for CoinGecko API
                # Valid values: 1, 14, 30, 90, 'max'
                # DO NOT use 'max' - use explicit numeric values only
                if since_days > 90:
                    api_days = 365  # Use largest explicit value
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
                # This endpoint RETURNS DAILY CANDLES for most values of 'days'
                ohlc_data = self.api.get_coin_ohlc_by_id(coin_id, vs_currency='usd', days=api_days)
                
                # Check if we got enough data
                if ohlc_data and len(ohlc_data) >= 10:
                    break  # Success, exit retry loop
                else:
                    logger.warning(f"CoinGecko returned insufficient data ({len(ohlc_data) if ohlc_data else 0} candles)")
                    use_yfinance_fallback = True
                    break
                    
            except Exception as e:
                error_str = str(e)
                # Check for rate limit or time range errors
                if '429' in error_str or 'rate limit' in error_str.lower():
                    logger.warning(f"Rate limit hit for {symbol}, waiting {retry_delay}s before retry {attempt+1}/{max_retries}")
                    time.sleep(retry_delay)
                elif '10012' in error_str or 'time range' in error_str.lower():
                    # Time range error - reduce days and retry
                    logger.warning(f"Time range error for {symbol}, reducing days parameter")
                    api_days = min(api_days if isinstance(api_days, int) else 90, 90)
                    try:
                        ohlc_data = self.api.get_coin_ohlc_by_id(coin_id, vs_currency='usd', days=api_days)
                        if ohlc_data and len(ohlc_data) >= 10:
                            break
                    except Exception as e2:
                        logger.warning(f"Error with reduced days: {e2}")
                    use_yfinance_fallback = True
                    break
                else:
                    logger.warning(f"Error fetching {symbol}: {e}")
                    if attempt == max_retries - 1:
                        use_yfinance_fallback = True
                    else:
                        time.sleep(1)
        
        # Fallback to yfinance if CoinGecko fails or returned insufficient data
        if use_yfinance_fallback or (ohlc_data is None or len(ohlc_data) < 10):
            logger.info(f"Attempting yfinance fallback for {symbol}...")
            try:
                return self._fetch_from_yfinance(symbol, timeframe, since_days)
            except Exception as yf_error:
                logger.error(f"yfinance fallback also failed for {symbol}: {yf_error}")
                raise ValueError(f"No sufficient data retrieved for {symbol} from any source")

        # Convert to DataFrame
        # CoinGecko returns: [timestamp(ms), open, high, low, close]
        df = pd.DataFrame(ohlc_data, columns=['timestamp', 'open', 'high', 'low', 'close'])
        
        # CRITICAL: CoinGecko OHLC endpoint doesn't include volume in free tier.
        # Set volume to NaN (not 0) to indicate unavailability.
        # Strategies requiring volume must handle this gracefully.
        # See data.providers.historical.HistoricalDataProvider for preferred implementation.
        df['volume'] = np.nan
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low',
                            'close': 'Close', 'volume': 'Volume'}, inplace=True)

        logger.info(f"✅ Retrieved {len(df)} DAILY candles for {symbol} (Range: {df.index.min()} to {df.index.max()})")
        logger.warning(f"⚠️ Volume unavailable for {symbol} from CoinGecko (set to NaN)")
        return df

    def _fetch_from_yfinance(self, symbol: str, timeframe: str, since_days: int) -> pd.DataFrame:
        """
        Fetch OHLCV data from yfinance as fallback
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Candle timeframe ('1h' for hourly, '1d' for daily)
            since_days: Number of days of historical data
            
        Returns:
            DataFrame with OHLCV data ['Open', 'High', 'Low', 'Close', 'Volume']
        """
        import yfinance as yf
        
        ticker_symbol = SYMBOL_TO_YFINANCE_TICKER.get(symbol)
        if ticker_symbol is None:
            raise ValueError(f"Symbol {symbol} not mapped to yfinance ticker. "
                           f"Available mappings: {list(SYMBOL_TO_YFINANCE_TICKER.keys())}")
        
        logger.info(f"Fetching {timeframe} data for {ticker_symbol} from yfinance ({since_days} days)")
        
        ticker = yf.Ticker(ticker_symbol)
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=since_days)
        
        # Download data
        df = ticker.history(start=start_date, end=end_date, interval=timeframe)
        
        if df.empty or len(df) < 10:
            raise ValueError(f"No sufficient data retrieved from yfinance for {symbol}")
        
        # Ensure proper column names
        df.rename(columns={
            'Open': 'Open', 'High': 'High', 'Low': 'Low',
            'Close': 'Close', 'Volume': 'Volume'
        }, inplace=True)
        
        logger.info(f"✅ Retrieved {len(df)} candles for {symbol} from yfinance (Range: {df.index.min()} to {df.index.max()})")
        return df[['Open', 'High', 'Low', 'Close', 'Volume']]

    def fetch_all_symbols(self, timeframe: str = '1d',
                           since_days: int = 90) -> Dict[str, pd.DataFrame]:
        """
        Fetch OHLCV data for all symbols.
        Note: Uses daily candles by default due to CoinGecko free API limitations.

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

    def calculate_returns(self, prices: pd.DataFrame, add_cash_column: bool = True) -> pd.DataFrame:
        """
        Calculate log returns from price data
        
        Args:
            prices: DataFrame of aligned prices
            add_cash_column: If True, adds a CASH column with zero return (stablecoin allocation option)

        Returns:
            DataFrame of log returns
        """
        returns = np.log(prices / prices.shift(1)).dropna()
        
        # FEATURE 1: Add cash/stablecoin column for defensive allocation
        if add_cash_column:
            # CASH has zero return (or very small positive like staking yield)
            # This allows optimizers to allocate to safety during market downturns
            returns['CASH'] = 0.0  # Zero daily return = stable value
            logger.info("Added CASH column for defensive allocation (zero return, zero variance)")
        
        logger.info(f"Returns calculated: {returns.shape}")
        return returns


def main():
    """Test data fetching"""
    fetcher = DataFetcher()

    # Fetch 90 days of daily data (within CoinGecko limits)
    data = fetcher.fetch_all_symbols(timeframe='1d', since_days=90)

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
