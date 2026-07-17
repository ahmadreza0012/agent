"""
Reinforcement Learning Agent - Self-Learning Layer Skeleton

This module provides a skeleton for an RL agent that can learn from
trading outcomes and adapt the strategy over time.

Implements:
- Simple Q-learning based position sizing
- Online learning updater for model fine-tuning
- Reward loop based on PnL and risk-adjusted returns
"""

import logging
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from abc import ABC, abstractmethod
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RLAgent(ABC):
    """Abstract base class for RL trading agents."""
    
    @abstractmethod
    def select_action(self, state: np.ndarray) -> int:
        """Select action based on current state."""
        pass
    
    @abstractmethod
    def update(self, state: np.ndarray, action: int, reward: float, next_state: np.ndarray):
        """Update agent's policy based on experience."""
        pass
    
    @abstractmethod
    def reset(self):
        """Reset agent state."""
        pass


class QLearningAgent(RLAgent):
    """
    Simple Q-learning agent for position sizing decisions.
    
    State space: Discretized market conditions (RSI, MACD, volatility)
    Action space: Position size multiplier (0=flat, 1=50%, 2=100%, 3=150%)
    Reward: Risk-adjusted return (Sharpe-like metric)
    """
    
    def __init__(
        self,
        state_bins: Tuple[int, int, int] = (5, 5, 5),
        n_actions: int = 4,
        learning_rate: float = 0.1,
        discount_factor: float = 0.95,
        epsilon: float = 0.1
    ):
        self.state_bins = state_bins  # Bins for each state dimension
        self.n_actions = n_actions
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon  # Exploration rate
        
        # Q-table: state -> action -> value
        self.q_table: Dict[Tuple, np.ndarray] = defaultdict(
            lambda: np.zeros(n_actions)
        )
        
        self.episode_rewards: List[float] = []
        self.current_state: Optional[Tuple] = None
        
        logger.info(f"QLearningAgent initialized: {state_bins} state bins, {n_actions} actions")
    
    def discretize_state(self, continuous_state: np.ndarray) -> Tuple:
        """Convert continuous state to discrete bins."""
        # State dimensions: [rsi_normalized, macd_normalized, volatility_normalized]
        rsi, macd, volatility = continuous_state[:3]
        
        # Bin each dimension
        rsi_bin = min(int(rsi * self.state_bins[0]), self.state_bins[0] - 1)
        macd_bin = min(int((macd + 1) * 0.5 * self.state_bins[1]), self.state_bins[1] - 1)
        vol_bin = min(int(volatility * self.state_bins[2]), self.state_bins[2] - 1)
        
        return (rsi_bin, macd_bin, vol_bin)
    
    def select_action(self, state: np.ndarray, training: bool = True) -> int:
        """
        Select action using epsilon-greedy policy.
        
        Args:
            state: Continuous state vector
            training: If True, use exploration; if False, use exploitation only
        
        Returns:
            Action index (0 to n_actions-1)
        """
        discrete_state = self.discretize_state(state)
        self.current_state = discrete_state
        
        # Epsilon-greedy
        if training and np.random.random() < self.epsilon:
            return np.random.randint(self.n_actions)
        else:
            q_values = self.q_table[discrete_state]
            return int(np.argmax(q_values))
    
    def update(self, state: np.ndarray, action: int, reward: float, next_state: np.ndarray, done: bool = False):
        """
        Update Q-value using Bellman equation.
        
        Q(s,a) = Q(s,a) + α * [r + γ * max(Q(s',a')) - Q(s,a)]
        """
        discrete_state = self.discretize_state(state)
        next_discrete_state = self.discretize_state(next_state)
        
        # Current Q-value
        current_q = self.q_table[discrete_state][action]
        
        # Max Q-value for next state
        max_next_q = np.max(self.q_table[next_discrete_state])
        
        # Bellman update
        if not done:
            new_q = current_q + self.learning_rate * (
                reward + self.discount_factor * max_next_q - current_q
            )
        else:
            # Terminal state: no future reward
            new_q = current_q + self.learning_rate * (reward - current_q)
        
        self.q_table[discrete_state][action] = new_q
        self.episode_rewards.append(reward)
    
    def reset(self):
        """Reset episode tracking."""
        self.current_state = None
        episode_return = sum(self.episode_rewards)
        if len(self.episode_rewards) > 0:
            logger.debug(f"Episode completed: {len(self.episode_rewards)} steps, total reward: {episode_return:.4f}")
        self.episode_rewards = []
    
    def get_position_size_multiplier(self, action: int) -> float:
        """Convert action to position size multiplier."""
        multipliers = {0: 0.0, 1: 0.5, 2: 1.0, 3: 1.5}
        return multipliers.get(action, 1.0)
    
    def save_q_table(self, filepath: str):
        """Save Q-table to file."""
        import pickle
        with open(filepath, 'wb') as f:
            pickle.dump(dict(self.q_table), f)
        logger.info(f"Q-table saved to {filepath}")
    
    def load_q_table(self, filepath: str):
        """Load Q-table from file."""
        import pickle
        try:
            with open(filepath, 'rb') as f:
                loaded = pickle.load(f)
                self.q_table = defaultdict(lambda: np.zeros(self.n_actions), loaded)
            logger.info(f"Q-table loaded from {filepath}")
        except FileNotFoundError:
            logger.warning(f"Q-table file not found: {filepath}")


