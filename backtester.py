"""
Backtester Module
Event-driven backtester with weekly rebalancing and realistic transaction costs
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Backtester:
    """
    Event-driven portfolio backtester
    
    Features:
    - Weekly rebalancing
    - Realistic transaction costs (0.1% taker fee + slippage)
    - Drawdown monitoring
    - Performance attribution
    """
    
    def __init__(self, initial_capital: float = 100000,
                 transaction_cost: float = 0.001,
                 slippage: float = 0.0005):
        """
        Initialize backtester
        
        Args:
            initial_capital: Starting capital in USDT
            transaction_cost: Taker fee (default 0.1%)
            slippage: Estimated slippage per trade (default 0.05%)
        """
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost
        self.slippage = slippage
        self.total_cost_rate = transaction_cost + slippage
        
        logger.info(f"Initialized backtester with ${initial_capital:,}")
        logger.info(f"Transaction cost: {transaction_cost:.2%}, Slippage: {slippage:.2%}")
    
    def run(self, prices: pd.DataFrame, 
            weights_strategy,
            rebalance_freq: str = 'W',
            lookback_hours: int = 168,
            train_split: float = 0.75) -> Dict:
        """
        Run full backtest with periodic rebalancing
        
        Args:
            prices: DataFrame of aligned prices
            weights_strategy: Function that returns optimal weights
            rebalance_freq: Rebalancing frequency ('W' = weekly)
            lookback_hours: Hours of data for optimization
            train_split: Train/test split ratio
            
        Returns:
            Dictionary with backtest results
        """
        logger.info(f"Starting backtest from {prices.index.min()} to {prices.index.max()}")
        
        # Split into train/test
        n_train = int(len(prices) * train_split)
        train_prices = prices.iloc[:n_train]
        test_prices = prices.iloc[n_train:]
        
        logger.info(f"Train period: {train_prices.index.min()} to {train_prices.index.max()}")
        logger.info(f"Test period: {test_prices.index.min()} to {test_prices.index.max()}")
        
        # Initialize portfolio
        capital = self.initial_capital
        weights = np.ones(len(prices.columns)) / len(prices.columns)  # Equal weight start
        
        # Track portfolio evolution
        portfolio_values = []
        rebalance_events = []
        daily_returns = []
        
        # Get rebalance dates (weekly)
        rebalance_dates = test_prices.resample(rebalance_freq).first().index
        
        current_idx = 0
        next_rebalance = rebalance_dates[0] if len(rebalance_dates) > 0 else test_prices.index[0]
        
        logger.info(f"Rebalancing on dates: {rebalance_dates[:5]}...")
        
        for i, (timestamp, row) in enumerate(test_prices.iterrows()):
            # Check if rebalance needed
            if timestamp >= next_rebalance and i > 0:
                # Calculate new weights using lookback data
                lookback_start = max(0, i + n_train - lookback_hours)
                lookback_prices = prices.iloc[lookback_start:i + n_train]
                lookback_returns = lookback_prices.pct_change().dropna()
                
                try:
                    # Get optimal weights
                    new_weights = weights_strategy(lookback_prices, lookback_returns)
                    new_weights = np.array(new_weights)
                    
                    # Calculate turnover and transaction costs
                    turnover = np.abs(new_weights - weights).sum() / 2
                    cost = capital * turnover * self.total_cost_rate
                    
                    # Record rebalance event
                    rebalance_events.append({
                        'date': timestamp,
                        'old_weights': weights.copy(),
                        'new_weights': new_weights.copy(),
                        'turnover': turnover,
                        'cost': cost,
                        'capital_before': capital
                    })
                    
                    # Apply transaction costs
                    capital -= cost
                    
                    weights = new_weights
                    
                    logger.info(f"Rebalanced at {timestamp}: turnover={turnover:.2%}, cost=${cost:.2f}")
                    
                    # Move to next rebalance date
                    future_dates = [d for d in rebalance_dates if d > timestamp]
                    if future_dates:
                        next_rebalance = future_dates[0]
                    else:
                        next_rebalance = test_prices.index[-1] + timedelta(hours=1)
                        
                except Exception as e:
                    logger.error(f"Rebalancing failed at {timestamp}: {e}")
            
            # Calculate portfolio value
            # Simple return approximation
            price_changes = row / test_prices.iloc[i-1] - 1 if i > 0 else np.zeros(len(row))
            port_return = np.dot(weights, price_changes)
            
            # Update capital
            capital *= (1 + port_return)
            
            # Record
            portfolio_values.append({
                'timestamp': timestamp,
                'value': capital,
                'weights': weights.copy()
            })
            
            if i > 0:
                daily_returns.append(port_return)
        
        # Convert to DataFrame
        pv_df = pd.DataFrame(portfolio_values).set_index('timestamp')
        
        # Calculate metrics
        metrics = self.calculate_metrics(pv_df, daily_returns, rebalance_events)
        
        logger.info("=== Backtest Complete ===")
        logger.info(f"Final Value: ${metrics['final_value']:,.2f}")
        logger.info(f"Total Return: {metrics['total_return']:.2%}")
        logger.info(f"Monthly Return: {metrics['monthly_return']:.2%}")
        logger.info(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        logger.info(f"Max Drawdown: {metrics['max_drawdown']:.2%}")
        
        return {
            'portfolio_values': pv_df,
            'metrics': metrics,
            'rebalance_events': rebalance_events,
            'daily_returns': pd.Series(daily_returns, index=test_prices.index[1:])
        }
    
    def calculate_metrics(self, pv_df: pd.DataFrame, 
                         returns: List[float],
                         rebalance_events: List[Dict]) -> Dict:
        """
        Calculate comprehensive performance metrics
        """
        values = pv_df['value'].values
        returns_series = pd.Series(returns)
        
        # Total return
        total_return = (values[-1] - self.initial_capital) / self.initial_capital
        
        # Annualized return (assuming hourly data over ~3 months test)
        n_periods = len(values)
        years = n_periods / (24 * 365)
        if years > 0:
            ann_return = (values[-1] / self.initial_capital) ** (1 / years) - 1
        else:
            ann_return = 0
        
        # Monthly return
        months = n_periods / (24 * 30)
        if months > 0:
            monthly_return = (values[-1] / self.initial_capital) ** (1 / months) - 1
        else:
            monthly_return = 0
        
        # Volatility and Sharpe
        if len(returns_series) > 1:
            vol = returns_series.std() * np.sqrt(24 * 365)
            mean_ret = returns_series.mean() * 24 * 365
            sharpe = (mean_ret - 0.02) / vol if vol > 0 else 0
        else:
            vol = 0
            sharpe = 0
        
        # Drawdown analysis
        cum_values = pd.Series(values)
        running_max = cum_values.cummax()
        drawdown = (cum_values - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # VaR and CVaR (95%)
        var_95 = returns_series.quantile(0.05) if len(returns_series) > 0 else 0
        cvar_95 = returns_series[returns_series <= var_95].mean() if len(returns_series) > 0 else 0
        
        # Transaction costs
        total_costs = sum(e['cost'] for e in rebalance_events)
        n_rebalances = len(rebalance_events)
        
        metrics = {
            'final_value': values[-1],
            'total_return': total_return,
            'annualized_return': ann_return,
            'monthly_return': monthly_return,
            'volatility': vol,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'var_95': var_95,
            'cvar_95': cvar_95,
            'total_transaction_costs': total_costs,
            'n_rebalances': n_rebalances,
            'avg_turnover': np.mean([e['turnover'] for e in rebalance_events]) if rebalance_events else 0
        }
        
        return metrics
    
    def plot_results(self, pv_df: pd.DataFrame, save_path: str = None):
        """
        Plot portfolio performance (requires matplotlib)
        """
        try:
            import matplotlib.pyplot as plt
            
            fig, axes = plt.subplots(3, 1, figsize=(14, 10))
            
            # Portfolio value
            axes[0].plot(pv_df.index, pv_df['value'])
            axes[0].axhline(y=self.initial_capital, color='gray', linestyle='--', alpha=0.5)
            axes[0].set_title('Portfolio Value Over Time')
            axes[0].set_ylabel('Value (USDT)')
            axes[0].grid(True, alpha=0.3)
            
            # Drawdown
            cum_values = pv_df['value']
            running_max = cum_values.cummax()
            drawdown = (cum_values - running_max) / running_max
            axes[1].fill_between(drawdown.index, drawdown, 0, alpha=0.5, color='red')
            axes[1].set_title('Drawdown')
            axes[1].set_ylabel('Drawdown %')
            axes[1].grid(True, alpha=0.3)
            
            # Weights evolution (stacked area)
            weight_cols = [c for c in pv_df.columns if 'weight' in str(c).lower()]
            if weight_cols:
                pv_df[weight_cols].plot(kind='area', ax=axes[2], alpha=0.7)
                axes[2].set_title('Portfolio Weights Over Time')
                axes[2].set_ylabel('Weight')
            
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=150)
                logger.info(f"Plot saved to {save_path}")
            
            plt.show()
            
        except ImportError:
            logger.warning("matplotlib not available for plotting")


def equal_weight_strategy(prices: pd.DataFrame, 
                         returns: pd.DataFrame) -> np.ndarray:
    """Simple equal weight strategy"""
    n_assets = len(prices.columns)
    return np.ones(n_assets) / n_assets


def main():
    """Test backtester"""
    np.random.seed(42)
    
    # Generate sample prices
    dates = pd.date_range('2024-01-01', periods=2000, freq='H')
    n_assets = 5
    
    # Random walk with drift
    returns_data = np.random.randn(2000, n_assets) * 0.01 + 0.0001
    prices_data = 100 * np.exp(np.cumsum(returns_data, axis=0))
    
    prices = pd.DataFrame(prices_data, index=dates, 
                         columns=['BTC', 'ETH', 'SOL', 'BNB', 'XRP'])
    
    # Run backtest
    backtester = Backtester(initial_capital=100000)
    results = backtester.run(prices, equal_weight_strategy, 
                            rebalance_freq='W',
                            train_split=0.75)
    
    print("\n=== Backtest Results ===")
    for key, value in results['metrics'].items():
        if isinstance(value, float):
            print(f"{key}: {value:.4f}" if value < 1 else f"{key}: {value:,.2f}")
        else:
            print(f"{key}: {value}")
    
    return results


if __name__ == "__main__":
    results = main()
