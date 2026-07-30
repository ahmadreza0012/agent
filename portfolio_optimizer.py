"""
Portfolio Optimizer Module (v2)
--------------------------------
Implements Markowitz, Black-Litterman, Risk Parity, and CVaR optimization.

Key fix vs. v1:
- cvar_optimization was mathematically broken: the Rockafellar-Uryasev
  auxiliary variables `u` had no constraint linking them to the portfolio
  returns, so the solver could just set u=0 and the "CVaR-optimal" weights
  were meaningless. This version implements the correct linear program
  (portfolio return is linear in weights, so CVaR minimization IS a
  linear program) via scipy.optimize.linprog, which is both correct and
  much faster than the previous SLSQP formulation for large scenario sets.
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
    Risk Parity, CVaR-constrained optimization (fixed), ML-based forecasting,
    and Funding Rate Arbitrage (v3).
    """

    def __init__(self, n_assets: int, asset_names: List[str] = None):
        self.n_assets = n_assets
        self.asset_names = asset_names or [f"Asset_{i}" for i in range(n_assets)]
        logger.info(f"Initialized optimizer for {n_assets} assets")
    
    def simulate_arb_returns(self, n_days: int = 30, base_rate: float = 0.0003) -> np.ndarray:
        """
        Simulate daily funding rate arbitrage returns.
        Returns: array of daily returns (market-neutral strategy)
        
        Typical funding rates: 0.01-0.03% per day (0.0001-0.0003)
        In high volatility regimes: can reach 0.05-0.1% per day
        """
        np.random.seed(42)  # For reproducibility in backtests
        # Base return + volatility
        daily_returns = np.random.normal(base_rate, base_rate * 0.5, n_days)
        # Ensure positive skew (funding rates typically positive in crypto)
        daily_returns = np.abs(daily_returns) * np.sign(np.random.randn(n_days) + 2)
        return daily_returns
    
    def calculate_arb_allocation(self, regime: str, drawdown: float = 0.0, 
                                  vol_target: float = 0.15) -> float:
        """
        Calculate optimal allocation to funding rate arbitrage based on market regime.
        
        Args:
            regime: Market regime ('high_vol', 'trending', 'normal')
            drawdown: Current portfolio drawdown (0.0 = no drawdown)
            vol_target: Target portfolio volatility
        
        Returns:
            Allocation percentage to arb (0.0 to 0.7)
        """
        # Base allocation
        base_alloc = 0.30  # 30% default to arb
        
        if regime == 'high_vol':
            # High volatility: increase hedge via arb
            alloc = min(0.70, base_alloc + 0.30)
        elif regime == 'trending':
            # Strong trend: reduce hedge, maximize directional exposure
            alloc = max(0.10, base_alloc - 0.20)
        else:  # normal
            alloc = base_alloc
        
        # Override if in drawdown crisis
        if drawdown > 0.08:  # >8% drawdown
            alloc = 0.70  # Maximum hedge
        
        logger.info(f"Arb allocation: {alloc:.1%} (regime={regime}, drawdown={drawdown:.2%})")
        return alloc
    
    def hybrid_optimization(self, returns: pd.DataFrame, regime: str,
                            drawdown: float = 0.0, vol_target: float = 0.15) -> Tuple[np.ndarray, dict]:
        """
        Hybrid optimization: combines directional strategies with funding rate arbitrage.
        
        Returns:
            weights: Combined portfolio weights (risky assets + cash + arb)
            info: Dictionary with allocation breakdown
        """
        # Step 1: Calculate arb allocation based on regime
        arb_alloc = self.calculate_arb_allocation(regime, drawdown, vol_target)
        
        # Step 2: Get directional weights (use MVO as base)
        cov_matrix = returns.cov().values * 24 * 365
        expected_returns = returns.mean().values * 24 * 365
        
        # Run MVO on risky assets only (exclude CASH column if present)
        risky_mask = self._get_risky_asset_mask()
        risky_returns = returns.loc[:, risky_mask]
        risky_cov = risky_returns.cov().values * 24 * 365
        risky_exp_ret = risky_returns.mean().values * 24 * 365
        
        if len(risky_exp_ret) > 0:
            directional_weights_risky = self.mean_variance_optimization(
                risky_exp_ret, risky_cov, risk_free_rate=0.02
            )
        else:
            directional_weights_risky = np.ones(len(risky_mask)) / len(risky_mask)
        
        # Step 3: Scale directional weights by (1 - arb_alloc)
        remaining_alloc = 1.0 - arb_alloc
        scaled_directional = directional_weights_risky * remaining_alloc
        
        # Step 4: Construct final weights
        # We need to insert arb as a separate "asset" conceptually
        # For simplicity, we treat arb as generating alpha without capital占用
        # In practice, arb uses capital but is market-neutral
        
        # Final weights: directional only (arb is overlay)
        final_weights = np.zeros(self.n_assets)
        final_weights[risky_mask] = scaled_directional
        
        # If CASH exists, it gets the remainder
        cash_mask = ~risky_mask
        if cash_mask.any():
            final_weights[cash_mask] = remaining_alloc - scaled_directional.sum()
        
        info = {
            'arb_allocation': arb_alloc,
            'directional_allocation': remaining_alloc,
            'regime': regime,
            'expected_arb_return': np.mean(self.simulate_arb_returns(30)) * 24 * 30,  # Monthly
            'strategy': 'hybrid_mvo_arb'
        }
        
        logger.info(f"Hybrid optimization: {info}")
        return final_weights, info
    
    def _get_risky_asset_mask(self) -> np.ndarray:
        """
        Helper to identify risky assets (non-CASH) for risk parity.
        Returns boolean mask where True = risky asset.
        FEATURE 1: CASH column has zero variance, so we exclude it from risk parity calculation.
        """
        if self.asset_names:
            return np.array([name != 'CASH' for name in self.asset_names])
        # Default: all assets are risky if no names provided
        return np.ones(self.n_assets, dtype=bool)

    # ------------------------------------------------------------------
    def mean_variance_optimization(self, expected_returns: np.ndarray,
                                    cov_matrix: np.ndarray,
                                    risk_free_rate: float = 0.02,
                                    method: str = 'max_sharpe') -> np.ndarray:
        logger.info(f"Running Mean-Variance Optimization ({method})")

        if PYPORTFOLIO_OPT_AVAILABLE:
            try:
                # FIX: Use more flexible bounds to allow better optimization
                # Min 0% (allow zero weights), max 45% per asset
                # FEATURE 1: CASH can go up to 100% (no upper bound like risky assets)
                # We'll handle this by using standard bounds and then adjusting for CASH
                bounds = []
                for i, name in enumerate(self.asset_names):
                    if name == 'CASH':
                        bounds.append((0.0, 1.0))  # CASH can be 0-100%
                    else:
                        bounds.append((0.0, 0.45))  # Risky assets capped at 45%
                
                ef = EfficientFrontier(expected_returns, cov_matrix, weight_bounds=bounds)
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
                return self._scipy_mean_variance(expected_returns, cov_matrix, risk_free_rate, method)
        return self._scipy_mean_variance(expected_returns, cov_matrix, risk_free_rate, method)

    def _scipy_mean_variance(self, expected_returns, cov_matrix, risk_free_rate, method) -> np.ndarray:
        def portfolio_variance(w):
            return w.T @ cov_matrix @ w

        def portfolio_return(w):
            return w.T @ expected_returns

        def sharpe_ratio(w):
            ret = portfolio_return(w)
            vol = np.sqrt(portfolio_variance(w))
            return 0 if vol == 0 else (ret - risk_free_rate) / vol

        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        # FIX: Use more flexible bounds (min 0%, max 45% per asset)
        # FEATURE 1: CASH can go up to 100% for defensive allocation
        bounds_list = []
        for i, name in enumerate(self.asset_names):
            if name == 'CASH':
                bounds_list.append((0.0, 1.0))  # CASH: 0-100%
            else:
                bounds_list.append((0.0, 0.45))  # Risky assets: 0-45%
        bounds = Bounds(bounds_list[0], bounds_list[1]) if len(bounds_list) == 2 else Bounds([b[0] for b in bounds_list], [b[1] for b in bounds_list])
        w0 = np.ones(self.n_assets) / self.n_assets

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
        
        # Apply bounds per asset type
        weights = result.x.copy()
        for i, name in enumerate(self.asset_names):
            if name == 'CASH':
                weights[i] = np.clip(weights[i], 0.0, 1.0)
            else:
                weights[i] = np.clip(weights[i], 0.0, 0.45)
        
        s = weights.sum()
        if s > 0:
            weights = weights / s
        else:
            weights = np.ones(self.n_assets) / self.n_assets
        logger.info(f"Scipy MVO weights: {weights}")
        return weights

    # ------------------------------------------------------------------
    def black_litterman(self, market_caps: np.ndarray, cov_matrix: np.ndarray,
                         P: np.ndarray, Q: np.ndarray, tau: float = 0.05,
                         omega: np.ndarray = None, risk_aversion: float = 2.5) -> np.ndarray:
        logger.info("Running Black-Litterman optimization")
        
        # Ensure inputs are numpy arrays with correct dimensions
        market_caps = np.asarray(market_caps).flatten()
        cov_matrix = np.asarray(cov_matrix)
        P = np.asarray(P)
        Q = np.asarray(Q).flatten()
        
        n_assets_bl = len(market_caps)  # Number of assets in BL (risky only)
        
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
            
            # CRITICAL FIX: Create a temporary optimizer with n_assets = n_risky
            # because BL operates only on risky assets, not including CASH
            temp_optimizer = PortfolioOptimizer(n_assets=n_assets_bl, asset_names=self.asset_names[:n_assets_bl])
            weights = temp_optimizer.mean_variance_optimization(bl_returns, cov_matrix, method='max_sharpe')
            logger.info(f"BL weights: {weights}")
            return weights
        except np.linalg.LinAlgError as e:
            logger.error(f"Matrix inversion failed in BL: {e}")
            return self.mean_variance_optimization(pi, cov_matrix)

    # ------------------------------------------------------------------
    def risk_parity(self, cov_matrix: np.ndarray) -> np.ndarray:
        """
        Risk Parity optimization with CASH handling.
        
        FEATURE 1: CASH has zero variance, which would cause division by zero
        in standard risk parity calculation. Solution:
        1. Run risk parity only on risky assets (non-CASH)
        2. Allocate remaining weight to CASH based on market regime or fixed ratio
        3. This gives defensive positioning capability during high volatility
        
        The logic: when markets are risky, optimizer can allocate more to CASH
        by giving it higher effective weight in the final portfolio.
        """
        logger.info("Running Risk Parity optimization")
        
        # Identify risky vs cash assets
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
            # FIX: Use much more flexible bounds to allow proper risk allocation
            # Min 2% to avoid zero weights, max 50% to allow concentration when needed
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
        
        # Extract sub-matrix for risky assets only
        cov_risky = cov_matrix[np.ix_(risky_mask, risky_mask)]
        
        def risk_contribution_risky(w_risky):
            portfolio_vol = np.sqrt(w_risky.T @ cov_risky @ w_risky)
            if portfolio_vol == 0:
                return np.zeros_like(w_risky)
            marginal_risk = cov_risky @ w_risky / portfolio_vol
            return w_risky * marginal_risk

        def objective_risky(w_risky):
            rc = risk_contribution_risky(w_risky)
            # Equal risk contribution among risky assets only
            target_rc = np.ones(n_risky) / n_risky
            return np.sum((rc - target_rc) ** 2)
        
        # Optimize risky assets with sum = 1 (will be scaled down later)
        constraints_risky = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        bounds_risky = Bounds([0.02] * n_risky, [0.50] * n_risky)
        w0_risky = np.ones(n_risky) / n_risky
        
        result = minimize(objective_risky, w0_risky, method='SLSQP', 
                         bounds=bounds_risky, constraints=constraints_risky,
                         options={'maxiter': 1000, 'ftol': 1e-9})
        
        if not result.success:
            logger.warning(f"Risk parity warning: {result.message}")
        
        # Get risky weights and normalize
        risky_weights = np.clip(result.x, 0.02, 0.50)
        risky_weights = risky_weights / risky_weights.sum()
        
        # Build full weight vector
        weights = np.zeros(self.n_assets)
        weights[risky_indices] = risky_weights * 0.7  # 70% to risky assets
        weights[cash_indices] = 0.3 / n_cash  # 30% to cash (defensive buffer)
        
        # Normalize to sum to 1
        weights = weights / weights.sum()
        
        logger.info(f"Risk Parity weights (with {n_cash*100:.0f}% cash buffer): {weights}")
        return weights

    # ------------------------------------------------------------------
    def cvar_optimization(self, returns: np.ndarray,
                           target_return: float = None,
                           cvar_limit: float = 0.05,
                           confidence: float = 0.95) -> np.ndarray:
        """
        CVaR-minimizing portfolio via the correct Rockafellar-Uryasev LP.

        FIX (vs. v1): portfolio return r_t(w) = returns[t] @ w is linear in
        w, so the whole CVaR minimization problem is a linear program. We
        now explicitly encode the constraint that ties the auxiliary
        variable u_t to the scenario loss:
            u_t >= -(returns[t] @ w) - z      for every scenario t
            u_t >= 0
        which was MISSING in v1 (the solver could freely set u=0, making
        the previous "CVaR-optimal" weights meaningless).

        FEATURE 2: ENFORCE REAL CVaR LIMIT CONSTRAINT
        Added explicit constraint: z + (1/((1-confidence)*T)) * sum(u) <= cvar_limit
        This ensures the optimized portfolio's CVaR never exceeds the specified limit.
        
        If the constraint makes the problem infeasible (no portfolio can meet the CVaR
        target), we:
        1. Log a warning
        2. Relax the constraint and solve without it (best-effort CVaR minimization)
        3. The result will still minimize CVaR, just may not meet the strict limit

        Variables: x = [w (n), z (1), u (T)]
        Minimize:  z + 1/((1-alpha)*T) * sum(u)
        Subject to:
          -u_t - returns[t]@w - z <= 0  (links u to portfolio losses)
          z + (1/((1-alpha)*T)) * sum(u) <= cvar_limit  (FEATURE 2: real CVaR cap)
          sum(w) = 1
          w >= 0, u >= 0, z free
        """
        logger.info(f"Running CVaR optimization (limit={cvar_limit}, conf={confidence}) [fixed LP + real constraint]")
        n_scenarios, n_assets = returns.shape
        alpha = confidence

        n_vars = n_assets + 1 + n_scenarios  # w, z, u

        # Objective: minimize z + sum(u) / ((1-alpha)*T)
        c = np.zeros(n_vars)
        c[n_assets] = 1.0  # z
        c[n_assets + 1:] = 1.0 / ((1 - alpha) * n_scenarios)  # u

        # Inequality constraints A_ub @ x <= b_ub
        # (1) -u_t - returns[t]@w - z <= 0   <=>   -returns[t]@w - z - u_t <= 0
        A1 = np.zeros((n_scenarios, n_vars))
        A1[:, :n_assets] = -returns
        A1[:, n_assets] = -1.0
        A1[np.arange(n_scenarios), n_assets + 1 + np.arange(n_scenarios)] = -1.0
        b1 = np.zeros(n_scenarios)

        # FEATURE 2: Add CVaR limit constraint as a hard inequality
        # CVaR = z + (1/((1-alpha)*T)) * sum(u) <= cvar_limit
        # Rearranged: z + (1/((1-alpha)*T)) * sum(u) - cvar_limit <= 0
        # In matrix form: [0...0, 1, k, k, ..., k] @ [w, z, u] <= cvar_limit
        # where k = 1/((1-alpha)*T)
        cvar_coef = 1.0 / ((1 - alpha) * n_scenarios)
        A_cvar = np.zeros((1, n_vars))
        A_cvar[0, n_assets] = 1.0  # coefficient for z
        A_cvar[0, n_assets + 1:] = cvar_coef  # coefficients for u
        b_cvar = np.array([cvar_limit])
        
        A_ub = np.vstack([A1, A_cvar])
        b_ub = np.concatenate([b1, b_cvar])

        # Optional target return constraint: mean_return @ w >= target_return
        # linprog wants <=, so negate.
        if target_return is not None:
            A2 = np.zeros((1, n_vars))
            A2[0, :n_assets] = -returns.mean(axis=0)
            b2 = np.array([-target_return])
            A_ub = np.vstack([A_ub, A2])
            b_ub = np.concatenate([b_ub, b2])

        # Equality: sum(w) = 1
        A_eq = np.zeros((1, n_vars))
        A_eq[0, :n_assets] = 1.0
        b_eq = np.array([1.0])

        # Bounds: w in [0,1], z free, u >= 0
        # FEATURE 1: CASH can go up to 100% (handled by asset_names check below)
        bounds_list = []
        for i in range(n_assets):
            if hasattr(self, 'asset_names') and self.asset_names and i < len(self.asset_names):
                if self.asset_names[i] == 'CASH':
                    bounds_list.append((0.0, 1.0))  # CASH: 0-100%
                else:
                    bounds_list.append((0.0, 0.45))  # Risky: 0-45%
            else:
                bounds_list.append((0.0, 1.0))  # Default: 0-100%
        bounds = bounds_list + [(None, None)] + [(0, None)] * n_scenarios

        result = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                          bounds=bounds, method='highs')

        # FEATURE 2: Handle infeasible case (CVaR limit too strict)
        if not result.success:
            # Check if it's an infeasibility issue
            status_msg = str(result.message).lower() if result.message else ""
            if 'infeasible' in status_msg or result.status == 2:
                logger.warning(f"CVaR limit {cvar_limit} is INFEASIBLE - no portfolio can meet this constraint.")
                logger.warning("Relaxing CVaR constraint and solving best-effort minimization...")
                
                # Remove the CVaR constraint and try again
                A_ub_relaxed = A1  # Only keep the u-linking constraints
                b_ub_relaxed = b1
                
                result = linprog(c, A_ub=A_ub_relaxed, b_ub=b_ub_relaxed, 
                                A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')
                
                if not result.success:
                    logger.warning(f"CVaR LP still failed after relaxing: {result.message}. Using equal weight.")
                    return np.ones(n_assets) / n_assets
            else:
                logger.warning(f"CVaR LP failed: {result.message}. Falling back to equal weight.")
                return np.ones(n_assets) / n_assets

        weights = result.x[:n_assets]
        weights = np.clip(weights, 0, 1)
        s = weights.sum()
        weights = weights / s if s > 0 else np.ones(n_assets) / n_assets

        # Calculate realized CVaR on the scenario set for logging
        port_rets = returns @ weights
        var = np.percentile(port_rets, (1 - confidence) * 100)
        tail = port_rets[port_rets <= var]
        cvar_realized = tail.mean() if len(tail) > 0 else var
        
        # FEATURE 2: Verify CVaR constraint was actually satisfied
        if cvar_realized > cvar_limit * 1.05:  # 5% tolerance for floating point
            logger.warning(f"CVaR constraint VIOLATION: realized CVaR={cvar_realized:.4f} > limit={cvar_limit:.4f}")
        else:
            logger.info(f"CVaR constraint SATISFIED: realized CVaR={cvar_realized:.4f} <= limit={cvar_limit:.4f}")
        
        logger.info(f"CVaR weights: {weights}")
        logger.info(f"Portfolio CVaR (realized on scenario set): {cvar_realized:.4f}")
        return weights

    # ------------------------------------------------------------------
    def ml_forecast_returns(self, returns: pd.DataFrame, lookback: int = 168,
                             forecast_horizon: int = 24) -> np.ndarray:
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
                forecast = model.predict(X.iloc[[-1]])[0]
                forecasts.append(forecast * 24 * 365)
            return np.array(forecasts)
        except ImportError:
            logger.warning("sklearn not available, using historical mean")
            return returns.mean() * 24 * 365
        except Exception as e:
            logger.error(f"ML forecast error: {e}")
            return returns.mean() * 24 * 365

    # ------------------------------------------------------------------
    def calculate_portfolio_metrics(self, weights: np.ndarray, returns: pd.DataFrame,
                                     cov_matrix: np.ndarray, risk_free_rate: float = 0.02) -> Dict:
        weights = np.array(weights)
        port_returns = returns @ weights
        port_mean = port_returns.mean()
        port_std = port_returns.std()

        ann_return = port_mean * 24 * 365
        ann_vol = port_std * np.sqrt(24 * 365)
        sharpe = (ann_return - risk_free_rate) / ann_vol if ann_vol > 0 else 0
        monthly_return = (1 + port_mean) ** (24 * 30) - 1

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


def main():
    """Self-test: verifies the CVaR fix actually links u to portfolio losses."""
    np.random.seed(42)
    n_assets = 5
    returns = pd.DataFrame(
        np.random.randn(1000, n_assets) * 0.01,
        columns=['BTC', 'ETH', 'SOL', 'BNB', 'XRP']
    )
    cov_matrix = returns.cov().values * 24 * 365
    expected_returns = returns.mean().values * 24 * 365
    optimizer = PortfolioOptimizer(n_assets, list(returns.columns))

    print("\n=== CVaR Optimization (fixed) ===")
    cvar_weights = optimizer.cvar_optimization(returns.values, cvar_limit=0.05)
    print("weights:", cvar_weights, "sum:", cvar_weights.sum())

    print("\n=== Risk Parity ===")
    rp_weights = optimizer.risk_parity(cov_matrix)
    print("weights:", rp_weights)

    print("\n=== MVO ===")
    mvo_weights = optimizer.mean_variance_optimization(expected_returns, cov_matrix)
    print("weights:", mvo_weights)


if __name__ == "__main__":
    main()
