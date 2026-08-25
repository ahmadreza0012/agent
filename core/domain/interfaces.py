"""
Abstract interfaces for the trading system.

These interfaces define contracts that concrete implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import pandas as pd


class DataProvider(ABC):
    """
    Abstract interface for market data providers.
    
    Implementations should provide market data from various sources
    (exchanges, aggregators, etc.) with a consistent interface.
    """
    
    @abstractmethod
    def get_ohlcv(
        self, 
        symbol: str, 
        timeframe: str, 
        start: str, 
        end: str
    ) -> pd.DataFrame:
        """
        Get OHLCV (Open, High, Low, Close, Volume) data.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframe: Candle timeframe (e.g., '1h', '4h', '1d')
            start: Start date in ISO format
            end: End date in ISO format
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        pass
    
    @abstractmethod
    def get_ticker(self, symbol: str) -> Dict[str, float]:
        """
        Get latest ticker data.
        
        Args:
            symbol: Trading pair symbol
        
        Returns:
            Dictionary with bid, ask, last, volume, etc.
        """
        pass
    
    @abstractmethod
    def get_balance(self, asset: Optional[str] = None) -> Dict[str, float]:
        """
        Get account balance.
        
        Args:
            asset: Specific asset to query (optional)
        
        Returns:
            Dictionary of asset -> balance
        """
        pass


class Strategy(ABC):
    """
    Abstract interface for trading strategies.
    
    All strategy implementations must implement this interface.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return strategy name."""
        pass
    
    @abstractmethod
    def generate_signal(
        self, 
        data: pd.DataFrame, 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a trading signal.
        
        Args:
            data: Historical price data
            **kwargs: Additional parameters
        
        Returns:
            Dictionary with signal information:
            - direction: 1 (long), -1 (short), 0 (neutral)
            - strength: Signal strength (0.0 to 1.0)
            - metadata: Additional information
        """
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Return strategy parameters."""
        pass
    
    @abstractmethod
    def set_parameters(self, params: Dict[str, Any]) -> None:
        """Set strategy parameters."""
        pass


class RiskEngine(ABC):
    """
    Abstract interface for risk management.
    
    Evaluates risk and provides decisions on whether trades should proceed.
    """
    
    @abstractmethod
    def evaluate(self, **kwargs) -> Dict[str, Any]:
        """
        Evaluate risk and return decision.
        
        Args:
            **kwargs: Risk evaluation parameters
        
        Returns:
            Dictionary with:
            - approved: bool - Whether the trade is approved
            - position_size: float - Approved position size
            - risk_level: str - Current risk level
            - reasons: list - Reasons for decision
        """
        pass
    
    @abstractmethod
    def get_risk_metrics(self) -> Dict[str, float]:
        """Get current risk metrics."""
        pass
    
    @abstractmethod
    def update_state(self, **kwargs) -> None:
        """Update risk engine state."""
        pass


class ExchangeAdapter(ABC):
    """
    Abstract interface for exchange integration.
    
    Provides a unified interface for interacting with different exchanges.
    """
    
    @abstractmethod
    def get_balance(self, asset: Optional[str] = None) -> Dict[str, Any]:
        """Get account balance."""
        pass
    
    @abstractmethod
    def create_order(
        self,
        symbol: str,
        side: str,
        type: str,
        amount: float,
        price: Optional[float] = None,
        **kwargs
    ) -> Any:
        """Create a new order."""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an existing order."""
        pass
    
    @abstractmethod
    def get_order(self, order_id: str, symbol: str) -> Any:
        """Get order status."""
        pass
    
    @abstractmethod
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Any]:
        """Get all open orders."""
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Any]:
        """Get all open positions."""
        pass


class PortfolioOptimizer(ABC):
    """
    Abstract interface for portfolio optimization.
    
    Implements portfolio construction and weight allocation algorithms.
    """
    
    @abstractmethod
    def optimize(
        self,
        returns: pd.DataFrame,
        **kwargs
    ) -> Dict[str, float]:
        """
        Optimize portfolio weights.
        
        Args:
            returns: Asset returns DataFrame
            **kwargs: Optimization parameters
        
        Returns:
            Dictionary of asset -> weight
        """
        pass
    
    @abstractmethod
    def get_objective(self) -> str:
        """Return optimization objective."""
        pass


class RegimeDetector(ABC):
    """
    Abstract interface for market regime detection.
    
    Identifies current market conditions (bull, bear, sideways, etc.).
    """
    
    @abstractmethod
    def detect_regime(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect current market regime.
        
        Args:
            data: Market data
        
        Returns:
            Dictionary with regime information:
            - trend: bull/bear/sideways
            - volatility: high/medium/low
            - confidence: float
        """
        pass
    
    @abstractmethod
    def get_regime_history(self) -> List[Dict[str, Any]]:
        """Get historical regime detections."""
        pass
