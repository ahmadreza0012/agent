"""
AI Sentiment Module
Generates market views from news/sentiment using LLM or mock fallback
"""
import logging
import os
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AISentimentAnalyzer:
    """
    Generate market views from sentiment analysis
    
    Supports:
    - Real LLM integration (Groq API)
    - Mock fallback for backtesting
    """
    
    def __init__(self, api_key: str = None, use_mock: bool = True):
        """
        Initialize sentiment analyzer
        
        Args:
            api_key: Groq API key (optional, falls back to mock)
            use_mock: If True, use deterministic mock sentiment
        """
        self.api_key = api_key or os.environ.get('GROQ_API_KEY')
        self.use_mock = use_mock or (self.api_key is None)
        
        if not self.use_mock and self.api_key:
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
                logger.info("Initialized Groq client for real sentiment analysis")
            except Exception as e:
                logger.warning(f"Failed to initialize Groq: {e}. Using mock.")
                self.use_mock = True
        else:
            logger.info("Using mock sentiment analyzer for backtesting")
        
        # Symbol mapping for sentiment generation
        self.symbol_names = {
            'BTC': 'Bitcoin',
            'ETH': 'Ethereum', 
            'SOL': 'Solana',
            'BNB': 'Binance Coin',
            'XRP': 'Ripple'
        }
    
    def generate_mock_sentiment(self, prices: pd.DataFrame, 
                                window: int = 168) -> pd.DataFrame:
        """
        Generate deterministic mock sentiment based on price momentum
        
        This simulates what an AI might infer from news/social media
        
        Args:
            prices: DataFrame of prices
            window: Lookback window in hours (default: 1 week = 168h)
            
        Returns:
            DataFrame of sentiment scores (-1 to 1)
        """
        logger.info("Generating mock sentiment from price momentum")
        
        sentiment_data = {}
        
        for symbol in prices.columns:
            # Calculate momentum-based sentiment
            returns = prices[symbol].pct_change(window)
            
            # Normalize to [-1, 1] range using tanh
            sentiment = np.tanh(returns * 10)  # Scale factor
            
            # Add some mean reversion pressure
            ma = prices[symbol].rolling(window=24).mean()
            deviation = (prices[symbol] - ma) / ma
            mean_rev = -np.tanh(deviation * 5) * 0.3
            
            # Combined sentiment
            sentiment_data[symbol] = sentiment + mean_rev
        
        sentiment_df = pd.DataFrame(sentiment_data, index=prices.index)
        sentiment_df = sentiment_df.clip(-1, 1)
        
        return sentiment_df
    
    def generate_real_sentiment(self, symbol: str, 
                               recent_news: str = None) -> float:
        """
        Generate sentiment score using real LLM
        
        Args:
            symbol: Cryptocurrency symbol
            recent_news: Recent news text (optional)
            
        Returns:
            Sentiment score (-1 to 1)
        """
        if not self.api_key:
            return 0.0
        
        try:
            name = self.symbol_names.get(symbol.replace('USDT', ''), symbol)
            
            prompt = f"""
            Analyze the market sentiment for {name} ({symbol}) based on recent crypto market conditions.
            Consider factors like:
            - Market momentum
            - Trading volume trends
            - General crypto market sentiment
            - Technical positioning
            
            Return ONLY a single number between -1 (very bearish) and 1 (very bullish).
            No explanation, just the number.
            """
            
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.3
            )
            
            sentiment_text = response.choices[0].message.content.strip()
            sentiment = float(sentiment_text)
            
            # Clip to valid range
            sentiment = np.clip(sentiment, -1, 1)
            
            logger.info(f"Real sentiment for {symbol}: {sentiment:.3f}")
            return sentiment
            
        except Exception as e:
            logger.error(f"Error getting real sentiment: {e}")
            return 0.0
    
    def generate_views(self, prices: pd.DataFrame, 
                      expected_returns: np.ndarray,
                      symbols: List[str]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate Black-Litterman views from sentiment
        
        Args:
            prices: Price DataFrame
            expected_returns: Historical expected returns
            symbols: List of symbol names
            
        Returns:
            Tuple of (P, Q) where:
            - P: View matrix (k x n)
            - Q: View returns vector (k x 1)
        """
        logger.info("Generating Black-Litterman views from sentiment")
        
        if self.use_mock:
            sentiment = self.generate_mock_sentiment(prices)
            latest_sentiment = sentiment.iloc[-1].values
        else:
            latest_sentiment = np.array([
                self.generate_real_sentiment(sym) for sym in symbols
            ])
        
        n_assets = len(symbols)
        
        # Create absolute views for each asset
        # P matrix: identity (each view is about one asset)
        P = np.eye(n_assets)
        
        # Q vector: sentiment-adjusted expected returns
        # Scale sentiment impact (confidence weight)
        confidence = 0.5  # Moderate confidence in AI views
        Q = latest_sentiment * confidence * np.abs(expected_returns)
        
        logger.info(f"Generated {n_assets} views")
        logger.info(f"View returns (Q): {Q}")
        
        return P, Q
    
    def get_confidence_matrix(self, n_assets: int, 
                             base_confidence: float = 0.05) -> np.ndarray:
        """
        Get uncertainty matrix for views (Omega)
        
        Args:
            n_assets: Number of assets
            base_confidence: Base uncertainty level
            
        Returns:
            Diagonal uncertainty matrix
        """
        # Higher confidence = lower uncertainty
        omega = np.diag([base_confidence] * n_assets)
        return omega


def main():
    """Test sentiment analyzer"""
    # Create sample data
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    prices = pd.DataFrame(
        np.random.randn(100, 5).cumsum() + 100,
        index=dates,
        columns=['BTC', 'ETH', 'SOL', 'BNB', 'XRP']
    )
    
    analyzer = AISentimentAnalyzer(use_mock=True)
    
    # Generate sentiment
    sentiment = analyzer.generate_mock_sentiment(prices)
    print("\n=== Sentiment Analysis ===")
    print(f"Latest sentiment:\n{sentiment.iloc[-1]}")
    print(f"\nSentiment statistics:")
    print(sentiment.describe())
    
    # Generate views
    expected_returns = np.array([0.001, 0.001, 0.001, 0.001, 0.001])
    symbols = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP']
    
    P, Q = analyzer.generate_views(prices, expected_returns, symbols)
    print(f"\n=== Black-Litterman Views ===")
    print(f"P matrix shape: {P.shape}")
    print(f"Q vector: {Q}")
    
    return sentiment, P, Q


if __name__ == "__main__":
    sentiment, P, Q = main()
