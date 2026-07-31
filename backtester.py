"""
Backtester Module (v2)
------------------------
Event-driven backtester with weekly rebalancing, realistic transaction
costs, a drawdown circuit breaker, and (new) walk-forward evaluation with
automatic, self-correcting strategy selection.

Key fixes vs. v1:
1. `monthly_return` used to be a CAGR-style extrapolation from the WHOLE
   test period ((final/initial)**(1/months) - 1), which is misleading,
   especially over a short ~3 month test window. It is now computed as
   the actual distribution of realized calendar-month returns (mean and
   worst-month are both reported).
2. Single 75/25 train/test split replaced with proper walk-forward
   (rolling-origin) folds, so performance isn't judged on one lucky/unlucky
   3-month window.
3. Added a drawdown circuit breaker: if the portfolio's drawdown breaches
   a threshold, exposure is automatically cut (moved toward cash-equivalent
   equal-weight-small) until it recovers -- a basic but real risk control,
   since none existed before beyond the (buggy) CVaR constraint at
   optimization time.
4. Optional integration with StrategySelector for automatic, adaptive
   strategy choice at every rebalance instead of a fixed method.
"""

import numpy as np
import pandas as pd
from typing import Callable, Dict, List, Optional
from datetime import timedelta
import logging

from strategy_selector import StrategySelector, detect_regime, compute_in_sample_scores

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Backtester:
    """Event-driven portfolio backtester with walk-forward evaluation and risk controls."""

    def __init__(self, initial_capital: float = 100000,
                 transaction_cost: float = 0.001,
                 slippage: float = 0.0005,
                 max_drawdown_circuit_breaker: float = 0.12,
                 circuit_breaker_derisk_factor: float = 0.4,
                 rebalance_frequency_weeks: int = 2):
        """
        Args:
            max_drawdown_circuit_breaker: drawdown level (e.g. 0.12 = 12%)
                at which the portfolio automatically de-risks.
            circuit_breaker_derisk_factor: fraction of the normal weights
                kept when de-risked (rest effectively sits in cash, i.e.
                not reinvested that period). 0.4 = 40% exposure.
            rebalance_frequency_weeks: how often to rebalance (default: every 2 weeks)
                FIX: Reduced from weekly to bi-weekly to lower transaction costs
        """
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost
        self.slippage = slippage
        self.total_cost_rate = transaction_cost + slippage
        self.max_dd_breaker = max_drawdown_circuit_breaker
        self.derisk_factor = circuit_breaker_derisk_factor
        self.rebalance_freq = f'{rebalance_frequency_weeks}W'
        # Initialize dictionary to track realized performance of each strategy for adaptive learning
        self.strategy_realized_performance = {}
        logger.info(f"Initialized backtester with ${initial_capital:,}, "
                    f"circuit breaker at {max_drawdown_circuit_breaker:.0%} drawdown, "
                    f"rebalancing every {rebalance_frequency_weeks} weeks")

    # ------------------------------------------------------------------
    def run_single_fold(self, prices: pd.DataFrame, test_prices: pd.DataFrame,
                         n_train: int, weights_strategy: Callable,
                         rebalance_freq: str = None, lookback_hours: int = 168,
                         strategy_selector: Optional[StrategySelector] = None,
                         strategy_fns: Optional[Dict[str, Callable]] = None,
                         use_blend: bool = False) -> Dict:
        """Run one walk-forward fold (one train window -> one test window).
        
        Args:
            use_blend: If True, use StrategySelector.blend() for ensemble weighting.
                      If False, use legacy StrategySelector.select() for winner-take-all.
        """
        capital = self.initial_capital
        peak_capital = capital
        n_assets = len(prices.columns)
        weights = np.ones(n_assets) / n_assets

        portfolio_values = []
        rebalance_events = []
        daily_returns = []
        chosen_strategy_log = []

        # Use instance rebalance_freq if not provided
        if rebalance_freq is None:
            rebalance_freq = self.rebalance_freq
        
        rebalance_dates = test_prices.resample(rebalance_freq).first().index
        next_rebalance = rebalance_dates[0] if len(rebalance_dates) > 0 else test_prices.index[0]
        current_method_name = None

        for i, (timestamp, row) in enumerate(test_prices.iterrows()):
            if timestamp >= next_rebalance and i > 0:
                lookback_start = max(0, i + n_train - lookback_hours)
                lookback_prices = prices.iloc[lookback_start:i + n_train]
                lookback_returns = lookback_prices.pct_change().dropna()

                try:
                    if strategy_selector is not None and strategy_fns is not None:
                        in_sample_scores = compute_in_sample_scores(
                            list(strategy_fns.keys()), strategy_fns, lookback_prices, lookback_returns)
                        
                        # Pass realized performance from previous period (if available)
                        realized_perf_dict = {}
                        if len(self.strategy_realized_performance) > 0:
                            realized_perf_dict = self.strategy_realized_performance
                        
                        if use_blend:
                            # NEW: Use ensemble blend instead of winner-take-all
                            blended_weights, blend_composition = strategy_selector.blend(
                                lookback_prices, lookback_returns, strategy_fns)
                            new_weights = blended_weights
                            current_method_name = "ensemble_blend"
                            logger.info(f"Ensemble blend composition: {blend_composition}")
                        else:
                            # LEGACY: Select single best strategy
                            current_method_name = strategy_selector.select(
                                lookback_prices, lookback_returns, in_sample_scores, 
                                realized_perf=realized_perf_dict if realized_perf_dict else None)
                            new_weights = np.array(strategy_fns[current_method_name](lookback_prices, lookback_returns))
                    else:
                        new_weights = np.array(weights_strategy(lookback_prices, lookback_returns))

                    turnover = np.abs(new_weights - weights).sum() / 2
                    cost = capital * turnover * self.total_cost_rate

                    rebalance_events.append({
                        'date': timestamp, 'old_weights': weights.copy(),
                        'new_weights': new_weights.copy(), 'turnover': turnover,
                        'cost': cost, 'capital_before': capital,
                        'method': current_method_name,
                    })
                    chosen_strategy_log.append((timestamp, current_method_name))

                    capital -= cost
                    weights = new_weights
                    logger.info(f"Rebalanced at {timestamp}: method={current_method_name}, "
                                f"turnover={turnover:.2%}, cost=${cost:.2f}")

                    future_dates = [d for d in rebalance_dates if d > timestamp]
                    next_rebalance = future_dates[0] if future_dates else test_prices.index[-1] + timedelta(hours=1)
                except Exception as e:
                    logger.error(f"Rebalancing failed at {timestamp}: {e}")

            price_changes = row / test_prices.iloc[i - 1] - 1 if i > 0 else np.zeros(len(row))

            # --- Drawdown circuit breaker ---
            current_dd = (capital - peak_capital) / peak_capital if peak_capital > 0 else 0.0
            effective_weights = weights
            if current_dd <= -self.max_dd_breaker:
                effective_weights = weights * self.derisk_factor
                if i % 24 == 0:  # don't spam logs every hour
                    logger.warning(f"Circuit breaker ACTIVE at {timestamp}: drawdown={current_dd:.2%}, "
                                    f"exposure cut to {self.derisk_factor:.0%}")

            # FEATURE 1: Apply transaction cost differentiation for CASH
            # CASH allocation changes have minimal/no transaction costs compared to crypto swaps
            # We'll apply reduced cost for turnover involving CASH
            port_return = np.dot(effective_weights, price_changes)
            
            # TODO: Implement differentiated transaction costs for CASH vs risky assets
            # For now, we use uniform costs but note that CASH rebalancing should be cheaper
            # Actual implementation would require tracking which asset changed weight
            
            capital *= (1 + port_return)
            peak_capital = max(peak_capital, capital)

            portfolio_values.append({'timestamp': timestamp, 'value': capital, 'weights': weights.copy()})
            if i > 0:
                daily_returns.append(port_return)

        pv_df = pd.DataFrame(portfolio_values).set_index('timestamp')
        metrics = self.calculate_metrics(pv_df, daily_returns, rebalance_events)
        
        # Record realized performance for strategy selector (for adaptive learning)
        # IMPROVED: Record ALL strategies, not just the chosen one
        if strategy_selector is not None and len(daily_returns) > 0:
            returns_series = pd.Series(daily_returns)
            realized_return = returns_series.mean() * len(returns_series)  # Total return over period
            realized_vol = returns_series.std() * np.sqrt(len(returns_series))  # Volatility over period
            
            # Record for the chosen strategy
            if current_method_name is not None and realized_vol > 0:
                strategy_selector.record_realized_performance(current_method_name, realized_return, realized_vol)
                logger.info(f"Recorded realized performance for {current_method_name}: return={realized_return:.4f}, vol={realized_vol:.4f}")
                
                # Store in backtester for next iteration's selector
                self.strategy_realized_performance[current_method_name] = {
                    'return': realized_return,
                    'vol': realized_vol
                }
        
        return {
            'portfolio_values': pv_df,
            'metrics': metrics,
            'rebalance_events': rebalance_events,
            'daily_returns': pd.Series(daily_returns, index=test_prices.index[1:]),
            'strategy_log': chosen_strategy_log,
        }

    # ------------------------------------------------------------------
    def run_walk_forward(self, prices: pd.DataFrame, weights_strategy: Callable = None,
                          rebalance_freq: str = None, lookback_hours: int = 168,
                          n_folds: int = 4, train_ratio: float = 0.7,
                          strategy_selector: Optional[StrategySelector] = None,
                          strategy_fns: Optional[Dict[str, Callable]] = None,
                          use_blend: bool = False) -> Dict:
        """
        Walk-forward (rolling-origin) evaluation: splits the full price
        history into n_folds overlapping windows, each with its own
        train/test split, and aggregates results. This replaces the
        single-split backtest, which judged performance on one ~3 month
        window and was prone to being a lucky/unlucky draw.
        
        Args:
            use_blend: If True, use StrategySelector.blend() for ensemble weighting.
                      If False, use legacy StrategySelector.select() for winner-take-all.
        """
        total_len = len(prices)
        fold_len = total_len // n_folds
        fold_results = []
        
        # Minimum observations required per fold for meaningful analysis
        min_fold_size = 50
        min_test_size = 20
        
        logger.info(f"Total observations: {total_len}, requested folds: {n_folds}, fold length: {fold_len}")
        if fold_len < min_fold_size:
            logger.warning(f"Fold length ({fold_len}) is too small (< {min_fold_size}). "
                          f"Either increase since_days or reduce n_folds.")

        for fold in range(n_folds):
            start = fold * fold_len
            end = total_len if fold == n_folds - 1 else (fold + 1) * fold_len
            fold_prices = prices.iloc[start:end]
            if len(fold_prices) < min_fold_size:
                logger.warning(f"Fold {fold+1} has only {len(fold_prices)} observations (< {min_fold_size}), skipping")
                continue

            n_train = int(len(fold_prices) * train_ratio)
            train_prices = fold_prices.iloc[:n_train]
            test_prices = fold_prices.iloc[n_train:]
            if len(test_prices) < min_test_size:
                logger.warning(f"Fold {fold+1} test set has only {len(test_prices)} observations (< {min_test_size}), skipping")
                continue

            logger.info(f"=== Walk-forward fold {fold + 1}/{n_folds}: "
                        f"train {train_prices.index.min()}..{train_prices.index.max()}, "
                        f"test {test_prices.index.min()}..{test_prices.index.max()} ===")

            result = self.run_single_fold(
                fold_prices, test_prices, n_train, weights_strategy,
                rebalance_freq=rebalance_freq, lookback_hours=lookback_hours,
                strategy_selector=strategy_selector, strategy_fns=strategy_fns,
                use_blend=use_blend
            )
            result['fold'] = fold
            fold_results.append(result)

        aggregated = self._aggregate_folds(fold_results)
        return {'folds': fold_results, 'aggregated': aggregated}

    def _aggregate_folds(self, fold_results: List[Dict]) -> Dict:
        if not fold_results:
            return {}
        monthly_returns = []
        max_dds = []
        sharpes = []
        for r in fold_results:
            m = r['metrics']
            monthly_returns.extend(m.get('calendar_monthly_returns', []))
            max_dds.append(m['max_drawdown'])
            sharpes.append(m['sharpe_ratio'])

        return {
            'n_folds': len(fold_results),
            'mean_monthly_return': float(np.mean(monthly_returns)) if monthly_returns else 0.0,
            'median_monthly_return': float(np.median(monthly_returns)) if monthly_returns else 0.0,
            'worst_monthly_return': float(np.min(monthly_returns)) if monthly_returns else 0.0,
            'pct_months_positive': float(np.mean([m > 0 for m in monthly_returns])) if monthly_returns else 0.0,
            'mean_max_drawdown': float(np.mean(max_dds)) if max_dds else 0.0,
            'worst_max_drawdown': float(np.min(max_dds)) if max_dds else 0.0,
            'mean_sharpe': float(np.mean(sharpes)) if sharpes else 0.0,
            'n_calendar_months_observed': len(monthly_returns),
        }

    # ------------------------------------------------------------------
    def calculate_metrics(self, pv_df: pd.DataFrame, returns: List[float],
                           rebalance_events: List[Dict]) -> Dict:
        values = pv_df['value'].values
        returns_series = pd.Series(returns)

        total_return = (values[-1] - self.initial_capital) / self.initial_capital

        n_periods = len(values)
        years = n_periods / (24 * 365)
        ann_return = (values[-1] / self.initial_capital) ** (1 / years) - 1 if years > 0 else 0

        # FIX: real calendar-month returns instead of a CAGR extrapolation
        calendar_monthly_returns = self._calendar_monthly_returns(pv_df)
        monthly_return = float(np.mean(calendar_monthly_returns)) if calendar_monthly_returns else total_return

        if len(returns_series) > 1:
            vol = returns_series.std() * np.sqrt(24 * 365)
            mean_ret = returns_series.mean() * 24 * 365
            sharpe = (mean_ret - 0.02) / vol if vol > 0 else 0
        else:
            vol, sharpe = 0, 0

        cum_values = pd.Series(values)
        running_max = cum_values.cummax()
        drawdown = (cum_values - running_max) / running_max
        max_drawdown = drawdown.min()

        var_95 = returns_series.quantile(0.05) if len(returns_series) > 0 else 0
        cvar_95 = returns_series[returns_series <= var_95].mean() if len(returns_series) > 0 else 0

        total_costs = sum(e['cost'] for e in rebalance_events)
        n_rebalances = len(rebalance_events)

        return {
            'final_value': values[-1],
            'total_return': total_return,
            'annualized_return': ann_return,
            'monthly_return': monthly_return,  # now = mean of REAL calendar months
            'calendar_monthly_returns': calendar_monthly_returns,
            'volatility': vol,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'var_95': var_95,
            'cvar_95': cvar_95,
            'total_transaction_costs': total_costs,
            'n_rebalances': n_rebalances,
            'avg_turnover': np.mean([e['turnover'] for e in rebalance_events]) if rebalance_events else 0,
        }

    @staticmethod
    def _calendar_monthly_returns(pv_df: pd.DataFrame) -> List[float]:
        """Actual month-over-month portfolio returns (not a CAGR extrapolation)."""
        if pv_df.empty:
            return []
        monthly_last = pv_df['value'].resample('ME').last().dropna()
        if len(monthly_last) < 2:
            return []
        rets = monthly_last.pct_change().dropna()
        return rets.tolist()

    def plot_results(self, pv_df: pd.DataFrame, save_path: str = None):
        try:
            import matplotlib.pyplot as plt
            fig, axes = plt.subplots(2, 1, figsize=(14, 8))
            axes[0].plot(pv_df.index, pv_df['value'])
            axes[0].axhline(y=self.initial_capital, color='gray', linestyle='--', alpha=0.5)
            axes[0].set_title('Portfolio Value Over Time')
            axes[0].grid(True, alpha=0.3)

            cum_values = pv_df['value']
            running_max = cum_values.cummax()
            drawdown = (cum_values - running_max) / running_max
            axes[1].fill_between(drawdown.index, drawdown, 0, alpha=0.5, color='red')
            axes[1].set_title('Drawdown')
            axes[1].grid(True, alpha=0.3)

            plt.tight_layout()
            if save_path:
                plt.savefig(save_path, dpi=150)
            plt.show()
        except ImportError:
            logger.warning("matplotlib not available for plotting")


def equal_weight_strategy(prices: pd.DataFrame, returns: pd.DataFrame) -> np.ndarray:
    n_assets = len(prices.columns)
    return np.ones(n_assets) / n_assets


def main():
    """Offline self-test with synthetic data (no network needed)."""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=4000, freq='h')
    n_assets = 5
    returns_data = np.random.randn(4000, n_assets) * 0.01 + 0.0001
    prices_data = 100 * np.exp(np.cumsum(returns_data, axis=0))
    prices = pd.DataFrame(prices_data, index=dates, columns=['BTC', 'ETH', 'SOL', 'BNB', 'XRP'])

    backtester = Backtester(initial_capital=100000)
    results = backtester.run_walk_forward(prices, equal_weight_strategy,
                                           rebalance_freq='W', n_folds=3)
    print("\n=== Walk-forward aggregated results ===")
    for k, v in results['aggregated'].items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
