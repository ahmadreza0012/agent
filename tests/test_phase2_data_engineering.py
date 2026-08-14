"""
Tests for Phase 2 Data Engineering

Tests for:
- SymbolMapper canonicalization
- DataQualityValidator catches issues
- Volume unavailable path does not fabricate zeros
- Cache write/read metadata roundtrip
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tempfile
import os

from data.providers.symbol_mapper import SymbolMapper
from data.providers.quality_validator import DataQualityValidator
from data.providers.base import OHLCVData


class TestSymbolMapper:
    """Test symbol mapping functionality."""
    
    def test_canonical_symbols(self):
        """Test that canonical symbols are defined."""
        mapper = SymbolMapper()
        symbols = mapper.get_canonical_symbols()
        assert 'BTC/USDT' in symbols
        assert 'ETH/USDT' in symbols
        assert len(symbols) >= 5
    
    def test_to_coingecko_id(self):
        """Test CoinGecko ID mapping."""
        mapper = SymbolMapper()
        assert mapper.to_coingecko_id('BTC/USDT') == 'bitcoin'
        assert mapper.to_coingecko_id('ETH/USDT') == 'ethereum'
        assert mapper.to_coingecko_id('UNKNOWN') is None
    
    def test_to_yfinance_ticker(self):
        """Test yfinance ticker mapping."""
        mapper = SymbolMapper()
        assert mapper.to_yfinance_ticker('BTC/USDT') == 'BTC-USD'
        assert mapper.to_yfinance_ticker('ETH/USDT') == 'ETH-USD'
        assert mapper.to_yfinance_ticker('UNKNOWN') is None
    
    def test_from_coingecko_id(self):
        """Test reverse CoinGecko lookup."""
        mapper = SymbolMapper()
        assert mapper.from_coingecko_id('bitcoin') == 'BTC/USDT'
        assert mapper.from_coingecko_id('ethereum') == 'ETH/USDT'
        assert mapper.from_coingecko_id('unknown') is None
    
    def test_normalize_yfinance(self):
        """Test normalization from yfinance format."""
        mapper = SymbolMapper()
        assert mapper.normalize_symbol('BTC-USD', 'yfinance') == 'BTC/USDT'
        assert mapper.normalize_symbol('ETH-USD', 'yfinance') == 'ETH/USDT'
    
    def test_normalize_coingecko(self):
        """Test normalization from CoinGecko format."""
        mapper = SymbolMapper()
        assert mapper.normalize_symbol('bitcoin', 'coingecko') == 'BTC/USDT'
        assert mapper.normalize_symbol('ethereum', 'coingecko') == 'ETH/USDT'
    
    def test_normalize_binance(self):
        """Test normalization from Binance format."""
        mapper = SymbolMapper()
        # Already canonical
        assert mapper.normalize_symbol('BTC/USDT', 'binance') == 'BTC/USDT'
        # CCXT format without slash
        assert mapper.normalize_symbol('BTCUSDT', 'binance') == 'BTC/USDT'
    
    def test_custom_mapping(self):
        """Test custom symbol mappings."""
        mapper = SymbolMapper()
        mapper.add_custom_mapping('BTC/USDT', 'exchange_x', 'BTCUSD')
        assert mapper.get_custom_mapping('BTC/USDT', 'exchange_x') == 'BTCUSD'
        assert mapper.get_custom_mapping('BTC/USDT', 'unknown') is None


class TestDataQualityValidator:
    """Test data quality validation."""
    
    def _create_valid_df(self, rows=100, freq='1H'):
        """Create a valid OHLCV DataFrame."""
        dates = pd.date_range(start='2024-01-01', periods=rows, freq=freq)
        df = pd.DataFrame({
            'Open': np.random.uniform(100, 110, rows),
            'High': np.random.uniform(110, 120, rows),
            'Low': np.random.uniform(90, 100, rows),
            'Close': np.random.uniform(100, 110, rows),
            'Volume': np.random.uniform(1000, 10000, rows)
        }, index=dates)
        return df
    
    def test_valid_data(self):
        """Test that valid data passes validation."""
        validator = DataQualityValidator()
        df = self._create_valid_df()
        report = validator.validate(df, symbol='BTC/USDT', timeframe='1h')
        
        assert report['valid'] is True
        assert report['duplicate_candles'] == 0
        assert report['out_of_order'] is False
        assert len(report['errors']) == 0
    
    def test_detects_duplicates(self):
        """Test detection of duplicate timestamps."""
        validator = DataQualityValidator()
        df = self._create_valid_df(rows=50)
        # Add duplicate row
        df = pd.concat([df, df.iloc[-1:]])
        
        report = validator.validate(df, symbol='BTC/USDT', timeframe='1h')
        
        assert report['valid'] is False
        assert report['duplicate_candles'] > 0
        assert any('duplicate' in err.lower() for err in report['errors'])
    
    def test_detects_out_of_order(self):
        """Test detection of out-of-order index."""
        validator = DataQualityValidator()
        df = self._create_valid_df(rows=50)
        # Sort in reverse order to make it non-monotonic
        df = df.sort_index(ascending=False)
        
        report = validator.validate(df, symbol='BTC/USDT', timeframe='1h')
        
        assert report['valid'] is False
        assert report['out_of_order'] is True
        assert any('order' in err.lower() or 'monotonic' in err.lower() 
                   for err in report['errors'])
    
    def test_detects_nans(self):
        """Test detection of NaN values."""
        validator = DataQualityValidator(max_nan_ratio=0.01)
        df = self._create_valid_df()
        # Introduce NaN values
        df.loc[df.index[:10], 'Close'] = np.nan
        
        report = validator.validate(df, symbol='BTC/USDT', timeframe='1h')
        
        assert report['nan_ratio'] > 0.01
        assert report['valid'] is False
        assert any('nan' in err.lower() for err in report['errors'])
    
    def test_detects_zero_volume(self):
        """Test detection of zero volume ratio."""
        validator = DataQualityValidator(zero_volume_threshold=0.1)
        df = self._create_valid_df()
        # Set many volumes to zero
        df.loc[df.index[:50], 'Volume'] = 0
        
        report = validator.validate(df, symbol='BTC/USDT', timeframe='1h')
        
        assert report['zero_volume_ratio'] > 0.1
        assert any('zero volume' in warn.lower() for warn in report['warnings'])
    
    def test_empty_dataframe_fails(self):
        """Test that empty DataFrame fails validation."""
        validator = DataQualityValidator()
        df = pd.DataFrame()
        
        report = validator.validate(df, symbol='BTC/USDT', timeframe='1h')
        
        assert report['valid'] is False
        assert any('empty' in err.lower() for err in report['errors'])
    
    def test_non_datetime_index_fails(self):
        """Test that non-DatetimeIndex fails validation."""
        validator = DataQualityValidator()
        df = self._create_valid_df()
        df.reset_index(inplace=True)  # Remove DatetimeIndex
        
        report = validator.validate(df, symbol='BTC/USDT', timeframe='1h')
        
        assert report['valid'] is False
        assert any('datetime' in err.lower() or 'index' in err.lower() 
                   for err in report['errors'])
    
    def test_volume_nan_unavailable_warning(self):
        """Test that entirely NaN volume triggers warning (not error)."""
        validator = DataQualityValidator()
        df = self._create_valid_df()
        df['Volume'] = np.nan
        
        report = validator.validate(df, symbol='BTC/USDT', timeframe='1h')
        
        # Should still be valid (volume is optional)
        assert report['valid'] is True
        # But should warn about unavailable volume
        assert any('unavailable' in warn.lower() or 'nan' in warn.lower() 
                   for warn in report['warnings'])


class TestOHLCVData:
    """Test OHLCVData container."""
    
    def test_ohlcv_data_creation(self):
        """Test creating OHLCVData with volume available."""
        df = pd.DataFrame({
            'Open': [100, 101],
            'High': [102, 103],
            'Low': [99, 100],
            'Close': [101, 102],
            'Volume': [1000, 2000]
        }, index=pd.date_range('2024-01-01', periods=2, freq='1h'))
        
        ohlcv = OHLCVData(
            df=df,
            symbol='BTC/USDT',
            timeframe='1h',
            source='yfinance',
            volume_available=True
        )
        
        assert ohlcv.symbol == 'BTC/USDT'
        assert ohlcv.volume_available is True
        assert ohlcv.row_count == 2
        assert ohlcv.start_date is not None
        assert ohlcv.end_date is not None
    
    def test_ohlcv_data_no_volume(self):
        """Test creating OHLCVData without volume (CoinGecko fallback)."""
        df = pd.DataFrame({
            'Open': [100, 101],
            'High': [102, 103],
            'Low': [99, 100],
            'Close': [101, 102],
            'Volume': [np.nan, np.nan]
        }, index=pd.date_range('2024-01-01', periods=2, freq='1d'))
        
        ohlcv = OHLCVData(
            df=df,
            symbol='BTC/USDT',
            timeframe='1d',
            source='coingecko',
            volume_available=False  # Critical: mark as unavailable
        )
        
        assert ohlcv.volume_available is False
        assert ohlcv.source == 'coingecko'


class TestCacheRoundtrip:
    """Test cache write/read roundtrip."""
    
    def test_cache_metadata_roundtrip(self):
        """Test that cache metadata survives roundtrip."""
        from data.providers.cached import CachedDataProvider
        from data.providers.historical import HistoricalDataProvider
        
        # Create test data
        df = pd.DataFrame({
            'Open': [100, 101, 102],
            'High': [105, 106, 107],
            'Low': [99, 100, 101],
            'Close': [101, 102, 103],
            'Volume': [1000, 2000, 3000]
        }, index=pd.date_range('2024-01-01', periods=3, freq='1h'))
        
        ohlcv = OHLCVData(
            df=df,
            symbol='BTC/USDT',
            timeframe='1h',
            source='test',
            volume_available=True
        )
        
        # Create temp directory for cache
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock provider
            class MockProvider:
                def get_source_name(self):
                    return 'mock'
                def supports_timeframe(self, tf):
                    return True
                def fetch_ohlcv(self, symbol, tf, days):
                    return ohlcv
                def fetch_all_symbols(self, symbols, tf, days):
                    return {symbol: ohlcv for symbol in symbols}
            
            cached_provider = CachedDataProvider(MockProvider(), cache_dir=tmpdir)
            
            # Save to cache
            key = cached_provider._get_cache_key('BTC/USDT', '1h', 30)
            cached_provider._save_to_cache(ohlcv, key)
            
            # Load from cache
            loaded = cached_provider._load_from_cache(key)
            
            assert loaded is not None
            assert loaded.symbol == ohlcv.symbol
            assert loaded.timeframe == ohlcv.timeframe
            assert loaded.source == ohlcv.source
            assert loaded.volume_available == ohlcv.volume_available
            assert loaded.row_count == ohlcv.row_count
            
            # Verify data equality
            pd.testing.assert_frame_equal(loaded.df, ohlcv.df)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
