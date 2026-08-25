"""
Return calculation utilities for the trading system.

This module provides standardized return calculations with proper
timeframe handling and annualization.
"""

import numpy as np
import pandas as pd
from typing import Union, Optional
from .timeframe import detect_frequency, FREQUENCY_SPECS


def simple_returns(prices: Union[pd.Series, pd.DataFrame]) -> Union[pd.Series, pd.DataFrame]:
    """
    Calculate simple returns from prices.
    
    Args:
        prices: Price series or dataframe
        
    Returns:
        Simple returns (pct_change)
    """
    if isinstance(prices, pd.Series):
        return prices.pct_change().dropna()
    elif isinstance(prices, pd.DataFrame):
        return prices.pct_change().dropna()
    else:
        raise TypeError(f"Expected Series or DataFrame, got {type(prices)}")


def log_returns(prices: Union[pd.Series, pd.DataFrame]) -> Union[pd.Series, pd.DataFrame]:
    """
    Calculate log returns from prices.
    
    Args:
        prices: Price series or dataframe
        
    Returns:
        Log returns (diff of log prices)
    """
    if isinstance(prices, pd.Series):
        return np.log(prices).diff().dropna()
    elif isinstance(prices, pd.DataFrame):
        return np.log(prices).diff().dropna()
    else:
        raise TypeError(f"Expected Series or DataFrame, got {type(prices)}")


def cumulative_returns(returns: Union[pd.Series, pd.DataFrame]) -> Union[pd.Series, pd.DataFrame]:
    """
    Calculate cumulative returns from periodic returns.
    
    Args:
        returns: Periodic returns series or dataframe
        
    Returns:
        Cumulative returns
    """
    if isinstance(returns, pd.Series):
        return (1 + returns).cumprod() - 1
    elif isinstance(returns, pd.DataFrame):
        return (1 + returns).cumprod() - 1
    else:
        raise TypeError(f"Expected Series or DataFrame, got {type(returns)}")


def portfolio_returns(
    returns: pd.DataFrame,
    weights: Union[pd.Series, np.ndarray]
) -> pd.Series:
    """
    Calculate portfolio returns from asset returns and weights.
    
    Args:
        returns: Asset returns DataFrame (time x assets)
        weights: Portfolio weights (assets,)
        
    Returns:
        Portfolio returns series
    """
    if isinstance(weights, pd.Series):
        # Align weights with columns
        weights = weights.reindex(returns.columns).fillna(0)
        return returns.dot(weights)
    elif isinstance(weights, np.ndarray):
        return pd.Series(returns.values @ weights, index=returns.index)
    else:
        raise TypeError(f"Expected Series or ndarray, got {type(weights)}")


def annualized_returns(
    returns: pd.Series,
    freq: Optional[str] = None
) -> float:
    """
    Calculate annualized return from periodic returns.
    
    Args:
        returns: Periodic returns series
        freq: Frequency string or FrequencySpec. Auto-detected if None.
        
    Returns:
        Annualized return as a decimal (e.g., 0.15 for 15%)
    """
    if freq is None:
        freq = detect_frequency(returns)
    
    # If freq is a FrequencySpec, use it directly
    if isinstance(freq, type(FREQUENCY_SPECS['1d'])):
        spec = freq
        periods_per_year = spec.observations_per_year
    else:
        # Otherwise treat as string key
        spec = FREQUENCY_SPECS.get(freq, FREQUENCY_SPECS['1d'])
        periods_per_year = spec.observations_per_year
    
    # Total cumulative return
    total_return = (1 + returns).prod() - 1
    
    # Number of periods
    n_periods = len(returns)
    
    # Annualize
    if n_periods == 0:
        return 0.0
    
    years = n_periods / periods_per_year
    if years <= 0:
        return 0.0
    
    annualized = (1 + total_return) ** (1 / years) - 1
    return float(annualized)


