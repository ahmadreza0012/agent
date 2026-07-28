"""
Main Orchestrator (v2) - Crypto Portfolio Optimization System
================================================================
Pipeline:
1. Data fetching from CoinGecko (real OHLCV, free API, no authentication required)
2. AI sentiment analysis from REAL news headlines (free RSS) + free LLM
   (Groq), with a clearly labeled offline fallback
3. Portfolio optimization: MVO, Black-Litterman, Risk Parity, CVaR (bug
   fixed), ML - with automatic, self-correcting strategy selection
4. Walk-forward backtesting (multiple folds) with a drawdown circuit
   breaker, instead of a single 75/25 split
5. Honest performance evaluation against the 5%/month target

IMPORTANT, READ THIS: this script requires network access (CoinGecko API,
news RSS feeds, optionally Groq) that was NOT available in the sandbox
this was built in. The logic in every module was verified with
synthetic/offline data (see each module's `if __name__ == "__main__"`
block). You must run this yourself, with network access and (optionally)
a free Groq API key exported as GROQ_API_KEY, to get real results on your
machine. Do not trust any number here that you have not personally
reproduced.

DATA SOURCE: The default data source is CoinGecko (set via DATA_SOURCE
environment variable or data_source parameter). CoinGecko provides free
OHLCV data without requiring an API key for basic usage. For higher rate
limits, get a free API key at https://www.coingecko.com/en/api
"""

import logging
import sys
from datetime import datetime
from typing import Dict, Optional

import numpy as np
import pandas as pd

from data_fetcher import DataFetcher
from ai_sentiment import AISentimentAnalyzer
from portfolio_optimizer import PortfolioOptimizer
from backtester import Backtester
from strategy_selector import StrategySelector

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler('portfolio_backtest.log')]
)
logger = logging.getLogger(__name__)

CANDIDATE_METHODS = ['mvo', 'black_litterman', 'risk_parity', 'cvar', 'ml']


