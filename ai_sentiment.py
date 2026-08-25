"""
AI Sentiment Analysis Module for Cryptocurrency Trading
Uses Groq API with robust JSON parsing and fallback mechanisms.
"""

import json
import re
from typing import Dict, List, Optional, Tuple
import logging
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AISentimentAnalyzer:
    """
    AI-powered sentiment analyzer using Groq API.
    Implements robust JSON parsing with regex extraction and rule-based fallbacks.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.1-70b-versatile"):
        """
        Initialize the sentiment analyzer.
        
        Args:
            api_key: Groq API key (can also be set via GROQ_API_KEY env var)
            model: Groq model to use (default: llama-3.1-70b-versatile)
        """
        self.api_key = api_key
        self.model = model
        self.client = self._initialize_client()
        
    def _initialize_client(self):
        """Initialize Groq client."""
        try:
            from groq import Groq
            return Groq(api_key=self.api_key)
        except ImportError:
            logger.warning("Groq library not installed. Install with: pip install groq")
            return None
        except Exception as e:
            logger.warning(f"Failed to initialize Groq client: {e}")
            return None
    
    def analyze_sentiment(
        self,
        asset: str,
        price_data: pd.Series,
        news_headlines: Optional[List[str]] = None,
        social_sentiment: Optional[float] = None
    ) -> Dict:
        """
        Analyze sentiment for a single asset.
        
        Args:
            asset: Asset symbol (e.g., 'BTC', 'ETH')
            price_data: Series of recent prices
            news_headlines: Optional list of news headlines
            social_sentiment: Optional pre-computed social sentiment score
            
        Returns:
            Dictionary with sentiment score, confidence, and view
        """
        # Calculate technical indicators for context
        momentum_7d = self._calculate_momentum(price_data, 7)
        momentum_21d = self._calculate_momentum(price_data, 21)
        rsi = self._calculate_rsi(price_data)
        volatility = price_data.pct_change().std()
        
        # Build prompt with strict JSON output requirement
        prompt = self._build_prompt(asset, momentum_7d, momentum_21d, rsi, 
                                   volatility, news_headlines, social_sentiment)
        
        # Try LLM analysis first
        llm_response = None
        if self.client is not None:
            try:
                llm_response = self._call_llm(prompt)
                sentiment_data = self._parse_llm_response(llm_response)
                
                if sentiment_data is not None and self._validate_sentiment_data(sentiment_data):
                    logger.info(f"{asset}: LLM sentiment parsed successfully: {sentiment_data}")
                    return sentiment_data
                    
            except Exception as e:
                logger.warning(f"{asset}: LLM call failed: {e}. Using fallback.")
        
        # Log raw response for debugging
        if llm_response:
            logger.warning(f"{asset}: Raw LLM response (fallback triggered): {llm_response[:500]}...")
        
        # Use rule-based fallback
        fallback_sentiment = self._rule_based_fallback(asset, momentum_7d, momentum_21d, rsi, volatility)
        logger.info(f"{asset}: Using rule-based fallback sentiment: {fallback_sentiment}")
        
        return fallback_sentiment
    
    def _build_prompt(
        self,
        asset: str,
        momentum_7d: float,
        momentum_21d: float,
        rsi: float,
        volatility: float,
        news_headlines: Optional[List[str]],
        social_sentiment: Optional[float]
    ) -> str:
        """
        Build a strict prompt that enforces JSON output format.
        
        Returns:
            Prompt string for LLM
        """
        news_context = ""
        if news_headlines:
            news_context = f"\nRecent News Headlines:\n" + "\n".join([f"- {h}" for h in news_headlines[:5]])
        
        social_context = ""
        if social_sentiment is not None:
            social_context = f"\nSocial Media Sentiment Score: {social_sentiment:.2f} (-1 to 1)"
        
        prompt = f"""You are a cryptocurrency market analyst. Analyze {asset} and provide a sentiment score.

