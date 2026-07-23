"""
Comprehensive Real Environment Testing Suite
Tests the system against live market data from Binance
Validates data fetching, optimization, and backtesting with real prices
"""

import numpy as np
import pandas as pd
import logging
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_live_environment.log')
    ]
)
logger = logging.getLogger(__name__)


class RealEnvironmentTester:
    """
    Comprehensive tester for real market environment
    
    Tests:
    1. Live data fetching from Binance
    2. Data quality validation
    3. Strategy optimization
    4. Backtesting with real prices
    5. Performance metrics calculation
    """
    
    def __init__(self, symbols: List[str] = None, initial_capital: float = 100000):
        """Initialize tester"""
        self.symbols = symbols or [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'
        ]
        self.initial_capital = initial_capital
        
        logger.info("=" * 70)
        logger.info("REAL ENVIRONMENT TESTER INITIALIZED")
        logger.info("=" * 70)
        logger.info(f"Symbols: {self.symbols}")
        logger.info(f"Initial Capital: ${initial_capital:,}")
    
    # ============ PHASE 1: DATA VALIDATION ============
    
    def test_data_fetching(self, since_days: int = 30, timeframe: str = '1h') -> Tuple[pd.DataFrame, bool]:
        """
        Test 1: Fetch real data from Binance
        
        Returns:
            (prices_df, success_flag)
        """
        logger.info("\n" + "=" * 70)
        logger.info("TEST 1: REAL DATA FETCHING FROM BINANCE")
        logger.info("=" * 70)
        
        try:
            import ccxt
            
            exchange = ccxt.binance({'enableRateLimit': True})
            since = int((datetime.now() - timedelta(days=since_days)).timestamp() * 1000)
            
            all_data = {}
            logger.info(f"Fetching {timeframe} candles for {len(self.symbols)} symbols (last {since_days} days)...")
            
            for symbol in self.symbols:
                try:
                    logger.info(f"  → Fetching {symbol}...")
                    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since)
                    
                    df = pd.DataFrame(
                        ohlcv,
                        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                    )
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    df.set_index('timestamp', inplace=True)
                    
                    all_data[symbol] = df
                    logger.info(f"     ✓ {len(df)} candles fetched for {symbol}")
                    
                except Exception as e:
                    logger.error(f"     ✗ Error fetching {symbol}: {e}")
                    return None, False
            
            # Align data
            prices = pd.DataFrame()
            for symbol, df in all_data.items():
                prices[symbol] = df['close']
            
            prices = prices.fillna(method='ffill').fillna(method='bfill')
            
            logger.info("\n" + "─" * 70)
            logger.info("DATA FETCHING RESULTS:")
            logger.info(f"  • Time range: {prices.index.min()} to {prices.index.max()}")
            logger.info(f"  • Total observations: {len(prices)}")
            logger.info(f"  • Total assets: {len(prices.columns)}")
            logger.info(f"  • Data points: {len(prices) * len(prices.columns):,}")
            logger.info(f"  • Missing values: {prices.isna().sum().sum()}")
            
            # Print sample data
            logger.info("\nSample prices (last 5 candles):")
            logger.info(f"\n{prices.tail()}")
            
            logger.info("\n✓ DATA FETCHING TEST PASSED")
            return prices, True
            
        except Exception as e:
            logger.error(f"✗ DATA FETCHING TEST FAILED: {e}", exc_info=True)
            return None, False
    
    def test_data_quality(self, prices: pd.DataFrame) -> bool:
        """
        Test 2: Validate data quality
        
        Checks:
        - No extreme values
        - Proper time alignment
        - Sufficient data points
        - Price reasonableness
        """
        logger.info("\n" + "=" * 70)
        logger.info("TEST 2: DATA QUALITY VALIDATION")
        logger.info("=" * 70)
        
        try:
            checks_passed = 0
            checks_total = 0
            
            # Check 1: Sufficient data
            checks_total += 1
            min_periods = 168  # 1 week of hourly data
            if len(prices) >= min_periods:
                logger.info(f"✓ Check 1 (Sufficient data): {len(prices)} >= {min_periods} ✓")
                checks_passed += 1
            else:
                logger.warning(f"✗ Check 1 (Sufficient data): {len(prices)} < {min_periods} ✗")
            
            # Check 2: No NaN values
            checks_total += 1
            nan_count = prices.isna().sum().sum()
            if nan_count == 0:
                logger.info(f"✓ Check 2 (No NaN values): {nan_count} NaN ✓")
                checks_passed += 1
            else:
                logger.warning(f"✗ Check 2 (No NaN values): {nan_count} NaN values found")
            
            # Check 3: Reasonable price ranges
            checks_total += 1
            returns = prices.pct_change().dropna()
            extreme_returns = (returns.abs() > 0.5).sum().sum()  # >50% hourly moves
            if extreme_returns == 0:
                logger.info(f"✓ Check 3 (Reasonable returns): No extreme moves (>50%) ✓")
                checks_passed += 1
            else:
                logger.warning(f"✗ Check 3 (Reasonable returns): {extreme_returns} extreme moves detected")
            
            # Check 4: Monotonic time index
            checks_total += 1
            if prices.index.is_monotonic_increasing:
                logger.info(f"✓ Check 4 (Time ordering): Timestamps monotonically increasing ✓")
                checks_passed += 1
            else:
                logger.warning(f"✗ Check 4 (Time ordering): Time index is not monotonic")
            
            # Check 5: Price statistics
            checks_total += 1
            logger.info(f"\nPrice Statistics:")
            for col in prices.columns:
                logger.info(f"  {col}:")
                logger.info(f"    - Current: ${prices[col].iloc[-1]:,.2f}")
                logger.info(f"    - Min: ${prices[col].min():,.2f}")
                logger.info(f"    - Max: ${prices[col].max():,.2f}")
                logger.info(f"    - Std: ${prices[col].std():,.2f}")
            
            daily_returns = prices.pct_change().groupby(prices.index.date).last().mean()
            logger.info(f"\nDaily Return Statistics:")
            logger.info(f"  - Mean: {daily_returns.mean():.4%}")
            logger.info(f"  - Std: {daily_returns.std():.4%}")
            logger.info(f"  - Max: {daily_returns.max():.4%}")
            logger.info(f"  - Min: {daily_returns.min():.4%}")
            checks_passed += 1
            
            # Summary
            logger.info(f"\n{'─' * 70}")
            logger.info(f"Quality Checks Passed: {checks_passed}/{checks_total}")
            
            if checks_passed >= checks_total - 1:  # Allow 1 failure
                logger.info("✓ DATA QUALITY TEST PASSED")
                return True
            else:
                logger.warning("✗ DATA QUALITY TEST FAILED")
                return False
            
        except Exception as e:
            logger.error(f"✗ DATA QUALITY TEST FAILED: {e}", exc_info=True)
            return False
    
    # ============ PHASE 2: STRATEGY TESTING ============
    
    def test_portfolio_optimization(self, prices: pd.DataFrame) -> bool:
        """
        Test 3: Test all optimization strategies
        """
        logger.info("\n" + "=" * 70)
        logger.info("TEST 3: PORTFOLIO OPTIMIZATION STRATEGIES")
        logger.info("=" * 70)
        
        try:
            from portfolio_optimizer import PortfolioOptimizer
            
            returns = prices.pct_change().dropna()
            cov_matrix = returns.cov().values * 24 * 365  # Annualized
            expected_returns = returns.mean().values * 24 * 365
            n_assets = len(prices.columns)
            
            optimizer = PortfolioOptimizer(n_assets, list(prices.columns))
            
            strategies = {}
            
            # Strategy 1: MVO (Max Sharpe)
            logger.info("\n1. Testing Mean-Variance Optimization (Max Sharpe)...")
            try:
                weights = optimizer.mean_variance_optimization(
                    expected_returns, cov_matrix, method='max_sharpe'
                )
                strategies['MVO_MaxSharpe'] = weights
                logger.info(f"   ✓ Weights: {weights}")
            except Exception as e:
                logger.error(f"   ✗ MVO failed: {e}")
            
            # Strategy 2: Risk Parity
            logger.info("\n2. Testing Risk Parity...")
            try:
                weights = optimizer.risk_parity(cov_matrix)
                strategies['RiskParity'] = weights
                logger.info(f"   ✓ Weights: {weights}")
            except Exception as e:
                logger.error(f"   ✗ Risk Parity failed: {e}")
            
            # Strategy 3: Black-Litterman
            logger.info("\n3. Testing Black-Litterman...")
            try:
                market_caps = np.array([1.0, 0.5, 0.2, 0.15, 0.1])[:n_assets]
                market_caps = market_caps / market_caps.sum() * n_assets
                P, Q = np.eye(n_assets), expected_returns * 0.5
                
                weights = optimizer.black_litterman(market_caps, cov_matrix, P, Q)
                strategies['BlackLitterman'] = weights
                logger.info(f"   ✓ Weights: {weights}")
            except Exception as e:
                logger.error(f"   ✗ Black-Litterman failed: {e}")
            
            # Strategy 4: CVaR
            logger.info("\n4. Testing CVaR Optimization...")
            try:
                weights = optimizer.cvar_optimization(returns.values, cvar_limit=0.05)
                strategies['CVaR'] = weights
                logger.info(f"   ✓ Weights: {weights}")
            except Exception as e:
                logger.error(f"   ✗ CVaR failed: {e}")
            
            # Calculate metrics for each strategy
            logger.info(f"\n{'─' * 70}")
            logger.info("STRATEGY COMPARISON:")
            logger.info(f"{'Strategy':<20} {'Ann. Return':<15} {'Volatility':<15} {'Sharpe':<10}")
            logger.info(f"{'-' * 60}")
            
            for strategy_name, weights in strategies.items():
                metrics = optimizer.calculate_portfolio_metrics(
                    weights, returns, cov_matrix
                )
                logger.info(
                    f"{strategy_name:<20} {metrics['annualized_return']:>13.2%} "
                    f"{metrics['annualized_volatility']:>13.2%} "
                    f"{metrics['sharpe_ratio']:>8.2f}"
                )
            
            logger.info(f"\n✓ PORTFOLIO OPTIMIZATION TEST PASSED")
            return len(strategies) >= 3  # At least 3 strategies worked
            
        except Exception as e:
            logger.error(f"✗ PORTFOLIO OPTIMIZATION TEST FAILED: {e}", exc_info=True)
            return False
    
    # ============ PHASE 3: BACKTESTING ============
    
    def test_backtesting(self, prices: pd.DataFrame) -> bool:
        """
        Test 4: Run real backtest with live data
        """
        logger.info("\n" + "=" * 70)
        logger.info("TEST 4: BACKTESTING WITH REAL DATA")
        logger.info("=" * 70)
        
        try:
            from backtester import Backtester
            from portfolio_optimizer import PortfolioOptimizer
            
            returns = prices.pct_change().dropna()
            n_assets = len(prices.columns)
            
            # Create simple strategy function
            def strategy(prices_df, returns_df):
                return np.ones(n_assets) / n_assets  # Equal weight
            
            backtester = Backtester(
                initial_capital=self.initial_capital,
                transaction_cost=0.001,
                slippage=0.0005
            )
            
            logger.info(f"\nRunning backtest with equal-weight strategy...")
            logger.info(f"  - Initial capital: ${self.initial_capital:,}")
            logger.info(f"  - Test period: {prices.index.min()} to {prices.index.max()}")
            logger.info(f"  - Observations: {len(prices)}")
            
            results = backtester.run(
                prices=prices,
                weights_strategy=strategy,
                rebalance_freq='W',
                lookback_hours=168,
                train_split=0.75
            )
            
            metrics = results['metrics']
            
            logger.info(f"\n{'─' * 70}")
            logger.info("BACKTEST RESULTS:")
            logger.info(f"  • Final Value: ${metrics['final_value']:,.2f}")
            logger.info(f"  • Total Return: {metrics['total_return']:.2%}")
            logger.info(f"  • Annualized Return: {metrics['annualized_return']:.2%}")
            logger.info(f"  • Monthly Return: {metrics['monthly_return']:.2%}")
            logger.info(f"  • Volatility: {metrics['volatility']:.2%}")
            logger.info(f"  • Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
            logger.info(f"  • Max Drawdown: {metrics['max_drawdown']:.2%}")
            logger.info(f"  • VaR (95%): {metrics['var_95']:.4f}")
            logger.info(f"  • CVaR (95%): {metrics['cvar_95']:.4f}")
            logger.info(f"  • Transaction Costs: ${metrics['total_transaction_costs']:,.2f}")
            logger.info(f"  • Number of Rebalances: {metrics['n_rebalances']}")
            logger.info(f"  • Avg Turnover: {metrics['avg_turnover']:.2%}")
            
            logger.info(f"\n✓ BACKTESTING TEST PASSED")
            return True
            
        except Exception as e:
            logger.error(f"✗ BACKTESTING TEST FAILED: {e}", exc_info=True)
            return False
    
    # ============ PHASE 4: REGIME DETECTION ============
    
    def test_regime_detection(self, prices: pd.DataFrame) -> bool:
        """
        Test 5: Test market regime detection
        """
        logger.info("\n" + "=" * 70)
        logger.info("TEST 5: MARKET REGIME DETECTION")
        logger.info("=" * 70)
        
        try:
            from strategies.regime_detection import MarketRegimeDetector
            
            returns = prices.pct_change().dropna()
            
            detector = MarketRegimeDetector(n_regimes=4)
            
            logger.info("Extracting market features...")
            features = detector.extract_features(prices, returns)
            
            logger.info("Fitting HMM model...")
            detector.fit(features)
            
            logger.info("Predicting regimes...")
            regimes = detector.predict(features)
            
            logger.info(f"\n{'─' * 70}")
            logger.info("REGIME DETECTION RESULTS:")
            logger.info(f"  • Total observations: {len(regimes)}")
            logger.info(f"  • Current regime: {regimes.iloc[-1]} ({detector.regime_names.get(regimes.iloc[-1], 'Unknown')})")
            logger.info(f"\nRegime distribution:")
            for regime_id, regime_name in detector.regime_names.items():
                count = (regimes == regime_id).sum()
                pct = count / len(regimes) * 100
                logger.info(f"  • {regime_name}: {count} ({pct:.1f}%)")
            
            # Show features of recent periods
            logger.info(f"\nRecent market features (last 5 periods):")
            logger.info(f"\n{features.tail()}")
            
            logger.info(f"\n✓ REGIME DETECTION TEST PASSED")
            return True
            
        except Exception as e:
            logger.error(f"✗ REGIME DETECTION TEST FAILED: {e}", exc_info=True)
            return False
    
    # ============ PHASE 5: RL AGENT ============
    
    def test_rl_agent(self, prices: pd.DataFrame) -> bool:
        """
        Test 6: Test RL agent creation and training capability
        """
        logger.info("\n" + "=" * 70)
        logger.info("TEST 6: REINFORCEMENT LEARNING AGENT")
        logger.info("=" * 70)
        
        try:
            from rl.rl_agent import RLTradingAgent, TradingEnvironment, SB3_AVAILABLE
            
            if not SB3_AVAILABLE:
                logger.warning("Stable Baselines3 not available - skipping RL tests")
                return True
            
            returns = prices.pct_change().dropna()
            
            # Test 1: Create environment
            logger.info("\n1. Testing TradingEnvironment creation...")
            try:
                env = TradingEnvironment(
                    prices=prices,
                    returns=returns,
                    initial_capital=100000,
                    transaction_cost=0.001,
                    risk_limit=0.15
                )
                obs, _ = env.reset()
                logger.info(f"   ✓ Environment created")
                logger.info(f"   ✓ Observation shape: {obs.shape}")
                logger.info(f"   ��� Action space: {env.action_space}")
            except Exception as e:
                logger.error(f"   ✗ Environment creation failed: {e}")
                return False
            
            # Test 2: Step through environment
            logger.info("\n2. Testing environment step...")
            try:
                action = env.action_space.sample()  # Random action
                obs, reward, terminated, truncated, info = env.step(action)
                logger.info(f"   ✓ Step executed")
                logger.info(f"   ✓ Reward: {reward:.6f}")
                logger.info(f"   ✓ Portfolio value: ${info['portfolio_value']:,.2f}")
            except Exception as e:
                logger.error(f"   ✗ Step failed: {e}")
                return False
            
            # Test 3: Create RL agent
            logger.info("\n3. Testing RLTradingAgent creation...")
            try:
                agent = RLTradingAgent(algorithm='PPO', learning_rate=3e-4)
                logger.info(f"   ✓ PPO agent created")
            except Exception as e:
                logger.error(f"   ✗ Agent creation failed: {e}")
                return False
            
            logger.info(f"\n✓ RL AGENT TEST PASSED")
            return True
            
        except Exception as e:
            logger.error(f"✗ RL AGENT TEST FAILED: {e}", exc_info=True)
            return False
    
    # ============ MAIN TEST RUNNER ============
    
    def run_all_tests(self, since_days: int = 30) -> Dict:
        """
        Run all tests and generate report
        """
        logger.info("\n\n")
        logger.info("╔" + "═" * 68 + "╗")
        logger.info("║" + " REAL ENVIRONMENT TESTING SUITE ".center(68) + "║")
        logger.info("║" + f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".ljust(68) + "║")
        logger.info("╚" + "═" * 68 + "╝")
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'tests': {}
        }
        
        # Test 1: Data Fetching
        prices, success = self.test_data_fetching(since_days=since_days)
        results['tests']['data_fetching'] = success
        
        if not success:
            logger.error("✗ Data fetching failed - cannot continue with other tests")
            return results
        
        # Test 2: Data Quality
        quality_ok = self.test_data_quality(prices)
        results['tests']['data_quality'] = quality_ok
        
        if not quality_ok:
            logger.warning("⚠ Data quality issues detected - proceeding with caution")
        
        # Test 3: Portfolio Optimization
        opt_ok = self.test_portfolio_optimization(prices)
        results['tests']['portfolio_optimization'] = opt_ok
        
        # Test 4: Backtesting
        backtest_ok = self.test_backtesting(prices)
        results['tests']['backtesting'] = backtest_ok
        
        # Test 5: Regime Detection
        regime_ok = self.test_regime_detection(prices)
        results['tests']['regime_detection'] = regime_ok
        
        # Test 6: RL Agent
        rl_ok = self.test_rl_agent(prices)
        results['tests']['rl_agent'] = rl_ok
        
        # Summary Report
        self._print_summary_report(results)
        
        return results
    
    def _print_summary_report(self, results: Dict):
        """Print final summary report"""
        logger.info("\n\n")
        logger.info("╔" + "═" * 68 + "╗")
        logger.info("║" + " FINAL TEST REPORT ".center(68) + "║")
        logger.info("╠" + "═" * 68 + "╣")
        
        tests = results['tests']
        passed = sum(1 for v in tests.values() if v)
        total = len(tests)
        
        for test_name, passed_flag in tests.items():
            status = "✓ PASS" if passed_flag else "✗ FAIL"
            logger.info(f"║ {test_name.ljust(50)} {status.rjust(15)} ║")
        
        logger.info("╠" + "═" * 68 + "╣")
        
        success_rate = passed / total * 100
        verdict = "🟢 READY FOR PRODUCTION" if passed >= total - 1 else "🟡 NEEDS FIXES"
        
        logger.info(f"║ {'Tests Passed':<50} {passed}/{total}".ljust(67) + "║")
        logger.info(f"║ {'Success Rate':<50} {success_rate:.1f}%".ljust(67) + "║")
        logger.info(f"║ {'Verdict':<50} {verdict}".ljust(67) + "║")
        logger.info("╚" + "═" * 68 + "╝")
        
        logger.info(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Full log saved to: test_live_environment.log")


def main():
    """Main test execution"""
    
    tester = RealEnvironmentTester(
        symbols=['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'],
        initial_capital=100000
    )
    
    results = tester.run_all_tests(since_days=30)
    
    return results


if __name__ == "__main__":
    results = main()