class OnlineLearningUpdater:
    """
    Online learning updater for ML model fine-tuning.
    
    Periodically updates the main prediction model with recent data
    to adapt to changing market conditions.
    """
    
    def __init__(
        self,
        model: Any,
        update_frequency: int = 100,
        max_buffer_size: int = 1000,
        warmup_samples: int = 50
    ):
        self.model = model
        self.update_frequency = update_frequency
        self.max_buffer_size = max_buffer_size
        self.warmup_samples = warmup_samples
        
        # Experience buffer for online learning
        self.feature_buffer: List[np.ndarray] = []
        self.label_buffer: List[int] = []
        
        self.samples_seen = 0
        self.updates_performed = 0
        
        logger.info(f"OnlineLearningUpdater initialized: update every {update_frequency} samples")
    
    def add_sample(self, features: np.ndarray, label: int, actual_outcome: Optional[int] = None):
        """
        Add a sample to the experience buffer.
        
        Args:
            features: Feature vector used for prediction
            label: Predicted label
            actual_outcome: Actual outcome (used when known)
        """
        # Use actual outcome if available, otherwise use prediction
        true_label = actual_outcome if actual_outcome is not None else label
        
        self.feature_buffer.append(features)
        self.label_buffer.append(true_label)
        self.samples_seen += 1
        
        # Trim buffer if too large
        if len(self.feature_buffer) > self.max_buffer_size:
            self.feature_buffer.pop(0)
            self.label_buffer.pop(0)
        
        # Check if update is needed
        if (self.samples_seen % self.update_frequency == 0 and 
            len(self.feature_buffer) >= self.warmup_samples):
            self._perform_update()
    
    def _perform_update(self):
        """Perform online model update."""
        try:
            X_buffer = np.array(self.feature_buffer)
            y_buffer = np.array(self.label_buffer)
            
            # Partial fit (if supported by model)
            if hasattr(self.model, 'partial_fit'):
                self.model.partial_fit(X_buffer, y_buffer)
                logger.info(f"Online update #{self.updates_performed + 1}: {len(X_buffer)} samples")
            
            # For XGBoost/sklearn without partial_fit, we would need to:
            # 1. Save current weights/parameters
            # 2. Train new model on combined old+new data
            # 3. Merge parameters (complex, model-specific)
            
            self.updates_performed += 1
            
        except Exception as e:
            logger.error(f"Online update failed: {e}")
    
    def get_update_stats(self) -> Dict[str, Any]:
        """Get statistics about online learning."""
        return {
            'samples_seen': self.samples_seen,
            'updates_performed': self.updates_performed,
            'buffer_size': len(self.feature_buffer),
            'buffer_fullness': len(self.feature_buffer) / self.max_buffer_size
        }


def calculate_reward(
    pnl: float,
    entry_price: float,
    exit_price: float,
    max_drawdown: float,
    holding_period: int,
    risk_free_rate: float = 0.0
) -> float:
    """
    Calculate risk-adjusted reward for RL agent.
    
    Combines multiple factors:
    - Raw PnL
    - Return relative to risk (drawdown)
    - Time efficiency (shorter is better)
    """
    # Raw return
    raw_return = (exit_price - entry_price) / entry_price
    
    # Risk-adjusted component (penalize drawdowns)
    if abs(max_drawdown) > 0:
        risk_adjustment = raw_return / abs(max_drawdown)
    else:
        risk_adjustment = raw_return
    
    # Time efficiency (prefer shorter trades)
    time_penalty = 0.01 * holding_period  # Small penalty per period
    
    # Combined reward
    reward = raw_return + 0.5 * risk_adjustment - time_penalty
    
    return float(reward)


# Example usage and integration pattern
if __name__ == "__main__":
    print("=" * 60)
    print("RL AGENT SKELETON DEMO")
    print("=" * 60)
    
    # Create Q-learning agent
    agent = QLearningAgent(
        state_bins=(5, 5, 5),
        n_actions=4,
        learning_rate=0.1,
        epsilon=0.1
    )
    
    # Simulate some trading episodes
    print("\nSimulating trading episodes:\n")
    
    np.random.seed(42)
    
    for episode in range(3):
        agent.reset()
        
        # Random initial state: [rsi_norm, macd_norm, volatility]
        state = np.random.rand(3)
        
        episode_reward = 0
        
        for step in range(10):
            # Select action
            action = agent.select_action(state, training=True)
            
            # Simulate environment response (random for demo)
            next_state = np.random.rand(3)
            reward = np.random.randn() * 0.1  # Random reward
            
            # Update agent
            agent.update(state, action, reward, next_state)
            
            state = next_state
            episode_reward += reward
        
        print(f"Episode {episode + 1}: Total reward = {episode_reward:.4f}")
    
    print()
    print("Q-table statistics:")
    print(f"  Number of states visited: {len(agent.q_table)}")
    print(f"  Actions per state: {agent.n_actions}")
    
    # Demo online learning updater
    print("\n" + "-" * 40)
    print("Online Learning Updater Demo:\n")
    
    # Mock model with partial_fit
    class MockModel:
        def partial_fit(self, X, y):
            print(f"    Model updated with {len(X)} samples")
    
    mock_model = MockModel()
    updater = OnlineLearningUpdater(
        model=mock_model,
        update_frequency=5,
        max_buffer_size=100,
        warmup_samples=5
    )
    
    # Add samples
    for i in range(15):
        features = np.random.rand(10)
        label = np.random.randint(0, 2)
        updater.add_sample(features, label)
    
    print(f"\nUpdater stats: {updater.get_update_stats()}")
    
    print("\n" + "=" * 60)
    print("Note: This is a skeleton/demo. For production use,")
    print("integrate with real market data and proper models.")
    print("=" * 60)
