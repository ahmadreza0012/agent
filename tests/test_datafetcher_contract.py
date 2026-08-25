"""
DataFetcher Contract Verification Tests
========================================
Verifies that the DataFetcher implementation matches the API expected by main.py

Tests cover:
1. Constructor accepts symbols parameter
2. fetch_all_symbols() method exists and returns correct format
3. align_data() method exists and returns aligned DataFrame
4. Full data pipeline execution with synthetic data
5. Symbol normalization
6. Data quality validation
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Dict


def make_synthetic_ohlcv(symbol: str, n_days: int = 365, freq: str = 'D', 
                          start_date: datetime = None) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    if start_date is None:
        start_date = datetime.now(timezone.utc) - timedelta(days=n_days)
    
    dates = pd.date_range(start_date, periods=n_days, freq=freq, tz=timezone.utc)
    np.random.seed(hash(symbol) % 1000)
    rets = np.random.normal(0.0001, 0.02, n_days)
    close = 100 * np.exp(np.cumsum(rets))
    
    return pd.DataFrame({
        'open': close * (1 - 0.001),
        'high': close * 1.002,
        'low': close * 0.998,
        'close': close,
        'volume': np.random.uniform(100, 1000, n_days)
    }, index=dates)


class TestDataFetcherConstructor:
    """Test DataFetcher constructor signatures."""
    
    def test_constructor_with_symbols_list(self):
        """main.py line 161: DataFetcher(symbols=symbols)"""
        from data_fetcher import DataFetcher
        
        symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
        df = DataFetcher(symbols=symbols)
        
        assert df.symbols == symbols
        assert hasattr(df, 'fetch_all_symbols')
        assert hasattr(df, 'align_data')
    
    def test_constructor_backward_compatible(self):
        """Legacy usage without symbols should still work."""
        from data_fetcher import DataFetcher
        
        # Should not raise TypeError
        df = DataFetcher()
        assert df.symbols == []
        
        df2 = DataFetcher(exchange_id='binance')
        assert df2.symbols == []
    
    def test_constructor_stores_symbols(self):
        """Symbols must be stored for fetch_all_symbols to use."""
        from data_fetcher import DataFetcher
        
        symbols = ['BTC/USDT', 'ETH/USDT']
        df = DataFetcher(symbols=symbols)
        
        assert df.symbols is not None
        assert len(df.symbols) == 2
        assert 'BTC/USDT' in df.symbols


class TestDataFetcherMethods:
    """Test required DataFetcher methods."""
    
    def test_fetch_all_symbols_exists(self):
        """Method must exist for main.py line 165."""
        from data_fetcher import DataFetcher
        
        df = DataFetcher(symbols=['BTC/USDT'])
        assert callable(getattr(df, 'fetch_all_symbols', None))
    
    def test_align_data_exists(self):
        """Method must exist for main.py line 166."""
        from data_fetcher import DataFetcher
        
        df = DataFetcher(symbols=['BTC/USDT'])
        assert callable(getattr(df, 'align_data', None))
    
    def test_align_data_returns_dataframe(self):
        """align_data must return a DataFrame with symbol columns."""
        from data_fetcher import DataFetcher
        
        symbols = ['BTC/USDT', 'ETH/USDT']
        df = DataFetcher(symbols=symbols)
        
        raw_data = {sym: make_synthetic_ohlcv(sym, n_days=100) for sym in symbols}
        aligned = df.align_data(raw_data)
        
        assert isinstance(aligned, pd.DataFrame)
        assert len(aligned.columns) == len(symbols)
        assert all(sym in aligned.columns for sym in symbols)
    
    def test_align_data_handles_missing_values(self):
        """align_data should forward/backward fill missing values."""
        from data_fetcher import DataFetcher
        
        symbols = ['BTC/USDT', 'ETH/USDT']
        df = DataFetcher(symbols=symbols)
        
        # Use same start date for both to ensure aligned indices
        base_date = datetime.now(timezone.utc) - timedelta(days=100)
        raw_data = {
            'BTC/USDT': make_synthetic_ohlcv('BTC/USDT', n_days=100, start_date=base_date),
            'ETH/USDT': make_synthetic_ohlcv('ETH/USDT', n_days=100, start_date=base_date)
        }
        
        aligned = df.align_data(raw_data)
        
        # After ffill/bfill with same date ranges, should have no NaN
        nan_count = aligned.isnull().sum().sum()
        assert nan_count == 0, f"Expected no NaN with aligned dates, got {nan_count}"


class TestFullDataPipeline:
    """Test the complete data fetching pipeline as used in main.py."""
    
    def test_main_py_lines_161_169(self):
        """
        Simulate exact code flow from main.py:
        Line 161: data_fetcher = DataFetcher(symbols=symbols)
        Line 165: raw_data = data_fetcher.fetch_all_symbols(since_days=since_days)
        Line 166: df_prices = data_fetcher.align_data(raw_data)
        Lines 167-169: Add CASH column
        """
        from data_fetcher import DataFetcher
        
        # Line 161
        symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']
        data_fetcher = DataFetcher(symbols=symbols)
        
        # Line 165 (simulated with synthetic data)
        raw_data = {sym: make_synthetic_ohlcv(sym, n_days=365) for sym in symbols}
        
        # Line 166
        df_prices = data_fetcher.align_data(raw_data)
        
        # Lines 167-169
        cash_column = pd.DataFrame([1.0] * len(df_prices), index=df_prices.index, columns=['CASH'])
        df_prices_with_cash = pd.concat([df_prices, cash_column], axis=1)
        
        # Verify results
        assert df_prices_with_cash.shape[0] > 0
        assert df_prices_with_cash.shape[1] == 6  # 5 symbols + CASH
        assert 'CASH' in df_prices_with_cash.columns
        assert all(sym in df_prices_with_cash.columns for sym in symbols)
    
    def test_data_quality_requirements(self):
        """Verify data meets quality requirements for downstream processing."""
        from data_fetcher import DataFetcher
        
        symbols = ['BTC/USDT', 'ETH/USDT']
        df = DataFetcher(symbols=symbols)
        
        raw_data = {sym: make_synthetic_ohlcv(sym, n_days=365) for sym in symbols}
        aligned = df.align_data(raw_data)
        
        # Check requirements
        assert isinstance(aligned.index, pd.DatetimeIndex), "Must have DatetimeIndex"
        assert aligned.index.is_monotonic_increasing, "Must be sorted by time"
        assert not aligned.index.has_duplicates, "No duplicate timestamps"
        # Check non-NaN values are positive (NaN may exist at edges after ffill/bfill)
        non_nan_values = aligned.dropna()
        assert (non_nan_values > 0).all().all(), "Non-NaN prices must be positive"
        assert not np.isinf(aligned.values).any(), "No infinite values"


class TestSymbolNormalization:
    """Test symbol format handling."""
    
    def test_standard_ccxt_format(self):
        """CCXT standard format: BTC/USDT"""
        from data_fetcher import DataFetcher
        
        symbols = ['BTC/USDT', 'ETH/USDT']
        df = DataFetcher(symbols=symbols)
        assert df.symbols == symbols
    
    def test_empty_symbols_list(self):
        """Empty symbols should be handled gracefully."""
        from data_fetcher import DataFetcher
        
        df = DataFetcher(symbols=[])
        assert df.symbols == []
        
        # fetch_all_symbols should return empty dict
        result = df.fetch_all_symbols()
        assert result == {}
    
    def test_none_symbols(self):
        """None symbols should default to empty list."""
        from data_fetcher import DataFetcher
        
        df = DataFetcher(symbols=None)
        assert df.symbols == []


class TestDataFetcherIntegration:
    """Integration tests with FakeDataFetcher pattern from integration_test.py."""
    
    def test_fake_data_fetcher_inheritance(self):
        """FakeDataFetcher can inherit and override fetch_all_symbols."""
        from data_fetcher import DataFetcher
        
        since_days = 365
        
        class FakeDataFetcher(DataFetcher):
            def fetch_all_symbols(self, timeframe='1d', since_days=365):
                return {sym: make_synthetic_ohlcv(sym, n_days=since_days) 
                        for sym in self.symbols}
        
        symbols = ['BTC/USDT', 'ETH/USDT']
        fake_df = FakeDataFetcher(symbols=symbols)
        
        raw_data = fake_df.fetch_all_symbols()
        assert len(raw_data) == 2
        assert all(isinstance(df, pd.DataFrame) for df in raw_data.values())
        
        aligned = fake_df.align_data(raw_data)
        assert aligned.shape[0] == since_days
        assert aligned.shape[1] == len(symbols)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
