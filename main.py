"""
Main Orchestrator - Crypto Portfolio Optimization System

This module orchestrates the complete pipeline:
1. Data fetching from Binance
2. AI sentiment analysis
3. Portfolio optimization (MVO, Black-Litterman, Risk Parity, CVaR)
4. Backtesting with weekly rebalancing
5. Performance evaluation

Target: 5% monthly return with max 10-15% drawdown
"""
import numpy as np
import pandas as pd
import logging
import sys
from datetime import datetime
from typing import Dict, Optional

# Import modules
from data_fetcher import DataFetcher
from ai_sentiment import AISentimentAnalyzer
from portfolio_optimizer import PortfolioOptimizer
from backtester import Backtester

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('portfolio_backtest.log')
    ]
)
logger = logging.getLogger(__name__)


class CryptoPortfolioSystem:
    """
    Complete crypto portfolio optimization system
    
    Integrates:
    - Real-time data fetching
    - AI sentiment analysis
    - Multiple optimization strategies
    - Rigorous backtesting
    """
    
    def __init__(self, symbols: list = None, initial_capital: float = 100000):
        """
        Initialize the system
        
        Args:
            symbols: List of trading pairs
            initial_capital: Starting capital in USDT
        """
        self.symbols = symbols or [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'
        ]
        self.initial_capital = initial_capital
        
        # Initialize components
        self.data_fetcher = DataFetcher(self.symbols)
        self.sentiment_analyzer = AISentimentAnalyzer(use_mock=True)
        self.optimizer = None  # Initialized after data fetch
        self.backtester = Backtester(
            initial_capital=initial_capital,
            transaction_cost=0.001,  # 0.1% taker fee
            slippage=0.0005  # 0.05% slippage
        )
        
        logger.info(f"CryptoPortfolioSystem initialized for {len(self.symbols)} symbols")
        logger.info(f"Symbols: {self.symbols}")
    
    def fetch_data(self, timeframe: str = '1h', 
                   since_days: int = 365) -> tuple:
        """
        Fetch and prepare historical data
        
        Returns:
            Tuple of (prices DataFrame, returns DataFrame)
        """
        logger.info("=" * 60)
        logger.info("STEP 1: Fetching Historical Data")
        logger.info("=" * 60)
        
        # Fetch OHLCV data
        raw_data = self.data_fetcher.fetch_all_symbols(
            timeframe=timeframe, 
            since_days=since_days
        )
        
        # Align timestamps
        prices = self.data_fetcher.align_data(raw_data)
        
        # Calculate returns
        returns = self.data_fetcher.calculate_returns(prices)
        
        logger.info(f"Data fetched successfully:")
        logger.info(f"  - Date range: {prices.index.min()} to {prices.index.max()}")
        logger.info(f"  - Observations: {len(prices)}")
        logger.info(f"  - Assets: {list(prices.columns)}")
        
        return prices, returns
    
    def create_optimization_strategy(self, method: str = 'black_litterman'):
        """
        Create a weights strategy function
        
        Args:
            method: Optimization method ('mvo', 'black_litterman', 'risk_parity', 'cvar', 'ml')
            
        Returns:
            Strategy function
        """
        def strategy(prices: pd.DataFrame, returns: pd.DataFrame) -> np.ndarray:
            n_assets = len(prices.columns)
            asset_names = list(prices.columns)
            
            # Initialize optimizer if needed
            if self.optimizer is None or self.optimizer.n_assets != n_assets:
                self.optimizer = PortfolioOptimizer(n_assets, asset_names)
            
            # Calculate inputs
            cov_matrix = returns.cov().values * 24 * 365  # Annualized
            
            if method == 'mvo':
                expected_returns = returns.mean().values * 24 * 365
                weights = self.optimizer.mean_variance_optimization(
                    expected_returns, cov_matrix, method='max_sharpe'
                )
                
            elif method == 'black_litterman':
                # Market caps (relative, normalized)
                market_caps = np.array([1.0, 0.5, 0.2, 0.15, 0.1])[:n_assets]
                market_caps = market_caps / market_caps.sum() * n_assets
                
                # Historical returns as prior
                expected_returns = returns.mean().values * 24 * 365
                
                # AI-generated views
                P, Q = self.sentiment_analyzer.generate_views(
                    prices, expected_returns, asset_names
                )
                omega = self.sentiment_analyzer.get_confidence_matrix(n_assets)
                
                weights = self.optimizer.black_litterman(
                    market_caps, cov_matrix, P, Q, omega=omega
                )
                
            elif method == 'risk_parity':
                weights = self.optimizer.risk_parity(cov_matrix)
                
            elif method == 'cvar':
                weights = self.optimizer.cvar_optimization(
                    returns.values, 
                    cvar_limit=0.05,
                    confidence=0.95
                )
                
            elif method == 'ml':
                expected_returns = self.optimizer.ml_forecast_returns(returns)
                weights = self.optimizer.mean_variance_optimization(
                    expected_returns, cov_matrix, method='max_sharpe'
                )
                
            else:
                # Default: equal weight
                weights = np.ones(n_assets) / n_assets
            
            return weights
        
        return strategy
    
    def run_backtest(self, prices: pd.DataFrame,
                    strategy_method: str = 'black_litterman',
                    train_split: float = 0.75,
                    rebalance_freq: str = 'W') -> Dict:
        """
        Run complete backtest
        
        Args:
            prices: Aligned price DataFrame
            strategy_method: Optimization strategy to use
            train_split: Train/test split ratio
            rebalance_freq: Rebalancing frequency
            
        Returns:
            Backtest results dictionary
        """
        logger.info("=" * 60)
        logger.info("STEP 2: Running Backtest")
        logger.info(f"Strategy: {strategy_method.upper()}")
        logger.info(f"Train/Test Split: {train_split:.0%}/{1-train_split:.0%}")
        logger.info(f"Rebalancing: {rebalance_freq}")
        logger.info("=" * 60)
        
        # Create strategy
        strategy = self.create_optimization_strategy(strategy_method)
        
        # Run backtest
        results = self.backtester.run(
            prices=prices,
            weights_strategy=strategy,
            rebalance_freq=rebalance_freq,
            lookback_hours=168,  # 1 week lookback
            train_split=train_split
        )
        
        return results
    
    def evaluate_results(self, results: Dict, target_monthly: float = 0.05,
                        max_dd_limit: float = 0.15) -> Dict:
        """
        Evaluate if targets were met
        
        Args:
            results: Backtest results
            target_monthly: Target monthly return (default 5%)
            max_dd_limit: Maximum allowed drawdown (default 15%)
            
        Returns:
            Evaluation dictionary
        """
        metrics = results['metrics']
        
        monthly_return = metrics['monthly_return']
        max_drawdown = abs(metrics['max_drawdown'])
        sharpe = metrics['sharpe_ratio']
        
        # Target assessment
        target_met = monthly_return >= target_monthly
        dd_within_limit = max_drawdown <= max_dd_limit
        
        evaluation = {
            'target_monthly_return': target_monthly,
            'actual_monthly_return': monthly_return,
            'target_achieved': target_met,
            'max_drawdown': max_drawdown,
            'drawdown_within_limit': dd_within_limit,
            'sharpe_ratio': sharpe,
            'total_return': metrics['total_return'],
            'transaction_costs': metrics['total_transaction_costs'],
            'n_rebalances': metrics['n_rebalances']
        }
        
        logger.info("=" * 60)
        logger.info("STEP 3: Performance Evaluation")
        logger.info("=" * 60)
        logger.info(f"Target Monthly Return: {target_monthly:.2%}")
        logger.info(f"Actual Monthly Return: {monthly_return:.2%}")
        logger.info(f"Target Achieved: {'YES ✓' if target_met else 'NO ✗'}")
        logger.info("")
        logger.info(f"Max Drawdown: {max_drawdown:.2%}")
        logger.info(f"Drawdown Limit: {max_dd_limit:.2%}")
        logger.info(f"Within Limit: {'YES ✓' if dd_within_limit else 'NO ✗'}")
        logger.info("")
        logger.info(f"Sharpe Ratio: {sharpe:.2f}")
        logger.info(f"Total Transaction Costs: ${metrics['total_transaction_costs']:,.2f}")
        logger.info(f"Number of Rebalances: {metrics['n_rebalances']}")
        
        return evaluation
    
    def run_full_pipeline(self, strategy_method: str = 'black_litterman',
                         since_days: int = 365,
                         train_split: float = 0.75) -> Dict:
        """
        Execute complete pipeline from data fetch to evaluation
        
        Returns:
            Complete results dictionary
        """
        logger.info("=" * 60)
        logger.info("CRYPTO PORTFOLIO OPTIMIZATION SYSTEM")
        logger.info(f"Start Time: {datetime.now().isoformat()}")
        logger.info("=" * 60)
        
        try:
            # Step 1: Fetch data
            prices, returns = self.fetch_data(since_days=since_days)
            
            # Step 2: Run backtest
            results = self.run_backtest(
                prices=prices,
                strategy_method=strategy_method,
                train_split=train_split
            )
            
            # Step 3: Evaluate
            evaluation = self.evaluate_results(results)
            
            # Combine results
            full_results = {
                'prices': prices,
                'returns': returns,
                'backtest': results,
                'evaluation': evaluation,
                'strategy': strategy_method
            }
            
            logger.info("=" * 60)
            logger.info("PIPELINE COMPLETE")
            logger.info(f"End Time: {datetime.now().isoformat()}")
            logger.info("=" * 60)
            
            return full_results
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise


