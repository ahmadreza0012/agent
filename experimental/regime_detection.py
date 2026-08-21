"""
Market Regime Detection using Hidden Markov Models
Detects bull/bear/sideways/volatile market states
"""
import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

try:
    from hmmlearn import hmm
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False
    logger.warning("hmmlearn not available - using rule-based regime detection")


class MarketRegimeDetector:
    """
    Detects market regimes using Hidden Markov Model
    Supports: Bull, Bear, Sideways, Volatile
    """
    
    def __init__(self, n_regimes: int = 4, covariance_type: str = 'full'):
        self.n_regimes = n_regimes
        self.covariance_type = covariance_type
        self.model = None
        self.scaler = None
        
        self.regime_names = {
            0: 'Bull',
            1: 'Bear',
            2: 'Sideways',
            3: 'Volatile'
        }
        
        logger.info(f"MarketRegimeDetector initialized (n_regimes={n_regimes})")
    
    def extract_features(self, prices: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
        """
        Extract features for regime detection
        
        Args:
            prices: Price DataFrame
            returns: Returns DataFrame
            
        Returns:
            Feature matrix
        """
        features = pd.DataFrame(index=prices.index)
        
        # Mean return
        features['mean_return'] = returns.mean(axis=1)
        
        # Volatility (rolling)
        features['volatility'] = returns.std(axis=1)
        
        # Correlation (rolling)
        features['correlation'] = returns.rolling(24).corr().groupby(level=0).mean()
        features['correlation'].fillna(0, inplace=True)
        
        # Momentum (price change)
        features['momentum'] = prices.pct_change(24).mean(axis=1)
        
        # Trend strength (via price slope)
        for col in prices.columns:
            prices[col + '_slope'] = prices[col].rolling(24).apply(lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) > 0 else 0)
        
        slope_cols = [col for col in prices.columns if '_slope' in col]
        features['trend_strength'] = prices[slope_cols].mean(axis=1)
        
        features.fillna(0, inplace=True)
        return features
    
    def fit(self, features: pd.DataFrame):
        """
        Fit HMM to features
        
        Args:
            features: Feature matrix
        """
        if not HMM_AVAILABLE:
            logger.warning("HMM not available, skipping fit")
            return
        
        try:
            X = features.values
            # Normalize
            X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-8)
            
            self.model = hmm.GaussianHMM(n_components=self.n_regimes, covariance_type=self.covariance_type, n_iter=1000)
            self.model.fit(X)
            
            logger.info(f"HMM fitted with {self.n_regimes} regimes")
            logger.info(f"Log-likelihood: {self.model.score(X):.4f}")
        except Exception as e:
            logger.error(f"HMM fitting failed: {e}")
            self.model = None
    
    def predict(self, features: pd.DataFrame) -> pd.Series:
        """
        Predict regimes for features
        
        Args:
            features: Feature matrix
            
        Returns:
            Series of regime labels
        """
        if self.model is None:
            return self._rule_based_detection(features)
        
        try:
            X = features.values
            X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-8)
            regimes = self.model.predict(X)
            return pd.Series(regimes, index=features.index)
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return self._rule_based_detection(features)
    
    def _rule_based_detection(self, features: pd.DataFrame) -> pd.Series:
        """
        Rule-based regime detection fallback
        """
        regimes = []
        
        for idx, row in features.iterrows():
            mean_ret = row['mean_return']
            vol = row['volatility']
            momentum = row['momentum']
            
            # High volatility
            if vol > features['volatility'].quantile(0.75):
                regime = 3  # Volatile
            # Positive return + positive momentum
            elif mean_ret > features['mean_return'].median() and momentum > 0:
                regime = 0  # Bull
            # Negative return + negative momentum
            elif mean_ret < features['mean_return'].median() and momentum < 0:
                regime = 1  # Bear
            # Low volatility + near zero return
            else:
                regime = 2  # Sideways
            
            regimes.append(regime)
        
        return pd.Series(regimes, index=features.index)
    
    def get_regime_properties(self, regime: int) -> Dict:
        """
        Get optimal parameters for a regime
        
        Returns:
            Dictionary of regime properties
        """
        properties = {
            0: {  # Bull
                'leverage': 3.0,
                'strategy': 'momentum',
                'risk_limit': 0.25,
                'rebalance_freq': 'W',
                'long_ratio': 1.0
            },
            1: {  # Bear
                'leverage': 2.0,
                'strategy': 'short',
                'risk_limit': 0.20,
                'rebalance_freq': '2W',
                'long_ratio': 0.3
            },
            2: {  # Sideways
                'leverage': 1.0,
                'strategy': 'mean_reversion',
                'risk_limit': 0.15,
                'rebalance_freq': 'D',
                'long_ratio': 0.5
            },
            3: {  # Volatile
                'leverage': 1.5,
                'strategy': 'delta_neutral',
                'risk_limit': 0.20,
                'rebalance_freq': '3D',
                'long_ratio': 0.5
            }
        }
        
        return properties.get(regime, properties[2])


class RegimeAdaptiveStrategy:
    """
    Adapts trading strategy based on detected regime
    """
    
    OPTIMAL_STRATEGIES = {
        0: 'momentum',      # Bull: momentum following
        1: 'short',         # Bear: short selling
        2: 'mean_reversion', # Sideways: mean reversion
        3: 'delta_neutral'  # Volatile: hedged strategies
    }
    
    def get_optimal_strategy(self, regime: int) -> str:
        """
        Get optimal strategy for regime
        
        Args:
            regime: Regime label (0-3)
            
        Returns:
            Strategy name
        """
        return self.OPTIMAL_STRATEGIES.get(regime, 'risk_parity')
    
    def get_weights_adjustment(self, regime: int, base_weights: np.ndarray) -> np.ndarray:
        """
        Adjust portfolio weights based on regime
        
        Args:
            regime: Regime label
            base_weights: Base portfolio weights
            
        Returns:
            Adjusted weights
        """
        if regime == 0:  # Bull
            # Increase risk
            return np.clip(base_weights * 1.5, 0, 1)
        elif regime == 1:  # Bear
            # Reduce exposure, increase cash
            return np.clip(base_weights * 0.5, 0, 1)
        elif regime == 3:  # Volatile
            # Reduce concentration
            return np.ones_like(base_weights) / len(base_weights)
        else:  # Sideways
            return base_weights
