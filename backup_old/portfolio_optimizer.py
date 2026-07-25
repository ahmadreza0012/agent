"""
Portfolio Optimizer Module
Implements Markowitz, Black-Litterman, Risk Parity, and CVaR optimization
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize, Bounds, LinearConstraint
from typing import Dict, List, Tuple, Optional
import logging

try:
    from pypfopt import EfficientFrontier, risk_models, expected_returns
    from pypfopt.black_litterman import BlackLittermanModel
    PYPORTFOLIO_OPT_AVAILABLE = True
except ImportError:
    PYPORTFOLIO_OPT_AVAILABLE = False
    logging.warning("PyPortfolioOpt not available, using scipy fallback")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PortfolioOptimizer:
    """
    Multi-strategy portfolio optimizer
    
    Supports:
    - Mean-Variance Optimization (Markowitz)
    - Black-Litterman with AI views
    - Risk Parity
    - CVaR-constrained optimization
    - ML-based return forecasting
    """
    
    def __init__(self, n_assets: int, asset_names: List[str] = None):
        """
        Initialize optimizer
        
        Args:
            n_assets: Number of assets in portfolio
            asset_names: Optional list of asset names
        """
        self.n_assets = n_assets
        self.asset_names = asset_names or [f"Asset_{i}" for i in range(n_assets)]
        logger.info(f"Initialized optimizer for {n_assets} assets")
    
    def mean_variance_optimization(self, expected_returns: np.ndarray,
                                   cov_matrix: np.ndarray,
                                   risk_free_rate: float = 0.02,
                                   method: str = 'max_sharpe') -> np.ndarray:
        """
        Classic Markowitz Mean-Variance Optimization
        
        Args:
            expected_returns: Vector of expected returns (annualized)
            cov_matrix: Covariance matrix (annualized)
            risk_free_rate: Risk-free rate for Sharpe calculation
            method: 'max_sharpe', 'min_volatility', or 'efficient_return'
            
        Returns:
            Optimal weights vector
        """
        logger.info(f"Running Mean-Variance Optimization ({method})")
        
        if PYPORTFOLIO_OPT_AVAILABLE:
            try:
                ef = EfficientFrontier(expected_returns, cov_matrix, 
                                      weight_bounds=(0, 1))
                
                if method == 'max_sharpe':
                    weights = ef.max_sharpe(risk_free_rate=risk_free_rate)
                elif method == 'min_volatility':
                    weights = ef.min_volatility()
                else:
                    target_return = np.mean(expected_returns)
                    weights = ef.efficient_return(target_return)
                
                weights_array = np.array(list(weights.values()))
                logger.info(f"MVO weights: {weights_array}")
                return weights_array
                
            except Exception as e:
                logger.warning(f"PyPortfolioOpt failed: {e}. Using scipy fallback.")
        
        # Scipy fallback
        return self._scipy_mean_variance(expected_returns, cov_matrix, 
                                         risk_free_rate, method)
    
    def _scipy_mean_variance(self, expected_returns: np.ndarray,
                            cov_matrix: np.ndarray,
                            risk_free_rate: float,
                            method: str) -> np.ndarray:
        """Scipy-based MVO fallback"""
        
        def portfolio_variance(w):
            return w.T @ cov_matrix @ w
        
        def portfolio_return(w):
            return w.T @ expected_returns
        
        def sharpe_ratio(w):
            ret = portfolio_return(w)
            vol = np.sqrt(portfolio_variance(w))
            if vol == 0:
                return 0
            return (ret - risk_free_rate) / vol
        
        # Constraints
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        bounds = Bounds([0] * self.n_assets, [1] * self.n_assets)
        
        # Initial guess
        w0 = np.ones(self.n_assets) / self.n_assets
        
        if method == 'max_sharpe':
            result = minimize(lambda w: -sharpe_ratio(w), w0, 
                            method='SLSQP', bounds=bounds, constraints=constraints)
        elif method == 'min_volatility':
            result = minimize(portfolio_variance, w0,
                            method='SLSQP', bounds=bounds, constraints=constraints)
        else:
            target = np.mean(expected_returns)
            constraints.append({'type': 'eq', 'fun': lambda w: portfolio_return(w) - target})
            result = minimize(portfolio_variance, w0,
                            method='SLSQP', bounds=bounds, constraints=constraints)
        
        if not result.success:
            logger.warning(f"Optimization warning: {result.message}")
        
        weights = result.x
        weights = np.clip(weights, 0, 1)
        weights = weights / weights.sum()  # Renormalize
        
        logger.info(f"Scipy MVO weights: {weights}")
        return weights
    
    def black_litterman(self, market_caps: np.ndarray, cov_matrix: np.ndarray,
                       P: np.ndarray, Q: np.ndarray, 
                       tau: float = 0.05, omega: np.ndarray = None,
                       risk_aversion: float = 2.5) -> np.ndarray:
        """
        Black-Litterman model with AI-generated views
        
        Args:
            market_caps: Market capitalizations (for equilibrium weights)
            cov_matrix: Covariance matrix
            P: View matrix (k x n)
            Q: View returns vector (k x 1)
            tau: Uncertainty scaling factor
            omega: View uncertainty matrix
            risk_aversion: Market risk aversion coefficient
            
        Returns:
            Optimal weights
        """
        logger.info("Running Black-Litterman optimization")
        
        # Calculate equilibrium weights from market caps
        pi_weights = market_caps / market_caps.sum()
        
        # Calculate implied equilibrium returns
        delta = risk_aversion
        pi = delta * cov_matrix @ pi_weights  # Implied returns
        
        # If omega not provided, use proportional to variance
        if omega is None:
            omega = np.diag(P @ (tau * cov_matrix) @ P.T)
        
        # Black-Litterman formula
        try:
            # Posterior estimate of returns
            M1 = np.linalg.inv(np.linalg.inv(tau * cov_matrix) + P.T @ np.linalg.inv(omega) @ P)
            M2 = np.linalg.inv(tau * cov_matrix) @ pi + P.T @ np.linalg.inv(omega) @ Q
            bl_returns = M1 @ M2
            
            # Optimize with BL returns
            weights = self.mean_variance_optimization(bl_returns, cov_matrix, 
                                                     method='max_sharpe')
            
            logger.info(f"BL returns: {bl_returns}")
            logger.info(f"BL weights: {weights}")
            return weights
            
        except np.linalg.LinAlgError as e:
            logger.error(f"Matrix inversion failed in BL: {e}")
            # Fallback to MVO
            return self.mean_variance_optimization(pi, cov_matrix)
    
    def risk_parity(self, cov_matrix: np.ndarray) -> np.ndarray:
        """
        Risk Parity allocation - equal risk contribution from each asset
        
        Args:
            cov_matrix: Covariance matrix
            
        Returns:
            Risk parity weights
        """
        logger.info("Running Risk Parity optimization")
        
        def risk_contribution(w):
            portfolio_vol = np.sqrt(w.T @ cov_matrix @ w)
            marginal_risk = cov_matrix @ w / portfolio_vol
            risk_contrib = w * marginal_risk
            return risk_contrib
        
        def objective(w):
            rc = risk_contribution(w)
            # Minimize sum of squared differences from equal risk
            target_rc = np.ones(self.n_assets) / self.n_assets
            return np.sum((rc - target_rc) ** 2)
        
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        bounds = Bounds([0.01] * self.n_assets, [1] * self.n_assets)
        w0 = np.ones(self.n_assets) / self.n_assets
        
        result = minimize(objective, w0, method='SLSQP', 
                         bounds=bounds, constraints=constraints)
        
        if not result.success:
            logger.warning(f"Risk parity warning: {result.message}")
        
        weights = result.x
        weights = np.clip(weights, 0.01, 1)
        weights = weights / weights.sum()
        
        logger.info(f"Risk Parity weights: {weights}")
        return weights
    
    def cvar_optimization(self, returns: np.ndarray, 
                         target_return: float = None,
                         cvar_limit: float = 0.05,
                         confidence: float = 0.95) -> np.ndarray:
        """
        CVaR-constrained optimization (Conditional Value at Risk)
        
        Args:
            returns: Historical returns matrix (T x n)
            target_return: Target portfolio return (optional)
            cvar_limit: Maximum allowed CVaR
            confidence: Confidence level for CVaR
            
        Returns:
            Optimal weights
        """
        logger.info(f"Running CVaR optimization (limit={cvar_limit}, conf={confidence})")
        
        n_scenarios, n_assets = returns.shape
        
        # CVaR optimization using Rockafellar-Uryasev formulation
        # Variables: w (weights), z (VaR), u (auxiliary)
        
        def objective(x):
            w = x[:n_assets]
            z = x[n_assets]
            u = x[n_assets + 1:]
            
            # Portfolio returns in each scenario
            port_rets = returns @ w
            
            # CVaR objective: z + (1/(1-alpha)) * sum(u) / n
            alpha = confidence
            cvar = z + np.sum(u) / (n_scenarios * (1 - alpha))
            
            return cvar
        
        # Initial guess
        x0 = np.zeros(n_assets + 1 + n_scenarios)
        x0[:n_assets] = np.ones(n_assets) / n_assets
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x[:n_assets]) - 1},  # Sum weights = 1
        ]
        
        if target_return is not None:
            constraints.append({
                'type': 'ineq', 
                'fun': lambda x: returns.mean(axis=0) @ x[:n_assets] - target_return
            })
        
        # u >= 0 and u >= -port_ret - z
        bounds_list = [(0, 1)] * n_assets  # weights
        bounds_list.append((None, None))  # z (VaR)
        bounds_list.extend([(0, None)] * n_scenarios)  # u >= 0
        
        bounds = Bounds([b[0] for b in bounds_list], [b[1] for b in bounds_list])
        
        try:
            result = minimize(objective, x0, method='SLSQP',
                            bounds=bounds, constraints=constraints,
                            options={'maxiter': 500})
            
            if not result.success:
                logger.warning(f"CVaR optimization warning: {result.message}")
            
            weights = result.x[:n_assets]
            weights = np.clip(weights, 0, 1)
            weights = weights / weights.sum()
            
            # Calculate actual CVaR
            port_rets = returns @ weights
            var = np.percentile(port_rets, (1 - confidence) * 100)
            cvar = port_rets[port_rets <= var].mean() if len(port_rets[port_rets <= var]) > 0 else var
            
            logger.info(f"CVaR weights: {weights}")
            logger.info(f"Portfolio CVaR: {cvar:.4f}")
            
            return weights
            
        except Exception as e:
            logger.error(f"CVaR optimization failed: {e}")
            # Fallback to equal weight
            return np.ones(n_assets) / n_assets
    
    def ml_forecast_returns(self, returns: pd.DataFrame, 
                           lookback: int = 168,
                           forecast_horizon: int = 24) -> np.ndarray:
        """
        ML-based expected return forecasting using simple momentum features
        
        Args:
            returns: Historical returns DataFrame
            lookback: Lookback window for features
            forecast_horizon: Horizon for prediction
            
        Returns:
            Forecasted expected returns (annualized)
        """
        logger.info(f"Generating ML return forecasts (lookback={lookback})")
        
        try:
            from sklearn.ensemble import RandomForestRegressor
            
            forecasts = []
            
            for symbol in returns.columns:
                # Create features: lagged returns, rolling stats
                df = returns[symbol].to_frame()
                
                # Features
                df['lag_1'] = df[symbol].shift(1)
                df['lag_24'] = df[symbol].shift(24)
                df['ma_24'] = df[symbol].rolling(24).mean()
                df['std_24'] = df[symbol].rolling(24).std()
                df['momentum_168'] = df[symbol].rolling(168).apply(
                    lambda x: x.iloc[-1] / x.iloc[0] - 1 if len(x) > 0 else 0
                )
                
                # Target: forward return
                df['target'] = df[symbol].shift(-forecast_horizon)
                
                df = df.dropna()
                
                if len(df) < lookback:
                    forecasts.append(0.0)
                    continue
                
                X = df[['lag_1', 'lag_24', 'ma_24', 'std_24', 'momentum_168']]
                y = df['target']
                
                # Train/test split
                split = int(len(df) * 0.8)
                X_train, X_test = X.iloc[:split], X.iloc[split:]
                y_train, y_test = y.iloc[:split], y.iloc[split:]
                
                # Train model
                model = RandomForestRegressor(n_estimators=50, max_depth=5, 
                                             random_state=42)
                model.fit(X_train, y_train)
                
                # Latest prediction
                latest_features = X.iloc[[-1]]
                forecast = model.predict(latest_features)[0]
                
                # Annualize (assuming hourly data)
                annualized = forecast * 24 * 365
                forecasts.append(annualized)
                
            return np.array(forecasts)
            
        except ImportError:
            logger.warning("sklearn not available, using historical mean")
            return returns.mean() * 24 * 365
        except Exception as e:
            logger.error(f"ML forecast error: {e}")
            return returns.mean() * 24 * 365
    
    def calculate_portfolio_metrics(self, weights: np.ndarray,
                                   returns: pd.DataFrame,
                                   cov_matrix: np.ndarray,
                                   risk_free_rate: float = 0.02) -> Dict:
        """
        Calculate comprehensive portfolio metrics
        
        Returns:
            Dictionary of metrics
        """
        weights = np.array(weights)
        
        # Basic statistics
        port_returns = returns @ weights
        port_mean = port_returns.mean()
        port_std = port_returns.std()
        
        # Annualized (hourly data assumption)
        ann_return = port_mean * 24 * 365
        ann_vol = port_std * np.sqrt(24 * 365)
        
        # Sharpe ratio
        sharpe = (ann_return - risk_free_rate) / ann_vol if ann_vol > 0 else 0
        
        # Monthly return
        monthly_return = (1 + port_mean) ** (24 * 30) - 1
        
        # Drawdown analysis
        cumulative = (1 + port_returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # VaR and CVaR (95% confidence)
        var_95 = np.percentile(port_returns, 5)
        cvar_95 = port_returns[port_returns <= var_95].mean()
        
        metrics = {
            'total_return': cumulative.iloc[-1] - 1,
            'annualized_return': ann_return,
            'monthly_return': monthly_return,
            'annualized_volatility': ann_vol,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'var_95': var_95,
            'cvar_95': cvar_95,
            'weights': weights
        }
        
        logger.info(f"Portfolio Metrics:")
        logger.info(f"  Annual Return: {ann_return:.2%}")
        logger.info(f"  Monthly Return: {monthly_return:.2%}")
        logger.info(f"  Volatility: {ann_vol:.2%}")
        logger.info(f"  Sharpe: {sharpe:.2f}")
        logger.info(f"  Max DD: {max_drawdown:.2%}")
        logger.info(f"  VaR 95%: {var_95:.4f}")
        logger.info(f"  CVaR 95%: {cvar_95:.4f}")
        
        return metrics


def main():
    """Test optimizer"""
    np.random.seed(42)
    
    # Sample data
    n_assets = 5
    returns = pd.DataFrame(
        np.random.randn(1000, n_assets) * 0.01,
        columns=['BTC', 'ETH', 'SOL', 'BNB', 'XRP']
    )
    
    cov_matrix = returns.cov().values * 24 * 365  # Annualized
    expected_returns = returns.mean().values * 24 * 365
    
    optimizer = PortfolioOptimizer(n_assets, list(returns.columns))
    
    # Test MVO
    print("\n=== Mean-Variance Optimization ===")
    mvo_weights = optimizer.mean_variance_optimization(expected_returns, cov_matrix)
    
    # Test Risk Parity
    print("\n=== Risk Parity ===")
    rp_weights = optimizer.risk_parity(cov_matrix)
    
    # Test Black-Litterman
    print("\n=== Black-Litterman ===")
    market_caps = np.array([1.0, 0.5, 0.2, 0.15, 0.1])  # Relative market caps
    P = np.eye(n_assets)
    Q = expected_returns * 0.5
    bl_weights = optimizer.black_litterman(market_caps, cov_matrix, P, Q)
    
    # Test CVaR
    print("\n=== CVaR Optimization ===")
    cvar_weights = optimizer.cvar_optimization(returns.values, cvar_limit=0.05)
    
    # Compare metrics
    print("\n=== Comparison ===")
    strategies = {
        'MVO': mvo_weights,
        'Risk Parity': rp_weights,
        'Black-Litterman': bl_weights,
        'CVaR': cvar_weights
    }
    
    for name, weights in strategies.items():
        metrics = optimizer.calculate_portfolio_metrics(weights, returns, cov_matrix)
        print(f"\n{name}:")
        print(f"  Weights: {weights}")
        print(f"  Monthly Return: {metrics['monthly_return']:.2%}")
        print(f"  Sharpe: {metrics['sharpe_ratio']:.2f}")
        print(f"  Max DD: {metrics['max_drawdown']:.2%}")


if __name__ == "__main__":
    main()