def print_final_summary(evaluation: Dict):
    """Print final verdict summary"""
    print("\n" + "=" * 60)
    print("FINAL ASSESSMENT")
    print("=" * 60)
    
    target_met = evaluation['target_achieved']
    dd_ok = evaluation['drawdown_within_limit']
    
    print(f"\n📊 PERFORMANCE METRICS:")
    print(f"   Monthly Return: {evaluation['actual_monthly_return']:.2%} (Target: {evaluation['target_monthly_return']:.2%})")
    print(f"   Max Drawdown: {evaluation['max_drawdown']:.2%} (Limit: 15%)")
    print(f"   Sharpe Ratio: {evaluation['sharpe_ratio']:.2f}")
    print(f"   Total Return: {evaluation['total_return']:.2%}")
    
    print(f"\n🎯 TARGET ACHIEVEMENT:")
    print(f"   5% Monthly Return: {'✓ ACHIEVED' if target_met else '✗ NOT ACHIEVED'}")
    print(f"   <15% Drawdown: {'✓ ACHIEVED' if dd_ok else '✗ NOT ACHIEVED'}")
    
    if target_met and dd_ok:
        print(f"\n✅ SUCCESS: Both targets achieved!")
    elif target_met:
        print(f"\n⚠️ PARTIAL: Return target met but drawdown exceeded")
    elif dd_ok:
        print(f"\n⚠️ PARTIAL: Drawdown within limit but return target not met")
    else:
        print(f"\n❌ FAILED: Neither target achieved")
    
    print("\n" + "=" * 60)