Technical Indicators:
- 7-day momentum: {momentum_7d:.2%}
- 21-day momentum: {momentum_21d:.2%}
- RSI (14-day): {rsi:.1f}
- Daily volatility: {volatility:.2%}
{news_context}{social_context}

Provide your analysis as a JSON object with this EXACT structure. NO other text allowed:
{{
    "sentiment_score": <float between -1 and 1, where 1 is very bullish, -1 is very bearish>,
    "confidence": <float between 0 and 1>,
    "view_return": <float representing expected return over next period, e.g., 0.05 for 5%>,
    "reasoning": "<brief explanation>"
}}

Rules:
1. Output ONLY valid JSON, no markdown, no code blocks, no explanations outside JSON
2. sentiment_score must be between -1 and 1
3. confidence must be between 0 and 1
4. view_return should be realistic (typically between -0.3 and 0.3 for crypto)
5. Base your analysis on the technical indicators provided

Your response:"""
        
        return prompt
    
    def _call_llm(self, prompt: str, max_retries: int = 2) -> Optional[str]:
        """
        Call the LLM with retry logic.
        
        Args:
            prompt: The prompt to send
            max_retries: Maximum retry attempts
            
        Returns:
            Raw LLM response string or None
        """
        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that outputs ONLY valid JSON. No markdown, no code blocks."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.3,
                    max_tokens=500,
                    timeout=30
                )
                
                if response and response.choices and len(response.choices) > 0:
                    return response.choices[0].message.content.strip()
                    
            except Exception as e:
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    logger.warning(f"LLM call attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                    import time
                    time.sleep(wait_time)
                else:
                    logger.error(f"LLM call failed after {max_retries + 1} attempts: {e}")
                    raise
        
        return None
    
    def _parse_llm_response(self, response: str) -> Optional[Dict]:
        """
        Parse LLM response with robust JSON extraction using regex.
        
        Args:
            response: Raw LLM response string
            
        Returns:
            Parsed dictionary or None if parsing fails
        """
        if not response:
            logger.warning("Empty LLM response")
            return None
        
        # Try direct JSON parsing first
        try:
            data = json.loads(response)
            return data
        except json.JSONDecodeError:
            pass
        
        # Try extracting JSON from markdown code blocks
        json_block_pattern = r'```(?:json)?\s*({.*?})\s*```'
        match = re.search(json_block_pattern, response, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                return data
            except json.JSONDecodeError:
                pass
        
        # Try finding any JSON object in the response using regex
        json_object_pattern = r'\{[^{}]*"sentiment_score"[^{}]*\}'
        match = re.search(json_object_pattern, response, re.IGNORECASE | re.DOTALL)
        if match:
            try:
                # Clean up the matched string
                json_str = match.group(0)
                # Remove any trailing commas before closing braces
                json_str = re.sub(r',\s*}', '}', json_str)
                data = json.loads(json_str)
                return data
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse extracted JSON: {e}")
        
        # Last resort: try to extract numeric values using patterns
        logger.info(f"Attempting pattern-based extraction from: {response[:200]}")
        
        sentiment_match = re.search(r'sentiment_score["\s:]+(-?[0-9.]+)', response, re.IGNORECASE)
        confidence_match = re.search(r'confidence["\s:]+([0-9.]+)', response, re.IGNORECASE)
        view_match = re.search(r'view_return["\s:]+(-?[0-9.]+)', response, re.IGNORECASE)
        
        if sentiment_match:
            return {
                'sentiment_score': float(sentiment_match.group(1)),
                'confidence': float(confidence_match.group(1)) if confidence_match else 0.5,
                'view_return': float(view_match.group(1)) if view_match else 0.0,
                'reasoning': 'Pattern-extracted partial response'
            }
        
        logger.warning(f"Could not parse any valid data from LLM response: {response[:300]}")
        return None
    
    def _validate_sentiment_data(self, data: Dict) -> bool:
        """
        Validate that the parsed sentiment data has required fields and valid ranges.
        
        Args:
            data: Parsed sentiment data dictionary
            
        Returns:
            True if valid, False otherwise
        """
        required_fields = ['sentiment_score', 'confidence', 'view_return']
        
        for field in required_fields:
            if field not in data:
                logger.warning(f"Missing required field: {field}")
                return False
        
        # Validate ranges
        if not (-1 <= data['sentiment_score'] <= 1):
            logger.warning(f"sentiment_score out of range: {data['sentiment_score']}")
            return False
        
        if not (0 <= data['confidence'] <= 1):
            logger.warning(f"confidence out of range: {data['confidence']}")
            return False
        
        # Check for zero/empty view_return (the original bug)
        if data.get('view_return', 0) == 0:
            logger.info("view_return is 0, but data structure is valid")
        
        return True
    
    def _rule_based_fallback(
        self,
        asset: str,
        momentum_7d: float,
        momentum_21d: float,
        rsi: float,
        volatility: float
    ) -> Dict:
        """
        Rule-based sentiment calculation as fallback when LLM fails.
        Uses recent price momentum to generate non-zero views for Black-Litterman.
        
        Args:
            asset: Asset symbol
            momentum_7d: 7-day price momentum
            momentum_21d: 21-day price momentum
            rsi: Relative Strength Index
            volatility: Price volatility
            
        Returns:
            Dictionary with sentiment data
        """
        # Combine momentum signals with weights
        # Recent momentum gets higher weight
        momentum_signal = 0.6 * momentum_7d + 0.4 * momentum_21d
        
        # RSI signal (overbought > 70, oversold < 30)
        if rsi > 70:
            rsi_signal = -0.3  # Overbought, expect pullback
        elif rsi < 30:
            rsi_signal = 0.3  # Oversold, expect bounce
        else:
            rsi_signal = 0.0
        
        # Volatility adjustment (high vol = lower confidence)
        vol_adjustment = min(1.0, 0.05 / (volatility + 0.01))
        
        # Combined sentiment score
        sentiment_score = np.clip(momentum_signal + rsi_signal, -1, 1)
        
        # View return based on momentum (capped to realistic values)
        view_return = np.clip(momentum_signal * 2, -0.3, 0.3)
        
        # Confidence based on signal agreement and volatility
        signal_agreement = 1.0 if (momentum_7d * momentum_21d > 0) else 0.5
        confidence = np.clip(signal_agreement * vol_adjustment, 0.2, 0.8)
        
        reasoning = (
            f"Rule-based fallback: 7d mom={momentum_7d:.2%}, 21d mom={momentum_21d:.2%}, "
            f"RSI={rsi:.1f}, vol={volatility:.2%}"
        )
        
        logger.info(f"{asset}: {reasoning} -> sentiment={sentiment_score:.3f}, view={view_return:.3f}")
        
        return {
            'sentiment_score': float(sentiment_score),
            'confidence': float(confidence),
            'view_return': float(view_return),
            'reasoning': reasoning
        }
    
    def _calculate_momentum(self, prices: pd.Series, period: int) -> float:
        """Calculate price momentum over a period."""
        if len(prices) < period:
            return 0.0
        return (prices.iloc[-1] / prices.iloc[-period] - 1)
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate Relative Strength Index."""
        if len(prices) < period + 1:
            return 50.0  # Neutral
        
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / (loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi.iloc[-1])
    
    def generate_views_for_portfolio(
        self,
        prices: pd.DataFrame,
        assets: List[str],
        news_data: Optional[Dict[str, List[str]]] = None,
        max_views: int = 5,
        q_magnitude_cap: float = 0.1
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Generate view vectors for Black-Litterman model across portfolio assets.
        
        Args:
            prices: DataFrame of asset prices
            assets: List of asset symbols to analyze
            news_data: Optional dict mapping assets to news headlines
            max_views: Maximum number of views to generate
            q_magnitude_cap: Cap on view magnitude
            
        Returns:
            Tuple of (Q vector, P matrix indices, asset names for views)
        """
        views = []
        confidences = []
        view_assets = []
        
        for asset in assets:
            if asset not in prices.columns:
                continue
                
            price_data = prices[asset]
            news = news_data.get(asset, []) if news_data else None
            
            result = self.analyze_sentiment(asset, price_data, news_headlines=news)
            
            view_return = result.get('view_return', 0.0)
            confidence = result.get('confidence', 0.5)
            
            # Only include views with meaningful magnitude
            if abs(view_return) > 0.01:  # At least 1% expected move
                # Cap the magnitude
                view_return = np.clip(view_return, -q_magnitude_cap, q_magnitude_cap)
                
                views.append(view_return)
                confidences.append(confidence)
                view_assets.append(asset)
                
                logger.info(f"{asset}: view_return={view_return:.4f}, confidence={confidence:.3f}")
        
        # Limit to max_views, prioritizing by confidence
        if len(views) > max_views:
            sorted_indices = np.argsort(confidences)[::-1][:max_views]
            views = [views[i] for i in sorted_indices]
            confidences = [confidences[i] for i in sorted_indices]
            view_assets = [view_assets[i] for i in sorted_indices]
        
        Q = np.array(views) if views else np.zeros(min(max_views, len(assets)))
        P_indices = np.arange(len(Q))  # Identity view matrix (each view on one asset)
        
        logger.info(f"Generated {len(Q)} views with Q magnitude cap={q_magnitude_cap}. Q={Q}")
        
        return Q, P_indices, view_assets
    
    def close(self):
        """Clean up resources."""
        self.client = None


def get_sentiment_views(
    prices: pd.DataFrame,
    assets: List[str],
    api_key: Optional[str] = None,
    max_views: int = 5,
    q_cap: float = 0.1
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Convenience function to get sentiment views for a portfolio.
    
    Args:
        prices: DataFrame of asset prices
        assets: List of asset symbols
        api_key: Groq API key
        max_views: Maximum views to generate
        q_cap: Cap on view magnitude
        
    Returns:
        Tuple of (Q vector, P indices, view assets)
    """
    analyzer = AISentimentAnalyzer(api_key=api_key)
    try:
        return analyzer.generate_views_for_portfolio(prices, assets, max_views=max_views, q_magnitude_cap=q_cap)
    finally:
        analyzer.close()


if __name__ == "__main__":
    # Example usage with mock data
    np.random.seed(42)
    
    # Create sample price data
    dates = pd.date_range('2024-01-01', periods=60, freq='D')
    assets = ['BTC', 'ETH', 'SOL', 'ADA', 'DOT']
    
    prices = pd.DataFrame(
        np.random.randn(60, 5).cumsum() + 100,
        index=dates,
        columns=assets
    )
    
    print("\n=== Testing AI Sentiment Analyzer ===")
    
    # Test with mock API (will use fallback)
    analyzer = AISentimentAnalyzer(api_key="mock_key")
    
    for asset in assets[:3]:
        result = analyzer.analyze_sentiment(asset, prices[asset])
        print(f"\n{asset}:")
        print(f"  Sentiment: {result['sentiment_score']:.3f}")
        print(f"  Confidence: {result['confidence']:.3f}")
        print(f"  View Return: {result['view_return']:.3f}")
        print(f"  Reasoning: {result['reasoning']}")
    
    print("\n=== Testing Portfolio Views Generation ===")
    Q, P_idx, view_assets = analyzer.generate_views_for_portfolio(
        prices, assets, max_views=5, q_magnitude_cap=0.1
    )
    
    print(f"Q vector: {Q}")
    print(f"View assets: {view_assets}")
    
    analyzer.close()
