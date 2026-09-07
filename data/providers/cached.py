"""
Cached Data Provider

Manages local cache of OHLCV data to avoid redundant downloads.
Stores metadata for validation and efficient lookups.
"""

from typing import Dict, List, Optional
import pandas as pd
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime
import logging

from .base import DataProvider, OHLCVData
from .historical import HistoricalDataProvider

logger = logging.getLogger(__name__)


class CachedDataProvider(DataProvider):
    """
    Wraps another provider with local caching.
    
    Cache structure:
    data/cache/{SYMBOL}_{TIMEFRAME}_{DAYS}d.csv
    data/cache/{SYMBOL}_{TIMEFRAME}_{DAYS}d.meta.json
    
    Metadata includes:
    - source: Original data provider name
    - download_timestamp: When data was cached
    - timeframe: Candle timeframe
    - rows: Number of rows
    - checksum: Simple hash for integrity
    - volume_available: Whether volume is real
    """
    
    def __init__(self, base_provider: DataProvider, cache_dir: str = 'data/cache'):
        """
        Initialize cached provider.
        
        Args:
            base_provider: Underlying data provider to wrap
            cache_dir: Directory for cache files
        """
        self.base_provider = base_provider
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized CachedDataProvider with cache at {cache_dir}")
    
    def get_source_name(self) -> str:
        return f"Cached({self.base_provider.get_source_name()})"
    
    def supports_timeframe(self, timeframe: str) -> bool:
        return self.base_provider.supports_timeframe(timeframe)
    
    def _get_cache_key(self, symbol: str, timeframe: str, since_days: int) -> str:
        """Generate cache file key."""
        # Normalize symbol for filename
        safe_symbol = symbol.replace('/', '_')
        return f"{safe_symbol}_{timeframe}_{since_days}d"
    
    def _get_csv_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.csv"
    
    def _get_meta_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.meta.json"
    
    def _compute_checksum(self, df: pd.DataFrame) -> str:
        """Compute simple checksum for DataFrame."""
        return hashlib.md5(df.to_csv().encode()).hexdigest()
    
    def _load_from_cache(self, key: str) -> Optional[OHLCVData]:
        """Try to load data from cache."""
        csv_path = self._get_csv_path(key)
        meta_path = self._get_meta_path(key)
        
        if not csv_path.exists() or not meta_path.exists():
            return None
        
        try:
            # Load metadata
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            
            # Check if cache is stale (optional: could add max_age check)
            download_time = datetime.fromisoformat(meta['download_timestamp'])
            age_hours = (datetime.now() - download_time).total_seconds() / 3600
            
            if age_hours > 24:  # Cache older than 24 hours
                logger.info(f"Cache for {key} is {age_hours:.1f}h old, refreshing")
                return None
            
            # Load data
            df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            
            # Verify checksum
            if self._compute_checksum(df) != meta['checksum']:
                logger.warning(f"Cache checksum mismatch for {key}")
                return None
            
            logger.info(f"✅ Loaded cached data for {key}")
            
            return OHLCVData(
                df=df,
                symbol=meta['symbol'],
                timeframe=meta['timeframe'],
                source=meta['source'],
                volume_available=meta.get('volume_available', True)
            )
            
        except Exception as e:
            logger.warning(f"Cache read failed for {key}: {e}")
            return None
    
    def _save_to_cache(self, ohlcv: OHLCVData, key: str):
        """Save data to cache with metadata."""
        try:
            csv_path = self._get_csv_path(key)
            meta_path = self._get_meta_path(key)
            
            # Save CSV
            ohlcv.df.to_csv(csv_path)
            
            # Save metadata
            meta = {
                'symbol': ohlcv.symbol,
                'timeframe': ohlcv.timeframe,
                'source': ohlcv.source,
                'download_timestamp': datetime.now().isoformat(),
                'rows': ohlcv.row_count,
                'checksum': self._compute_checksum(ohlcv.df),
                'volume_available': ohlcv.volume_available,
                'start_date': str(ohlcv.start_date),
                'end_date': str(ohlcv.end_date)
            }
            
            with open(meta_path, 'w') as f:
                json.dump(meta, f, indent=2)
            
            logger.info(f"💾 Cached data for {key} ({ohlcv.row_count} rows)")
            
        except Exception as e:
            logger.error(f"Cache write failed for {key}: {e}")
    
    def fetch_ohlcv(self, symbol: str, timeframe: str, since_days: int) -> OHLCVData:
        """
        Fetch OHLCV data, using cache if available.
        
        Priority:
        1. Load from cache (if valid and fresh)
        2. Fetch from base provider and cache
        """
        key = self._get_cache_key(symbol, timeframe, since_days)
        
        # Try cache first
        cached = self._load_from_cache(key)
        if cached is not None:
            return cached
        
        # Fetch from base provider
        logger.info(f"Cache miss for {key}, fetching from {self.base_provider.get_source_name()}")
        ohlcv = self.base_provider.fetch_ohlcv(symbol, timeframe, since_days)
        
        # Save to cache
        self._save_to_cache(ohlcv, key)
        
        return ohlcv
    
    def fetch_all_symbols(self, symbols: List[str], timeframe: str,
                          since_days: int) -> Dict[str, OHLCVData]:
        """Fetch multiple symbols with caching."""
        data = {}
        for symbol in symbols:
            try:
                ohlcv = self.fetch_ohlcv(symbol, timeframe, since_days)
                data[symbol] = ohlcv
            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")
        
        return data
    
    def clear_cache(self, symbol: Optional[str] = None, 
                    timeframe: Optional[str] = None):
        """
        Clear cache entries.
        
        Args:
            symbol: Clear only this symbol (None = all)
            timeframe: Clear only this timeframe (None = all)
        """
        for meta_file in self.cache_dir.glob("*.meta.json"):
            try:
                with open(meta_file, 'r') as f:
                    meta = json.load(f)
                
                should_delete = True
                if symbol and meta['symbol'] != symbol:
                    should_delete = False
                if timeframe and meta['timeframe'] != timeframe:
                    should_delete = False
                
                if should_delete:
                    csv_file = meta_file.with_suffix('.csv')
                    meta_file.unlink()
                    if csv_file.exists():
                        csv_file.unlink()
                    logger.info(f"Cleared cache for {meta['symbol']} {meta['timeframe']}")
                    
            except Exception as e:
                logger.warning(f"Failed to clear cache entry {meta_file}: {e}")
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        stats = {
            'total_files': 0,
            'total_size_bytes': 0,
            'symbols': set(),
            'timeframes': set()
        }
        
        for meta_file in self.cache_dir.glob("*.meta.json"):
            try:
                with open(meta_file, 'r') as f:
                    meta = json.load(f)
                
                stats['total_files'] += 1
                csv_file = meta_file.with_suffix('.csv')
                if csv_file.exists():
                    stats['total_size_bytes'] += csv_file.stat().st_size
                
                stats['symbols'].add(meta['symbol'])
                stats['timeframes'].add(meta['timeframe'])
                
            except Exception:
                pass
        
        stats['symbols'] = list(stats['symbols'])
        stats['timeframes'] = list(stats['timeframes'])
        stats['total_size_mb'] = round(stats['total_size_bytes'] / (1024 * 1024), 2)
        
        return stats
