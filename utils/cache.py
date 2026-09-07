"""
Smart Cache for the Trading System.

This module provides intelligent caching with TTL (time-to-live) support
to avoid redundant computations and improve performance.
"""

import hashlib
import pickle
from pathlib import Path
from functools import wraps
from datetime import datetime, timedelta
from typing import Any, Optional, Callable, Dict
import logging
import threading
from collections import OrderedDict

logger = logging.getLogger(__name__)


class SmartCache:
    """
    Intelligent caching for trading system operations.
    
    Features:
    - File-based persistence for large objects
    - In-memory LRU cache for frequently accessed items
    - TTL (time-to-live) based expiration
    - Automatic cache cleanup
    - Thread-safe operation
    - Function decorator for easy caching
    
    Usage:
        # Create cache instance
        cache = SmartCache(cache_dir='cache', ttl_hours=24)
        
        # Use as decorator
        @cache.cached(ttl_hours=6)
        def expensive_calculation(data, params):
            pass
        
        # Manual cache operations
        key = cache.key(func_name, *args, **kwargs)
        cached = cache.get(key)
        if cached is None:
            result = compute()
            cache.set(key, result)
    """
    
    def __init__(self, cache_dir: str = 'cache', ttl_hours: int = 24, 
                 memory_cache_size: int = 1000):
        """
        Initialize the cache.
        
        Args:
            cache_dir: Directory for file-based cache storage
            ttl_hours: Default time-to-live in hours
            memory_cache_size: Size of in-memory LRU cache
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
        self.default_ttl_hours = ttl_hours
        
        # In-memory LRU cache for frequently accessed items
        self._memory_cache: OrderedDict[str, tuple] = OrderedDict()
        self._memory_cache_size = memory_cache_size
        self._lock = threading.RLock()
        
        logger.info(f"SmartCache initialized: dir={cache_dir}, ttl={ttl_hours}h")
    
    def key(self, prefix: str, *args, **kwargs) -> str:
        """
        Generate cache key from arguments.
        
        Args:
            prefix: Prefix for the cache key (usually function name)
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            MD5 hash of the serialized arguments
        """
        content = {
            'prefix': prefix,
            'args': args,
            'kwargs': sorted(kwargs.items()) if kwargs else {}
        }
        content_str = str(content)
        return hashlib.md5(content_str.encode()).hexdigest()
    
    def get(self, key: str, use_memory: bool = True) -> Optional[Any]:
        """
        Get cached value if not expired.
        
        Args:
            key: Cache key
            use_memory: Also check in-memory cache
            
        Returns:
            Cached value or None if not found/expired
        """
        # Check memory cache first
        if use_memory:
            with self._lock:
                if key in self._memory_cache:
                    value, expiry = self._memory_cache[key]
                    if datetime.now() < expiry:
                        # Move to end (most recently used)
                        self._memory_cache.move_to_end(key)
                        logger.debug(f"Memory cache hit: {key}")
                        return value
                    else:
                        # Expired
                        del self._memory_cache[key]
        
        # Check file cache
        cache_path = self.cache_dir / f"{key}.pkl"
        if not cache_path.exists():
            return None
        
        try:
            # Check TTL
            age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
            if age > self.ttl:
                cache_path.unlink()
                logger.debug(f"File cache expired: {key}")
                return None
            
            with open(cache_path, 'rb') as f:
                value = pickle.load(f)
                
                # Add to memory cache
                if use_memory:
                    self._add_to_memory(key, value)
                
                logger.debug(f"File cache hit: {key}")
                return value
                
        except (pickle.PickleError, EOFError, IOError) as e:
            logger.warning(f"Cache read error for {key}: {e}")
            try:
                cache_path.unlink()
            except:
                pass
            return None
    
    def set(self, key: str, value: Any, use_memory: bool = True):
        """
        Cache a value.
        
        Args:
            key: Cache key
            value: Value to cache
            use_memory: Also store in memory cache
        """
        cache_path = self.cache_dir / f"{key}.pkl"
        
        try:
            # Write to file
            with open(cache_path, 'wb') as f:
                pickle.dump(value, f, protocol=4)  # Protocol 4 is more efficient
            
            # Add to memory cache
            if use_memory:
                self._add_to_memory(key, value)
            
            logger.debug(f"Cached: {key}")
            
        except (pickle.PickleError, IOError) as e:
            logger.error(f"Cache write error for {key}: {e}")
    
    def _add_to_memory(self, key: str, value: Any):
        """Add item to memory cache with LRU eviction."""
        with self._lock:
            expiry = datetime.now() + self.ttl
            
            # Evict oldest if at capacity
            while len(self._memory_cache) >= self._memory_cache_size:
                self._memory_cache.popitem(last=False)
            
            self._memory_cache[key] = (value, expiry)
    
    def invalidate(self, key: str):
        """
        Invalidate a cached value.
        
        Args:
            key: Cache key to invalidate
        """
        # Remove from memory
        with self._lock:
            self._memory_cache.pop(key, None)
        
        # Remove from file
        cache_path = self.cache_dir / f"{key}.pkl"
        if cache_path.exists():
            try:
                cache_path.unlink()
                logger.debug(f"Invalidated cache: {key}")
            except IOError as e:
                logger.warning(f"Failed to invalidate cache {key}: {e}")
    
    def clear(self):
        """Clear all cached data."""
        # Clear memory cache
        with self._lock:
            self._memory_cache.clear()
        
        # Clear file cache
        for cache_file in self.cache_dir.glob('*.pkl'):
            try:
                cache_file.unlink()
            except IOError:
                pass
        
        logger.info("Cache cleared")
    
    def cleanup(self, max_age_days: int = 30):
        """
        Remove old cache files.
        
        Args:
            max_age_days: Maximum age in days for cache files
        """
        cutoff = datetime.now() - timedelta(days=max_age_days)
        removed = 0
        
        for cache_file in self.cache_dir.glob('*.pkl'):
            try:
                if datetime.fromtimestamp(cache_file.stat().st_mtime) < cutoff:
                    cache_file.unlink()
                    removed += 1
            except (IOError, OSError):
                pass
        
        if removed > 0:
            logger.info(f"Cleaned up {removed} old cache files")
        
        return removed
    
    def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        file_count = sum(1 for _ in self.cache_dir.glob('*.pkl'))
        file_size = sum(f.stat().st_size for f in self.cache_dir.glob('*.pkl'))
        
        return {
            'memory_cache_size': len(self._memory_cache),
            'memory_cache_max': self._memory_cache_size,
            'file_cache_count': file_count,
            'file_cache_size_bytes': file_size,
            'file_cache_size_mb': file_size / (1024 * 1024),
            'default_ttl_hours': self.default_ttl_hours,
        }
    
    def cached(self, ttl_hours: Optional[int] = None, use_memory: bool = True):
        """
        Decorator for caching function results.
        
        Args:
            ttl_hours: Time-to-live in hours (overrides default)
            use_memory: Also cache in memory
            
        Returns:
            Decorated function with caching
            
        Example:
            @cache.cached(ttl_hours=6)
            def expensive_calculation(data, params):
                pass
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = self.key(func.__name__, *args, **kwargs)
                
                # Check cache
                cached = self.get(cache_key, use_memory=use_memory)
                if cached is not None:
                    logger.debug(f"Cache hit: {func.__name__}")
                    return cached
                
                # Compute and cache
                result = func(*args, **kwargs)
                
                # Use custom TTL if provided
                if ttl_hours is not None:
                    old_ttl = self.ttl
                    self.ttl = timedelta(hours=ttl_hours)
                    self.set(cache_key, result, use_memory=use_memory)
                    self.ttl = old_ttl
                else:
                    self.set(cache_key, result, use_memory=use_memory)
                
                logger.debug(f"Cache miss, computed: {func.__name__}")
                return result
            return wrapper
        return decorator
    
    def __repr__(self) -> str:
        stats = self.stats()
        return (f"SmartCache(memory={stats['memory_cache_size']}/{stats['memory_cache_max']}, "
                f"files={stats['file_cache_count']}, size={stats['file_cache_size_mb']:.2f}MB)")


# Global cache instance
cache = SmartCache(cache_dir='data/cache', ttl_hours=24)


def cached_function(ttl_hours: int = 24):
    """
    Convenience decorator for caching function results.
    
    Uses the global cache instance.
    
    Args:
        ttl_hours: Time-to-live in hours
        
    Example:
        @cached_function(ttl_hours=6)
        def fetch_data(symbol):
            pass
    """
    return cache.cached(ttl_hours=ttl_hours)