def main():
    """Main execution"""
    # Initialize system
    system = CryptoPortfolioSystem(
        symbols=['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'],
        initial_capital=100000
    )
    
    # Run full pipeline with Black-Litterman strategy
    results = system.run_full_pipeline(
        strategy_method='black_litterman',
        since_days=365,
        train_split=0.75  # 9 months train, 3 months test
    )
    
    # Print summary
    print_final_summary(results['evaluation'])
    
    # Also test other strategies for comparison
    print("\n\n" + "=" * 60)
    print("COMPARISON: Testing Alternative Strategies")
    print("=" * 60)
    
    for method in ['mvo', 'risk_parity', 'cvar']:
        print(f"\n--- Testing {method.upper()} ---")
        try:
            system2 = CryptoPortfolioSystem(initial_capital=100000)
            prices, _ = system2.fetch_data(since_days=365)
            results2 = system2.run_backtest(prices, strategy_method=method, train_split=0.75)
            eval2 = system2.evaluate_results(results2)
            print(f"Monthly Return: {eval2['actual_monthly_return']:.2%}")
            print(f"Max Drawdown: {eval2['max_drawdown']:.2%}")
            print(f"Sharpe: {eval2['sharpe_ratio']:.2f}")
        except Exception as e:
            print(f"Error with {method}: {e}")
    
    return results


if __name__ == "__main__":
    results = main()