class CryptoPortfolioSystem:
    """Complete crypto portfolio optimization system with adaptive strategy selection."""

    def __init__(self, symbols: list = None, initial_capital: float = 100000,
                 groq_api_key: Optional[str] = None, data_source: str = 'coingecko'):
        self.symbols = symbols or ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']
        self.initial_capital = initial_capital
        self.data_source = data_source

        self.data_fetcher = DataFetcher(self.symbols)
        # use_mock=None -> auto-detects: real news+LLM if GROQ_API_KEY is set, mock otherwise
        self.sentiment_analyzer = AISentimentAnalyzer(api_key=groq_api_key, use_mock=None)
        self.optimizer: Optional[PortfolioOptimizer] = None
        self.backtester = Backtester(
            initial_capital=initial_capital,
            transaction_cost=0.001,
            slippage=0.0005,
            max_drawdown_circuit_breaker=0.15,
        )
        self.strategy_selector = StrategySelector(CANDIDATE_METHODS)

        logger.info(f"CryptoPortfolioSystem initialized for {len(self.symbols)} symbols: {self.symbols}")

    # ------------------------------------------------------------------
    def fetch_data(self, timeframe: str = '1h', since_days: int = 365) -> tuple:
        logger.info("=" * 60)
        logger.info(f"STEP 1: Fetching Historical Data ({self.data_source.upper()}, real OHLCV)")
        logger.info("=" * 60)
        raw_data = self.data_fetcher.fetch_all_symbols(timeframe=timeframe, since_days=since_days)
        prices = self.data_fetcher.align_data(raw_data)
        returns = self.data_fetcher.calculate_returns(prices)
        logger.info(f"Data fetched: {prices.index.min()} to {prices.index.max()}, "
                    f"{len(prices)} obs, assets={list(prices.columns)}")
        return prices, returns

    # ------------------------------------------------------------------
    def _build_strategy_fn(self, method: str):
        """Build a (prices, returns) -> weights function for a given method."""
        def strategy(prices: pd.DataFrame, returns: pd.DataFrame) -> np.ndarray:
            n_assets = len(prices.columns)
            asset_names = list(prices.columns)
            if self.optimizer is None or self.optimizer.n_assets != n_assets:
                self.optimizer = PortfolioOptimizer(n_assets, asset_names)

            cov_matrix = returns.cov().values * 24 * 365

            if method == 'mvo':
                expected_returns = returns.mean().values * 24 * 365
                return self.optimizer.mean_variance_optimization(expected_returns, cov_matrix, method='max_sharpe')

            elif method == 'black_litterman':
                market_caps = np.array([1.0, 0.5, 0.2, 0.15, 0.1])[:n_assets]
                market_caps = market_caps / market_caps.sum() * n_assets
                expected_returns = returns.mean().values * 24 * 365
                P, Q = self.sentiment_analyzer.generate_views(prices, expected_returns, asset_names)
                omega = self.sentiment_analyzer.get_confidence_matrix(n_assets, symbols=asset_names)
                weights = self.optimizer.black_litterman(market_caps, cov_matrix, P, Q, omega=omega)
                # Feed back realized outcome next time this is called for self-correction:
                # here we log the *view* direction; actual realized-return feedback happens
                # in evaluate_and_feedback() after we know what happened.
                return weights

            elif method == 'risk_parity':
                return self.optimizer.risk_parity(cov_matrix)

            elif method == 'cvar':
                return self.optimizer.cvar_optimization(returns.values, cvar_limit=0.05, confidence=0.95)

            elif method == 'ml':
                expected_returns = self.optimizer.ml_forecast_returns(returns)
                return self.optimizer.mean_variance_optimization(expected_returns, cov_matrix, method='max_sharpe')

            else:
                return np.ones(n_assets) / n_assets

        return strategy

    def build_all_strategy_fns(self) -> Dict:
        return {m: self._build_strategy_fn(m) for m in CANDIDATE_METHODS}

    # ------------------------------------------------------------------
    def run_walk_forward_backtest(self, prices: pd.DataFrame, n_folds: int = 4,
                                   rebalance_freq: str = 'W', use_auto_selection: bool = True) -> Dict:
        logger.info("=" * 60)
        logger.info(f"STEP 2: Walk-forward backtest ({n_folds} folds), "
                    f"auto strategy selection={use_auto_selection}")
        logger.info("=" * 60)

        strategy_fns = self.build_all_strategy_fns()
        if use_auto_selection:
            results = self.backtester.run_walk_forward(
                prices, weights_strategy=None, rebalance_freq=rebalance_freq,
                lookback_hours=216, n_folds=n_folds,  # margin above the 168h sentiment window (see UPGRADE_NOTES)
                strategy_selector=self.strategy_selector, strategy_fns=strategy_fns,
            )
        else:
            # fixed strategy, for comparison (e.g. 'black_litterman' baseline)
            results = self.backtester.run_walk_forward(
                prices, weights_strategy=strategy_fns['black_litterman'],
                rebalance_freq=rebalance_freq, lookback_hours=216, n_folds=n_folds,  # margin above the 168h sentiment window (see UPGRADE_NOTES)
            )
        return results

    # ------------------------------------------------------------------
    def evaluate_results(self, walk_forward_results: Dict, target_monthly: float = 0.05,
                          max_dd_limit: float = 0.15) -> Dict:
        agg = walk_forward_results.get('aggregated', {})
        if not agg:
            logger.error("No aggregated results (folds too short?). Try a longer since_days or fewer n_folds.")
            return {}

        monthly_return = agg['mean_monthly_return']
        worst_month = agg['worst_monthly_return']
        max_dd = abs(agg['worst_max_drawdown'])

        evaluation = {
            'target_monthly_return': target_monthly,
            'mean_monthly_return': monthly_return,
            'median_monthly_return': agg['median_monthly_return'],
            'worst_monthly_return': worst_month,
            'pct_months_positive': agg['pct_months_positive'],
            'target_achieved_on_average': monthly_return >= target_monthly,
            'target_achieved_every_month': worst_month >= target_monthly,
            'mean_max_drawdown': agg['mean_max_drawdown'],
            'worst_max_drawdown': agg['worst_max_drawdown'],
            'drawdown_within_limit': max_dd <= max_dd_limit,
            'mean_sharpe': agg['mean_sharpe'],
            'n_calendar_months_observed': agg['n_calendar_months_observed'],
            'n_folds': agg['n_folds'],
        }

        logger.info("=" * 60)
        logger.info("STEP 3: Honest Performance Evaluation (walk-forward, out-of-sample)")
        logger.info("=" * 60)
        logger.info(f"Calendar months observed: {evaluation['n_calendar_months_observed']} "
                     f"(more months = more trustworthy conclusion)")
        logger.info(f"Mean monthly return: {monthly_return:.2%} (target {target_monthly:.2%})")
        logger.info(f"Median monthly return: {evaluation['median_monthly_return']:.2%}")
        logger.info(f"Worst monthly return: {worst_month:.2%}")
        logger.info(f"% months positive: {evaluation['pct_months_positive']:.0%}")
        logger.info(f"Worst fold max drawdown: {evaluation['worst_max_drawdown']:.2%} "
                     f"(limit {max_dd_limit:.0%})")
        logger.info(f"Mean Sharpe: {evaluation['mean_sharpe']:.2f}")

        if evaluation['n_calendar_months_observed'] < 6:
            logger.warning("Fewer than 6 calendar months observed out-of-sample: "
                            "treat any conclusion here as PRELIMINARY, not a guarantee.")

        return evaluation

    # ------------------------------------------------------------------
    def run_full_pipeline(self, since_days: int = 365, n_folds: int = 4,
                           use_auto_selection: bool = True) -> Dict:
        logger.info("=" * 60)
        logger.info("CRYPTO PORTFOLIO OPTIMIZATION SYSTEM (v2)")
        logger.info(f"Start Time: {datetime.now().isoformat()}")
        logger.info("=" * 60)
        try:
            prices, returns = self.fetch_data(since_days=since_days)
            wf_results = self.run_walk_forward_backtest(prices, n_folds=n_folds,
                                                          use_auto_selection=use_auto_selection)
            evaluation = self.evaluate_results(wf_results)

            full_results = {
                'prices': prices, 'returns': returns,
                'walk_forward': wf_results, 'evaluation': evaluation,
            }
            logger.info("=" * 60)
            logger.info(f"PIPELINE COMPLETE. End Time: {datetime.now().isoformat()}")
            logger.info("=" * 60)
            return full_results
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise


