"""
Risk Metrics Calculation
========================
Calculate various risk metrics for portfolio evaluation.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field


@dataclass
class RiskMetrics:
    """Risk metrics for portfolio evaluation."""
    
    # Exposure metrics
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    cash_weight: float = 0.0
    
    # Position metrics
    max_position: float = 0.0
    max_position_asset: str = ""
    hhi: float = 0.0  # Herfindahl-Hirschman Index
    
    # Volatility metrics
    portfolio_volatility: float = 0.0
    avg_asset_volatility: float = 0.0
    
    # Drawdown metrics
    current_drawdown: float = 0.0
    max_drawdown_historical: float = 0.0
    daily_pnl: float = 0.0
    
    # Correlation metrics
    avg_correlation: float = 0.0
    max_correlation: float = 0.0
    correlation_matrix: Optional[np.ndarray] = None
    
    # Liquidity metrics
    avg_liquidity: float = 0.0
    min_liquidity: float = 0.0
    avg_spread: float = 0.0
    
    # Performance metrics
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    
    # Combined risk score (0-100)
    risk_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'gross_exposure': self.gross_exposure,
            'net_exposure': self.net_exposure,
            'cash_weight': self.cash_weight,
            'max_position': self.max_position,
            'max_position_asset': self.max_position_asset,
            'hhi': self.hhi,
            'portfolio_volatility': self.portfolio_volatility,
            'avg_asset_volatility': self.avg_asset_volatility,
            'current_drawdown': self.current_drawdown,
            'max_drawdown_historical': self.max_drawdown_historical,
            'daily_pnl': self.daily_pnl,
            'avg_correlation': self.avg_correlation,
            'max_correlation': self.max_correlation,
            'avg_liquidity': self.avg_liquidity,
            'min_liquidity': self.min_liquidity,
            'avg_spread': self.avg_spread,
            'total_return': self.total_return,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'risk_score': self.risk_score,
        }


def calculate_risk_metrics(
    portfolio_weights: Dict[str, float],
    asset_returns: pd.DataFrame,
    asset_prices: pd.DataFrame,
    asset_volumes: Optional[Dict[str, float]] = None,
    asset_spreads: Optional[Dict[str, float]] = None,
    lookback: int = 252,
) -> RiskMetrics:
    """
    Calculate risk metrics for a portfolio.
    
    Args:
        portfolio_weights: Dictionary of asset -> weight
        asset_returns: DataFrame of historical returns
        asset_prices: DataFrame of historical prices
        asset_volumes: Dictionary of asset -> average daily volume
        asset_spreads: Dictionary of asset -> current spread
        lookback: Number of periods for rolling calculations
        
    Returns:
        RiskMetrics object
    """
    metrics = RiskMetrics()
    assets = list(portfolio_weights.keys())
    weights = np.array([portfolio_weights.get(a, 0.0) for a in assets])
    cash_weight = 1.0 - sum(weights)
    
    # 1. Exposure metrics
    metrics.gross_exposure = sum(abs(w) for w in weights)
    metrics.net_exposure = sum(weights)
    metrics.cash_weight = cash_weight
    
    # 2. Position metrics
    if len(weights) > 0:
        max_idx = np.argmax(abs(weights))
        metrics.max_position = abs(weights[max_idx])
        metrics.max_position_asset = assets[max_idx] if max_idx < len(assets) else ""
        metrics.hhi = sum(w ** 2 for w in weights)
    
    # 3. Volatility metrics
    if len(asset_returns) >= lookback:
        recent_returns = asset_returns.iloc[-lookback:]
        asset_vols = recent_returns[assets].std().values
        metrics.avg_asset_volatility = np.mean(asset_vols) * np.sqrt(252)
        
        # Portfolio volatility
        if len(weights) > 1:
            cov_matrix = recent_returns[assets].cov().values
            portfolio_vol = np.sqrt(weights @ cov_matrix @ weights.T) * np.sqrt(252)
        else:
            portfolio_vol = asset_vols[0] * np.sqrt(252) if len(asset_vols) > 0 else 0
        metrics.portfolio_volatility = portfolio_vol
    
    # 4. Drawdown metrics
    if len(asset_prices) > 0:
        # Portfolio value (assuming equal weighting for simplicity)
        portfolio_values = (asset_prices[assets].mean(axis=1) * len(assets)).ffill()
        if len(portfolio_values) > 0:
            peak = portfolio_values.expanding().max()
            metrics.current_drawdown = (portfolio_values.iloc[-1] - peak.iloc[-1]) / peak.iloc[-1] if peak.iloc[-1] > 0 else 0
            metrics.max_drawdown_historical = (portfolio_values / peak - 1).min() if len(portfolio_values) > 0 else 0
        
        # Daily PnL
        if len(portfolio_values) > 1:
            metrics.daily_pnl = (portfolio_values.iloc[-1] / portfolio_values.iloc[-2] - 1)
    
    # 5. Correlation metrics
    if len(assets) > 1 and len(asset_returns) >= lookback:
        recent_returns = asset_returns.iloc[-lookback:]
        corr_matrix = recent_returns[assets].corr().values
        metrics.correlation_matrix = corr_matrix
        
        # Average correlation (excluding diagonal)
        n = len(corr_matrix)
        if n > 1:
            upper_tri = corr_matrix[np.triu_indices(n, k=1)]
            metrics.avg_correlation = np.mean(upper_tri) if len(upper_tri) > 0 else 0
            metrics.max_correlation = np.max(upper_tri) if len(upper_tri) > 0 else 0
    
    # 6. Liquidity metrics
    if asset_volumes:
        volumes = [asset_volumes.get(a, 0) for a in assets]
        metrics.avg_liquidity = np.mean(volumes) if volumes else 0
        metrics.min_liquidity = np.min(volumes) if volumes else 0
    
    if asset_spreads:
        spreads = [asset_spreads.get(a, 0) for a in assets]
        metrics.avg_spread = np.mean(spreads) if spreads else 0
    
    # 7. Performance metrics
    if len(asset_returns) >= lookback:
        portfolio_returns = (asset_returns[assets] * weights).sum(axis=1)
        if len(portfolio_returns) > 0:
            metrics.total_return = portfolio_returns.sum()
            # Sharpe ratio (assuming 0 risk-free rate)
            if portfolio_returns.std() > 0:
                metrics.sharpe_ratio = (portfolio_returns.mean() / portfolio_returns.std()) * np.sqrt(252)
            
            # Sortino ratio
            negative_returns = portfolio_returns[portfolio_returns < 0]
            if len(negative_returns) > 0 and negative_returns.std() > 0:
                metrics.sortino_ratio = (portfolio_returns.mean() / negative_returns.std()) * np.sqrt(252)
    
    # 8. Combined risk score (0-100, lower = better)
    risk_factors = []
    if metrics.gross_exposure > 0:
        risk_factors.append(min(metrics.gross_exposure, 2.0) / 2.0 * 20)
    if metrics.max_position > 0:
        risk_factors.append(min(metrics.max_position, 1.0) * 20)
    if metrics.portfolio_volatility > 0:
        risk_factors.append(min(metrics.portfolio_volatility, 1.0) * 20)
    if metrics.current_drawdown < 0:
        risk_factors.append(min(abs(metrics.current_drawdown), 1.0) * 20)
    if metrics.hhi > 0:
        risk_factors.append(min(metrics.hhi, 1.0) * 20)
    
    metrics.risk_score = sum(risk_factors) if risk_factors else 0
    
    return metrics
