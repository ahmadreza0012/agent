"""
Enhanced Data Fetcher - Multi-Exchange Support
Supports Binance (via CCXT) and Nobitex (Iranian exchange)
Provides unified interface for historical and real-time data
"""
import ccxt
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import time
import os
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MultiExchangeDataFetcher:
    """
    Unified data fetcher supporting multiple exchanges
    
    Features:
    - Binance via CCXT (global prices)
    - Nobitex via API (Iranian market, IRR pairs)
    - Automatic data alignment
    - OHLCV + volume data
    - Caching for efficiency
    """
    
    def __init__(self, symbols: List[str] = None, 
                 exchange: str = 'binance',
                 cache_dir: str = 'data/cache'):
        """
        Initialize multi-exchange data fetcher
        
        Args:
            symbols: List of trading pairs
            exchange: Primary exchange ('binance' or 'nobitex')
            cache_dir: Directory for caching fetched data
        """
        self.symbols = symbols or [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'
        ]
        self.exchange_name = exchange
        self.cache_dir = cache_dir
        
        # Create cache directory
        os.makedirs(cache_dir, exist_ok=True)
        
        # Initialize exchange
        if exchange == 'binance':
            self.exchange = ccxt.binance({
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            })
        elif exchange == 'nobitex':
            self.exchange = ccxt.nobitex({
                'enableRateLimit': True,
            })
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")
        
        logger.info(f"Initialized MultiExchangeDataFetcher for {exchange}")
        logger.info(f"Symbols: {self.symbols}")
    
    def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', 
                    since_days: int = 365,
                    use_cache: bool = True) -> pd.DataFrame:
        """
        Fetch OHLCV data for a single symbol
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Candle timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            since_days: Number of days of historical data
            use_cache: Whether to use cached data
            
        Returns:
            DataFrame with OHLCV data
        """
        # Check cache
        cache_file = os.path.join(
            self.cache_dir, 
            f"{symbol.replace('/', '_')}_{timeframe}_{since_days}d.csv"
        )
        
        if use_cache and os.path.exists(cache_file):
            logger.info(f"Loading cached data from {cache_file}")
            df = pd.read_csv(cache_file, index_col='timestamp', parse_dates=True)
            return df
        
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
        df.rename(columns={
            'open': 'Open', 
            'high': 'High', 
            'low': 'Low', 
            'close': 'Close', 
            'volume': 'Volume'
        }, inplace=True)
        
        # Save to cache
        if use_cache:
            df.to_csv(cache_file)
            logger.info(f"Cached data to {cache_file}")
        
        logger.info(f"Retrieved {len(df)} candles for {symbol}")
        return df
    
    def fetch_all_symbols(self, timeframe: str = '1h', 
                         since_days: int = 365,
                         use_cache: bool = True) -> Dict[str, pd.DataFrame]:
        """
        Fetch OHLCV data for all symbols
        
        Returns:
            Dictionary mapping symbol to DataFrame
        """
        data = {}
        for symbol in self.symbols:
            try:
                df = self.fetch_ohlcv(symbol, timeframe, since_days, use_cache)
                data[symbol] = df
            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")
        
        return data
    
    def align_data(self, data: Dict[str, pd.DataFrame], 
                   method: str = 'inner') -> pd.DataFrame:
        """
        Align all symbols to common timestamps
        
        Args:
            data: Dictionary of symbol -> DataFrame
            method: Join method ('inner', 'outer', 'forward_fill')
            
        Returns:
            DataFrame with Close prices for all symbols aligned
        """
        close_prices = {}
        for symbol, df in data.items():
            clean_symbol = symbol.replace('/', '_').replace('USDT', '')
            close_prices[clean_symbol] = df['Close']
        
        # Join based on method
        if method == 'inner':
            aligned = pd.DataFrame(close_prices).dropna()
        elif method == 'outer':
            aligned = pd.DataFrame(close_prices)
        elif method == 'forward_fill':
            aligned = pd.DataFrame(close_prices).ffill().bfill()
        else:
            aligned = pd.DataFrame(close_prices).dropna()
        
        logger.info(f"Aligned data shape: {aligned.shape}")
        logger.info(f"Date range: {aligned.index.min()} to {aligned.index.max()}")
        
        return aligned
    
    def calculate_returns(self, prices: pd.DataFrame, 
                         method: str = 'log') -> pd.DataFrame:
        """
        Calculate returns from price data
        
        Args:
            prices: DataFrame of aligned prices
            method: Return type ('log' or 'simple')
            
        Returns:
            DataFrame of returns
        """
        if method == 'log':
            returns = np.log(prices / prices.shift(1)).dropna()
        else:
            returns = prices.pct_change().dropna()
        
        logger.info(f"Returns calculated ({method}): {returns.shape}")
        return returns
    
    def get_market_regime_features(self, prices: pd.DataFrame,
                                   window: int = 168) -> pd.DataFrame:
        """
        Calculate features for market regime detection
        
        Args:
            prices: Price DataFrame
            window: Lookback window (hours)
            
        Returns:
            DataFrame with regime features
        """
        features = pd.DataFrame(index=prices.index)
        
        for col in prices.columns:
            # Momentum
            features[f'{col}_momentum'] = prices[col].pct_change(window)
            
            # Volatility (rolling std)
            features[f'{col}_volatility'] = prices[col].pct_change().rolling(window).std()
            
            # Trend strength (ADX proxy)
            high = prices[col].rolling(window).max()
            low = prices[col].rolling(window).min()
            close = prices[col]
            tr = high - low
            features[f'{col}_trend'] = (close - low) / (tr + 1e-10)
            
            # Volume trend
            vol_ma = prices[f'{col}_Volume'].rolling(window).mean() if f'{col}_Volume' in prices.columns else 1
            features[f'{col}_volume_trend'] = vol_ma / vol_ma.shift(window)
        
        return features.dropna()
    
    def fetch_realtime_price(self, symbol: str) -> float:
        """
        Fetch current price for a symbol
        
        Args:
            symbol: Trading pair
            
        Returns:
            Current price
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            logger.error(f"Error fetching realtime price: {e}")
            return None


class NobitexDataFetcher(MultiExchangeDataFetcher):
    """
    Specialized fetcher for Nobitex exchange (Iranian market)
    Useful for IRR-denominated pairs and local arbitrage opportunities
    """
    
    def __init__(self, symbols: List[str] = None,
                 cache_dir: str = 'data/nobitex'):
        """
        Initialize Nobitex fetcher
        
        Args:
            symbols: List of trading pairs (e.g., ['BTC/IRT', 'ETH/IRT'])
        """
        symbols = symbols or ['BTC/IRT', 'ETH/IRT', 'USDT/IRT']
        super().__init__(symbols=symbols, exchange='nobitex', cache_dir=cache_dir)
        
        logger.info("Nobitex fetcher initialized for Iranian market")
    
    def get_irr_usdt_rate(self) -> float:
        """
        Get current USDT/IRR exchange rate
        Important for converting between local and global prices
        """
        try:
            ticker = self.exchange.fetch_ticker('USDT/IRT')
            return ticker['last']
        except Exception as e:
            logger.error(f"Error fetching USDT/IRT rate: {e}")
            return None
    
    def calculate_premium(self, global_price: float, 
                         local_price: float,
                         usdt_rate: float) -> float:
        """
        Calculate premium/discount of local market vs global
        
        Args:
            global_price: Price in USD (e.g., BTC/USDT on Binance)
            local_price: Price in IRR (e.g., BTC/IRT on Nobitex)
            usdt_rate: USDT/IRR exchange rate
            
        Returns:
            Premium percentage
        """
        local_price_usd = local_price / usdt_rate
        premium = (local_price_usd - global_price) / global_price
        return premium


def load_cached_data(cache_dir: str = 'data/cache',
                     symbols: List[str] = None,
                     timeframe: str = '1h',
                     since_days: int = 365) -> pd.DataFrame:
    """
    Load cached price data for backtesting
    
    Returns:
        Aligned price DataFrame
    """
    symbols = symbols or ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']
    
    fetcher = MultiExchangeDataFetcher(symbols=symbols, cache_dir=cache_dir)
    data = fetcher.fetch_all_symbols(timeframe=timeframe, since_days=since_days, use_cache=True)
    prices = fetcher.align_data(data)
    
    return prices


if __name__ == "__main__":
    # Test data fetching
    fetcher = MultiExchangeDataFetcher(
        symbols=['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
        exchange='binance'
    )
    
    # Fetch 1 year of hourly data
    data = fetcher.fetch_all_symbols(timeframe='1h', since_days=90, use_cache=True)
    
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