def print_final_summary(evaluation: Dict):
    if not evaluation:
        print("No evaluation available (see log for errors).")
        return
    print("\n" + "=" * 60)
    print("FINAL ASSESSMENT (walk-forward, out-of-sample, real calendar months)")
    print("=" * 60)
    print(f"\nMonths observed: {evaluation['n_calendar_months_observed']} across {evaluation['n_folds']} folds")
    print(f"Mean monthly return: {evaluation['mean_monthly_return']:.2%} "
          f"(target: {evaluation['target_monthly_return']:.2%})")
    print(f"Median monthly return: {evaluation['median_monthly_return']:.2%}")
    print(f"Worst single month: {evaluation['worst_monthly_return']:.2%}")
    print(f"% months meeting/beating target: computed from pct_months_positive as a proxy = "
          f"{evaluation['pct_months_positive']:.0%} positive")
    print(f"Worst-fold max drawdown: {evaluation['worst_max_drawdown']:.2%}")
    print(f"Mean Sharpe: {evaluation['mean_sharpe']:.2f}")

    print("\nTARGET ACHIEVEMENT:")
    print(f"  5% avg monthly return: {'YES' if evaluation['target_achieved_on_average'] else 'NO'}")
    print(f"  5% EVERY month (worst month too): {'YES' if evaluation['target_achieved_every_month'] else 'NO'}")
    print(f"  Drawdown within 15% limit (worst fold): {'YES' if evaluation['drawdown_within_limit'] else 'NO'}")

    if evaluation['n_calendar_months_observed'] < 6:
        print("\nCAUTION: fewer than 6 calendar months of out-of-sample data were observed. "
              "Do not treat this result as statistically reliable yet — extend since_days "
              "and/or n_folds before trusting these numbers with real capital.")
    print("\n" + "=" * 60)


def main():
    system = CryptoPortfolioSystem(
        symbols=['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'],
        initial_capital=100000,
    )
    results = system.run_full_pipeline(since_days=365, n_folds=4, use_auto_selection=True)
    print_final_summary(results['evaluation'])
    return results


if __name__ == "__main__":
    results = main()
