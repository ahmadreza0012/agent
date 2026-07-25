"""
News Fetcher Module
--------------------
Fetches recent crypto news headlines from FREE, no-API-key-required RSS feeds
(CoinDesk, Cointelegraph, CryptoPanic public RSS) and filters them per symbol.

Why RSS instead of a paid news API:
- No signup / API key needed -> truly free and always available
- No rate-limit surprises that would break an automated pipeline
- Good enough signal for sentiment scoring (headlines carry most of the signal)

This module has NO dependency on ccxt/groq, so it can be imported and unit
tested even without network access.
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from urllib.request import urlopen, Request
from xml.etree import ElementTree

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Free, public, no-key-required RSS feeds
RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://cryptopanic.com/news/rss/",
]

# Keyword map so a headline can be attributed to a symbol
SYMBOL_KEYWORDS = {
    "BTC": ["bitcoin", "btc"],
    "ETH": ["ethereum", "eth", "ether "],
    "SOL": ["solana", "sol "],
    "BNB": ["binance coin", "bnb", "binance smart chain"],
    "XRP": ["ripple", "xrp"],
}

# Very small, transparent keyword lexicon used ONLY as a cheap pre-filter /
# fallback when no LLM is available. The real scoring is done by the LLM
# in ai_sentiment.py; this is not meant to be a serious sentiment model.
_POSITIVE_WORDS = ["surge", "rally", "bullish", "soar", "gain", "record high",
                   "approval", "adoption", "partnership", "upgrade", "etf inflow"]
_NEGATIVE_WORDS = ["crash", "plunge", "bearish", "hack", "exploit", "lawsuit",
                    "ban", "sell-off", "selloff", "outflow", "collapse", "fraud"]


class NewsFetcher:
    """Fetches and filters recent crypto news headlines from free RSS feeds."""

    def __init__(self, feeds: List[str] = None, timeout: int = 8):
        self.feeds = feeds or RSS_FEEDS
        self.timeout = timeout

    def _fetch_feed(self, url: str) -> List[Dict]:
        """Fetch and parse a single RSS feed. Returns list of {title, published, link}."""
        items = []
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 (crypto-agent news fetcher)"})
            with urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
            root = ElementTree.fromstring(raw)
            for item in root.iter("item"):
                title_el = item.find("title")
                date_el = item.find("pubDate")
                link_el = item.find("link")
                if title_el is None or not title_el.text:
                    continue
                items.append({
                    "title": title_el.text.strip(),
                    "published": date_el.text.strip() if date_el is not None and date_el.text else None,
                    "link": link_el.text.strip() if link_el is not None and link_el.text else None,
                    "source": url,
                })
        except Exception as e:
            logger.warning(f"Could not fetch/parse feed {url}: {e}")
        return items

    def fetch_all(self) -> List[Dict]:
        """Fetch headlines from all configured feeds."""
        all_items = []
        for url in self.feeds:
            items = self._fetch_feed(url)
            logger.info(f"Fetched {len(items)} headlines from {url}")
            all_items.extend(items)
            time.sleep(0.2)  # be polite
        return all_items

    def get_headlines_for_symbol(self, symbol: str, headlines: List[Dict] = None,
                                  max_items: int = 8) -> List[str]:
        """
        Filter fetched headlines that mention a given symbol (e.g. 'BTC').

        Args:
            symbol: base symbol, e.g. 'BTC', 'ETH'
            headlines: pre-fetched list from fetch_all(); fetched fresh if None
            max_items: max number of matching headlines to return
        """
        if headlines is None:
            headlines = self.fetch_all()

        keywords = SYMBOL_KEYWORDS.get(symbol.upper(), [symbol.lower()])
        matched = []
        for h in headlines:
            title_lower = h["title"].lower()
            if any(kw in title_lower for kw in keywords):
                matched.append(h["title"])
            if len(matched) >= max_items:
                break
        return matched

    @staticmethod
    def keyword_fallback_score(headlines: List[str]) -> float:
        """
        Cheap, transparent, LLM-free sentiment estimate used ONLY when no
        LLM is reachable (e.g. offline / no API key / API failure).
        Returns a score in [-1, 1]. NOT a substitute for real analysis.
        """
        if not headlines:
            return 0.0
        pos, neg = 0, 0
        for h in headlines:
            hl = h.lower()
            pos += sum(1 for w in _POSITIVE_WORDS if w in hl)
            neg += sum(1 for w in _NEGATIVE_WORDS if w in hl)
        total = pos + neg
        if total == 0:
            return 0.0
        return (pos - neg) / total


def main():
    """Manual test (requires network)."""
    fetcher = NewsFetcher()
    headlines = fetcher.fetch_all()
    print(f"Total headlines fetched: {len(headlines)}")
    for sym in SYMBOL_KEYWORDS:
        sym_headlines = fetcher.get_headlines_for_symbol(sym, headlines)
        score = fetcher.keyword_fallback_score(sym_headlines)
        print(f"\n{sym}: {len(sym_headlines)} headlines, keyword_score={score:.2f}")
        for h in sym_headlines[:3]:
            print(f"  - {h}")


if __name__ == "__main__":
    main()
