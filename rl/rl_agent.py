"""
Reinforcement Learning Trading Agent
Implements PPO/SAC agents for position sizing and strategy selection
Uses stable-baselines3 for robust RL training
"""
import numpy as np
import pandas as pd
import gymnasium as gym
from gymnasium import spaces
from typing import Dict, List, Optional, Tuple, Any
import logging
import os
import json
from datetime import datetime

try:
    from stable_baselines3 import PPO, SAC, A2C
    from stable_baselines3.common.callbacks import BaseCallback, EvalCallback
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
    from stable_baselines3.common.monitor import Monitor
    SB3_AVAILABLE = True
except ImportError:
    SB3_AVAILABLE = False
    logging.warning("stable-baselines3 not available. RL features disabled.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradingEnv(gym.Env):
    """
    Custom Gym environment for crypto trading
    
    Features:
    - Multi-asset portfolio management
    - Position sizing via RL
    - Strategy selection
    - Realistic transaction costs
    - Risk constraints
    """
    
    metadata = {'render_modes': ['human', 'rgb_array']}
    
    def __init__(self, 
                 prices: pd.DataFrame,
                 returns: pd.DataFrame,
                 initial_capital: float = 100000,
                 transaction_cost: float = 0.001,
                 max_position: float = 1.0,
                 risk_limit: float = 0.15,
                 window_size: int = 48,
                 use_regime_features: bool = True):
        """
        Initialize trading environment
        
        Args:
            prices: Price DataFrame
            returns: Returns DataFrame  
            initial_capital: Starting capital
            transaction_cost: Trading cost per trade
            max_position: Maximum position size per asset
            risk_limit: Maximum drawdown limit
            window_size: Lookback window for observations
            use_regime_features: Include regime detection features
        """
        super().__init__()
        
        self.prices = prices
        self.returns = returns
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost
        self.max_position = max_position
        self.risk_limit = risk_limit
        self.window_size = window_size
        
        self.n_assets = len(prices.columns)
        
        # Action space: continuous weights for each asset [0, 1]
        self.action_space = spaces.Box(
            low=0.0, 
            high=max_position, 
            shape=(self.n_assets,), 
            dtype=np.float32
        )
        
        # Observation space: prices + returns + technical indicators + regime
        n_features = self._get_feature_count()
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(window_size, n_features),
            dtype=np.float32
        )
        
        # State variables
        self.current_step = 0
        self.capital = initial_capital
        self.positions = np.zeros(self.n_assets)
        self.weights_history = []
        self.portfolio_values = []
        
        logger.info(f"TradingEnv initialized: {self.n_assets} assets, "
                   f"window={window_size}, features={n_features}")
    
    def _get_feature_count(self) -> int:
        """Calculate number of observation features"""
        # Base features: price, return, volatility, momentum
        base_features = 4 * self.n_assets
        
        # Optional regime features
        if hasattr(self, 'regime_features'):
            base_features += self.regime_features.shape[1] if hasattr(self, 'regime_features') else 0
        
        return base_features
    
    def _get_observation(self) -> np.ndarray:
        """Get current observation window"""
        start_idx = max(0, self.current_step - self.window_size + 1)
        end_idx = self.current_step + 1
        
        # Get price and return windows
        price_window = self.prices.iloc[start_idx:end_idx].values
        return_window = self.returns.iloc[start_idx:end_idx].values
        
        # Calculate technical features
        volatility = self.returns.iloc[start_idx:end_idx].rolling(
            min(12, self.window_size)
        ).std().fillna(0).values
        
        momentum = self.prices.iloc[start_idx:end_idx].pct_change(
            min(24, self.window_size)
        ).fillna(0).values
        
        # Stack features
        features = np.stack([price_window, return_window, volatility, momentum], axis=-1)
        features = features.reshape(features.shape[0], -1)
        
        # Normalize
        features = (features - np.mean(features, axis=0)) / (np.std(features, axis=0) + 1e-10)
        
        # Pad if necessary
        if len(features) < self.window_size:
            padding = np.zeros((self.window_size - len(features), features.shape[1]))
            features = np.vstack([padding, features])
        
        return features.astype(np.float32)
    
    def reset(self, seed=None, options=None) -> Tuple[np.ndarray, Dict]:
        """Reset environment to initial state"""
        super().reset(seed=seed)
        
        self.current_step = self.window_size  # Start after warmup
        self.capital = self.initial_capital
        self.positions = np.ones(self.n_assets) / self.n_assets  # Equal weight start
        self.weights_history = []
        self.portfolio_values = [self.initial_capital]
        
        obs = self._get_observation()
        info = {'capital': self.capital, 'step': self.current_step}
        
        return obs, info
    
    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        Execute one time step
        
        Args:
            action: New target weights from RL agent
            
        Returns:
            Tuple of (observation, reward, terminated, truncated, info)
        """
        # Normalize action to valid weights
        action = np.clip(action, 0, self.max_position)
        action_sum = action.sum()
        if action_sum > 0:
            action = action / action_sum  # Normalize to sum to 1
        else:
            action = np.ones(self.n_assets) / self.n_assets
        
        # Calculate turnover and transaction costs
        turnover = np.abs(action - self.positions).sum() / 2
        cost = self.capital * turnover * self.transaction_cost
        
        # Apply transaction costs
        self.capital -= cost
        
        # Get current returns
        if self.current_step < len(self.returns):
            period_returns = self.returns.iloc[self.current_step].values
            
            # Update positions based on returns
            position_values = self.capital * self.positions * (1 + period_returns)
            self.capital = position_values.sum()
        
        # Update positions
        self.positions = action
        self.weights_history.append(action.copy())
        self.portfolio_values.append(self.capital)
        
        # Calculate reward (Sharpe ratio of recent returns)
        if len(self.portfolio_values) > 1:
            port_returns = np.diff(self.portfolio_values[-20:]) / np.array(self.portfolio_values[-20:-1])
            if len(port_returns) > 1 and np.std(port_returns) > 0:
                reward = np.mean(port_returns) / np.std(port_returns)  # Sharpe
            else:
                reward = 0
        else:
            reward = 0
        
        # Penalize high turnover
        reward -= turnover * 0.1
        
        # Check termination conditions
        terminated = False
        truncated = False
        
        # Max drawdown breach
        if len(self.portfolio_values) > 1:
            running_max = max(self.portfolio_values)
            drawdown = (self.capital - running_max) / running_max
            if drawdown < -self.risk_limit:
                terminated = True
                reward -= 10  # Large penalty
        
        # Out of capital
        if self.capital <= self.initial_capital * 0.1:
            terminated = True
            reward -= 10
        
        # End of data
        if self.current_step >= len(self.prices) - 1:
            truncated = True
        
        self.current_step += 1
        
        # Get next observation
        obs = self._get_observation()
        
        info = {
            'capital': self.capital,
            'step': self.current_step,
            'turnover': turnover,
            'cost': cost,
            'positions': self.positions.copy(),
            'portfolio_value': self.capital
        }
        
        return obs, float(reward), terminated, truncated, info
    
    def render(self, mode='human'):
        """Render environment state"""
        if mode == 'human':
            print(f"Step: {self.current_step}")
            print(f"Capital: ${self.capital:,.2f}")
            print(f"Positions: {self.positions}")
            print(f"Return: {(self.capital - self.initial_capital) / self.initial_capital:.2%}")


class RLTradingAgent:
    """
    Reinforcement Learning Trading Agent
    
    Features:
    - PPO/SAC/A2C algorithms
    - Automatic hyperparameter tuning
    - Experience replay and memory
    - Online learning capability
    - Strategy selection via RL
    """
    
    def __init__(self,
                 algorithm: str = 'PPO',
                 policy_type: str = 'MlpPolicy',
                 learning_rate: float = 3e-4,
                 n_steps: int = 2048,
                 batch_size: int = 64,
                 n_epochs: int = 10,
                 gamma: float = 0.99,
                 gae_lambda: float = 0.95,
                 verbose: int = 1):
        """
        Initialize RL agent
        
        Args:
            algorithm: RL algorithm ('PPO', 'SAC', 'A2C')
            policy_type: Policy network type
            learning_rate: Learning rate
            n_steps: Steps per rollout
            batch_size: Training batch size
            n_epochs: Training epochs per update
            gamma: Discount factor
            gae_lambda: GAE lambda for advantage estimation
            verbose: Verbosity level
        """
        if not SB3_AVAILABLE:
            raise ImportError("stable-baselines3 required for RL agent")
        
        self.algorithm = algorithm
        self.policy_type = policy_type
        self.learning_rate = learning_rate
        self.verbose = verbose
        
        # Model hyperparameters
        self.n_steps = n_steps
        self.batch_size = batch_size
        self.n_epochs = n_epochs
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        
        self.model = None
        self.env = None
        self.training_history = []
        
        logger.info(f"RLTradingAgent initialized: {algorithm}")
    
    def create_environment(self, prices: pd.DataFrame,
                          returns: pd.DataFrame,
                          n_envs: int = 4,
                          **env_kwargs) -> gym.Env:
        """
        Create vectorized trading environment
        
        Args:
            prices: Price DataFrame
            returns: Returns DataFrame
            n_envs: Number of parallel environments
            env_kwargs: Additional environment arguments
            
        Returns:
            Vectorized Gym environment
        """
        def make_env():
            env = TradingEnv(prices, returns, **env_kwargs)
            env = Monitor(env)
            return env
        
        if n_envs > 1:
            self.env = SubprocVecEnv([make_env for _ in range(n_envs)])
        else:
            self.env = DummyVecEnv([make_env])
        
        logger.info(f"Created {n_envs} parallel trading environments")
        return self.env
    
    def train(self,
              total_timesteps: int = 100000,
              eval_env: gym.Env = None,
              eval_freq: int = 10000,
              save_path: str = 'rl_models/',
              log_interval: int = 1000) -> Any:
        """
        Train RL agent
        
        Args:
            total_timesteps: Total training timesteps
            eval_env: Evaluation environment
            eval_freq: Evaluation frequency
            save_path: Directory to save models
            log_interval: Logging interval
            
        Returns:
            Trained model
        """
        os.makedirs(save_path, exist_ok=True)
        
        # Create model based on algorithm
        if self.algorithm == 'PPO':
            self.model = PPO(
                policy=self.policy_type,
                env=self.env,
                learning_rate=self.learning_rate,
                n_steps=self.n_steps,
                batch_size=self.batch_size,
                n_epochs=self.n_epochs,
                gamma=self.gamma,
                gae_lambda=self.gae_lambda,
                verbose=self.verbose,
                tensorboard_log=f"{save_path}/tensorboard"
            )
        elif self.algorithm == 'SAC':
            self.model = SAC(
                policy=self.policy_type,
                env=self.env,
                learning_rate=self.learning_rate,
                buffer_size=100000,
                batch_size=self.batch_size,
                gamma=self.gamma,
                tau=0.005,
                verbose=self.verbose,
                tensorboard_log=f"{save_path}/tensorboard"
            )
        elif self.algorithm == 'A2C':
            self.model = A2C(
                policy=self.policy_type,
                env=self.env,
                learning_rate=self.learning_rate,
                gamma=self.gamma,
                verbose=self.verbose,
                tensorboard_log=f"{save_path}/tensorboard"
            )
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm}")
        
        # Setup callbacks
        callbacks = []
        
        if eval_env is not None:
            eval_callback = EvalCallback(
                eval_env,
                best_model_save_path=save_path,
                log_path=save_path,
                eval_freq=eval_freq,
                deterministic=True,
                render=False
            )
            callbacks.append(eval_callback)
        
        # Train
        logger.info(f"Starting training for {total_timesteps} timesteps...")
        self.model.learn(
            total_timesteps=total_timesteps,
            callback=callbacks if callbacks else None,
            log_interval=log_interval
        )
        
        # Save final model
        self.model.save(f"{save_path}/{self.algorithm}_final")
        logger.info(f"Training complete. Model saved to {save_path}")
        
        return self.model
    
    def predict(self, observation: np.ndarray, 
               deterministic: bool = True) -> np.ndarray:
        """
        Get action prediction from trained model
        
        Args:
            observation: Current observation
            deterministic: Use deterministic policy
            
        Returns:
            Predicted action (weights)
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        action, _ = self.model.predict(observation, deterministic=deterministic)
        return action
    
    def evaluate(self, env: gym.Env = None, 
                n_episodes: int = 10) -> Dict:
        """
        Evaluate trained agent
        
        Args:
            env: Evaluation environment
            n_episodes: Number of episodes
            
        Returns:
            Evaluation metrics
        """
        if self.model is None:
            raise ValueError("Model not trained")
        
        if env is None:
            env = self.env
        
        episode_rewards = []
        episode_returns = []
        
        for _ in range(n_episodes):
            obs, _ = env.reset()
            done = False
            total_reward = 0
            
            while not done:
                action, _ = self.model.predict(obs, deterministic=True)
                obs, reward, terminated, truncated, info = env.step(action)
                total_reward += reward
                done = terminated or truncated
            
            episode_rewards.append(total_reward)
            if 'portfolio_value' in info:
                episode_returns.append(
                    (info['portfolio_value'] - env.initial_capital) / env.initial_capital
                )
        
        metrics = {
            'mean_reward': np.mean(episode_rewards),
            'std_reward': np.std(episode_rewards),
            'mean_return': np.mean(episode_returns) if episode_returns else 0,
            'best_return': max(episode_returns) if episode_returns else 0,
            'worst_return': min(episode_returns) if episode_returns else 0
        }
        
        logger.info(f"Evaluation complete: Mean Return = {metrics['mean_return']:.2%}")
        return metrics
    
    def save_model(self, path: str):
        """Save model to file"""
        if self.model:
            self.model.save(path)
            logger.info(f"Model saved to {path}")
    
    def load_model(self, path: str):
        """Load model from file"""
        if self.algorithm == 'PPO':
            self.model = PPO.load(path, env=self.env)
        elif self.algorithm == 'SAC':
            self.model = SAC.load(path, env=self.env)
        elif self.algorithm == 'A2C':
            self.model = A2C.load(path, env=self.env)
        logger.info(f"Model loaded from {path}")
    
    def online_finetune(self, new_data: pd.DataFrame,
                       n_timesteps: int = 10000,
                       learning_rate: float = 1e-4) -> None:
        """
        Fine-tune model with new data (online learning)
        
        Args:
            new_data: New price/return data
            n_timesteps: Fine-tuning timesteps
            learning_rate: Reduced learning rate for fine-tuning
        """
        if self.model is None:
            raise ValueError("No pre-trained model to fine-tune")
        
        logger.info(f"Online fine-tuning with {len(new_data)} new data points...")
        
        # Create new environment with recent data
        returns = new_data.pct_change().dropna()
        self.create_environment(new_data, returns)
        
        # Reduce learning rate for fine-tuning
        self.model.learning_rate = learning_rate
        
        # Continue training
        self.model.learn(total_timesteps=n_timesteps)
        
        logger.info("Online fine-tuning complete")


