"""
Symbol Mapper

Maps canonical internal symbols (BTC/USDT) to exchange-specific formats.
Ensures consistent symbol handling across data sources.
"""

from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SymbolMapper:
    """
    Maps canonical trading pair symbols to exchange-specific formats.
    
    Canonical format: BASE/QUOTE (e.g., BTC/USDT, ETH/USDT)
    """
    
    # Canonical internal symbols (USDT-oriented)
    CANONICAL_SYMBOLS = [
        'BTC/USDT',
        'ETH/USDT',
        'SOL/USDT',
        'BNB/USDT',
        'XRP/USDT',
    ]
    
    # CoinGecko ID mappings
    COINGECKO_IDS: Dict[str, str] = {
        'BTC/USDT': 'bitcoin',
        'ETH/USDT': 'ethereum',
        'SOL/USDT': 'solana',
        'BNB/USDT': 'binancecoin',
        'XRP/USDT': 'ripple',
    }
    
    # yfinance ticker mappings (USD pairs, not USDT)
    YFINANCE_TICKERS: Dict[str, str] = {
        'BTC/USDT': 'BTC-USD',
        'ETH/USDT': 'ETH-USD',
        'SOL/USDT': 'SOL-USD',
        'BNB/USDT': 'BNB-USD',
        'XRP/USDT': 'XRP-USD',
    }
    
    # Binance/CCXT symbol format
    BINANCE_SYMBOLS: Dict[str, str] = {
        'BTC/USDT': 'BTC/USDT',
        'ETH/USDT': 'ETH/USDT',
        'SOL/USDT': 'SOL/USDT',
        'BNB/USDT': 'BNB/USDT',
        'XRP/USDT': 'XRP/USDT',
    }
    
    # CoinGecko IDs (reverse lookup convenience)
    COINGECKO_TO_CANONICAL: Dict[str, str] = {v: k for k, v in COINGECKO_IDS.items()}
    
    def __init__(self):
        self._custom_mappings: Dict[str, Dict[str, str]] = {}
    
    def to_coingecko_id(self, symbol: str) -> Optional[str]:
        """Convert canonical symbol to CoinGecko coin ID."""
        return self.COINGECKO_IDS.get(symbol)
    
    def to_yfinance_ticker(self, symbol: str) -> Optional[str]:
        """Convert canonical symbol to yfinance ticker."""
        return self.YFINANCE_TICKERS.get(symbol)
    
    def to_binance_symbol(self, symbol: str) -> Optional[str]:
        """Convert canonical symbol to Binance/CCXT format."""
        return self.BINANCE_SYMBOLS.get(symbol)
    
    def from_coingecko_id(self, coin_id: str) -> Optional[str]:
        """Convert CoinGecko coin ID to canonical symbol."""
        return self.COINGECKO_TO_CANONICAL.get(coin_id)
    
    def normalize_symbol(self, symbol: str, source: str = 'canonical') -> str:
        """
        Normalize a symbol from various formats to canonical form.
        
        Args:
            symbol: Input symbol (e.g., 'BTC-USD', 'bitcoin', 'BTCUSDT')
            source: Source format ('yfinance', 'coingecko', 'binance', 'canonical')
            
        Returns:
            Canonical symbol (e.g., 'BTC/USDT') or original if unknown
            
        Note: This is best-effort; explicit mapping tables are preferred.
        """
        if source == 'canonical':
            return symbol
        
        if source == 'yfinance':
            # Reverse lookup for yfinance tickers
            for canonical, ticker in self.YFINANCE_TICKERS.items():
                if ticker == symbol:
                    return canonical
            # Try pattern matching for unknown symbols
            if symbol.endswith('-USD'):
                base = symbol[:-4]
                candidate = f'{base}/USDT'
                if candidate in self.CANONICAL_SYMBOLS:
                    logger.warning(f"Assuming {symbol} ({source}) maps to {candidate}. "
                                  f"Note: USD vs USDT difference not converted.")
                    return candidate
        
        elif source == 'coingecko':
            return self.from_coingecko_id(symbol) or symbol
        
        elif source == 'binance':
            # CCXT/binance format may already be canonical
            if symbol in self.CANONICAL_SYMBOLS:
                return symbol
            # Handle 'BTCUSDT' format
            if symbol.endswith('USDT') and '/' not in symbol:
                base = symbol[:-4]
                candidate = f'{base}/USDT'
                if candidate in self.CANONICAL_SYMBOLS:
                    return candidate
        
        logger.debug(f"Unknown symbol mapping: {symbol} ({source})")
        return symbol
    
    def get_canonical_symbols(self) -> list:
        """Return list of supported canonical symbols."""
        return self.CANONICAL_SYMBOLS.copy()
    
    def add_custom_mapping(self, symbol: str, source: str, mapped_value: str):
        """
        Add custom mapping for non-standard symbols.
        
        Args:
            symbol: Canonical symbol
            source: Data source name ('exchange_x', etc.)
            mapped_value: Source-specific symbol
        """
        if symbol not in self._custom_mappings:
            self._custom_mappings[symbol] = {}
        self._custom_mappings[symbol][source] = mapped_value
        logger.info(f"Added custom mapping: {symbol} -> {mapped_value} ({source})")
    
    def get_custom_mapping(self, symbol: str, source: str) -> Optional[str]:
        """Get custom mapping for a symbol/source pair."""
        return self._custom_mappings.get(symbol, {}).get(source)
