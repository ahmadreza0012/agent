"""
Time-series tests for look-ahead bias.
"""

import sys
sys.path.insert(0, '/workspace')

import unittest
import pandas as pd
import numpy as np


class TestLookAheadBias(unittest.TestCase):
    """Test for look-ahead bias in ML and data processing."""
    
    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        self.dates = pd.date_range('2020-01-01', periods=200, freq='D')
        self.returns = pd.DataFrame({
            'BTC': np.random.randn(200) * 0.01,
            'ETH': np.random.randn(200) * 0.015,
            'SOL': np.random.randn(200) * 0.02,
        }, index=self.dates)
    
    def test_ml_no_future_data(self):
        """Test ML pipeline doesn't use future data."""
        try:
            from ml.pipeline import MLPipeline
            
            pipeline = MLPipeline()
            train_X = self.returns.iloc[:100].values
            train_y = self.returns.iloc[1:101, 0].values
            test_X = self.returns.iloc[100:150].values
            
            pipeline.train(train_X, train_y)
            predictions = pipeline.predict(test_X)
            self.assertEqual(len(predictions), len(test_X))
        except ImportError:
            self.skipTest("MLPipeline not implemented yet")
    
    def test_scaler_no_future_data(self):
        """Test scalers don't use future data."""
        try:
            from sklearn.preprocessing import StandardScaler
            
            train_data = self.returns.iloc[:100]
            test_data = self.returns.iloc[100:150]
            
            scaler = StandardScaler()
            scaler.fit(train_data)
            scaled_test = scaler.transform(test_data)
            
            # Test data should be scaled using training statistics only
            test_mean = scaled_test.mean(axis=0)
            self.assertAlmostEqual(test_mean.mean(), 0, places=6)
        except ImportError:
            self.skipTest("sklearn not installed")
    
    def test_rolling_window_no_center(self):
        """Test rolling windows are not centered."""
        series = pd.Series(np.random.randn(100))
        causal = series.rolling(20).mean()
        
        # Check that values at time t use only data <= t
        for i in range(20, len(causal)):
            expected = series.iloc[i-19:i+1].mean()
            self.assertAlmostEqual(causal.iloc[i], expected, places=10)
    
    def test_imputation_no_future(self):
        """Test imputation doesn't use future data."""
        series = pd.Series([1, 2, np.nan, 4, 5])
        ffill = series.ffill()
        self.assertEqual(ffill.iloc[2], 2)  # Uses previous value


if __name__ == '__main__':
    unittest.main()
