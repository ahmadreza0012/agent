"""
Performance tests for pandas operations.
"""

import sys
sys.path.insert(0, '/workspace')

import unittest
import pandas as pd
import numpy as np
import time


class TestPandasOperations(unittest.TestCase):
    """Test pandas operation performance."""
    
    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        self.large_df = pd.DataFrame({
            'open': np.random.randn(10000).cumsum() + 100,
            'high': np.random.randn(10000).cumsum() + 100,
            'low': np.random.randn(10000).cumsum() + 100,
            'close': np.random.randn(10000).cumsum() + 100,
            'volume': np.random.randint(100, 10000, 10000)
        }, index=pd.date_range('2020-01-01', periods=10000, freq='H'))
    
    def test_rolling_mean_performance(self):
        """Test rolling mean performance."""
        start_time = time.time()
        
        result = self.large_df['close'].rolling(20).mean()
        
        elapsed = time.time() - start_time
        # Should complete in under 1 second for 10k rows
        self.assertLess(elapsed, 1.0)
        self.assertEqual(len(result), len(self.large_df))
    
    def test_ewm_performance(self):
        """Test exponentially weighted mean performance."""
        start_time = time.time()
        
        result = self.large_df['close'].ewm(span=20).mean()
        
        elapsed = time.time() - start_time
        # Should complete in under 1 second for 10k rows
        self.assertLess(elapsed, 1.0)
        self.assertEqual(len(result), len(self.large_df))
    
    def test_covariance_matrix_performance(self):
        """Test covariance matrix calculation performance."""
        returns_df = pd.DataFrame({
            'BTC': np.random.randn(1000) * 0.01,
            'ETH': np.random.randn(1000) * 0.015,
            'SOL': np.random.randn(1000) * 0.02,
            'ADA': np.random.randn(1000) * 0.025,
            'DOT': np.random.randn(1000) * 0.03,
        })
        
        start_time = time.time()
        
        cov_matrix = returns_df.cov()
        
        elapsed = time.time() - start_time
        # Should complete in under 0.5 seconds
        self.assertLess(elapsed, 0.5)
        self.assertEqual(cov_matrix.shape, (5, 5))
    
    def test_merge_performance(self):
        """Test DataFrame merge performance."""
        df1 = pd.DataFrame({
            'date': pd.date_range('2020-01-01', periods=5000, freq='H'),
            'price': np.random.randn(5000).cumsum()
        })
        df2 = pd.DataFrame({
            'date': pd.date_range('2020-01-01', periods=5000, freq='H'),
            'volume': np.random.randint(100, 1000, 5000)
        })
        
        start_time = time.time()
        
        result = pd.merge(df1, df2, on='date')
        
        elapsed = time.time() - start_time
        # Should complete in under 0.5 seconds
        self.assertLess(elapsed, 0.5)
        self.assertEqual(len(result), 5000)


if __name__ == '__main__':
    unittest.main()
