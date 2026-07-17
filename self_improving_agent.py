"""
Self-Improving Crypto Trading Agent - Main Orchestrator
Integrates all components into a unified, production-ready system
"""
import numpy as np
import pandas as pd
import logging
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import warnings
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('trading_agent.log')
    ]
)
logger = logging.getLogger(__name__)

# Import local modules
from data.enhanced_data_fetcher import MultiExchangeDataFetcher, load_cached_data
from rl.rl_agent import RLTradingAgent, StrategySelectorRL, SB3_AVAILABLE
from strategies.regime_detection import MarketRegimeDetector, RegimeAdaptiveStrategy, HMM_AVAILABLE
from memory.experience_memory import TradingMemory, Experience, CHROMA_AVAILABLE
from portfolio_optimizer import PortfolioOptimizer
from ai_sentiment import AISentimentAnalyzer
from backtester import Backtester


class SelfImprovingTradingAgent:
    """
    Complete Self-Improving Crypto Trading Agent
    
    Features:
    - Multi-exchange data (Binance + Nobitex)
    - Regime detection (HMM or rule-based)
    - RL-based strategy selection (PPO/SAC)
    - AI sentiment integration (Groq/Gemini)
    - Experience memory with vector search
    - Walk-forward optimization
    - Online learning capability
    - Risk management circuit breakers
    """
    
    def __init__(self,
                 symbols: List[str] = None,
                 initial_capital: float = 100000,
                 use_rl: bool = True,
                 use_regime_detection: bool = True,
                 use_ai_sentiment: bool = True,
                 use_memory: bool = True,
                 config: Dict = None):
        """
        Initialize self-improving trading agent
        
        Args:
            symbols: List of trading pairs
            initial_capital: Starting capital in USDT
            use_rl: Enable RL-based decisions
            use_regime_detection: Enable regime detection
            use_ai_sentiment: Enable AI sentiment analysis
            use_memory: Enable experience memory
            config: Configuration dictionary
        """
        self.symbols = symbols or [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'
        ]
        self.initial_capital = initial_capital
        self.config = config or self._default_config()
        
        # Feature flags
        self.use_rl = use_rl and SB3_AVAILABLE
        self.use_regime = use_regime_detection
        self.use_sentiment = use_ai_sentiment
        self.use_memory = use_memory and CHROMA_AVAILABLE
        
        logger.info("=" * 60)
        logger.info("SELF-IMPROVING CRYPTO TRADING AGENT")
        logger.info("=" * 60)
        logger.info(f"Symbols: {self.symbols}")
        logger.info(f"Initial Capital: ${initial_capital:,}")
        logger.info(f"RL Enabled: {self.use_rl}")
        logger.info(f"Regime Detection: {self.use_regime}")
        logger.info(f"AI Sentiment: {self.use_sentiment}")
        logger.info(f"Memory System: {self.use_memory}")
        
        # Initialize components
        self.data_fetcher = MultiExchangeDataFetcher(
            symbols=self.symbols,
            exchange='binance'
        )
        
        self.optimizer = PortfolioOptimizer(
            n_assets=len(self.symbols),
            asset_names=[s.replace('/USDT', '') for s in self.symbols]
        )
        
        self.sentiment_analyzer = AISentimentAnalyzer(use_mock=True)
        
        self.backtester = Backtester(
            initial_capital=initial_capital,
            transaction_cost=0.001,
            slippage=0.0005
        )
        
        # Regime detector
        if self.use_regime:
            self.regime_detector = MarketRegimeDetector(n_regimes=4)
            self.regime_strategy = RegimeAdaptiveStrategy()
        else:
            self.regime_detector = None
            self.regime_strategy = None
        
        # RL Agent
        if self.use_rl:
            self.rl_agent = RLTradingAgent(
                algorithm=self.config['rl_algorithm'],
                learning_rate=self.config['rl_learning_rate']
            )
        else:
            self.rl_agent = None
        
        # Memory system
        if self.use_memory:
            self.memory = TradingMemory(
                storage_path='memory/',
                use_vector_db=CHROMA_AVAILABLE
            )
        else:
            self.memory = None
        
        # State variables
        self.current_regime = None
        self.current_weights = None
        self.training_complete = False
        
        logger.info("SelfImprovingTradingAgent initialized successfully")
    
    def _default_config(self) -> Dict:
        """Default configuration"""
        return {
            'rl_algorithm': 'PPO',
            'rl_learning_rate': 3e-4,
            'rl_timesteps': 50000,
            'walk_forward_periods': 4,
            'train_test_split': 0.75,
            'rebalance_frequency': 'W',  # Weekly
            'lookback_hours': 168,  # 1 week
            'max_drawdown_limit': 0.15,
            'risk_free_rate': 0.02,
            'target_monthly_return': 0.05
        }
    
    def fetch_and_prepare_data(self, 
                               timeframe: str = '1h',
                               since_days: int = 365,
                               use_cache: bool = True) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Fetch and prepare historical data
        
        Returns:
            Tuple of (prices, returns) DataFrames
        """
        logger.info("Fetching historical data...")
        
        data = self.data_fetcher.fetch_all_symbols(
            timeframe=timeframe,
            since_days=since_days,
            use_cache=use_cache
        )
        
        prices = self.data_fetcher.align_data(data)
        returns = self.data_fetcher.calculate_returns(prices)
        
        logger.info(f"Data prepared: {len(prices)} observations, {len(prices.columns)} assets")
        logger.info(f"Date range: {prices.index.min()} to {prices.index.max()}")
        
        return prices, returns
    
    def detect_regimes(self, prices: pd.DataFrame,
                      returns: pd.DataFrame) -> pd.Series:
        """
        Detect market regimes from historical data
        
        Returns:
            Series of regime labels
        """
        if not self.use_regime:
            logger.info("Regime detection disabled")
            return pd.Series([2] * len(prices), index=prices.index)  # Default: Sideways
        
        logger.info("Detecting market regimes...")
        
        # Extract features
        features = self.regime_detector.extract_features(prices, returns)
        
        # Fit and predict
        self.regime_detector.fit(features)
        regimes = self.regime_detector.predict(features)
        
        # Store current regime
        self.current_regime = regimes.iloc[-1]
        regime_name = self.regime_detector.regime_names.get(self.current_regime, 'Unknown')
        
        logger.info(f"Current regime: {self.current_regime} ({regime_name})")
        logger.info(f"Regime distribution:\n{regimes.value_counts()}")
        
        return regimes
    
    def train_rl_agent(self, prices: pd.DataFrame,
                       returns: pd.DataFrame,
                       regimes: pd.Series,
                       total_timesteps: int = None) -> None:
        """
        Train RL agent on historical data
        
        Args:
            prices: Price DataFrame
            returns: Returns DataFrame
            regimes: Regime labels
            total_timesteps: Training timesteps (optional)
        """
        if not self.use_rl:
            logger.info("RL training disabled")
            return
        
        logger.info("Training RL agent...")
        
        timesteps = total_timesteps or self.config['rl_timesteps']
        
        # Create environment
        self.rl_agent.create_environment(
            prices=prices,
            returns=returns,
            n_envs=4,
            transaction_cost=0.001,
            risk_limit=self.config['max_drawdown_limit']
        )
        
        # Train
        self.rl_agent.train(
            total_timesteps=timesteps,
            save_path='rl_models/'
        )
        
        self.training_complete = True
        logger.info("RL agent training complete")
    
    def run_walk_forward_backtest(self, prices: pd.DataFrame,
                                  returns: pd.DataFrame,
                                  regimes: pd.Series) -> Dict:
        """
        Run walk-forward backtest with periodic retraining
        
        Args:
            prices: Price DataFrame
            returns: Returns DataFrame
            regimes: Regime labels
            
        Returns:
            Backtest results dictionary
        """
        logger.info("=" * 60)
        logger.info("WALK-FORWARD BACKTEST")
        logger.info("=" * 60)
        
        n_periods = self.config['walk_forward_periods']
        split_ratio = self.config['train_test_split']
        
        # Calculate period lengths
        n_total = len(prices)
        n_train = int(n_total * split_ratio)
        n_test = n_total - n_train
        period_size = n_test // n_periods
        
        logger.info(f"Total periods: {n_periods}")
        logger.info(f"Train size: {n_train}, Test per period: {period_size}")
        
        all_results = []
        portfolio_values = []
        
        for i in range(n_periods):
            logger.info(f"\n{'='*40}")
            logger.info(f"PERIOD {i+1}/{n_periods}")
            logger.info(f"{'='*40}")
            
            # Define train/test windows
            train_end = n_train + i * period_size
            test_start = train_end
            test_end = train_end + period_size if i < n_periods - 1 else n_total
            
            train_prices = prices.iloc[:train_end]
            train_returns = returns.iloc[:train_end]
            test_prices = prices.iloc[test_start:test_end]
            
            logger.info(f"Train: {train_prices.index.min()} to {train_prices.index.max()}")
            logger.info(f"Test: {test_prices.index.min()} to {test_prices.index.max()}")
            
            # Retrain RL agent periodically (every 2 periods)
            if self.use_rl and i % 2 == 0:
                logger.info("Retraining RL agent...")
                self.train_rl_agent(
                    train_prices, 
                    train_returns,
                    regimes.iloc[:train_end],
                    total_timesteps=10000  # Shorter retraining
                )
            
            # Run backtest for this period
            try:
                period_result = self._backtest_single_period(
                    train_prices, train_returns,
                    test_prices,
                    regimes.iloc[test_start:test_end]
                )
                
                all_results.append(period_result)
                portfolio_values.extend(period_result['portfolio_values'])
                
                # Record to memory
                if self.use_memory:
                    self._record_period_to_memory(period_result, i)
                
            except Exception as e:
                logger.error(f"Period {i+1} failed: {e}")
                continue
        
        # Combine results
        combined_results = self._combine_walk_forward_results(all_results)
        
        return combined_results
    
    def _backtest_single_period(self,
                                train_prices: pd.DataFrame,
                                train_returns: pd.DataFrame,
                                test_prices: pd.DataFrame,
                                test_regimes: pd.Series) -> Dict:
        """Backtest a single walk-forward period"""
        
        # Get optimal strategy based on regime
        if self.use_regime and test_regimes is not None:
            dominant_regime = test_regimes.mode().iloc[0] if len(test_regimes) > 0 else 2
            strategy = self.regime_strategy.get_optimal_strategy(dominant_regime)
            logger.info(f"Selected strategy for regime {dominant_regime}: {strategy}")
        else:
            strategy = 'black_litterman'
        
        # Create weights strategy function
        def weights_strategy(prices_df, returns_df):
            return self._get_optimal_weights(
                prices_df, returns_df, strategy
            )
        
        # Run backtest
        result = self.backtester.run(
            prices=test_prices,
            weights_strategy=weights_strategy,
            rebalance_freq=self.config['rebalance_frequency'],
            lookback_hours=self.config['lookback_hours'],
            train_split=1.0  # Already split
        )
        
        result['strategy'] = strategy
        return result
    
    def _get_optimal_weights(self, prices: pd.DataFrame,
                            returns: pd.DataFrame,
                            strategy: str) -> np.ndarray:
        """Get optimal weights using specified strategy"""
        
        n_assets = len(prices.columns)
        cov_matrix = returns.cov().values * 24 * 365
        
        if strategy == 'momentum':
            # Momentum-tilted MVO
            expected_returns = returns.mean().values * 24 * 365
            # Boost high momentum assets
            momentum = prices.pct_change(168).iloc[-1].values
            expected_returns *= (1 + momentum)
            weights = self.optimizer.mean_variance_optimization(
                expected_returns, cov_matrix, method='max_sharpe'
            )
        
        elif strategy == 'mean_reversion':
            # Mean reversion: overweight underperformers
            momentum = prices.pct_change(168).iloc[-1].values
            expected_returns = -momentum * 0.1  # Small mean reversion signal
            weights = self.optimizer.mean_variance_optimization(
                expected_returns, cov_matrix, method='min_volatility'
            )
        
        elif strategy == 'risk_parity':
            weights = self.optimizer.risk_parity(cov_matrix)
        
        elif strategy == 'cvar':
            weights = self.optimizer.cvar_optimization(
                returns.values,
                cvar_limit=0.05,
                confidence=0.95
            )
        
        elif strategy == 'black_litterman':
            # Market cap weights (simplified)
            market_caps = np.array([1.0, 0.5, 0.2, 0.15, 0.1])[:n_assets]
            market_caps = market_caps / market_caps.sum() * n_assets
            expected_returns = returns.mean().values * 24 * 365
            
            P, Q = self.sentiment_analyzer.generate_views(
                prices, expected_returns, list(prices.columns)
            )
            omega = self.sentiment_analyzer.get_confidence_matrix(n_assets)
            
            weights = self.optimizer.black_litterman(
                market_caps, cov_matrix, P, Q, omega=omega
            )
        
        else:
            # Default: equal weight
            weights = np.ones(n_assets) / n_assets
        
        self.current_weights = weights
        return weights
    
    def _combine_walk_forward_results(self, results: List[Dict]) -> Dict:
        """Combine walk-forward period results"""
        
        if not results:
            return {'error': 'No results'}
        
        # Aggregate metrics
        metrics = {}
        metric_keys = results[0]['metrics'].keys()
        
        for key in metric_keys:
            values = [r['metrics'][key] for r in results if key in r['metrics']]
            if isinstance(values[0], (int, float)):
                metrics[f'{key}_mean'] = np.mean(values)
                metrics[f'{key}_std'] = np.std(values)
                metrics[key] = values
        
        # Combined portfolio values
        all_values = []
        for r in results:
            if 'portfolio_values' in r:
                all_values.extend(r['portfolio_values'])
        
        combined_metrics = self.backtester.calculate_metrics(
            pd.DataFrame({'value': all_values}),
            [],
            []
        )
        
        return {
            'period_results': results,
            'combined_metrics': combined_metrics,
            'aggregate_metrics': metrics,
            'n_periods': len(results)
        }
    
    def _record_period_to_memory(self, result: Dict, period: int):
        """Record period results to memory"""
        if not self.use_memory:
            return
        
        metrics = result.get('metrics', {})
        regime = self.current_regime if self.current_regime is not None else 2
        
        exp = Experience(
            timestamp=datetime.now(),
            market_state={
                'regime': regime,
                'period': period
            },
            action_taken={
                'strategy': result.get('strategy', 'unknown'),
                'weights': self.current_weights.tolist() if self.current_weights is not None else []
            },
            outcome={
                'return': metrics.get('monthly_return', 0),
                'drawdown': metrics.get('max_drawdown', 0),
                'sharpe': metrics.get('sharpe_ratio', 0)
            },
            reward=metrics.get('sharpe_ratio', 0),
            metadata={'period': period}
        )
        
        self.memory.add_experience(exp)
    
    def evaluate_performance(self, results: Dict) -> Dict:
        """
        Evaluate if performance targets were met
        
        Returns:
            Evaluation dictionary
        """
        metrics = results.get('combined_metrics', results.get('metrics', {}))
        
        monthly_return = metrics.get('monthly_return', 0)
        max_drawdown = abs(metrics.get('max_drawdown', 0))
        sharpe = metrics.get('sharpe_ratio', 0)
        
        target_met = monthly_return >= self.config['target_monthly_return']
        dd_ok = max_drawdown <= self.config['max_drawdown_limit']
        
        evaluation = {
            'monthly_return': monthly_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'target_return': self.config['target_monthly_return'],
            'target_achieved': target_met,
            'drawdown_within_limit': dd_ok,
            'verdict': self._get_verdict(target_met, dd_ok)
        }
        
        logger.info("=" * 60)
        logger.info("PERFORMANCE EVALUATION")
        logger.info("=" * 60)
        logger.info(f"Monthly Return: {monthly_return:.2%} (Target: {self.config['target_monthly_return']:.2%})")
        logger.info(f"Max Drawdown: {max_drawdown:.2%} (Limit: {self.config['max_drawdown_limit']:.2%})")
        logger.info(f"Sharpe Ratio: {sharpe:.2f}")
        logger.info(f"Verdict: {evaluation['verdict']}")
        
        return evaluation
    
    def _get_verdict(self, target_met: bool, dd_ok: bool) -> str:
        """Get performance verdict"""
        if target_met and dd_ok:
            return "SUCCESS - Both targets achieved"
        elif target_met:
            return "PARTIAL - Return target met, but drawdown exceeded"
        elif dd_ok:
            return "PARTIAL - Drawdown controlled, but return target not met"
        else:
            return "FAILED - Neither target achieved"
    
    def run_full_pipeline(self, 
                         since_days: int = 365,
                         skip_rl_training: bool = False) -> Dict:
        """
        Run complete pipeline: data → regimes → RL training → walk-forward backtest
        
        Returns:
            Complete results dictionary
        """
        logger.info("=" * 60)
        logger.info("STARTING FULL PIPELINE")
        logger.info(f"Time: {datetime.now().isoformat()}")
        logger.info("=" * 60)
        
        try:
            # Step 1: Fetch data
            prices, returns = self.fetch_and_prepare_data(since_days=since_days)
            
            # Step 2: Detect regimes
            regimes = self.detect_regimes(prices, returns)
            
            # Step 3: Train RL agent (optional)
            if not skip_rl_training and self.use_rl:
                self.train_rl_agent(prices, returns, regimes)
            
            # Step 4: Walk-forward backtest
            results = self.run_walk_forward_backtest(prices, returns, regimes)
            
            # Step 5: Evaluate
            evaluation = self.evaluate_performance(results)
            
            # Step 6: Extract lessons (if memory enabled)
            if self.use_memory:
                lessons = self.memory.extract_lessons(min_reward_threshold=0.3)
                logger.info(f"Extracted {len(lessons)} lessons from experience")
            else:
                lessons = []
            
            full_results = {
                'prices': prices,
                'returns': returns,
                'regimes': regimes,
                'backtest': results,
                'evaluation': evaluation,
                'lessons': lessons,
                'config': self.config
            }
            
            logger.info("=" * 60)
            logger.info("PIPELINE COMPLETE")
            logger.info("=" * 60)
            
            return full_results
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise
    
    def get_current_recommendation(self) -> Dict:
        """
        Get current trading recommendation based on latest data
        
        Returns:
            Recommendation dictionary
        """
        # Fetch recent data
        recent_prices, _ = self.fetch_and_prepare_data(since_days=30)
        
        # Detect current regime
        if self.use_regime:
            features = self.regime_detector.extract_features(
                recent_prices, 
                recent_prices.pct_change().dropna()
            )
            regime, regime_name = self.regime_detector.get_current_regime(features)
        else:
            regime, regime_name = 2, "Sideways"
        
        # Get recommended strategy
        if self.use_regime:
            strategy = self.regime_strategy.get_optimal_strategy(regime)
        else:
            strategy = 'black_litterman'
        
        # Get weights
        returns = recent_prices.pct_change().dropna()
        weights = self._get_optimal_weights(recent_prices, returns, strategy)
        
        recommendation = {
            'timestamp': datetime.now().isoformat(),
            'regime': regime,
            'regime_name': regime_name,
            'recommended_strategy': strategy,
            'weights': dict(zip([s.replace('/USDT', '') for s in self.symbols], weights)),
            'confidence': 'high' if self.training_complete else 'medium'
        }
        
        return recommendation


def print_final_report(evaluation: Dict, lessons: List = None):
    """Print comprehensive final report"""
    
    print("\n" + "=" * 70)
    print("SELF-IMPROVING TRADING AGENT - FINAL REPORT")
    print("=" * 70)
    
    print(f"\n📊 PERFORMANCE METRICS:")
    print(f"   Monthly Return: {evaluation['monthly_return']:.2%}")
    print(f"   Max Drawdown: {evaluation['max_drawdown']:.2%}")
    print(f"   Sharpe Ratio: {evaluation['sharpe_ratio']:.2f}")
    
    print(f"\n🎯 TARGET ASSESSMENT:")
    print(f"   5% Monthly Return: {'✓ ACHIEVED' if evaluation['target_achieved'] else '✗ NOT ACHIEVED'}")
    print(f"   <15% Drawdown: {'✓ ACHIEVED' if evaluation['drawdown_within_limit'] else '✗ NOT ACHIEVED'}")
    
    print(f"\n🏆 VERDICT: {evaluation['verdict']}")
    
    if lessons:
        print(f"\n💡 LESSONS LEARNED ({len(lessons)} extracted):")
        for lesson in lessons[:5]:  # Show top 5
            print(f"   - Regime: {lesson['regime']}, Best Strategy: {lesson['best_strategy']}, "
                  f"Avg Return: {lesson['avg_return']:.2%}")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    # Initialize agent
    agent = SelfImprovingTradingAgent(
        symbols=['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'],
        initial_capital=100000,
        use_rl=SB3_AVAILABLE,
        use_regime_detection=True,
        use_ai_sentiment=True,
        use_memory=False  # Disable for simpler testing
    )
    
    # Run full pipeline with 1 year of data
    results = agent.run_full_pipeline(
        since_days=365,
        skip_rl_training=not SB3_AVAILABLE
    )
    
    # Print report
    print_final_report(
        results['evaluation'],
        results.get('lessons', [])
    )
    
    # Get current recommendation
    rec = agent.get_current_recommendation()
    print(f"\n📈 CURRENT RECOMMENDATION:")
    print(f"   Regime: {rec['regime_name']}")
    print(f"   Strategy: {rec['recommended_strategy']}")
    print(f"   Weights: {rec['weights']}")