class StrategySelectorRL(RLTradingAgent):
    """
    RL agent specialized for strategy selection
    
    Instead of direct position sizing, selects among predefined strategies:
    - Momentum
    - Mean Reversion
    - Risk Parity
    - Black-Litterman
    """
    
    def __init__(self, strategies: List[str] = None, **kwargs):
        """
        Initialize strategy selector
        
        Args:
            strategies: List of strategy names
            kwargs: Parent class arguments
        """
        self.strategies = strategies or [
            'momentum', 'mean_reversion', 'risk_parity', 
            'black_litterman', 'equal_weight'
        ]
        
        super().__init__(**kwargs)
        
        # Discrete action space for strategy selection
        self.n_strategies = len(self.strategies)
        logger.info(f"StrategySelectorRL initialized with {self.n_strategies} strategies")
    
    def select_strategy(self, observation: np.ndarray,
                       market_regime: str = None) -> str:
        """
        Select optimal strategy given market state
        
        Args:
            observation: Market observation
            market_regime: Detected market regime (optional)
            
        Returns:
            Selected strategy name
        """
        if self.model is None:
            # Default: equal weight
            return 'equal_weight'
        
        action, _ = self.model.predict(observation, deterministic=True)
        
        # Map action to strategy
        if isinstance(action, np.ndarray):
            action_idx = int(action[0]) % self.n_strategies
        else:
            action_idx = int(action) % self.n_strategies
        
        selected = self.strategies[action_idx]
        logger.info(f"Selected strategy: {selected} (regime: {market_regime})")
        
        return selected


if __name__ == "__main__":
    # Test RL agent
    np.random.seed(42)
    
    # Generate sample data
    dates = pd.date_range('2024-01-01', periods=1000, freq='H')
    n_assets = 3
    
    returns_data = np.random.randn(1000, n_assets) * 0.01 + 0.0001
    prices_data = 100 * np.exp(np.cumsum(returns_data, axis=0))
    
    prices = pd.DataFrame(prices_data, index=dates, columns=['BTC', 'ETH', 'SOL'])
    returns = prices.pct_change().dropna()
    
    if SB3_AVAILABLE:
        # Create and train agent
        agent = RLTradingAgent(algorithm='PPO', verbose=1)
        agent.create_environment(prices, returns, n_envs=2)
        
        # Quick training test
        agent.train(total_timesteps=5000, save_path='test_models/')
        
        # Evaluate
        metrics = agent.evaluate(n_episodes=3)
        print(f"\n=== RL Agent Evaluation ===")
        for k, v in metrics.items():
            print(f"{k}: {v:.4f}" if isinstance(v, float) else f"{k}: {v}")
    else:
        print("stable-baselines3 not available. Skipping RL test.")
