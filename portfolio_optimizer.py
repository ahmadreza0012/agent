"""
Portfolio Optimizer Module (v3)
--------------------------------
Implements Markowitz, Black-Litterman, Risk Parity, and CVaR optimization.

CRITICAL FIXES IN THIS VERSION:
1. Default risk_free_rate changed from 0.02 to 0.0 (crypto volatility makes 2% too high)
2. MVO strategy rewritten to use ACTUAL historical returns (not hardcoded [0.1]*n_assets)
3. Fallback chain improved: max_sharpe -> min_volatility -> scipy equal-weight
4. CVaR limit increased from 5% to 10% (5% infeasible for crypto volatility)
5. Trend-following allocates 80%+ to CASH when no uptrends (was 70%)
6. All MVO calls now explicitly pass risk_free_rate=0.0
7. Better error handling and logging throughout optimization chain
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize, Bounds, linprog
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
    Multi-strategy portfolio optimizer.
    Supports: Mean-Variance (Markowitz), Black-Litterman with AI views,
    Risk Parity, CVaR-constrained optimization (fixed), ML-based forecasting.
    """

    def __init__(self, n_assets: int, asset_names: List[str] = None):
        self.n_assets = n_assets
        self.asset_names = asset_names or [f"Asset_{i}" for i in range(n_assets)]
        logger.info(f"Initialized optimizer for {n_assets} assets: {self.asset_names}")
    
    def _get_risky_asset_mask(self) -> np.ndarray:
        """
        Helper to identify risky assets (non-CASH) for risk parity.
        Returns boolean mask where True = risky asset.
        CASH column has zero variance, so we exclude it from risk parity calculation.
        """
        if self.asset_names:
            return np.array([name != 'CASH' for name in self.asset_names])
        return np.ones(self.n_assets, dtype=bool)

    # ------------------------------------------------------------------
    def mean_variance_optimization(self, expected_returns: np.ndarray,
                                    cov_matrix: np.ndarray,
                                    risk_free_rate: float = 0.0,
                                    method: str = 'max_sharpe') -> np.ndarray:
        """
        Mean-Variance Optimization with IMPROVED FALLBACK CHAIN (Stage 5+).
        
        CRITICAL FIX STAGE 5+: 
        When max_sharpe fails, do NOT jump directly to pure min_volatility (which produces ~100% CASH).
        Implement this enhanced fallback chain:
        1. Try max_sharpe with risk_free_rate=0.0
        2. If fails → try efficient_return with modest target (mean of POSITIVE expected returns or 3-5% annualized)
        3. If still fails → run min_volatility but force maximum 40% CASH (minimum 60% in risky assets)
        4. Last resort: equal-weight among risky assets + 25% CASH
        
        CRITICAL FIX STAGE 5++:
        Each fallback step must create a FRESH EfficientFrontier instance.
        PyPortfolioOpt explicitly forbids reusing an optimizer after it has been solved:
        "Adding constraints to an already solved problem might have unintended consequences."
        
        Risk-free rate defaults to 0.0 (crypto volatility makes higher rates unrealistic).
        """
        logger.info(f"Running Mean-Variance Optimization ({method}, rf_rate={risk_free_rate})")

        if PYPORTFOLIO_OPT_AVAILABLE:
            # Define bounds helper (same for all attempts)
            def get_bounds():
                bounds = []
                for i, name in enumerate(self.asset_names):
                    if name == 'CASH':
                        bounds.append((0.0, 1.0))  # CASH: 0-100%
                    else:
                        bounds.append((0.0, 0.45))  # Risky: 0-45%
                return bounds
            
            # ATTEMPT 1: max_sharpe with fresh instance
            try:
                ef1 = EfficientFrontier(expected_returns, cov_matrix, weight_bounds=get_bounds())
                if method == 'max_sharpe':
                    weights = ef1.max_sharpe(risk_free_rate=risk_free_rate)
                elif method == 'min_volatility':
                    # For min_volatility method, use cash-capped version with fresh instance
                    weights = self._min_volatility_with_cash_cap_fresh(expected_returns, cov_matrix, max_cash=0.40)
                else:
                    target_return = np.mean(expected_returns)
                    weights = ef1.efficient_return(target_return)
                
                weights_array = np.array(list(weights.values()))
                logger.info(f"MVO weights (attempt 1): {weights_array}")
                return weights_array
            except Exception as e:
                logger.warning(f"Attempt 1 (max_sharpe/direct) failed: {e}. Trying Attempt 2 (efficient_return)...")
            
            # ATTEMPT 2: efficient_return with modest positive target (fresh instance)
            # Use mean of positive expected returns, or at least 3-5% annualized
            try:
                positive_returns = expected_returns[expected_returns > 0]
                if len(positive_returns) > 0:
                    target_ret = max(np.mean(positive_returns), 0.03 / 24 / 365)  # At least 3% annualized
                else:
                    target_ret = 0.05 / 24 / 365  # 5% annualized as fallback
                
                ef2 = EfficientFrontier(expected_returns, cov_matrix, weight_bounds=get_bounds())
                weights = ef2.efficient_return(target_ret)
                
                weights_array = np.array(list(weights.values()))
                logger.info(f"MVO weights (attempt 2 - efficient_return): {weights_array}")
                return weights_array
            except Exception as e2:
                logger.warning(f"Attempt 2 (efficient_return) failed: {e2}. Trying Attempt 3 (min_volatility with cash cap)...")
            
            # ATTEMPT 3: min_volatility with cash cap (fresh instance)
            try:
                weights = self._min_volatility_with_cash_cap_fresh(expected_returns, cov_matrix, max_cash=0.40)
                weights_array = np.array(list(weights.values()))
                logger.info(f"MVO weights (attempt 3 - min_volatility capped): {weights_array}")
                return weights_array
            except Exception as e3:
                logger.warning(f"Attempt 3 (min_volatility capped) failed: {e3}. Using last resort equal-weight.")
            
            # LAST RESORT: equal-weight among risky assets + 25% CASH
            n_assets = len(self.asset_names)
            cash_idx = next((i for i, name in enumerate(self.asset_names) if name == 'CASH'), None)
            if cash_idx is not None:
                n_risky = n_assets - 1
                weights_array = np.array([0.75 / n_risky if name != 'CASH' else 0.25 for name in self.asset_names])
            else:
                weights_array = np.ones(n_assets) / n_assets
            
            logger.info(f"MVO weights (last resort - equal-weight): {weights_array}")
            return weights_array
        
        # SciPy fallback if PyPortfolioOpt not available
        return self._scipy_mean_variance(expected_returns, cov_matrix, risk_free_rate, method)
    
    def _min_volatility_with_cash_cap(self, ef, max_cash: float = 0.40) -> dict:
        """
        Stage 5: Helper to run min_volatility while capping CASH allocation.
        Prevents the optimizer from going 100% CASH which kills returns.
        
        NOTE: This method expects an already-created EfficientFrontier instance.
        For a fresh instance approach, use _min_volatility_with_cash_cap_fresh instead.
        """
        try:
            # First try standard min_volatility
            weights = ef.min_volatility()
            
            # Check if CASH is too high
            cash_weight = 0.0
            for name, w in weights.items():
                if name == 'CASH':
                    cash_weight = w
                    break
            
            if cash_weight > max_cash:
                logger.info(f"CASH weight {cash_weight:.1%} exceeds cap {max_cash:.0%}. Redistributing to risky assets.")
                # Cap CASH and redistribute proportionally to risky assets
                excess_cash = cash_weight - max_cash
                weights['CASH'] = max_cash
                
                # Find risky assets and redistribute excess proportionally
                risky_assets = [k for k in weights.keys() if k != 'CASH']
                risky_total = sum(weights[k] for k in risky_assets)
                
                if risky_total > 0:
                    for asset in risky_assets:
                        weights[asset] += excess_cash * (weights[asset] / risky_total)
                else:
                    # All risky assets are zero, distribute equally
                    for asset in risky_assets:
                        weights[asset] = excess_cash / len(risky_assets)
            
            return weights
        except Exception as e:
            logger.error(f"_min_volatility_with_cash_cap failed: {e}. Using equal-weight fallback.")
            # Last resort: equal weight with capped cash
            n_assets = len(self.asset_names)
            cash_idx = next((i for i, name in enumerate(self.asset_names) if name == 'CASH'), None)
            if cash_idx is not None:
                # Equal weight risky + 30% CASH
                n_risky = n_assets - 1
                weights = {name: 0.70 / n_risky if name != 'CASH' else 0.30 for name in self.asset_names}
            else:
                weights = {name: 1.0 / n_assets for name in self.asset_names}
            return weights
    
    def _min_volatility_with_cash_cap_fresh(self, expected_returns: np.ndarray, cov_matrix: np.ndarray, 
                                             max_cash: float = 0.40) -> dict:
        """
        Stage 5++: Helper to run min_volatility while capping CASH allocation.
        Creates a FRESH EfficientFrontier instance to avoid PyPortfolioOpt's restriction on reusing solved optimizers.
        
        PyPortfolioOpt explicitly forbids: \"Adding constraints to an already solved problem might have unintended consequences.\"
        """
        try:
            # Create fresh instance
            bounds = []
            for i, name in enumerate(self.asset_names):
                if name == 'CASH':
                    bounds.append((0.0, 1.0))
                else:
                    bounds.append((0.0, 0.45))
            
            ef_fresh = EfficientFrontier(expected_returns, cov_matrix, weight_bounds=bounds)
            
            # Run min_volatility on fresh instance
            weights = ef_fresh.min_volatility()
            
            # Check if CASH is too high
            cash_weight = 0.0
            for name, w in weights.items():
                if name == 'CASH':
                    cash_weight = w
                    break
            
            if cash_weight > max_cash:
                logger.info(f"CASH weight {cash_weight:.1%} exceeds cap {max_cash:.0%}. Redistributing to risky assets.")
                # Cap CASH and redistribute proportionally to risky assets
                excess_cash = cash_weight - max_cash
                weights['CASH'] = max_cash
                
                # Find risky assets and redistribute excess proportionally
                risky_assets = [k for k in weights.keys() if k != 'CASH']
                risky_total = sum(weights[k] for k in risky_assets)
                
                if risky_total > 0:
                    for asset in risky_assets:
                        weights[asset] += excess_cash * (weights[asset] / risky_total)
                else:
                    # All risky assets are zero, distribute equally
                    for asset in risky_assets:
                        weights[asset] = excess_cash / len(risky_assets)
            
            return weights
        except Exception as e:
            logger.error(f"_min_volatility_with_cash_cap_fresh failed: {e}. Using equal-weight fallback.")
            # Last resort: equal weight with capped cash
            n_assets = len(self.asset_names)
            cash_idx = next((i for i, name in enumerate(self.asset_names) if name == 'CASH'), None)
            if cash_idx is not None:
                # Equal weight risky + 25% CASH (last resort)
                n_risky = n_assets - 1
                weights = {name: 0.75 / n_risky if name != 'CASH' else 0.25 for name in self.asset_names}
            else:
                weights = {name: 1.0 / n_assets for name in self.asset_names}
            return weights

    def _scipy_mean_variance(self, expected_returns, cov_matrix, risk_free_rate, method) -> np.ndarray:
        """Scipy-based MVO fallback with better error handling and CASH cap (Stage 5)."""
        def portfolio_variance(w):
            return w.T @ cov_matrix @ w

        def portfolio_return(w):
            return w.T @ expected_returns

        def sharpe_ratio(w):
            ret = portfolio_return(w)
            vol = np.sqrt(portfolio_variance(w))
            return 0 if vol == 0 else (ret - risk_free_rate) / vol

        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        
        # STAGE 5 FIX: Cap CASH at 40% maximum in bounds to prevent 100% CASH solutions
        max_cash_cap = 0.40
        bounds_list = []
        for i, name in enumerate(self.asset_names):
            if name == 'CASH':
                bounds_list.append((0.0, max_cash_cap))  # Cap CASH at 40%
            else:
                bounds_list.append((0.0, 0.45))
        
        bounds = Bounds([b[0] for b in bounds_list], [b[1] for b in bounds_list])
        w0 = np.ones(self.n_assets) / self.n_assets

        try:
            if method == 'max_sharpe':
                result = minimize(lambda w: -sharpe_ratio(w), w0, method='SLSQP',
                                bounds=bounds, constraints=constraints,
                                options={'maxiter': 1000, 'ftol': 1e-9})
            elif method == 'min_volatility':
                result = minimize(portfolio_variance, w0, method='SLSQP',
                                bounds=bounds, constraints=constraints,
                                options={'maxiter': 1000, 'ftol': 1e-9})
            else:
                target = np.mean(expected_returns)
                constraints.append({'type': 'eq', 'fun': lambda w: portfolio_return(w) - target})
                result = minimize(portfolio_variance, w0, method='SLSQP',
                                bounds=bounds, constraints=constraints,
                                options={'maxiter': 1000, 'ftol': 1e-9})

            if not result.success:
                logger.warning(f"Optimization warning: {result.message}")
            
            weights = result.x.copy()
            
            # Ensure bounds are respected
            for i, name in enumerate(self.asset_names):
                if name == 'CASH':
                    weights[i] = np.clip(weights[i], 0.0, max_cash_cap)
                else:
                    weights[i] = np.clip(weights[i], 0.0, 0.45)
            
            s = weights.sum()
            if s > 0:
                weights = weights / s
            else:
                # Last resort: equal weight with capped cash
                n_risky = sum(1 for name in self.asset_names if name != 'CASH')
                if n_risky > 0:
                    weights = np.array([0.60 / n_risky if name != 'CASH' else 0.40 for name in self.asset_names])
                else:
                    weights = np.ones(self.n_assets) / self.n_assets
                    
            logger.info(f"Scipy MVO weights: {weights}")
            return weights
        except Exception as e:
            logger.error(f"Scipy MVO failed: {e}. Using equal-weight fallback.")
            return np.ones(self.n_assets) / self.n_assets

    # ------------------------------------------------------------------
    def black_litterman(self, market_caps: np.ndarray, cov_matrix: np.ndarray,
                         P: np.ndarray, Q: np.ndarray, tau: float = 0.05,
                         omega: np.ndarray = None, risk_aversion: float = 2.5,
                         risk_free_rate: float = 0.0) -> np.ndarray:
        """
        Black-Litterman optimization with AI-generated views.
        
        CRITICAL FIX: Now passes risk_free_rate=0.0 explicitly to mean_variance_optimization
        """
        logger.info("Running Black-Litterman optimization")
        
        market_caps = np.asarray(market_caps).flatten()
        cov_matrix = np.asarray(cov_matrix)
        P = np.asarray(P)
        Q = np.asarray(Q).flatten()
        
        n_assets_bl = len(market_caps)
        
        pi_weights = market_caps / market_caps.sum()
        delta = risk_aversion
        pi = delta * cov_matrix @ pi_weights

        if omega is None:
            omega = np.diag(P @ (tau * cov_matrix) @ P.T)

        try:
            M1 = np.linalg.inv(np.linalg.inv(tau * cov_matrix) + P.T @ np.linalg.inv(omega) @ P)
            M2 = np.linalg.inv(tau * cov_matrix) @ pi + P.T @ np.linalg.inv(omega) @ Q
            bl_returns = M1 @ M2
            logger.info(f"BL returns: {bl_returns}")
            
            temp_optimizer = PortfolioOptimizer(n_assets=n_assets_bl, asset_names=self.asset_names[:n_assets_bl])
            weights = temp_optimizer.mean_variance_optimization(bl_returns, cov_matrix, 
                                                                 risk_free_rate=risk_free_rate, 
                                                                 method='max_sharpe')
            logger.info(f"BL weights: {weights}")
            return weights
        except np.linalg.LinAlgError as e:
            logger.error(f"Matrix inversion failed in BL: {e}")
            return self.mean_variance_optimization(pi, cov_matrix, risk_free_rate=risk_free_rate)

    # ------------------------------------------------------------------
    def risk_parity(self, cov_matrix: np.ndarray) -> np.ndarray:
        """
        Risk Parity optimization with CASH handling.
        
        When CASH exists: run risk parity on risky assets only (70% allocation),
        allocate remainder (30%) to CASH for defensive buffer.
        """
        logger.info("Running Risk Parity optimization")
        
        risky_mask = self._get_risky_asset_mask()
        n_risky = risky_mask.sum()
        n_cash = self.n_assets - n_risky
        
        if n_cash == 0:
            # No CASH column - run standard risk parity
            def risk_contribution(w):
                portfolio_vol = np.sqrt(w.T @ cov_matrix @ w)
                if portfolio_vol == 0:
                    return np.zeros_like(w)
                marginal_risk = cov_matrix @ w / portfolio_vol
                return w * marginal_risk

            def objective(w):
                rc = risk_contribution(w)
                target_rc = np.ones(self.n_assets) / self.n_assets
                return np.sum((rc - target_rc) ** 2)

            constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
            bounds = Bounds([0.02] * self.n_assets, [0.50] * self.n_assets)
            w0 = np.ones(self.n_assets) / self.n_assets
            result = minimize(objective, w0, method='SLSQP', bounds=bounds, constraints=constraints,
                            options={'maxiter': 1000, 'ftol': 1e-9})
            if not result.success:
                logger.warning(f"Risk parity warning: {result.message}")
            weights = np.clip(result.x, 0.02, 0.50)
            weights = weights / weights.sum()
            logger.info(f"Risk Parity weights: {weights}")
            return weights
        
        # CASH exists - run risk parity on risky assets only
        logger.info(f"Risk Parity: {n_risky} risky assets, {n_cash} cash asset(s)")
        risky_indices = np.where(risky_mask)[0]
        cash_indices = np.where(~risky_mask)[0]
        
        cov_risky = cov_matrix[np.ix_(risky_mask, risky_mask)]
        
        def risk_contribution_risky(w_risky):
            portfolio_vol = np.sqrt(w_risky.T @ cov_risky @ w_risky)
            if portfolio_vol == 0:
                return np.zeros_like(w_risky)
            marginal_risk = cov_risky @ w_risky / portfolio_vol
            return w_risky * marginal_risk

        def objective_risky(w_risky):
            rc = risk_contribution_risky(w_risky)
            target_rc = np.ones(n_risky) / n_risky
            return np.sum((rc - target_rc) ** 2)
        
        constraints_risky = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        bounds_risky = Bounds([0.02] * n_risky, [0.50] * n_risky)
        w0_risky = np.ones(n_risky) / n_risky
        
        result = minimize(objective_risky, w0_risky, method='SLSQP', 
                         bounds=bounds_risky, constraints=constraints_risky,
                         options={'maxiter': 1000, 'ftol': 1e-9})
        
        if not result.success:
            logger.warning(f"Risk parity warning: {result.message}")
        
        risky_weights = np.clip(result.x, 0.02, 0.50)
        risky_weights = risky_weights / risky_weights.sum()
        
        weights = np.zeros(self.n_assets)
        weights[risky_indices] = risky_weights * 0.7
        weights[cash_indices] = 0.3 / n_cash
        weights = weights / weights.sum()
        
        logger.info(f"Risk Parity weights (with 30% cash buffer): {weights}")
        return weights

    # ------------------------------------------------------------------
    def cvar_optimization(self, returns: np.ndarray,
                           target_return: float = None,
                           cvar_limit: float = 0.10,
                           confidence: float = 0.95) -> np.ndarray:
        """
        CVaR-minimizing portfolio via the correct Rockafellar-Uryasev LP.
        
        STAGE 5 FIX: When optimizer wants 100% CASH, cap CASH at 50-60% maximum
        and distribute the rest according to risk parity or inverse-volatility
        among risky assets. Keep the 10% CVaR limit, but prevent extreme all-cash solutions.
        """
        logger.info(f"Running CVaR optimization (limit={cvar_limit}, conf={confidence})")
        n_scenarios, n_assets = returns.shape
        alpha = confidence

        n_vars = n_assets + 1 + n_scenarios

        c = np.zeros(n_vars)
        c[n_assets] = 1.0
        c[n_assets + 1:] = 1.0 / ((1 - alpha) * n_scenarios)

        A1 = np.zeros((n_scenarios, n_vars))
        A1[:, :n_assets] = -returns
        A1[:, n_assets] = -1.0
        A1[np.arange(n_scenarios), n_assets + 1 + np.arange(n_scenarios)] = -1.0
        b1 = np.zeros(n_scenarios)

        cvar_coef = 1.0 / ((1 - alpha) * n_scenarios)
        A_cvar = np.zeros((1, n_vars))
        A_cvar[0, n_assets] = 1.0
        A_cvar[0, n_assets + 1:] = cvar_coef
        b_cvar = np.array([cvar_limit])
        
        A_ub = np.vstack([A1, A_cvar])
        b_ub = np.concatenate([b1, b_cvar])

        if target_return is not None:
            A2 = np.zeros((1, n_vars))
            A2[0, :n_assets] = -returns.mean(axis=0)
            b2 = np.array([-target_return])
            A_ub = np.vstack([A_ub, A2])
            b_ub = np.concatenate([b_ub, b2])

        A_eq = np.zeros((1, n_vars))
        A_eq[0, :n_assets] = 1.0
        b_eq = np.array([1.0])

        bounds_list = []
        for i in range(n_assets):
            if hasattr(self, 'asset_names') and self.asset_names and i < len(self.asset_names):
                if self.asset_names[i] == 'CASH':
                    bounds_list.append((0.0, 1.0))
                else:
                    bounds_list.append((0.0, 0.45))
            else:
                bounds_list.append((0.0, 1.0))
        bounds = bounds_list + [(None, None)] + [(0, None)] * n_scenarios

        result = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                        bounds=bounds, method='highs')

        if not result.success:
            status_msg = str(result.message).lower() if result.message else ""
            if 'infeasible' in status_msg or result.status == 2:
                logger.warning(f"CVaR limit {cvar_limit} is INFEASIBLE - relaxing constraint...")
                
                A_ub_relaxed = A1
                b_ub_relaxed = b1
                
                result = linprog(c, A_ub=A_ub_relaxed, b_ub=b_ub_relaxed, 
                                A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')
                
                if not result.success:
                    logger.warning(f"CVaR LP still failed: {result.message}. Using equal weight.")
                    return np.ones(n_assets) / n_assets
            else:
                logger.warning(f"CVaR LP failed: {result.message}. Using equal weight.")
                return np.ones(n_assets) / n_assets

        weights = result.x[:n_assets]
        weights = np.clip(weights, 0, 1)
        s = weights.sum()
        weights = weights / s if s > 0 else np.ones(n_assets) / n_assets

        # STAGE 5 FIX: Cap CASH at 60% maximum and redistribute to risky assets
        cash_mask = np.array([name == 'CASH' for name in self.asset_names])
        risky_mask = ~cash_mask
        
        cash_weight = weights[cash_mask].sum() if cash_mask.any() else 0.0
        max_cash_cap = 0.60  # Stage 5: Maximum 60% CASH
        
        if cash_weight > max_cash_cap:
            logger.info(f"CVaR CASH weight {cash_weight:.1%} exceeds cap {max_cash_cap:.0%}. "
                       f"Redistributing to risky assets via inverse-volatility.")
            
            excess_cash = cash_weight - max_cash_cap
            
            # Cap CASH
            if cash_mask.any():
                weights[cash_mask] = max_cash_cap / cash_mask.sum()
            
            # Distribute excess to risky assets using inverse-volatility weighting
            if risky_mask.sum() > 0:
                risky_indices = np.where(risky_mask)[0]
                volatilities = np.sqrt(np.diag(np.cov(returns[:, risky_mask].T)))
                # Inverse volatility weights
                inv_vol = 1.0 / (volatilities + 1e-8)
                inv_vol_weights = inv_vol / inv_vol.sum()
                
                # Add excess proportionally
                weights[risky_indices] += excess_cash * inv_vol_weights
            
            # Renormalize
            weights = weights / weights.sum()
            logger.info(f"CVaR weights after CASH cap: {weights}")

        port_rets = returns @ weights
        var = np.percentile(port_rets, (1 - confidence) * 100)
        tail = port_rets[port_rets <= var]
        cvar_realized = tail.mean() if len(tail) > 0 else var
        
        if cvar_realized > cvar_limit * 1.05:
            logger.warning(f"CVaR constraint VIOLATION: realized={cvar_realized:.4f} > limit={cvar_limit:.4f}")
        else:
            logger.info(f"CVaR constraint satisfied: realized={cvar_realized:.4f} <= limit={cvar_limit:.4f}")
        
        logger.info(f"CVaR weights: {weights}")
        return weights

    # ------------------------------------------------------------------
    def ml_forecast_returns(self, returns: pd.DataFrame, lookback: int = 168,
                             forecast_horizon: int = 24) -> np.ndarray:
        """ML-based return forecasting using Random Forest.
        
        CRITICAL FIX: Returns are per-bar forecasts (NOT annualized).
        Caller must apply correct annualization based on detected data frequency.
        """
        logger.info(f"Generating ML return forecasts (lookback={lookback})")
        try:
            from sklearn.ensemble import RandomForestRegressor

            forecasts = []
            for symbol in returns.columns:
                df = returns[symbol].to_frame()
                df['lag_1'] = df[symbol].shift(1)
                df['lag_24'] = df[symbol].shift(24)
                df['ma_24'] = df[symbol].rolling(24).mean()
                df['std_24'] = df[symbol].rolling(24).std()
                df['momentum_168'] = df[symbol].rolling(168).apply(
                    lambda x: x.iloc[-1] / x.iloc[0] - 1 if len(x) > 0 else 0)
                df['target'] = df[symbol].shift(-forecast_horizon)
                df = df.dropna()

                if len(df) < lookback:
                    forecasts.append(0.0)
                    continue

                X = df[['lag_1', 'lag_24', 'ma_24', 'std_24', 'momentum_168']]
                y = df['target']
                split = int(len(df) * 0.8)
                X_train, y_train = X.iloc[:split], y.iloc[:split]

                model = RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42)
                model.fit(X_train, y_train)
                # PHASE 1 FIX: Return per-bar forecast (NOT annualized)
                # Caller must apply freq.annualization_factor_mean
                forecast = model.predict(X.iloc[[-1]])[0]
                forecasts.append(forecast)
            return np.array(forecasts)
        except ImportError:
            logger.warning("sklearn not available, using historical mean")
            # PHASE 1 FIX: Return per-bar mean (NOT annualized)
            return returns.mean().values
        except Exception as e:
            logger.error(f"ML forecast error: {e}")
            # PHASE 1 FIX: Return per-bar mean (NOT annualized)
            return returns.mean().values

    # ------------------------------------------------------------------
    def calculate_portfolio_metrics(self, weights: np.ndarray, returns: pd.DataFrame,
                                     cov_matrix: np.ndarray, risk_free_rate: float = 0.0,
                                     freq=None) -> Dict:
        """
        Calculate portfolio performance metrics.
        
        CRITICAL FIX: Accepts optional FrequencySpec for correct annualization.
        If freq is None, falls back to hourly assumption (legacy behavior).
        
        Args:
            weights: Portfolio weights
            returns: DataFrame of per-bar returns
            cov_matrix: Annualized covariance matrix
            risk_free_rate: Risk-free rate (default 0.0 for crypto)
            freq: FrequencySpec for annualization (optional, defaults to hourly)
        """
        weights = np.array(weights)
        port_returns = returns @ weights
        port_mean = port_returns.mean()
        port_std = port_returns.std()

        # PHASE 1 FIX: Use detected frequency for annualization if provided
        if freq is not None:
            ann_return = port_mean * freq.annualization_factor_mean
            ann_vol = port_std * freq.annualization_factor_vol
            monthly_return = (1 + port_mean) ** (freq.observations_per_day * 30) - 1
        else:
            # Legacy fallback: assume hourly data
            logger.warning("calculate_portfolio_metrics: freq not provided, assuming hourly")
            ann_return = port_mean * 24 * 365
            ann_vol = port_std * np.sqrt(24 * 365)
            monthly_return = (1 + port_mean) ** (24 * 30) - 1
            
        sharpe = (ann_return - risk_free_rate) / ann_vol if ann_vol > 0 else 0

        cumulative = (1 + port_returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()

        var_95 = np.percentile(port_returns, 5)
        cvar_95 = port_returns[port_returns <= var_95].mean()

        return {
            'total_return': cumulative.iloc[-1] - 1,
            'annualized_return': ann_return,
            'monthly_return': monthly_return,
            'annualized_volatility': ann_vol,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'var_95': var_95,
            'cvar_95': cvar_95,
            'weights': weights,
        }


def trend_following_strategy(prices: pd.DataFrame, returns: pd.DataFrame, 
                               short_window: int = 20, long_window: int = 100) -> np.ndarray:
    """
    Trend-following strategy based on moving average crossovers.
    
    CRITICAL FIX: When no uptrends detected, allocate 80%+ to CASH (was 70%)
    This provides stronger defensive positioning in non-trending markets.
    """
    n_assets = len(returns.columns)
    weights = np.zeros(n_assets)
    
    cash_col_idx = None
    if 'CASH' in returns.columns:
        cash_col_idx = returns.columns.get_loc('CASH')
    elif prices.columns[-1] == 'CASH':
        cash_col_idx = n_assets - 1
    
    trend_strengths = {}
    for i, col in enumerate(returns.columns):
        if i == cash_col_idx:
            continue
            
        if len(prices[col]) < long_window:
            trend_strengths[i] = 0.0
            continue
            
        ma_short = prices[col].rolling(window=short_window).mean().iloc[-1]
        ma_long = prices[col].rolling(window=long_window).mean().iloc[-1]
        
        if ma_long > 0:
            strength = (ma_short / ma_long) - 1.0
            if strength > 0:
                trend_strengths[i] = strength
            else:
                trend_strengths[i] = 0.0
        else:
            trend_strengths[i] = 0.0
    
    total_strength = sum(trend_strengths.values())
    
    if total_strength > 0 and len(trend_strengths) > 0:
        for idx, strength in trend_strengths.items():
            if strength > 0:
                weights[idx] = strength / total_strength
        
        risky_allocation = min(0.8, total_strength * 2.0)
        weights = weights * risky_allocation
        
        if cash_col_idx is not None:
            weights[cash_col_idx] = 1.0 - weights.sum()
        else:
            if weights.sum() > 0:
                weights = weights / weights.sum()
    else:
        # CRITICAL FIX: No trends detected -> allocate 80%+ to CASH (was 70%)
        logger.info("Trend-following: No uptrends detected, allocating 80% to CASH")
        if cash_col_idx is not None:
            weights[cash_col_idx] = 0.80
            risky_mask = np.ones(n_assets, dtype=bool)
            if cash_col_idx is not None:
                risky_mask[cash_col_idx] = False
            if risky_mask.sum() > 0:
                weights[risky_mask] = 0.20 / risky_mask.sum()
        else:
            weights = np.ones(n_assets) / n_assets
    
    return weights


def mean_reversion_strategy(prices: pd.DataFrame, returns: pd.DataFrame,
                             lookback_window: int = 50, z_score_threshold: float = 1.5) -> np.ndarray:
    """
    Mean-reversion strategy based on z-score of price deviation from moving average.
    Independent of covariance-based methods - uses only price statistics.
    """
    n_assets = len(returns.columns)
    weights = np.zeros(n_assets)
    scores = []
    
    cash_col_idx = None
    if 'CASH' in returns.columns:
        cash_col_idx = returns.columns.get_loc('CASH')
    
    for i, col in enumerate(returns.columns):
        if i == cash_col_idx:
            scores.append(0.0)
            continue
        
        if len(prices[col]) < lookback_window:
            scores.append(0.0)
            continue
        
        ma = prices[col].rolling(window=lookback_window).mean().iloc[-1]
        std = prices[col].rolling(window=lookback_window).std().iloc[-1]
        current_price = prices[col].iloc[-1]
        
        if std > 0:
            z_score = (current_price - ma) / std
        else:
            z_score = 0.0
        
        if z_score < -z_score_threshold:
            score = abs(z_score)
        elif z_score > z_score_threshold:
            score = 0.1
        else:
            score = max(0.2, 1.0 - abs(z_score))
        
        scores.append(score)
    
    total_score = sum(scores)
    
    if total_score > 0:
        score_idx = 0
        for i in range(n_assets):
            if i == cash_col_idx:
                continue
            weights[i] = scores[score_idx] / total_score
            score_idx += 1
        
        weights = weights * 0.80
        
        if cash_col_idx is not None:
            weights[cash_col_idx] = 1.0 - weights.sum()
    else:
        weights = np.ones(n_assets) / n_assets
    
    return weights


__all__ = ['PortfolioOptimizer', 'trend_following_strategy', 'mean_reversion_strategy']


def main():
    """Self-test: verifies the fixes."""
    np.random.seed(42)
    n_assets = 5
    returns = pd.DataFrame(
        np.random.randn(1000, n_assets) * 0.01,
        columns=['BTC', 'ETH', 'SOL', 'BNB', 'XRP']
    )
    cov_matrix = returns.cov().values * 24 * 365
    expected_returns = returns.mean().values * 24 * 365
    optimizer = PortfolioOptimizer(n_assets, list(returns.columns))

    print("\n=== CVaR Optimization (with 10% limit) ===")
    cvar_weights = optimizer.cvar_optimization(returns.values, cvar_limit=0.10)
    print("weights:", cvar_weights, "sum:", cvar_weights.sum())

    print("\n=== Risk Parity ===")
    rp_weights = optimizer.risk_parity(cov_matrix)
    print("weights:", rp_weights)

    print("\n=== MVO (with historical returns, rf=0%) ===")
    mvo_weights = optimizer.mean_variance_optimization(expected_returns, cov_matrix, 
                                                        risk_free_rate=0.0, method='max_sharpe')
    print("weights:", mvo_weights)


if __name__ == "__main__":
    main()
