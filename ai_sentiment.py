"""
AI Sentiment Module (v2)
-------------------------
Generates market views from REAL news headlines using a free LLM (Groq),
with a transparent, clearly-labeled fallback when no API key / network
is available.

Key fixes vs. v1:
- No longer hardcoded to mock mode from main.py; auto-detects based on
  GROQ_API_KEY availability (can still be forced either way).
- Real mode now actually feeds the LLM real news headlines fetched from
  news_fetcher.NewsFetcher, instead of asking it to guess with no context.
- Adds a simple self-improving confidence mechanism: the module tracks
  whether each past view direction (bullish/bearish) matched the
  subsequent realized return, and adjusts the Black-Litterman confidence
  (omega) up/down accordingly. This is the "self-correcting" feedback
  loop requested -- it is a lightweight, auditable version, not a
  reinforcement-learning agent, and that trade-off is intentional so the
  behavior stays inspectable.
"""

import json
import logging
import os
import re
import time
from collections import deque
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from news_fetcher import NewsFetcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AISentimentAnalyzer:
    """
    Generate market views from real news + LLM sentiment, with a
    self-adjusting confidence track record.
    """

    def __init__(self, api_key: str = None, use_mock: Optional[bool] = None,
                 model: str = "llama-3.1-8b-instant",
                 track_record_len: int = 20):
        """
        Args:
            api_key: Groq API key. Falls back to GROQ_API_KEY env var.
            use_mock: True/False to force a mode, or None to auto-detect
                      (mock is used automatically if no key is available).
            model: Groq model name (free tier).
            track_record_len: how many past views to keep for the
                               self-adjusting confidence mechanism.
        """
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model = model
        # Auto-detect unless explicitly forced by the caller
        self.use_mock = (self.api_key is None) if use_mock is None else use_mock

        self.client = None
        if not self.use_mock:
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
                logger.info(f"Groq client initialized (model={self.model}) - REAL sentiment mode")
            except Exception as e:
                logger.warning(f"Failed to initialize Groq ({e}). Falling back to mock mode.")
                self.use_mock = True
        if self.use_mock:
            logger.warning(
                "AISentimentAnalyzer running in MOCK mode (no GROQ_API_KEY found). "
                "Views will be derived from price momentum only, NOT real news/LLM. "
                "Set the GROQ_API_KEY environment variable to enable real analysis."
            )

        self.news_fetcher = NewsFetcher()
        self.symbol_names = {
            "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana",
            "BNB": "Binance Coin", "XRP": "Ripple",
        }

        # Self-improving track record: per symbol, deque of
        # (predicted_direction, realized_direction) used to scale confidence.
        self._track_record: Dict[str, deque] = {}
        self._track_record_len = track_record_len

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """
        Robustly extract the base ticker (e.g. 'BTC') from whatever symbol
        format is passed in. Handles 'BTC/USDT', 'BTCUSDT', and -- important
        integration fix -- 'BTC_' (the trailing-underscore form produced by
        data_fetcher.py's align_data(), whose naive
        symbol.replace('/', '_').replace('USDT', '') leaves a stray '_').
        A plain .replace("USDT", "").replace("/", "") does NOT strip that
        trailing underscore, which silently broke news/keyword matching.
        """
        cleaned = symbol.upper().replace("USDT", "").replace("/", "")
        return re.sub(r"[^A-Z]", "", cleaned)

    # ------------------------------------------------------------------
    # Mock mode (price-momentum based) - kept as an explicit, labeled
    # fallback, not disguised as "AI".
    # ------------------------------------------------------------------
    def generate_mock_sentiment(self, prices: pd.DataFrame, window: int = 168) -> pd.DataFrame:
        logger.info("[MOCK] Generating momentum-based pseudo-sentiment (not real news/LLM)")
        sentiment_data = {}
        for symbol in prices.columns:
            returns = prices[symbol].pct_change(window)
            sentiment = np.tanh(returns * 10)
            ma = prices[symbol].rolling(window=24).mean()
            deviation = (prices[symbol] - ma) / ma
            mean_rev = -np.tanh(deviation * 5) * 0.3
            sentiment_data[symbol] = sentiment + mean_rev
        sentiment_df = pd.DataFrame(sentiment_data, index=prices.index)
        # FIX (found via integration testing): when the lookback window is
        # only as long as `window`, pct_change(window) is NaN on the last
        # row, which silently propagated NaN into Black-Litterman's Q
        # vector and made it fall back to equal-weight without warning.
        n_nan = int(sentiment_df.iloc[-1].isna().sum())
        if n_nan > 0:
            logger.warning(f"{n_nan} symbol(s) had NaN mock sentiment (lookback shorter than "
                            f"{window}h window) - filled with 0 (neutral) instead of propagating NaN")
        return sentiment_df.fillna(0.0).clip(-1, 1)

    # ------------------------------------------------------------------
    # Real mode: news + LLM
    # ------------------------------------------------------------------
    def generate_real_sentiment(self, symbol: str, headlines: List[str] = None) -> float:
        """
        Score sentiment for one symbol using real news headlines + Groq LLM.
        Falls back to a transparent keyword score if the LLM call fails.
        """
        base_symbol = self._normalize_symbol(symbol)
        if headlines is None:
            headlines = self.news_fetcher.get_headlines_for_symbol(base_symbol)

        if not headlines:
            logger.info(f"No recent headlines found for {symbol}; returning neutral sentiment")
            return 0.0

        if not self.api_key or self.client is None:
            score = NewsFetcher.keyword_fallback_score(headlines)
            logger.info(f"[fallback keyword score] {symbol}: {score:.3f}")
            return score

        name = self.symbol_names.get(base_symbol, symbol)
        headline_block = "\n".join(f"- {h}" for h in headlines)
        prompt = f"""You are a crypto market analyst. Based ONLY on the following
real recent news headlines about {name} ({symbol}), score the current market
sentiment.

Headlines:
{headline_block}

Return ONLY a single number between -1 (very bearish) and 1 (very bullish).
No explanation, just the number.
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.2,
            )
            sentiment_text = response.choices[0].message.content.strip()
            sentiment = float(sentiment_text.split()[0])
            sentiment = float(np.clip(sentiment, -1, 1))
            logger.info(f"[LLM] Real sentiment for {symbol}: {sentiment:.3f} (from {len(headlines)} headlines)")
            return sentiment
        except Exception as e:
            logger.error(f"LLM sentiment call failed for {symbol}: {e}. Using keyword fallback.")
            return NewsFetcher.keyword_fallback_score(headlines)

    # ------------------------------------------------------------------
    # Self-improving confidence tracking
    # ------------------------------------------------------------------
    def record_outcome(self, symbol: str, predicted_sentiment: float, realized_return: float):
        """
        Feed back what actually happened after a view was made, so future
        confidence in this symbol's views can adapt. Call this once you
        know the realized return for the period the view covered.
        """
        pred_dir = np.sign(predicted_sentiment)
        real_dir = np.sign(realized_return)
        correct = 1.0 if pred_dir == real_dir and pred_dir != 0 else 0.0
        self._track_record.setdefault(symbol, deque(maxlen=self._track_record_len)).append(correct)

    def get_symbol_confidence(self, symbol: str, base_confidence: float = 0.05) -> float:
        """
        Self-adjusting uncertainty (lower = more confident) per symbol,
        based on recent hit-rate of the AI's directional calls.
        No track record yet -> use base_confidence (neutral prior).
        """
        record = self._track_record.get(symbol)
        if not record or len(record) < 5:
            return base_confidence
        hit_rate = float(np.mean(record))
        # hit_rate 0.5 (coin-flip) -> confidence unchanged
        # hit_rate 1.0 -> confidence tightened (lower omega, trust the view more)
        # hit_rate 0.0 -> confidence loosened a lot (don't trust the view)
        adjustment = 1.0 + (0.5 - hit_rate) * 2.0  # ranges roughly [0, 2]
        adjustment = float(np.clip(adjustment, 0.2, 3.0))
        return base_confidence * adjustment

    # ------------------------------------------------------------------
    # Black-Litterman view generation
    # ------------------------------------------------------------------
    def generate_views(self, prices: pd.DataFrame, expected_returns: np.ndarray,
                        symbols: List[str]) -> Tuple[np.ndarray, np.ndarray]:
        logger.info(f"Generating Black-Litterman views (mode={'MOCK' if self.use_mock else 'REAL news+LLM'})")

        # Rate limiting cache: track which symbols have already been processed
        # in this trading cycle to avoid duplicate Groq calls
        if not hasattr(self, '_sentiment_cache'):
            self._sentiment_cache = {}
        
        if self.use_mock:
            sentiment = self.generate_mock_sentiment(prices)
            latest_sentiment = sentiment.iloc[-1].values
        else:
            all_headlines = self.news_fetcher.fetch_all()
            latest_sentiment = []
            
            for sym in symbols:
                # Check cache first - if we've already analyzed this symbol in this cycle, reuse
                if sym in self._sentiment_cache:
                    logger.info(f"[CACHE HIT] Reusing cached sentiment for {sym}")
                    latest_sentiment.append(self._sentiment_cache[sym])
                    continue
                
                # Generate real sentiment with rate limiting
                sentiment_score = self.generate_real_sentiment(
                    sym, self.news_fetcher.get_headlines_for_symbol(
                        self._normalize_symbol(sym), all_headlines))
                
                # Cache the result for this symbol
                self._sentiment_cache[sym] = sentiment_score
                latest_sentiment.append(sentiment_score)
                
                # Add rate limiting delay between Groq API calls to prevent 429 errors
                # This is critical when processing multiple symbols (BTC, ETH, XRP, etc.)
                # as each one makes a separate Groq call
                time.sleep(1.5)  # 1.5 second delay between consecutive API calls
            
            latest_sentiment = np.array(latest_sentiment)

        n_assets = len(symbols)
        P = np.eye(n_assets)
        confidence = 0.5
        latest_sentiment = np.nan_to_num(latest_sentiment, nan=0.0)  # safety net, see fix above
        Q = latest_sentiment * confidence * np.abs(expected_returns)
        logger.info(f"Generated {n_assets} views. Q={Q}")
        return P, Q

    def get_confidence_matrix(self, n_assets: int, symbols: List[str] = None,
                               base_confidence: float = 0.05) -> np.ndarray:
        """
        Uncertainty matrix (Omega) for Black-Litterman views.
        If symbols are given, uses the self-adjusting per-symbol confidence
        from record_outcome(); otherwise uses a flat base_confidence.
        """
        if symbols is not None and len(symbols) == n_assets:
            diag = [self.get_symbol_confidence(s, base_confidence) for s in symbols]
        else:
            diag = [base_confidence] * n_assets
        return np.diag(diag)


def main():
    """Test sentiment analyzer (mock mode works offline)."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=200, freq="h")
    prices = pd.DataFrame(
        np.random.randn(200, 5).cumsum() + 100,
        index=dates, columns=["BTC", "ETH", "SOL", "BNB", "XRP"],
    )

    analyzer = AISentimentAnalyzer()  # auto-detects mock vs real
    sentiment = analyzer.generate_mock_sentiment(prices)
    print("Latest mock sentiment:\n", sentiment.iloc[-1])

    expected_returns = np.array([0.001] * 5)
    symbols = ["BTC", "ETH", "SOL", "BNB", "XRP"]
    P, Q = analyzer.generate_views(prices, expected_returns, symbols)
    print("\nP shape:", P.shape, "Q:", Q)

    # demo self-adjusting confidence
    analyzer.record_outcome("BTC", predicted_sentiment=0.5, realized_return=0.02)
    analyzer.record_outcome("BTC", predicted_sentiment=0.3, realized_return=-0.01)
    print("\nBTC confidence after 2 outcomes:", analyzer.get_symbol_confidence("BTC"))


if __name__ == "__main__":
    main()
