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
                 model: str = None,
                 track_record_len: int = 20):
        """
        Args:
            api_key: Groq API key. Falls back to GROQ_API_KEY env var.
            use_mock: True/False to force a mode, or None to auto-detect
                      (mock is used automatically if no key is available).
            model: Groq model name. Defaults to 'llama-3.3-70b-versatile'.
                   Can be overridden via GROQ_MODEL env var.
            track_record_len: how many past views to keep for the
                               self-adjusting confidence mechanism.
        """
        # Model selection: arg > env var > default
        if model is None:
            model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.model = model
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
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
    # Dual-signal sentiment generation (Phase 5)
    # ------------------------------------------------------------------
    def generate_per_asset_news_sentiment(self, symbols: List[str], headlines_map: Dict[str, List[str]]) -> Dict[str, float]:
        """
        Generate per-asset news sentiment scores from LLM analysis of headlines.
        This is used ONLY for Black-Litterman views.
        
        Returns dict mapping symbol -> sentiment score in [-1, 1]
        """
        logger.info(f"[Phase 5] Generating per_asset_news_sentiment for {len(symbols)} symbols")
        sentiment_scores = {}
        
        for symbol in symbols:
            base_symbol = self._normalize_symbol(symbol)
            headlines = headlines_map.get(base_symbol, [])
            
            if not headlines:
                logger.info(f"No headlines found for {symbol}, setting neutral per_asset_news_sentiment")
                sentiment_scores[symbol] = 0.0
                continue
            
            # Cap max headlines to avoid LLM context overflow and rate limits
            capped_headlines = headlines[:8]
            
            if not self.api_key or self.client is None:
                # Use keyword fallback on LLM failure
                score = NewsFetcher.keyword_fallback_score(capped_headlines)
                logger.info(f"[fallback keyword score] {symbol}: {score:.3f}")
            else:
                score = self.generate_real_sentiment(symbol, capped_headlines)
            
            # Clip to [-1, 1] range (required by Phase 5)
            score = float(np.clip(score, -1.0, 1.0))
            sentiment_scores[symbol] = score
            logger.info(f"per_asset_news_sentiment[{symbol}] = {score:.3f} (from {len(capped_headlines)} headlines)")
        
        return sentiment_scores
    
    def generate_market_tone_score(self, per_asset_sentiments: Dict[str, float]) -> float:
        """
        Generate market-wide tone score from per-asset sentiments.
        This is used ONLY for strategy weight multipliers.
        
        Market tone = mean of available per-asset sentiment scores
        Named distinctly to avoid confusion with per_asset_news_sentiment
        """
        if not per_asset_sentiments:
            logger.info("No per-asset sentiments available, market_tone_score = 0.0 (neutral)")
            return 0.0
        
        # Simple average of all available asset sentiments
        scores = list(per_asset_sentiments.values())
        market_tone = float(np.mean(scores))
        
        # Clip to [-1, 1] range
        market_tone = float(np.clip(market_tone, -1.0, 1.0))
        
        logger.info(f"market_tone_score = {market_tone:.3f} (mean of {len(scores)} asset sentiments)")
        return market_tone

    def generate_views(self, prices: pd.DataFrame, expected_returns: np.ndarray,
                        symbols: List[str], per_asset_sentiment: Dict[str, float] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate Black-Litterman views with Q magnitude capping (Phase 5 requirement).
        
        Args:
            prices: Price data
            expected_returns: Base expected returns
            symbols: Asset symbols
            per_asset_sentiment: Optional dict of sentiment scores from generate_per_asset_news_sentiment
        
        Returns:
            P (pick matrix), Q (view vector) with capped magnitudes
        """
        logger.info(f"Generating Black-Litterman views (mode={'MOCK' if self.use_mock else 'REAL news+LLM'})")
        
        # Use provided sentiment or fall back to legacy method
        if per_asset_sentiment is None:
            # Legacy path - use mock sentiment from prices
            sentiment = self.generate_mock_sentiment(prices)
            latest_sentiment = sentiment.iloc[-1].values
            n_assets = len(symbols)
            P = np.eye(n_assets)
            confidence = 0.5
            latest_sentiment = np.nan_to_num(latest_sentiment, nan=0.0)
            Q = latest_sentiment * confidence * np.abs(expected_returns)
        else:
            # Phase 5 dual-signal path: use per_asset_news_sentiment for BL views
            n_assets = len(symbols)
            P = np.eye(n_assets)
            
            # Build Q vector from sentiment scores
            Q = np.zeros(n_assets)
            matched_symbols = []
            unmatched_symbols = []
            
            for i, sym in enumerate(symbols):
                # FIX B: Normalize symbol key to match per_asset_sentiment dict keys
                normalized_sym = self._normalize_symbol(sym)
                
                # Try direct lookup first, then normalized lookup
                sentiment = per_asset_sentiment.get(sym, None)
                if sentiment is None:
                    # Try normalized key
                    for key in per_asset_sentiment.keys():
                        if self._normalize_symbol(key) == normalized_sym:
                            sentiment = per_asset_sentiment[key]
                            matched_symbols.append(f"{sym}<-{key}")
                            break
                
                if sentiment is None:
                    sentiment = 0.0
                    unmatched_symbols.append(sym)
                
                # Scale by expected return magnitude but apply hard cap (Phase 5 requirement)
                base_view_magnitude = np.abs(expected_returns[i]) if i < len(expected_returns) else 0.001
                Q[i] = sentiment * base_view_magnitude
            
            # Log matched vs unmatched symbols for debugging
            if matched_symbols:
                logger.info(f"BL views: matched {len(matched_symbols)} symbols: {matched_symbols}")
            if unmatched_symbols:
                logger.warning(f"BL views: {len(unmatched_symbols)} unmatched symbols: {unmatched_symbols}")
            
            # PHASE 5 REQUIREMENT: Cap Q magnitudes to prevent explosion vs prior
            # Limit view magnitudes to reasonable bounds (±10% annual max)
            Q_CAP = 0.10  # Hard cap on view magnitude
            Q = np.clip(Q, -Q_CAP, Q_CAP)
            
            logger.info(f"Generated {n_assets} views with Q magnitude cap={Q_CAP}. Q={Q}")
        
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
