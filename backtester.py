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