def sharpe_ratio(
    returns: pd.Series,
    freq: Optional[str] = None,
    risk_free_rate: float = 0.0
) -> float:
    """
    Calculate Sharpe ratio.
    
    Args:
        returns: Periodic returns series
        freq: Frequency string or FrequencySpec. Auto-detected if None.
        risk_free_rate: Annual risk-free rate (decimal)
        
    Returns:
        Annualized Sharpe ratio
    """
    if freq is None:
        freq = detect_frequency(returns)
    
    # If freq is a FrequencySpec, use it directly
    if isinstance(freq, type(FREQUENCY_SPECS['1d'])):
        spec = freq
        periods_per_year = spec.observations_per_year
    else:
        spec = FREQUENCY_SPECS.get(freq, FREQUENCY_SPECS['1d'])
        periods_per_year = spec.observations_per_year
    
    if len(returns) == 0 or returns.std() == 0:
        return 0.0
    
    # Annualize mean and std
    excess_return = returns.mean() - risk_free_rate / periods_per_year
    ann_excess = excess_return * periods_per_year
    ann_std = returns.std() * np.sqrt(periods_per_year)
    
    if ann_std == 0:
        return 0.0
    
    return float(ann_excess / ann_std)


def sortino_ratio(
    returns: pd.Series,
    freq: Optional[str] = None,
    risk_free_rate: float = 0.0,
    target_return: float = 0.0
) -> float:
    """
    Calculate Sortino ratio (downside deviation version).
    
    Args:
        returns: Periodic returns series
        freq: Frequency string or FrequencySpec. Auto-detected if None.
        risk_free_rate: Annual risk-free rate (decimal)
        target_return: Target return (default 0)
        
    Returns:
        Annualized Sortino ratio
    """
    if freq is None:
        freq = detect_frequency(returns)
    
    # If freq is a FrequencySpec, use it directly
    if isinstance(freq, type(FREQUENCY_SPECS['1d'])):
        spec = freq
        periods_per_year = spec.observations_per_year
    else:
        spec = FREQUENCY_SPECS.get(freq, FREQUENCY_SPECS['1d'])
        periods_per_year = spec.observations_per_year
    
    if len(returns) == 0:
        return 0.0
    
    # Downside returns (below target)
    downside = returns[returns < target_return]
    
    if len(downside) == 0:
        # No downside, return high value
        ann_excess = (returns.mean() - risk_free_rate / periods_per_year) * periods_per_year
        return float(ann_excess / 0.0001) if ann_excess > 0 else 0.0
    
    # Downside deviation
    downside_std = np.sqrt(((returns - target_return).clip(upper=0) ** 2).mean())
    ann_downside_std = downside_std * np.sqrt(periods_per_year)
    
    # Annualized excess return
    excess_return = returns.mean() - risk_free_rate / periods_per_year
    ann_excess = excess_return * periods_per_year
    
    if ann_downside_std == 0:
        return 0.0
    
    return float(ann_excess / ann_downside_std)


def calmar_ratio(
    returns: pd.Series,
    freq: Optional[str] = None
) -> float:
    """
    Calculate Calmar ratio (return / max drawdown).
    
    Args:
        returns: Periodic returns series
        freq: Frequency string or FrequencySpec. Auto-detected if None.
        
    Returns:
        Calmar ratio
    """
    ann_ret = annualized_returns(returns, freq)
    
    # Calculate max drawdown
    cum_returns = (1 + returns).cumprod()
    running_max = cum_returns.cummax()
    drawdown = (cum_returns - running_max) / running_max
    max_dd = abs(drawdown.min())
    
    if max_dd == 0:
        return 0.0
    
    return float(ann_ret / max_dd)


def max_drawdown(returns: pd.Series) -> float:
    """
    Calculate maximum drawdown.
    
    Args:
        returns: Periodic returns series
        
    Returns:
        Maximum drawdown as a positive decimal
    """
    cum_returns = (1 + returns).cumprod()
    running_max = cum_returns.cummax()
    drawdown = (cum_returns - running_max) / running_max
    return float(abs(drawdown.min()))


def var_historical(
    returns: pd.Series,
    confidence: float = 0.95
) -> float:
    """
    Calculate historical Value at Risk.
    
    Args:
        returns: Periodic returns series
        confidence: Confidence level (e.g., 0.95 for 95%)
        
    Returns:
        VaR as a positive decimal (loss)
    """
    percentile = (1 - confidence) * 100
    return float(-np.percentile(returns, percentile))


def cvar_historical(
    returns: pd.Series,
    confidence: float = 0.95
) -> float:
    """
    Calculate historical Conditional Value at Risk (Expected Shortfall).
    
    Args:
        returns: Periodic returns series
        confidence: Confidence level (e.g., 0.95 for 95%)
        
    Returns:
        CVaR as a positive decimal (expected loss beyond VaR)
    """
    var = var_historical(returns, confidence)
    tail_returns = returns[returns <= -var]
    if len(tail_returns) == 0:
        return var
    return float(-tail_returns.mean())
