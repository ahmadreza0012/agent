"""
Reinforcement Learning Agent for Trading
Uses PPO and SAC algorithms from Stable Baselines3
"""
import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple, Any
from typing import Callable

logger = logging.getLogger(__name__)

try:
    from stable_baselines3 import PPO, SAC
    from stable_baselines3.common.vec_env import DummyVecEnv
    from gymnasium import Env, spaces
    import gymnasium as gym
    SB3_AVAILABLE = True
except ImportError:
    SB3_AVAILABLE = False
    logger.warning("Stable Baselines3 or Gymnasium not available")


class TradingEnvironment(Env):
    """
    Gym-compatible trading environment
    """
    
    def __init__(self, prices: pd.DataFrame, returns: pd.DataFrame,
                 initial_capital: float = 100000,
                 transaction_cost: float = 0.001,
                 risk_limit: float = 0.15):
        
        super().__init__()
        self.prices = prices
        self.returns = returns
        self.n_assets = len(prices.columns)
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost
        self.risk_limit = risk_limit
        
        self.current_step = 0
        self.portfolio_value = initial_capital
        self.weights = np.ones(self.n_assets) / self.n_assets
        
        # Action space: weight allocation for each asset
        self.action_space = spaces.Box(low=0, high=1, shape=(self.n_assets,), dtype=np.float32)
        
        # Observation space: prices, returns, portfolio value
        obs_dim = self.n_assets * 3 + 2  # prices, returns, volume, portfolio_value, total_return
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32)
    
    def reset(self, seed=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.portfolio_value = self.initial_capital
        self.weights = np.ones(self.n_assets) / self.n_assets
        return self._get_observation()
    
    def step(self, action):
        # Normalize weights
        weights = np.clip(action, 0, 1)
        weights = weights / (weights.sum() + 1e-8)
        
        # Calculate transaction costs
        weight_change = np.abs(weights - self.weights).sum()
        transaction_cost = self.portfolio_value * weight_change * self.transaction_cost
        
        # Get returns
        period_returns = self.returns.iloc[self.current_step].values
        portfolio_return = (weights * period_returns).sum()
        
        # Update portfolio
        self.portfolio_value *= (1 + portfolio_return)
        self.portfolio_value -= transaction_cost
        self.weights = weights
        
        # Calculate reward
        reward = portfolio_return - self.transaction_cost * weight_change
        
        # Move to next step
        self.current_step += 1
        done = self.current_step >= len(self.returns) - 1
        
        obs = self._get_observation()
        info = {
            'portfolio_value': self.portfolio_value,
            'weights': weights,
            'return': portfolio_return
        }
        
        return obs, reward, done, False, info
    
    def _get_observation(self):
        if self.current_step >= len(self.prices):
            self.current_step = len(self.prices) - 1
        
        prices = self.prices.iloc[self.current_step].values
        returns = self.returns.iloc[self.current_step].values if self.current_step > 0 else np.zeros(self.n_assets)
        
        # Normalize
        prices = prices / (np.max(prices) + 1e-8)
        
        total_return = (self.portfolio_value - self.initial_capital) / self.initial_capital
        
        obs = np.concatenate([
            prices,
            returns,
            self.weights,
            [self.portfolio_value / self.initial_capital],
            [total_return]
        ])
        
        return obs.astype(np.float32)


class RLTradingAgent:
    """
    RL-based trading agent using PPO or SAC
    """
    
    def __init__(self, algorithm: str = 'PPO', learning_rate: float = 3e-4, verbose: int = 0):
        self.algorithm = algorithm
        self.learning_rate = learning_rate
        self.verbose = verbose
        self.model = None
        self.env = None
        
        if not SB3_AVAILABLE:
            logger.warning("SB3 not available")
    
    def create_environment(self, prices: pd.DataFrame, returns: pd.DataFrame,
                          n_envs: int = 4,
                          transaction_cost: float = 0.001,
                          risk_limit: float = 0.15):
        """
        Create training environment(s)
        """
        if not SB3_AVAILABLE:
            logger.warning("Cannot create environment - SB3 not available")
            return
        
        def make_env():
            return TradingEnvironment(
                prices=prices,
                returns=returns,
                transaction_cost=transaction_cost,
                risk_limit=risk_limit
            )
        
        self.env = DummyVecEnv([make_env for _ in range(n_envs)])
        logger.info(f"Environment created with {n_envs} parallel envs")
    
    def train(self, total_timesteps: int = 50000, save_path: str = 'rl_models/'):
        """
        Train the RL agent
        """
        if not SB3_AVAILABLE or self.env is None:
            logger.warning("Cannot train - SB3 not available or no environment")
            return
        
        try:
            if self.algorithm == 'PPO':
                self.model = PPO(
                    'MlpPolicy',
                    self.env,
                    learning_rate=self.learning_rate,
                    verbose=self.verbose
                )
            elif self.algorithm == 'SAC':
                self.model = SAC(
                    'MlpPolicy',
                    self.env,
                    learning_rate=self.learning_rate,
                    verbose=self.verbose
                )
            else:
                raise ValueError(f"Unknown algorithm: {self.algorithm}")
            
            self.model.learn(total_timesteps=total_timesteps)
            
            # Save model
            import os
            os.makedirs(save_path, exist_ok=True)
            model_path = f"{save_path}{self.algorithm.lower()}_model"
            self.model.save(model_path)
            logger.info(f"Model saved to {model_path}")
            
        except Exception as e:
            logger.error(f"Training failed: {e}")
    
    def predict(self, obs, deterministic: bool = True):
        """
        Get action from trained model
        """
        if self.model is None:
            return None
        
        action, _ = self.model.predict(obs, deterministic=deterministic)
        return action
    
    def load(self, path: str):
        """
        Load trained model
        """
        if not SB3_AVAILABLE:
            logger.warning("Cannot load - SB3 not available")
            return
        
        try:
            if self.algorithm == 'PPO':
                self.model = PPO.load(path)
            elif self.algorithm == 'SAC':
                self.model = SAC.load(path)
            logger.info(f"Model loaded from {path}")
        except Exception as e:
            logger.error(f"Loading failed: {e}")


class StrategySelectorRL:
    """
    RL-based strategy selector
    Learns which strategy works best in different market conditions
    """
    
    STRATEGIES = [
        'momentum',
        'mean_reversion',
        'risk_parity',
        'black_litterman'
    ]
    
    def __init__(self):
        self.strategy_scores = {s: [] for s in self.STRATEGIES}
    
    def record_performance(self, strategy: str, return_val: float, sharpe: float):
        """
        Record strategy performance
        """
        score = return_val * sharpe  # Combined score
        self.strategy_scores[strategy].append(score)
    
    def get_best_strategy(self) -> str:
        """
        Get best performing strategy
        """
        avg_scores = {s: np.mean(self.strategy_scores[s]) if self.strategy_scores[s] else 0 for s in self.STRATEGIES}
        return max(avg_scores, key=avg_scores.get)
