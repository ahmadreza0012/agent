"""
Regime Detection Module
Detects market regimes (Bull, Bear, Sideways, High Vol) using HMM
Enables adaptive strategy selection based on market conditions
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging

try:
    from hmmlearn import hmm
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False
    logging.warning("hmmlearn not available. Using fallback regime detection.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarketRegimeDetector:
    """
    Detect market regimes using Hidden Markov Models
    
    Regimes:
    - 0: Bull (trending up, low vol)
    - 1: Bear (trending down, high vol)  
    - 2: Sideways (range-bound)
    - 3: High Volatility (crisis/opportunity)
    """
    
    def __init__(self, n_regimes: int = 4, model_type: str = 'GaussianHMM'):
        """
        Initialize regime detector
        
        Args:
            n_regimes: Number of market regimes to detect
            model_type: HMM model type ('GaussianHMM', 'GMMHMM')
        """
        self.n_regimes = n_regimes
        self.model_type = model_type
        self.model = None
        self.regime_names = self._get_regime_names()
        
        logger.info(f"MarketRegimeDetector initialized: {n_regimes} regimes")
    
    def _get_regime_names(self) -> Dict[int, str]:
        """Map regime IDs to names"""
        if self.n_regimes == 2:
            return {0: 'Bear', 1: 'Bull'}
        elif self.n_regimes == 3:
            return {0: 'Bear', 1: 'Sideways', 2: 'Bull'}
        else:
            return {
                0: 'Bull Low Vol',
                1: 'Bear High Vol', 
                2: 'Sideways',
                3: 'High Volatility'
            }
    
    def extract_features(self, prices: pd.DataFrame,
                        returns: pd.DataFrame,
                        window: int = 168) -> pd.DataFrame:
        """
        Extract features for regime detection
        
        Args:
            prices: Price DataFrame
            returns: Returns DataFrame
            window: Lookback window (hours)
            
        Returns:
            Feature DataFrame
        """
        features = pd.DataFrame(index=returns.index)
        
        for col in returns.columns:
            # Return features
            features[f'{col}_return'] = returns[col]
            features[f'{col}_momentum'] = prices[col].pct_change(window)
            features[f'{col}_volatility'] = returns[col].rolling(window).std()
            
            # Trend strength
            ma_short = prices[col].rolling(24).mean()
            ma_long = prices[col].rolling(window).mean()
            features[f'{col}_trend'] = (ma_short - ma_long) / ma_long
            
            # Volume features (if available)
            vol_col = f'{col}_Volume'
            if vol_col in prices.columns:
                vol = prices[vol_col]
                features[f'{col}_volume_ma'] = vol.rolling(24).mean() / vol.rolling(window).mean()
        
        # Market-wide features
        mean_return = returns.mean(axis=1)
        mean_vol = returns.std(axis=1)
        
        features['market_return'] = mean_return
        features['market_volatility'] = mean_vol
        features['market_momentum'] = mean_return.rolling(window).mean()
        
        return features.dropna()
    
    def fit(self, features: pd.DataFrame) -> 'MarketRegimeDetector':
        """
        Fit HMM model to historical data
        
        Args:
            features: Feature DataFrame
            
        Returns:
            Self
        """
        if not HMM_AVAILABLE:
            logger.warning("hmmlearn not available. Using rule-based regime detection.")
            return self
        
        try:
            X = features.values
            
            if self.model_type == 'GaussianHMM':
                self.model = hmm.GaussianHMM(
                    n_components=self.n_regimes,
                    covariance_type='full',
                    n_iter=100,
                    random_state=42,
                    verbose=0
                )
            elif self.model_type == 'GMMHMM':
                self.model = hmm.GMMHMM(
                    n_components=self.n_regimes,
                    n_mix=2,
                    covariance_type='full',
                    n_iter=100,
                    random_state=42
                )
            else:
                raise ValueError(f"Unknown model type: {self.model_type}")
            
            logger.info(f"Fitting HMM with {len(X)} samples...")
            self.model.fit(X)
            
            logger.info("HMM fitting complete")
            
        except Exception as e:
            logger.error(f"HMM fitting failed: {e}. Using fallback.")
        
        return self
    
    def predict(self, features: pd.DataFrame) -> pd.Series:
        """
        Predict regime for each timestep
        
        Args:
            features: Feature DataFrame
            
        Returns:
            Series of regime labels
        """
        if self.model is None or not HMM_AVAILABLE:
            # Fallback: rule-based regime detection
            return self._rule_based_prediction(features)
        
        X = features.values
        regimes = self.model.predict(X)
        
        regime_series = pd.Series(regimes, index=features.index, name='regime')
        
        # Map to regime names
        regime_names = regime_series.map(self.regime_names)
        
        logger.info(f"Predicted regimes: {regime_series.value_counts().to_dict()}")
        
        return regime_series
    
    def _rule_based_prediction(self, features: pd.DataFrame) -> pd.Series:
        """
        Fallback rule-based regime detection
        
        Uses simple heuristics when HMM is unavailable
        """
        regimes = []
        
        for idx in features.index:
            row = features.loc[idx]
            
            # Get market-wide signals
            market_ret = row.get('market_return', 0)
            market_vol = row.get('market_volatility', 0)
            market_mom = row.get('market_momentum', 0)
            
            # Simple rules
            if market_vol > 0.02:  # High volatility threshold
                regime = 3  # High Volatility
            elif market_mom > 0.01 and market_ret > 0:
                regime = 0  # Bull
            elif market_mom < -0.01 and market_ret < 0:
                regime = 1  # Bear
            else:
                regime = 2  # Sideways
            
            regimes.append(regime)
        
        return pd.Series(regimes, index=features.index, name='regime')
    
    def get_regime_probability(self, features: pd.DataFrame) -> pd.DataFrame:
        """
        Get probability distribution over regimes
        
        Args:
            features: Feature DataFrame
            
        Returns:
            DataFrame with regime probabilities
        """
        if self.model is None or not HMM_AVAILABLE:
            # Return uniform distribution as fallback
            prob_df = pd.DataFrame(
                np.ones((len(features), self.n_regimes)) / self.n_regimes,
                index=features.index,
                columns=[f'regime_{i}' for i in range(self.n_regimes)]
            )
            return prob_df
        
        X = features.values
        probs = self.model.predict_proba(X)
        
        prob_df = pd.DataFrame(
            probs,
            index=features.index,
            columns=[f'regime_{i}' for i in range(self.n_regimes)]
        )
        
        return prob_df
    
    def get_current_regime(self, features: pd.DataFrame) -> Tuple[int, str]:
        """
        Get most recent regime
        
        Args:
            features: Feature DataFrame
            
        Returns:
            Tuple of (regime_id, regime_name)
        """
        regimes = self.predict(features)
        current_regime = regimes.iloc[-1]
        
        return current_regime, self.regime_names.get(current_regime, 'Unknown')
    
    def get_regime_duration(self, regimes: pd.Series) -> pd.DataFrame:
        """
        Analyze regime durations
        
        Args:
            regimes: Series of regime labels
            
        Returns:
            DataFrame with regime duration statistics
        """
        duration_stats = []
        
        current_regime = None
        start_idx = None
        
        for idx, regime in regimes.items():
            if regime != current_regime:
                if current_regime is not None:
                    duration = idx - start_idx
                    duration_stats.append({
                        'regime': current_regime,
                        'duration': duration,
                        'end': idx
                    })
                current_regime = regime
                start_idx = idx
        
        if current_regime is not None:
            duration_stats.append({
                'regime': current_regime,
                'duration': len(regimes) - start_idx,
                'end': 'ongoing'
            })
        
        stats_df = pd.DataFrame(duration_stats)
        
        if len(stats_df) > 0:
            summary = stats_df.groupby('regime')['duration'].agg(['mean', 'std', 'max', 'min'])
        else:
            summary = pd.DataFrame()
        
        return summary


class RegimeAdaptiveStrategy:
    """
    Strategy selector that adapts to detected market regimes
    
    Maps regimes to optimal strategies:
    - Bull: Momentum, growth tilt
    - Bear: Defensive, risk parity
    - Sideways: Mean reversion
    - High Vol: Risk-off, CVaR optimization
    """
    
    def __init__(self):
        """Initialize regime-adaptive strategy mapper"""
        self.regime_strategy_map = {
            0: 'momentum',      # Bull
            1: 'risk_parity',   # Bear
            2: 'mean_reversion', # Sideways
            3: 'cvar'           # High Vol
        }
        
        self.regime_weights = {
            0: {'risk_appetite': 1.0, 'leverage': 1.0},
            1: {'risk_appetite': 0.5, 'leverage': 0.5},
            2: {'risk_appetite': 0.7, 'leverage': 0.8},
            3: {'risk_appetite': 0.3, 'leverage': 0.3}
        }
        
        logger.info("RegimeAdaptiveStrategy initialized")
    
    def get_optimal_strategy(self, regime: int) -> str:
        """
        Get optimal strategy for given regime
        
        Args:
            regime: Regime ID
            
        Returns:
            Strategy name
        """
        return self.regime_strategy_map.get(regime, 'equal_weight')
    
    def get_risk_parameters(self, regime: int) -> Dict:
        """
        Get risk parameters for given regime
        
        Args:
            regime: Regime ID
            
        Returns:
            Dictionary with risk parameters
        """
        return self.regime_weights.get(regime, {
            'risk_appetite': 0.5,
            'leverage': 0.5
        })
    
    def adjust_position_sizing(self, base_weights: np.ndarray,
                               regime: int) -> np.ndarray:
        """
        Adjust position sizes based on regime
        
        Args:
            base_weights: Base portfolio weights
            regime: Current regime
            
        Returns:
            Adjusted weights
        """
        params = self.get_risk_parameters(regime)
        
        # Scale positions by risk appetite
        adjusted = base_weights * params['risk_appetite']
        
        # Ensure sum to 1 (remaining in cash)
        cash_weight = 1 - adjusted.sum()
        if cash_weight > 0:
            adjusted = np.append(adjusted, cash_weight)
        
        return adjusted


if __name__ == "__main__":
    # Test regime detection
    np.random.seed(42)
    
    # Generate sample data with different regimes
    n_periods = 1000
    n_assets = 3
    
    # Simulate regime changes
    regimes = np.zeros(n_periods, dtype=int)
    regimes[:300] = 0  # Bull
    regimes[300:500] = 1  # Bear
    regimes[500:700] = 2  # Sideways
    regimes[700:] = 3  # High vol
    
    # Generate returns based on regimes
    returns_data = np.random.randn(n_periods, n_assets) * 0.01
    for i in range(n_periods):
        if regimes[i] == 0:  # Bull
            returns_data[i] += 0.002
        elif regimes[i] == 1:  # Bear
            returns_data[i] -= 0.003
            returns_data[i] *= 1.5  # Higher vol
        elif regimes[i] == 3:  # High vol
            returns_data[i] *= 3
    
    prices_data = 100 * np.exp(np.cumsum(returns_data, axis=0))
    
    dates = pd.date_range('2024-01-01', periods=n_periods, freq='H')
    prices = pd.DataFrame(prices_data, index=dates, columns=['BTC', 'ETH', 'SOL'])
    returns = prices.pct_change().dropna()
    
    # Test regime detector
    detector = MarketRegimeDetector(n_regimes=4)
    features = detector.extract_features(prices, returns)
    
    if HMM_AVAILABLE:
        detector.fit(features)
        predicted_regimes = detector.predict(features)
        
        print("\n=== Regime Detection Results ===")
        print(predicted_regimes.value_counts())
        
        current_regime, current_name = detector.get_current_regime(features)
        print(f"\nCurrent Regime: {current_regime} ({current_name})")
    else:
        # Test fallback
        predicted_regimes = detector._rule_based_prediction(features)
        print("\n=== Rule-Based Regime Detection ===")
        print(predicted_regimes.value_counts())
    
    # Test regime-adaptive strategy
    adaptive = RegimeAdaptiveStrategy()
    
    for regime_id in range(4):
        strategy = adaptive.get_optimal_strategy(regime_id)
        params = adaptive.get_risk_parameters(regime_id)
        print(f"\nRegime {regime_id}: Strategy={strategy}, Risk={params}")
