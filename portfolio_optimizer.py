"""
Portfolio Optimizer Module for Cryptocurrency Algorithmic Trading
Implements MVO, CVaR, Black-Litterman, and Risk Parity strategies with Ledoit-Wolf shrinkage.
"""

import numpy as np
import pandas as pd
import cvxpy as cp
from typing import Dict, List, Optional, Tuple
from sklearn.covariance import LedoitWolf
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PortfolioOptimizer:
    """
    Portfolio optimization with multiple strategies.
    Uses Ledoit-Wolf shrinkage for stable covariance estimation.
    """
    
    def __init__(self, risk_free_rate: float = 0.02):
        """
        Initialize the optimizer.
        
        Args:
            risk_free_rate: Annual risk-free rate (default: 2%)
        """
        self.risk_free_rate = risk_free_rate
        self.daily_rf_rate = risk_free_rate / 252
        
    def compute_returns(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Compute log returns from price data.
        
        Args:
            prices: DataFrame of asset prices
            
        Returns:
            DataFrame of log returns
        """
        return np.log(prices / prices.shift(1)).dropna()
    
    def ledoit_wolf_covariance(self, returns: pd.DataFrame) -> np.ndarray:
        """
        Compute Ledoit-Wolf shrunk covariance matrix for stability.
        
        This is CRITICAL for crypto portfolios where standard covariance
        matrices are often ill-conditioned or non-invertible.
        
        Args:
            returns: DataFrame of asset returns
            
        Returns:
            Shrunk covariance matrix (numpy array)
        """
        # Remove any NaN values
        returns_clean = returns.dropna()
        
        if len(returns_clean) < 2:
            logger.warning("Insufficient data for covariance estimation")
            # Return identity matrix scaled by variance as fallback
            n_assets = returns.shape[1]
            variances = returns_clean.var().values if len(returns_clean) > 0 else np.ones(n_assets)
            return np.diag(variances)
        
        try:
            # Fit Ledoit-Wolf estimator
            lw_model = LedoitWolf(assume_centered=False)
            lw_model.fit(returns_clean.values)
            cov_matrix = lw_model.covariance_
            
            # Ensure positive definiteness
            min_eig = np.min(np.linalg.eigvalsh(cov_matrix))
            if min_eig <= 0:
                # Add small regularization to ensure positive definiteness
                reg_value = abs(min_eig) + 1e-8
                cov_matrix += reg_value * np.eye(cov_matrix.shape[0])
                logger.info(f"Added regularization ({reg_value:.2e}) to ensure positive definiteness")
            
            logger.info(f"Ledoit-Wolf covariance computed successfully. Condition number: {np.linalg.cond(cov_matrix):.2f}")
            return cov_matrix
            
        except Exception as e:
            logger.error(f"Ledoit-Wolf failed: {e}. Using diagonal covariance as fallback.")
            # Fallback to diagonal covariance
            variances = np.diag(returns_clean.var().values)
            return variances + 1e-6 * np.eye(len(returns_clean.columns))
    
    def mean_variance_optimization(
        self,
        returns: pd.DataFrame,
        target_return: Optional[float] = None,
        max_volatility: Optional[float] = None,
        min_weight: float = 0.0,
        max_weight: float = 1.0,
        allow_short: bool = False
    ) -> Dict[str, np.ndarray]:
        """
        Mean-Variance Optimization (MVO) with Ledoit-Wolf covariance.
        
        Args:
            returns: DataFrame of asset returns
            target_return: Target portfolio return (for efficient frontier)
            max_volatility: Maximum allowed portfolio volatility
            min_weight: Minimum weight per asset
            max_weight: Maximum weight per asset
            allow_short: Allow short selling
            
        Returns:
            Dictionary with weights, expected_return, volatility, sharpe_ratio
        """
        n_assets = returns.shape[1]
        assets = returns.columns.tolist()
        
        # Use Ledoit-Wolf for stable covariance
        cov_matrix = self.ledoit_wolf_covariance(returns)
        mu = returns.mean().values * 252  # Annualized returns
        
        # Decision variables
        w = cp.Variable(n_assets)
        
        # Portfolio metrics
        portfolio_return = mu @ w
        portfolio_volatility = cp.sqrt(cp.quad_form(w, cov_matrix) * 252)  # Annualized
        sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_volatility
        
        # Constraints
        constraints = [
            cp.sum(w) == 1.0,
        ]
        
        if not allow_short:
            constraints.append(w >= min_weight)
        else:
            constraints.append(w >= -max_weight)
            
        constraints.append(w <= max_weight)
        
        if target_return is not None:
            constraints.append(portfolio_return >= target_return)
            
        if max_volatility is not None:
            constraints.append(portfolio_volatility <= max_volatility)
        
        # Maximize Sharpe ratio
        problem = cp.Problem(cp.Maximize(sharpe_ratio), constraints)
        
        try:
            problem.solve(solver=cp.SCS, verbose=False, max_iters=5000)
            
            if problem.status not in ['optimal', 'optimal_inaccurate']:
                logger.warning(f"MVO solver status: {problem.status}. Trying alternative approach...")
                # Try minimizing volatility instead
                problem = cp.Problem(cp.Minimize(portfolio_volatility), constraints)
                problem.solve(solver=cp.SCS, verbose=False)
            
            weights = w.value
            
            # Handle numerical issues
            if weights is None:
                logger.warning("MVO returned None weights. Using equal weights.")
                weights = np.ones(n_assets) / n_assets
            
            # Normalize weights
            weights = weights / np.sum(weights)
            
            result = {
                'weights': weights,
                'assets': assets,
                'expected_return': float(mu @ weights),
                'volatility': float(np.sqrt(weights @ cov_matrix @ weights) * np.sqrt(252)),
                'sharpe_ratio': float((mu @ weights - self.risk_free_rate) / 
                                     (np.sqrt(weights @ cov_matrix @ weights) * np.sqrt(252))),
                'cov_matrix': cov_matrix
            }
            
            logger.info(f"MVO completed. Sharpe: {result['sharpe_ratio']:.3f}, Vol: {result['volatility']:.3f}")
            return result
            
        except Exception as e:
            logger.error(f"MVO failed: {e}. Using equal weights as fallback.")
            weights = np.ones(n_assets) / n_assets
            return {
                'weights': weights,
                'assets': assets,
                'expected_return': float(mu @ weights),
                'volatility': float(np.sqrt(weights @ cov_matrix @ weights) * np.sqrt(252)),
                'sharpe_ratio': 0.0,
                'cov_matrix': cov_matrix
            }
    
    def cvar_optimization(
        self,
        returns: pd.DataFrame,
        confidence_level: float = 0.95,
        target_return: Optional[float] = None,
        min_weight: float = 0.0,
        max_weight: float = 1.0
    ) -> Dict[str, np.ndarray]:
        """
        Conditional Value at Risk (CVaR) optimization with Ledoit-Wolf covariance.
        
        Args:
            returns: DataFrame of asset returns
            confidence_level: Confidence level for CVaR (default: 95%)
            target_return: Target portfolio return
            min_weight: Minimum weight per asset
            max_weight: Maximum weight per asset
            
        Returns:
            Dictionary with weights and CVaR metrics
        """
        n_assets = returns.shape[1]
        assets = returns.columns.tolist()
        returns_array = returns.values
        n_scenarios = len(returns_array)
        
        # Use Ledoit-Wolf for covariance (used in constraints)
        cov_matrix = self.ledoit_wolf_covariance(returns)
        
        # Decision variables
        w = cp.Variable(n_assets)
        z = cp.Variable(n_scenarios)  # Loss in each scenario
        VaR = cp.Variable()  # Value at Risk
        
        # Constraints
        constraints = [
            cp.sum(w) == 1.0,
            w >= min_weight,
            w <= max_weight,
            z >= 0,
        ]
        
        # CVaR constraints: z_i >= -w'r_i - VaR
        for i in range(n_scenarios):
            constraints.append(z[i] >= -returns_array[i] @ w - VaR)
        
        if target_return is not None:
            mu = returns.mean().values * 252
            constraints.append(mu @ w >= target_return)
        
        # Minimize CVaR
        alpha = 1 - confidence_level
        objective = VaR + (1 / (alpha * n_scenarios)) * cp.sum(z)
        
        problem = cp.Problem(cp.Minimize(objective), constraints)
        
        try:
            problem.solve(solver=cp.SCS, verbose=False)
            
            if problem.status not in ['optimal', 'optimal_inaccurate']:
                logger.warning(f"CVaR solver status: {problem.status}")
            
            weights = w.value
            if weights is None:
                weights = np.ones(n_assets) / n_assets
            
            weights = weights / np.sum(weights)
            
            # Calculate CVaR
            portfolio_returns = returns_array @ weights
            var_threshold = np.percentile(portfolio_returns, (1 - confidence_level) * 100)
            cvar = -np.mean(portfolio_returns[portfolio_returns <= var_threshold])
            
            result = {
                'weights': weights,
                'assets': assets,
                'cvar': float(cvar),
                'var': float(-var_threshold),
                'cov_matrix': cov_matrix
            }
            
            logger.info(f"CVaR optimization completed. CVaR: {result['cvar']:.4f}")
            return result
            
        except Exception as e:
            logger.error(f"CVaR optimization failed: {e}. Using equal weights.")
            weights = np.ones(n_assets) / n_assets
            return {
                'weights': weights,
                'assets': assets,
                'cvar': 0.0,
                'var': 0.0,
                'cov_matrix': cov_matrix
            }
    
    def black_litterman(
        self,
        returns: pd.DataFrame,
        views: np.ndarray,
        view_confidences: Optional[np.ndarray] = None,
        tau: float = 0.05,
        risk_aversion: float = 2.5
    ) -> Dict[str, np.ndarray]:
        """
        Black-Litterman model with Ledoit-Wolf covariance.
        
        Args:
            returns: DataFrame of asset returns
            views: View matrix Q (expected returns on views)
            view_confidences: Confidence in each view (omega diagonal)
            tau: Scaling factor for prior uncertainty
            risk_aversion: Risk aversion coefficient
            
        Returns:
            Dictionary with posterior weights and expected returns
        """
        n_assets = returns.shape[1]
        assets = returns.columns.tolist()
        
        # Use Ledoit-Wolf for stable covariance (CRITICAL)
        cov_matrix = self.ledoit_wolf_covariance(returns)
        
        # Market equilibrium returns (implied by market cap or equal weight)
        market_weights = np.ones(n_assets) / n_assets
        pi = risk_aversion * cov_matrix @ market_weights  # Implied equilibrium returns
        
        # Number of views
        k = len(views)
        
        # View matrix P (identity if not specified - each view is on one asset)
        P = np.eye(k, n_assets)
        
        # Omega - uncertainty of views (diagonal matrix)
        if view_confidences is None:
            view_confidences = np.ones(k) * 0.5  # Default 50% confidence
        
        # Omega = diag(P * tau * Sigma * P') scaled by confidence
        omega_diag = np.diag(P @ (tau * cov_matrix) @ P.T) / view_confidences
        omega = np.diag(omega_diag)
        
        try:
            # Black-Litterman formula
            # Posterior expected returns
            tau_sigma = tau * cov_matrix
            
            # M = [(tau * Sigma)^-1 + P' * Omega^-1 * P]^-1
            M = np.linalg.inv(np.linalg.inv(tau_sigma) + P.T @ np.linalg.inv(omega) @ P)
            
            # E[R] = M * [(tau * Sigma)^-1 * pi + P' * Omega^-1 * Q]
            posterior_returns = M @ (np.linalg.inv(tau_sigma) @ pi + P.T @ np.linalg.inv(omega) @ views)
            
            # Posterior covariance
            posterior_cov = cov_matrix + M
            
            # Optimal weights
            weights = np.linalg.inv(risk_aversion * posterior_cov) @ posterior_returns
            
            # Normalize weights
            weights = weights / np.sum(weights)
            
            # Ensure no negative weights for long-only
            weights = np.maximum(weights, 0)
            weights = weights / np.sum(weights)
            
            result = {
                'weights': weights,
                'assets': assets,
                'posterior_returns': posterior_returns,
                'prior_returns': pi,
                'posterior_cov': posterior_cov,
                'views_applied': views
            }
            
            logger.info(f"Black-Litterman completed. Views: {views}, Weights sum: {np.sum(weights):.4f}")
            return result
            
        except np.linalg.LinAlgError as e:
            logger.error(f"Black-Litterman matrix inversion failed: {e}. Using MVO fallback.")
            return self.mean_variance_optimization(returns)
        except Exception as e:
            logger.error(f"Black-Litterman failed: {e}. Using equal weights.")
            weights = np.ones(n_assets) / n_assets
            return {
                'weights': weights,
                'assets': assets,
                'posterior_returns': pi,
                'prior_returns': pi,
                'posterior_cov': cov_matrix,
                'views_applied': views
            }
    
    def risk_parity(
        self,
        returns: pd.DataFrame,
        budget: Optional[np.ndarray] = None,
        min_weight: float = 0.0,
        max_weight: float = 1.0
    ) -> Dict[str, np.ndarray]:
        """
        Risk Parity optimization - equal risk contribution from each asset.
        
        Args:
            returns: DataFrame of asset returns
            budget: Risk budget for each asset (default: equal)
            min_weight: Minimum weight per asset
            max_weight: Maximum weight per asset
            
        Returns:
            Dictionary with risk parity weights
        """
        n_assets = returns.shape[1]
        assets = returns.columns.tolist()
        
        # Use Ledoit-Wolf for stable covariance
        cov_matrix = self.ledoit_wolf_covariance(returns)
        
        if budget is None:
            budget = np.ones(n_assets) / n_assets
        
        # Decision variables
        w = cp.Variable(n_assets)
        sigma_p = cp.sqrt(cp.quad_form(w, cov_matrix))
        
        # Risk contribution of each asset
        rc = cp.multiply(w, cov_matrix @ w) / sigma_p
        
        # Objective: minimize sum of squared differences between actual and target risk contributions
        target_rc = cp.multiply(budget, sigma_p)
        objective = cp.Minimize(cp.sum_squares(rc - target_rc))
        
        # Constraints
        constraints = [
            cp.sum(w) == 1.0,
            w >= min_weight,
            w <= max_weight,
            sigma_p >= 1e-8
        ]
        
        problem = cp.Problem(objective, constraints)
        
        try:
            problem.solve(solver=cp.SCS, verbose=False)
            
            if problem.status not in ['optimal', 'optimal_inaccurate']:
                logger.warning(f"Risk Parity solver status: {problem.status}")
            
            weights = w.value
            if weights is None:
                weights = np.ones(n_assets) / n_assets
            
            weights = np.maximum(weights, 0)
            weights = weights / np.sum(weights)
            
            # Calculate actual risk contributions
            sigma_p_val = np.sqrt(weights @ cov_matrix @ weights)
            rc_actual = (weights * (cov_matrix @ weights)) / sigma_p_val
            
            result = {
                'weights': weights,
                'assets': assets,
                'risk_contributions': rc_actual,
                'target_risk_budget': budget,
                'portfolio_volatility': sigma_p_val,
                'cov_matrix': cov_matrix
            }
            
            logger.info(f"Risk Parity completed. Portfolio vol: {sigma_p_val:.4f}")
            return result
            
        except Exception as e:
            logger.error(f"Risk Parity failed: {e}. Using equal weights.")
            weights = np.ones(n_assets) / n_assets
            return {
                'weights': weights,
                'assets': assets,
                'risk_contributions': budget,
                'target_risk_budget': budget,
                'portfolio_volatility': np.sqrt(weights @ cov_matrix @ weights),
                'cov_matrix': cov_matrix
            }
    
    def optimize(
        self,
        returns: pd.DataFrame,
        strategy: str = 'mvo',
        **kwargs
    ) -> Dict[str, np.ndarray]:
        """
        Main optimization interface.
        
        Args:
            returns: DataFrame of asset returns
            strategy: Optimization strategy ('mvo', 'cvar', 'black_litterman', 'risk_parity')
            **kwargs: Strategy-specific arguments
            
        Returns:
            Optimization result dictionary
        """
        logger.info(f"Running {strategy} optimization on {len(returns.columns)} assets")
        
        if strategy == 'mvo':
            return self.mean_variance_optimization(returns, **kwargs)
        elif strategy == 'cvar':
            return self.cvar_optimization(returns, **kwargs)
        elif strategy == 'black_litterman':
            return self.black_litterman(returns, **kwargs)
        elif strategy == 'risk_parity':
            return self.risk_parity(returns, **kwargs)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")


def generate_quantitative_features(prices: pd.DataFrame, lookback: int = 14) -> pd.DataFrame:
    """
    Generate quantitative features for ML models.
    Includes RSI, MACD, and rolling volatility.
    
    Args:
        prices: DataFrame of asset prices
        lookback: Lookback period for indicators
        
    Returns:
        DataFrame with additional feature columns
    """
    features = prices.copy()
    
    for col in prices.columns:
        prefix = col.replace('/', '_').replace(' ', '_')
        
        # Returns
        features[f'{prefix}_return_1d'] = prices[col].pct_change(1)
        features[f'{prefix}_return_{lookback}d'] = prices[col].pct_change(lookback)
        
        # RSI (Relative Strength Index)
        delta = prices[col].diff()
        gain = delta.where(delta > 0, 0).rolling(window=lookback).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=lookback).mean()
        rs = gain / (loss + 1e-10)
        features[f'{prefix}_rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = prices[col].ewm(span=12, adjust=False).mean()
        exp2 = prices[col].ewm(span=26, adjust=False).mean()
        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        features[f'{prefix}_macd'] = macd_line - signal_line  # MACD histogram
        features[f'{prefix}_macd_line'] = macd_line
        features[f'{prefix}_macd_signal'] = signal_line
        
        # Rolling Volatility (ATR-like using standard deviation)
        features[f'{prefix}_volatility_{lookback}d'] = prices[col].pct_change().rolling(lookback).std()
        
        # ATR (Average True Range)
        high = prices[col]  # For single price series, use close as proxy
        low = prices[col]
        close = prices[col]
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        features[f'{prefix}_atr'] = tr.rolling(lookback).mean()
        
        # Moving averages
        features[f'{prefix}_ma_7'] = prices[col].rolling(7).mean()
        features[f'{prefix}_ma_21'] = prices[col].rolling(21).mean()
        features[f'{prefix}_ma_ratio'] = features[f'{prefix}_ma_7'] / features[f'{prefix}_ma_21']
        
        # Momentum
        features[f'{prefix}_momentum_7'] = prices[col] / prices[col].shift(7) - 1
        features[f'{prefix}_momentum_21'] = prices[col] / prices[col].shift(21) - 1
    
    return features


if __name__ == "__main__":
    # Example usage
    np.random.seed(42)
    
    # Create sample price data
    dates = pd.date_range('2023-01-01', periods=252, freq='D')
    n_assets = 5
    
    # Simulate correlated returns
    base_returns = np.random.randn(252, n_assets) * 0.02
    correlation_matrix = np.ones((n_assets, n_assets)) * 0.5
    np.fill_diagonal(correlation_matrix, 1)
    cholesky = np.linalg.cholesky(correlation_matrix)
    correlated_returns = base_returns @ cholesky
    
    prices = pd.DataFrame(
        100 * np.cumprod(1 + correlated_returns),
        index=dates,
        columns=[f'Asset_{i}' for i in range(n_assets)]
    )
    
    optimizer = PortfolioOptimizer()
    returns = optimizer.compute_returns(prices)
    
    print("\n=== Testing Ledoit-Wolf Covariance ===")
    cov = optimizer.ledoit_wolf_covariance(returns)
    print(f"Covariance shape: {cov.shape}")
    print(f"Condition number: {np.linalg.cond(cov):.2f}")
    
    print("\n=== Testing MVO ===")
    mvo_result = optimizer.mean_variance_optimization(returns)
    print(f"Weights: {mvo_result['weights']}")
    print(f"Sharpe Ratio: {mvo_result['sharpe_ratio']:.3f}")
    
    print("\n=== Testing Risk Parity ===")
    rp_result = optimizer.risk_parity(returns)
    print(f"Weights: {rp_result['weights']}")
    print(f"Risk Contributions: {rp_result['risk_contributions']}")
    
    print("\n=== Testing Black-Litterman ===")
    views = np.array([0.05, 0.03])  # Expected returns on 2 views
    bl_result = optimizer.black_litterman(returns, views=views)
    print(f"Weights: {bl_result['weights']}")
    
    print("\n=== Testing Quantitative Features ===")
    features = generate_quantitative_features(prices)
    print(f"Features shape: {features.shape}")
    print(f"Feature columns: {list(features.columns)}")
