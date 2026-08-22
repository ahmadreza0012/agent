"""
Unit tests for technical indicators.
"""

import sys
sys.path.insert(0, '/workspace')

import unittest
import pandas as pd
import numpy as np


class TestIndicators(unittest.TestCase):
    """Test technical indicator calculations."""
    
    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        self.prices = pd.Series(np.random.randn(100).cumsum() + 100)
        self.ohlc = pd.DataFrame({
            'open': self.prices + np.random.randn(100) * 0.1,
            'high': self.prices + np.abs(np.random.randn(100)) * 0.2,
            'low': self.prices - np.abs(np.random.randn(100)) * 0.2,
            'close': self.prices,
            'volume': np.random.randint(100, 1000, 100)
        })
    
    def test_ema_calculation(self):
        """Test EMA calculation."""
        from features.technical import EMA
        ema = EMA(self.prices, period=20)
        self.assertEqual(len(ema), len(self.prices))
        self.assertTrue((ema > 0).all())
        # EMA should be smoother than raw prices
        self.assertLess(ema.std(), self.prices.std())
    
    def test_ema_causal(self):
        """Test EMA uses only past data."""
        from features.technical import EMA
        ema = EMA(self.prices, period=20)
        # Check that EMA at time t depends only on data <= t
        for i in range(20, len(self.prices)):
            # Recalculate EMA using only data up to i
            truncated = self.prices.iloc[:i+1]
            ema_truncated = EMA(truncated, period=20)
            self.assertEqual(ema.iloc[i], ema_truncated.iloc[-1])
    
    def test_rsi_calculation(self):
        """Test RSI calculation."""
        from features.technical import RSI
        rsi = RSI(self.prices, period=14)
        self.assertEqual(len(rsi), len(self.prices))
        self.assertTrue((rsi >= 0).all())
        self.assertTrue((rsi <= 100).all())
    
    def test_atr_calculation(self):
        """Test ATR calculation."""
        from features.technical import ATR
        atr = ATR(self.ohlc, period=14)
        self.assertEqual(len(atr), len(self.ohlc))
        self.assertTrue((atr >= 0).all())
    
    def test_macd_calculation(self):
        """Test MACD calculation."""
        from features.technical import MACD
        macd, signal, histogram = MACD(self.prices)
        self.assertEqual(len(macd), len(self.prices))
        self.assertEqual(len(signal), len(self.prices))
        self.assertEqual(len(histogram), len(self.prices))
    
    def test_adx_calculation(self):
        """Test ADX calculation."""
        from features.technical import ADX
        adx = ADX(self.ohlc, period=14)
        self.assertEqual(len(adx), len(self.ohlc))
        self.assertTrue((adx >= 0).all())
        self.assertTrue((adx <= 100).all())
    
    def test_indicator_input_validation(self):
        """Test indicators handle invalid inputs."""
        from features.technical import EMA, RSI
        
        # Empty series
        empty_series = pd.Series([])
        with self.assertRaises(ValueError):
            EMA(empty_series, period=20)
        
        # Insufficient data
        short_series = pd.Series(np.random.randn(10))
        with self.assertRaises(ValueError):
            RSI(short_series, period=20)


if __name__ == '__main__':
    unittest.main()
