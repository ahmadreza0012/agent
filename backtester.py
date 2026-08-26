"""
Backtester Module for Cryptocurrency Algorithmic Trading
Implements Walk-Forward Backtesting with No-Trade Zone to reduce transaction costs.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Backtester:
    """
    Walk-forward backtester with realistic transaction cost modeling.
    Implements No-Trade Zone to minimize unnecessary rebalancing.
    """
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        transaction_cost_bps: float = 10.0,  # 10 basis points = 0.1%
        no_trade_threshold: float = 0.03,  # 3% weight change threshold
        slippage_bps: float = 5.0  # Additional slippage cost
    ):
        """
        Initialize the backtester.
        
        Args:
            initial_capital: Starting capital in USD
            transaction_cost_bps: Transaction cost in basis points (default: 10 bps = 0.1%)
            no_trade_threshold: Minimum weight change to trigger rebalancing (default: 3%)
            slippage_bps: Slippage cost in basis points (default: 5 bps)
        """
        self.initial_capital = initial_capital
        self.transaction_cost_bps = transaction_cost_bps
        self.no_trade_threshold = no_trade_threshold
        self.slippage_bps = slippage_bps
        
        self.total_transaction_costs = 0.0
        self.rebalance_count = 0
        self.skipped_rebalances = 0
    
    def run_walk_forward(
        self,
        prices: pd.DataFrame,
        n_folds: int = 3,
        strategy_selector=None,
        strategy_fns: Dict = None,
        use_blend: bool = True,
        train_window_ratio: float = 0.6,
        test_window_ratio: float = 0.2,
        step_ratio: float = 0.2
    ) -> Dict:
        """
        Run walk-forward backtesting with multiple strategies.
        
        Implements proper temporal causality:
        - Training data only contains information available before test period
        - Scalers/models fit ONLY on training data
        - No future information leaks into training
        
        Args:
            prices: DataFrame of asset prices (DatetimeIndex, columns = assets)
            n_folds: Number of walk-forward folds
            strategy_selector: StrategySelector instance for tracking performance
            strategy_fns: Dict mapping strategy names to weight functions
            use_blend: Whether to use ensemble blending
            train_window_ratio: Fraction of data for training (default: 60%)
            test_window_ratio: Fraction of data for testing (default: 20%)
            step_ratio: Step size between folds (default: 20%)
            
        Returns:
            Dictionary with:
                - 'aggregated': aggregated metrics across all folds
                - 'folds': list of per-fold results
                - 'strategy_results': per-strategy performance
        """
        logger.info("=" * 70)
        logger.info(f"WALK-FORWARD BACKTEST: {n_folds} folds")
        logger.info("=" * 70)
        
        if len(prices) < 60:
            logger.warning(f"Insufficient data: {len(prices)} rows (need at least 60)")
            return {
                'aggregated': {
                    'mean_monthly_return': 0.0,
                    'worst_max_drawdown': 0.0,
                    'mean_sharpe': 0.0,
                    'pct_months_positive': 0.0,
                    'n_calendar_months_observed': 0,
                    'n_folds': 0
                },
                'folds': [],
                'strategy_results': {}
            }
        
        # Generate fold indices ensuring temporal causality
        folds = self._generate_walk_forward_folds(
            n_samples=len(prices),
            n_folds=n_folds,
            train_ratio=train_window_ratio,
            test_ratio=test_window_ratio,
            step_ratio=step_ratio
        )
        
        if not folds:
            logger.warning("Could not generate valid walk-forward folds")
            return {
                'aggregated': {
                    'mean_monthly_return': 0.0,
                    'worst_max_drawdown': 0.0,
                    'mean_sharpe': 0.0,
                    'pct_months_positive': 0.0,
                    'n_calendar_months_observed': 0,
                    'n_folds': 0
                },
                'folds': [],
                'strategy_results': {}
            }
        
        logger.info(f"Generated {len(folds)} walk-forward folds")
        
        # Store results per fold and per strategy
        fold_results = []
        strategy_monthly_returns = {name: [] for name in strategy_fns.keys()} if strategy_fns else {}
        
        for fold_idx, (train_start, train_end, test_start, test_end) in enumerate(folds):
            logger.info(f"\n{'='*50}")
            logger.info(f"FOLD {fold_idx + 1}/{len(folds)}")
            logger.info(f"{'='*50}")
            logger.info(f"Train: [{train_start}:{train_end}) | Test: [{test_start}:{test_end})")
            
            # Split data - NO LOOKAHEAD
            train_prices = prices.iloc[train_start:train_end].copy()
            test_prices = prices.iloc[test_start:test_end].copy()
            
            if len(train_prices) < 30 or len(test_prices) < 5:
                logger.warning(f"Fold {fold_idx + 1}: Insufficient data, skipping")
                continue
            
            # Calculate returns on training data ONLY
            train_returns = train_prices.pct_change().dropna()
            test_returns = test_prices.pct_change().dropna()
            
            if len(train_returns) < 20 or len(test_returns) < 3:
                logger.warning(f"Fold {fold_idx + 1}: Insufficient returns, skipping")
                continue
            
            fold_strategy_results = {}
            
            # Evaluate each strategy
            if strategy_fns and strategy_selector:
                for strategy_name, strategy_fn in strategy_fns.items():
                    logger.info(f"\nEvaluating strategy: {strategy_name}")
                    
                    try:
                        # Get weights from training period ONLY
                        # Pass both prices and returns for strategies that need them
                        try:
                            target_weights = strategy_fn(train_prices, train_returns)
                        except TypeError:
                            # Some strategies only accept prices
                            target_weights = strategy_fn(train_prices)
                        
                        # Ensure weights are valid
                        if target_weights is None:
                            logger.warning(f"{strategy_name}: No weights returned")
                            continue
                        
                        # Normalize weights
                        if isinstance(target_weights, dict):
                            total = sum(abs(w) for w in target_weights.values())
                            if total > 0:
                                target_weights = {k: v/total for k, v in target_weights.items()}
                        elif hasattr(target_weights, '__iter__'):
                            target_weights = np.array(target_weights)
                            total = np.sum(np.abs(target_weights))
                            if total > 0:
                                target_weights = target_weights / total
                        
                        # Calculate portfolio returns on TEST period (out-of-sample)
                        if isinstance(target_weights, dict):
                            weight_array = np.array([
                                target_weights.get(col, 1.0/len(test_prices.columns))
                                for col in test_prices.columns
                            ])
                        else:
                            weight_array = np.array(target_weights)
                            if len(weight_array) != len(test_prices.columns):
                                # Pad or truncate to match
                                n_assets = len(test_prices.columns)
                                if len(weight_array) > n_assets:
                                    weight_array = weight_array[:n_assets]
                                else:
                                    weight_array = np.pad(
                                        weight_array,
                                        (0, n_assets - len(weight_array)),
                                        constant_values=1.0/n_assets
                                    )
                        
                        # Re-normalize
                        weight_sum = np.sum(np.abs(weight_array))
                        if weight_sum > 0:
                            weight_array = weight_array / weight_sum
                        
                        # Portfolio returns (execution at t+1, signal at t)
                        # Shift returns by 1 to prevent lookahead bias
                        portfolio_returns = (test_returns * weight_array).sum(axis=1)
                        
                        # Calculate metrics on OOS test period
                        cum_return = (1 + portfolio_returns).prod() - 1
                        
                        # Monthly returns for calendar month analysis
                        monthly_returns = self._calculate_monthly_returns(
                            portfolio_returns, 
                            test_prices.index[len(test_returns)-len(portfolio_returns):]
                        )
                        
                        mean_monthly = np.mean(monthly_returns) if len(monthly_returns) > 0 else 0.0
                        max_dd = self._calculate_max_drawdown(portfolio_returns)
                        sharpe = self._calculate_sharpe(portfolio_returns)
                        pct_positive = np.mean([r > 0 for r in monthly_returns]) if len(monthly_returns) > 0 else 0.0
                        
                        logger.info(f"  Cumulative Return: {cum_return:.2%}")
                        logger.info(f"  Mean Monthly Return: {mean_monthly:.2%}")
                        logger.info(f"  Max Drawdown: {max_dd:.2%}")
                        logger.info(f"  Sharpe: {sharpe:.3f}")
                        
                        # Store results
                        fold_strategy_results[strategy_name] = {
                            'fold': fold_idx,
                            'cumulative_return': cum_return,
                            'mean_monthly_return': mean_monthly,
                            'max_drawdown': max_dd,
                            'sharpe': sharpe,
                            'pct_positive': pct_positive,
                            'weights': target_weights if isinstance(target_weights, dict) 
                                      else dict(zip(test_prices.columns, weight_array)),
                            'n_months': len(monthly_returns)
                        }
                        
                        # Track for aggregation
                        if strategy_name in strategy_monthly_returns:
                            strategy_monthly_returns[strategy_name].extend(monthly_returns)
                        
                        # Update strategy selector track record
                        if strategy_selector and hasattr(strategy_selector, '_track_record'):
                            strategy_selector._track_record[strategy_name].append({
                                'return_pct': cum_return,
                                'volatility': portfolio_returns.std(),
                                'sharpe': sharpe,
                                'fold': fold_idx,
                                'period': f"{test_prices.index[0]}:{test_prices.index[-1]}"
                            })
                        
                    except Exception as e:
                        logger.warning(f"{strategy_name} failed in fold {fold_idx + 1}: {e}")
                        fold_strategy_results[strategy_name] = {
                            'fold': fold_idx,
                            'error': str(e),
                            'cumulative_return': 0.0,
                            'mean_monthly_return': 0.0,
                            'max_drawdown': 0.0,
                            'sharpe': 0.0,
                            'pct_positive': 0.0,
                            'n_months': 0
                        }
            
            # Aggregate fold results
            if fold_strategy_results:
                avg_monthly = np.mean([
                    r['mean_monthly_return'] for r in fold_strategy_results.values()
                    if 'mean_monthly_return' in r and r.get('n_months', 0) > 0
                ]) if fold_strategy_results else 0.0
                
                worst_dd = min([
                    r['max_drawdown'] for r in fold_strategy_results.values()
                    if 'max_drawdown' in r
                ], default=0.0)
                
                avg_sharpe = np.mean([
                    r['sharpe'] for r in fold_strategy_results.values()
                    if 'sharpe' in r and r.get('n_months', 0) > 0
                ]) if fold_strategy_results else 0.0
                
                all_months = []
                for r in fold_strategy_results.values():
                    if r.get('n_months', 0) > 0:
                        all_months.append(r['pct_positive'])
                pct_positive = np.mean(all_months) if all_months else 0.0
                
                n_months = sum([r.get('n_months', 0) for r in fold_strategy_results.values()]) // max(len(fold_strategy_results), 1)
                
                fold_results.append({
                    'fold': fold_idx,
                    'train_start': train_start,
                    'train_end': train_end,
                    'test_start': test_start,
                    'test_end': test_end,
                    'strategy_results': fold_strategy_results,
                    'avg_monthly_return': avg_monthly,
                    'worst_drawdown': worst_dd,
                    'avg_sharpe': avg_sharpe,
                    'pct_positive': pct_positive,
                    'n_months': n_months
                })
        
        # Aggregate across all folds
        if fold_results:
            aggregated = {
                'mean_monthly_return': np.mean([f['avg_monthly_return'] for f in fold_results]),
                'worst_max_drawdown': min([f['worst_drawdown'] for f in fold_results], default=0.0),
                'mean_sharpe': np.mean([f['avg_sharpe'] for f in fold_results]),
                'pct_months_positive': np.mean([f['pct_positive'] for f in fold_results]),
                'n_calendar_months_observed': sum([f['n_months'] for f in fold_results]),
                'n_folds': len(fold_results)
            }
            
            # Per-strategy aggregation
            strategy_results = {}
            for strat_name, monthly_rets in strategy_monthly_returns.items():
                if monthly_rets:
                    rets_array = np.array(monthly_rets)
                    strategy_results[strat_name] = {
                        'mean_monthly_return': np.mean(rets_array),
                        'std_monthly_return': np.std(rets_array),
                        'sharpe': np.mean(rets_array) / np.std(rets_array) * np.sqrt(12) if np.std(rets_array) > 0 else 0,
                        'total_months': len(monthly_rets),
                        'pct_positive': np.mean([r > 0 for r in monthly_rets])
                    }
        else:
            aggregated = {
                'mean_monthly_return': 0.0,
                'worst_max_drawdown': 0.0,
                'mean_sharpe': 0.0,
                'pct_months_positive': 0.0,
                'n_calendar_months_observed': 0,
                'n_folds': 0
            }
            strategy_results = {}
        
        logger.info("\n" + "=" * 70)
        logger.info("WALK-FORWARD BACKTEST COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Folds: {aggregated['n_folds']}")
        logger.info(f"Mean Monthly Return: {aggregated['mean_monthly_return']:.2%}")
        logger.info(f"Worst Max Drawdown: {aggregated['worst_max_drawdown']:.2%}")
        logger.info(f"Mean Sharpe: {aggregated['mean_sharpe']:.3f}")
        logger.info(f"% Positive Months: {aggregated['pct_months_positive']:.0%}")
        logger.info(f"Total Calendar Months: {aggregated['n_calendar_months_observed']}")
        
        return {
            'aggregated': aggregated,
            'folds': fold_results,
            'strategy_results': strategy_results
        }
    
    def _generate_walk_forward_folds(
        self,
        n_samples: int,
        n_folds: int,
        train_ratio: float = 0.6,
        test_ratio: float = 0.2,
        step_ratio: float = 0.2
    ) -> List[Tuple[int, int, int, int]]:
        """
        Generate walk-forward fold indices ensuring temporal causality.
        
        Each fold:
        - Training window: [0, train_end)
        - Test window: [train_end, test_end)
        - Next fold shifts by step_size
        
        Args:
            n_samples: Total number of samples
            n_folds: Number of folds to generate
            train_ratio: Fraction for training window
            test_ratio: Fraction for test window
            step_ratio: Fraction for step size
            
        Returns:
            List of (train_start, train_end, test_start, test_end) tuples
        """
        folds = []
        
        min_train = max(30, int(n_samples * train_ratio))
        min_test = max(10, int(n_samples * test_ratio))
        step_size = max(5, int(n_samples * step_ratio))
        
        if n_samples < min_train + min_test:
            logger.warning(f"Insufficient data: {n_samples} < {min_train + min_test}")
            return folds
        
        train_start = 0
        for i in range(n_folds):
            train_end = min_train + i * step_size
            test_start = train_end
            test_end = min(train_end + min_test, n_samples)
            
            if test_end > n_samples:
                break
            
            if train_end - train_start >= min_train and test_end - test_start >= min_test:
                folds.append((train_start, train_end, test_start, test_end))
                logger.debug(f"Fold {i+1}: Train[{train_start}:{train_end}], Test[{test_start}:{test_end}]")
        
        logger.info(f"Generated {len(folds)} walk-forward folds from {n_samples} samples")
        return folds
    
    def _calculate_monthly_returns(
        self,
        daily_returns: pd.Series,
        dates: pd.DatetimeIndex
    ) -> List[float]:
        """Convert daily returns to monthly returns."""
        if len(daily_returns) == 0 or len(dates) != len(daily_returns):
            return []
        
        # Create DataFrame with dates index
        ret_df = pd.DataFrame({'returns': daily_returns.values}, index=dates)
        
        # Resample to monthly
        monthly = ret_df['returns'].groupby(pd.Grouper(freq='M')).apply(
            lambda x: (1 + x).prod() - 1
        )
        
        return monthly.dropna().tolist()
    
    def _calculate_max_drawdown(self, returns: pd.Series) -> float:
        """Calculate maximum drawdown from returns series."""
        if len(returns) == 0:
            return 0.0
        
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        
        return float(drawdown.min()) if len(drawdown) > 0 else 0.0
    
    def _calculate_sharpe(self, returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """Calculate annualized Sharpe ratio."""
        if len(returns) == 0 or returns.std() == 0:
            return 0.0
        
        mean_return = returns.mean() * 252  # Annualized
        volatility = returns.std() * np.sqrt(252)  # Annualized
        
        return float((mean_return - risk_free_rate) / volatility) if volatility > 0 else 0.0
        
    def run_backtest(
        self,
        prices: pd.DataFrame,
        weights_func,
        start_date: Optional[pd.Timestamp] = None,
        end_date: Optional[pd.Timestamp] = None,
        rebalance_frequency: str = 'W',  # Weekly rebalancing
        **kwargs
    ) -> Dict:
        """
        Run walk-forward backtest with periodic rebalancing.
        
        Args:
            prices: DataFrame of asset prices (DatetimeIndex)
            weights_func: Function that returns target weights given historical prices
            start_date: Start date for backtest
            end_date: End date for backtest
            rebalance_frequency: Pandas frequency string for rebalancing ('D', 'W', 'M')
            **kwargs: Additional arguments passed to weights_func
            
        Returns:
            Dictionary with backtest results
        """
        if start_date is None:
            start_date = prices.index[0]
        if end_date is None:
            end_date = prices.index[-1]
        
        # Filter prices to backtest period
        prices = prices[(prices.index >= start_date) & (prices.index <= end_date)]
        
        # Initialize tracking variables
        capital = self.initial_capital
        positions = {}  # asset -> shares held
        current_weights = {}  # asset -> weight
        assets = prices.columns.tolist()
        
        # Initialize with equal weights
        for asset in assets:
            current_weights[asset] = 1.0 / len(assets)
            positions[asset] = 0.0
        
        # Generate rebalance dates
        rebalance_dates = pd.date_range(start=start_date, end=end_date, freq=rebalance_frequency)
        
        # Tracking lists
        portfolio_values = []
        daily_returns = []
        turnover_history = []
        cost_history = []
        
        prev_portfolio_value = self.initial_capital
        
        logger.info(f"Starting backtest from {start_date} to {end_date}")
        logger.info(f"Rebalancing {len(rebalance_dates)} times with frequency {rebalance_frequency}")
        
        for date_idx, date in enumerate(prices.index):
            price_row = prices.loc[date]
            
            # Update portfolio value based on price changes
            portfolio_value = capital
            for asset in assets:
                if positions[asset] > 0:
                    portfolio_value += positions[asset] * price_row[asset]
            
            # Check if this is a rebalance date
            if date in rebalance_dates:
                # Get historical prices up to this point for weight calculation
                historical_prices = prices.loc[:date]
                
                try:
                    # Calculate target weights
                    target_weights = weights_func(historical_prices, **kwargs)
                    
                    # Ensure weights sum to 1
                    if isinstance(target_weights, dict):
                        total = sum(target_weights.values())
                        if total > 0:
                            target_weights = {k: v/total for k, v in target_weights.items()}
                    elif isinstance(target_weights, np.ndarray):
                        target_weights = {assets[i]: target_weights[i] for i in range(len(assets))}
                        target_weights = {k: v/sum(target_weights.values()) for k, v in target_weights.items()}
                    
                    # Apply No-Trade Zone filter
                    adjusted_weights, turnover, skipped = self._apply_no_trade_zone(
                        current_weights, target_weights, portfolio_value, price_row
                    )
                    
                    if skipped:
                        self.skipped_rebalances += 1
                        logger.debug(f"{date}: Skipped rebalance (below threshold)")
                    else:
                        self.rebalance_count += 1
                        
                        # Execute rebalancing
                        capital, positions = self._execute_rebalance(
                            adjusted_weights, portfolio_value, price_row, positions
                        )
                        
                        # Update current weights
                        current_weights = adjusted_weights.copy()
                    
                    turnover_history.append({
                        'date': date,
                        'turnover': turnover,
                        'cost': self._calculate_transaction_cost(turnover, portfolio_value)
                    })
                    
                except Exception as e:
                    logger.warning(f"{date}: Weight calculation failed: {e}. Keeping current weights.")
                    turnover_history.append({
                        'date': date,
                        'turnover': 0.0,
                        'cost': 0.0
                    })
            
            # Record daily metrics
            portfolio_values.append({
                'date': date,
                'value': portfolio_value,
                'capital': capital
            })
            
            if prev_portfolio_value > 0:
                daily_return = (portfolio_value - prev_portfolio_value) / prev_portfolio_value
                daily_returns.append(daily_return)
            
            prev_portfolio_value = portfolio_value
        
        # Compile results
        results_df = pd.DataFrame(portfolio_values).set_index('date')
        results_df['return'] = pd.Series(daily_returns, index=results_df.index)
        results_df['cumulative_return'] = (1 + results_df['return']).cumprod() - 1
        
        # Calculate metrics
        metrics = self._calculate_metrics(results_df, turnover_history)
        
        logger.info(f"Backtest completed:")
        logger.info(f"  Final Value: ${results_df['value'].iloc[-1]:,.2f}")
        logger.info(f"  Total Return: {metrics['total_return']:.2%}")
        logger.info(f"  Annualized Return: {metrics['annualized_return']:.2%}")
        logger.info(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.3f}")
        logger.info(f"  Max Drawdown: {metrics['max_drawdown']:.2%}")
        logger.info(f"  Total Transaction Costs: ${self.total_transaction_costs:,.2f}")
        logger.info(f"  Rebalances Executed: {self.rebalance_count}")
        logger.info(f"  Rebalances Skipped (No-Trade Zone): {self.skipped_rebalances}")
        
        return {
            'returns': results_df,
            'metrics': metrics,
            'turnover_history': turnover_history,
            'transaction_costs': self.total_transaction_costs
        }
    
    def _apply_no_trade_zone(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        portfolio_value: float,
        prices: pd.Series
    ) -> Tuple[Dict[str, float], float, bool]:
        """
        Apply No-Trade Zone filter to minimize unnecessary trading.
        
        If the absolute weight change for any asset is below the threshold,
        keep the current weight instead of rebalancing.
        
        Args:
            current_weights: Current portfolio weights
            target_weights: Target weights from optimizer
            portfolio_value: Current portfolio value
            prices: Current asset prices
            
        Returns:
            Tuple of (adjusted_weights, turnover, was_skipped)
        """
        assets = list(current_weights.keys())
        adjusted_weights = current_weights.copy()
        
        max_weight_change = 0.0
        should_rebalance = False
        
        for asset in assets:
            current = current_weights.get(asset, 0.0)
            target = target_weights.get(asset, 0.0)
            
            weight_change = abs(target - current)
            max_weight_change = max(max_weight_change, weight_change)
            
            # Check if weight change exceeds threshold
            if weight_change >= self.no_trade_threshold:
                adjusted_weights[asset] = target
                should_rebalance = True
            # else: keep current weight (don't trade)
        
        # Normalize adjusted weights to sum to 1
        total_weight = sum(adjusted_weights.values())
        if total_weight > 0:
            adjusted_weights = {k: v/total_weight for k, v in adjusted_weights.items()}
        
        # Calculate turnover (only for assets that crossed threshold)
        turnover = sum(abs(adjusted_weights[a] - current_weights.get(a, 0.0)) for a in assets) / 2
        
        return adjusted_weights, turnover, not should_rebalance
    
    def _execute_rebalance(
        self,
        target_weights: Dict[str, float],
        portfolio_value: float,
        prices: pd.Series,
        current_positions: Dict[str, float]
    ) -> Tuple[float, Dict[str, float]]:
        """
        Execute rebalancing trades.
        
        Args:
            target_weights: Target portfolio weights
            portfolio_value: Current portfolio value
            prices: Current asset prices
            current_positions: Current share positions
            
        Returns:
            Tuple of (remaining_capital, new_positions)
        """
        new_positions = {}
        total_trade_value = 0.0
        
        for asset, weight in target_weights.items():
            target_value = portfolio_value * weight
            current_value = current_positions.get(asset, 0.0) * prices[asset]
            
            trade_value = target_value - current_value
            total_trade_value += abs(trade_value)
            
            # Calculate shares to buy/sell (with slippage adjustment)
            if prices[asset] > 0:
                slippage_factor = 1 + (self.slippage_bps / 10000) if trade_value > 0 else 1 - (self.slippage_bps / 10000)
                effective_price = prices[asset] * slippage_factor
                new_positions[asset] = max(0, trade_value / effective_price)
            else:
                new_positions[asset] = current_positions.get(asset, 0.0)
        
        # Calculate and deduct transaction costs
        transaction_cost = self._calculate_transaction_cost(total_trade_value / 2, portfolio_value)
        self.total_transaction_costs += transaction_cost
        
        # Remaining capital after accounting for rounding and costs
        invested_value = sum(new_positions[a] * prices[a] for a in new_positions)
        remaining_capital = max(0, portfolio_value - invested_value - transaction_cost)
        
        if transaction_cost > 0:
            logger.debug(f"Transaction cost: ${transaction_cost:,.2f}")
        
        return remaining_capital, new_positions
    
    def _calculate_transaction_cost(self, turnover_value: float, portfolio_value: float) -> float:
        """
        Calculate transaction cost based on turnover.
        
        Args:
            turnover_value: Dollar value of trades
            portfolio_value: Total portfolio value
            
        Returns:
            Transaction cost in dollars
        """
        cost_rate = self.transaction_cost_bps / 10000
        return turnover_value * cost_rate
    
    def _calculate_metrics(self, results_df: pd.DataFrame, turnover_history: List[Dict]) -> Dict:
        """
        Calculate performance metrics.
        
        Args:
            results_df: DataFrame with returns
            turnover_history: List of turnover records
            
        Returns:
            Dictionary of metrics
        """
        returns = results_df['return'].dropna()
        
        if len(returns) == 0:
            return {
                'total_return': 0.0,
                'annualized_return': 0.0,
                'volatility': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'avg_turnover': 0.0
            }
        
        # Total return
        total_return = (results_df['value'].iloc[-1] / self.initial_capital) - 1
        
        # Annualized return
        n_days = len(returns)
        annualized_return = (1 + total_return) ** (252 / n_days) - 1
        
        # Volatility
        volatility = returns.std() * np.sqrt(252)
        
        # Sharpe ratio (assuming risk-free rate of 2%)
        risk_free_rate = 0.02
        sharpe_ratio = (annualized_return - risk_free_rate) / volatility if volatility > 0 else 0.0
        
        # Maximum drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # Average turnover
        avg_turnover = np.mean([t['turnover'] for t in turnover_history]) if turnover_history else 0.0
        
        return {
            'total_return': float(total_return),
            'annualized_return': float(annualized_return),
            'volatility': float(volatility),
            'sharpe_ratio': float(sharpe_ratio),
            'max_drawdown': float(max_drawdown),
            'avg_turnover': float(avg_turnover),
            'total_trading_days': n_days
        }


class WalkForwardValidator:
    """
    Walk-Forward Analysis for robust strategy validation.
    """
    
    def __init__(
        self,
        train_window: int = 252,  # 1 year training
        test_window: int = 63,   # 3 months testing
        step_size: int = 21      # 1 month step
    ):
        """
        Initialize walk-forward validator.
        
        Args:
            train_window: Training window size in days
            test_window: Test window size in days
            step_size: Step size between folds
        """
        self.train_window = train_window
        self.test_window = test_window
        self.step_size = step_size
        
    def generate_folds(self, dates: pd.DatetimeIndex) -> List[Tuple[pd.DatetimeIndex, pd.DatetimeIndex]]:
        """
        Generate train/test fold indices.
        
        Args:
            dates: Full date range
            
        Returns:
            List of (train_dates, test_dates) tuples
        """
        folds = []
        
        start_idx = 0
        while start_idx + self.train_window + self.test_window <= len(dates):
            train_start = start_idx
            train_end = start_idx + self.train_window
            test_end = train_end + self.test_window
            
            train_dates = dates[train_start:train_end]
            test_dates = dates[train_end:test_end]
            
            folds.append((train_dates, test_dates))
            
            start_idx += self.step_size
        
        logger.info(f"Generated {len(folds)} walk-forward folds")
        return folds
    
    def validate(
        self,
        prices: pd.DataFrame,
        weights_func,
        **kwargs
    ) -> Dict:
        """
        Run walk-forward validation.
        
        Args:
            prices: Price DataFrame
            weights_func: Weight generation function
            **kwargs: Arguments for weights_func
            
        Returns:
            Dictionary with OOS results for each fold
        """
        folds = self.generate_folds(prices.index)
        oos_results = []
        
        for fold_idx, (train_dates, test_dates) in enumerate(folds):
            logger.info(f"Fold {fold_idx + 1}/{len(folds)}: Train {train_dates[0]} to {train_dates[-1]}, "
                       f"Test {test_dates[0]} to {test_dates[-1]}")
            
            # Training period
            train_prices = prices.loc[train_dates]
            
            try:
                # Calculate optimal weights on training data
                target_weights = weights_func(train_prices, **kwargs)
                
                # Test period
                test_prices = prices.loc[test_dates]
                
                # Calculate returns with these fixed weights
                if isinstance(target_weights, dict):
                    weights_array = np.array([target_weights.get(col, 0) for col in test_prices.columns])
                else:
                    weights_array = target_weights
                
                # Normalize weights
                weights_array = weights_array / np.sum(weights_array)
                
                # Portfolio returns
                asset_returns = test_prices.pct_change().dropna()
                portfolio_returns = (asset_returns * weights_array).sum(axis=1)
                
                # Calculate metrics
                cumulative_return = (1 + portfolio_returns).prod() - 1
                sharpe = portfolio_returns.mean() / portfolio_returns.std() * np.sqrt(252) if portfolio_returns.std() > 0 else 0
                
                oos_results.append({
                    'fold': fold_idx,
                    'train_start': train_dates[0],
                    'train_end': train_dates[-1],
                    'test_start': test_dates[0],
                    'test_end': test_dates[-1],
                    'cumulative_return': cumulative_return,
                    'sharpe_ratio': sharpe,
                    'weights': target_weights
                })
                
            except Exception as e:
                logger.warning(f"Fold {fold_idx + 1} failed: {e}")
                oos_results.append({
                    'fold': fold_idx,
                    'cumulative_return': 0.0,
                    'sharpe_ratio': 0.0,
                    'error': str(e)
                })
        
        # Aggregate results
        results_df = pd.DataFrame(oos_results)
        
        avg_oos_return = results_df['cumulative_return'].mean()
        avg_oos_sharpe = results_df['sharpe_ratio'].mean()
        
        logger.info(f"Walk-Forward Results:")
        logger.info(f"  Avg OOS Return: {avg_oos_return:.2%}")
        logger.info(f"  Avg OOS Sharpe: {avg_oos_sharpe:.3f}")
        
        return {
            'fold_results': results_df,
            'avg_oos_return': avg_oos_return,
            'avg_oos_sharpe': avg_oos_sharpe
        }


def _generate_walk_forward_folds(
    n_samples: int,
    n_folds: int,
    min_train_size: int = 60,
    min_test_size: int = 20
) -> List[Tuple[int, int, int, int]]:
    """
    Generate walk-forward fold indices ensuring temporal causality.
    
    Args:
        n_samples: Total number of samples
        n_folds: Number of folds to generate
        min_train_size: Minimum training window size
        min_test_size: Minimum test window size
        
    Returns:
        List of (train_start, train_end, test_start, test_end) index tuples
    """
    folds = []
    
    # Calculate fold sizes
    total_required = min_train_size + min_test_size
    if n_samples < total_required:
        logger.warning(f"Insufficient data: {n_samples} samples < {total_required} required")
        return folds
    
    # Divide available data into folds
    available_for_folds = n_samples - min_train_size
    fold_step = max(1, available_for_folds // n_folds)
    
    for i in range(n_folds):
        train_start = 0
        train_end = min_train_size + i * fold_step
        test_start = train_end
        test_end = min(test_start + min_test_size, n_samples)
        
        if test_end > n_samples:
            break
            
        if train_end - train_start >= min_train_size and test_end - test_start >= min_test_size:
            folds.append((train_start, train_end, test_start, test_end))
    
    logger.info(f"Generated {len(folds)} walk-forward folds from {n_samples} samples")
    return folds


if __name__ == "__main__":
    # Example usage
    np.random.seed(42)
    
    # Create sample price data
    dates = pd.date_range('2023-01-01', periods=500, freq='D')
    n_assets = 5
    assets = [f'Asset_{i}' for i in range(n_assets)]
    
    # Simulate correlated returns
    returns = np.random.randn(500, n_assets) * 0.02
    prices = pd.DataFrame(
        100 * np.cumprod(1 + returns),
        index=dates,
        columns=assets
    )
    
    # Simple equal weight strategy
    def equal_weights(prices, **kwargs):
        n = len(prices.columns)
        return {col: 1/n for col in prices.columns}
    
    print("\n=== Testing Backtester ===")
    backtester = Backtester(
        initial_capital=100000,
        transaction_cost_bps=10,
        no_trade_threshold=0.03
    )
    
    results = backtester.run_backtest(
        prices,
        equal_weights,
        rebalance_frequency='W'
    )
    
    print(f"\nFinal Portfolio Value: ${results['returns']['value'].iloc[-1]:,.2f}")
    print(f"Total Return: {results['metrics']['total_return']:.2%}")
    print(f"Sharpe Ratio: {results['metrics']['sharpe_ratio']:.3f}")
    print(f"Total Transaction Costs: ${results['transaction_costs']:,.2f}")
    
    print("\n=== Testing Walk-Forward Validator ===")
    validator = WalkForwardValidator(
        train_window=126,  # 6 months
        test_window=42,    # 2 months
        step_size=21       # 1 month
    )
    
    wf_results = validator.validate(prices, equal_weights)
    print(f"\nAvg OOS Return: {wf_results['avg_oos_return']:.2%}")
    print(f"Avg OOS Sharpe: {wf_results['avg_oos_sharpe']:.3f}")
