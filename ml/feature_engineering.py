import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from sklearn.preprocessing import StandardScaler
import logging
logger = logging.getLogger(__name__)

@dataclass
class FeatureConfig:
    windows: List[int] = field(default_factory=lambda: [5, 10, 20, 50])
    technical_indicators: List[str] = field(default_factory=lambda: ['rsi', 'macd', 'bb', 'atr'])
    use_price_features: bool = True; use_volume_features: bool = True
    use_returns_features: bool = True; use_lagged_features: bool = True
    max_lags: int = 5; use_rolling_stats: bool = True
    rolling_stats: List[str] = field(default_factory=lambda: ['mean', 'std', 'skew', 'kurt'])

class CausalFeatureEngineer:
    def __init__(self, config: Optional[FeatureConfig] = None):
        self.config = config or FeatureConfig()
        self.scalers = {}; self.is_fitted = False
    
    def calculate_features(self, data: pd.DataFrame, timestamp=None, lookback=100) -> Dict[str, float]:
        if timestamp is None: timestamp = data.index[-1]
        sliced = data[data.index <= timestamp]
        if len(sliced) < 2: return {}
        features = {}
        prices = sliced['close'] if 'close' in sliced else sliced.iloc[:, 0]
        volume = sliced['volume'] if 'volume' in sliced else None
        if self.config.use_price_features: features.update(self._price_features(prices))
        if self.config.use_returns_features and len(prices) > 1:
            returns = prices.pct_change().dropna()
            features.update(self._returns_features(returns))
        if self.config.use_volume_features and volume is not None:
            features.update(self._volume_features(volume))
        features.update(self._technical_indicators(prices, volume))
        if self.config.use_lagged_features:
            features.update(self._lagged_features(prices, returns if 'returns' in locals() else None))
        return features
    
    def _price_features(self, prices: pd.Series) -> Dict[str, float]:
        f = {}; latest = prices.iloc[-1]
        f['price'] = latest; f['price_log'] = np.log(latest + 1e-6)
        for w in self.config.windows:
            if len(prices) >= w:
                past = prices.iloc[-w]
                f[f'price_change_{w}d'] = (latest - past) / past
                f[f'price_pct_{w}d'] = (latest / past) - 1
        return f
    
    def _returns_features(self, returns: pd.Series) -> Dict[str, float]:
        f = {}
        for w in self.config.windows:
            if len(returns) >= w:
                r = returns.iloc[-w:]
                f[f'return_mean_{w}d'] = r.mean(); f[f'return_std_{w}d'] = r.std()
                f[f'return_skew_{w}d'] = r.skew(); f[f'return_kurt_{w}d'] = r.kurtosis()
                f[f'return_sharpe_{w}d'] = r.mean() / r.std() if r.std() > 0 else 0
                f[f'momentum_{w}d'] = (1 + r).prod() - 1
        return f
    
    def _volume_features(self, volume: pd.Series) -> Dict[str, float]:
        f = {}; latest = volume.iloc[-1]
        f['volume'] = latest; f['volume_log'] = np.log(latest + 1e-6)
        for w in self.config.windows:
            if len(volume) >= w:
                v = volume.iloc[-w:]
                f[f'volume_mean_{w}d'] = v.mean(); f[f'volume_std_{w}d'] = v.std()
                f[f'volume_ratio_{w}d'] = latest / v.mean() if v.mean() > 0 else 1
        return f
    
    def _technical_indicators(self, prices: pd.Series, volume=None) -> Dict[str, float]:
        f = {}
        if len(prices) < 20: return f
        if 'rsi' in self.config.technical_indicators and len(prices) >= 14:
            delta = prices.diff(); gain = delta.clip(lower=0); loss = (-delta).clip(lower=0)
            avg_gain = gain.rolling(14).mean(); avg_loss = loss.rolling(14).mean()
            rs = avg_gain / avg_loss; f['rsi_14'] = 100 - (100 / (1 + rs.iloc[-1])) if len(rs) > 0 else 50
        if 'bb' in self.config.technical_indicators and len(prices) >= 20:
            middle = prices.rolling(20).mean(); std = prices.rolling(20).std()
            upper = middle + (std * 2); lower = middle - (std * 2)
            f['bb_width'] = (upper.iloc[-1] - lower.iloc[-1]) / middle.iloc[-1] if middle.iloc[-1] > 0 else 0
        return f
    
    def _lagged_features(self, prices: pd.Series, returns=None) -> Dict[str, float]:
        f = {}
        for lag in range(1, self.config.max_lags + 1):
            if len(prices) > lag:
                f[f'price_lag_{lag}'] = prices.iloc[-lag]
                f[f'price_lag_{lag}_pct'] = (prices.iloc[-1] - prices.iloc[-lag]) / prices.iloc[-lag]
            if returns is not None and len(returns) > lag:
                f[f'return_lag_{lag}'] = returns.iloc[-lag]
        return f
    
    def fit_scalers(self, training_data: pd.DataFrame, features: List[str]) -> None:
        if len(training_data) == 0: raise ValueError("Training data is empty")
        self.scalers['standard'] = StandardScaler().fit(training_data[features])
        self.is_fitted = True
    
    def transform(self, data: pd.DataFrame, features: List[str]) -> pd.DataFrame:
        if not self.is_fitted: raise ValueError("Scalers must be fitted first")
        result = data[features].copy()
        return pd.DataFrame(self.scalers['standard'].transform(result), index=result.index, columns=[f'{c}_scaled' for c in result.columns])
