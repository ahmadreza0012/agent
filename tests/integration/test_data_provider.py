"""
Integration tests for DataProvider.
"""

import sys
sys.path.insert(0, '/workspace')

import unittest
import pandas as pd
from unittest.mock import Mock, patch


class TestDataProvider(unittest.TestCase):
    """Test DataProvider integration."""
    
    def setUp(self):
        """Create test data provider."""
        pass
    
    @patch('data.providers.exchange.BinanceProvider')
    def test_get_historical_data(self, mock_exchange):
        """Test getting historical data."""
        try:
            from data.providers import DataProvider
            
            # Mock response
            mock_data = pd.DataFrame({
                'open': [50000, 50100, 50200],
                'high': [50100, 50200, 50300],
                'low': [49900, 50000, 50100],
                'close': [50100, 50200, 50300],
                'volume': [100, 150, 120]
            }, index=pd.date_range('2024-01-01', periods=3, freq='D'))
            mock_exchange.get_ohlcv.return_value = mock_data
            
            provider = DataProvider()
            data = provider.get_historical_data('BTC/USDT', '2024-01-01', '2024-01-31')
            self.assertIsInstance(data, pd.DataFrame)
            self.assertIn('close', data.columns)
            self.assertEqual(len(data), 3)
        except ImportError:
            self.skipTest("DataProvider not implemented yet")
    
    def test_data_validation(self):
        """Test data validation."""
        try:
            from data.providers import DataProvider
            
            invalid_data = pd.DataFrame({
                'close': [50000, None, 50200, 50300, 50000],
                'volume': [100, 150, None, 120, 130]
            })
            provider = DataProvider()
            result = provider.validate_data(invalid_data)
            self.assertIsInstance(result, dict)
            self.assertIn('valid', result)
        except ImportError:
            self.skipTest("DataProvider not implemented yet")
    
    def test_symbol_normalization(self):
        """Test symbol normalization."""
        try:
            from data.providers import DataProvider
            
            provider = DataProvider()
            normalized = provider.normalize_symbol('BTC-USD')
            self.assertEqual(normalized, 'BTC/USDT')
            
            normalized = provider.normalize_symbol('BTCUSDT')
            self.assertEqual(normalized, 'BTC/USDT')
        except ImportError:
            self.skipTest("DataProvider not implemented yet")


if __name__ == '__main__':
    unittest.main()
