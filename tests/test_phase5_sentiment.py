"""
Phase 5 Sentiment Integration Tests
====================================
Tests for dual-signal sentiment (per_asset_news_sentiment + market_tone_score),
news pipeline robustness, BL Q magnitude capping, and bounded multipliers.
"""
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, '/workspace')

from ai_sentiment import AISentimentAnalyzer
from news_fetcher import NewsFetcher


class TestPhase5Sentiment:
    """Phase 5 sentiment integration tests."""
    
    def test_api_failure_returns_neutral(self):
        """Test that API/network failures return neutral sentiment (0.0) without crashing."""
        analyzer = AISentimentAnalyzer(use_mock=True)
        
        # Test with empty headlines (simulates API failure)
        symbols = ['BTC', 'ETH']
        headlines_map = {'BTC': [], 'ETH': []}
        
        result = analyzer.generate_per_asset_news_sentiment(symbols, headlines_map)
        
        # Should return neutral (0.0) for all symbols
        assert result['BTC'] == 0.0
        assert result['ETH'] == 0.0
    
    def test_clip_scores_to_range(self):
        """Test that sentiment scores are clipped to [-1, 1] range."""
        analyzer = AISentimentAnalyzer(use_mock=True)
        
        # Mock generate_real_sentiment to return extreme values
        with patch.object(analyzer, 'generate_real_sentiment', return_value=5.0):
            symbols = ['BTC']
            headlines_map = {'BTC': ['headline1', 'headline2', 'headline3']}
            
            result = analyzer.generate_per_asset_news_sentiment(symbols, headlines_map)
            
            # Score should be clipped to 1.0 maximum
            assert result['BTC'] <= 1.0
            assert result['BTC'] >= -1.0
        
        # Test negative extreme
        with patch.object(analyzer, 'generate_real_sentiment', return_value=-5.0):
            result = analyzer.generate_per_asset_news_sentiment(symbols, headlines_map)
            
            # Score should be clipped to -1.0 minimum
            assert result['BTC'] >= -1.0
            assert result['BTC'] <= 1.0
    
    def test_market_tone_bounded(self):
        """Test that market_tone_score is bounded and computed correctly."""
        analyzer = AISentimentAnalyzer(use_mock=True)
        
        # Test with mixed sentiments
        per_asset_sentiments = {
            'BTC': 0.8,
            'ETH': -0.5,
            'SOL': 0.3
        }
        
        market_tone = analyzer.generate_market_tone_score(per_asset_sentiments)
        
        # Should be mean of sentiments: (0.8 + (-0.5) + 0.3) / 3 = 0.2
        expected_mean = np.mean([0.8, -0.5, 0.3])
        assert abs(market_tone - expected_mean) < 1e-6
        
        # Should be within [-1, 1]
        assert market_tone >= -1.0
        assert market_tone <= 1.0
    
    def test_market_tone_empty_input(self):
        """Test that empty per_asset_sentiments returns neutral market_tone."""
        analyzer = AISentimentAnalyzer(use_mock=True)
        
        market_tone = analyzer.generate_market_tone_score({})
        
        assert market_tone == 0.0
    
    def test_bl_q_magnitude_capped(self):
        """Test that Black-Litterman Q vector magnitudes are capped."""
        analyzer = AISentimentAnalyzer(use_mock=True)
        
        # Create mock data with proper column format
        dates = pd.date_range("2024-01-01", periods=200, freq="h")
        prices = pd.DataFrame(
            np.random.randn(200, 3).cumsum() + 100,
            index=dates,
            columns=['BTC', 'ETH', 'SOL']
        )
        expected_returns = np.array([0.5, -0.3, 0.8])  # Extreme expected returns
        
        # Test with extreme sentiment scores
        per_asset_sentiment = {
            'BTC': 1.0,   # Maximum positive
            'ETH': -1.0,  # Maximum negative
            'SOL': 1.0
        }
        
        P, Q = analyzer.generate_views(prices, expected_returns, 
                                        ['BTC', 'ETH', 'SOL'],
                                        per_asset_sentiment=per_asset_sentiment)
        
        # Q_CAP should be 0.10 (defined in generate_views)
        Q_CAP = 0.10
        assert np.all(Q <= Q_CAP), f"Q values exceed cap: {Q}"
        assert np.all(Q >= -Q_CAP), f"Q values below negative cap: {Q}"
        
        # All Q values should be finite
        assert np.all(np.isfinite(Q))
    
    def test_bl_neutral_views_degrade_to_prior(self):
        """Test that neutral/empty views degrade gracefully to prior."""
        analyzer = AISentimentAnalyzer(use_mock=True)
        
        dates = pd.date_range("2024-01-01", periods=200, freq="h")
        prices = pd.DataFrame(
            np.random.randn(200, 3).cumsum() + 100,
            index=dates,
            columns=['BTC', 'ETH', 'SOL']
        )
        expected_returns = np.array([0.01, 0.02, 0.015])
        
        # Neutral sentiment (all zeros)
        per_asset_sentiment = {'BTC': 0.0, 'ETH': 0.0, 'SOL': 0.0}
        
        P, Q = analyzer.generate_views(prices, expected_returns,
                                        ['BTC', 'ETH', 'SOL'],
                                        per_asset_sentiment=per_asset_sentiment)
        
        # Q should be all zeros (neutral views)
        assert np.allclose(Q, 0.0)
        
        # P should be identity matrix
        assert np.allclose(P, np.eye(3))
    
    def test_news_deduplication(self):
        """Test that duplicate headlines are removed."""
        fetcher = NewsFetcher()
        
        headlines = [
            {"title": "Bitcoin surges past $50k", "source": "coindesk"},
            {"title": "BITCOIN SURGES PAST $50K", "source": "cointelegraph"},  # Duplicate (case-insensitive)
            {"title": "Ethereum upgrade scheduled", "source": "coindesk"},
            {"title": "Bitcoin surges past $50k", "source": "cryptopanic"},  # Exact duplicate
        ]
        
        unique = NewsFetcher.deduplicate_headlines(headlines)
        
        # Should remove duplicates, keeping only unique headlines
        assert len(unique) == 2
        titles = [h["title"] for h in unique]
        assert "Bitcoin surges past $50k" in titles
        assert "Ethereum upgrade scheduled" in titles
    
    def test_offline_mock_mode_works(self):
        """Test that system works in offline/mock mode without network."""
        # Create analyzer with use_mock=True (no API key needed)
        analyzer = AISentimentAnalyzer(use_mock=True)
        
        # Generate mock sentiment from prices
        dates = pd.date_range("2024-01-01", periods=200, freq="h")
        prices = pd.DataFrame(
            np.random.randn(200, 3).cumsum() + 100,
            columns=['BTC', 'ETH', 'SOL']
        )
        
        sentiment = analyzer.generate_mock_sentiment(prices)
        
        # Should produce valid sentiment scores
        assert sentiment is not None
        assert len(sentiment.columns) == 3
        assert all(sentiment.iloc[-1].notna())
        
        # Scores should be in [-1, 1] range
        assert (sentiment.iloc[-1] >= -1.0).all()
        assert (sentiment.iloc[-1] <= 1.0).all()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
